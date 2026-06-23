from __future__ import annotations

from typing import Any

from .models import EnvironmentResult, Requirement


def format_value(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(str(row[index])) for row in [headers, *rows])
        for index in range(len(headers))
    ]
    print(" | ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(row[index]).ljust(widths[index]) for index in range(len(headers))))


def print_requirements(requirements: dict[str, Requirement], actual: dict[str, float]) -> int:
    headers = ["资源项", "需要", "单位", "实际可用", "结果", "备注"]
    rows: list[list[str]] = []
    exit_code = 0

    for req in requirements.values():
        actual_value = actual.get(req.name)
        if actual_value is None:
            actual_text = "-"
            result = "未检查"
        elif actual_value >= req.value:
            actual_text = format_value(actual_value)
            result = "OK"
        else:
            actual_text = format_value(actual_value)
            result = f"不足 {format_value(req.value - actual_value)}"
            exit_code = 2

        rows.append([
            req.name,
            format_value(req.value),
            req.unit,
            actual_text,
            result,
            req.note,
        ])

    _print_table(headers, rows)
    return exit_code


def print_env_matrix(results: list[EnvironmentResult]) -> int:
    rows: list[list[str]] = []
    exit_code = 2

    for result in results:
        if result.passed:
            exit_code = 0
            rows.append([result.name, "满足", "-", ""])
        else:
            rows.append([result.name, "不满足", str(len(result.missing)), "; ".join(result.missing[:5])])

    _print_table(["环境", "结论", "缺口项数", "主要缺口(最多5项)"], rows)

    passed = [result.name for result in results if result.passed]
    print()
    if passed:
        print(f"可执行环境: {', '.join(passed)}")
    else:
        print("可执行环境: 无")
    return exit_code


def print_quota_max(profile: dict[str, Any]) -> None:
    print("\nIAM 配额最大值口径:")
    for group_name, quotas in profile.get("iam_quota_max", {}).items():
        print(f"\n[{group_name}]")
        for quota_name, entry in quotas.items():
            service = entry.get("service", "")
            value = entry.get("value", "")
            unit = entry.get("unit", "")
            print(f"- {quota_name}: {value} {unit} ({service})")
