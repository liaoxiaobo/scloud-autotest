"""vm fixture 拆分后的模块集合。

所有内部模块通过此文件统一导出，外部调用方无需关心具体文件位置。
"""

from .types import VmFixtureParams, VmMetadata, VmDependencyResolver

__all__ = ["VmFixtureParams", "VmMetadata", "VmDependencyResolver"]
