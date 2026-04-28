from .acl import AclMixin
from .eip import EipMixin
from .internal_dns import InternalDnsMixin
from .ip_group import IpGroupMixin
from .nat import NatMixin
from .peer_connect import PeerConnectMixin
from .qos import QosMixin
from .sg import SgMixin
from .slb import SlbMixin
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
):
    """网络服务页面聚合类。"""

    service_name = "虚拟私有云"

__all__ = ["VpcPage"]
