from sugon_web.pages.container.cce_base import CceBaseMixin
from sugon_web.pages.container.cce_cluster import CceClusterMixin
from sugon_web.pages.container.cce_config import CceConfigMixin
from sugon_web.pages.container.cce_node import CceNodeMixin
from sugon_web.pages.container.cce_storage import CceStorageMixin


class CcePage(CceBaseMixin, CceClusterMixin, CceNodeMixin,
              CceStorageMixin, CceConfigMixin):
    """云容器引擎CCE页面聚合类（保持对外接口不变）。"""

    service_name = "云容器引擎"
