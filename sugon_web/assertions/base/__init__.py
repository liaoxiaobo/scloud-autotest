from .popup import PopupAssertionMixin
from .list import ListAssertionMixin
from .status import StatusAssertionMixin


class AssertionsMixin(PopupAssertionMixin, ListAssertionMixin, StatusAssertionMixin):
    """通用断言集合 Mixin。

    聚合所有基础断言能力，供 BasePage 组合使用：
    - PopupAssertionMixin: 弹窗/Toast/对话框断言
    - ListAssertionMixin: 列表页存在性、删除验证等断言
    - StatusAssertionMixin: 资源状态收敛断言
    """
    pass


__all__ = [
    "PopupAssertionMixin",
    "ListAssertionMixin",
    "StatusAssertionMixin",
    "AssertionsMixin",
]
