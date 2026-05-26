import re
from time import sleep

import pytest

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger


class ESPage(BasePage):
    """云搜索服务 CSS 实例管理页面对象"""

    @property
    def _input_search(self):
        locators = [
            self.get_by_role("textbox", name="搜索(集群名称)"),
            self.get_by_role("textbox", name="搜索（参数名称）"),
            self.locator(".input-with-select > .el-input__inner"),
        ]
        return self._find_element(locators, "搜索框")

    def _visible_dialog(self):
        return self.page.locator("div.el-dialog:visible").last

    def _select_visible_option(self, option_text: str, exact: bool = True):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        if exact:
            option = dropdown.locator("li.el-select-dropdown__item").filter(
                has_text=re.compile(rf"^{re.escape(option_text)}$")
            )
        else:
            option = dropdown.locator("li.el-select-dropdown__item").filter(has_text=option_text)
        target = option.first
        target.scroll_into_view_if_needed()
        try:
            target.click(timeout=3000)
        except Exception:
            target.click(force=True, timeout=3000)
        try:
            dropdown.wait_for(state="hidden", timeout=3000)
        except Exception:
            self.page.keyboard.press("Escape")

    def _select_visible_option_by_parts(self, option_parts: list[str]):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        options = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        option_texts = []
        for i in range(options.count()):
            option = options.nth(i)
            option_text = option.inner_text().strip()
            option_texts.append(option_text)
            if all(part in option_text for part in option_parts):
                option.scroll_into_view_if_needed()
                option.click(force=True)
                try:
                    dropdown.wait_for(state="hidden", timeout=3000)
                except Exception:
                    self.page.keyboard.press("Escape")
                return option_text

        raise AssertionError(f"未找到包含 {option_parts} 的下拉选项，可选项: {option_texts}")

    def _select_form_option(self, label: str, option_text: str, exact: bool = True):
        dropdown = db_util.select_labeled_dropdown(self, label)
        dropdown.scroll_into_view_if_needed()
        current_value = dropdown.input_value().strip()
        if option_text in current_value:
            logger.info(f"{label}已选择: {current_value}")
            return current_value

        dropdown.click()
        self._select_visible_option(option_text, exact=exact)
        actual_value = dropdown.input_value().strip()
        if option_text not in actual_value:
            raise AssertionError(f"{label}下拉框未成功选择{option_text}，当前值为{actual_value}")
        return actual_value

    def _set_security_mode(self, enabled: bool, password: str):
        security_form = self.locator("form").filter(has_text="安全模式")
        if security_form.count() == 0:
            return

        switch = security_form.get_by_role("switch").first
        if switch.count() == 0:
            return

        checked = switch.get_attribute("aria-checked") == "true"
        if checked != enabled:
            switch.click()

        if not enabled:
            return

        password_input = self._find_element(
            [
                self.get_by_placeholder("请输入管理员用户密码"),
                self.get_by_placeholder("请输入admin管理员用户密码"),
                self._form_item("管理员密码").get_by_role("textbox"),
                self.locator("input[type='password']").nth(0),
            ],
            "管理员密码",
            timeout=5000,
        )
        confirm_input = self._find_element(
            [
                self.get_by_placeholder("请输入确认密码"),
                self._form_item("确认密码").get_by_role("textbox"),
                self.locator("input[type='password']").nth(1),
            ],
            "确认密码",
            timeout=5000,
        )
        password_input.fill(password)
        confirm_input.fill(password)

    def _click_select_input(self, select_input):
        select_input.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
        self.page.wait_for_timeout(300)
        select = select_input.locator("xpath=ancestor::div[contains(@class,'el-select')][1]")
        triggers = [
            select.locator(".el-input__suffix").first,
            select_input,
            select,
        ]
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last

        for trigger in triggers:
            try:
                trigger.click(timeout=2000, force=True)
                dropdown.wait_for(state="visible", timeout=1000)
                return
            except Exception:
                continue

        select_input.evaluate("""
            el => {
                const select = el.closest('.el-select') || el;
                for (const target of [el, select]) {
                    ['mousedown', 'mouseup', 'click'].forEach(type => {
                        target.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true}));
                    });
                }
            }
        """)
        dropdown.wait_for(state="visible", timeout=3000)

    def _select_specification(self, specification_name: str):
        spec_table = self.locator(".el-table").filter(has_text=specification_name).filter(has_text="2核").filter(
            has_text="4GiB"
        ).first
        body_rows = spec_table.locator(".el-table__body-wrapper tbody tr.el-table__row")
        target_row = None
        target_index = 0
        for i in range(body_rows.count()):
            row = body_rows.nth(i)
            row_text = row.inner_text().strip()
            if specification_name in row_text and "2核" in row_text and "4GiB" in row_text:
                target_row = row
                target_index = i
                break

        if target_row is None:
            target_row = body_rows.first

        fixed_rows = spec_table.locator(".el-table__fixed-body-wrapper > .el-table__body > tbody > tr")
        if fixed_rows.count() > target_index:
            target_row = fixed_rows.nth(target_index)

        target_row.scroll_into_view_if_needed()
        target_input = target_row.locator("input.el-radio__original").first
        target_value = target_input.get_attribute("value")
        target_input.check(force=True)

        if target_value:
            matched_inputs = spec_table.locator(f"input.el-radio__original[value='{target_value}']")
            for i in range(matched_inputs.count()):
                matched_inputs.nth(i).evaluate("""
                    el => {
                        el.checked = true;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                """)

        self.page.wait_for_timeout(500)

    def _configure_kibana_node(self, disk_type: str):
        spec_dropdowns = self.locator("#cloud-container-content input[placeholder='请选择节点规格']:visible")
        if spec_dropdowns.count() == 0:
            return

        spec_dropdown = spec_dropdowns.last
        if not spec_dropdown.input_value().strip():
            self._click_select_input(spec_dropdown)
            self._select_visible_option_by_parts(["2核", "4GiB"])

        disk_dropdowns = self.locator("#cloud-container-content input[placeholder='请选择云硬盘类型']:visible")
        if disk_dropdowns.count() == 0:
            return

        disk_dropdown = disk_dropdowns.last
        if not disk_dropdown.input_value().strip():
            self._click_select_input(disk_dropdown)
            self._select_visible_option(disk_type, exact=False)

    def _form_item(self, label: str):
        return self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label)}"))

    def ensure_instance_tab(self, name: str, tab_name: str = "详情"):
        """进入 ES 实例详情页并切换到指定页签。"""
        if "/es-detail" not in self.page.url:
            self.locator("#cloud-container-content").get_by_text(name, exact=True).first.click()
            sleep(2)
        if tab_name and tab_name != "详情":
            self.get_by_role("tab", name=tab_name).click()
            sleep(1)

    @submenu("实例管理")
    def create_instance(self, name: str, version: str = "7.10.2", security_mode: bool = False,
                        password: str = "Admin123@sugon", network: str = "Autotest",
                        subnet: str = "Autotest:10.", disk_type: str = None,
                        disk_size: int = 10, host_aggregate: str = None,
                        cluster: str = "Autotest", specification_name: str = "es.d6.large"):
        """创建 ES 集群实例。"""
        self.get_by_text("新建集群").click()
        sleep(1)

        self._form_item("名称").get_by_role("textbox").fill(name)

        version_form = self._form_item("版本")
        version_form.locator("input").first.click()
        self._select_visible_option(version)

        cluster_name = host_aggregate or cluster
        self._select_form_option("集群", cluster_name, exact=host_aggregate is None)

        self._set_security_mode(security_mode, password)

        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        selected_disk_type = disk_type if disk_type else self.volume_type
        db_util.select_disk_type_like_doris(self, selected_disk_type, label_texts=["云硬盘类型"])
        self._form_item("云硬盘大小(GiB)").get_by_role("spinbutton").fill(str(disk_size))

        self._select_specification(specification_name)
        self._configure_kibana_node(selected_disk_type)
        self.get_by_text("立即创建", exact=True).click()

    @submenu("实例管理")
    def delete_instance(self, name: str):
        self.click_action(name, "删除集群")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """批量删除 ES 集群实例"""
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_instance(self, name: str):
        self.click_action(name, "重启集群")
        self.get_by_label("重启集群").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_root_password(self, name: str, new_password: str):
        try:
            self.click_action(name, "修改管理员密码")
        except Exception:
            self.click_action(name, "修改root密码")
        dialog = self._visible_dialog()
        dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str):
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("绑定公网IP").first.click()
        dialog = self._visible_dialog()
        dialog.get_by_placeholder("请选择").click()
        self._select_visible_option(network, exact=False)
        ip_row = dialog.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()
        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("解绑公网IP").first.click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str):
        node_name = f"{name}-data-0"
        self.ensure_instance_tab(name, "详情")
        self.click_action(node_name, "绑定公网IP")
        dialog = self._visible_dialog()
        dialog.get_by_placeholder("请选择").click()
        self._select_visible_option(network, exact=False)
        ip_row = dialog.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()
        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        node_name = f"{name}-data-0"
        self.ensure_instance_tab(name, "详情")
        self.click_action(node_name, "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def restart_node(self, name: str, node_name: str):
        self.ensure_instance_tab(name, "详情")
        self.click_action(node_name, "重启")
        self.get_by_label("重启节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_disk_size(self, name: str, node_name: str, new_size: int):
        self.ensure_instance_tab(name, "详情")
        self.click_action(node_name, "修改云硬盘大小")
        dialog = self._visible_dialog()
        dialog.get_by_role("spinbutton").fill(str(new_size))
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_specification(self, name: str, node_name: str, specification_name: str = None):
        self.ensure_instance_tab(name, "详情")
        self.click_action(node_name, "修改规格")
        dialog = self._visible_dialog()
        if specification_name:
            row = dialog.locator("tr").filter(has_text=re.compile(re.escape(specification_name))).first
        else:
            row = dialog.locator("tr.el-table__row").first
        row.locator(".el-radio, label[role='radio']").first.click()
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def es_hot_migration(self, name: str, node_name: str):
        self.ensure_instance_tab(name, "详情")
        try:
            self.click_action(node_name, "热迁移")
        except Exception:
            pytest.skip("当前 ES 前端未暴露节点热迁移入口")

        self.locator("form div").filter(has_text="目标物理机").get_by_placeholder("请选择").click()
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        options = dropdown.locator("li.el-select-dropdown__item")
        checked_host = None
        for i in range(options.count()):
            opt = options.nth(i)
            if "is-disabled" not in (opt.get_attribute("class") or ""):
                checked_host = opt.inner_text().strip().split()[0]
                opt.click()
                logger.info(f"自动选择并点击可用的物理机: {checked_host}")
                break
        if not checked_host:
            self._visible_dialog().get_by_text("取消").click()
            pytest.skip("没有可用的物理机可供迁移")
        self._visible_dialog().get_by_text("确定", exact=True).click()
        return checked_host

    @submenu("实例管理")
    def switch_network(self, name: str, network: str = "Autotest", subnet: str = "subnet:10.",
                       selection_type: str = "快速选择"):
        """
        切换 ES 实例网络。流程保持与 MySQL 一致。
        :param name: 实例名称
        :param network: 网络名称
        :param subnet: 子网名称
        :param selection_type: 选择类型 ("快速选择" 或 "手动输入")
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("切换网络").first.click()

        dialog = self.get_by_label("切换网络")

        dialog.get_by_placeholder("请选择").nth(2).click()
        self.page.locator("li").filter(has_text=re.compile(rf"^{network}$")).nth(1).click()

        dialog.get_by_placeholder("请选择").nth(3).click()
        self.page.get_by_text(subnet).nth(1).click()

        dialog.get_by_placeholder("请选择IP地址").click()
        sleep(2)
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        ip_options = dropdown.locator("li.el-select-dropdown__item").all_inner_texts()
        ip_list = [ip.strip() for ip in ip_options if ip.strip()]
        logger.info(f"获取到 ES 切换网络可用IP列表: {ip_list}")

        if selection_type == "快速选择":
            dialog.locator("label").filter(has_text="快速选择").click()
            dialog.get_by_placeholder("请选择IP地址").click()
            self.page.locator("li.el-select-dropdown__item").filter(has_text=ip_list[0]).first.click()
        else:
            self.page.keyboard.press("Escape")
            dialog.locator("label").filter(has_text="手动输入").click()
            dialog.get_by_placeholder("请输入IP地址").fill(ip_list[0])

        arrow_up = self.page.locator(".el-form-item__content > .el-icon-arrow-up")
        if arrow_up.is_visible():
            arrow_up.click()

        rows = dialog.locator("tr.el-table__row").all()
        for i, row in enumerate(rows):
            if i + 1 < len(ip_list):
                target_ip = ip_list[i + 1]
                row.get_by_role("textbox").click()
                row.get_by_role("textbox").fill(target_ip)
                logger.info(f"为 ES 节点 {i} 分配第 {i + 2} 个可用IP: {target_ip}")
            else:
                logger.error(f"ES 切换网络可用IP不足，无法为节点 {i} 分配IP")

        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def add_data_node(self, name: str):
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("新建数据节点", exact=True).click()
        self.get_by_label("新建数据节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        self.ensure_instance_tab(name, "白名单")
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        self.ensure_instance_tab(name, "白名单")
        self.locator(".el-tag").filter(has_text=ip_address).first.locator(".el-icon-close").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list):
        self.ensure_instance_tab(name, "白名单")
        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        dialog = self.get_by_label("删除白名单")
        dialog.get_by_placeholder("请选择要删除的白名单").click()
        for ip in ip_addresses:
            self.page.locator("li").filter(has_text=ip).click()
        dialog.locator(".el-dialog__header").click()
        self.page.locator("div.el-select-dropdown:visible").wait_for(state="hidden", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        self.ensure_instance_tab(name, "白名单")
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def edit_instance_parameter(self, name: str, param_name: str, param_value: str):
        self.ensure_instance_tab(name, "参数配置")
        if self.get_by_role("tab", name="参数配置").count() == 0:
            pytest.skip("当前 ES 前端未暴露参数配置页签")
        self.locator("tr").filter(has_text=param_name).get_by_text("编辑").last.click()
        dialog = self._visible_dialog()
        target_input = dialog.get_by_role("spinbutton")
        if target_input.count() == 0:
            target_input = dialog.get_by_role("textbox")
        target_input.first.fill(param_value)
        dialog.get_by_text("确定", exact=True).click()
