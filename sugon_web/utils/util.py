"""utils/util.py —— 向后兼容转发文件。

⚠️ 本文件已按 5.1.2 职责纯化方案拆分，不再包含实际实现。
现有代码的 import 路径仍保持可用，但新代码请使用以下新路径：

┌─────────────────────────────┬──────────────────────────────────────┐
│  旧路径 (from utils.util)   │  新路径                              │
├─────────────────────────────┼──────────────────────────────────────┤
│ random_data                 │ sugon_web.utils.data                 │
│ load_data                   │ sugon_web.utils.data                 │
│ random_string               │ sugon_web.utils.data                 │
│ auto_days                   │ sugon_web.utils.data                 │
│ render_data                 │ sugon_web.utils.data                 │
│ get_file_abspath            │ sugon_web.utils.data                 │
│ skip_stor / only_stor       │ sugon_web.framework.decorators       │
│ skip_if_nodes_less_than     │ sugon_web.framework.decorators       │
│ skip_arch                   │ sugon_web.framework.decorators       │
│ capture_failure_screenshot  │ sugon_web.framework.hooks            │
│ get_page_from_item          │ sugon_web.framework.hooks            │
└─────────────────────────────┴──────────────────────────────────────┘

TODO：逐步迁移现有 import，本文件将在所有引用清理后移除。
"""

# === 纯数据/工具 ===
from sugon_web.utils.data import (
    auto_days,
    get_file_abspath,
    load_data,
    random_data,
    random_string,
    render_data,
)

# === 框架装饰器 ===
from sugon_web.framework.decorators import (
    only_stor,
    skip_arch,
    skip_if_nodes_less_than,
    skip_stor,
)

# === pytest 钩子辅助 ===
from sugon_web.framework.hooks import capture_failure_screenshot, get_page_from_item

__all__ = [
    # data
    "auto_days",
    "get_file_abspath",
    "load_data",
    "random_data",
    "random_string",
    "render_data",
    # decorators
    "only_stor",
    "skip_arch",
    "skip_if_nodes_less_than",
    "skip_stor",
    # hooks
    "capture_failure_screenshot",
    "get_page_from_item",
]
