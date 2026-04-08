from .affinity import AffinityGroupPage
from .ecs import EcsPageBase
from .image import ImageServicePage
from .label import LabelPage
from .recycle import RecyclePage
from .snapshot import SnapshotPage


class ElasticCloudServerPage(EcsPageBase):
    pass


class EcsPage(
    RecyclePage,
    AffinityGroupPage,
    ImageServicePage,
    SnapshotPage,
    LabelPage,
    EcsPageBase,
):
    """兼容现有用例的计算页面聚合对象。"""


class EcsCreatePage(EcsPage):
    pass


__all__ = [
    "AffinityGroupPage",
    "EcsCreatePage",
    "EcsPage",
    "EcsPageBase",
    "ElasticCloudServerPage",
    "ImageServicePage",
    "LabelPage",
    "RecyclePage",
    "SnapshotPage",
]
