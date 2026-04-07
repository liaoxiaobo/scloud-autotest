from sugon_web.common.base import BasePage

from .acl import AclPage
from .eip import EipMixin
from .ip_group import IpGroupPage
from .nat import NatMixin
from .peer_connect import PeerConnectMixin
from .qos import QosMixin
from .sg import SgPage
from .slb import SlbPage
from .vpc import VpcMixin


class VpcPage(VpcMixin, PeerConnectMixin, EipMixin, NatMixin, QosMixin, BasePage):
    """网络服务页面聚合类。"""
