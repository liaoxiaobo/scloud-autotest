import re
from time import sleep

import pytest

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger
from sugon_web.config.config import Config


class XScalePage(BasePage):
    """XScale实例管理页面对象"""

    service_name = "xscale"

    def _get_dialog(self, title: str):
        """获取指定标题的可见弹窗"""
        dialog = self.get_by_role("dialog").filter(has_text=title).last
        dialog.wait_for(state="visible", timeout=10000)
        return dialog

    def _select_spec_by_name(self, dialog, spec_name: str) -> str:
        """在规格弹窗中按规格名搜索，并选择搜索结果中的第一条规格"""
        search_input = dialog.get_by_placeholder("搜索（规格名称）")
        if search_input.count() > 0:
            search_input.fill(spec_name)
            dialog.get_by_text("搜索", exact=True).click()
            rows = dialog.locator(".el-table__body-wrapper tbody tr.el-table__row")
            rows.first.wait_for(state="visible", timeout=5000)
        else:
            rows = dialog.locator(".el-table__body-wrapper tbody tr.el-table__row")

        count = rows.count()
        for i in range(count):
            row = rows.nth(i)
            if not row.is_visible():
                continue
            radio = row.locator("label[role='radio']")
            if radio.count() == 0:
                continue
            class_name = radio.first.get_attribute("class") or ""
            if "is-disabled" in class_name:
                raise AssertionError(f"搜索结果中的目标规格不可选: {spec_name}")
            row.scroll_into_view_if_needed()
            actual_spec_name = row.locator("td").nth(2).inner_text().strip()
            radio.first.click(force=True)
            return actual_spec_name

        raise AssertionError(f"未找到规格搜索结果: {spec_name}")

    def _get_node_section(self, section_title: str):
        """根据节点列表标题获取对应的表格区域"""
        section = self.locator(
            f"xpath=//*[normalize-space()='{section_title}']/following::*[contains(@class,'el-table')][1]"
        )
        if section.count() == 0:
            raise AssertionError(f"未找到节点列表区域: {section_title}")
        return section.first

    def get_first_node_name_by_type(self, instance_name: str, node_type: str) -> str:
        """
        在详情页中获取指定节点类型的第一个节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型文本，如“元数据节点”“日志节点”
        :return: 节点名称
        """
        section_title = f"{node_type}列表"
        section = self._get_node_section(section_title)

        fixed_rows = section.locator(".el-table__fixed .el-table__fixed-body-wrapper tbody tr.el-table__row")
        if fixed_rows.count() > 0:
            for i in range(fixed_rows.count()):
                row = fixed_rows.nth(i)
                if not row.is_visible():
                    continue
                node_name = row.locator("td").first.inner_text().strip()
                if node_name:
                    logger.info(f"获取到 {node_type} 的第一个节点: {node_name}")
                    return node_name

        body_rows = section.locator(".el-table__body-wrapper tbody tr.el-table__row")
        for i in range(body_rows.count()):
            row = body_rows.nth(i)
            if not row.is_visible():
                continue
            node_name = row.locator("td").first.inner_text().strip()
            if node_name and node_name not in {"运行中", "就绪"}:
                logger.info(f"获取到 {node_type} 的第一个节点: {node_name}")
                return node_name

        raise AssertionError(f"未在实例 {instance_name} 详情页找到节点类型 {node_type} 的节点")

    def get_node_names_by_type(self, instance_name: str, node_type: str) -> list[str]:
        """
        在详情页中获取指定节点类型的所有节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型文本，如“计算节点”“存储节点”
        :return: 节点名称列表
        """
        section_title = f"{node_type}列表"
        section = self._get_node_section(section_title)
        node_names = []

        fixed_rows = section.locator(".el-table__fixed .el-table__fixed-body-wrapper tbody tr.el-table__row")
        if fixed_rows.count() > 0:
            for i in range(fixed_rows.count()):
                row = fixed_rows.nth(i)
                if not row.is_visible():
                    continue
                node_name = row.locator("td").first.inner_text().strip()
                if node_name and node_name not in node_names:
                    node_names.append(node_name)

        if not node_names:
            body_rows = section.locator(".el-table__body-wrapper tbody tr.el-table__row")
            for i in range(body_rows.count()):
                row = body_rows.nth(i)
                if not row.is_visible():
                    continue
                node_name = row.locator("td").first.inner_text().strip()
                if node_name and node_name not in {"运行中", "就绪"} and node_name not in node_names:
                    node_names.append(node_name)

        if not node_names:
            raise AssertionError(f"未在实例 {instance_name} 详情页找到节点类型 {node_type} 的节点列表")

        logger.info(f"获取到 {node_type} 节点列表: {node_names}")
        return node_names

    def _select_dropdown_option(self, trigger, preferred_text: str = None):
        """点击下拉框并优先选择指定选项，不存在时回退到第一个可用选项"""
        trigger.click()
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        self.page.wait_for_timeout(300)

        options = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        if preferred_text:
            preferred = options.filter(has_text=preferred_text)
            if preferred.count() > 0:
                preferred.first.scroll_into_view_if_needed()
                preferred.first.click(force=True)
                return

        options.first.scroll_into_view_if_needed()
        options.first.click(force=True)

    def _select_node_spec(self, section_index: int):
        """为指定节点配置区域选择首个可用规格"""
        self.get_by_text("选择节点规格", exact=True).nth(section_index).click()
        drawer = self.page.locator(".el-drawer__wrapper:visible").last
        drawer.wait_for(state="visible", timeout=10000)
        drawer.get_by_role("radio").first.click()
        drawer.get_by_text("确定", exact=True).click()

    def _fill_spinbutton(self, index: int, value: int):
        """按顺序填写页面中的步进器值"""
        spin_button = self.get_by_role("spinbutton").nth(index)
        spin_button.click()
        spin_button.fill(str(value))

    @submenu("实例管理")
    def create_instance(
        self,
        name: str,
        version: str = None,
        password: str = "admin1234@sugon",
        network: str = "Autotest",
        subnet: str = "Autotest:10.",
        volume_type: str = None,
        gms_volume_size: int = 50,
        cn_volume_size: int = 50,
        dn_volume_size: int = 100,
        cdc_volume_size: int = 50,
    ):
        """
        创建XScale实例
        :param name: 实例名称
        :param version: 版本，不传时使用页面默认值
        :param password: admin管理员密码
        :param network: 网络名称
        :param subnet: 子网名称，支持前缀匹配
        :param volume_type: 数据盘类型，不传时使用环境默认磁盘类型
        :param gms_volume_size: 元数据节点数据盘大小
        :param cn_volume_size: 计算节点数据盘大小
        :param dn_volume_size: 存储节点数据盘大小
        :param cdc_volume_size: 日志节点数据盘大小
        """
        self.btn_create.click()

        basic_form = self.locator("form").first
        resource_form = self.locator("form").nth(1)

        basic_form.get_by_role("textbox").first.fill(name)

        if version:
            version_trigger = basic_form.locator(".el-select").first.locator("input")
            self._select_dropdown_option(version_trigger, version)

        cluster_trigger = basic_form.locator(".el-select").nth(1).locator("input")
        self._select_dropdown_option(cluster_trigger)
        self.page.wait_for_timeout(1000)

        resource_form.get_by_placeholder("请输入admin管理员用户密码").fill(password)
        db_util.input_confirm_password(self).fill(password)

        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        selected_volume_type = volume_type if volume_type else self.stor
        volume_dropdowns = resource_form.locator(".el-select").locator("input")
        for index in range(2, 6):
            self._select_dropdown_option(volume_dropdowns.nth(index), selected_volume_type)

        self._fill_spinbutton(1, gms_volume_size)
        self._fill_spinbutton(3, cn_volume_size)
        self._fill_spinbutton(5, dn_volume_size)
        self._fill_spinbutton(7, cdc_volume_size)

        for section_index in range(4):
            self._select_node_spec(section_index)

        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name: str):
        """
        删除XScale实例
        :param name: 实例名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """
        修改XScale实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def restart_instance(self, name: str):
        """
        重启XScale实例
        :param name: 实例名称
        """
        self.click_action(name, "重启实例")
        self.get_by_label("重启").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_admin_password(self, name: str, new_password: str):
        """
        修改XScale实例管理员密码
        :param name: 实例名称
        :param new_password: 新密码
        """
        self.click_action(name, "修改管理员密码")
        dialog = self.get_by_label("重置密码")
        dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_instance_status(self, name: str):
        """
        重置XScale实例状态
        :param name: 实例名称
        """
        self.click_action(name, "状态重置")

    @submenu("实例管理")
    def get_jdbc_connection_string(self, name: str) -> str:
        """
        打开JDBC连接串弹窗并返回连接串文本
        :param name: 实例名称
        :return: JDBC连接串
        """
        self.click_action(name, "JDBC连接串")
        dialog = self.get_by_role("dialog").filter(has_text="JDBC连接字符串")
        dialog.wait_for(state="visible", timeout=5000)
        return dialog.locator(".jdbc-text").inner_text().strip()

    def close_jdbc_dialog(self):
        """关闭JDBC连接串弹窗"""
        dialog = self.get_by_role("dialog").filter(has_text="JDBC连接字符串")
        dialog.get_by_text("关闭", exact=True).click()

    @submenu("实例管理")
    def create_database(self, instance_name: str, db_name: str):
        """
        在指定 XScale 实例下创建数据库
        :param instance_name: 实例名称
        :param db_name: 数据库名称
        """
        self.goto_detail_page(instance_name, tab_name="数据库")
        self.page.wait_for_timeout(1000)
        self.btn_create.click()
        dialog = self.get_by_label("新建数据库")
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(db_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_database(self, instance_name: str, db_name: str):
        """
        在指定 XScale 实例下删除数据库
        :param instance_name: 实例名称
        :param db_name: 数据库名称
        """
        self.goto_detail_page(instance_name, tab_name="数据库")
        self.page.wait_for_timeout(1000)
        self.search(db_name)
        self.click_action(db_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_databases(self, instance_name: str, db_names: list[str]):
        """
        在指定 XScale 实例下批量删除数据库
        :param instance_name: 实例名称
        :param db_names: 数据库名称列表
        """
        self.goto_detail_page(instance_name, tab_name="数据库")
        self.page.wait_for_timeout(1000)
        self.select_rows_by_names(db_names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_user(self, name: str, user_name: str, password: str, db_name: str, privileges: str):
        """
        在指定实例下创建用户并授权
        :param name: 实例名称
        :param user_name: 用户名
        :param password: 密码
        :param db_name: 授权的数据库
        :param privileges: 权限，如“只读”“读写”
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        self.btn_create.click()
        dialog = self.get_by_role("dialog")
        dialog.locator("form div").filter(has_text="用户名").get_by_role("textbox").fill(user_name)
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)
        dialog.locator("form div").filter(has_text=re.compile(r"数据库")).get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=db_name).click()
        dialog.locator("div").filter(has_text=re.compile(r"^权限")).locator("i").click()
        self.page.locator("li").filter(has_text=privileges).click()
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def change_user_privileges(self, name: str, user_name: str, new_password: str):
        """
        修改用户密码
        :param name: 实例名称
        :param user_name: 用户名
        :param new_password: 新密码
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        self.click_action(user_name, "修改用户")
        dialog = self.get_by_label("修改用户")
        dialog.locator("input[type=\"password\"]").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def authorize_user(self, name: str, user_name: str, db_name: str, privileges: str = "读写"):
        """
        为用户授权数据库
        :param name: 实例名称
        :param user_name: 用户名
        :param db_name: 数据库名称
        :param privileges: 权限，如“只读”“读写”
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        self.click_action(user_name, "授权")
        dialog = self.get_by_label("授权", exact=True)
        self.page.wait_for_timeout(1000)
        dialog.get_by_role("row", name=re.compile(db_name)).locator("span").nth(1).click()
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=privileges).click()
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_user(self, name: str, user_name: str):
        """
        在指定实例下删除用户
        :param name: 实例名称
        :param user_name: 用户名
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        self.click_action(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_users(self, name: str, user_names: list[str]):
        """
        在指定实例下批量删除用户
        :param name: 实例名称
        :param user_names: 用户名列表
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        for user_name in user_names:
            self.get_by_role("row", name=re.compile(user_name)).locator("span").nth(1).click()
        self.btn_batch_delete.click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def deauthorize_user(self, name: str, user_name: str, db_name: str):
        """
        解除用户数据库授权
        :param name: 实例名称
        :param user_name: 用户名
        :param db_name: 数据库名称
        """
        self.goto_detail_page(name, tab_name="用户")
        self.page.wait_for_timeout(1000)
        self.click_action(user_name, "解除授权")
        dialog = self.get_by_label("解除授权")
        select_input = dialog.get_by_placeholder("请选择")
        select_input.click()
        self.page.locator("li").filter(has_text=db_name).click()
        # XScale 此处为多选下拉，选中后下拉层不会自动收起，需要主动关闭避免遮挡“确定”按钮。
        self.page.keyboard.press("Escape")
        self.page.locator("body > div.el-select-dropdown:visible").last.wait_for(state="hidden", timeout=5000)
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def enable_slow_log(self, name: str):
        """
        为 XScale 实例开启慢日志
        :param name: 实例名称
        """
        self.goto_detail_page(name, tab_name="慢日志")
        self.page.wait_for_timeout(1000)
        self.get_by_text("立即开启").click()
        self.get_by_label("开启慢日志").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def disable_slow_log(self, name: str):
        """
        为 XScale 实例关闭慢日志
        :param name: 实例名称
        """
        self.goto_detail_page(name, tab_name="慢日志")
        self.page.wait_for_timeout(1000)
        self.get_by_text("服务设置").first.click()
        self.get_by_role("switch").locator("span").click()
        self.get_by_label("服务设置").get_by_text("确定").click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """
        为 XScale 实例添加白名单
        :param name: 实例名称
        :param ip_address: IP 地址或 CIDR
        """
        self.goto_detail_page(name, tab_name="白名单")
        self.page.wait_for_timeout(1000)
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定").click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """
        为 XScale 实例删除单个白名单
        :param name: 实例名称
        :param ip_address: IP 地址或 CIDR
        """
        self.goto_detail_page(name, tab_name="白名单")
        self.page.wait_for_timeout(1000)
        self.locator("span").filter(has_text=ip_address).locator("i").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list[str]):
        """
        为 XScale 实例批量删除白名单
        :param name: 实例名称
        :param ip_addresses: IP 地址或 CIDR 列表
        """
        self.goto_detail_page(name, tab_name="白名单")
        self.btn_batch_delete.click()
        self.get_by_placeholder("请选择要删除的白名单").click()
        for ip in ip_addresses:
            self.page.locator("li", has_text=ip).click()
        # XScale 此处为多选下拉，选中后下拉层不会自动收起，需要主动关闭避免遮挡“确定”按钮。
        self.page.keyboard.press("Escape")
        self.page.locator("body > div.el-select-dropdown:visible").last.wait_for(state="hidden", timeout=5000)
        self.get_by_label("删除白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """
        为 XScale 实例重置白名单
        :param name: 实例名称
        """
        self.goto_detail_page(name, tab_name="白名单")
        self.page.wait_for_timeout(1000)
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_node_specification(self, instance_name: str, node_type: str, spec_name: str | None = None) -> str:
        """
        修改节点规格并返回节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :param spec_name: 目标规格名
        :return: 节点名称
        """
        if not spec_name:
            raise AssertionError("修改规格时必须显式传入目标规格名")
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)
        self.click_action(node_name, "修改规格")
        dialog = self._get_dialog("修改规格")
        self._select_spec_by_name(dialog, spec_name)
        dialog.get_by_text("确定", exact=True).click()
        return node_name

    @submenu("实例管理")
    def scale_out_compute_node(self, instance_name: str, disk_type: str = None, disk_size: int = 100) -> str:
        """
        通过详情页按钮为 XScale 实例扩容一个计算节点，并返回新节点名称
        :param instance_name: 实例名称
        :param disk_type: 数据盘类型，不传时使用当前环境默认磁盘类型
        :param disk_size: 数据盘大小
        :return: 新计算节点名称
        """
        self.goto_detail_page(instance_name)
        current_nodes = self.get_node_names_by_type(instance_name, "计算节点")
        new_node_name = f"{instance_name}-cn-{len(current_nodes)}"

        self.get_by_text("计算节点扩容", exact=True).click()
        dialog = self._get_dialog("新增节点")
        selected_disk_type = disk_type if disk_type else self.stor
        self._select_dropdown_option(dialog.locator(".el-select").first.locator("input"), selected_disk_type)
        dialog.get_by_role("spinbutton").fill(str(disk_size))
        dialog.get_by_text("确定", exact=True).click()
        return new_node_name

    @submenu("实例管理")
    def scale_in_compute_node(self, instance_name: str) -> None:
        """
        通过详情页按钮为 XScale 实例缩容一个计算节点
        :param instance_name: 实例名称
        """
        self.goto_detail_page(instance_name)
        self.get_by_text("计算节点缩容", exact=True).click()

    @submenu("实例管理")
    def restart_compute_nodes(self, instance_name: str) -> list[str]:
        """
        通过详情页按钮重启全部计算节点，并返回重启前的计算节点名称列表
        :param instance_name: 实例名称
        :return: 计算节点名称列表
        """
        self.goto_detail_page(instance_name)
        node_names = self.get_node_names_by_type(instance_name, "计算节点")
        self.get_by_text("重启计算节点", exact=True).click()
        self._get_dialog("重启计算节点").get_by_text("确定", exact=True).click()
        return node_names

    @submenu("实例管理")
    def scale_out_storage_node(self, instance_name: str, disk_type: str = None, disk_size: int = 100) -> list[str]:
        """
        通过详情页按钮为 XScale 实例扩容一个存储节点组，并返回新增的三个节点名称
        :param instance_name: 实例名称
        :param disk_type: 数据盘类型，不传时使用当前环境默认磁盘类型
        :param disk_size: 数据盘大小
        :return: 新增节点名称列表
        """
        self.goto_detail_page(instance_name)
        current_nodes = self.get_node_names_by_type(instance_name, "存储节点")
        group_indexes = []
        for node_name in current_nodes:
            match = re.search(rf"^{re.escape(instance_name)}-dn-(\d+)-", node_name)
            if match:
                group_indexes.append(int(match.group(1)))
        next_group_index = max(group_indexes, default=-1) + 1
        new_node_names = [
            f"{instance_name}-dn-{next_group_index}-cand-0",
            f"{instance_name}-dn-{next_group_index}-cand-1",
            f"{instance_name}-dn-{next_group_index}-log-0",
        ]

        self.get_by_text("存储节点扩容", exact=True).click()
        dialog = self._get_dialog("新增节点")
        selected_disk_type = disk_type if disk_type else self.stor
        self._select_dropdown_option(dialog.locator(".el-select").first.locator("input"), selected_disk_type)
        dialog.get_by_role("spinbutton").fill(str(disk_size))
        dialog.get_by_text("确定", exact=True).click()
        return new_node_names

    @submenu("实例管理")
    def scale_in_storage_node(self, instance_name: str) -> None:
        """
        通过详情页按钮为 XScale 实例缩容一个存储节点组
        :param instance_name: 实例名称
        """
        self.goto_detail_page(instance_name)
        self.get_by_text("存储节点缩容", exact=True).click()

    @submenu("实例管理")
    def restart_storage_nodes(self, instance_name: str) -> list[str]:
        """
        通过详情页按钮重启全部存储节点，并返回重启前的存储节点名称列表
        :param instance_name: 实例名称
        :return: 存储节点名称列表
        """
        self.goto_detail_page(instance_name)
        node_names = self.get_node_names_by_type(instance_name, "存储节点")
        self.get_by_text("重启存储节点", exact=True).click()
        self._get_dialog("重启存储节点").get_by_text("确定", exact=True).click()
        return node_names

    @submenu("实例管理")
    def change_node_disk_size(self, instance_name: str, new_size: int, node_type: str) -> str:
        """
        修改节点云硬盘大小并返回节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :param new_size: 新磁盘大小
        :return: 节点名称
        """
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)
        self.click_action(node_name, "修改云硬盘大小")
        dialog = self._get_dialog("修改云硬盘大小")
        dialog.get_by_role("spinbutton").fill(str(new_size))
        dialog.get_by_text("确定", exact=True).click()
        return node_name

    @submenu("实例管理")
    def node_ip_binding(self, instance_name: str, node_type: str) -> tuple[str, str]:
        """
        为节点绑定公网IP并返回节点名称与公网IP
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :return: (节点名称, 绑定的公网IP)
        """
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)

        # 使用更精确的dialog定位
        self.click_action(node_name, "绑定公网IP")
        dialog = self.get_by_label("绑定公网IP", exact=True)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(Config.get("network")).click()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        # 使用dialog内的确定按钮，避免多个匹配
        self.dialog_confirm.click()
        return node_name, ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, instance_name: str, node_type: str) -> str:
        """
        为节点解绑公网IP并返回节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :return: 节点名称
        """
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)
        self.click_action(node_name, "解绑公网IP")
        dialog = self._get_dialog("解除绑定公网IP")
        dialog.get_by_text("确定", exact=True).click()
        return node_name

    @submenu("实例管理")
    def restart_node(self, instance_name: str, node_type: str) -> str:
        """
        重启节点并返回节点名称
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :return: 节点名称
        """
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)
        self.click_action(node_name, "重启节点")
        self._get_dialog("重启").get_by_text("确定", exact=True).click()
        return node_name

    @submenu("实例管理")
    def hot_migration_node(
        self,
        instance_name: str,
        node_type: str,
        bandwidth: str = "50%",
        cpu_auto: bool = True,
    ) -> tuple[str, str, str]:
        """
        节点热迁移并返回节点名称、原物理机与目标物理机
        :param instance_name: 实例名称
        :param node_type: 节点类型
        :param bandwidth: 迁移速率
        :param cpu_auto: 是否开启CPU自动收敛
        :return: (节点名称, 原物理机, 选择的目标物理机)
        """
        self.goto_detail_page(instance_name)
        node_name = self.get_first_node_name_by_type(instance_name, node_type)
        self.click_action(node_name, "热迁移")
        dialog = self._get_dialog("热迁移")
        old_host = dialog.locator("input").nth(2).input_value().strip()

        # 选择目标物理机
        dialog.locator("form div").filter(has_text="目标物理机").get_by_placeholder("请选择").click()

        # 获取下拉列表中的所有选项
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        options = dropdown.locator("li.el-select-dropdown__item")
        options.first.wait_for(state="visible", timeout=5000)

        checked_host = None
        count = options.count()
        for i in range(count):
            opt = options.nth(i)
            class_name = opt.get_attribute("class") or ""
            option_text = opt.inner_text().strip()
            host_name = option_text.split()[0] if option_text else ""
            if "is-disabled" in class_name or not host_name:
                continue
            if host_name == old_host or "当前节点" in option_text:
                continue
            checked_host = host_name
            opt.click()
            break

        if not checked_host:
            dialog.get_by_text("取消").click()
            pytest.skip("没有可用的物理机可供迁移")

        # 选择迁移速率
        if bandwidth:
            dialog.locator("div").filter(has_text=re.compile(r"^迁移速率")).get_by_placeholder("请选择").click()
            sleep(1)
            self.locator("li").filter(has_text=bandwidth).click()

        # 设置CPU自动收敛
        if cpu_auto:
            switch_locator = dialog.get_by_role("switch").locator("span")
            if switch_locator.is_visible():
                switch_locator.click()

        # 确认热迁移
        dialog.get_by_text("确定").click()

        return node_name, old_host, checked_host
