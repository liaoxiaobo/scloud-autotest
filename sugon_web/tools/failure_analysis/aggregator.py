"""
失败分析相似聚合器。

将相同或相似根因的失败聚合为组，减少重复 LLM 调用和报告噪音。
"""

import re
from dataclasses import dataclass, field
from typing import Callable

from sugon_web.tools.failure_analysis.classifier import FailureCategory
from sugon_web.tools.failure_analysis.collector import FailureContext


@dataclass
class FailureGroup:
    """相似失败聚合组。"""

    category: FailureCategory
    key: str
    signature: str
    contexts: list[FailureContext] = field(default_factory=list)
    representative: FailureContext | None = None

    @property
    def count(self) -> int:
        return len(self.contexts)

    @property
    def case_names(self) -> list[str]:
        return [ctx.case.name for ctx in self.contexts]


def extract_top_frame(trace: str) -> str:
    """从 traceback 中提取最底层（最近）的代码位置。"""
    lines = [line.strip() for line in (trace or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if "File " in line and ", line " in line:
            match = re.search(r'File "([^"]+)", line (\d+)', line)
            if match:
                return f"{match.group(1)}:{match.group(2)}"
    return ""


def normalize_error_message(message: str) -> str:
    """规范化错误消息，去掉变量值、随机 ID 等噪音。"""
    if not message:
        return ""
    text = message.strip()

    # UUID
    text = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<UUID>",
        text,
        flags=re.I,
    )
    # IP 地址
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<IP>", text)
    # 时间戳
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\b", "<TIME>", text)
    # 随机资源名（如 ecs-abc123、vol-xyz789）
    text = re.sub(r"\b[a-z]+-[a-z0-9]{6,}\b", "<NAME>", text)

    return text[:200]


def build_group_key(
    ctx: FailureContext,
    category: FailureCategory,
) -> str:
    """构建聚合键：分类 + 顶层堆栈帧 + 规范化错误消息。"""
    top_frame = extract_top_frame(ctx.case.status_trace)
    norm_msg = normalize_error_message(ctx.case.status_message)
    return f"{category.value}|{top_frame}|{norm_msg}"


def aggregate_failures(
    classified_contexts: list[tuple[FailureContext, FailureCategory]],
    key_builder: Callable[[FailureContext, FailureCategory], str] | None = None,
) -> list[FailureGroup]:
    """聚合相似失败。

    Args:
        classified_contexts: (FailureContext, FailureCategory) 列表。
        key_builder: 自定义聚合键生成函数。

    Returns:
        FailureGroup 列表，按组内用例数降序排列。
    """
    key_builder = key_builder or build_group_key
    groups: dict[str, FailureGroup] = {}

    for ctx, category in classified_contexts:
        key = key_builder(ctx, category)
        if key not in groups:
            groups[key] = FailureGroup(
                category=category,
                key=key,
                signature=normalize_error_message(ctx.case.status_message) or ctx.case.name,
                representative=ctx,
            )
        groups[key].contexts.append(ctx)

    return sorted(groups.values(), key=lambda g: g.count, reverse=True)
