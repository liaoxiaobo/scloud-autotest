from sugon_web.pages.cms.inspection import InspectionMixin
from sugon_web.pages.network import MonitorMixin


class CmsPage(
    InspectionMixin,
    MonitorMixin,
):
    """网络服务页面聚合类。"""

    service_name = "运维"

__all__ = ["CmsPage"]
