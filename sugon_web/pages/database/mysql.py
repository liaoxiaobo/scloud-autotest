import re
import pytest
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger


class MySQLPage(BasePage):
    """MySQL实例管理页面对象"""

    @submenu("实例管理")
    def create_instance(self, name: str, instance_type: str = "单机", version: str = "8.0",
                        password: str = "admin1234@sugon", port: int = 3306, case_sensitivity: str = "区分大小写",
                        network: str = "Autotest", subnet: str = "Autotest:10.",
                        disk_type: str = None, disk_size: int = 20):
        """
        创建MySQL实例（支持多种参数）
        :param name: 实例名称
        :param instance_type：实例类型
        :param version: 版本
        :param password: 密码
        :param port: 端口
        :param case_sensitivity: 大小写策略
        :param network: 网络
        :param subnet: 子网（支持模糊匹配，如"Autotest:"）
        :param disk_type: 磁盘类型
        :param disk_size: 磁盘大小
        """
        self.btn_create.click()

        # --- 类型设置 ---
        self.get_by_role("radio", name=instance_type).click()
        db_util.input_name(self).fill(name)

        # 版本选择
        self.locator("div").filter(has_text=re.compile(r"^版本8\.05\.75\.6$")).get_by_placeholder("请选择").click()
        self.locator(".el-select-dropdown__item").filter(has_text=version).click()

        # --- 基本设置 ---
        db_util.project_dropdown(self).click()
        db_util.project_autotest(self).click()

        # 密码
        db_util.input_password(self).fill(password)
        db_util.input_confirm_password(self).fill(password)

        # 端口
        self.locator("input[type=\"number\"]").click()
        self.locator("input[type=\"number\"]").fill(str(port))

        # 大小写策略
        self.locator(f':text-is("{case_sensitivity}")').click()

        # --- 网络设置 ---
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # --- 存储设置 ---
        selected_disk_type = disk_type if disk_type else self.volume_type
        db_util.select_disk_type_like_doris(self, selected_disk_type)

        # 数据盘大小
        self.locator("form").filter(has_text="数据盘大小").get_by_role("spinbutton").fill(str(disk_size))

        # 规格选择（默认选择列表中的第一个规格）
        self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()
        # --- 确认创建 ---
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """
        删除MySQL实例
        :param name: 实例名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """
        批量删除MySQL实例
        :param names: 实例名称列表
        """
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name, new_name):
        """
        修改MySQL实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称").get_by_role("textbox")
        dialog.click()
        dialog.fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_instance(self, name):
        """
        重启MySQL实例
        :param name: 实例名称
        """
        self.click_action(name, "重启实例")
        self.get_by_label("重启实例").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_root_password(self, name, new_password):
        """
        修改MySQL实例的管理员密码
        :param name: 实例名称
        :param new_password: 新密码
        """
        self.click_action(name, "修改管理员密码")
        dialog = self.get_by_role("dialog")
        pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox")
        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(new_password)
        confirm_pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")
        confirm_pwd_input.wait_for(state="visible", timeout=5000)
        confirm_pwd_input.fill(new_password)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_disk_size(self, name: str, new_size: int):
        """
        修改MySQL节点磁盘大小
        :param name: 实例名称
        :param new_size: 新磁盘大小
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "修改云硬盘大小")

        dialog = self.get_by_role("dialog")
        # 定位到步进器输入框并填充新大小
        spin_button = dialog.get_by_role("spinbutton")
        spin_button.wait_for(state="visible", timeout=5000)
        spin_button.fill(str(new_size))
        # 确认修改
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_specification(self, name: str, specification_name: str):
        """
        修改MySQL实例规格
        :param name: 实例名称
        :param specification_name: 新规格名称
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为MySQL实例绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("绑定公网IP").first.click()
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为“关闭”的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """
        为MySQL实例解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_label("详情").get_by_text("解绑公网IP").click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str = None):
        """
        为MySQL节点绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "绑定公网IP")
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为“关闭”的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        """
        为MySQL节点解绑弹性IP
        :param name: 实例名称
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_node(self, name: str):
        """
        为MySQL实例添加只读节点
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_label("详情").get_by_text("新建只读节点").click()
        self.get_by_label("新建只读节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_node(self, name: str, node_name: str):
        """
        删除MySQL实例的节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(30)
        self.locator(".el-icon-refresh").click()
        self.click_action(node_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_database(self, name: str, db_name: str):
        """
        在指定实例下创建数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(5)
        self.get_by_role("tab", name=re.compile(r"^数据库$")).click()
        sleep(3)
        self.btn_create.click()
        sleep(3)
        dialog = self.get_by_label("新建数据库")
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(db_name)
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_database(self, name: str, db_name: str):
        """
        在指定实例下删除数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(5)
        self.get_by_role("tab", name=re.compile(r"^数据库$")).click()
        sleep(5)
        self.locator("tr").filter(has_text=db_name).get_by_text("删除").last.click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_databases(self, name: str, db_names: list):
        """
        在指定实例下批量删除数据库
        :param name: 实例名称
        :param db_names: 数据库名称列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(5)
        self.get_by_role("tab", name=re.compile(r"^数据库$")).click()
        sleep(5)

        for db_name in db_names:
            self.get_by_role("row", name=re.compile(db_name)).locator("span").nth(1).click()

        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_user(self, name: str, user_name: str, password: str, db_name: str, privileges: str):
        """
        在指定实例下创建用户并授权
        :param name: 实例名称
        :param user_name: 用户名
        :param password: 密码
        :param db_name: 授权的数据库
        :param privileges: 权限 (e.g., "只读")
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
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
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
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
        :param privileges: 权限 (e.g., "读写")
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(2)
        self.get_by_role("tab", name="用户").click()
        sleep(2)
        self.click_action(user_name, "授权")
        dialog = self.get_by_label("授权", exact=True)
        sleep(2)
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
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        self.click_action(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_users(self, name: str, user_names: list):
        """
        在指定实例下批量删除用户
        :param name: 实例名称
        :param user_names: 用户名列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()

        for user_name in user_names:
            self.get_by_role("row", name=re.compile(user_name)).locator("span").nth(1).click()

        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def deauthorize_user(self, name: str, user_name: str, db_name: str):
        """
        解除用户数据库授权
        :param name: 实例名称
        :param user_name: 用户名
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        self.click_action(user_name, "解除授权")
        dialog = self.get_by_label("解除授权")
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=db_name).click()
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def enable_splitting(self, name: str):
        """
        为MySQL实例开通读写分离
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="读写分离").click()
        self.get_by_text("开通读写分离", exact=True).click()

    @submenu("实例管理")
    def disable_splitting(self, name: str):
        """
        为MySQL实例关闭读写分离
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="读写分离").click()
        self.locator("div.cloud-button-btn").filter(has_text="关闭读写分离").click()
        self.get_by_label("关闭读写分离").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def create_backup(self, name: str, backup_name: str):
        """
        为MySQL实例创建备份
        :param name: 实例名称
        :param backup_name: 备份名称
        """
        self.click_action(name, "备份")
        dialog = self.get_by_label("备份")
        dialog.get_by_role("textbox").fill(backup_name)
        dialog.get_by_role("button", name="确定").click()

    @submenu("实例管理")
    def enable_slow_log(self, name: str):
        """
        为MySQL实例开启慢日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="慢日志").click()
        self.get_by_text("立即开启").click()
        self.get_by_label("开启慢日志").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def disable_slow_log(self, name: str):
        """
        为MySQL实例关闭慢日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="慢日志").click()
        self.get_by_text("服务设置").first.click()
        self.get_by_role("switch").locator("span").click()
        self.get_by_label("服务设置").get_by_text("确定").click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """
        为MySQL实例添加白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定").click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """
        为MySQL实例删除单个白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        # 精准定位到要删除的IP地址对应的删除按钮
        self.locator("span").filter(has_text=ip_address).locator("i").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list):
        """
        为MySQL实例批量删除白名单
        :param name: 实例名称
        :param ip_addresses: IP地址或CIDR的列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.get_by_placeholder("请选择要删除的白名单").click()
        for ip in ip_addresses:
            self.page.locator("li", has_text=ip).click()
        self.get_by_label("删除白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """
        为MySQL实例重置白名单
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("参数管理")
    def create_parameter_model(self, model_name: str, version: str = "8.0"):
        """
        创建参数模板
        :param model_name: 模板名称
        :param version: 数据库版本
        """
        self.get_by_text("新建", exact=True).click()
        dialog = self.get_by_label("新建模板")
        dialog.locator("div").filter(has_text=re.compile(r"^模板名称$")).get_by_role("textbox").fill(model_name)
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=version).click()
        self.get_by_text("下一步").click()
        # 添加一个默认参数以完成创建
        self.get_by_text("添加参数").click()
        self.get_by_role("row", name="参数名称 运行值", exact=True).locator("span").first.click()
        self.get_by_label("选择参数").get_by_text("确定").click()
        self.get_by_text("立即创建").click()

    @submenu("参数管理")
    def delete_parameter_model(self, model_name: str):
        """
        删除参数模板
        :param model_name: 模板名称
        """
        self.click_action(model_name, "删除")
        self.dialog_confirm.click()


    @submenu("参数管理")
    def edit_parameter_model(self, model_name: str, param_name: str):
        """
        编辑参数模板，为其添加新参数
        :param model_name: 模板名称
        :param param_name: 要添加的参数名称
        """
        self.get_by_text(model_name).first.click()
        sleep(3)
        self.locator(".table-tool-bar-left > div:nth-child(2) > .cloud-button-btn").click()
        sleep(3)
        self.get_by_role("row", name=f"{param_name}").get_by_role("checkbox").check()
        self.get_by_label("选择参数").get_by_text("确定").click()

    @submenu("参数管理")
    def apply_parameter_model(self, model_name: str, name: str):
        """
        将参数模板应用到实例
        :param model_name: 模板名称
        :param instance_name: 实例名称
        """
        self.get_by_text(model_name).first.click()
        self.locator("div.cloud-button-btn").filter(has_text="应用").click()
        # 选择实例
        # self.locator("input[type=\"text\"]").filter(has_text="请选择").click()
        # self.locator("input[type=\"text\"]").filter(has_text="请选择").fill(name)
        # self.locator("div.cloud-button-btn").filter(has_text="前选择").click()
        # self.filter(has_text=instance_name+"0").click()
        self.locator("td").filter(has_text=name).get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=name).click()
        self.locator("td").filter(has_text=f"{name}-0").get_by_placeholder("请选择").click()
        # self.locator("li").filter(has_text=name+"-0").click()
        items = self.locator("li").filter(has_text=name + "-").all()
        for item in items:
            item.click()

        # 确认应用
        self.dialog_confirm.click()

    @submenu("实例管理")
    def edit_instance_parameter(self, name: str, param_name: str, param_value: str):
        """
        编辑实例的参数值并应用
        :param name: 实例名称
        :param param_name: 参数名称
        :param param_value: 参数新值
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(3)
        self.get_by_role("tab", name="参数设置").click()
        # 定位到参数行并点击编辑图标
        sleep(3)
        self.page.locator("tr").filter(has_text=param_name).get_by_text("编辑").last.click()
        # 在弹窗中修改值
        dialog = self.get_by_label("编辑参数")
        spinbutton = dialog.get_by_role("spinbutton")
        spinbutton.click()
        spinbutton.fill(param_value)
        dialog.get_by_text("确定").click()
        # 应用更改
        self.get_by_text("应用", exact=True).click()

    @submenu("实例管理")
    def export_instance_parameters(self, name: str):
        """
        导出实例的参数
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(3)
        self.get_by_role("tab", name="参数设置").click()
        sleep(3)
        self.get_by_text("导出", exact=True).click()

    @submenu("实例管理")
    def mysql_hot_migration(self, name, node_name, bandwidth="50%", cpu_auto=True):
        """
        MySQL节点热迁移
        :param name: 实例名称
        :param node_name: 节点名称 (如 f"{name}-0")
        :param bandwidth: 迁移速率 (25%, 50%, 75%, 全速)
        :param cpu_auto: 是否开启CPU自动收敛
        """
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "热迁移")
        sleep(2)

        # 选择目标物理机
        # 定位目标物理机选择框并点击
        self.locator("form div").filter(has_text="目标物理机").get_by_placeholder("请选择").click()
        sleep(1)
        
        # 获取下拉列表中的所有选项
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        options = dropdown.locator("li.el-select-dropdown__item")
        
        checked_host = None
        # 尝试选择第一个可用的
        count = options.count()
        for i in range(count):
            opt = options.nth(i)
            if "is-disabled" not in opt.get_attribute("class"):
                checked_host = opt.inner_text().strip().split()[0]
                opt.click()
                logger.info(f"自动选择并点击可用的物理机: {checked_host}")
                break
        
        if not checked_host:
            self.get_by_role("dialog").get_by_text("取消").click()
            pytest.skip("没有可用的物理机可供迁移")

        # 选择迁移速率
        if bandwidth:
            self.locator("div").filter(has_text=re.compile(r"^迁移速率")).get_by_placeholder("请选择").click()
            sleep(1)
            self.locator("li").filter(has_text=bandwidth).click()
            logger.info(f"已选择迁移速率: {bandwidth}")

        # 设置CPU自动收敛
        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if switch_locator.is_visible():
                switch_locator.click()
                logger.info("已点击CPU自动收敛开关")

        # 确认热迁移
        self.get_by_role("dialog").get_by_text("确定").click()
        logger.info(f"已点击确定按钮，开始热迁移 {node_name}")
        
        return checked_host
    @submenu("实例管理")
    def switch_network(self, name: str, network: str = "Autotest", subnet: str = "subnet:10.", selection_type: str = "快速选择"):
        """
        切换MySQL实例网络
        :param name: 实例名称
        :param network: 网络名称
        :param subnet: 子网名称
        :param selection_type: 选择类型 ("快速选择" 或 "手动输入")
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_label("详情").get_by_text("切换网络").click()

        dialog = self.get_by_label("切换网络")

        # 选择网络 (nth(2) based on user script)
        dialog.get_by_placeholder("请选择").nth(2).click()
        self.page.locator("li").filter(has_text=re.compile(rf"^{network}$")).nth(1).click()

        # 选择子网 (nth(3) based on user script)
        dialog.get_by_placeholder("请选择").nth(3).click()
        self.page.get_by_text(subnet).nth(1).click()

        # 获取当前可用的IP列表
        dialog.get_by_placeholder("请选择IP地址").click()
        sleep(2)
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        ip_options = dropdown.locator("li.el-select-dropdown__item").all_inner_texts()
        ip_list = [ip.strip() for ip in ip_options if ip.strip()]
        logger.info(f"获取到可用IP列表: {ip_list}")

        if selection_type == "快速选择":
            dialog.locator("label").filter(has_text="快速选择").click()
            # 重新点击下拉框以重新获得焦点或显示列表
            dialog.get_by_placeholder("请选择IP地址").click()
            self.page.locator("li.el-select-dropdown__item").filter(has_text=ip_list[0]).first.click()
        else:
            # 手动输入
            # 隐藏下拉框
            self.page.keyboard.press("Escape")
            dialog.locator("label").filter(has_text="手动输入").click()
            dialog.get_by_placeholder("请输入IP地址").fill(ip_list[0])

        # 节点IP选择 (展开节点列表)
        arrow_up = self.page.locator(".el-form-item__content > .el-icon-arrow-up")
        if arrow_up.is_visible():
            arrow_up.click()

        # 为每个节点输入IP，必须是IP列表中的
        # 实例使用 ip_list[0]，三个节点依次使用 ip_list[1], ip_list[2], ip_list[3]
        rows = dialog.locator("tr.el-table__row").all()
        for i, row in enumerate(rows):
            if i + 1 < len(ip_list):
                target_ip = ip_list[i + 1]
                row.get_by_role("textbox").click()
                row.get_by_role("textbox").fill(target_ip)
                logger.info(f"为节点 {i} 分配第 {i+2} 个可用IP: {target_ip}")
            else:
                logger.error(f"可用IP不足，无法为节点 {i} 分配IP")

        # 确定
        dialog.get_by_text("确定").click()
