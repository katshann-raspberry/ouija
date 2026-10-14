from __future__ import annotations

import os
import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from .config import AppConfig, Coordinate, load_config

try:
    import serial
except ImportError:  # pragma: no cover - startup will report a useful error.
    serial = None


STATUS_RE = re.compile(r"^<([^|>]+)")


JobKind = Literal["text", "restart", "position"]
POSITION_COMMANDS = ("yes", "no", "goodbye")


@dataclass
class QueuedJob:
    kind: JobKind
    text: str = ""
    position: str = ""


@dataclass
class ControllerSnapshot:
    connected: bool = False
    machine_state: str = "unknown"
    busy: bool = False
    queue_depth: int = 0
    last_error: str | None = None
    active_job: str | None = None
    log: list[str] = field(default_factory=list)


class Controller:
    def __init__(self) -> None:
        self.config: AppConfig = load_config()
        self.jobs: queue.Queue[QueuedJob] = queue.Queue()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.serial_conn = None
        self.connected = False
        self.machine_state = "unknown"
        self.busy = False
        self.active_job: str | None = None
        self.last_error: str | None = None
        self.log: deque[str] = deque(maxlen=200)
        self.dry_run = os.environ.get("OUIJACNC_DRY_RUN") == "1"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="ouijacnc-controller", daemon=True)
        self.thread.start()

    def submit_text(self, text: str) -> None:
        self.jobs.put(QueuedJob(kind="text", text=text))

    def restart(self) -> None:
        self.jobs.put(QueuedJob(kind="restart"))

    def submit_position(self, name: str) -> None:
        name = name.lower()
        self._validate_position(name)
        self.jobs.put(QueuedJob(kind="position", position=name))

    def _validate_position(self, name: str) -> None:
        if name not in POSITION_COMMANDS or name not in self.config.positions:
            raise ValueError(f"Position '{name}' is not available")

    def snapshot(self) -> ControllerSnapshot:
        with self.lock:
            return ControllerSnapshot(
                connected=self.connected,
                machine_state=self.machine_state,
                busy=self.busy,
                queue_depth=self.jobs.qsize(),
                last_error=self.last_error,
                active_job=self.active_job,
                log=list(self.log),
            )

    def validate_text(self, text: str) -> list[str]:
        unknown = []
        for char in text.upper():
            if char.isspace():
                continue
            if char not in self.config.characters and char not in unknown:
                unknown.append(char)
        return unknown

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._ensure_connected()
                self._initialize()
                break
            except Exception as exc:
                self._set_error(f"Connect/init failed: {exc}")
                time.sleep(3)

        while not self.stop_event.is_set():
            try:
                job = self.jobs.get(timeout=0.5)
            except queue.Empty:
                self._poll_status_quietly()
                continue

            try:
                with self.lock:
                    self.busy = True
                    self.active_job = (
                        "restart" if job.kind == "restart" else
                        job.position.title() if job.kind == "position" else job.text
                    )
                    self.last_error = None

                self._ensure_connected()
                if job.kind == "restart":
                    self._initialize()
                elif job.kind == "position":
                    self._run_position(job.position)
                else:
                    self._run_text(job.text)
            except Exception as exc:
                self._set_error(str(exc))
                self._close_serial()
            finally:
                with self.lock:
                    self.busy = False
                    self.active_job = None
                self.jobs.task_done()

    def _ensure_connected(self) -> None:
        if self.dry_run:
            with self.lock:
                self.connected = True
                self.machine_state = "dry-run"
            return

        if self.serial_conn and getattr(self.serial_conn, "is_open", False):
            return
        if serial is None:
            raise RuntimeError("pyserial is not installed")

        serial_config = self.config.settings["serial"]
        self._log(f"Opening {serial_config['port']} at {serial_config['baudrate']}")
        self.serial_conn = serial.Serial(
            port=serial_config["port"],
            baudrate=int(serial_config["baudrate"]),
            timeout=float(serial_config.get("timeout_seconds", 1.0)),
            write_timeout=float(serial_config.get("write_timeout_seconds", 1.0)),
        )
        time.sleep(2.0)
        self.serial_conn.reset_input_buffer()
        self.serial_conn.reset_output_buffer()
        with self.lock:
            self.connected = True

    def _initialize(self) -> None:
        self.config = load_config()
        startup = self.config.settings.get("startup", {})
        self._log("Initializing controller")
        if startup.get("unlock_before_home", False):
            self._send_line("$X")
        if startup.get("home_on_connect", True):
            self._send_line("$H", timeout=120)
            self._wait_until_idle(timeout=120)
        for command in self.config.settings.get("gcode", {}).get("setup", []):
            self._send_line(command)
        if startup.get("move_to_start_after_home", True):
            self._move_named_position("start")

    def _run_text(self, text: str) -> None:
        self.config = load_config()
        text = text.upper()
        unknown = self.validate_text(text)
        if unknown and self.config.settings["safety"].get("require_known_characters", True):
            raise ValueError(f"Unsupported characters: {', '.join(unknown)}")

        words = [word for word in re.split(r"\s+", text.strip()) if word]
        if not words:
            return

        for word in words:
            for char in word:
                coord = self.config.characters.get(char)
                if coord is None:
                    continue
                self._move(coord, label=char)
                self._dwell(self.config.settings["gcode"].get("char_dwell_seconds", 0.0))
            self._move_named_position("goodbye")
            self._dwell(self.config.settings["gcode"].get("word_pause_seconds", 0.0))

    def _run_position(self, name: str) -> None:
        self.config = load_config()
        self._validate_position(name)
        self._move_named_position(name)

    def _move_named_position(self, name: str) -> None:
        coord = self.config.positions.get(name)
        if coord is None:
            self._log(f"Named position '{name}' is not configured; skipping")
            return
        self._move(coord, label=name)

    def _move(self, coord: Coordinate, label: str) -> None:
        self._validate_bounds(coord, label)
        template = self.config.settings["gcode"]["move_template"]
        self._send_line(template.format(x=coord.x, y=coord.y, label=label))
        self._wait_until_idle(timeout=60)

    def _validate_bounds(self, coord: Coordinate, label: str) -> None:
        bounds = self.config.settings.get("safety", {}).get("bounds", {})
        checks = (
            ("x_min", coord.x >= float(bounds.get("x_min", coord.x))),
            ("x_max", coord.x <= float(bounds.get("x_max", coord.x))),
            ("y_min", coord.y >= float(bounds.get("y_min", coord.y))),
            ("y_max", coord.y <= float(bounds.get("y_max", coord.y))),
        )
        failed = [name for name, ok in checks if not ok]
        if failed:
            raise ValueError(f"{label} coordinate {coord} is outside configured bounds: {failed}")

    def _dwell(self, seconds: float | int | str) -> None:
        seconds = float(seconds)
        if seconds <= 0:
            return
        self._send_line(f"G4 P{seconds:.3f}")

    def _send_line(self, line: str, timeout: float = 30) -> None:
        line = line.strip()
        if not line:
            return
        self._log(f"> {line}")
        if self.dry_run:
            self._log("< ok")
            return

        self.serial_conn.write((line + "\r\n").encode("ascii"))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = self._readline()
            if response is None:
                continue
            if response.startswith("<"):
                self._record_status(response)
                continue
            self._log(f"< {response}")
            lower = response.lower()
            if lower == "ok":
                return
            if lower.startswith("error") or lower.startswith("alarm"):
                raise RuntimeError(f"FluidNC rejected '{line}': {response}")
        raise TimeoutError(f"Timed out waiting for ok after '{line}'")

    def _wait_until_idle(self, timeout: float) -> None:
        if self.dry_run:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self._query_status()
            if state and state.lower() == "idle":
                return
            time.sleep(0.2)
        raise TimeoutError("Timed out waiting for FluidNC to become idle")

    def _query_status(self) -> str | None:
        self.serial_conn.write(b"?")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            response = self._readline()
            if response is None:
                continue
            if response.startswith("<"):
                return self._record_status(response)
            self._log(f"< {response}")
        return None

    def _poll_status_quietly(self) -> None:
        if not self.connected or self.dry_run or self.busy:
            return
        try:
            self._query_status()
        except Exception as exc:
            self._set_error(f"Status poll failed: {exc}")
            self._close_serial()

    def _record_status(self, response: str) -> str | None:
        self._log(f"< {response}")
        match = STATUS_RE.match(response)
        if not match:
            return None
        state = match.group(1)
        with self.lock:
            self.machine_state = state
        return state

    def _readline(self) -> str | None:
        raw = self.serial_conn.readline()
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace").strip()

    def _close_serial(self) -> None:
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.serial_conn = None
        with self.lock:
            self.connected = False
            self.machine_state = "disconnected"

    def _set_error(self, message: str) -> None:
        with self.lock:
            self.last_error = message
        self._log(f"! {message}")

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        with self.lock:
            self.log.append(f"{timestamp} {message}")


controller = Controller()
