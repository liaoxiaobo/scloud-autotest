from __future__ import annotations

from .models import EnvironmentResult, Requirement
from .report import format_value


def evaluate_env(requirements: dict[str, Requirement], actual: dict[str, float]) -> EnvironmentResult:
    missing: list[str] = []
    for req in requirements.values():
        actual_value = actual.get(req.name)
        if actual_value is None:
            missing.append(f"{req.name}: 未采集，需 {format_value(req.value)} {req.unit}".strip())
        elif actual_value < req.value:
            missing.append(
                f"{req.name}: 需 {format_value(req.value)} {req.unit}, "
                f"可用 {format_value(actual_value)} {req.unit}, "
                f"缺 {format_value(req.value - actual_value)} {req.unit}"
            )
    return EnvironmentResult(name="", passed=not missing, missing=missing)


def evaluate_envs(
    requirements: dict[str, Requirement],
    envs: dict[str, dict[str, float]],
) -> list[EnvironmentResult]:
    results: list[EnvironmentResult] = []
    for env_name, actual in sorted(envs.items()):
        result = evaluate_env(requirements, actual)
        result.name = env_name
        results.append(result)
    return results
