from sugon_web.pages.cms.inspection import InspectionMixin
from sugon_web.pages.cms.storage_pool import StoragePoolMixin
from sugon_web.pages.network import MonitorMixin


class CmsPage(
    InspectionMixin,
    StoragePoolMixin,
    MonitorMixin,
):
    """网络服务页面聚合类。"""

    service_name = "运维"

__all__ = ["CmsPage"]
