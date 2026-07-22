"""
失败分析器。

对聚合后的失败组调用 LLM 进行根因分析，输出结构化的 GroupAnalysis。
"""

import json
import re
from pathlib import Path

from sugon_web.tools.failure_analysis.aggregator import FailureGroup
from sugon_web.tools.failure_analysis.classifier import FailureCategory
from sugon_web.tools.failure_analysis.llm_client import call_llm
from sugon_web.tools.failure_analysis.reporter import GroupAnalysis, _normalize_text


# 规则直通分类：这些分类命中时直接生成分析结果，不再调用 LLM。
# 环境问题通常证据明确（如平台维护、503、SSH 不通等），适合规则直通。
RULE_BASED_CATEGORIES = {FailureCategory.ENVIRONMENT}


OUTPUT_SCHEMA = {
    "root_cause": "1-2句话说明最可能根因",
    "confidence": "高/中/低",
    "evidence": ["证据1", "证据2"],
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


def _extract_json_object(text: str) -> str:
    """从文本中提取第一个完整的 JSON 对象。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else ""


def parse_analysis_response(content: str) -> dict:
    """从 LLM 响应中解析 JSON；失败时返回兜底结构。"""
    if not content or not content.strip():
        return {
            "root_cause": "LLM 返回为空，需人工复核原始报错",
            "confidence": "低",
            "evidence": ["LLM 响应 content 为空"],
            "short_term_fix": "检查模型服务可用性与 prompt 输入后重试",
            "long_term_fix": "",
        }

    content = _strip_markdown_code_block(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试从文本中提取嵌套的 JSON 对象（应对 LLM 输出被截断或包裹说明文字的情况）
        try:
            obj = _extract_json_object(content)
            if obj:
                return json.loads(obj)
        except json.JSONDecodeError:
            pass
        root_cause = content[:300] if content.strip() else "LLM 返回为空，需人工复核原始报错"
        return {
            "root_cause": root_cause,
            "confidence": "低",
            "evidence": ["LLM 返回非 JSON，已按原文兜底解析"],
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


def build_rule_based_analysis(group: FailureGroup) -> GroupAnalysis:
    """对高置信度规则分类直接生成分析结果，跳过 LLM 调用。"""
    category_label = group.category.label
    signature = _normalize_text(group.signature)[:120]

    return GroupAnalysis(
        group=group,
        root_cause=f"规则分类命中【{category_label}】：{signature}",
        confidence="高",
        evidence=[
            f"错误信息匹配 {category_label} 关键词",
            f"影响用例数 {group.count}",
        ],
        short_term_fix="检查测试环境可用性（平台状态、网络、资源、服务是否就绪）后重试",
        long_term_fix="",
    )


def analyze_group(
    group: FailureGroup,
    system_prompt: str = "",
    case_library: str = "",
    provider: str = "deepseek",
    model: str = "",
) -> GroupAnalysis:
    """对单个失败组进行根因分析。

    若分类命中 RULE_BASED_CATEGORIES，直接返回规则分析结果，不调用 LLM。
    否则调用 LLM 进行深度分析。

    Args:
        group: 相似失败聚合组。
        system_prompt: system 角色提示词。
        case_library: 历史案例库文本。
        provider: 模型提供商。
        model: 模型名称。

    Returns:
        GroupAnalysis 对象。
    """
    if group.category in RULE_BASED_CATEGORIES:
        return build_rule_based_analysis(group)

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
