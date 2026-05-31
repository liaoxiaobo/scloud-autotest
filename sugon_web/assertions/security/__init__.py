"""安全合规模块断言层。

按业务域组织 USM/VER/APT 断言 Mixin。
"""

from sugon_web.assertions.security.usm import UsmAssertionMixin
from sugon_web.assertions.security.ver import VerAssertionMixin
from sugon_web.assertions.security.apt import AptAssertionMixin

__all__ = [
    "AptAssertionMixin",
    "UsmAssertionMixin",
    "VerAssertionMixin",
]
