"""
失败分析器。

对聚合后的失败组调用 LLM 进行根因分析，输出结构化的 GroupAnalysis。
"""

import json
import re
from pathlib import Path

from sugon_web.tools.failure_analysis.aggregator import FailureGroup
from sugon_web.tools.failure_analysis.llm_client import call_llm
from sugon_web.tools.failure_analysis.reporter import GroupAnalysis


OUTPUT_SCHEMA = {
    "root_cause": "1-2句话说明最可能根因",
    "confidence": "高/中/低",
    "evidence": ["证据1", "证据2"],
    "exclusions": ["为什么不是另外两类"],
    "short_term_fix": "短期可执行的修复建议",
    "long_term_fix": "长期修复建议（可选）",
}


def _read_file_if_exists(path: Path) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _strip_markdown_code_block(text: str) -> str:
    """去除 LLM 输出外层的 markdown 代码块。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_analysis_response(content: str) -> dict:
    """从 LLM 响应中解析 JSON；失败时返回兜底结构。"""
    content = _strip_markdown_code_block(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "root_cause": content[:300],
            "confidence": "低",
            "evidence": ["LLM 返回非 JSON，已按原文兜底解析"],
            "exclusions": [],
            "short_term_fix": "请人工复核 LLM 输出",
            "long_term_fix": "",
        }


def build_analysis_prompt(
    group: FailureGroup,
    case_library: str = "",
) -> str:
    """为单个失败组构建分析 prompt。"""
    ctx = group.representative
    if ctx is None:
        ctx = group.contexts[0]

    lines = [
        "请基于以下自动化测试失败信息，输出根因分析。",
        "",
        "## 失败组信息",
        f"- 根因分类: {group.category.label}",
        f"- 影响用例数: {group.count}",
        f"- 用例列表: {', '.join(group.case_names[:10])}",
        f"- 代表性用例: {ctx.case.full_name or ctx.case.name}",
        "",
        "## 报错信息",
        ctx.case.status_message or "无",
        "",
        "## 堆栈信息",
        ctx.case.status_trace or "无",
        "",
        "## 相关日志片段",
        ctx.log_excerpt or "无",
        "",
    ]

    if case_library:
        lines.extend(["## 历史案例库", case_library, ""])

    lines.extend([
        "## 输出要求",
        "请严格按以下 JSON 格式输出，不要包含 markdown 代码块：",
        json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
    ])

    return "\n".join(lines)


def analyze_group(
    group: FailureGroup,
    system_prompt: str = "",
    case_library: str = "",
    provider: str = "deepseek",
    model: str = "",
) -> GroupAnalysis:
    """对单个失败组进行 LLM 根因分析。

    Args:
        group: 相似失败聚合组。
        system_prompt: system 角色提示词。
        case_library: 历史案例库文本。
        provider: 模型提供商。
        model: 模型名称。

    Returns:
        GroupAnalysis 对象。
    """
    user_prompt = build_analysis_prompt(group, case_library)
    messages = [
        {"role": "system", "content": system_prompt or "你是自动化测试根因分析专家。"},
        {"role": "user", "content": user_prompt},
    ]
    response = call_llm(messages, provider=provider, model=model)
    result = parse_analysis_response(response.content)

    return GroupAnalysis(
        group=group,
        root_cause=result.get("root_cause", "未生成根因"),
        confidence=result.get("confidence", "低"),
        evidence=result.get("evidence", []),
        exclusions=result.get("exclusions", []),
        short_term_fix=result.get("short_term_fix", "请人工复核"),
        long_term_fix=result.get("long_term_fix", ""),
    )


def analyze_groups(
    groups: list[FailureGroup],
    system_prompt: str = "",
    case_library: str = "",
    provider: str = "deepseek",
    model: str = "",
    max_groups: int = 100,
) -> list[GroupAnalysis]:
    """批量分析失败组。"""
    analyses = []
    for group in groups[:max_groups]:
        analyses.append(
            analyze_group(
                group,
                system_prompt=system_prompt,
                case_library=case_library,
                provider=provider,
                model=model,
            )
        )
    return analyses
