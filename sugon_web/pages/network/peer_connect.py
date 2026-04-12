import re

from playwright.sync_api import expect

from sugon_web.common.base import submenu


class PeerConnectMixin:
    """对等连接页面动作。"""

    @submenu("对等连接")
    def peer_connect_create(self, name, requester_vpc, receiver_vpc, desc=""):
        """创建对等连接。"""
        self.btn_create.click()

        dialog = self.get_by_role("dialog", name="新建对等连接")
        dialog.get_by_placeholder("请输入名称").fill(name)

        account_radio = dialog.get_by_role("radio", name="当前账户")
        if account_radio.count() > 0 and account_radio.first.is_visible():
            account_radio.first.click()

        requester_select = dialog.get_by_placeholder("请选择本端VPC")
        requester_select.click()
        requester_option = self.locator(".el-select-dropdown:visible").last.locator("li").filter(
            has_text=re.compile(rf"^{re.escape(requester_vpc)}$")
        ).first
        expect(requester_option).to_be_visible(timeout=8000)
        requester_option.click()

        self.page.wait_for_timeout(500)

        receiver_select = dialog.get_by_placeholder("请选择对端vpc")
        receiver_select.click()
        receiver_option = self.locator(".el-select-dropdown:visible").last.locator("li").filter(
            has_text=re.compile(rf"^{re.escape(receiver_vpc)}$")
        ).first
        expect(receiver_option).to_be_visible(timeout=8000)
        receiver_option.click()

        if desc:
            dialog.locator("textarea").fill(desc)

        dialog.get_by_text("立即创建", exact=True).click()

    @submenu("对等连接")
    def peer_connect_delete(self, names):
        """删除对等连接，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()

    @submenu("对等连接")
    def peer_connect_edit(self, name, new_name=None, new_desc=None):
        """修改对等连接的名称和描述。"""
        self.click_action(name, "修改")

        dialog = self.get_by_role("dialog", name="修改对等连接信息")

        if new_name is not None:
            dialog.get_by_role("textbox").first.clear()
            dialog.get_by_role("textbox").first.fill(new_name)

        if new_desc is not None:
            dialog.locator("textarea").clear()
            dialog.locator("textarea").fill(new_desc)

        self.dialog_confirm.click()
