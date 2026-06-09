import re

from sugon_web.common.base import BasePage, submenu


class QosMixin(BasePage):
    """网络 QoS 页面动作。"""

    _NO_CHANGE = object()

    @submenu("网络QoS")
    def qos_create(self, name, send_rate, recv_rate, desc=""):
        """创建网络QoS。"""
        self.btn_create.click()

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
    def qos_edit(self, name, new_name=_NO_CHANGE, new_send_rate=_NO_CHANGE,
                 new_recv_rate=_NO_CHANGE, new_desc=_NO_CHANGE):
        """修改网络QoS。

        Args:
            name: 当前QoS名称。
            new_name: 新名称，默认不修改。
            new_send_rate: 新发送速率，传入None表示改为不限制，默认不修改。
            new_recv_rate: 新接收速率，传入None表示改为不限制，默认不修改。
            new_desc: 新描述，默认不修改。
        """
        try:
            self.click_action(name, "修改")
        except Exception:
            self.click_action(name, "编辑")

        dialog = self.get_by_label("修改QoS")
        if dialog.count() == 0:
            dialog = self.get_by_label("编辑QoS")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")

        if new_name is not self._NO_CHANGE:
            dialog.locator(".el-input__inner").nth(0).fill(new_name)

        if new_send_rate is not self._NO_CHANGE:
            self._set_qos_rate(dialog, "发送速率", new_send_rate)
        if new_recv_rate is not self._NO_CHANGE:
            self._set_qos_rate(dialog, "接收速率", new_recv_rate)
        if new_desc is not self._NO_CHANGE:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()

    @submenu("网络QoS")
    def qos_delete(self, names):
        """删除网络QoS，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()

    @submenu("网络QoS")
    def qos_search(self, keyword):
        """搜索网络QoS。"""
        self.search(keyword)

    @submenu("网络QoS")
    def qos_search_reset(self):
        """重置网络QoS搜索条件。"""
        self.btn_reset.click()
        self.page.wait_for_timeout(1000)
