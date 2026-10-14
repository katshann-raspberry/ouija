from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@dataclass(frozen=True)
class Coordinate:
    x: float
    y: float


@dataclass(frozen=True)
class AppConfig:
    settings: dict[str, Any]
    characters: dict[str, Coordinate]
    positions: dict[str, Coordinate]


def load_config() -> AppConfig:
    settings = _read_json(CONFIG_DIR / "settings.json")
    char_config = _read_json(CONFIG_DIR / "characters.json")

    characters = _coordinates(char_config.get("letters", {}), "letters", str.upper)
    positions = _coordinates(char_config.get("buttons", {}), "buttons", str.lower)

    return AppConfig(settings=settings, characters=characters, positions=positions)


def _coordinates(entries: Any, label: str, normalize: Any) -> dict[str, Coordinate]:
    if not isinstance(entries, dict):
        raise ValueError(f"{label} must be a JSON object")
    result = {}
    for key, value in entries.items():
        # The mapping keeps unmeasured locations as pairs of empty strings.
        if isinstance(value, dict) and value.get("x") == "" and value.get("y") == "":
            continue
        result[normalize(key)] = _coordinate(value, f"{label}.{key}")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _coordinate(value: Any, label: str) -> Coordinate:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object with x and y")
    try:
        coord = Coordinate(x=float(value["x"]), y=float(value["y"]))
        if not math.isfinite(coord.x) or not math.isfinite(coord.y):
            raise ValueError("Coordinates must be finite")
        return coord
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain numeric x and y") from exc
