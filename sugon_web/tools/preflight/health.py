from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .health_models import EnvironmentHealthResult, HealthFinding


DEFAULT_HEALTH_RULES = Path(__file__).resolve().parent / "profiles" / "health_rules.yaml"


def load_health_input(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file_obj:
        raw = json.load(file_obj)
    if any(key in raw for key in ("frontend", "backend", "inspection", "frontend_ok")):
        return {"default": raw}
    return raw


def load_health_rules(path: Path | None = None) -> dict[str, Any]:
    rules_path = path or DEFAULT_HEALTH_RULES
    with rules_path.open("r", encoding="utf-8-sig") as file_obj:
        return yaml.safe_load(file_obj)


def evaluate_health_env(env_name: str, snapshot: dict[str, Any], rules: dict[str, Any]) -> EnvironmentHealthResult:
    result = EnvironmentHealthResult(env_name=env_name)
    for check_name, rule in rules.get("checks", {}).items():
        finding = _evaluate_rule(check_name, snapshot, rule)
        result.findings.append(finding)
    return result


def evaluate_health_envs(
    snapshots: dict[str, dict[str, Any]],
    rules: dict[str, Any],
) -> list[EnvironmentHealthResult]:
    return [
        evaluate_health_env(env_name, snapshot, rules)
        for env_name, snapshot in sorted(snapshots.items())
    ]


def _evaluate_rule(check_name: str, snapshot: dict[str, Any], rule: dict[str, Any]) -> HealthFinding:
    actual = _first_present(snapshot, rule.get("paths", []))
    required = bool(rule.get("required", True))
    severity = str(rule.get("severity", "fail")).upper()
    fail_status = "WARN" if severity == "WARN" else "FAIL"

    if actual is None:
        if required:
            return HealthFinding(check_name, "UNKNOWN", expected=_expected_text(rule), detail="未采集到该检查项")
        return HealthFinding(check_name, "OK", actual=None, expected="optional")

    if "equals" in rule:
        expected = rule["equals"]
        if actual == expected:
            return HealthFinding(check_name, "OK", actual=actual, expected=str(expected))
        return HealthFinding(check_name, fail_status, actual=actual, expected=str(expected), detail="实际值不符合预期")

    if "max" in rule:
        max_value = float(rule["max"])
        try:
            actual_value = float(actual)
        except (TypeError, ValueError):
            return HealthFinding(check_name, "FAIL", actual=actual, expected=f"<= {max_value:g}", detail="实际值不是数字")
        if actual_value <= max_value:
            return HealthFinding(check_name, "OK", actual=actual, expected=f"<= {max_value:g}")
        return HealthFinding(check_name, fail_status, actual=actual, expected=f"<= {max_value:g}", detail="超过阈值")

    if "one_of" in rule:
        expected_values = rule["one_of"]
        if actual in expected_values:
            return HealthFinding(check_name, "OK", actual=actual, expected=", ".join(map(str, expected_values)))
        return HealthFinding(check_name, fail_status, actual=actual, expected=", ".join(map(str, expected_values)))

    return HealthFinding(check_name, "OK", actual=actual, expected=_expected_text(rule))


def _first_present(snapshot: dict[str, Any], paths: list[str]) -> Any:
    for path in paths:
        value = _get_path(snapshot, path)
        if value is not None:
            return value
    return None


def _get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _expected_text(rule: dict[str, Any]) -> str:
    if "equals" in rule:
        return str(rule["equals"])
    if "max" in rule:
        return f"<= {float(rule['max']):g}"
    if "one_of" in rule:
        return ", ".join(map(str, rule["one_of"]))
    return ""
