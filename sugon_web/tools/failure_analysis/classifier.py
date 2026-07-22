"""
失败分析规则分类器。

基于错误消息、堆栈、日志等上下文，将失败快速归类为环境 / 用例 / 产品缺陷。
规则优先于 LLM，用于降低成本和延迟。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from sugon_web.tools.failure_analysis.collector import FailureContext


class FailureCategory(Enum):
    """失败根因分类。"""

    ENVIRONMENT = "environment"
    SCRIPT = "script"
    PRODUCT = "product"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        """中文分类标签。"""
        return {
            "environment": "环境问题",
            "script": "用例问题",
            "product": "产品缺陷",
            "unknown": "未知",
        }.get(self.value, self.value)


@dataclass(frozen=True)
class ClassificationRule:
    """单条分类规则。"""

    name: str
    category: FailureCategory
    condition: Callable[[FailureContext], bool]


def _combined_text(ctx: FailureContext) -> str:
    """组合用于规则匹配的文本。"""
    parts = [
        ctx.case.status_message or "",
        ctx.case.status_trace or "",
        ctx.log_excerpt or "",
    ]
    return "\n".join(parts).lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


# 环境问题关键词：平台维护、网络、SSH、资源不足等
ENVIRONMENT_KEYWORDS = (
    "系统升级中",
    "系统维护",
    "503",
    "没有可用节点",
    "可分配IP数量不足",
    "资源不足",
    "配额不足",
)

# 产品缺陷关键词：业务错误、状态不一致、后端返回错误等
PRODUCT_KEYWORDS = (
    "runtimeerror",
    "api error",
    "接口返回",
    "业务错误",
    "状态不一致",
    "状态不匹配",
    "状态未收敛",
    "创建失败",
    "删除失败",
    "绑定失败",
    "操作失败",
    "internal server error",
    "500",
    "expected .* but got",
    "backend",
)

# 用例问题关键词：断言、超时、定位失败、代码异常等
SCRIPT_KEYWORDS = (
    "assertionerror",
    "assert ",
    "timeouterror",
    "timed out",
    "element not found",
    "could not find",
    "locator",
    "selector",
    "no element matches",
    "indexerror",
    "keyerror",
    "attributeerror",
    "valueerror",
    "typeerror",
    "filenotfounderror",
    "fixture",
    "teardown",
    "setup",
)


def _build_default_rules() -> list[ClassificationRule]:
    """构建默认规则列表。规则按优先级排序，先匹配先返回。"""
    return [
        ClassificationRule(
            name="environment_error",
            category=FailureCategory.ENVIRONMENT,
            condition=lambda ctx: _contains_any(_combined_text(ctx), ENVIRONMENT_KEYWORDS),
        ),
        ClassificationRule(
            name="product_error",
            category=FailureCategory.PRODUCT,
            condition=lambda ctx: _contains_any(_combined_text(ctx), PRODUCT_KEYWORDS),
        ),
        ClassificationRule(
            name="script_error",
            category=FailureCategory.SCRIPT,
            condition=lambda ctx: _contains_any(_combined_text(ctx), SCRIPT_KEYWORDS),
        ),
    ]


DEFAULT_RULES = _build_default_rules()


def classify_failure(
    ctx: FailureContext,
    rules: list[ClassificationRule] | None = None,
) -> FailureCategory:
    """对单个失败上下文进行分类。

    Args:
        ctx: 失败上下文。
        rules: 自定义规则列表；默认使用 DEFAULT_RULES。

    Returns:
        失败分类。
    """
    rules = rules or DEFAULT_RULES
    for rule in rules:
        if rule.condition(ctx):
            return rule.category
    return FailureCategory.UNKNOWN


def classify_failures(
    contexts: list[FailureContext],
    rules: list[ClassificationRule] | None = None,
) -> list[tuple[FailureContext, FailureCategory]]:
    """批量分类失败上下文。

    Args:
        contexts: 失败上下文列表。
        rules: 自定义规则列表。

    Returns:
        (上下文, 分类) 列表。
    """
    return [(ctx, classify_failure(ctx, rules)) for ctx in contexts]
