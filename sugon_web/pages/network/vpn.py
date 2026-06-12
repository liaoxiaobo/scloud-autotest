"""虚拟专用网络VPN页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log


class VpnMixin(BasePage):
    """虚拟专用网络VPN模块页面对象，封装VPN网关等页面的交互操作。"""

    service_name = "专有网络VPN"

    def _ensure_vpn_gateway_list(self):
        """确保当前位于VPN网关列表页。"""
        self.goto_service(self.service_name)
        try:
            self.goto_submenu("VPN网关")
        except Exception:
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/vpn-gateway-list")
            self.wait_for_page_ready()
        self.wait_for_page_ready()

        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass

    def _get_form_context(self):
        """获取表单定位上下文。"""
        # 尝试多种可能的表单容器选择器
        selectors = [".el-form", ".add-box", ".form-box", ".create-box", ".content-box .form"]
        for selector in selectors:
            elem = self.page.locator(selector).first
            if elem.count() > 0 and elem.is_visible():
                return elem
        return self.page.locator("body")

    def _click_dropdown_by_label(self, label: str, option_text: str):
        """通过标签文本定位下拉框并选择选项。

        Args:
            label: 表单标签文本，如"集群"、"类型"。
            option_text: 要选择的选项文本。
        """
        ctx = self._get_form_context()
        # 找到包含该标签的表单项（精确匹配标签文本，避免子串误匹配）
        form_items = ctx.locator(".el-form-item")
        target_item = None
        for i in range(form_items.count()):
            item = form_items.nth(i)
            try:
                # 获取标签文本（通常是 .el-form-item__label 的内容）
                label_elem = item.locator(".el-form-item__label").first
                if label_elem.count() > 0:
                    label_text = label_elem.inner_text(timeout=2000).strip().lstrip("*").strip()
                    if label_text == label:
                        target_item = item
                        break
                # fallback: 检查整个表单项文本
                item_text = item.inner_text(timeout=2000)
                # 要求标签文本在行首或紧跟在 * 后面
                lines = item_text.split("\n")
                for line in lines:
                    clean_line = line.strip().lstrip("*").strip()
                    if clean_line == label:
                        target_item = item
                        break
                if target_item:
                    break
            except Exception:
                continue
        if target_item is None:
            raise AssertionError(f"未找到标签为 '{label}' 的表单项")
        # 点击该表单项内的下拉框触发器（el-select 的 input）
        dropdown_trigger = target_item.locator(".el-select .el-input__inner").first
        if dropdown_trigger.count() == 0:
            dropdown_trigger = target_item.locator(".el-select").first
        dropdown_trigger.click()
        self.page.wait_for_timeout(500)

        dropdown = self.page.locator(".el-select-dropdown:visible")
        expect(dropdown).to_be_visible(timeout=10000)

        options = dropdown.locator(".el-select-dropdown__item")
        expect(options.first).to_be_visible(timeout=10000)

        # 尝试精确匹配，失败则尝试子串匹配
        try:
            dropdown.get_by_text(option_text, exact=True).first.click()
        except Exception:
            # 尝试用更短的子串匹配
            short_text = option_text.split("(")[0] if "(" in option_text else option_text
            dropdown.get_by_text(short_text, exact=False).first.click()
        self.page.wait_for_timeout(500)

    def _select_radio_by_label(self, label: str, option_text: str):
        """通过标签文本定位单选按钮组并选择选项。

        Args:
            label: 表单标签文本。
            option_text: 要选择的选项文本。
        """
        ctx = self._get_form_context()
        # 从标签开始向上/横向查找radio组
        label_elem = ctx.get_by_text(label, exact=True).first
        # 找到同级的radio组或在同一form-item内的radio组
        parent = label_elem.locator("xpath=../..")
        radio_group = parent.locator(".el-radio-group").first
        if radio_group.count() == 0:
            # 尝试从labelElem的父元素查找
            parent = label_elem.locator("..")
            radio_group = parent.locator(".el-radio-group").first
        radio_group.get_by_text(option_text, exact=True).first.click()
        self.page.wait_for_timeout(500)

    def _select_type(self, vpn_type: str):
        """选择VPN网关类型（SSL/IPSEC）。

        Args:
            vpn_type: VPN类型，"SSL"或"IPSEC"。
        """
        with allure_step_log(f"选择VPN网关类型: {vpn_type}"):
            try:
                self._click_dropdown_by_label("类型", vpn_type)
                return
            except Exception:
                pass

            # fallback: 尝试radio
            ctx = self._get_form_context()
            try:
                radio_group = ctx.locator(".el-radio-group").first
                if radio_group.count() > 0 and radio_group.is_visible():
                    radio_group.get_by_text(vpn_type, exact=True).first.click()
                    self.page.wait_for_timeout(500)
                    return
            except Exception:
                pass

            # 兜底
            ctx.get_by_text(vpn_type, exact=True).first.click()
            self.page.wait_for_timeout(500)

    def _select_connection_type(self, connection_type: str):
        """选择连接类型（虚拟私有云/企业路由器）。

        Args:
            connection_type: 连接类型文本，如"虚拟私有云"。
        """
        with allure_step_log(f"选择连接类型: {connection_type}"):
            try:
                self._select_radio_by_label("连接类型", connection_type)
                return
            except Exception:
                pass

            # fallback
            ctx = self._get_form_context()
            try:
                radio_group = ctx.locator(".el-radio-group").nth(1)
                if radio_group.count() > 0 and radio_group.is_visible():
                    radio_group.get_by_text(connection_type, exact=True).click()
                    self.page.wait_for_timeout(500)
                    return
            except Exception:
                pass

            ctx.get_by_text(connection_type, exact=True).first.click()
            self.page.wait_for_timeout(500)

    def vpn_gateway_create(
        self,
        name: str,
        cluster: str = "Autotest",
        vpn_type: str = "SSL",
        resource_pool: str = "公有网络public_net(基础版)",
        fip_address: str = "",
        connection_type: str = "虚拟私有云",
        vpc_name: str = "",
        flavor: str = "虚拟专用网络数据型",
        resource_pool_tag: str = "",
        client_subnet: str = "",
    ):
        """创建VPN网关。

        Args:
            name: VPN网关名称。
            cluster: 集群名称，默认"Autotest"。
            vpn_type: VPN类型，"SSL"或"IPSEC"。
            resource_pool: 资源池名称，默认"公有网络public_net(基础版)"。
            fip_address: 绑定的弹性公网IP地址。
            connection_type: 连接类型，默认"虚拟私有云"。
            vpc_name: 关联的虚拟私有云名称。
            flavor: 规格，默认"虚拟专用网络数据型"。
            resource_pool_tag: 资源池标签，仅SSL类型时需要，如"基础版"。
            client_subnet: 客户端网段，仅SSL类型时需要，如"17.17.17.0/24"。
        """
        with allure_step_log("进入VPN网关列表页并打开新建页面"):
            self._ensure_vpn_gateway_list()
            self.page.wait_for_timeout(1000)
            # 点击"新建"按钮，限定在内容区域避免匹配到其他菜单中的"新建"
            content = self.page.locator("#cloud-container-content").first
            content.get_by_text("新建", exact=True).first.click()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(2000)

        ctx = self._get_form_context()

        with allure_step_log("填写VPN网关名称"):
            name_input = ctx.get_by_placeholder("请输入名称").first
            name_input.fill(name)

        with allure_step_log("选择集群"):
            try:
                self._click_dropdown_by_label("集群", cluster)
            except Exception:
                # 集群可能不是下拉选择，或者是自动填充的
                self.logger.info("集群选择可能已自动填充或无需手动选择")

        with allure_step_log(f"选择VPN类型: {vpn_type}"):
            self._select_type(vpn_type)

        # SSL类型特有字段
        if vpn_type == "SSL" and resource_pool_tag:
            with allure_step_log("选择资源池标签"):
                try:
                    self._select_radio_by_label("资源池标签", resource_pool_tag)
                except Exception:
                    self.logger.info("资源池标签选择可能不存在或已自动填充")

        with allure_step_log("选择资源池"):
            self._click_dropdown_by_label("资源池", resource_pool)

        with allure_step_log("选择IP地址"):
            if fip_address:
                try:
                    self._click_dropdown_by_label("IP地址", fip_address)
                except Exception:
                    self.logger.info("IP地址选择可能不存在或已自动填充")

        # SSL类型特有字段：客户端网段
        if vpn_type == "SSL" and client_subnet:
            with allure_step_log("填写客户端网段"):
                try:
                    # 通过标签定位客户端网段输入框
                    form_item = ctx.locator(".el-form-item").filter(has_text="客户端网段").first
                    subnet_input = form_item.locator("input").first
                    subnet_input.fill(client_subnet)
                except Exception:
                    self.logger.info("客户端网段输入框未找到，可能不需要")

        with allure_step_log(f"选择连接类型: {connection_type}"):
            self._select_connection_type(connection_type)

        if vpc_name and connection_type == "虚拟私有云":
            with allure_step_log("选择虚拟私有云"):
                try:
                    # 直接通过placeholder找到VPC下拉框
                    vpc_select = ctx.get_by_placeholder("请选择虚拟私有云").first
                    vpc_select.click()
                    self.page.wait_for_timeout(500)
                    dropdown = self.page.locator(".el-select-dropdown:visible")
                    expect(dropdown).to_be_visible(timeout=10000)
                    options = dropdown.locator(".el-select-dropdown__item")
                    expect(options.first).to_be_visible(timeout=10000)
                    # 使用前缀匹配查找VPC名称
                    dropdown.get_by_text(vpc_name, exact=False).first.click()
                    self.page.wait_for_timeout(500)
                except Exception as e:
                    self.logger.info(f"VPC选择失败: {e}")

        with allure_step_log("选择规格"):
            try:
                # 规格在表格中通过radio按钮选择，找到包含规格名称的行并点击其radio
                table = ctx.locator(".el-table").first
                rows = table.locator(".el-table__row")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    row_text = row.inner_text()
                    if flavor in row_text:
                        radio = row.locator(".el-radio__input, .el-radio").first
                        radio.click()
                        self.page.wait_for_timeout(500)
                        break
                else:
                    # 兜底：直接点击文本
                    ctx.get_by_text(flavor, exact=False).first.click()
                    self.page.wait_for_timeout(500)
            except Exception:
                self.logger.info("规格选择可能已自动填充")

        with allure_step_log("点击立即创建按钮"):
            # 滚动到底部确保按钮在视口内
            self.page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(500)
            # 使用 get_by_text 定位按钮并点击
            self.page.get_by_text("立即创建", exact=True).first.click()
            self.page.wait_for_timeout(2000)

    def vpn_gateway_delete(self, name: str):
        """删除指定VPN网关。

        Args:
            name: 需要删除的VPN网关名称。
        """
        with allure_step_log(f"删除VPN网关 '{name}'"):
            self.click_action(name, "删除")

        with allure_step_log("确认删除"):
            # 尝试多种对话框选择器
            dialog_selectors = [
                ".el-dialog__wrapper:visible",
                ".sugon-dialog:visible",
                ".el-dialog:visible",
                ".el-dialog__wrapper",
                ".sugon-dialog",
            ]
            dialog = None
            for sel in dialog_selectors:
                dialog = self.page.locator(sel).first
                if dialog.count() > 0 and dialog.is_visible():
                    break
            if dialog is None or dialog.count() == 0:
                # 兜底：直接找包含"确定"的可见按钮
                pass
            else:
                expect(dialog).to_be_visible(timeout=10000)
            # 点击确定按钮
            self.page.get_by_text("确定", exact=True).first.click()
            self.page.wait_for_timeout(1000)

    def open_vpn_gateway_detail(self, name: str):
        """点击VPN网关名称，进入详情页。

        Args:
            name: VPN网关名称。
        """
        with allure_step_log(f"点击VPN网关名称 '{name}' 进入详情页"):
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)
            # 先定位到目标行，再在行内点击名称，避免匹配到页面其他区域的同名文本
            row = self.get_row_by_name(name)
            name_elem = row.get_by_text(name, exact=True).first
            try:
                name_elem.click()
            except Exception:
                # 兜底：使用JS点击绕过可见性检查
                name_elem.evaluate("el => el.click()")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(2000)

    def get_vpn_gateway_detail_field(self, label: str) -> str:
        """从详情页获取指定标签对应的字段值。

        Args:
            label: 字段标签，如"名称"、"类型"、"集群"等。

        Returns:
            str: 字段值文本。
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)

        content = self.page.locator("#cloud-container-content").first
        expect(content).to_be_visible(timeout=10000)

        # 策略1: 使用JS遍历DOM，找到label文本节点后取父容器内的相邻文本
        try:
            result = self.page.evaluate(f'''
                () => {{
                    const label = "{label}";
                    const knownLabels = ["名称","ID","类型","集群","运行状态","状态","创建时间",
                        "网络类型","客户端连接数","客户端网段","公网IP地址","已创建",
                        "实例信息","专有网络","基本配置","详情","VPN网关"];

                    // 遍历所有文本节点
                    const walker = document.createTreeWalker(
                        document.querySelector("#cloud-container-content") || document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    let node;
                    while (node = walker.nextNode()) {{
                        if (node.textContent.trim() === label) {{
                            const parent = node.parentElement;
                            const container = parent.closest(".el-descriptions__cell, .info-item, .detail-item, [class*='detail'], [class*='info'], [class*='descriptions']") || parent.parentElement;
                            const texts = Array.from(container.querySelectorAll("*")).map(el => el.innerText.trim()).filter(t => t && t !== label);
                            // 去重并保持顺序
                            const unique = [];
                            for (const t of texts) {{
                                if (!unique.includes(t) && t !== label) unique.push(t);
                            }}
                            if (unique.length > 0) {{
                                // 过滤掉已知label
                                const val = unique.find(t => !knownLabels.includes(t));
                                if (val) return val;
                                return unique[0];
                            }}
                        }}
                    }}
                    return null;
                }}
            ''')
            if result:
                return result
        except Exception:
            pass

        # 策略2: 按行文本顺序匹配
        try:
            all_text = content.inner_text()
            lines = [l.strip() for l in all_text.split("\n") if l.strip()]
            known_labels = ["名称", "ID", "类型", "集群", "运行状态", "状态", "创建时间",
                           "网络类型", "客户端连接数", "客户端网段", "公网IP地址", "已创建",
                           "实例信息", "专有网络", "基本配置", "详情", "VPN网关"]
            for i, line in enumerate(lines):
                if line == label and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if next_line not in known_labels:
                        return next_line
        except Exception:
            pass

        # 策略3: 按section分组匹配（label和value可能在相邻行）
        try:
            all_text = content.inner_text()
            lines = [l.strip() for l in all_text.split("\n") if l.strip()]
            known_labels = ["名称", "ID", "类型", "集群", "运行状态", "状态", "创建时间",
                           "网络类型", "客户端连接数", "客户端网段", "公网IP地址", "已创建",
                           "实例信息", "专有网络", "基本配置", "详情", "VPN网关"]
            # 在 "实例信息" section 内查找
            in_section = False
            for i, line in enumerate(lines):
                if line == "实例信息":
                    in_section = True
                    continue
                if line in ["专有网络", "基本配置"]:
                    in_section = False
                    continue
                if in_section and line == label and i + 1 < len(lines):
                    val = lines[i + 1]
                    if val not in known_labels:
                        return val
        except Exception:
            pass

        raise AssertionError(f"详情页中未找到字段: {label}")
