from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_actual(raw: dict[str, Any]) -> dict[str, float]:
    actual: dict[str, float] = {}
    for name, value in raw.items():
        if isinstance(value, dict):
            if "available" in value:
                actual[name] = float(value["available"])
            elif "free" in value:
                actual[name] = float(value["free"])
            elif "remaining" in value:
                actual[name] = float(value["remaining"])
            elif "total" in value and "used" in value:
                actual[name] = float(value["total"]) - float(value["used"])
        else:
            actual[name] = float(value)
    return actual


def load_actual(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig") as file_obj:
        return normalize_actual(json.load(file_obj))


def load_envs(path: Path | None) -> dict[str, dict[str, float]]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig") as file_obj:
        raw = json.load(file_obj)

    envs: dict[str, dict[str, float]] = {}
    for env_name, env_actual in raw.items():
        if not isinstance(env_actual, dict):
            raise SystemExit(f"环境 {env_name!r} 的值必须是资源字典")
        envs[env_name] = normalize_actual(env_actual)
    return envs
