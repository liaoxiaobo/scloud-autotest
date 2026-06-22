"""断言错误消息格式化工具。

所有 assert 语句的失败消息必须遵循统一格式：
[<分类标签>] <被测对象> | <描述> | 期望: <expected> | 实际: <actual>
"""


def fmt_assertion_error(tag, subject, description, expected=None, actual=None, error=None):
    """格式化断言错误消息。

    Args:
        tag: 分类标签，如 'StatusAssertion'、'ListAssertion'。
        subject: 被测对象，如 "ECS 'web-01'"、"autotest-wnpnx 资源状态"。
        description: 描述，如 '状态未收敛'、'存在性校验失败'。
        expected: 期望结果。
        actual: 实际结果。
        error: 错误信息（与 actual 互斥）。

    Returns:
        格式化后的错误消息字符串。
    """
    parts = [f"[{tag}] {subject} | {description}"]
    if expected is not None:
        parts.append(f"期望: {expected}")
    if error is not None:
        parts.append(f"错误: {error}")
    elif actual is not None:
        parts.append(f"实际: {actual}")
    return " | ".join(parts)
