from .affinity import AffinityGroupMixin
from .bms import BmsPage
from .ecs import EcsMixin
from .image import ImageServiceMixin
from .label import LabelMixin
from .recycle import RecycleMixin
from .snapshot import SnapshotMixin


class EcsPage(
    EcsMixin,
    RecycleMixin,
    AffinityGroupMixin,
    ImageServiceMixin,
    SnapshotMixin,
    LabelMixin,
):
    """兼容现有计算用例的聚合页面对象。"""
    service_name = "弹性云服务器"


__all__ = ["EcsPage", "BmsPage"]
