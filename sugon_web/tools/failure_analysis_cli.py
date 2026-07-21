"""
失败分析 CLI 入口。

整合收集、分类、聚合、分析、报告生成全流程，供 Jenkins 和本地调试调用。
"""

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，支持直接运行本脚本
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sugon_web.tools.failure_analysis.aggregator import aggregate_failures
from sugon_web.tools.failure_analysis.analyzer import analyze_groups
from sugon_web.tools.failure_analysis.classifier import classify_failures
from sugon_web.tools.failure_analysis.collector import (
    collect_failure_contexts,
    parse_allure_results,
)
from sugon_web.tools.failure_analysis.reporter import (
    append_allure_description,
    build_json_report,
    build_markdown_report,
    write_json_report,
    write_markdown_report,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = ROOT_DIR / "allure-result"
DEFAULT_LOGS_DIR = ROOT_DIR / "logs"
DEFAULT_TRACES_DIR = ROOT_DIR / "traces"
DEFAULT_OUTPUT = ROOT_DIR / "reports" / "ai-test-summary.md"
DEFAULT_JSON_OUTPUT = ROOT_DIR / "reports" / "failure-report.json"
DEFAULT_PROMPT = ROOT_DIR / "sugon_web" / "tools" / "failure_analysis.md"
DEFAULT_CASE_LIBRARY = (
    ROOT_DIR
    / ".claude"
    / "skills"
    / "test-failure-analysis"
    / "references"
    / "case_library.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试失败 AI 根因分析 CLI")
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Allure 结果目录，默认: ./allure-result",
    )
    parser.add_argument(
        "--logs-dir",
        default=str(DEFAULT_LOGS_DIR),
        help="pytest 日志目录，默认: ./logs",
    )
    parser.add_argument(
        "--traces-dir",
        default="",
        help="Playwright trace 目录，默认不收集",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Markdown 报告输出路径，默认: ./reports/ai-test-summary.md",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_JSON_OUTPUT),
        help="JSON 报告输出路径，默认: ./reports/failure-report.json",
    )
    parser.add_argument(
        "--provider",
        default="sugoncloud",
        choices=["deepseek", "dashscope", "sugoncloud"],
        help="模型提供商，默认: sugoncloud",
    )
    parser.add_argument(
        "--model",
        default="",
        help="模型名称；默认使用 provider 默认模型",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=100,
        help="送入 LLM 分析的最大失败组数，默认: 100",
    )
    parser.add_argument(
        "--prompt",
        default=str(DEFAULT_PROMPT),
        help="system prompt 文件路径",
    )
    parser.add_argument(
        "--case-library",
        default=str(DEFAULT_CASE_LIBRARY),
        help="历史案例库文件路径",
    )
    parser.add_argument(
        "--append-allure",
        action="store_true",
        help="将分析结果追加到 Allure result.json 的 description 字段",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只做本地分类聚合，不调用 LLM",
    )
    return parser.parse_args()


def _read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    traces_dir = Path(args.traces_dir) if args.traces_dir else None

    print(f"收集 Allure 结果: {results_dir}")
    all_cases = parse_allure_results(results_dir)
    contexts = collect_failure_contexts(results_dir, logs_dir, traces_dir)
    print(f"共收集到 {len(contexts)} 个 failed / broken 用例（总用例 {len(all_cases)}）")

    print("规则分类...")
    classified = classify_failures(contexts)

    print("相似聚合...")
    groups = aggregate_failures(classified)
    print(f"聚合为 {len(groups)} 个失败组")

    execution_summary = {
        "total": len(all_cases),
        "failed": len(contexts),
        "passed": len([c for c in all_cases if c.status == "passed"]),
        "skipped": len([c for c in all_cases if c.status == "skipped"]),
        "other": len([c for c in all_cases if c.status not in {"passed", "failed", "broken", "skipped"}]),
    }

    if args.dry_run:
        print("dry-run 模式，跳过 LLM 分析")
        analyses = []
    else:
        print(f"调用 LLM 分析前 {args.max_failures} 个失败组...")
        system_prompt = _read_text(args.prompt)
        case_library = _read_text(args.case_library)
        analyses = analyze_groups(
            groups,
            system_prompt=system_prompt,
            case_library=case_library,
            provider=args.provider,
            model=args.model,
            max_groups=args.max_failures,
        )

    md_content = build_markdown_report(analyses, execution_summary)
    md_path = Path(args.output)
    write_markdown_report(md_content, md_path)
    print(f"已生成 Markdown 报告: {md_path}")

    json_report = build_json_report(analyses, execution_summary)
    json_path = Path(args.json_output)
    write_json_report(json_report, json_path)
    print(f"已生成 JSON 报告: {json_path}")

    if args.append_allure and analyses:
        append_allure_description(results_dir, analyses)
        print("已追加分析结果到 Allure result.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
