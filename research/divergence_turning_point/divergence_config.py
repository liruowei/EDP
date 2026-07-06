from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).with_name("config.json")


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def path_value(value: str) -> Path:
    return Path(value)


def data_path(config: dict[str, Any], *parts: str) -> Path:
    return path_value(str(config["data_dir"])).joinpath(*parts)

