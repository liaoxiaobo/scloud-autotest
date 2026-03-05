import re
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util


class PgSQLPage(BasePage):
    """PostgreSQL实例管理页面对象"""

    @submenu("实例管理")
    def create_instance(self, name: str, instance_type: str = "单机", version: str = "14",
                        password: str = "admin1234@sugon", network: str = "Autotest",
                        subnet: str = "Autotest:10.", disk_type: str = None, disk_size: int = 20):
        """
        创建PostgreSQL实例（支持多种参数）
        :param name: 实例名称
        :param instance_type: 实例类型（单机/高可用/集群）
        :param version: 版本
        :param password: postgres管理员密码
        :param network: 网络
        :param subnet: 子网（支持模糊匹配，如"Autotest:"）
        :param disk_type: 磁盘类型
        :param disk_size: 磁盘大小
        """
        self.btn_create.click()

        # --- 基本设置 ---
        # 类型设置
        self.get_by_role("radio", name=instance_type).click()

        # 名称
        self.locator("form").filter(has_text="基本设置").get_by_role("textbox").first.fill(name)

        # 版本选择（如果有需要切换版本）
        # version_dropdown = self.locator("div").filter(has_text=re.compile(r"^版本")).get_by_placeholder("请选择")
        # if version_dropdown.is_visible():
        #     version_dropdown.click()
        #     self.locator("li").filter(has_text=re.compile(rf"^{re.escape(version)}$")).click()

        # 项目选择
        db_util.project_dropdown(self).click()
        db_util.project_autotest(self).click()

        # 密码
        self.get_by_placeholder("请输入postgres管理员用户密码").fill(password)
        db_util.input_confirm_password(self).fill(password)

        # --- 网络设置 ---
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # --- 存储设置 ---
        db_util.disk_type_dropdown(self).click()
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_disk_type = disk_type if disk_type else self.volume_type
        self.page.locator("li").filter(has_text=selected_disk_type).click()

        # 数据盘大小
        self.locator("form").filter(has_text="数据盘大小").get_by_role("spinbutton").fill(str(disk_size))

        # --- 确认创建 ---
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """
        删除PostgreSQL实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """
        批量删除PostgreSQL实例
        :param names: 实例名称列表
        """
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """
        修改PostgreSQL实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_dropdown_option(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称").get_by_role("textbox")
        dialog.click()
        dialog.fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_instance(self, name: str):
        """
        重启PostgreSQL实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "重启实例")
        self.get_by_label("重启实例").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_root_password(self, name: str, new_password: str):
        """
        修改PostgreSQL实例的管理员密码
        :param name: 实例名称
        :param new_password: 新密码
        """
        self.click_dropdown_option(name, "修改管理员密码")
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
        修改PostgreSQL节点磁盘大小
        :param name: 实例名称
        :param new_size: 新磁盘大小
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.click_dropdown_option(f"{name}-0", "修改云硬盘大小")

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
        修改PostgreSQL实例规格
        :param name: 实例名称
        :param specification_name: 新规格名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.click_dropdown_option(f"{name}-0", "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为PostgreSQL实例绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        :return: 绑定的IP地址
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.get_by_text("绑定公网IP").first.click()
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()
        self.wait_for_page_ready()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """
        为PostgreSQL实例解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.get_by_label("详情").get_by_text("解绑公网IP").click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str = None):
        """
        为PostgreSQL节点绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        :return: 绑定的IP地址
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.click_dropdown_option(f"{name}-0", "绑定公网IP")
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()
        self.wait_for_page_ready()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        """
        为PostgreSQL节点解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.click_dropdown_option(f"{name}-0", "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_node(self, name: str):
        """
        为PostgreSQL实例添加只读节点
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.get_by_label("详情").get_by_text("新建只读节点").click()
        self.get_by_label("新建只读节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_node(self, name: str, node_name: str):
        """
        删除PostgreSQL实例的节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        sleep(30)
        self.wait_for_page_ready()
        self.locator(".el-icon-refresh").click()
        self.click_dropdown_option(node_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_database(self, name: str, db_name: str):
        """
        在指定实例下创建数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        sleep(3)
        self.get_by_role("tab", name="数据库", exact=True).click()
        sleep(3)
        self.wait_for_page_ready()
        self.btn_create.click()
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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        sleep(3)
        self.get_by_role("tab", name="数据库", exact=True).click()
        sleep(5)
        self.wait_for_page_ready()
        self.get_by_role("row", name=f"{db_name}").locator("i").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_databases(self, name: str, db_names: list):
        """
        在指定实例下批量删除数据库
        :param name: 实例名称
        :param db_names: 数据库名称列表
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        sleep(3)
        self.get_by_role("tab", name="数据库", exact=True).click()
        sleep(5)
        self.wait_for_page_ready()

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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "修改用户")
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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        sleep(2)
        self.get_by_role("tab", name="用户").click()
        sleep(2)
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "授权")
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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_users(self, name: str, user_names: list):
        """
        在指定实例下批量删除用户
        :param name: 实例名称
        :param user_names: 用户名列表
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()

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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "解除授权")
        dialog = self.get_by_label("解除授权")
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=db_name).click()
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """
        为PostgreSQL实例添加白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定").click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """
        为PostgreSQL实例删除单个白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        # 精准定位到要删除的IP地址对应的删除按钮
        self.locator("span").filter(has_text=ip_address).locator("i").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list):
        """
        为PostgreSQL实例批量删除白名单
        :param name: 实例名称
        :param ip_addresses: IP地址或CIDR的列表
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        self.wait_for_page_ready()
        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.get_by_placeholder("请选择要删除的白名单").click()
        for ip in ip_addresses:
            self.page.locator("li", has_text=ip).click()
        self.get_by_label("删除白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """
        为PostgreSQL实例重置白名单
        :param name: 实例名称
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def edit_instance_parameter(self, name: str, param_name: str, param_value: str):
        """
        编辑实例的参数值并应用
        :param name: 实例名称
        :param param_name: 参数名称
        :param param_value: 参数新值
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        sleep(3)
        self.get_by_role("tab", name="参数设置").click()
        # 定位到参数行并点击编辑图标
        sleep(3)
        self.wait_for_page_ready()
        row = self.page.locator("tr", has_text=param_name).first
        row.locator("i").first.click()
        # 在弹窗中修改值
        dialog = self.get_by_label("编辑参数")
        spinbutton = dialog.get_by_role("spinbutton")
        spinbutton.click()
        spinbutton.fill(param_value)
        dialog.get_by_text("确定").click()
        # 应用更改
        self.get_by_text("应用", exact=True).click()
