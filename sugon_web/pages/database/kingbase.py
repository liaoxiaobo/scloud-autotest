import re
from time import sleep, time

import pytest

from sugon_web.common.base import submenu
from sugon_web.pages.database.pgsql import PgSQLPage


class KingbasePage(PgSQLPage):
    """KingbaseES实例管理页面对象"""

    service_name = "人大金仓 KingbaseES"

    def _select_visible_option(self, option_text: str = None):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        items = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        if option_text:
            target = items.filter(has_text=re.compile(rf"^{re.escape(option_text)}$"))
            if target.count() > 0:
                target.first.click()
                return
        items.first.click()

    def _open_instance_detail_tab(self, name: str, tab_name: str):
        self.goto_detail_page(name, tab_name=tab_name)
        sleep(2)

    def _bind_public_ip_from_dialog(self, pool_name: str = None) -> str:
        dialog = self.get_by_label("绑定公网IP", exact=True)
        pool_select = dialog.locator(".el-select").first
        pool_select.click()
        self._select_visible_option(pool_name)
        self.page.wait_for_timeout(1000)

        ip_rows = dialog.locator("tr.el-table__row")
        if ip_rows.count() == 0:
            raise AssertionError("绑定公网IP弹窗中没有可用IP")

        ip_row = ip_rows.first
        ip_address = ip_row.locator("td").nth(1).inner_text().strip()
        ip_row.locator("label[role='radio']").click()
        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    def _get_detail_node_names(self, name: str) -> list[str]:
        self.goto_detail_page(name, tab_name="详情")
        self.page.wait_for_timeout(1000)
        names = self.get_column_data("名称", context="active-tab")
        return [node_name for node_name in names if node_name.startswith(f"{name}-")]

    def assert_whitelist_contains(self, ip_address: str):
        self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text(ip_address, exact=True).first.wait_for(
            state="visible", timeout=10000
        )

    def assert_whitelist_not_contains(self, ip_address: str):
        deadline = time() + 10
        locator = self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text(ip_address, exact=True).first
        while time() < deadline:
            if locator.count() == 0 or not locator.is_visible():
                return
            self.page.wait_for_timeout(500)
        raise AssertionError(f"白名单中仍然存在 {ip_address}")

    @submenu("实例管理")
    def create_instance(
        self,
        name: str,
        instance_type: str = "单机",
        version: str = None,
        password: str = "Admin1234@sugon",
        network: str = "Autotest",
        subnet: str = "Autotest:10.",
        disk_type: str = None,
        disk_size: int = 20,
        cluster_name: str = None,
        node_count: int = 1,
        db_mode: str = "pg",
        auth_method: str = "scram-sha-256",
        charset: str = "UTF8",
        collation: str = "zh_CN.utf8",
    ):
        """创建KingbaseES实例，支持单机和集群。"""
        self.btn_create.click()

        self.get_by_role("radio", name=instance_type).click()
        self.input_name().fill(name)

        if instance_type == "集群":
            self.locator("div").filter(has_text=re.compile(r"^恢复方式")).get_by_text("等待", exact=True).click()
            self.locator("div").filter(has_text=re.compile(r"^节点数量")).get_by_role("spinbutton").fill(str(node_count))

        version_dropdown = self.select_labeled_dropdown("版本")
        version_dropdown.click()
        self._select_visible_option(version)

        cluster_dropdown = self.select_labeled_dropdown("集群")
        cluster_dropdown.click()
        self._select_visible_option(cluster_name)

        self.get_by_role("radio", name=db_mode, exact=True).click()
        self.get_by_role("radio", name=auth_method, exact=True).click()

        charset_dropdown = self.select_labeled_dropdown("编码")
        charset_dropdown.click()
        self._select_visible_option(charset)

        locale_dropdown = self.select_labeled_dropdown("编码区域")
        locale_dropdown.click()
        self._select_visible_option(collation)

        self.get_by_placeholder("请输入root管理员用户密码").fill(password)
        self.input_confirm_password().fill(password)

        self.select_network("请选择网络", network)
        self.select_network("请选择子网", subnet)

        selected_disk_type = disk_type if disk_type else self.volume_type
        self.select_disk_type_like_doris(selected_disk_type)
        self.locator("form").filter(has_text="数据盘大小").get_by_role("spinbutton").fill(str(disk_size))

        self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()
        self.btn_submit.click()

    @submenu("实例管理")
    def restart_instance(self, name: str):
        """重启KingbaseES实例数据库。"""
        self.click_action(name, "重启数据库")
        self.get_by_label("重启数据库").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """修改KingbaseES实例名称。"""
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_root_password(self, name: str, new_password: str):
        """重置KingbaseES管理员密码。"""
        self.click_action(name, "重置密码")
        dialog = self.get_by_label("重置密码")
        dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, pool_name: str = None) -> str:
        """为实例绑定公网IP。"""
        self.goto_detail_page(name, tab_name="详情")
        self.get_by_text("绑定公网IP", exact=True).first.click()
        return self._bind_public_ip_from_dialog(pool_name)

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """为实例解绑公网IP。"""
        self.goto_detail_page(name, tab_name="详情")
        self.get_by_text("解绑公网IP", exact=True).first.click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, node_name: str = None, pool_name: str = None) -> str:
        """为节点绑定公网IP。"""
        node_name = node_name or f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "绑定公网IP")
        return self._bind_public_ip_from_dialog(pool_name)

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str, node_name: str = None):
        """为节点解绑公网IP。"""
        node_name = node_name or f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_backup_node(self, name: str):
        """为集群新增备节点。"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(5)
        self.get_by_text("新建备节点", exact=True).first.click()
        self.get_by_label("新建备节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def create_database(
        self,
        name: str,
        db_name: str,
        charset: str = "UTF8",
        collation: str = "zh_CN.utf8",
    ):
        """在实例详情页创建数据库。"""
        self._open_instance_detail_tab(name, "数据库")
        self.btn_create.click()
        dialog = self.get_by_label("新建数据库")
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(db_name)
        dialog.locator(".el-select").nth(0).click()
        self._select_visible_option(charset)
        dialog.locator(".el-select").nth(1).click()
        self._select_visible_option(collation)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_database(self, name: str, db_name: str):
        """删除数据库。"""
        self._open_instance_detail_tab(name, "数据库")
        self.click_action(db_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_databases(self, name: str, db_names: list[str]):
        """批量删除数据库。"""
        self._open_instance_detail_tab(name, "数据库")
        for db_name in db_names:
            self.get_row_by_name(db_name).locator("span").nth(1).click()
        self.btn_batch_delete.click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def create_user(self, name: str, user_name: str, password: str, host: str = "%"):
        """创建用户。"""
        self._open_instance_detail_tab(name, "用户")
        self.btn_create.click()
        dialog = self.get_by_label("创建用户")
        dialog.locator("div").filter(has_text=re.compile(r"^用户名$")).get_by_role("textbox").fill(user_name)
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_user_privileges(self, name: str, user_name: str, new_password: str):
        """修改用户密码。"""
        self._open_instance_detail_tab(name, "用户")
        self.click_action(user_name, "修改用户")
        dialog = self.get_by_label("修改用户")
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def authorize_user(self, name: str, user_name: str, db_name: str):
        """为用户授权数据库。"""
        self._open_instance_detail_tab(name, "用户")
        sleep(2)
        self.click_action(user_name, "授权")
        dialog = self.get_by_label("授权", exact=True)
        sleep(2)
        dialog.get_by_placeholder("搜索数据库名称").fill(db_name)
        dialog.get_by_text("搜索", exact=True).click()
        dialog.get_by_role("row", name=re.compile(db_name)).locator("span").nth(1).click()
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def deauthorize_user(self, name: str, user_name: str, db_name: str):
        """解除用户数据库授权。"""
        self._open_instance_detail_tab(name, "用户")
        sleep(2)
        self.click_action(user_name, "解除授权")
        dialog = self.get_by_label("解除授权")
        sleep(2)
        dialog.locator(".el-select").click()
        self._select_visible_option(db_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """添加白名单。"""
        self._open_instance_detail_tab(name, "白名单")
        self.get_by_text("添加", exact=True).click()
        dialog = self.get_by_label("添加白名单")
        dialog.get_by_role("textbox").fill(ip_address)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """删除单个白名单。"""
        self._open_instance_detail_tab(name, "白名单")
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])")
        active_tab.locator("span").filter(has_text=re.compile(rf"^{re.escape(ip_address)}$")).locator("i").first.click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list[str]):
        """批量删除白名单。"""
        self._open_instance_detail_tab(name, "白名单")
        self.btn_batch_delete.click()
        dialog = self.get_by_label("删除白名单")
        dialog.get_by_placeholder("请选择要删除的白名单").click()
        for ip_address in ip_addresses:
            self.page.locator("li").filter(has_text=ip_address).click()
        dialog.locator(".el-dialog__header").click()
        self.page.locator("div.el-select-dropdown:visible").wait_for(state="hidden", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """重置白名单。"""
        self._open_instance_detail_tab(name, "白名单")
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])")
        active_tab.locator("div.cloud-button-btn").filter(has_text="重置白名单").first.click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def kingbase_hot_migration(self, name: str, node_name: str, bandwidth: str = "50%", cpu_auto: bool = False):
        """节点热迁移。"""
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "热迁移")
        sleep(2)

        dialog = self.get_by_label("热迁移")
        dialog.locator("div").filter(has_text=re.compile(r"^目标物理机")).locator(".el-select").click()
        host_dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        options = host_dropdown.locator("li.el-select-dropdown__item")
        selected_host = None
        for i in range(options.count()):
            option = options.nth(i)
            class_name = option.get_attribute("class") or ""
            if "is-disabled" in class_name:
                continue
            selected_host = option.inner_text().strip().split()[0]
            option.click()
            break

        if not selected_host:
            dialog.get_by_text("取消", exact=True).click()
            pytest.skip("没有可用的物理机可供迁移")

        if bandwidth:
            dialog.locator("div").filter(has_text=re.compile(r"^迁移速率")).locator(".el-select").click()
            self._select_visible_option(bandwidth)

        if cpu_auto:
            dialog.get_by_role("switch").click()

        dialog.get_by_text("确定", exact=True).click()
        return selected_host
