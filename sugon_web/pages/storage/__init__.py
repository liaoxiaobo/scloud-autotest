from .evs import EvsPage as VolumePage
from .evss import EvssPage
from .recycle import RecyclePage


class EvsPage(VolumePage, RecyclePage, EvssPage):
    """兼容现有存储用例的聚合页面对象。"""


__all__ = ["EvsPage", "VolumePage", "RecyclePage", "EvssPage"]
