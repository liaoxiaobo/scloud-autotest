"""
失败分析报告生成器。

根据分类、聚合后的失败组生成 Markdown、JSON 报告，并可回写 Allure 描述。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from sugon_web.tools.failure_analysis.aggregator import FailureGroup


@dataclass
class GroupAnalysis:
    """单个失败组的分析结果。"""

    group: FailureGroup
    root_cause: str
    confidence: str
    evidence: list[str] = field(default_factory=list)
    short_term_fix: str = ""
    long_term_fix: str = ""


def _default_summary() -> dict:
    return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "other": 0}


_MISSING_EVIDENCE_PREFIX = "缺失证据："
_MISSING_EVIDENCE_KEYWORDS = ("缺少", "缺失", "不足", "无法获取", "无法验证")


def _is_missing_evidence(text: str) -> bool:
    """判断证据项是否在描述缺失材料。"""
    return text.startswith(_MISSING_EVIDENCE_PREFIX) or any(
        kw in text for kw in _MISSING_EVIDENCE_KEYWORDS
    )


def build_markdown_report(
    analyses: list[GroupAnalysis],
    execution_summary: dict | None = None,
) -> str:
    """生成 Markdown 分析报告。

    Args:
        analyses: 每组失败的分析结果。
        execution_summary: 执行概览统计。

    Returns:
        Markdown 字符串。
    """
    summary = execution_summary or _default_summary()

    lines = [
        "# 测试失败 AI 分析报告",
        "",
        "## 执行概览",
        "",
        f"- 总用例数: {summary.get('total', 0)}",
        f"- 通过: {summary.get('passed', 0)}",
        f"- 失败: {summary.get('failed', 0)}",
        f"- 跳过: {summary.get('skipped', 0)}",
        "",
        "## 失败分类统计",
        "",
    ]

    category_counts: dict[str, int] = {}
    for a in analyses:
        label = a.group.category.label
        category_counts[label] = category_counts.get(label, 0) + 1
    for label, count in sorted(category_counts.items()):
        lines.append(f"- {label}: {count}")
    lines.append("")

    lines.extend(["## 详细分析", ""])
    if not analyses:
        lines.append("- 无失败用例")
        return "\n".join(lines)

    for idx, analysis in enumerate(analyses, 1):
        g = analysis.group
        case_list = ", ".join(g.case_names[:5])
        if g.count > 5:
            case_list += f" 等 {g.count} 个用例"

        # 标题简短化，避免原始错误信息过长
        title = g.signature[:80]

        lines.extend([
            f"### {idx}. {title}",
            f"- **原始错误**: {g.signature}",
            f"- **分类**: {g.category.label}",
            f"- **置信度**: {analysis.confidence}",
            f"- **影响范围**: {g.count} 个用例（{case_list}）",
            "",
            "#### 根因",
            analysis.root_cause,
            "",
            "#### 关键证据",
        ])

        # 给证据加可信度标记；置信度低时，缺失材料描述标记为【缺失证据】
        for i, ev in enumerate(analysis.evidence):
            clean_ev = ev
            if clean_ev.startswith(_MISSING_EVIDENCE_PREFIX):
                clean_ev = clean_ev[len(_MISSING_EVIDENCE_PREFIX):]
            if analysis.confidence == "低" and _is_missing_evidence(ev):
                marker = "【缺失证据】"
            elif i == 0:
                marker = "【直接证据】"
            else:
                marker = "【间接证据】"
            lines.append(f"- {marker}{clean_ev}")

        lines.extend(["", "#### 修复建议"])
        lines.append(f"- 短期：{analysis.short_term_fix}")
        if analysis.long_term_fix:
            lines.append(f"- 长期：{analysis.long_term_fix}")
        lines.append("")

    return "\n".join(lines)


def build_json_report(
    analyses: list[GroupAnalysis],
    execution_summary: dict | None = None,
) -> dict:
    """生成 JSON 结构化报告。

    Args:
        analyses: 每组失败的分析结果。
        execution_summary: 执行概览统计。

    Returns:
        可序列化的字典。
    """
    return {
        "summary": execution_summary or _default_summary(),
        "groups": [
            {
                "category": a.group.category.value,
                "category_label": a.group.category.label,
                "signature": a.group.signature,
                "count": a.group.count,
                "case_names": a.group.case_names,
                "root_cause": a.root_cause,
                "confidence": a.confidence,
                "evidence": a.evidence,
                "short_term_fix": a.short_term_fix,
                "long_term_fix": a.long_term_fix,
            }
            for a in analyses
        ],
    }


def write_markdown_report(content: str, output_path: Path) -> None:
    """写入 Markdown 报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content + "\n", encoding="utf-8")


def write_json_report(report: dict, output_path: Path) -> None:
    """写入 JSON 报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_allure_description(
    results_dir: Path,
    analyses: list[GroupAnalysis],
) -> None:
    """将 AI 分析结果追加到 Allure result.json 的 description 字段。

    注意：直接修改 Allure JSON 文件，建议在生成 Allure 报告之前调用。
    """
    for a in analyses:
        if not a.group.representative:
            continue
        # 查找 representative 对应的 result.json
        full_name = a.group.representative.case.full_name
        for result_file in results_dir.rglob("*-result.json"):
            data = json.loads(result_file.read_text(encoding="utf-8"))
            if data.get("fullName") == full_name:
                desc = data.get("description", "")
                ai_note = (
                    f"\n\n【AI 根因分析】\n"
                    f"分类：{a.group.category.label}\n"
                    f"置信度：{a.confidence}\n"
                    f"结论：{a.root_cause}\n"
                    f"建议：{a.short_term_fix}"
                )
                data["description"] = desc + ai_note
                result_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                break
