import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect


class IpGroupPage(BasePage):
    """负载均衡 IP地址组页面对象。"""

    def _get_dialog(self, *titles):
        locators = []
        for title in titles:
            locators.extend([
                self.get_by_role("dialog", name=title),
                self.get_by_label(title),
                self.get_by_role("dialog").filter(has_text=title),
            ])
        locators.append(self.get_by_role("dialog"))
        return self._find_element(locators, "IP地址组弹窗", timeout=5000)

    @staticmethod
    def _normalize_ip_addresses(ip_addresses):
        if ip_addresses is None:
            return None
        if isinstance(ip_addresses, str):
            return ip_addresses
        return "\n".join(str(ip).strip() for ip in ip_addresses if str(ip).strip())

    def _fill_ip_group_form(self, dialog, name=None, ip_addresses=None, desc=None, enable_ipv6=None):
        if name is not None:
            name_input = dialog.locator(".el-form-item").filter(has_text=re.compile(r"名称")).locator("input[type='text']")
            if name_input.count() == 0:
                name_input = dialog.locator("input[type='text']")
            name_input.fill(name)

        if enable_ipv6 is not None:
            checkbox = dialog.locator("label").filter(has_text=re.compile(r"启用IPv6"))
            checkbox_input = checkbox.locator("input[type='checkbox']")
            if checkbox_input.count() > 0 and checkbox_input.is_checked() != enable_ipv6:
                checkbox.click()

        if ip_addresses is not None:
            ip_input = dialog.locator(".el-form-item").filter(has_text=re.compile(r"IP地址")).locator("textarea")
            if ip_input.count() == 0:
                ip_input = dialog.locator("textarea")
            ip_input.fill(self._normalize_ip_addresses(ip_addresses))

        if desc is not None:
            desc_input = dialog.locator(".el-form-item").filter(has_text=re.compile(r"描述")).locator("textarea")
            if desc_input.count() == 0:
                textareas = dialog.locator("textarea")
                desc_input = textareas.nth(1) if textareas.count() > 1 else textareas.first
            desc_input.fill(desc)

    @submenu("IP地址组")
    def ip_group_create(self, name, ip_addresses, desc=None, enable_ipv6=False):
        """创建IP地址组。"""
        self.btn_create.click()
        dialog = self._get_dialog("新建IP地址组")
        self._fill_ip_group_form(
            dialog,
            name=name,
            ip_addresses=ip_addresses,
            desc=desc,
            enable_ipv6=enable_ipv6,
        )
        self.dialog_confirm.click()

    @submenu("IP地址组")
    def ip_group_delete(self, names):
        """删除IP地址组，支持单个和批量。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()

    @submenu("IP地址组")
    def ip_group_edit(self, name, new_name=None, new_ip_addresses=None, new_desc=None, enable_ipv6=None):
        """修改IP地址组。"""
        self.click_action(name, "修改")
        dialog = self._get_dialog("修改IP地址组")
        self._fill_ip_group_form(
            dialog,
            name=new_name,
            ip_addresses=new_ip_addresses,
            desc=new_desc,
            enable_ipv6=enable_ipv6,
        )
        dialog.get_by_text("确定", exact=True).click()

    @submenu("IP地址组")
    def ip_group_edit_in_detail(self, name, old_ip_addresses, new_ip_addresses):
        """在详情页修改IP地址。

        Args:
            name: IP地址组名称。
            old_ip_addresses: 需要被替换的原IP地址，支持单个地址或地址列表。
            new_ip_addresses: 修改后的IP地址，支持单个地址或地址列表。
        """
        self.goto_ip_group_detail(name)
        targets = old_ip_addresses if isinstance(old_ip_addresses, list) else [old_ip_addresses]
        self.select_rows_by_names([str(ip) for ip in targets])
        self.get_by_text("修改IP地址", exact=True).click()
        dialog = self._get_dialog("修改IP地址")
        self._fill_ip_group_form(dialog, ip_addresses=new_ip_addresses)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("IP地址组")
    def ip_group_search(self, keyword):
        """搜索IP地址组。"""
        self.search(keyword)

    @submenu("IP地址组")
    def ip_group_search_reset(self):
        """重置IP地址组搜索条件。"""
        self.btn_reset.click()
        self.page.wait_for_timeout(1000)

    @submenu("IP地址组")
    def goto_ip_group_detail(self, name, tab_name=None):
        """进入IP地址组详情页。"""
        target_row = self.get_row_by_name(name)
        clickable = target_row.locator("a").first
        if clickable.count() == 0:
            clickable = target_row.get_by_text(name, exact=True).first
        if clickable.count() == 0:
            clickable = target_row.locator("td").nth(1)
        clickable.click()

        if tab_name:
            self.get_by_role("tab", name=tab_name).click()

    def assert_detail_basic_info(self, name=None, desc=None):
        """校验详情页基本信息区域。"""
        detail_root = self.locator("#detail_container, #cloud-container-content").first
        expect(detail_root).to_be_visible(timeout=5000)
        if name is not None:
            expect(detail_root).to_contain_text(name)
        if desc is not None:
            expect(detail_root).to_contain_text(desc)

    def get_detail_ip_addresses(self):
        """获取详情页IP地址列表。"""
        return self.get_column_data("IP地址", context="active-tab")

    @submenu("IP地址组")
    def ip_group_add_ip_addresses(self, name, ip_addresses):
        """在详情页添加IP地址。

        Args:
            name: IP地址组名称。
            ip_addresses: 需要新增的IP地址，支持单个地址或地址列表。
        """
        self.goto_ip_group_detail(name)
        self.get_by_text("添加IP地址", exact=True).click()
        dialog = self._get_dialog("添加IP地址")
        self._fill_ip_group_form(dialog, ip_addresses=ip_addresses)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("IP地址组")
    def ip_group_delete_ip_addresses(self, name, ip_addresses):
        """在详情页删除IP地址。

        Args:
            name: IP地址组名称。
            ip_addresses: 需要删除的IP地址，支持单个地址或地址列表。
        """
        self.goto_ip_group_detail(name)
        targets = ip_addresses if isinstance(ip_addresses, list) else [ip_addresses]
        for ip in targets:
            self.click_action(str(ip), "删除")
            self.dialog_confirm.click()

    @submenu("IP地址组")
    def ip_group_batch_delete_ip_addresses(self, name, ip_addresses):
        """在详情页批量删除IP地址。

        Args:
            name: IP地址组名称。
            ip_addresses: 需要批量删除的IP地址，支持单个地址或地址列表。
        """
        self.goto_ip_group_detail(name)
        targets = ip_addresses if isinstance(ip_addresses, list) else [ip_addresses]
        self.select_rows_by_names([str(ip) for ip in targets])
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
