import re

from sugon_web.common.base import BasePage, submenu


class MySQLPage(BasePage):
    """MySQL实例管理页面对象"""

    @submenu("实例管理")
    def create_instance(self, name: str, instance_type: str = "单机", version: str = "8.0",
                        password: str = "admin1234@sugon", port: int = 3306, case_sensitivity: str = "区分大小写",
                        network: str = "Autotest", subnet: str = "Autotest:10.25.248.0/24",
                        disk_type: str = "xstor-type", disk_size: int = 20):
        """
        创建MySQL实例（支持多种参数）
        :param name: 实例名称
        :param instance_type：实例类型
        :param version: 版本
        :param password: 密码
        :param port: 端口
        :param case_sensitivity: 大小写策略
        :param network: 网络
        :param subnet: 子网
        :param disk_type: 磁盘类型
        :param disk_size: 磁盘大小
        """
        self.btn_create.click()

        # --- 类型设置 ---
        self.get_by_role("radio", name=instance_type).click()
        self.input_name.fill(name)

        # 版本选择
        self.locator("div").filter(has_text=re.compile(r"^版本8\.05\.75\.6$")).get_by_placeholder("请选择").click()
        self.locator(".el-select-dropdown__item").filter(has_text=version).click()

        # --- 基本设置 ---
        self.project_dropdown.click()
        self.project_autotest.click()

        # 密码
        self.input_password.fill(password)
        self.input_confirm_password.fill(password)

        # 端口
        self.locator("input[type=\"number\"]").click()
        self.locator("input[type=\"number\"]").fill(str(port))

        # 大小写策略
        self.locator(f':text-is("{case_sensitivity}")').click()

        # --- 网络设置 ---
        self._select_network(network, subnet)

        # --- 存储设置 ---
        self.disk_type_dropdown.click()
        self.page.locator("li").filter(has_text=disk_type).click()

        # 数据盘大小
        self.locator("form").filter(has_text="数据盘大小").get_by_role("spinbutton").fill(str(disk_size))
        # --- 确认创建 ---
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """
        删除MySQL实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name, new_name):
        """
        修改MySQL实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_dropdown_option(old_name, "修改实例名称")
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
        self.click_dropdown_option(name, "重启实例")
        self.get_by_label("重启实例").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_root_password(self, name, new_password):
        """
        修改MySQL实例的管理员密码
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
        修改MySQL节点磁盘大小
        :param name: 实例名称
        :param new_size: 新磁盘大小
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.click_dropdown_option(name + "-0", "修改云硬盘大小")

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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.click_dropdown_option(name + "-0", "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为MySQL实例绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_text("绑定公网IP").first.click()
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()
        self.page.locator("tr.el-table__row:first-child td label[role='radio']").click()
        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """
        为MySQL实例解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_label("详情").get_by_text("解绑公网IP").click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str = None):
        """
        为MySQL节点绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.click_dropdown_option(name + "-0", "绑定公网IP")
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()
        self.page.locator("tr.el-table__row:first-child td label[role='radio']").click()
        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        """
        为MySQL节点解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.click_dropdown_option(name + "-0", "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def create_database(self, name: str, db_name: str):
        """
        在指定实例下创建数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="数据库", exact=True).click()
        self.wait_for_page_ready()
        self.btn_create.click()
        dialog = self.get_by_label("新建数据库")
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(db_name)
        dialog.get_by_text("确定").click()

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
        self.get_by_role("tab", name="用户").click()
        self.click_dropdown_option(user_name, "授权")
        dialog = self.get_by_label("授权", exact=True)
        dialog.get_by_role("row", name=re.compile(db_name)).locator("span").nth(1).click()
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=privileges).click()
        dialog.get_by_text("确定").click()

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
        self.click_dropdown_option(user_name, "解除授权")
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
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="读写分离").click()
        self.get_by_text("开通读写分离", exact=True).click()

    @submenu("实例管理")
    def disable_splitting(self, name: str):
        """
        为MySQL实例关闭读写分离
        :param name: 实例名称
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
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
        self.click_dropdown_option(name, "备份")
        dialog = self.get_by_label("备份")
        dialog.get_by_role("textbox").fill(backup_name)
        dialog.get_by_role("button", name="确定").click()

    @submenu("实例管理")
    def enable_slow_log(self, name: str):
        """
        为MySQL实例开启慢日志
        :param name: 实例名称
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="慢日志").click()
        self.get_by_text("立即开启").click()
        self.get_by_label("开启慢日志").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def disable_slow_log(self, name: str):
        """
        为MySQL实例关闭慢日志
        :param name: 实例名称
        """
        self.locator(f"#cloud-container-content").get_by_text(name).click()
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
        self.locator(f"#cloud-container-content").get_by_text(name).click()
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
        self.locator(f"#cloud-container-content").get_by_text(name).click()
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
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        self.wait_for_page_ready()
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
        self.locator(f"#cloud-container-content").get_by_text(name).click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    # --- 定位器属性 ---
    @property
    def input_name(self):
        return self.locator("form").filter(has_text="基本设置").get_by_role("textbox").first

    @property
    def input_password(self):
        return self.get_by_placeholder("请输入管理员用户密码")

    @property
    def input_confirm_password(self):
        return self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")

    @property
    def project_dropdown(self):
        return self.locator("form").filter(has_text="基本设置").get_by_placeholder("请选择").nth(1)

    @property
    def project_autotest(self):
        return self.locator("li").filter(has_text="Autotest").nth(2)

    def _select_network(self, network, subnet):
        """选择网络和子网（使用可靠的等待机制）"""
        # --- 选择网络 ---
        self.get_by_role("textbox", name="请选择网络").click()
        # 等待下拉列表出现
        network_list_locator = self.page.locator("body > div.el-select-dropdown:visible").last
        network_list_locator.wait_for(state="visible", timeout=5000)
        # 点击选项
        network_list_locator.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network)}$")).click()

        # --- 选择子网 ---
        self.get_by_role("textbox", name="请选择子网").click()
        # 等待下拉列表出现
        subnet_list_locator = self.page.locator("body > div.el-select-dropdown:visible").last
        subnet_list_locator.wait_for(state="visible", timeout=5000)
        # 点击选项
        subnet_list_locator.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(subnet)}$")).locator(
            "span").click()

    @property
    def disk_type_dropdown(self):
        return self.locator("div").filter(has_text=re.compile(r"^数据盘类型")).get_by_placeholder("请选择")
