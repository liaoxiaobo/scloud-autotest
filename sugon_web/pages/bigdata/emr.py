import re
from time import sleep

from sugon_web.common.base import BasePage, submenu


class EMRPage(BasePage):
    """E-MapReduce 集群管理页面对象。"""

    service_name = "E-MapReduce"

    def _select_visible_option(self, option_text: str = None, exact: bool = True):
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        items = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        target = None
        if option_text:
            if option_text == "Autotest":
                pattern = re.compile(rf"^{re.escape(option_text)}$")
            elif exact:
                pattern = re.compile(rf"^{re.escape(option_text)}$")
            else:
                pattern = re.compile(rf"^{re.escape(option_text)}.*")
            target = items.filter(
                has_text=pattern
            ).first
            if target.count() == 0:
                raise AssertionError(f"下拉选项中未找到: {option_text}")
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
            sleep(0.5)

    def _select_labeled_option(self, label_text: str, option_text: str = None, exact: bool = True, retries: int = 1):
        field = self.select_labeled_dropdown(label_text)
        last_error = None
        for _ in range(retries):
            field.scroll_into_view_if_needed()
            field.click()
            try:
                self._select_visible_option(option_text, exact=exact)
                return
            except AssertionError as exc:
                last_error = exc
                self.page.keyboard.press("Escape")
                sleep(2)
        raise last_error

    def _select_next_form_item_option(self, previous_label: str, option_text: str, exact: bool = False, retries: int = 1):
        field = self.locator(".el-form-item").filter(has_text=previous_label).first.locator(
            "xpath=following-sibling::div[contains(@class,'el-form-item')][1]//input[@placeholder='请选择']"
        )
        last_error = None
        for _ in range(retries):
            field.scroll_into_view_if_needed()
            field.click()
            try:
                self._select_visible_option(option_text, exact=exact)
                return
            except AssertionError as exc:
                last_error = exc
                self.page.keyboard.press("Escape")
                sleep(2)
        raise last_error

    def _fill_labeled_input(self, label_text: str, value: str, index: int = 0):
        form_item = self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label_text)}"))
        form_item.locator("input").nth(index).fill(value)

    def _active_detail_tab(self):
        return self.locator(".el-tab-pane:not([aria-hidden='true'])")

    def ensure_list_page(self):
        if "/map-reduce-list" not in self.page.url:
            self.page.goto(f"{self.base_url}/emr/#/map-reduce-list")
            self.page.wait_for_load_state("networkidle")

    def ensure_detail_tab(self, name: str, tab_name: str = "基础信息"):
        """进入集群详情页并切换到指定页签。"""
        if "/cluster-detail/" not in self.page.url:
            self.ensure_list_page()
            row = self.get_row_by_name(name)
            row.locator("td").nth(1).click()
            sleep(2)
        if tab_name:
            self.get_by_role("tab", name=tab_name).click()
            sleep(1)

    def _select_first_radio_in_dialog(self, dialog):
        radio = dialog.locator("label[role='radio'], .el-radio").first
        radio.wait_for(state="visible", timeout=5000)
        radio.click()

    @submenu("实例")
    def create_cluster(
        self,
        name: str,
        deploy_mode: str = "主从分置",
        password: str = "admin1234@sugon",
        manager_password: str = "admin1234@sugon",
        cluster: str = "Autotest",
        network: str = "Autotest",
        subnet: str = "Autotest:10.",
        security_group: str = "default",
        disk_type: str = None,
        disk_size: int = 100,
    ):
        """创建 E-MapReduce 集群。"""
        self.btn_create.click()
        sleep(1)

        self._fill_labeled_input("集群名称", name)
        self._fill_labeled_input("密码", password)
        self.locator(".el-form-item").filter(has_text=re.compile(r"^确认密码")).nth(0).locator("input").fill(password)
        self._fill_labeled_input("EMR Manager密码", manager_password)
        self.locator(".el-form-item").filter(has_text=re.compile(r"^确认密码")).nth(1).locator("input").fill(
            manager_password
        )

        self._select_labeled_option("产品版本")
        sleep(1)

        self._select_labeled_option("集群", cluster, exact=False, retries=10)
        self._select_labeled_option("专有网络", network, exact=False, retries=10)
        self._select_next_form_item_option("专有网络", subnet, exact=False, retries=10)
        self._select_labeled_option("默认安全组", security_group, exact=False, retries=10)
        self._select_labeled_option("部署模式", deploy_mode, retries=10)
        sleep(1)

        selected_disk_type = disk_type if disk_type and disk_type != "default" else self.volume_type
        for row_index in range(self.locator(".el-table__expand-icon").count()):
            expand_icon = self.locator(".el-table__expand-icon").nth(row_index)
            if "expanded" not in (expand_icon.get_attribute("class") or ""):
                expand_icon.click()
                sleep(0.5)

        for dropdown in self.locator(".el-form-item").filter(has_text="数据盘类型").locator("input[placeholder='请选择']").all():
            if dropdown.input_value().strip():
                continue
            dropdown.scroll_into_view_if_needed()
            dropdown.click()
            option_pattern = re.compile(rf"类型：\s*{re.escape(selected_disk_type)}\s*[；;]")
            option = self.page.locator("body > div.el-select-dropdown:visible").last.locator("li").filter(
                has_text=option_pattern
            ).first
            option.scroll_into_view_if_needed()
            try:
                option.click(timeout=3000)
            except Exception:
                option.click(force=True, timeout=3000)

        for spin in self.locator(".el-form-item").filter(has_text="数据盘大小").locator("input[role='spinbutton']").all():
            spin.fill(str(disk_size))

        self.get_by_text("点击创建", exact=True).click()

    def assert_cluster_visible(self, name: str):
        self.ensure_list_page()
        self.locator(".el-table").filter(has_text=name).first.wait_for(state="visible", timeout=10000)

    @submenu("实例")
    def delete_cluster(self, name: str):
        """删除 E-MapReduce 集群。"""
        self.click_action(name, "删除集群")
        self.dialog_confirm.click()

    @submenu("实例")
    def batch_delete_clusters(self, names: list[str]):
        for name in names:
            self.get_by_role("row", name=re.compile(re.escape(name))).locator("label").first.click()
        self.get_by_text("删除", exact=True).click()
        self.dialog_confirm.click()

    @submenu("实例")
    def instance_ip_binding(self, name: str, network: str):
        self.ensure_detail_tab(name, "基础信息")
        self.get_by_text("绑定公网IP", exact=True).first.click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.get_by_placeholder("请选择").first.click()
        self._select_visible_option(network, exact=False)
        row = dialog.locator("tr.el-table__row").filter(has_text="运行中").first
        if row.count() == 0:
            row = dialog.locator("tr.el-table__row").first
        ip = row.locator("td").nth(1).inner_text().strip()
        row.locator("label[role='radio'], .el-radio").first.click()
        dialog.get_by_text("确定", exact=True).click()
        return ip

    def add_service(self, name: str):
        self.ensure_detail_tab(name, "集群服务")
        self._active_detail_tab().get_by_text("添加服务", exact=True).click()
        dialog = self.page.locator("div.el-dialog:visible").last
        checkbox = dialog.locator("label.el-checkbox:not(.is-disabled)").first
        checkbox.wait_for(state="visible", timeout=5000)
        checkbox.click()
        dialog.get_by_text("确定", exact=True).click()

    def uninstall_service(self, name: str):
        self.ensure_detail_tab(name, "集群服务")
        tab = self._active_detail_tab()
        tab.get_by_text("卸载服务", exact=True).click()
        checkbox = tab.locator("label.el-checkbox").first
        checkbox.wait_for(state="visible", timeout=5000)
        checkbox.click()
        tab.get_by_text("确定", exact=True).click()
        self.page.locator("div.el-dialog:visible").last.get_by_text("确定", exact=True).click()

    def operate_all_services(self, name: str, action: str):
        self.ensure_detail_tab(name, "集群服务")
        self._active_detail_tab().get_by_text("更多操作", exact=True).click()
        self.page.locator("body .el-dropdown-menu:visible").last.get_by_text(action, exact=True).click()

    def _first_node_group_action(self, action: str):
        tab = self._active_detail_tab()
        action_button = tab.locator(".blue-link").filter(has_text=re.compile(rf"^{re.escape(action)}$")).first
        if action_button.count() == 0:
            raise AssertionError(f"当前没有可用的节点组操作: {action}")
        action_button.click()

    def change_specification(self, name: str):
        self.ensure_detail_tab(name, "节点管理")
        self._first_node_group_action("修改规格")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator("label[role='radio'], .el-radio").last.click()
        dialog.get_by_text("确定", exact=True).click()

    def expand_disk(self, name: str, size: int = 110):
        self.ensure_detail_tab(name, "节点管理")
        self._first_node_group_action("磁盘扩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator("input[role='spinbutton']").first.fill(str(size))
        dialog.get_by_text("确定", exact=True).click()

    def add_node(self, name: str, password: str = "Admin1234@sugon"):
        self.ensure_detail_tab(name, "节点管理")
        self._first_node_group_action("扩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        if dialog.locator("input[type='password']").count() >= 2:
            dialog.locator("input[type='password']").nth(0).fill(password)
            dialog.locator("input[type='password']").nth(1).fill(password)
        dialog.get_by_text("确定", exact=True).click()

    def delete_node(self, name: str):
        self.ensure_detail_tab(name, "节点管理")
        self._first_node_group_action("缩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator("input[role='spinbutton']").first.fill("1")
        dialog.get_by_text("确定", exact=True).click()

    def node_ip_binding(self, name: str, network: str):
        self.ensure_detail_tab(name, "节点管理")
        tab = self._active_detail_tab()
        expand = tab.locator(".el-table__expand-icon").first
        if "expanded" not in (expand.get_attribute("class") or ""):
            expand.click()
            sleep(1)
        tab.locator(".el-table__expanded-cell").locator("cl-table-dropdown, .cl-table-dropdown, .el-dropdown").first.click()
        self.page.locator("body .el-dropdown-menu:visible").last.get_by_text("绑定公网IP", exact=True).click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.get_by_placeholder("请选择").first.click()
        self._select_visible_option(network, exact=False)
        row = dialog.locator("tr.el-table__row").filter(has_text="运行中").first
        if row.count() == 0:
            row = dialog.locator("tr.el-table__row").first
        ip = row.locator("td").nth(1).inner_text().strip()
        row.locator("label[role='radio'], .el-radio").first.click()
        dialog.get_by_text("确定", exact=True).click()
        return ip
