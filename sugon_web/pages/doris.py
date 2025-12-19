import re
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
        db_util.select_network(self, "请选择子网", subnet, fuzzy_match=True)

        # --- 配置设置 ---
        # 操作系统
        self.locator("div").filter(has_text=re.compile(r"^操作系统CentOS 7\.9AnolisOS 7\.9$")).get_by_placeholder(
            "请选择").click()
        self.locator("li").filter(has_text=re.compile(rf"^{re.escape(os_type)}$")).click()

        # 大小写策略 - 通过下拉框选择
        case_sensitivity_dropdown = self.locator("form").filter(
            has_text="配置 专有网络 操作系统 大小写策略"
        ).get_by_placeholder("请选择", exact=True).nth(1)
        case_sensitivity_dropdown.click()
        # 滚动到选项并点击
        case_option = self.page.locator("li").filter(has_text=case_sensitivity).first
        case_option.scroll_into_view_if_needed()
        case_option.click()

        # 密码
        self.get_by_placeholder("请输入admin管理员用户密码").fill(password)
        self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)

        # FE节点配置 - 高可用类型
        self.get_by_role("radio", name=ha_type).click()

        # FE节点数据盘类型
        fe_disk_dropdown = self.locator("form").filter(
            has_text="FE节点配置 高可用"
        ).get_by_placeholder("请选择", exact=True).nth(3)
        fe_disk_dropdown.click()
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_fe_disk_type = fe_disk_type if fe_disk_type else self.volume_type
        self.locator("li").filter(has_text=selected_fe_disk_type).nth(1).click()

        # FE节点数据盘大小
        self.get_by_role("spinbutton").first.fill(str(fe_disk_size))

        # BE节点配置 - 数据盘类型
        be_disk_dropdown = self.locator("form").filter(
            has_text="BE节点配置"
        ).get_by_placeholder("请选择", exact=True).nth(4)
        be_disk_dropdown.click()
        # 使用指定的磁盘类型，如果未指定则使用环境变量中的磁盘类型
        selected_be_disk_type = be_disk_type if be_disk_type else self.volume_type
        self.locator("li").filter(has_text=selected_be_disk_type).nth(2).click()

        # BE节点数据盘大小
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
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为Doris实例绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        :return: 绑定的IP地址
        """
        self.locator("#cloud-container-content").get_by_text(name).click()
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
        self.locator("#cloud-container-content").get_by_text(name).click()
        self.wait_for_page_ready()
        self.get_by_label("详情").get_by_text("解绑公网IP").first.click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()