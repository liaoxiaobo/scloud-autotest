from playwright.sync_api import Page

from sugon_web.common.playwright import Playwright
from sugon_web.common.components.navigation import NavigationMixin, submenu
from sugon_web.common.components.buttons import ButtonsMixin
from sugon_web.common.components.dialogs import DialogsMixin
from sugon_web.common.components.inputs import InputsMixin
from sugon_web.common.components.selectors import SelectorsMixin
from sugon_web.common.components.tables import TablesMixin
from sugon_web.common.components.actions import ActionsMixin
from sugon_web.assertions.base import AssertionsMixin
from sugon_web.common.components.waits import WaitsMixin
from sugon_web.config.config import Config
from sugon_web.config.constants import SERVICE_PATH_MAP



class BasePage(
    Playwright,
    NavigationMixin,
    ButtonsMixin,
    DialogsMixin,
    InputsMixin,
    SelectorsMixin,
    TablesMixin,
    ActionsMixin,
    AssertionsMixin,
    WaitsMixin,
):
    """所有页面对象的基类。

    当前为兼容门面，实际能力由各 Mixin 提供：
    - NavigationMixin: 页面导航 (goto_service, goto_submenu, @submenu)
    - ButtonsMixin: 按钮类组件 (btn_create, btn_submit, btn_reset 等)
    - DialogsMixin: 弹窗/对话框组件 (popup, dialog_confirm, close_dialog_if_exists 等)
    - InputsMixin: 输入框组件 (input_name, input_password 等)
    - SelectorsMixin: 选择器组件 (select_network, project_dropdown 等)
    - TablesMixin: 表格操作 (get_row_by_name, get_column_data, sort_by_header 等)
    - ActionsMixin: 交互操作 (click_action, search, goto_detail_page)
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
