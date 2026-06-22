from typing import Any

import pytest
from sugon_web.pages.compute.ecs import EcsCreateRequest
from sugon_web.utils.logger import logger

from .types import VmFixtureParams, VmDependencyResolver, _normalize_vm_fixture_list
from .utils import _merge_vm_create_sections


def _build_vm_sg_dependency(fixture_value: Any) -> EcsCreateRequest:
    """将安全组 fixture 返回值转换为 ECS 创建请求片段。

    Args:
        fixture_value: `sg` fixture 的返回值，可以是单个安全组名称或名称列表。

    Returns:
        EcsCreateRequest: 可合并到 `network.security_groups` 的请求片段；
        如果没有可用安全组，则返回空字典。
    """
    security_groups = _normalize_vm_fixture_list(fixture_value)
    if not security_groups:
        return {}
    return {"network": {"security_groups": security_groups}}


def _build_vm_labels_dependency(fixture_value: Any) -> EcsCreateRequest:
    """将标签 fixture 返回值转换为 ECS 创建请求片段。

    Args:
        fixture_value: `labels` fixture 的返回值，可以是单个标签或标签列表。

    Returns:
        EcsCreateRequest: 可合并到 `basic.labels` 的请求片段；
        如果没有可用标签，则返回空字典。
    """
    labels = _normalize_vm_fixture_list(fixture_value)
    if not labels:
        return {}
    return {"basic": {"labels": labels}}


def _build_vm_affinity_dependency(fixture_value: Any) -> EcsCreateRequest:
    """将亲和组 fixture 返回值转换为 ECS 创建请求片段。

    Args:
        fixture_value: `affinity` fixture 的返回值，可以是单个亲和组或列表。

    Returns:
        EcsCreateRequest: 可合并到 `advanced.affinity` 的请求片段；
        如果没有可用亲和组，则返回空字典。
    """
    affinities = _normalize_vm_fixture_list(fixture_value)
    if not affinities:
        return {}
    return {"advanced": {"affinity": affinities}}


# vm fixture 的"依赖 fixture -> ECS 创建参数"映射表。
#
# 使用场景：
# - 测试已经通过其他 fixture 预创建了关联资源，例如安全组、标签、亲和组
# - vm fixture 需要自动把这些资源带入 ECS 创建请求
#
# 当前约定：
# - sg -> network.security_groups
# - labels -> basic.labels
# - affinity -> advanced.affinity
#
# 扩展方式：
# 1. 新增一个 resolver，输入为该 fixture 的返回值，输出为 EcsCreateRequest 片段
# 2. 在这里注册 fixture 名与 resolver 的对应关系
# 3. 确保该依赖 fixture 的 scope 不低于 vm fixture（当前 vm 为 class scope）
VM_DEPENDENCY_RESOLVERS: dict[str, VmDependencyResolver] = {
    "sg": _build_vm_sg_dependency,
    "labels": _build_vm_labels_dependency,
    "affinity": _build_vm_affinity_dependency,
}


LEGACY_VM_DEPENDENCY_PARAM_SWITCHES: dict[str, str] = {
    "sg": "inject_sg",
    "labels": "inject_labels",
    "affinity": "inject_affinity",
}


def _normalize_vm_dependency_policy(raw_policy: Any) -> set[str]:
    """将 vm 的依赖注入策略规范化为启用的依赖名称集合。"""
    dependency_names = set(VM_DEPENDENCY_RESOLVERS)

    if raw_policy is True or raw_policy == "all":
        return dependency_names
    if raw_policy is False or raw_policy == "none":
        return set()
    if isinstance(raw_policy, str):
        if raw_policy in dependency_names:
            return {raw_policy}
        raise ValueError(
            f"Unsupported inject_dependencies value: {raw_policy!r}. "
            f"Expected one of 'all', 'none', or dependency names {sorted(dependency_names)!r}."
        )
    if isinstance(raw_policy, (list, tuple, set)):
        enabled_dependencies = set(raw_policy)
        invalid_dependencies = sorted(enabled_dependencies - dependency_names)
        if invalid_dependencies:
            raise ValueError(
                f"Unsupported inject_dependencies entries: {invalid_dependencies!r}. "
                f"Supported dependencies: {sorted(dependency_names)!r}."
            )
        return enabled_dependencies
    raise TypeError(
        f"'inject_dependencies' expects bool, 'all'/'none', or a list of dependency names; "
        f"got {type(raw_policy).__name__!r}."
    )


def _resolve_vm_enabled_dependencies(params: VmFixtureParams) -> set[str]:
    """解析 vm fixture 当前允许自动注入的依赖集合。"""
    if "inject_dependencies" in params:
        enabled_dependencies = _normalize_vm_dependency_policy(params["inject_dependencies"])
        logger.info(f"vm fixture 使用统一依赖注入策略，启用依赖: {sorted(enabled_dependencies)}")
        return enabled_dependencies

    enabled_dependencies = set(VM_DEPENDENCY_RESOLVERS)
    for fixture_name, switch_name in LEGACY_VM_DEPENDENCY_PARAM_SWITCHES.items():
        if not params.get(switch_name, True):
            enabled_dependencies.discard(fixture_name)
    return enabled_dependencies


def _collect_vm_dependency_overrides(
    request: pytest.FixtureRequest,
    params: VmFixtureParams,
) -> EcsCreateRequest:
    """收集 vm 依赖 fixture 对 ECS 创建请求的自动注入项。

    行为说明：
    - 仅处理 `VM_DEPENDENCY_RESOLVERS` 中登记过的 fixture
    - 只有当测试函数实际声明了该 fixture，才会触发注入
    - 多个依赖 fixture 同时存在时，统一合并为一份 EcsCreateRequest 片段

    例如：
    - `sg` 返回 `["sg-a", "sg-b"]` -> 注入到 `network.security_groups`
    - `labels` 返回 `["l1", "l2"]` -> 注入到 `basic.labels`
    """
    overrides: EcsCreateRequest = {}
    enabled_dependencies = _resolve_vm_enabled_dependencies(params)
    for fixture_name, resolver in VM_DEPENDENCY_RESOLVERS.items():
        if fixture_name not in enabled_dependencies:
            logger.info(f"vm fixture 已禁用依赖 {fixture_name} 的自动注入")
            continue
        if fixture_name not in request.fixturenames:
            continue
        fixture_value = request.getfixturevalue(fixture_name)
        resolved_overrides = resolver(fixture_value)
        if not resolved_overrides:
            continue
        overrides = _merge_vm_create_sections(overrides, resolved_overrides)
        logger.info(f"vm fixture 检测到依赖 {fixture_name}，注入创建参数: {resolved_overrides}")
    return overrides
