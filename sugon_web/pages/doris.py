import re
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util


class DorisPage(BasePage):
    """Doris实例管理页面对象"""

    @submenu("实例管理")
    def create_instance(self, name: str, version: str = "2.1.9", ha_type: str = "读高可用",
                        password: str = "admin1234@sugon", network: str = "Autotest",
                        subnet: str = "Autotest:10.", os_type: str = "AnolisOS 7.9",
                        case_sensitivity: str = "不区分大小写（将所有表名转换为小写存储）",
                        fe_disk_type: str = None, fe_disk_size: int = 50,
                        be_disk_type: str = None, be_disk_size: int = 100):
        """
        创建Doris实例（支持多种参数）
        :param name: 实例名称
        :param version: 版本
        :param ha_type: 高可用类型（非高可用/读高可用/读写高可用）
        :param password: 管理员密码
        :param network: 网络
        :param subnet: 子网（支持模糊匹配，如"Autotest:"）
        :param os_type: 操作系统
        :param case_sensitivity: 大小写策略
        :param fe_disk_type: FE节点磁盘类型
        :param fe_disk_size: FE节点磁盘大小
        :param be_disk_type: BE节点磁盘类型
        :param be_disk_size: BE节点磁盘大小
        """
        self.btn_create.click()

        # --- 基本设置 ---
        # 名称
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        # 版本选择
        self.locator("div").filter(has_text=re.compile(r"^版本2\.1\.9$")).get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=re.compile(rf"^{re.escape(version)}$")).click()

        # 项目选择
        db_util.project_dropdown(self).click()
        db_util.project_autotest(self).click()

        # --- 网络设置 ---
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # --- 配置设置 ---
        # 大小写策略 - 在配置区域的第一个"请选择"下拉框
        # 使用包含"大小写策略"关键字的表单区域定位
        self.locator("form").filter(has_text="配置 专有网络 大小写策略").get_by_placeholder("请选择", exact=True).first.click()
        # 点击选项
        re.compile(rf"^{re.escape(case_sensitivity)}$")
        self.locator("span").filter(has_text=re.compile(rf"^{re.escape(case_sensitivity)}$")).click()

        # 密码
        self.get_by_placeholder("请输入admin管理员用户密码").fill(password)
        self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)

        # FE节点配置 - 高可用类型
        self.get_by_role("radio", name=ha_type).click()

        # FE节点数据盘类型 - 在配置区域的第3个"请选择"（索引为2）
        fe_disk_dropdown = self.locator("form").filter(
            has_text="配置 专有网络 大小写策略 用户名 密码 确认密码 FE"
        ).get_by_placeholder("请选择", exact=True).nth(2)
        fe_disk_dropdown.click()
        # 等待下拉列表出现
        self.page.wait_for_timeout(1000)
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_fe_disk_type = fe_disk_type if fe_disk_type else self.volume_type
        # 点击 FE 的磁盘类型选项（第2个，索引为1）
        self.locator("li").filter(has_text=selected_fe_disk_type).nth(1).click()

        # FE节点数据盘大小
        self.get_by_role("spinbutton").first.click()
        self.get_by_role("spinbutton").first.fill(str(fe_disk_size))
        
        # 点击 BE 区域关闭 FE 下拉框
        self.locator("form").filter(has_text="BE节点配置").click()
        self.page.wait_for_timeout(1000)
        
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_be_disk_type = be_disk_type if be_disk_type else self.volume_type
        # BE 数据盘类型 - 在配置区域的第4个"请选择"（索引为3）
        be_disk_dropdown = self.locator("form").filter(
            has_text="配置 专有网络 大小写策略 用户名 密码 确认密码 FE"
        ).get_by_placeholder("请选择", exact=True).nth(3)
        be_disk_dropdown.click()
        self.page.wait_for_timeout(1000)
        # 点击 BE 的磁盘类型选项（第3个，索引为2）
        self.locator("li").filter(has_text=selected_be_disk_type).nth(2).click()

        # BE节点数据盘大小
        self.get_by_role("spinbutton").nth(2).click()
        self.get_by_role("spinbutton").nth(2).fill(str(be_disk_size))

        # --- 确认创建 ---
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """
        删除Doris实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """
        批量删除Doris实例
        :param names: 实例名称列表
        """
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """
        修改Doris实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_dropdown_option(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称").get_by_role("textbox")
        dialog.click()
        dialog.fill(new_name)
        self.get_by_label("修改实例名称").get_by_text("确定").click()

    @submenu("实例管理")
    def reset_admin_password(self, name: str, new_password: str):
        """
        重置Doris实例的管理员密码
        :param name: 实例名称
        :param new_password: 新密码
        """
        self.click_dropdown_option(name, "重置密码")
        dialog = self.get_by_label("重置密码")
        # 新密码
        pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox")
        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(new_password)
        # 确认密码
        confirm_pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")
        confirm_pwd_input.wait_for(state="visible", timeout=5000)
        confirm_pwd_input.fill(new_password)
        # 确认
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def stop_instance(self, name: str):
        """
        停止Doris实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "停止实例")
        self.get_by_label("停止").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def start_instance(self, name: str):
        """
        启动Doris实例
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "重启实例")
        self.get_by_label("重启").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_instance(self, name: str):
        """
        重置Doris实例状态
        :param name: 实例名称
        """
        self.click_dropdown_option(name, "状态重置")

    @submenu("实例管理")
    def change_disk_size(self, name: str, node_type: str = "fe", new_size: int = 60):
        """
        修改Doris节点磁盘大小
        :param name: 实例名称
        :param node_type: 节点类型，"fe"或"be"
        :param new_size: 新磁盘大小
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()

        # 根据节点类型确定节点名称
        if node_type.lower() == "fe":
            node_name = f"{name}_fe_node01"
        else:
            node_name = f"{name}_be_node01"
        self.click_dropdown_option(node_name, "修改云硬盘大小")

        dialog = self.get_by_role("dialog")
        # 定位到步进器输入框并填充新大小
        spin_button = dialog.get_by_role("spinbutton")
        spin_button.wait_for(state="visible", timeout=5000)
        spin_button.fill(str(new_size))
        # 确认修改
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_specification(self, name: str, specification_name: str, node_type: str = "be"):
        """
        修改Doris节点规格
        :param name: 实例名称
        :param specification_name: 新规格名称（用于页面选择）
        :param node_type: 节点类型，"fe"或"be"
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()

        # 根据节点类型确定节点名称（使用原始命名格式）
        if node_type.lower() == "fe":
            node_name = f"{name}_fe_node01"
        else:
            node_name = f"{name}_be_node01"

        self.click_option(node_name, "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为Doris实例绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        :return: 绑定的IP地址
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_text("绑定公网IP").first.click()

        # 使用更精确的dialog定位
        dialog = self.get_by_label("绑定公网IP", exact=True)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        # 使用dialog内的确定按钮，避免多个匹配
        self.dialog_confirm.click()

        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """
        为Doris实例解绑弹性IP
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_label("详情").get_by_text("解绑公网IP").first.click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str = None, node_type: str = "fe"):
        """
        为Doris节点绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        :param node_type: 节点类型，"fe"或"be"
        :return: 绑定的IP地址
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()

        # 根据节点类型确定节点名称（使用原始命名格式）
        if node_type.lower() == "fe":
            node_name = f"{name}_fe_node01"
        else:
            node_name = f"{name}_be_node01"

        self.click_dropdown_option(node_name, "绑定公网IP")

        # 使用更精确的dialog定位
        dialog = self.get_by_label("绑定公网IP", exact=True)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network).click()
        self.wait_for_page_ready()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.dialog_confirm.click()

        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str, node_type: str = "fe"):
        """
        为Doris节点解绑弹性IP
        :param name: 实例名称
        :param node_type: 节点类型，"fe"或"be"
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()

        # 根据节点类型确定节点名称（使用原始命名格式）
        if node_type.lower() == "fe":
            node_name = f"{name}_fe_node01"
        else:
            node_name = f"{name}_be_node01"

        self.click_dropdown_option(node_name, "解绑公网IP")
        self.get_by_role("dialog").get_by_text("确定").click()

        # self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_be_node(self, name: str, disk_type: str = None, specification_name: str = "doris.d1 doris.d1.4c8g 4核 8GiB"):
        """
        为Doris实例添加BE节点
        :param name: 实例名称
        :param disk_type: 磁盘类型，如果未指定则使用环境变量中的磁盘类型
        :param specification_name: 节点规格名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_label("详情").get_by_text("新增BE节点").click()

        # 选择数据盘类型
        dialog = self.get_by_label("新增节点")
        dialog.get_by_text("数据盘类型", exact=True) \
            .locator("xpath=ancestor::div[contains(@class,'el-form-item')]") \
            .locator("input").click()
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_disk_type = disk_type if disk_type else self.volume_type
        self.page.locator("li").filter(has_text=selected_disk_type).click()

        # 选择计算规格
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()

        # 确认添加
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_node(self, name: str, node_name: str):
        """
        删除Doris实例的节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(3)
        self.wait_for_page_ready()
        self.click_dropdown_option(node_name, "删除节点")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def stop_node(self, name: str, node_name: str):
        """
        停止Doris节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.click_dropdown_option(node_name, "停止节点")
        self.get_by_label("停止").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def start_node(self, name: str, node_name: str):
        """
        启动Doris节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.click_dropdown_option(node_name, "启动节点")
        self.get_by_label("启动").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def offline_be_node(self, name: str, node_name: str):
        """
        下线Doris BE节点（从集群中移除但不删除，下线后无法再上线）
        :param name: 实例名称
        :param node_name: BE节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.click_dropdown_option(node_name, "下线节点")
        self.get_by_label("下线").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def restart_node(self, name: str, node_name: str):
        """
        重启Doris节点
        :param name: 实例名称
        :param node_name: 节点名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.click_dropdown_option(node_name, "重启节点")
        self.get_by_role("dialog").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def create_database(self, name: str, db_name: str, catalog: str = "internal"):
        """
        在指定Doris实例下创建数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        :param catalog: 数据目录（默认为internal）
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="数据库").click()
        self.wait_for_page_ready()
        self.locator(".el-icon-plus").click()

        dialog = self.get_by_label("新建数据库")
        # 选择catalog
        dialog.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=catalog).click()
        # 输入数据库名称
        dialog.locator("div").filter(has_text=re.compile(r"^数据库名称$")).get_by_role("textbox").fill(db_name)
        # 确认创建
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_database(self, name: str, db_name: str):
        """
        在指定Doris实例下删除数据库
        :param name: 实例名称
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="数据库", exact=True).click()
        sleep(3)
        self.wait_for_page_ready()
        self.page.locator(f"span.key-name:text-is('{db_name}')") \
            .locator("xpath=ancestor::tr[1]") \
            .get_by_text("删除") \
            .click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_user(self, name: str, user_name: str, password: str):
        """
        在指定Doris实例下创建用户并授权
        :param name: 实例名称
        :param user_name: 用户名
        :param password: 密码
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.btn_create.click()

        dialog = self.get_by_role("dialog")
        # 输入用户名
        dialog.locator("form div").filter(has_text=re.compile(r"^用户名$")).get_by_role("textbox").fill(user_name)
        # 输入密码
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(password)
        # 确认密码
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)
        # 确认创建
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def change_user_password(self, name: str, user_name: str, new_password: str):
        """
        修改Doris用户密码
        :param name: 实例名称
        :param user_name: 用户名
        :param new_password: 新密码
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "修改用户")

        dialog = self.get_by_label("修改用户")
        # 输入新密码
        dialog.locator("input[type=\"password\"]").fill(new_password)
        # 确认新密码
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        # 确认修改
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_user(self, name: str, user_name: str):
        """
        在指定Doris实例下删除用户
        :param name: 实例名称
        :param user_name: 用户名
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_dropdown_option(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_users(self, name: str, user_names: list):
        """
        在指定Doris实例下批量删除用户
        :param name: 实例名称
        :param user_names: 用户名列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()

        for user_name in user_names:
            self.get_by_role("row", name=re.compile(user_name)).locator("span").nth(1).click()

        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def authorize_user(self, name: str, user_name: str, db_name: str, privileges: str = "对数据库、表的读写权限"):
        """
        为Doris用户授权数据库
        :param name: 实例名称
        :param user_name: 用户名
        :param db_name: 数据库名称
        :param privileges: 权限类型，可选：
            - "对数据库、表的只读权限"
            - "对数据库、表的写权限"
            - "对数据库、表的更改权限"
            - "创建数据库、表的权限"
            - "删除对数据库、表的权限"
            - "资源的使用权限"
            - "执行 SHOW CREATE VIEW 的权限"
            - "对数据库、表的读写权限" (默认)
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        sleep(2)
        self.get_by_role("tab", name="用户").click()
        sleep(2)
        self.wait_for_page_ready()
        self.click_option(user_name, "授权")
        dialog = self.get_by_label("授权", exact=True)
        sleep(2)
        dialog.get_by_role("row", name=re.compile(db_name)).locator("span").nth(1).click()
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=privileges).click()
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def deauthorize_user(self, name: str, user_name: str, db_name: str):
        """
        解除Doris用户数据库授权
        :param name: 实例名称
        :param user_name: 用户名
        :param db_name: 数据库名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="用户").click()
        self.wait_for_page_ready()
        self.click_option(user_name, "解除授权")
        dialog = self.get_by_label("解除授权")
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=db_name).click()
        dialog.click()
        confirm_btn = dialog.get_by_text("确定").locator("visible=true").last
        confirm_btn.scroll_into_view_if_needed()
        confirm_btn.click()

    @submenu("实例管理")
    def enable_audit_log(self, name: str):
        """
        为Doris实例开启审计日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="审计日志").click()
        self.get_by_text("立即开启").click()
        self.get_by_label("开启审计日志").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def disable_audit_log(self, name: str):
        """
        为Doris实例关闭审计日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name="审计日志").click()
        self.get_by_text("服务设置").first.click()
        self.get_by_role("switch").locator("span").click()
        self.get_by_label("服务设置").get_by_text("确定").click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """
        为Doris实例添加白名单
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
        为Doris实例删除单个白名单
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
        为Doris实例批量删除白名单
        :param name: 实例名称
        :param ip_addresses: IP地址或CIDR的列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
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
        为Doris实例重置白名单
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def edit_fe_parameter(self, name: str, param_name: str, param_value: str):
        """
        编辑Doris实例的FE节点参数并应用
        :param name: 实例名称
        :param param_name: 参数名称
        :param param_value: 参数新值
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(2)
        self.wait_for_page_ready()
        self.get_by_role("tab", name="参数设置").click()
        self.wait_for_page_ready()
        sleep(2)
        # 定位到参数行并点击编辑图标
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
    def edit_be_parameter(self, name: str, param_name: str, param_value: str):
        """
        编辑Doris实例的BE节点参数并应用
        :param name: 实例名称
        :param param_name: 参数名称
        :param param_value: 参数新值
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.wait_for_page_ready()
        sleep(2)
        self.get_by_role("tab", name="参数设置").click()
        self.wait_for_page_ready()
        # 选择BE节点类型
        self.get_by_placeholder("请选择节点类型").click()
        self.get_by_text("BE节点").click()
        sleep(2)
        # 定位到参数行并点击编辑图标
        self.page.locator("tr").filter(has_text=param_name).get_by_text("编辑").last.click()
        # 在弹窗中修改值
        dialog = self.get_by_label("编辑参数")
        spinbutton = dialog.get_by_role("spinbutton")
        spinbutton.click()
        spinbutton.fill(param_value)
        dialog.get_by_text("确定").click()
        # 应用更改
        self.get_by_text("应用", exact=True).click()
        self.get_by_label("提示").get_by_text("确定").click()

    def assert_database_exist(self, db_name: str):
        """
        专门用于 Doris 数据库列表的断言方法（前缀匹配）
        注意：调用此方法前需要已经在数据库 Tab 页面
        :param db_name: 数据库名前缀
        """
        self.logger.info(f"检查是否存在以前缀 '{db_name}' 开头的数据库")

        # 等待页面加载完成
        self.wait_for_page_ready()

        # 定位所有数据库名称
        db_elements = self.locator("span.key-name")

        # 等待至少出现一个数据库（避免 count 瞬时为 0）
        db_elements.first.wait_for(state="visible", timeout=30000)

        # 提取所有数据库名称
        db_list = []
        for i in range(db_elements.count()):
            db_text = db_elements.nth(i).inner_text().strip()
            db_list.append(db_text)
            self.logger.debug(f"第{i + 1}个数据库: {db_text}")

        self.logger.info(f"获取到的数据库列表共 {len(db_list)} 个: {db_list}")

        # 前缀匹配
        matched_dbs = [db for db in db_list if db.startswith(db_name)]

        if matched_dbs:
            self.logger.info(f"匹配到数据库（前缀匹配）: {matched_dbs}")
        else:
            assert False, (
                f"未找到以前缀 '{db_name}' 开头的数据库，"
                f"实际数据库列表: {db_list}"
            )


