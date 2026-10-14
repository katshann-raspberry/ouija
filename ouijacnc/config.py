from __future__ import annotations

import json
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

    characters = {
        key.upper(): _coordinate(value, f"characters.{key}")
        for key, value in char_config.get("characters", {}).items()
    }
    positions = {
        key: _coordinate(value, f"positions.{key}")
        for key, value in char_config.get("positions", {}).items()
    }

    return AppConfig(settings=settings, characters=characters, positions=positions)


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
        return Coordinate(x=float(value["x"]), y=float(value["y"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain numeric x and y") from exc
