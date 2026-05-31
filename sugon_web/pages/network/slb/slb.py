from .lb_pool import LbPoolMixin
from .cert import CertMixin


class SlbPage(LbPoolMixin, CertMixin):
    """负载均衡服务统一入口，聚合所有子页面操作。"""
    pass


# 向后兼容
SlbMixin = SlbPage
