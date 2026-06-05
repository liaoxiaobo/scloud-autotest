"""pytest 条件跳过装饰器。

根据环境配置（存储类型、架构、节点数等）决定是否跳过测试用例。
所有装饰器只读取 Config，不依赖具体服务语义。
"""

from functools import wraps

import pytest

from sugon_web.config.config import Config
from sugon_web.utils.logger import logger


def skip_stor(*stor_value):
    """存储类型跳过装饰器。

    当当前配置的存储类型在指定的列表中时，跳过测试用例。

    Args:
        *stor_value: 需要跳过测试的存储类型列表

    Examples:
        @skip_stor('ceph')
        def test_function(self):
            pass
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            stor = Config.get("stor")
            if stor in stor_value:
                pytest.skip(f"{stor}存储不支持该测试用例")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator


def only_stor(*stor_value):
    """存储类型支持装饰器。

    当当前配置的存储类型不在指定的列表中时，跳过测试用例。
    与 skip_stor 逻辑相反。

    Args:
        *stor_value: 支持测试的存储类型列表
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            stor = Config.get("stor")
            if stor not in stor_value:
                supported = ", ".join(stor_value)
                pytest.skip(f"此测试用例仅支持 {supported} 存储，当前为 {stor}")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator


def skip_if_nodes_less_than(min_nodes=2):
    """节点数跳过装饰器。

    当物理机节点数小于指定值时，跳过测试用例。

    Args:
        min_nodes: 最小节点数，默认为 2
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            nodes = Config.get('_node_count', "")
            if int(nodes) < min_nodes:
                logger.warning(f"节点数不足，准备跳过测试")
                pytest.skip(f"节点数不足，当前节点数: {nodes}，要求最小节点数: {min_nodes}")
            logger.info(f"节点数满足要求，继续执行测试")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator


def skip_arch(*arch_value):
    """架构类型跳过装饰器。

    当当前配置的架构类型在指定的列表中时，跳过测试用例。

    Args:
        *arch_value: 需要跳过测试的架构类型列表 (如 'aarch64', 'x86_64')
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            architecture = Config.get("architecture")
            if architecture in arch_value:
                pytest.skip(f"{architecture}架构不支持该测试用例")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator
