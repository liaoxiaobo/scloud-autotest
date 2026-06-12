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
        er_name: str = "",
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
            er_name: 关联的企业路由器名称，连接类型为"企业路由器"时使用。
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
        is_high_edition = False
        if vpn_type == "SSL" and resource_pool_tag:
            with allure_step_log("选择资源池标签"):
                try:
                    self._select_radio_by_label("资源池标签", resource_pool_tag)
                    is_high_edition = resource_pool_tag == "高级版"
                except Exception:
                    self.logger.info("资源池标签选择可能不存在或已自动填充")

        # 定义IP选择的内部辅助逻辑
        def _select_ip_from_dropdown(ip_addr):
            """使用 JS 直接操作 DOM 和 Vue 组件来选择 IP 地址。

            绕过 Playwright 的 CustomLocator 包装和复杂的 UI 交互。
            """
            result = self.page.evaluate(
                '''(ipAddr) => {
                    return new Promise((resolve) => {
                        // 1. 找到 IP 地址表单项
                        const items = document.querySelectorAll('.el-form-item');
                        let ipItem = null;
                        for (const item of items) {
                            const label = item.querySelector('.el-form-item__label');
                            if (label) {
                                const text = label.textContent.trim().replace('*', '').trim();
                                if (text === 'IP地址') {
                                    ipItem = item;
                                    break;
                                }
                            }
                        }
                        if (!ipItem) {
                            resolve({ error: 'IP地址表单项未找到' });
                            return;
                        }

                        // 2. 尝试通过 Vue 实例打开下拉框
                        const selectEl = ipItem.querySelector('.el-select');
                        let opened = false;
                        if (selectEl && selectEl.__vue__) {
                            try {
                                selectEl.__vue__.toggleMenu();
                                opened = true;
                            } catch (e) {}
                        }

                        // 3. 如果 Vue 方法失败，使用 DOM click
                        if (!opened) {
                            const input = ipItem.querySelector('.el-input__inner');
                            if (input) {
                                input.scrollIntoView({ behavior: 'instant', block: 'center' });
                                input.focus();
                                input.click();
                                opened = true;
                            }
                        }

                        if (!opened) {
                            resolve({ error: '无法打开IP下拉框' });
                            return;
                        }

                        // 4. 等待选项加载
                        setTimeout(() => {
                            const options = document.querySelectorAll('.el-select-dropdown__item');
                            const texts = Array.from(options).map(o => o.textContent.trim());

                            if (options.length === 0) {
                                resolve({ error: '下拉框无选项', opened: true });
                                return;
                            }

                            // 5. 查找匹配的选项，否则选择第一个
                            let targetIdx = 0;
                            for (let i = 0; i < options.length; i++) {
                                if (options[i].textContent.includes(ipAddr)) {
                                    targetIdx = i;
                                    break;
                                }
                            }

                            // 6. 点击选项
                            options[targetIdx].click();

                            // 7. 等待选择生效
                            setTimeout(() => {
                                const input = ipItem.querySelector('.el-input__inner');
                                resolve({
                                    success: true,
                                    selected: input ? input.value : 'unknown',
                                    texts: texts,
                                    targetIdx: targetIdx
                                });
                            }, 500);
                        }, 1500);
                    });
                }''',
                ip_addr,
            )
            self.logger.info(f"JS IP选择结果: {result}")
            if isinstance(result, dict) and result.get("error"):
                raise AssertionError(f"IP地址选择失败: {result['error']}")
            if isinstance(result, dict) and not result.get("success"):
                raise AssertionError(f"IP地址选择未成功: {result}")

        if not is_high_edition:
            with allure_step_log("选择资源池"):
                self._click_dropdown_by_label("资源池", resource_pool)
                # 资源池选择后异步加载IP列表，需充分等待
                self.page.wait_for_timeout(5000)

            with allure_step_log("选择IP地址"):
                if fip_address:
                    try:
                        _select_ip_from_dropdown(fip_address)
                    except Exception as e:
                        self.logger.warning(f"IP地址选择失败: {e}")

        # SSL类型特有字段：客户端网段
        if vpn_type == "SSL" and client_subnet:
            with allure_step_log("填写客户端网段"):
                try:
                    form_item = ctx.locator(".el-form-item").filter(has_text="客户端网段").first
                    subnet_input = form_item.locator("input").first
                    subnet_input.fill(client_subnet)
                except Exception:
                    self.logger.info("客户端网段输入框未找到，可能不需要")

        with allure_step_log(f"选择连接类型: {connection_type}"):
            self._select_connection_type(connection_type)

        # 连接类型切换后表单可能重新渲染，刷新上下文
        ctx = self._get_form_context()
        self.page.wait_for_timeout(1500)

        # 连接类型切换后IP地址会被重置，需要重新选择（仅基础版）
        if not is_high_edition and fip_address:
            with allure_step_log("重新选择IP地址"):
                try:
                    _select_ip_from_dropdown(fip_address)
                except Exception as e:
                    self.logger.warning(f"IP地址重新选择失败: {e}")

        # 连接类型切换后客户端网段可能被重置，重新填充
        if vpn_type == "SSL" and client_subnet:
            with allure_step_log("重新填写客户端网段"):
                try:
                    form_item = ctx.locator(".el-form-item").filter(has_text="客户端网段").first
                    subnet_input = form_item.locator("input").first
                    subnet_input.fill(client_subnet)
                except Exception:
                    self.logger.info("客户端网段重新输入框未找到，可能不需要")

        if vpc_name and connection_type == "虚拟私有云":
            with allure_step_log("选择虚拟私有云"):
                try:
                    vpc_select = ctx.get_by_placeholder("请选择虚拟私有云").first
                    vpc_select.click()
                    self.page.wait_for_timeout(500)
                    dropdown = self.page.locator(".el-select-dropdown:visible")
                    expect(dropdown).to_be_visible(timeout=10000)
                    options = dropdown.locator(".el-select-dropdown__item")
                    expect(options.first).to_be_visible(timeout=10000)
                    dropdown.get_by_text(vpc_name, exact=False).first.click()
                    self.page.wait_for_timeout(500)
                except Exception as e:
                    self.logger.info(f"VPC选择失败: {e}")

        if er_name and connection_type == "企业路由器":
            with allure_step_log("选择企业路由器"):
                try:
                    self.page.wait_for_timeout(2000)
                    er_form_item = None
                    all_form_items = self.page.locator(".el-form-item")
                    for i in range(all_form_items.count()):
                        item = all_form_items.nth(i)
                        try:
                            label_elem = item.locator(".el-form-item__label").first
                            if label_elem.count() > 0:
                                label_text = label_elem.inner_text(timeout=2000).strip().lstrip("*").strip()
                                if label_text == "企业路由器":
                                    er_form_item = item
                                    break
                        except Exception:
                            continue
                    if er_form_item is None:
                        raise AssertionError("未找到标签为'企业路由器'的表单项")
                    expect(er_form_item).to_be_visible(timeout=10000)
                    er_select = er_form_item.locator(".el-select").first
                    er_select.evaluate("el => el.scrollIntoView({behavior: 'instant', block: 'center'})")
                    self.page.wait_for_timeout(500)
                    try:
                        er_select.click()
                    except Exception:
                        er_select.evaluate(
                            "el => el.dispatchEvent(new MouseEvent('click',"
                            " { bubbles: true, cancelable: true }))"
                        )
                    self.page.wait_for_timeout(500)
                    dropdown = self.page.locator(".el-select-dropdown:visible")
                    expect(dropdown).to_be_visible(timeout=10000)
                    options = dropdown.locator(".el-select-dropdown__item")
                    for _ in range(30):
                        if options.count() > 0:
                            break
                        self.page.wait_for_timeout(500)
                    expect(options.first).to_be_visible(timeout=10000)
                    target_option = None
                    for i in range(options.count()):
                        opt = options.nth(i)
                        opt_text = opt.inner_text()
                        if er_name in opt_text:
                            target_option = opt
                            break
                    if target_option is None:
                        raise AssertionError(
                            f"ER下拉选项中未找到 '{er_name}'")
                    target_option.evaluate(
                        "el => el.dispatchEvent(new MouseEvent('click',"
                        " { bubbles: true, cancelable: true }))"
                    )
                    self.page.wait_for_timeout(500)
                    if dropdown.count() > 0:
                        target_option.click()
                    try:
                        expect(dropdown).to_have_count(0, timeout=5000)
                    except Exception:
                        pass
                    self.page.wait_for_timeout(2000)
                    er_input = er_form_item.locator(
                        ".el-select .el-input__inner").first
                    input_value = er_input.input_value()
                    if er_name not in input_value:
                        self.logger.warning(
                            f"ER选择后验证失败: 期望包含 '{er_name}',"
                            f" 实际值: '{input_value}'")
                        try:
                            self.page.get_by_text(
                                er_name, exact=False).first.click()
                            self.page.wait_for_timeout(2000)
                        except Exception as retry_err:
                            self.logger.warning(f"ER重选失败: {retry_err}")
                    else:
                        self.logger.info(f"ER选择验证通过: '{input_value}'")
                except Exception as e:
                    self.logger.warning(f"企业路由器选择失败: {e}")

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
            # 使用 dialog_confirm 定位弹窗内的确定按钮，避免点到页面其他"确定"
            self.dialog_confirm.click()
            self.page.wait_for_timeout(1000)

    def open_vpn_gateway_detail(self, name: str):
        """点击VPN网关名称，进入详情页。

        Args:
            name: VPN网关名称。
        """
        with allure_step_log(f"点击VPN网关名称 '{name}' 进入详情页"):
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)
            # 先定位到目标行，滚动到可视区域后再点击名称链接
            row = self.get_row_by_name(name)
            row.scroll_into_view_if_needed()
            # 名称列渲染为 <a><span>name</span></a>，但 <span>/<a> 都可能因表格
            # overflow 被 Playwright 判定为不可见，故统一用 JS 点击触发导航
            name_link = row.locator("a").filter(has_text=name).first
            if name_link.count() > 0:
                name_link.evaluate("el => el.click()")
            else:
                row.get_by_text(name, exact=True).first.evaluate("el => el.click()")
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

                    function normalizeText(text) {{
                        return text.replace(/\\s+/g, ' ').trim();
                    }}

                    // 遍历所有文本节点
                    const walker = document.createTreeWalker(
                        document.querySelector("#cloud-container-content") || document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    let node;
                    while (node = walker.nextNode()) {{
                        if (normalizeText(node.textContent) === label) {{
                            const parent = node.parentElement;
                            const container = parent.closest(".el-descriptions__cell, .info-item, .detail-item, [class*='detail'], [class*='info'], [class*='descriptions'], .el-form-item, .el-row") || parent.parentElement;
                            const texts = Array.from(container.querySelectorAll("*")).map(el => el.innerText.trim()).filter(t => t && normalizeText(t) !== label);
                            // 去重并保持顺序
                            const unique = [];
                            for (const t of texts) {{
                                const nt = normalizeText(t);
                                if (nt && !unique.includes(nt) && nt !== label) unique.push(nt);
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
