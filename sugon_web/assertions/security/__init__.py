"""安全合规模块断言层。

按业务域组织 USM/VER/APT/VDB/WAF/RAS 断言 Mixin。
"""

from sugon_web.assertions.security.usm import UsmAssertionMixin
from sugon_web.assertions.security.ver import VerAssertionMixin
from sugon_web.assertions.security.apt import AptAssertionMixin
from sugon_web.assertions.security.vdb import VdbAssertionMixin
from sugon_web.assertions.security.waf import WafAssertionMixin
from sugon_web.assertions.security.ras import RasAssertionMixin
from sugon_web.assertions.security.wpt import WptAssertionMixin

__all__ = [
    "AptAssertionMixin",
    "UsmAssertionMixin",
    "VerAssertionMixin",
    "VdbAssertionMixin",
    "WafAssertionMixin",
    "RasAssertionMixin",
    "WptAssertionMixin",
]
