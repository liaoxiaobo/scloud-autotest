import random
import re

import pytest
from playwright.sync_api import expect

from sugon_web.common.base import submenu


class NatMixin:
    """NAT 网关页面动作。"""

    @submenu("NAT网关")
    def nat_create(self, name, vpc_name, public_ip_pool="public_net(基础版)", eip=None, desc=""):
        """创建NAT网关"""
        self.get_by_text("新建").click()

        self.locator("form div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        self.get_by_role("radiogroup").locator("label").filter(has_text="虚拟私有云").click()
        self.get_by_placeholder("请选择虚拟私有云").click()
        self.locator("li").filter(has_text=vpc_name).click()

        self.get_by_placeholder("请选择公网IP资源池").click()
        self.get_by_text(public_ip_pool).click()

        self.get_by_placeholder("请选择弹性公网IP").click()
        if eip:
            self.get_by_text(eip).click()
        else:
            self.page.wait_for_timeout(1000)
            options = self.page.locator(".el-select-dropdown:visible li.el-select-dropdown__item").all()
            if options:
                random.choice(options).click()
            else:
                self.logger.warning("未找到可用的弹性公网IP")
                self.page.mouse.click(0, 0)

        if desc:
            self.locator("textarea").fill(desc)

        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()

    @submenu("NAT网关")
    def nat_delete(self, names):
        """删除NAT网关，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.get_by_label("删除NAT网关").get_by_text("确定", exact=True).click()

    @submenu("NAT网关")
    def nat_edit(self, name, new_name=None, new_desc=None):
        """修改NAT网关名称和描述"""
        self.click_action(name, "修改")

        if new_name is not None:
            name_input = self.locator("form").locator("input[type=\"text\"]")
            name_input.click()
            name_input.fill(new_name)

        if new_desc is not None:
            self.locator("textarea").click()
            self.locator("textarea").fill(new_desc)

        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()

    @submenu("NAT网关")
    def nat_unbind_eip(self, name):
        """解绑NAT网关的弹性公网IP"""
        data = self.get_row_data(name)
        eip = data.get("弹性公网IP", "")

        self.click_action(name, "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定").click()

        return eip

    @submenu("NAT网关")
    def nat_bind_eip(self, name, network_type="public_net(基础版)"):
        """为NAT网关绑定弹性公网IP"""
        self.click_action(name, "绑定公网IP")

        dialog = self.get_by_label("绑定公网IP")
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)
        available_rows = rows_locator.all()
        if not available_rows:
            pytest.skip("当前环境无可用的弹性公网IP（状态为'关闭'）")
        selected_row = random.choice(available_rows)
        eip = selected_row.get_by_role("cell").nth(1).text_content().strip()
        selected_row.get_by_role("radio").click()

        dialog.get_by_text("确定").click()

        return eip

    @submenu("NAT网关")
    def dnat_rule_create(self, nat_name, ext_port, subnet_cidr, protocol="TCP",
                         private_ip=None, int_port=None, desc=""):
        """在NAT网关详情页创建DNAT规则"""
        self.get_by_role("cell", name=nat_name).locator("a").click()

        self.get_by_role("tab", name="DNAT规则").click()

        self.get_by_text("新建").click()

        self.locator("label").filter(has_text=protocol).click()
        self.get_by_placeholder("端口范围1~32767").fill(str(ext_port))

        subnet_row = self.locator("form div").filter(has_text=re.compile(r"私有子网"))
        subnet_row.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=subnet_cidr).first.click()

        ip_row = self.locator("form div").filter(has_text=re.compile(r"私网IP"))
        ip_row.get_by_placeholder("请选择").click()
        if private_ip:
            ip_option = self.locator("li").filter(has_text=private_ip).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()
        else:
            first_option = self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").first
            expect(first_option).to_be_visible(timeout=8000)
            if not self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").count():
                pytest.skip("私网IP下拉无可用选项，请确认子网内有已创建的虚机")
            first_option.click()

        if int_port is not None:
            self.get_by_placeholder("端口范围1~65535").fill(str(int_port))

        if desc:
            self.locator("textarea").fill(desc)

        self.get_by_label("创建DNAT规则").get_by_text("确定").click()

    def _nat_open_detail_tab(self, nat_name, tab_name):
        """进入 NAT 网关详情并切换到指定 Tab。"""
        self.get_by_role("cell", name=nat_name).locator("a").click()
        self.get_by_role("tab", name=tab_name).click()

    def _select_form_option_by_label(self, form_root, label_pattern, option_text=None):
        """在表单中按标签选择下拉框选项。"""
        form_item = form_root.locator(".el-form-item").filter(
            has=self.locator("label").filter(has_text=label_pattern)
        )
        dropdown = form_item.get_by_placeholder("请选择")
        dropdown.click()

        if option_text:
            option = self.locator("li").filter(has_text=option_text).first
            expect(option).to_be_visible(timeout=8000)
            option.click()
            return option_text

        first_option = self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").first
        expect(first_option).to_be_visible(timeout=8000)
        selected_text = first_option.text_content().strip()
        first_option.click()
        return selected_text

    def _snat_fill_source(self, dialog, source_type, source_value=None):
        """填写 SNAT 规则源地址。"""
        dialog.get_by_role("radio", name=source_type).click()

        if source_value is None:
            return

        if source_type == "私网IP" and isinstance(source_value, dict):
            dropdowns = dialog.get_by_placeholder("请选择")
            visible_dropdowns = [dropdowns.nth(i) for i in range(dropdowns.count()) if dropdowns.nth(i).is_visible()]

            if len(visible_dropdowns) < 2:
                raise AssertionError("私网IP类型未找到足够的下拉框，期望至少包含子网和私网IP两个选择框")

            visible_dropdowns[0].click()
            subnet_option = self.locator("li").filter(has_text=source_value["subnet_cidr"]).first
            expect(subnet_option).to_be_visible(timeout=8000)
            subnet_option.click()

            visible_dropdowns[1].click()
            ip_option = self.locator("li").filter(has_text=source_value["private_ip"]).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()
            return

        select_locator = dialog.get_by_placeholder("请选择")
        if select_locator.count() > 0:
            for i in range(select_locator.count()):
                dropdown = select_locator.nth(i)
                if dropdown.is_visible():
                    dropdown.click()
                    option = self.locator("li").filter(has_text=source_value).first
                    expect(option).to_be_visible(timeout=8000)
                    option.click()
                    return

        inputs = dialog.locator("input:not([disabled]):not([type='radio'])")
        for i in range(inputs.count()):
            input_box = inputs.nth(i)
            if input_box.is_visible():
                input_box.fill(source_value)
                return

        raise AssertionError(f"未找到可填写的SNAT源地址输入控件，source_type={source_type}, source_value={source_value}")

    @submenu("NAT网关")
    def snat_rule_create(self, nat_name, source_type="所有", source_value=None, desc=""):
        """在 NAT 网关详情页创建 SNAT 规则。"""
        self._nat_open_detail_tab(nat_name, "SNAT规则")

        self.get_by_text("新建").click()

        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"创建SNAT规则")).last
        self._snat_fill_source(dialog, source_type, source_value)

        if desc and dialog.locator("textarea").count() > 0:
            dialog.locator("textarea").fill(desc)

        dialog.get_by_text("确定", exact=True).click()

    @submenu("NAT网关")
    def snat_rule_edit(self, nat_name, source_address, new_source_type=None, new_source_value=None, new_desc=None):
        """在 NAT 网关详情页修改 SNAT 规则。"""
        self._nat_open_detail_tab(nat_name, "SNAT规则")

        self.click_action(source_address, "修改")

        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"SNAT规则")).last

        if new_source_type is not None:
            self._snat_fill_source(dialog, new_source_type, new_source_value)

        if new_desc is not None and dialog.locator("textarea").count() > 0:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()

    def snat_rule_delete(self, source_addresses):
        """删除 SNAT 规则，支持单个和批量操作（需已在 NAT 网关详情页的 SNAT 规则 Tab 下）。"""
        if isinstance(source_addresses, list):
            self.select_rows_by_names(source_addresses)
            self.btn_batch_delete.click()
        else:
            self.click_action(str(source_addresses), "删除")

        self.dialog_confirm.click()

    @submenu("NAT网关")
    def dnat_rule_edit(self, nat_name, ext_port, new_ext_port=None, new_protocol=None,
                       new_private_ip=None, new_int_port=None, new_desc=None):
        """在NAT网关详情页修改DNAT规则"""
        self.get_by_role("cell", name=nat_name).locator("a").click()

        self.get_by_role("tab", name="DNAT规则").click()

        self.click_action(str(ext_port), "修改")

        dialog = self.get_by_label("修改DNAT规则")

        if new_protocol:
            dialog.locator("label").filter(has_text=new_protocol).click()

        if new_ext_port is not None:
            dialog.get_by_placeholder("端口范围1~32767").fill(str(new_ext_port))

        if new_private_ip:
            ip_row = dialog.locator("form div").filter(has_text=re.compile(r"私网IP"))
            ip_row.get_by_placeholder("请选择").click()
            ip_option = self.locator("li").filter(has_text=new_private_ip).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()

        if new_int_port is not None:
            dialog.get_by_placeholder("端口范围1~65535").fill(str(new_int_port))

        if new_desc is not None:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()

    def dnat_rule_delete(self, ext_ports):
        """删除DNAT规则，支持单个和批量操作（需已在NAT网关详情页的DNAT规则Tab下）"""
        if isinstance(ext_ports, list):
            self.select_rows_by_names(ext_ports)
            self.btn_batch_delete.click()
        else:
            self.click_action(str(ext_ports), "删除")

        self.dialog_confirm.click()
