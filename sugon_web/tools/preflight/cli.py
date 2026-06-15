from __future__ import annotations

import argparse
import json
from pathlib import Path

from .collectors.static_json import load_actual, load_envs
from .demand import (
    aggregate_requirements,
    load_profile,
    parse_modules,
    resolve_profile,
    scale_requirements,
)
from .matrix import evaluate_envs
from .report import print_env_matrix, print_quota_max, print_requirements
from .suites import load_suites, resolve_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自动化运行前资源前置检查")
    parser.add_argument("--profile", help="资源画像 YAML 路径")
    parser.add_argument("--suite", help="检查关键词，如 network/storage/all/resource")
    parser.add_argument("--suites", help="关键词展开配置 YAML，默认使用 profiles/check_suites.yaml")
    parser.add_argument("--modules", default="all", help="模块列表，如 all 或 network,storage")
    parser.add_argument("--mode", choices=["max", "sum"], default="sum", help="聚合方式：max=串行峰值，sum=保守总量")
    parser.add_argument("--workers", type=int, default=1, help="pytest-xdist worker 数")
    parser.add_argument("--safety", type=float, default=1.0, help="安全系数，如 1.2")
    parser.add_argument("--actual-json", help="单个环境的实际可用资源 JSON，用于判定 OK/不足")
    parser.add_argument("--envs-json", help="多个环境的实际可用资源 JSON，用于输出环境适配矩阵")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出需要的资源")
    parser.add_argument("--show-quota-max", action="store_true", help="同时输出 IAM 配额最大值")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile_path = resolve_profile(args.profile)
    profile = load_profile(profile_path)
    available_modules = sorted(profile.get("module_peak", {}))
    modules = _resolve_modules(args, available_modules)
    requirements = aggregate_requirements(profile, modules, args.mode)
    scaled_requirements = scale_requirements(requirements, workers=args.workers, safety=args.safety)

    if args.json:
        print(json.dumps({
            name: {
                "required": req.value,
                "unit": req.unit,
                "scale_with_workers": req.scale_with_workers,
                "note": req.note,
            }
            for name, req in scaled_requirements.items()
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"资源画像: {profile_path}")
    print(f"模块: {', '.join(modules)}")
    print(f"聚合模式: {args.mode}; workers={args.workers}; safety={args.safety}")

    if args.envs_json:
        results = evaluate_envs(scaled_requirements, load_envs(Path(args.envs_json)))
        exit_code = print_env_matrix(results)
    else:
        actual = load_actual(Path(args.actual_json) if args.actual_json else None)
        exit_code = print_requirements(scaled_requirements, actual)

    if args.show_quota_max:
        print_quota_max(profile)

    return exit_code


def _resolve_modules(args: argparse.Namespace, available_modules: list[str]) -> list[str]:
    if args.suite:
        suites = load_suites(Path(args.suites) if args.suites else None)
        expanded = resolve_suite(
            args.suite,
            suites,
            available_modules=available_modules,
            available_checks=[],
        )
        if not expanded["resource_modules"]:
            raise SystemExit(f"关键词 {args.suite!r} 未配置资源模块，请换用 --modules 或选择资源类关键词")
        return expanded["resource_modules"]
    return parse_modules(args.modules, available_modules)


if __name__ == "__main__":
    raise SystemExit(main())
