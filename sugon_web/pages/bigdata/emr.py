import re
import time
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config


class EMRPage(BasePage):
    """E-MapReduce 集群管理页面对象。"""

    service_name = "E-MapReduce"
    common_node_name = "common01"

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
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/emr/#/map-reduce-list")
            self.page.wait_for_load_state("networkidle")

    def ensure_detail_tab(self, name: str, tab_name: str = "基础信息"):
        """进入集群详情页并切换到指定页签。"""
        if "/cluster-detail/" not in self.page.url:
            self.ensure_list_page()
            row = self.get_row_by_name(name)
            detail_link = row.locator(".blue-link").filter(has_text=re.compile(rf"^{re.escape(name)}$")).first
            if detail_link.count() == 0:
                raise AssertionError(f"未找到可进入详情的集群名称链接: {name}")
            detail_link.click()
            self.page.wait_for_url(re.compile(r".*/cluster-detail/.*"), timeout=15000)
            self.locator(".el-tabs").wait_for(state="visible", timeout=15000)
        if tab_name:
            tab = self.locator(".el-tabs__item").filter(has_text=re.compile(rf"^{re.escape(tab_name)}$")).first
            if "is-active" not in (tab.get_attribute("class") or ""):
                self.page.keyboard.press("Escape")
                try:
                    self.page.locator(".el-tooltip__popper").evaluate_all(
                        "els => els.forEach(el => el.style.display = 'none')"
                    )
                except Exception:
                    pass
                try:
                    tab.click(timeout=3000)
                except Exception:
                    tab.click(force=True, timeout=3000)
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
        disk_size: int = 60,
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
        expand_icons = self.locator(".el-table__expand-icon")
        for row_index in range(expand_icons.count()):
            expand_icon = expand_icons.nth(row_index)
            if "expanded" not in (expand_icon.get_attribute("class") or ""):
                expand_icon.click()
                sleep(0.5)
            form_items = self.locator(".el-form-item").filter(has_text="数据盘类型")
            if form_items.count() <= row_index:
                continue

            disk_type_item = form_items.nth(row_index)
            dropdown = disk_type_item.locator("input[placeholder='请选择']").first
            current_value = dropdown.input_value().strip()
            if current_value != selected_disk_type:
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
                sleep(1)

            disk_size_items = self.locator(".el-form-item").filter(has_text="数据盘大小")
            if disk_size_items.count() <= row_index:
                continue
            spin = disk_size_items.nth(row_index).locator("input[role='spinbutton']").first
            spin.fill(str(disk_size))
            sleep(1)

        self.get_by_text("点击创建", exact=True).click()

    def assert_cluster_visible(self, name: str):
        self.ensure_list_page()
        self.locator(".el-table").filter(has_text=name).first.wait_for(state="visible", timeout=10000)

    def _select_public_network_in_dialog(self, dialog, network: str = None):
        if not network:
            return
        dialog.get_by_placeholder("请选择").first.click()
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=5000)
        items = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)")
        option = items.filter(has_text=network).first
        if option.count() == 0 and "(" in network:
            option = items.filter(has_text=network.split("(", 1)[0]).first
        if option.count() == 0:
            option = items.first
        option.click()

    def _select_available_public_ip(self, dialog):
        row = dialog.locator("tr.el-table__row").filter(has_text="关闭").first
        if row.count() == 0:
            row = dialog.locator("tr.el-table__row").first
        row.wait_for(state="visible", timeout=10000)
        ip = row.locator("td").nth(1).inner_text().strip()
        row.locator("label[role='radio'], .el-radio").first.click()
        return ip

    def _wait_unbind_public_ip_ready(self, dialog, timeout: int = 30):
        select_input = dialog.locator(".el-form-item").filter(has_text="公网IP").locator("input").first
        last_error = None
        for _ in range(timeout):
            if select_input.input_value().strip():
                return
            select_input.click()
            try:
                dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
                dropdown.wait_for(state="visible", timeout=1000)
                option = dropdown.locator("li.el-select-dropdown__item:not(.is-disabled)").first
                option.wait_for(state="visible", timeout=1000)
                option.click()
                return
            except Exception as exc:
                last_error = exc
                self.page.keyboard.press("Escape")
                sleep(1)
        raise AssertionError(f"解绑公网IP弹窗中未加载出可选公网IP: {last_error}")

    def _ensure_common_node_visible(self, name: str):
        """确保写死的 common01 节点可见。"""
        self.ensure_detail_tab(name, "节点管理")
        if self.page.locator("tr.el-table__row").filter(has_text=self.common_node_name).count() > 0:
            return

        tab = self._active_detail_tab()
        for expand_icon in tab.locator(".el-table__expand-icon").all():
            if "expanded" not in (expand_icon.get_attribute("class") or ""):
                expand_icon.click()
                sleep(0.5)
            if self.page.locator("tr.el-table__row").filter(has_text=self.common_node_name).count() > 0:
                break

        self.page.locator("tr.el-table__row").filter(has_text=self.common_node_name).first.wait_for(
            state="visible", timeout=10000
        )

    def assert_common_node_status(
        self, name: str, node_name: str, status: str = "运行", timeout: int = 300, refresh: bool = False, refresh_interval: int = 5
    ):
        start_time = time.time()
        current_status = "未知"
        first_check = True

        while time.time() - start_time < timeout:
            try:
                if refresh and not first_check:
                    self.btn_refresh.click()
                    self.wait_for_page_ready()
                first_check = False

                self.ensure_detail_tab(name, "节点管理")
                common_row = self.page.locator("tr.el-table__row").filter(has_text=re.compile(r"\bCOMMON\b", re.I)).first
                expand_icon = common_row.locator(".el-table__expand-icon").first
                if expand_icon.count() > 0 and "expanded" not in (expand_icon.get_attribute("class") or ""):
                    expand_icon.click()
                    sleep(0.5)

                node_row = self.page.locator("tr.el-table__row").filter(has_text=re.compile(rf"^{re.escape(node_name)}\b", re.I)).first
                node_row.wait_for(state="visible", timeout=10000)
                current_status = node_row.inner_text()
                if status in current_status:
                    self.logger.info(f"COMMON 子节点状态验证成功: {node_name} -> {status}")
                    return
            except Exception as e:
                self.logger.debug(f"检查 COMMON 子节点状态时出错: {e}")

            sleep(refresh_interval)

        raise AssertionError(
            f"[StatusAssertion] COMMON 子节点状态 | 状态收敛失败 | "
            f"节点: {node_name} | 期望: '{status}' | 实际: '{current_status}' | 超时未收敛"
        )

    def assert_node_group_status(
        self, name: str, group_name: str, status: str = "运行", timeout: int = 300, refresh: bool = False, refresh_interval: int = 5
    ):
        start_time = time.time()
        current_status = "未知"
        first_check = True

        while time.time() - start_time < timeout:
            try:
                if refresh and not first_check:
                    self.btn_refresh.click()
                    self.wait_for_page_ready()
                first_check = False

                self.ensure_detail_tab(name, "节点管理")
                tab = self._active_detail_tab()
                row = tab.locator("tr.el-table__row").filter(has_text=re.compile(rf"\b{re.escape(group_name)}\b", re.I)).first
                row.wait_for(state="visible", timeout=10000)
                current_status = row.inner_text()
                if status in current_status:
                    self.logger.info(f"节点组状态验证成功: {group_name} -> {status}")
                    return
            except Exception as e:
                self.logger.debug(f"检查节点组状态时出错: {e}")

            sleep(refresh_interval)

        raise AssertionError(
            f"[StatusAssertion] 节点组状态 | 状态收敛失败 | "
            f"节点组: {group_name} | 期望: '{status}' | 实际: '{current_status}' | 超时未收敛"
        )

    def assert_common_node_absent(
        self, name: str, node_name: str, timeout: int = 300, refresh: bool = False, refresh_interval: int = 5
    ):
        start_time = time.time()
        first_check = True

        while time.time() - start_time < timeout:
            try:
                if refresh and not first_check:
                    self.btn_refresh.click()
                    self.wait_for_page_ready()
                first_check = False

                self.ensure_detail_tab(name, "节点管理")
                common_row = self.page.locator("tr.el-table__row").filter(has_text=re.compile(r"\bCOMMON\b", re.I)).first
                expand_icon = common_row.locator(".el-table__expand-icon").first
                if expand_icon.count() > 0 and "expanded" not in (expand_icon.get_attribute("class") or ""):
                    expand_icon.click()
                    sleep(0.5)

                node_rows = self.page.locator("tr.el-table__row").filter(has_text=re.compile(rf"^{re.escape(node_name)}\b", re.I))
                if node_rows.count() == 0:
                    self.logger.info(f"COMMON 子节点不存在断言通过: {node_name} 已消失")
                    return
            except Exception as e:
                self.logger.debug(f"检查 COMMON 子节点不存在时出错: {e}")

            sleep(refresh_interval)

        raise AssertionError(
            f"[StatusAssertion] COMMON 子节点不存在 | 断言失败 | "
            f"节点: {node_name} | 超时 {timeout} 秒后页面仍存在"
        )

    @submenu("实例")
    def delete_cluster(self, name: str):
        """删除 E-MapReduce 集群。"""
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例")
    def batch_delete_clusters(self, names: list[str]):
        for name in names:
            self.get_by_role("row", name=re.compile(re.escape(name))).locator("label").first.click()
        self.get_by_text("批量删除", exact=True).click()
        self.dialog_confirm.click()

    @submenu("实例")
    def instance_ip_binding(self, name: str, network: str):
        self.ensure_detail_tab(name, "基础信息")
        self.get_by_text("绑定公网IP", exact=True).first.click()
        dialog = self.page.locator("div.el-dialog:visible").last
        self._select_public_network_in_dialog(dialog, network)
        ip = self._select_available_public_ip(dialog)
        dialog.get_by_text("确定", exact=True).click()
        return ip

    @submenu("实例")
    def instance_ip_unbinding(self, name: str):
        self.ensure_detail_tab(name, "基础信息")
        self.get_by_text("解绑公网IP", exact=True).first.click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.wait_for(state="visible", timeout=5000)
        self._wait_unbind_public_ip_ready(dialog)
        dialog.get_by_text("确定", exact=True).click()

    def _service_card(self, service_name: str):
        service_pattern = re.compile(re.escape(service_name), re.IGNORECASE)
        return self.page.locator(".el-tab-pane:not([aria-hidden='true']) .serve_item, "
                                 ".el-tab-pane:not([aria-hidden='true']) .serve_item_disable").filter(
            has_text=service_pattern
        ).first

    def _has_service_card(self, service_name: str) -> bool:
        return self.page.evaluate(
            """serviceName => {
                const service = serviceName.toLowerCase();
                return Array.from(document.querySelectorAll(
                    '.serve_content .serve_item, .serve_content .serve_item_disable, ' +
                    '.el-tab-pane:not([aria-hidden="true"]) .serve_item, ' +
                    '.el-tab-pane:not([aria-hidden="true"]) .serve_item_disable'
                )).some(el => {
                    const title = el.querySelector('.title_text')?.textContent?.trim().toLowerCase();
                    return title === service;
                });
            }""",
            service_name,
        )

    def _wait_service_cards_loaded(self, timeout: int = 30):
        cards = self.page.locator(".el-tab-pane:not([aria-hidden='true']) .serve_item, "
                                  ".el-tab-pane:not([aria-hidden='true']) .serve_item_disable")
        cards.first.wait_for(state="visible", timeout=timeout * 1000)

    def _get_service_card_text(self, service_name: str) -> str:
        return self.page.evaluate(
            """serviceName => {
                const service = serviceName.toLowerCase();
                const items = Array.from(document.querySelectorAll(
                    '.serve_content .serve_item, .serve_content .serve_item_disable, ' +
                    '.el-tab-pane:not([aria-hidden="true"]) .serve_item, ' +
                    '.el-tab-pane:not([aria-hidden="true"]) .serve_item_disable'
                ));
                const item = items.find(el => {
                    const title = el.querySelector('.title_text')?.textContent?.trim().toLowerCase();
                    return title === service;
                });
                return item ? item.innerText.replace(/\\s+/g, ' ').trim() : '';
            }""",
            service_name,
        )

    def _ensure_cluster_service_tab_active(self):
        self.page.locator(".el-tabs").wait_for(state="visible", timeout=15000)
        tab = self.page.locator(".el-tabs__item").filter(has_text=re.compile(r"^集群服务$")).first
        if "is-active" not in (tab.get_attribute("class") or ""):
            self.page.keyboard.press("Escape")
            try:
                tab.click(timeout=3000)
            except Exception:
                tab.click(force=True, timeout=3000)

    def assert_service_status(self, service_name: str, expected_status: str):
        text = self._get_service_card_text(service_name)
        if expected_status in text:
            self.logger.info(f"服务状态断言通过: {service_name} 包含状态 {expected_status}")
            return

        services = self.page.evaluate(
            """() => Array.from(document.querySelectorAll('.serve_content .serve_item, .serve_content .serve_item_disable'))
                .map(item => ({
                    name: item.querySelector('.title_text')?.textContent?.trim() || '',
                    text: item.innerText.replace(/\\s+/g, ' ').trim()
                }))"""
        )
        raise AssertionError(
            f"服务状态断言失败，服务: {service_name}，期望状态: {expected_status}，实际服务卡片: {services}"
        )

    @submenu("实例")
    def is_service_installed(self, name: str, service_name: str):
        self.ensure_detail_tab(name, "集群服务")
        return self._has_service_card(service_name)

    def wait_service_status(self, service_name: str, expected_status: str, timeout: int = 1800):
        for _ in range(max(1, timeout // 10)):
            self.page.reload()
            self._ensure_cluster_service_tab_active()
            self._wait_service_cards_loaded()
            text = self._get_service_card_text(service_name)
            if expected_status in text:
                self.logger.info(f"服务状态等待通过: {service_name} 已变为 {expected_status}")
                return
            sleep(10)
        services = self.page.evaluate(
            """() => Array.from(document.querySelectorAll('.serve_content .serve_item, .serve_content .serve_item_disable'))
                .map(item => ({
                    name: item.querySelector('.title_text')?.textContent?.trim() || '',
                    text: item.innerText.replace(/\\s+/g, ' ').trim()
                }))"""
        )
        raise AssertionError(f"{service_name} 服务未在 {timeout} 秒内变为{expected_status}，当前服务卡片: {services}")

    def wait_service_installing(self, service_name: str, timeout: int = 300):
        for _ in range(max(1, timeout // 5)):
            text = self._get_service_card_text(service_name)
            if "安装中" in text:
                self.logger.info(f"服务状态等待通过: {service_name} 已进入 安装中")
                return
            if "正常" in text:
                self.logger.info(f"服务状态等待通过: {service_name} 已直接变为 正常")
                return
            sleep(5)
        raise AssertionError(f"{service_name} 服务未在 {timeout} 秒内进入安装中或正常状态")

    def wait_service_running(self, service_name: str, timeout: int = 1800):
        self.wait_service_status(service_name, "正常", timeout=timeout)

    def wait_service_absent(self, service_name: str, timeout: int = 300):
        for _ in range(max(1, timeout // 10)):
            self.page.reload()
            self._ensure_cluster_service_tab_active()
            self._wait_service_cards_loaded()
            if not self._has_service_card(service_name):
                self.logger.info(f"服务卸载断言通过: {service_name} 已不存在")
                return
            sleep(10)
        raise AssertionError(f"{service_name} 服务未在 {timeout} 秒内卸载完成")

    @submenu("实例")
    def add_service(self, name: str, service_name: str = "HDFS"):
        self.ensure_detail_tab(name, "集群服务")
        self._wait_service_cards_loaded()
        if self._has_service_card(service_name):
            self.wait_service_running(service_name, timeout=1800)
            return False
        self._active_detail_tab().get_by_text("添加服务", exact=True).click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator(".server-item, .server-item_active").first.wait_for(state="visible", timeout=10000)
        service = dialog.locator(".server-item, .server-item_active").filter(
            has_text=re.compile(re.escape(service_name), re.IGNORECASE)
        ).first
        service.wait_for(state="visible", timeout=10000)
        if "server-item_active" not in (service.get_attribute("class") or ""):
            service.click()
        self.dialog_confirm.click()
        return True

    @submenu("实例")
    def uninstall_service(self, name: str, service_name: str = "Kafka"):
        self.ensure_detail_tab(name, "集群服务")
        if not self._has_service_card(service_name):
            self.logger.info(f"服务 {service_name} 不存在，跳过卸载")
            return False
        tab = self._active_detail_tab()
        tab.get_by_text("卸载服务", exact=True).click()

        service_card = tab.locator(".serve_item, .serve_item_disable").filter(
            has_text=re.compile(re.escape(service_name), re.IGNORECASE)
        ).first
        checkbox = service_card.locator("label.el-checkbox, .el-checkbox").first
        checkbox.wait_for(state="visible", timeout=5000)
        checkbox.click()
        tab.get_by_text("确定", exact=True).click()
        self.dialog_confirm.click()
        return True

    @submenu("实例")
    def operate_all_services(self, name: str, action: str):
        self.ensure_detail_tab(name, "集群服务")
        self._active_detail_tab().get_by_text("更多操作", exact=True).click()
        self.page.locator("body .el-dropdown-menu:visible").last.get_by_text(action, exact=True).click()

    def _node_group_action(self, group_name: str, action: str):
        tab = self._active_detail_tab()
        name_rows = tab.locator(".el-table__fixed .el-table__fixed-body-wrapper tbody tr.el-table__row")
        if name_rows.count() == 0:
            name_rows = tab.locator(".el-table__body-wrapper tbody tr.el-table__row")

        target_index = None
        for i in range(name_rows.count()):
            row = name_rows.nth(i)
            try:
                text = row.inner_text().strip()
            except Exception:
                continue
            if re.search(rf"\b{re.escape(group_name)}\b", text, re.I):
                target_index = i
                break

        if target_index is None:
            raise AssertionError(f"未找到 {group_name} 节点组行")

        action_rows = tab.locator(".el-table__fixed-right .el-table__fixed-body-wrapper tbody tr.el-table__row")
        if action_rows.count() == 0:
            action_rows = tab.locator(".el-table__body-wrapper tbody tr.el-table__row")
        if action_rows.count() <= target_index:
            raise AssertionError(f"未找到 {group_name} 节点组对应的操作列行，目标索引: {target_index}")

        action_button = action_rows.nth(target_index).get_by_text(action, exact=True).first
        action_button.click()

    @submenu("实例")
    def change_specification(self, name: str):
        self.ensure_detail_tab(name, "节点管理")
        self._node_group_action("WEB", "修改规格")
        specification_name = "emr.d6 emr.d6.2xlarge 8核"
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例")
    def expand_disk(self, name: str, size: int = 70):
        self.ensure_detail_tab(name, "节点管理")
        self._node_group_action("WEB", "磁盘扩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator("input[role='spinbutton']").first.fill(str(size))
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例")
    def add_node(self, name: str, password: str = "Admin1234@sugon"):
        self.ensure_detail_tab(name, "节点管理")
        self._node_group_action("COMMON", "扩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        if dialog.locator("input[type='password']").count() >= 2:
            dialog.locator("input[type='password']").nth(0).fill(password)
            dialog.locator("input[type='password']").nth(1).fill(password)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例")
    def delete_node(self, name: str):
        self.ensure_detail_tab(name, "节点管理")
        self._node_group_action("COMMON", "缩容")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.locator("input[role='spinbutton']").first.fill("1")
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例")
    def node_ip_binding(self, name: str, network: str):
        self._ensure_common_node_visible(name)
        self.click_action(self.common_node_name, "绑定公网IP")
        dialog = self.page.locator("div.el-dialog:visible").last
        self._select_public_network_in_dialog(dialog, network)
        ip = self._select_available_public_ip(dialog)
        dialog.get_by_text("确定", exact=True).click()
        return ip

    @submenu("实例")
    def node_ip_unbinding(self, name: str):
        self._ensure_common_node_visible(name)
        self.click_action(self.common_node_name, "解绑公网IP")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.wait_for(state="visible", timeout=5000)
        self._wait_unbind_public_ip_ready(dialog)
        dialog.get_by_text("确定", exact=True).click()
