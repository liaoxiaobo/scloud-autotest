"""公共类型别名。

为 common 层的公共 API 提供统一的类型标注，减少重复和歧义。
"""

from typing import TypeAlias

Seconds: TypeAlias = int
"""超时时间，单位为秒（公共 API 统一使用秒）。"""

ResourceName: TypeAlias = str
"""资源名称。"""

ResourceNames: TypeAlias = str | list[str]
"""单个资源名称或资源名称列表。"""

ColumnData: TypeAlias = list[str]
"""表格列数据。"""

TableRowData: TypeAlias = dict[str, str]
"""单行表格数据（表头: 单元格内容）。"""
