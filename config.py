"""Persistent user config stored in ~/.screenshot_tool/config.json."""

import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / ".screenshot_tool" / "config.json"


def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = CONFIG_FILE.with_name(f"{CONFIG_FILE.name}.tmp")
    tmp_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp_file, CONFIG_FILE)
