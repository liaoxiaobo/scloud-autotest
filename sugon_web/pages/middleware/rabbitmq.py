import re
from time import sleep

from sugon_web.common.base import BasePage, submenu


class RabbitMQPage(BasePage):
    """分布式消息服务 RabbitMQ 实例管理页面对象"""

    service_name = "分布式消息服务 RabbitMQ"

    def _select_visible_option(self, option_text: str = None, exact: bool = True):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        items = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        target = None
        if option_text:
            if exact:
                option = items.filter(has_text=re.compile(rf"^{re.escape(option_text)}$"))
            else:
                option = items.filter(has_text=option_text)
            if option.count() > 0:
                target = option.first
        if target is None:
            target = items.first

        target.scroll_into_view_if_needed()
        try:
            target.click(timeout=3000)
        except Exception:
            target.click(force=True, timeout=3000)
        try:
            dropdown.wait_for(state="hidden", timeout=3000)
        except Exception:
            self.page.keyboard.press("Escape")

    def ensure_instance_tab(self, name: str, tab_name: str = "详情"):
        """进入 RabbitMQ 实例详情页并切换到指定页签。"""
        if "/rbs-detail" not in self.page.url and "/detail" not in self.page.url:
            row = self.get_row_by_name(name)
            cells = row.locator("td")
            target = cells.nth(1) if cells.count() > 1 else row
            target.click()
            sleep(2)
        if tab_name and tab_name != "详情":
            self.get_by_role("tab", name=tab_name).click()
            sleep(1)

    @submenu("实例管理")
    def create_instance(
        self,
        name: str,
        instance_type: str = "集群",
        version: str = "3.11.28",
        cluster: str = "Autotest",
        password: str = "Admin1234@sugon",
        network: str = "Autotest",
        subnet: str = "Autotest:10.",
        disk_type: str = None,
        disk_size: int = 10,
        specification_name: str = "rbs.d6.large",
    ):
        """创建 RabbitMQ 实例。"""
        self.btn_create.click()
        sleep(1)

        self.get_by_role("radio", name=instance_type).click()
        self.get_by_placeholder("请输入名称").fill(name)

        version_dropdown = self.select_labeled_dropdown("版本")
        version_dropdown.click()
        self._select_visible_option(version)

        cluster_dropdown = self.select_labeled_dropdown("集群")
        cluster_dropdown.click()
        self._select_visible_option(cluster)

        self.get_by_placeholder("请输入admin管理员用户密码").fill(password)
        self.get_by_placeholder("请输入确认密码").fill(password)

        self.select_network("请选择网络", network)
        self.select_network("请选择子网", subnet)

        selected_disk_type = disk_type if disk_type and disk_type != "default" else self.volume_type
        self.select_disk_type_like_doris(selected_disk_type, label_texts=["数据盘类型"])
        self.locator("div").filter(has_text=re.compile(r"^数据盘大小\(GiB\)$")).get_by_role("spinbutton").fill(
            str(disk_size)
        )

        specification_row = self.locator("tr").filter(has_text=re.compile(re.escape(specification_name)))
        if specification_row.count() > 0:
            specification_row.first.locator(".el-radio, label[role='radio']").first.click()
        else:
            self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()

        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name: str):
        """删除 RabbitMQ 实例。"""
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list[str]):
        """批量删除 RabbitMQ 实例。"""
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()
        self.locator("div.cloud-button-btn").filter(has_text=re.compile(r"批量删除|删除")).first.click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """修改 RabbitMQ 实例名称。"""
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str):
        """实例绑定公网IP。"""
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("绑定公网IP", exact=True).first.click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("body > div.el-select-dropdown:visible").last.get_by_text(network).click()

        ip_row = dialog.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text().strip()
        ip_row.locator("label[role='radio']").click()
        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """实例解绑公网IP。"""
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("解绑公网IP", exact=True).first.click()
        self.page.locator("div.el-dialog:visible").last.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """添加白名单。"""
        self.ensure_instance_tab(name, "白名单")
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """删除单个白名单。"""
        self.ensure_instance_tab(name, "白名单")
        whitelist_tag = self.locator("span").filter(has_text=ip_address).first
        whitelist_tag.hover()
        close_icon = whitelist_tag.locator("i").first
        try:
            close_icon.click(timeout=5000)
        except Exception:
            close_icon.click(force=True)
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list[str]):
        """批量删除白名单。"""
        self.ensure_instance_tab(name, "白名单")
        sleep(2)
        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        dialog = self.get_by_label("删除白名单")
        dialog.get_by_placeholder("请选择要删除的白名单").click()
        for ip_address in ip_addresses:
            self.page.locator("li", has_text=ip_address).click()
        dialog.locator(".el-dialog__header").click()
        self.page.locator("div.el-select-dropdown.label-select:visible").wait_for(state="hidden", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """重置白名单。"""
        self.ensure_instance_tab(name, "白名单")
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()
