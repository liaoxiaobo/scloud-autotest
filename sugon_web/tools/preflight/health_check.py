from __future__ import annotations

import argparse
import json
from pathlib import Path

from .health import evaluate_health_envs, load_health_input, load_health_rules
from .health_models import EnvironmentHealthResult
from .suites import filter_health_rules, load_suites, resolve_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自动化运行前环境健康巡检统计")
    parser.add_argument("--health-json", required=True, help="健康巡检结果 JSON，可为单环境或多环境")
    parser.add_argument("--rules", help="健康巡检规则 YAML，默认使用 profiles/health_rules.yaml")
    parser.add_argument("--suite", help="检查关键词，如 frontend/backend/inspection/health/all")
    parser.add_argument("--checks", help="显式健康检查项，逗号分隔；优先级高于 --suite")
    parser.add_argument("--suites", help="关键词展开配置 YAML，默认使用 profiles/check_suites.yaml")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出统计结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rules = load_health_rules(Path(args.rules) if args.rules else None)
    checks = _resolve_checks(args, rules)
    if checks is not None:
        rules = filter_health_rules(rules, checks)
    snapshots = load_health_input(Path(args.health_json))
    results = evaluate_health_envs(snapshots, rules)

    if args.json:
        print(json.dumps(_to_json(results), ensure_ascii=False, indent=2))
    else:
        _print_matrix(results)

    return 0 if any(result.passed for result in results) else 2


def _resolve_checks(args: argparse.Namespace, rules: dict[str, object]) -> list[str] | None:
    available_checks = list(rules.get("checks", {}))
    if args.checks:
        return [item.strip() for item in args.checks.split(",") if item.strip()]
    if args.suite:
        suites = load_suites(Path(args.suites) if args.suites else None)
        expanded = resolve_suite(
            args.suite,
            suites,
            available_modules=[],
            available_checks=available_checks,
        )
        return expanded["health_checks"]
    return None


def _to_json(results: list[EnvironmentHealthResult]) -> dict[str, object]:
    return {
        result.env_name: {
            "passed": result.passed,
            "failed": len(result.failed),
            "warnings": len(result.warnings),
            "unknown": len(result.unknown),
            "findings": [
                {
                    "check": finding.check,
                    "status": finding.status,
                    "actual": finding.actual,
                    "expected": finding.expected,
                    "detail": finding.detail,
                }
                for finding in result.findings
            ],
        }
        for result in results
    }


def _print_matrix(results: list[EnvironmentHealthResult]) -> None:
    rows: list[list[str]] = []
    for result in results:
        conclusion = "健康" if result.passed else "不健康"
        main_findings = result.failed + result.unknown + result.warnings
        rows.append([
            result.env_name,
            conclusion,
            str(len(result.failed)),
            str(len(result.warnings)),
            str(len(result.unknown)),
            "; ".join(
                f"{finding.check}: {finding.status}, 实际={finding.actual}, 期望={finding.expected}"
                for finding in main_findings[:5]
            ),
        ])

    headers = ["环境", "结论", "失败项", "告警项", "未采集", "主要问题(最多5项)"]
    widths = [
        max(len(str(row[index])) for row in [headers, *rows])
        for index in range(len(headers))
    ]
    print(" | ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(row[index]).ljust(widths[index]) for index in range(len(headers))))

    passed = [result.env_name for result in results if result.passed]
    print()
    print(f"可执行健康环境: {', '.join(passed) if passed else '无'}")


if __name__ == "__main__":
    raise SystemExit(main())
