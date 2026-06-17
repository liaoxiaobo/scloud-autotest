import pytest
from sugon_web.config.config import Config
from sugon_web.pages.compute.ecs import (
    EcsCreateRequest,
    _normalize_ecs_create_request,
)
from sugon_web.utils.logger import logger

from .dependency_resolver import _collect_vm_dependency_overrides
from .param_parser import _resolve_fixture_param_refs
from .types import VmFixtureParams
from .utils import _merge_vm_section


def _resolve_vm_fixture_network(
    request: pytest.FixtureRequest,
    params: VmFixtureParams,
    dependency_overrides: EcsCreateRequest | None = None,
) -> tuple[str, str]:
    """返回 vm fixture 最终使用的首张网卡网络与子网。

    优先级说明：
    1. 若测试依赖了 `vpc` 或 `vip` fixture，强制使用该 fixture 提供的网络/子网
    2. 否则使用 vm 显式参数 `network.networks[0]`
    3. 否则使用依赖 fixture 自动注入的 network 配置
    4. 最后回退到默认网络 `Autotest`

    注意：
    - `vpc`/`vip` 会覆盖"首张网卡"的 network/subnet，这是一个显式设计
    - 安全组等其他 network 字段不会在这里处理，只在创建请求合并时保留
    """
    if "vpc" in request.fixturenames or "vip" in request.fixturenames:
        vpc_data = request.getfixturevalue("vpc")
        network = vpc_data["name"]
        subnet = vpc_data["subnet_name"]
        logger.info(f"检测到与VPC相关的fixture，使用VPC网络: {network}, 子网: {subnet}")
        return network, subnet

    network_config = params.get("network")
    if network_config:
        networks = network_config.get("networks") or []
        if networks:
            return networks[0].get("network", "Autotest"), networks[0].get("subnet", "Autotest(10")

    dependency_network = (dependency_overrides or {}).get("network") or {}
    networks = dependency_network.get("networks") or []
    if networks:
        return networks[0].get("network", "Autotest"), networks[0].get("subnet", "Autotest(10")

    return "Autotest", "Autotest(10"


def _build_vm_create_request(
    request: pytest.FixtureRequest,
    params: VmFixtureParams,
    base_name: str,
) -> tuple[EcsCreateRequest, int, str, str]:
    """构建 vm fixture 最终传给 `ecs_create` 的标准请求。

    最终请求来源有三层，优先级从低到高如下：
    1. vm fixture 默认值
    2. 依赖 fixture 自动注入值，例如 sg / labels / affinity
    3. vm 显式参数化传入值

    特殊规则：
    - 若存在 `vpc` / `vip` fixture，则首张网卡的 network/subnet 会被强制覆盖
    - 返回值中的 `count`、`network`、`subnet` 会用于后续状态校验和元数据回填
    """
    resolved_params = _resolve_fixture_param_refs(params, request)
    dependency_overrides = _collect_vm_dependency_overrides(request, resolved_params)
    default_network, default_subnet = _resolve_vm_fixture_network(request, resolved_params, dependency_overrides)

    basic = _merge_vm_section(
        {
            "name": base_name,
            "count": 1,
            "cluster": "Autotest",
            "flavor": {"base": "ecs.c6.Autotest"},
        },
        dependency_overrides.get("basic"),
    )
    basic = _merge_vm_section(basic, resolved_params.get("basic"))

    storage = _merge_vm_section(
        {
            "storage_pool": f"{Config.get('stor')}-test",
            "image": {"source": "镜像", "name": f"{Config.get('stor')}-test"},
            "system_disk": 25,
        },
        dependency_overrides.get("storage"),
    )
    storage = _merge_vm_section(storage, resolved_params.get("storage"))

    network_config = _merge_vm_section(
        {
            "networks": [{"network": default_network, "subnet": default_subnet}],
            "enable_ipv6": False,
        },
        dependency_overrides.get("network"),
    )
    network_config = _merge_vm_section(network_config, resolved_params.get("network"))
    networks = network_config.get("networks") or [{"network": default_network, "subnet": default_subnet}]
    explicit_networks = ((resolved_params.get("network") or {}).get("networks") or [])
    if ("vpc" in request.fixturenames or "vip" in request.fixturenames) and not explicit_networks:
        networks = [dict(networks[0], network=default_network, subnet=default_subnet), *networks[1:]]
    network_config["networks"] = networks
    manage = _merge_vm_section(
        {
            "login_type": "密码登录",
            "login_pwd": "admin1234@sugon",
            "vnc_pwd": "sugon@20",
        },
        dependency_overrides.get("manage"),
    )
    manage = _merge_vm_section(manage, resolved_params.get("manage"))
    advanced = _merge_vm_section({}, dependency_overrides.get("advanced"))
    advanced = _merge_vm_section(advanced, resolved_params.get("advanced"))

    create_request = _normalize_ecs_create_request(
        basic=basic,
        storage=storage,
        network=network_config,
        manage=manage,
        advanced=advanced,
    )

    primary_network = network_config["networks"][0]["network"]
    primary_subnet = network_config["networks"][0]["subnet"]
    return create_request, basic["count"], primary_network, primary_subnet


def _build_vm_instance_params(shared_params: VmFixtureParams, instance_params: VmFixtureParams) -> VmFixtureParams:
    """合并共享参数与单实例参数，生成单台虚机的最终创建参数。

    `vm.instances` 用于描述同一场景下多台配置不同的虚机。
    本函数负责把外层共享配置与当前实例的局部配置合并成标准 `vm` 入参。

    Args:
        shared_params: 所有实例共享的 `vm` 参数。
        instance_params: 当前单台实例的覆盖参数。

    Returns:
        VmFixtureParams: 可直接传入 `_build_vm_create_request` 的单实例参数。
    """
    merged: VmFixtureParams = {
        key: value
        for key, value in shared_params.items()
        if key in {
            "basic",
            "storage",
            "network",
            "manage",
            "advanced",
            "bind_mfip",
            "inject_dependencies",
            "inject_sg",
            "inject_labels",
            "inject_affinity",
        }
    }
    for section_name in ("basic", "storage", "network", "manage", "advanced"):
        merged_section = dict(merged.get(section_name, {}) or {})
        instance_section = instance_params.get(section_name) or {}
        if instance_section:
            merged_section.update(instance_section)
        if merged_section:
            merged[section_name] = merged_section
    for key in ("bind_mfip", "inject_dependencies", "inject_sg", "inject_labels", "inject_affinity"):
        if key in instance_params:
            merged[key] = instance_params[key]
    return merged
