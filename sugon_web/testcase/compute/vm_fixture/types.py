from typing import Any, Callable, NotRequired, TypedDict
from sugon_web.pages.compute.ecs import (
    EcsCreateRequest,
    EcsBasicConfig,
    EcsStorageConfig,
    EcsNetworkConfig,
    EcsManageConfig,
    EcsAdvancedConfig,
)


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
    public_ip: NotRequired[str]
    port_id: NotRequired[str | None]
    project_id: NotRequired[str | None]


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
