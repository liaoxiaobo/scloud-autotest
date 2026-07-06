import argparse
import functools
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = ROOT_DIR / "allure-result"
DEFAULT_LOGS_DIR = ROOT_DIR / "logs"
DEFAULT_REPORTS_DIR = ROOT_DIR / "ai-reports"
ROOT_CAUSE_PROMPT = ROOT_DIR / "sugon_web" / "tools" / "test_failure_analysis_prompt.md"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DASHSCOPE_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"
PROVIDER_CONFIG = {
    "deepseek": {
        "env": "DEEPSEEK_API_KEY",
        "base_url": DEEPSEEK_BASE_URL,
        "default_model": "deepseek-v4-pro",
        "timeout": 600,
    },
    "dashscope": {
        "env": "DASHSCOPE_API_KEY",
        "base_url": DASHSCOPE_BASE_URL,
        "default_model": "glm-5",
        "timeout": 600,
    },
}

PAYLOAD_LIMITS = {
    "message_chars": 1500,
    "trace_chars": 2500,
    "attachment_items": 3,
    "attachment_chars": 1200,
    "log_chars": 1800,
}


@dataclass
class Attachment:
    name: str
    source: str
    type: str = ""


@dataclass
class TestCaseResult:
    name: str
    full_name: str
    status: str
    history_id: str = ""
    suite: str = ""
    feature: str = ""
    story: str = ""
    status_message: str = ""
    status_trace: str = ""
    attachments: list[Attachment] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 Allure 结果并生成 AI 测试总结"
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Allure 结果目录，默认: ./allure-result",
    )
    parser.add_argument(
        "--log-file",
        default="",
        help="指定 pytest 日志文件；不传则自动使用 logs 下最新文件",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Markdown 输出文件；默认: ai-reports/ai-report-<timestamp>.md",
    )
    parser.add_argument(
        "--provider",
        default="deepseek",
        choices=["deepseek", "dashscope"],
        help="模型提供商，默认: deepseek",
    )
    parser.add_argument(
        "--model",
        default="",
        help="模型名称；默认随 provider 自动选择",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=100,
        help="送入模型分析的失败用例数量上限，默认: 100",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只做本地解析和摘要，不调用 OpenAI API",
    )
    return parser.parse_args()


def collect_result_files(results_dir: Path) -> list[Path]:
    """递归收集 Allure 结果文件，支持按 run_id/env 隔离的子目录结构。"""
    return sorted(results_dir.rglob("*-result.json"))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def labels_to_map(labels: list[dict]) -> dict[str, str]:
    return {
        item["name"]: item["value"]
        for item in labels or []
        if item.get("name") and item.get("value")
    }


def collect_attachments(node: dict) -> list[Attachment]:
    items = []
    for attachment in node.get("attachments", []) or []:
        items.append(
            Attachment(
                name=attachment.get("name", ""),
                source=attachment.get("source", ""),
                type=attachment.get("type", ""),
            )
        )

    for step in node.get("steps", []) or []:
        items.extend(collect_attachments(step))
    return items


def parse_allure_results(results_dir: Path) -> list[TestCaseResult]:
    cases = []
    for file_path in collect_result_files(results_dir):
        data = load_json(file_path)
        labels = labels_to_map(data.get("labels", []))
        status_details = data.get("statusDetails", {}) or {}
        cases.append(
            TestCaseResult(
                name=data.get("name", file_path.stem),
                full_name=data.get("fullName", ""),
                status=data.get("status", "unknown"),
                history_id=data.get("historyId", ""),
                suite=labels.get("suite", ""),
                feature=labels.get("feature", ""),
                story=labels.get("story", ""),
                status_message=status_details.get("message", ""),
                status_trace=status_details.get("trace", ""),
                attachments=collect_attachments(data),
            )
        )
    return cases


def resolve_latest_log(log_file: str) -> Path | None:
    if log_file:
        path = Path(log_file)
        return path if path.exists() else None

    if not DEFAULT_LOGS_DIR.exists():
        return None

    log_files = sorted(DEFAULT_LOGS_DIR.glob("pytest-*.log"), key=lambda p: p.stat().st_mtime)
    return log_files[-1] if log_files else None


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


@functools.lru_cache(maxsize=1)
def _load_root_cause_prompt() -> str:
    return read_text_if_exists(ROOT_CAUSE_PROMPT).strip()


def snippet(text: str, max_chars: int = 1600) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]..."


def find_case_log_excerpt(log_text: str, marker: str, max_chars: int = 2000) -> str:
    if not log_text or not marker:
        return ""

    idx = log_text.find(marker)
    if idx == -1:
        return ""

    start = max(0, idx - 600)
    end = min(len(log_text), idx + max_chars)
    return log_text[start:end].strip()


def attachment_text(
    results_dir: Path,
    attachments: list[Attachment],
    max_items: int = 3,
    max_chars: int = 1200,
) -> str:
    chunks = []
    for attachment in attachments[:max_items]:
        if not attachment.type.startswith("text") and attachment.name not in {"失败信息", "步骤日志"}:
            continue
        source_path = results_dir / attachment.source
        content = read_text_if_exists(source_path)
        if content:
            chunks.append(f"[{attachment.name}]\n{snippet(content, max_chars)}")
    return "\n\n".join(chunks)


def build_local_summary(cases: list[TestCaseResult], log_path: Path | None) -> str:
    """精简的本地执行摘要，仅含统计信息。失败详情由 AI 总结提供，避免重复。"""
    failed_cases = [case for case in cases if case.status in {"failed", "broken"}]
    skipped_cases = [case for case in cases if case.status == "skipped"]
    passed_cases = [case for case in cases if case.status == "passed"]
    other_count = len(cases) - len(failed_cases) - len(skipped_cases) - len(passed_cases)

    lines = [
        "# 测试执行摘要",
        "",
        f"- 总用例数: {len(cases)}",
        f"- 通过: {len(passed_cases)}",
        f"- 失败: {len(failed_cases)}",
        f"- 跳过: {len(skipped_cases)}",
        f"- 其他状态: {other_count}",
    ]

    if log_path:
        lines.append(f"- 日志文件: {log_path}")

    return "\n".join(lines)


def build_failure_payload(
    cases: list[TestCaseResult],
    results_dir: Path,
    log_text: str,
    max_failures: int,
) -> str:
    failed_cases = [case for case in cases if case.status in {"failed", "broken"}][:max_failures]
    parts = []
    for index, case in enumerate(failed_cases, start=1):
        parts.append(f"## 失败用例 {index}")
        parts.append(f"名称: {case.name}")
        parts.append(f"全名: {case.full_name or case.name}")
        parts.append(f"模块: {case.feature or case.suite or '未分类'}")
        parts.append(f"场景: {case.story or '未标记'}")
        parts.append(f"状态: {case.status}")

        if case.status_message:
            parts.append(f"报错信息:\n{snippet(case.status_message, PAYLOAD_LIMITS['message_chars'])}")
        if case.status_trace:
            parts.append(f"堆栈信息:\n{snippet(case.status_trace, PAYLOAD_LIMITS['trace_chars'])}")

        attach_preview = attachment_text(
            results_dir,
            case.attachments,
            max_items=PAYLOAD_LIMITS["attachment_items"],
            max_chars=PAYLOAD_LIMITS["attachment_chars"],
        )
        if attach_preview:
            parts.append(f"附件内容:\n{attach_preview}")

        log_excerpt = find_case_log_excerpt(log_text, case.full_name or case.name)
        if log_excerpt:
            parts.append(f"相关日志片段:\n{snippet(log_excerpt, PAYLOAD_LIMITS['log_chars'])}")

        parts.append("")

    return "\n".join(parts).strip()


def build_execution_summary(cases: list[TestCaseResult], log_path: Path | None) -> str:
    """精简的执行统计，仅含数字，用于 AI prompt，避免与 failure_payload 重复。"""
    failed_cases = [case for case in cases if case.status in {"failed", "broken"}]
    skipped_cases = [case for case in cases if case.status == "skipped"]
    passed_cases = [case for case in cases if case.status == "passed"]
    other_count = len(cases) - len(failed_cases) - len(skipped_cases) - len(passed_cases)

    lines = [
        f"- 总用例数: {len(cases)}",
        f"- 通过: {len(passed_cases)}",
        f"- 失败: {len(failed_cases)}",
        f"- 跳过: {len(skipped_cases)}",
        f"- 其他状态: {other_count}",
    ]
    if log_path:
        lines.append(f"- 日志文件: {log_path}")
    return "\n".join(lines)


def build_chat_messages(execution_summary: str, failure_payload: str) -> list[dict]:
    instructions = _load_root_cause_prompt()
    user_input = "\n\n".join(
        [
            "请分析以下自动化测试失败结果。",
            "",
            "### 执行统计",
            execution_summary,
            "",
            "### 失败详情",
            failure_payload or "无失败用例",
        ]
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": user_input},
    ]


def resolve_provider_config(provider: str, model: str) -> tuple[str, str, str]:
    config = PROVIDER_CONFIG[provider]
    api_key = os.environ.get(config["env"])
    resolved_model = model or config["default_model"]
    return api_key or "", config["base_url"], resolved_model


def call_model_summary(
    provider: str,
    model: str,
    execution_summary: str,
    failure_payload: str,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 openai SDK，请先执行 `pip install -r requirements.txt`") from exc

    api_key, base_url, resolved_model = resolve_provider_config(provider, model)
    if not api_key:
        env_name = PROVIDER_CONFIG[provider]["env"]
        raise RuntimeError(f"未检测到 {env_name} 环境变量")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=resolved_model,
            messages=build_chat_messages(execution_summary, failure_payload),
            timeout=PROVIDER_CONFIG[provider]["timeout"],
        )
    except Exception as exc:
        provider_label = "DeepSeek" if provider == "deepseek" else "DashScope"
        raise RuntimeError(
            f"{provider_label} 调用失败: {exc}"
        ) from exc
    return (response.choices[0].message.content or "").strip()


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"未找到 Allure 结果目录: {results_dir}")
        return 1

    cases = parse_allure_results(results_dir)
    if not cases:
        print(f"目录中没有找到 *-result.json 文件: {results_dir}")
        return 1

    log_path = resolve_latest_log(args.log_file)
    log_text = read_text_if_exists(log_path) if log_path else ""

    local_summary = build_local_summary(cases, log_path)
    execution_summary = build_execution_summary(cases, log_path)
    failure_payload = build_failure_payload(
        cases,
        results_dir,
        log_text,
        args.max_failures,
    )

    if args.dry_run:
        content = local_summary
    else:
        ai_summary = call_model_summary(
            provider=args.provider,
            model=args.model,
            execution_summary=execution_summary,
            failure_payload=failure_payload,
        )
        content = "\n\n".join([local_summary, "# AI 总结", "", ai_summary]).strip()

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = DEFAULT_REPORTS_DIR / f"ai-report-{timestamp}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content + "\n", encoding="utf-8")

    print(f"已生成AI总结分析: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
