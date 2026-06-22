import re
from typing import Any

import pytest

from .types import VmFixtureParams


def _get_vm_fixture_params(request: pytest.FixtureRequest) -> VmFixtureParams:
    """返回 vm fixture 的显式参数。

    这里只读取 `@pytest.mark.parametrize("vm", [...], indirect=True)` 传入的内容，
    不处理依赖 fixture 的自动注入；自动注入由依赖解析模块统一负责。
    """
    params = getattr(request, "param", {})
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise TypeError(f"'vm' fixture expects request.param to be a dict, got {type(params).__name__}")

    return dict(params)


def _resolve_fixture_param_refs(value: Any, request: pytest.FixtureRequest) -> Any:
    """递归解析参数中的 `@fixture.path` 引用。

    该工具函数允许在参数化数据中通过字符串引用其他 fixture 的返回值，
    例如 `@vpc.name`、`@vpc.extra_subnets[0].name`。

    Args:
        value: 待解析的原始值，可以是标量、字典或列表。
        request: 当前 pytest 请求对象，用于按名称取 fixture 值。

    Returns:
        Any: 解析后的值。若字符串不符合引用语法，则保持原值返回。
    """
    if isinstance(value, dict):
        return {key: _resolve_fixture_param_refs(item, request) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_fixture_param_refs(item, request) for item in value]
    if not isinstance(value, str) or not value.startswith("@"):
        return value

    expression = value[1:]
    match = re.match(r"^(?P<fixture>[a-zA-Z_]\w*)(?P<path>(?:\.[^. \[\]]+|\[\d+\])*)$", expression)
    if not match:
        return value

    resolved = request.getfixturevalue(match.group("fixture"))
    path = match.group("path")
    if not path:
        return resolved

    token_pattern = re.compile(r"\.(?P<key>[^.\[\]]+)|\[(?P<index>\d+)\]")
    for token in token_pattern.finditer(path):
        key = token.group("key")
        index = token.group("index")
        if key is not None:
            resolved = resolved[key]
        else:
            resolved = resolved[int(index)]
    return resolved
