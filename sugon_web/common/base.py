from playwright.sync_api import Page

from sugon_web.common.playwright import Playwright
from sugon_web.common.navigation import NavigationMixin, submenu
from sugon_web.common.elements import ElementsMixin
from sugon_web.common.tables import TablesMixin
from sugon_web.common.actions import ActionsMixin
from sugon_web.common.assertions import AssertionsMixin
from sugon_web.common.waits import WaitsMixin
from sugon_web.config.config import Config


class BasePage(
    Playwright,
    NavigationMixin,
    ElementsMixin,
    TablesMixin,
    ActionsMixin,
    AssertionsMixin,
    WaitsMixin,
):
    """所有页面对象的基类。

    当前为兼容门面，实际能力由各 Mixin 提供：
    - NavigationMixin: 页面导航 (goto_service, goto_submenu, @submenu)
    - ElementsMixin: 公共元素定位器 (popup, btn_create, dialog_confirm 等)
    - TablesMixin: 表格操作 (get_row_by_name, get_column_data, sort_by_header 等)
    - ActionsMixin: 行操作 (click_action, search, goto_detail_page)
    - AssertionsMixin: 断言集合 (assert_popup_success, assert_status, assert_deleted 等)
    - WaitsMixin: 等待策略 (wait_for_page_ready, _dismiss_hover_tips)
    """

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # 从内存中读取，不会重复加载文件
        self.stor = Config.get('stor')
        self.storage_pool, self.volume_type = self.stor + '-test', self.stor + '-type'


# 保持原有导入兼容
__all__ = ["BasePage", "submenu"]
