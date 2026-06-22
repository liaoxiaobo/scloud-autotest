from sugon_web.pages.ops import OpsPage
from sugon_web.assertions.compute.ecs import EcsAssertionMixin

from .ecs_create import (
    EcsCreateMixin,
    EcsCreateRequest,
    EcsBasicConfig,
    EcsStorageConfig,
    EcsNetworkConfig,
    EcsManageConfig,
    EcsAdvancedConfig,
    _normalize_ecs_create_request,
)
from .ecs_lifecycle import EcsLifecycleMixin
from .ecs_network import EcsNetworkMixin
from .ecs_migration import EcsMigrationMixin
from .ecs_volume import EcsVolumeMixin
from .ecs_batch import EcsBatchMixin
from .ecs_detail import EcsDetailMixin
from .ecs_ssh import EcsSshMixin
from .ecs_keypair import EcsKeypairMixin

class EcsMixin(
    EcsKeypairMixin,
    EcsCreateMixin,
    EcsLifecycleMixin,
    EcsNetworkMixin,
    EcsMigrationMixin,
    EcsVolumeMixin,
    EcsBatchMixin,
    EcsDetailMixin,
    EcsSshMixin,
    EcsAssertionMixin,
    OpsPage,
):
    """兼容现有计算用例的聚合 Mixin，所有方法按功能域拆分到子 Mixin 中。"""
    pass
