"""
失败分析数据收集模块。

负责从 Allure 结果、pytest 日志、截图、trace 等来源收集失败用例的完整上下文。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass
class Attachment:
    """Allure 附件元数据。"""

    name: str
    source: str
    type: str = ""


@dataclass
class TestCaseResult:
    """解析后的 Allure 测试用例结果。"""

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


@dataclass
class FailureContext:
    """单个失败用例的完整分析上下文。"""

    case: TestCaseResult
    log_excerpt: str = ""
    screenshot_path: Path | None = None
    trace_path: Path | None = None
    ssh_state: dict | None = None
    timestamp: datetime = field(default_factory=datetime.now)


def collect_result_files(results_dir: Path) -> list[Path]:
    """递归收集 Allure 结果文件。"""
    if not results_dir.exists():
        return []
    return sorted(results_dir.rglob("*-result.json"))


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def labels_to_map(labels: Iterable[dict]) -> dict[str, str]:
    result = {}
    for item in labels or []:
        name = item.get("name")
        value = item.get("value")
        if name and value and name not in result:
            result[name] = value
    return result


def collect_attachments(node: dict) -> list[Attachment]:
    """递归收集 Allure 节点中的附件。"""
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


def _result_identity(data: dict, file_path: Path) -> tuple[str, int]:
    """生成 Allure result.json 的去重标识。

    优先使用 historyId（Allure 用其区分同一用例的不同参数/重试），
    缺失时回退到 fullName 或文件名。

    返回 (key, start_time_ms)，用于在重复结果中保留最新的一份。
    """
    key = data.get("historyId") or data.get("fullName") or data.get("name", file_path.stem)
    start = data.get("start") or 0
    if not start:
        # 没有 start 时间时，使用文件修改时间作为兜底排序依据
        start = int(file_path.stat().st_mtime * 1000)
    return key, start


def parse_allure_results(results_dir: Path) -> list[TestCaseResult]:
    """解析 Allure 结果目录下的所有测试用例，并按 historyId 去重。

    Jenkins 多环境执行时会先把各 env-* 子目录的结果合并到 allure-result 根目录，
    同时保留原 env-* 子目录；递归收集时会出现重复 result.json，导致用例数翻倍。
    按 historyId 去重后，统计结果与 Allure 报告页面保持一致。
    """
    latest_by_key: dict[str, tuple[int, TestCaseResult]] = {}

    for file_path in collect_result_files(results_dir):
        data = load_json(file_path)
        key, start = _result_identity(data, file_path)

        if key in latest_by_key and start <= latest_by_key[key][0]:
            continue

        labels = labels_to_map(data.get("labels", []))
        status_details = data.get("statusDetails", {}) or {}
        latest_by_key[key] = (
            start,
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
            ),
        )

    return [case for _, case in latest_by_key.values()]


def read_text_if_exists(path: Path, max_chars: int | None = None) -> str:
    """读取文本文件，不存在或超限则返回空字符串/截断内容。"""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def resolve_latest_log(logs_dir: Path) -> Path | None:
    """查找日志目录下最新的 pytest 日志文件。"""
    if not logs_dir.exists():
        return None
    log_files = sorted(logs_dir.rglob("pytest-*.log"), key=lambda p: p.stat().st_mtime)
    return log_files[-1] if log_files else None


def find_case_log_excerpt(log_text: str, marker: str, max_chars: int = 2000) -> str:
    """从日志中提取包含 marker 的片段。"""
    if not log_text or not marker:
        return ""
    idx = log_text.find(marker)
    if idx == -1:
        return ""
    start = max(0, idx - 600)
    end = min(len(log_text), idx + max_chars)
    return log_text[start:end].strip()


def resolve_screenshot_path(
    results_dir: Path,
    attachments: list[Attachment],
) -> Path | None:
    """从附件中解析失败截图路径。"""
    for attachment in attachments:
        if "screenshot" in attachment.type or attachment.name in {"失败截图", "screenshot"}:
            path = results_dir / attachment.source
            if path.exists():
                return path
    return None


def resolve_trace_path(
    traces_dir: Path,
    case: TestCaseResult,
) -> Path | None:
    """根据用例名查找 Playwright trace 文件。"""
    if not traces_dir.exists():
        return None
    candidate_names = [
        case.full_name.replace("::", "_"),
        case.name,
    ]
    for trace_file in sorted(traces_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        for candidate in candidate_names:
            if candidate and candidate in trace_file.name:
                return trace_file
    return None


def collect_failure_contexts(
    results_dir: Path,
    logs_dir: Path | None = None,
    traces_dir: Path | None = None,
) -> list[FailureContext]:
    """收集所有失败 / broken 用例的上下文信息。

    Args:
        results_dir: Allure 结果目录。
        logs_dir: pytest 日志目录；默认在 results_dir 同级 logs/ 下查找。
        traces_dir: Playwright trace 目录；默认不收集 trace。

    Returns:
        失败用例上下文列表。
    """
    cases = parse_allure_results(results_dir)
    failed_cases = [case for case in cases if case.status in {"failed", "broken"}]

    if logs_dir is None:
        logs_dir = results_dir.parent / "logs"
    log_path = resolve_latest_log(logs_dir)
    log_text = read_text_if_exists(log_path) if log_path else ""

    contexts = []
    for case in failed_cases:
        screenshot_path = resolve_screenshot_path(results_dir, case.attachments)
        trace_path = resolve_trace_path(traces_dir, case) if traces_dir else None
        log_excerpt = find_case_log_excerpt(log_text, case.full_name or case.name)
        contexts.append(
            FailureContext(
                case=case,
                log_excerpt=log_excerpt,
                screenshot_path=screenshot_path,
                trace_path=trace_path,
            )
        )
    return contexts
