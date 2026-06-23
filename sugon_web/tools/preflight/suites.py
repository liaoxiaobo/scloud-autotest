from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_SUITES = Path(__file__).resolve().parent / "profiles" / "check_suites.yaml"


def load_suites(path: Path | None = None) -> dict[str, Any]:
    suites_path = path or DEFAULT_SUITES
    with suites_path.open("r", encoding="utf-8-sig") as file_obj:
        return yaml.safe_load(file_obj) or {}


def resolve_suite(
    suite_name: str,
    suites: dict[str, Any],
    available_modules: list[str],
    available_checks: list[str],
) -> dict[str, list[str]]:
    suite = suites.get("suites", {}).get(suite_name)
    if suite is None:
        known = ", ".join(sorted(suites.get("suites", {})))
        raise SystemExit(f"未知检查关键词: {suite_name}。可选关键词: {known}")

    return {
        "resource_modules": _expand_names(
            suite.get("resource_modules", []),
            available_modules,
            label="资源模块",
        ),
        "health_checks": _expand_names(
            suite.get("health_checks", []),
            available_checks,
            label="健康检查项",
        ),
        "pytest_marks": list(suite.get("pytest_marks", [])),
    }


def filter_health_rules(rules: dict[str, Any], check_names: list[str]) -> dict[str, Any]:
    if not check_names:
        return {"checks": {}}
    available = rules.get("checks", {})
    unknown = sorted(set(check_names) - set(available))
    if unknown:
        raise SystemExit(f"未知健康检查项: {', '.join(unknown)}")
    return {
        **rules,
        "checks": {
            check_name: available[check_name]
            for check_name in check_names
        },
    }


def _expand_names(raw_names: list[str], available: list[str], label: str) -> list[str]:
    names: list[str] = []
    for raw_name in raw_names:
        if raw_name == "all":
            names.extend(available)
        elif raw_name in available:
            names.append(raw_name)
        else:
            raise SystemExit(f"未知{label}: {raw_name}。可选值: {', '.join(available)}")

    deduped: list[str] = []
    seen = set()
    for name in names:
        if name not in seen:
            deduped.append(name)
            seen.add(name)
    return deduped
