import re
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util


class PrometheusPage(BasePage):
    """监控服务 Prometheus 集群管理页面对象"""

    service_name = "监控服务"

    def _select_visible_option(self, option_text: str = None, exact: bool = True):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        items = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        if option_text:
            if exact:
                target = items.filter(has_text=re.compile(rf"^{re.escape(option_text)}$"))
            else:
                target = items.filter(has_text=option_text)
            if target.count() > 0:
                target.first.click()
                return
        items.first.click()

    def _ensure_agent_node_enabled(self):
        agent_label = self.locator("label").filter(has_text="部署Agent节点").first
        if agent_label.count() == 0:
            return
        checked_input = agent_label.locator("input[type='checkbox']")
        if checked_input.count() > 0 and not checked_input.first.is_checked():
            agent_label.click()

    def _configure_agent_node(self, disk_type: str):
        """配置底部角色配置中的 Agent 节点规格和数据盘类型。"""
        agent_row = self.locator("tr").filter(has_text="Agent节点").last
        if agent_row.count() == 0:
            return

        selects = agent_row.locator(".el-select input[placeholder='请选择']")
        if selects.count() > 0 and not selects.nth(0).input_value().strip():
            selects.nth(0).click()
            self._select_visible_option("2核 4GiB", exact=False)

        if selects.count() > 1 and not selects.nth(1).input_value().strip():
            selects.nth(1).click()
            self._select_visible_option(disk_type, exact=False)

    def ensure_instance_tab(self, name: str, tab_name: str = "详情"):
        """进入 Prometheus 集群详情页并切换到指定页签。"""
        if "/prom-detail" not in self.page.url and "/detail" not in self.page.url:
            row = self.get_row_by_name(name)
            cells = row.locator("td")
            target = cells.nth(1) if cells.count() > 1 else row
            target.click()
            sleep(2)
        if tab_name and tab_name != "详情":
            self.get_by_role("tab", name=tab_name).click()
            sleep(1)

    @submenu("集群管理")
    def create_instance(
        self,
        name: str,
        version: str = "v1.99",
        cluster: str = "Autotest",
        network: str = "Autotest",
        subnet: str = "Autotest:10.",
        disk_type: str = None,
        disk_size: int = 10,
        specification_name: str = "prom.d6.xlarge",
    ):
        """创建 Prometheus 集群。"""
        self.btn_create.click()
        sleep(1)

        self.get_by_placeholder("请输入名称").fill(name)

        self.locator("div").filter(has_text=re.compile(r"^版本")).locator("input").first.click()
        self._select_visible_option(version)

        self.locator("div").filter(has_text=re.compile(r"^集群")).locator("input").first.click()
        self._select_visible_option(cluster)

        self._ensure_agent_node_enabled()

        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        selected_disk_type = disk_type if disk_type and disk_type != "default" else self.volume_type
        db_util.select_disk_type_like_doris(self, selected_disk_type, label_texts=["数据盘类型"])
        self.locator("div").filter(has_text=re.compile(r"^数据盘大小\(GiB\)$")).get_by_role("spinbutton").fill(
            str(disk_size)
        )

        specification_row = self.locator("tr").filter(has_text=re.compile(re.escape(specification_name)))
        if specification_row.count() > 0:
            specification_row.first.locator(".el-radio, label[role='radio']").first.click()
        else:
            self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()

        self._configure_agent_node(selected_disk_type)
        self.btn_submit.click()

    @submenu("集群管理")
    def delete_instance(self, name: str):
        """删除 Prometheus 集群。"""
        try:
            self.click_action(name, "删除集群")
        except Exception:
            self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("集群管理")
    def rename_instance(self, old_name: str, new_name: str):
        """修改 Prometheus 集群名称。"""
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("集群管理")
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

    @submenu("集群管理")
    def instance_ip_unbinding(self, name: str):
        """实例解绑公网IP。"""
        self.ensure_instance_tab(name, "详情")
        self.get_by_text("解绑公网IP", exact=True).first.click()
        self.page.locator("div.el-dialog:visible").last.get_by_text("确定", exact=True).click()
