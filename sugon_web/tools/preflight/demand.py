from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Requirement


DEFAULT_PROFILE = Path(__file__).resolve().parent / "profiles" / "resource_requirements.yaml"
LEGACY_PROFILE = Path(__file__).resolve().parents[2] / "config" / "resource_preflight.yaml"


def resolve_profile(path: str | None = None) -> Path:
    """Return the explicit, packaged, or legacy profile path."""
    if path:
        return Path(path)
    if DEFAULT_PROFILE.exists():
        return DEFAULT_PROFILE
    return LEGACY_PROFILE


def load_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file_obj:
        return yaml.safe_load(file_obj)


def parse_modules(raw: str, available_modules: list[str]) -> list[str]:
    if raw == "all":
        return available_modules
    modules = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(modules) - set(available_modules))
    if unknown:
        raise SystemExit(f"未知模块: {', '.join(unknown)}。可选模块: {', '.join(available_modules)}")
    return modules


def resource_from_entry(name: str, entry: dict[str, Any]) -> Requirement:
    return Requirement(
        name=name,
        value=float(entry.get("value", 0)),
        unit=str(entry.get("unit", "")),
        scale_with_workers=bool(entry.get("scale_with_workers", True)),
        note=str(entry.get("note", "")),
    )


def aggregate_requirements(profile: dict[str, Any], modules: list[str], mode: str) -> dict[str, Requirement]:
    aggregated: dict[str, Requirement] = {}

    for module in modules:
        resources = profile["module_peak"][module].get("resources", {})
        for name, entry in resources.items():
            req = resource_from_entry(name, entry)
            current = aggregated.get(name)
            if current is None:
                aggregated[name] = req
                continue
            if mode == "sum":
                current.value += req.value
                current.note = "; ".join(item for item in [current.note, req.note] if item)
                current.scale_with_workers = current.scale_with_workers or req.scale_with_workers
            elif mode == "max":
                if req.value > current.value:
                    aggregated[name] = req
            else:
                raise SystemExit(f"不支持的聚合模式: {mode}")

    return dict(sorted(aggregated.items()))


def scale_requirements(
    requirements: dict[str, Requirement],
    workers: int,
    safety: float,
) -> dict[str, Requirement]:
    return {
        name: req.scaled(workers=workers, safety=safety)
        for name, req in requirements.items()
    }
