import re

from sugon_web.common.base import submenu


class QosMixin:
    """网络 QoS 页面动作。"""

    @submenu("网络QoS")
    def qos_create(self, name, send_rate, recv_rate, desc=""):
        """创建网络QoS。"""
        self.btn_create.click()
        self.wait_for_page_ready()

        dialog = self.get_by_label("新建QoS")
        if dialog.count() == 0:
            dialog = self.get_by_label("新建网络QoS")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")

        dialog.locator(".el-input__inner").nth(0).fill(name)
        self._set_qos_rate(dialog, "发送速率", send_rate)
        self._set_qos_rate(dialog, "接收速率", recv_rate)
        if desc:
            dialog.locator("textarea").fill(desc)

        submit_btn = dialog.get_by_text("立即创建", exact=True)
        if submit_btn.count() > 0 and submit_btn.first.is_visible():
            submit_btn.click()
        else:
            self.btn_submit.click()
        self.wait_for_page_ready()

    def _set_qos_rate(self, dialog, field_name, value):
        """设置网络QoS速率；value 为 None 时保持不限速。"""
        item = dialog.locator(".el-form-item").filter(has_text=re.compile(field_name)).first
        checkbox = item.locator(".el-checkbox").first
        checkbox_input = item.locator("input[type=\"checkbox\"]").first
        rate_input = item.locator(".el-input__inner:visible").first

        if value is None:
            if checkbox_input.count() > 0 and not checkbox_input.is_checked():
                checkbox.click()
            return

        if checkbox_input.count() > 0 and checkbox_input.is_checked():
            checkbox.locator(".el-checkbox__input").click(force=True)

        if rate_input.is_disabled():
            checkbox.locator(".el-checkbox__input").click(force=True)

        rate_input.fill(str(value))

    @submenu("网络QoS")
    def qos_edit(self, name, new_name=None, new_send_rate=None, new_recv_rate=None, new_desc=None):
        """修改网络QoS。"""
        try:
            self.click_action(name, "修改")
        except Exception:
            self.click_action(name, "编辑")
        self.wait_for_page_ready()

        dialog = self.get_by_label("修改QoS")
        if dialog.count() == 0:
            dialog = self.get_by_label("编辑QoS")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")

        if new_name is not None:
            dialog.locator(".el-input__inner").nth(0).fill(new_name)

        if new_send_rate is not None:
            self._set_qos_rate(dialog, "发送速率", new_send_rate)
        if new_recv_rate is not None:
            self._set_qos_rate(dialog, "接收速率", new_recv_rate)
        if new_desc is not None:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("网络QoS")
    def qos_delete(self, names):
        """删除网络QoS，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("网络QoS")
    def qos_search(self, keyword):
        """搜索网络QoS。"""
        self.search(keyword)

    @submenu("网络QoS")
    def qos_search_reset(self):
        """重置网络QoS搜索条件。"""
        self.btn_reset.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)
