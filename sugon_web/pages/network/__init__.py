from .acl import AclMixin
from .dc import DcMixin
from .cms_monitor import MonitorMixin
from .eip import EipMixin
from .er import ErMixin
from .internal_dns import InternalDnsMixin
from .ip_group import IpGroupMixin
from .nat import NatMixin
from .peer_connect import PeerConnectMixin
from .qos import QosMixin
from .sg import SgMixin
from .slb import SlbMixin
from .tm import TmMixin
from .vpc import VpcMixin


class VpcPage(
    VpcMixin,
    AclMixin,
    SgMixin,
    SlbMixin,
    IpGroupMixin,
    PeerConnectMixin,
    InternalDnsMixin,
    EipMixin,
    NatMixin,
    QosMixin,
    MonitorMixin
):
    """网络服务页面聚合类。"""

    service_name = "虚拟私有云"


class DcPage(DcMixin):
    """云专线DC页面类。"""

    service_name = "云专线DC"


class ErPage(ErMixin):
    """企业路由器页面类。"""

    service_name = "企业路由器"


class TmPage(TmMixin):
    """流量镜像页面类。"""

    service_name = "流量镜像"


__all__ = ["VpcPage", "DcPage", "ErPage", "TmPage"]
