import re
import pytest
from sugon_web.pages.login import LoginPage
from sugon_web.pages.network import VpcPage
from sugon_web.pages.storage import EvsPage
from sugon_web.pages.compute import EcsPage
from sugon_web.pages.compute.ecs import (
    EcsCreateRequest,
    EcsBasicConfig,
    EcsStorageConfig,
    EcsNetworkConfig,
    EcsManageConfig,
    EcsAdvancedConfig,
    _normalize_ecs_create_request,
)
from typing import Any, Callable, Iterator, NotRequired, TypedDict
from sugon_web.pages.ops import OpsPage
from sugon_web.config.config import Config
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data
from sugon_web.conftest import _create_logged_in_page


class VmFixtureParams(TypedDict, total=False):
    """vm fixture 的显式入参。

    设计目标:
    1. 与 `ecs_create` 使用同一套分组字典结构，避免维护两套创建协议
    2. 仅增加少量 vm fixture 自身控制参数，避免把创建协议拆成两套

    支持的直接传参:
    - basic: 对应 ECS 基本信息
    - storage: 对应 ECS 存储信息
    - network: 对应 ECS 网络信息
    - manage: 对应 ECS 管理信息
    - advanced: 对应 ECS 高级配置
    - bind_mfip: vm fixture 自身开关，控制是否自动绑定 MFIP
    - inject_dependencies: 统一控制依赖 fixture 自动注入，默认 True
    - instances: 多实例创建清单；当需要为每台虚机指定不同参数时使用

    兼容字段:
    - inject_sg / inject_labels / inject_affinity
      仅保留向后兼容；当 `inject_dependencies` 未提供时才生效

    示例:
        @pytest.mark.parametrize(
            "vm",
            [{
                "basic": {"count": 2},
                "network": {"enable_ipv6": True},
                "bind_mfip": False,
                "inject_dependencies": ["sg"],
            }],
            indirect=True,
        )
    """

    bind_mfip: bool
    inject_dependencies: bool | str | list[str]
    inject_sg: bool
    inject_labels: bool
    inject_affinity: bool
    instances: list["VmFixtureParams"]
    basic: EcsBasicConfig
    storage: EcsStorageConfig
    network: EcsNetworkConfig
    manage: EcsManageConfig
    advanced: EcsAdvancedConfig

class VmMetadata(TypedDict):
    """vm fixture 返回的最小虚机元数据。"""

    name: str
    id: str
    ip: str
    ipv6: str
    host: str
    flavor: str
    image: str
    project: str
    network: str
    subnet: str
    mfip: NotRequired[str | None]


VmDependencyResolver = Callable[[Any], EcsCreateRequest]


def _normalize_vm_fixture_list(value: Any) -> list[Any]:
    """将 fixture 返回值统一转换为列表，便于映射到 ECS 分组参数。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


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


# vm fixture 的“依赖 fixture -> ECS 创建参数”映射表。
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
#
# 这样测试可以写成：
#   @pytest.mark.parametrize("sg", [2], indirect=True)
#   @pytest.mark.parametrize("labels", [{"count": 3}], indirect=True)
#   @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
#   def test_xxx(vm, sg, labels):
#       ...
#
# vm 会自动把 sg / labels 注入到 ecs_create 对应分组，无需测试手工拼装。
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

@pytest.fixture(scope="function")
def login_page(page):
    """初始化登录页对象"""
    login_page = LoginPage(page)
    login_page.logout()   # 登录测试用例需要先退出登录状态
    return login_page


@pytest.fixture(scope="function")
def evs_page(page):
    """初始化云硬盘页对象"""
    evs_page = EvsPage(page)
    evs_page.goto_service('云硬盘')
    return evs_page


@pytest.fixture()
def volume(evs_page, request):
    """初始化云硬盘数据

    Args:
        evs_page: 云硬盘页面对象
        request: pytest fixture，用于获取参数和动态获取其他 fixture
        request.param: 包含云硬盘配置的字典，例如：
            {
                "empty": True,  # 是否创建空白云硬盘，默认为True
                "image_name": "",  # 镜像名称，当empty=False时使用
                "size": 30,  # 云硬盘大小，默认为30GB
                "desc": "",  # 云硬盘描述，默认为空
                "shared": False,  # 是否创建共享云硬盘，默认为False
            }
    """
    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    empty = params.get('empty', True)
    image_name = params.get('image_name', '')
    size = params.get('size', 30)
    desc = params.get('desc', '')
    shared = params.get('shared', False)

    # 当存储类型为 local 时，且测试用例引用了 vm fixture 时，才动态获取 host 信息
    host = None
    if evs_page.stor == 'local' and 'vm' in request.fixturenames:
        resource = request.getfixturevalue('vm')
        if isinstance(resource, list):
            resource = resource[0]
        host = resource.get('host')
        logger.info(f"检测到存储类型为{evs_page.stor}，从虚机 {resource['name']} 获取 host: {host}")

    name = random_data()
    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试

    # 构建云硬盘创建参数
    create_kwargs = {
        "name": name,
        "empty": empty,
        "image_name": image_name,
        "size": size,
        "desc": desc,
        "shared": shared,
        "host": host
    }
    with allure_step_log("创建云硬盘"):
        evs_page.evs_create(**create_kwargs)
        evs_page.assert_popup_success()
        evs_page.assert_status(name, status="可用")
        row_data = evs_page.get_row_data(name)
        volume = {"name": name}

    yield volume

    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试
    evs_page.evs_remove([volume["name"]])
    evs_page.evs_delete([volume["name"]])
    evs_page.assert_deleted(volume["name"])


@pytest.fixture(scope="function")
def ecs_page(page):
    """初始化弹性云服务器页对象"""
    ecs_page = EcsPage(page)
    ecs_page.goto_service('弹性云服务器')
    return ecs_page

@pytest.fixture(scope="function")
def ops_page(page):
    """初始化运维管理页对象"""
    ops_page = OpsPage(page)
    ops_page.goto_service('网络设施')
    return ops_page

def _get_vm_fixture_params(request: pytest.FixtureRequest) -> VmFixtureParams:
    """返回 vm fixture 的显式参数。

    这里只读取 `@pytest.mark.parametrize("vm", [...], indirect=True)` 传入的内容，
    不处理依赖 fixture 的自动注入；自动注入由 `_collect_vm_dependency_overrides`
    统一负责。
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
    - `vpc`/`vip` 会覆盖“首张网卡”的 network/subnet，这是一个显式设计
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


def _merge_vm_section(defaults: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
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


def _build_vm_fixture_names(base_name: str, count: int) -> list[str]:
    """根据创建数量返回虚机名称列表。"""
    if count < 1:
        raise ValueError(f"'count' must be >= 1, got {count!r}")
    if count == 1:
        return [base_name]
    return [f"{base_name}-{index}" for index in range(1, count+1)]


def _create_vm_resources(
    ecs_page: EcsPage,
    create_request: EcsCreateRequest,
    vm_names: list[str],
) -> None:
    """创建指定数量的虚机并等待状态可用。

    入参 `create_request` 必须已经是标准 EcsCreateRequest。
    这里不再关心参数来自默认值、参数化传参还是依赖 fixture 注入。
    """
    with allure_step_log("创建指定数量的虚机"):
        ecs_page.goto_service("弹性云服务器")
        ecs_page.ecs_create(**create_request)
        ecs_page.assert_popup_success("创建实例命令下发成功")
        ecs_page.assert_status(vm_names)


def _collect_vm_fixture_metadata(
    ecs_page: EcsPage,
    vm_names: list[str],
    network: str,
    subnet: str,
) -> list[VmMetadata]:
    """收集 vm fixture 所需的虚机元数据。"""
    metadata_list: list[VmMetadata] = []
    for vm_name in vm_names:
        row_data = ecs_page.get_row_data(vm_name)
        ip_list = row_data["IP地址"].split("固定: ")
        metadata_list.append(
            {
                "name": vm_name,
                "id": row_data["名称/ID"].split(":")[1].strip(),
                "ip": ip_list[-1].strip(),
                "ipv6": ip_list[-2].strip(),
                "host": row_data["物理机"],
                "flavor": row_data["规格"],
                "image": row_data["镜像名称"],
                "project": row_data["项目名称"],
                "network": network,
                "subnet": subnet,
            }
        )
    return metadata_list


def _bind_vm_fixture_mfips(
    ecs_page: EcsPage,
    metadata_list: list[VmMetadata],
    network: str,
) -> None:
    """为虚机绑定 MFIP，并回填到元数据。"""
    with allure_step_log(f"为虚机绑定 MFIP"):
        for vm_data in metadata_list:
            ecs_page.goto_service("网络设施")
            ecs_page.mfip_create(vm_data["project"], network, vm_data["ip"])
            ecs_page.assert_popup_success()
            ecs_page.mfip_search(vm_data["ip"])
            vm_data["mfip"] = ecs_page.get_row_data(vm_data["ip"]).get("管理IP地址")
    ecs_page.goto_service("弹性云服务器")


def _cleanup_vm_resources(ecs_page: EcsPage, vm_names: list[str]) -> None:
    """清理 vm fixture 创建的虚机。"""
    if not vm_names:
        return
    ecs_page.goto_service("弹性云服务器")
    ecs_page.ecs_remove(vm_names)
    ecs_page.ecs_delete(vm_names)
    ecs_page.assert_deleted(vm_names)


@pytest.fixture(scope="class")
def vm(
    browser_context: Any,
    config: Any,
    request: pytest.FixtureRequest,
) -> Iterator[VmMetadata | list[VmMetadata]]:
    """初始化弹性云服务器数据

    通用 ECS 资源 fixture，职责是：
    1. 按标准 `ecs_create` 分组参数创建虚机
    2. 兼容 pytest 参数化
    3. 自动吸收部分依赖 fixture 产物（如 sg / labels / affinity）
    4. 返回后续用例常用的最小虚机元数据，并在测试结束后自动清理

    一、直接参数化方式

    `vm` 仅接受与 `ecs_create` 一致的分组字典：
    - `basic`
    - `storage`
    - `network`
    - `manage`
    - `advanced`

    以及 vm 自身扩展参数：
    - `bind_mfip`
    - `inject_dependencies`
    - `instances`

    兼容旧参数：
    - `inject_sg`
    - `inject_labels`
    - `inject_affinity`

    示例：
        @pytest.mark.parametrize(
            "vm",
            [{
                "basic": {"count": 2},
                "storage": {"system_disk": 40},
                "network": {"enable_ipv6": True},
                "bind_mfip": False,
                "inject_dependencies": ["labels"],
            }],
            indirect=True,
        )

    二、依赖 fixture 自动注入

    若测试同时声明了某些已注册依赖 fixture，`vm` 会自动把它们映射到
    ECS 创建参数中。例如：
    - `sg` -> `network.security_groups`
    - `labels` -> `basic.labels`
    - `affinity` -> `advanced.affinity`

    示例：
        @pytest.mark.parametrize("sg", [2], indirect=True)
        @pytest.mark.parametrize("labels", [{"count": 3}], indirect=True)
        @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
        def test_xxx(vm, sg, labels):
            ...

    三、参数优先级

    从低到高：
    1. vm fixture 默认值
    2. 依赖 fixture 自动注入
    3. vm 显式参数化传参

    特殊规则：
    - 若存在 `vpc` / `vip` fixture，首张网卡的 `network/subnet` 强制取自它们
    - 若设置 `inject_dependencies=False` 或 `"none"`，则关闭全部自动注入
    - 若设置 `inject_dependencies=["sg", "labels"]`，则仅注入列出的依赖
    - 旧参数 `inject_sg/inject_labels/inject_affinity` 仍兼容，但仅建议用于存量用例

    四、返回值

    - 创建 1 台虚机：返回单个 `dict`
    - 创建多台虚机：返回 `list[dict]`

    每台虚机当前至少包含：
    - `name`, `id`, `ip`, `ipv6`, `host`
    - `flavor`, `image`, `project`
    - `network`, `subnet`
    - `mfip`（仅在 `bind_mfip=True` 时回填）

    五、维护入口

    - 调整直接传参协议：修改 `VmFixtureParams`
    - 新增自动注入依赖：修改 `VM_DEPENDENCY_RESOLVERS`
    - 调整创建优先级或默认值：修改 `_build_vm_create_request`
    - 新增返回字段：修改 `VmMetadata` 与元数据收集函数
    """
    params = _get_vm_fixture_params(request)
    instance_params_list = params.get("instances") or []
    if instance_params_list and not isinstance(instance_params_list, list):
        raise TypeError("'vm.instances' expects a list of dict items")

    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    vm_names: list[str] = []

    try:
        metadata_list: list[VmMetadata] = []

        if instance_params_list:
            shared_params = {key: value for key, value in params.items() if key != "instances"}
            for instance_params in instance_params_list:
                instance_config = _build_vm_instance_params(shared_params, instance_params)
                base_name = random_data()
                create_request, count, network, subnet = _build_vm_create_request(request, instance_config, base_name)
                if count != 1:
                    raise ValueError("'vm.instances' items do not support basic.count > 1")

                current_vm_names = _build_vm_fixture_names(create_request["basic"]["name"], count)
                _create_vm_resources(
                    ecs_page=ecs_page,
                    create_request=create_request,
                    vm_names=current_vm_names,
                )
                current_metadata = _collect_vm_fixture_metadata(ecs_page, current_vm_names, network, subnet)
                if instance_config.get("bind_mfip", True):
                    _bind_vm_fixture_mfips(ecs_page, current_metadata, network)

                vm_names.extend(current_vm_names)
                metadata_list.extend(current_metadata)
        else:
            bind_mfip = params.get("bind_mfip", True)
            base_name = random_data()
            create_request, count, network, subnet = _build_vm_create_request(request, params, base_name)
            vm_names = _build_vm_fixture_names(create_request["basic"]["name"], count)

            _create_vm_resources(
                ecs_page=ecs_page,
                create_request=create_request,
                vm_names=vm_names,
            )
            metadata_list = _collect_vm_fixture_metadata(ecs_page, vm_names, network, subnet)

            if bind_mfip:
                _bind_vm_fixture_mfips(ecs_page, metadata_list, network)

        yield metadata_list[0] if len(metadata_list) == 1 else metadata_list
    finally:
        try:
            _cleanup_vm_resources(ecs_page, vm_names)
        finally:
            page.close()

@pytest.fixture(scope="function")
def test_context(request):
    """用于在测试用例各步骤间传递数据的上下文"""
    if not hasattr(request.node, "test_context"):
        request.node.test_context = {}
    return request.node.test_context


def _allocate_eips(
    vpc_page: VpcPage,
    count: int = 1,
    pool: str = 'public_net(基础版)',
    method: str = '快速选择',
    ip: str | None = None,
) -> list[str]:
    """分配并返回弹性公网IP列表。"""
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count!r}")

    with allure_step_log(f"Setup: 分配 {count} 个弹性公网IP"):
        created_ips = vpc_page.eip_allocate(pool=pool, count=count, method=method, ip=ip)

    if created_ips is None:
        return []
    if isinstance(created_ips, list):
        return created_ips
    if isinstance(created_ips, tuple):
        return list(created_ips)
    return [created_ips]


def _release_eips(
    vpc_page: VpcPage,
    created_ips: str | list[str] | tuple[str, ...] | None,
) -> None:
    """释放已创建的弹性公网IP。"""
    if created_ips is None:
        current_ips = []
    elif isinstance(created_ips, list):
        current_ips = created_ips
    elif isinstance(created_ips, tuple):
        current_ips = list(created_ips)
    else:
        current_ips = [created_ips]

    with allure_step_log(f"Teardown: 释放弹性公网IP {current_ips}"):
        if not current_ips:
            return

        try:
            for current_ip in current_ips:
                vpc_page.goto_service('虚拟私有云')
                vpc_page.search(current_ip)
                if current_ip in vpc_page.get_eip_list():
                    vpc_page.eip_release(current_ip)
                    vpc_page.assert_deleted(current_ip)
                vpc_page.btn_reset.click()
        except Exception as e:
            logger.warning(f"清理弹性公网IP时出错: {e}")


@pytest.fixture(scope="function")
def eip(page: Any, request: pytest.FixtureRequest) -> Iterator[str | list[str]]:
    """创建并返回弹性公网IP，测试结束后自动清理。"""
    params = getattr(request, 'param', {})
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        raise TypeError(
            f"'eip' fixture expects request.param to be a dict, got {type(params).__name__}"
        )

    count = params.get('count', 1)
    pool = params.get('pool', 'public_net(基础版)')
    method = params.get('method', '快速选择')
    ip = params.get('ip')

    vpc_page = VpcPage(page)
    vpc_page.goto_service('虚拟私有云')

    created_ips = _allocate_eips(vpc_page, count=count, pool=pool, method=method, ip=ip)
    result = created_ips[0] if count == 1 else created_ips

    try:
        yield result
    finally:
        _release_eips(vpc_page, created_ips)
