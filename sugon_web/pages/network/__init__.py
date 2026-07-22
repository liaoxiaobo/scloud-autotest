from .acl import AclMixin
from .cfw import CfwMixin
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
from .tm import TmMixin
from .sci_transfer_strategy import TransferStrategyMixin
from .slb import SlbMixin, SlbPage
from .vpc import VpcMixin
from .vpn import VpnMixin


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


class CfwPage(CfwMixin):
    """云防火墙页面类。"""

    service_name = "云防火墙"


class DcPage(DcMixin):
    """云专线DC页面类。"""

    service_name = "云专线DC"


class ErPage(ErMixin):
    """企业路由器页面类。"""

    service_name = "企业路由器"


class TmPage(TmMixin):
    """流量镜像页面类。"""

    service_name = "流量镜像"


class VpnPage(VpnMixin):
    """虚拟专用网络VPN页面类。"""

    service_name = "专有网络VPN"


class TransferStrategyPage(TransferStrategyMixin):
    """传输策略组页面类。"""

    service_name = "虚拟私有云"


__all__ = ["VpcPage", "CfwPage", "DcPage", "ErPage", "TmPage", "TransferStrategyPage", "VpnPage", "SlbPage", "SlbMixin"]
