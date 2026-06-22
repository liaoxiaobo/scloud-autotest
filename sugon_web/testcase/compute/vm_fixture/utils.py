from sugon_web.pages.compute.ecs import EcsCreateRequest


def _merge_vm_section(defaults: dict[str, object], overrides: dict[str, object] | None) -> dict[str, object]:
    """合并单个 ECS 配置分组。

    采用浅合并即可满足当前场景：
    - 先给默认值
    - 再叠加依赖 fixture 注入值
    - 最后叠加 vm 显式传参
    """
    merged = dict(defaults)
    if overrides:
        merged.update(overrides)
    return merged


def _merge_vm_create_sections(
    base_request: EcsCreateRequest,
    overrides: EcsCreateRequest,
) -> EcsCreateRequest:
    """按 ECS 创建请求分组合并配置。

    这个函数只负责分组级别合并，不负责设置默认值。
    用途主要是把多个依赖 fixture 产生的片段收敛成一份标准 EcsCreateRequest。
    """
    merged: EcsCreateRequest = dict(base_request)
    for section_name in ("basic", "storage", "network", "manage", "advanced"):
        base_section = merged.get(section_name)
        override_section = overrides.get(section_name)
        if not base_section and not override_section:
            continue
        merged[section_name] = _merge_vm_section(base_section or {}, override_section)
    return merged
