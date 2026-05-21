import random
import re
import time

from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config
from sugon_web.utils.util import random_data
from sugon_web.common.playwright import expect


class SlbMixin(BasePage):
    """
    负载均衡页面
    """

    def _get_slb_basic_settings_form(self):
        """获取创建负载均衡页面中的“基础设置”表单区域。"""
        return self.locator("form").filter(has_text=re.compile(r"基础设置")).first

    @submenu("负载均衡（基础版）")
    def slb_create(self, name=None, version="V2", cluster=None, vpc=None,
                   ip_type="自动分配", ip_address=None, spec=None, desc=None,
                   ha_enable=False):
        """创建负载均衡

        Args:
            name: 负载均衡名称，可以为None，将会自动生成随机名称
            version: 版本类型，"V1" 或 "V2"，默认"V2"
            cluster: 集群名称，V2版本适用
            vpc: 虚拟私有云(VPC)名称
            ip_type: IP分配方式，"自动分配"、"快速选择" 或 "手动输入"
            ip_address: 当ip_type为"快速选择"或"手动输入"时的IP地址，此时为必填项
            spec: 规格设置，V2版本适用 (例如: "slb.d6.large 2核 4GiB 内网带宽")
            desc: 描述信息
            ha_enable: 是否启用HA开关 (True=开启, False=不开启)
        """
        self.btn_create.click()

        # 填写名称
        if not name:
            name = f"slb-{random_data()}"
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").click()
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        # 选择版本类型
        self.get_by_role("radio", name=version).click()

        # HA开关设置（对V1和V2通用）
        deploy_mode = Config.get("deploy_mode")
        if deploy_mode == "stack" and ha_enable:
            ha_switch = self._get_slb_basic_settings_form().get_by_role("switch").first
            if ha_switch.count() > 0 and ha_switch.is_visible():
                is_checked = ha_switch.get_attribute("aria-checked") == "true"
                if is_checked != ha_enable:
                    ha_switch.locator("span").click()
        else:
            self.logger.info(f"当前 deploy_mode={deploy_mode}，创建页不展示 HA 开关")

        # 只有在V2时才需要选择集群和规格
        if version == "V2":
            # 集群选择
            if cluster:
                cluster_form_item = self._get_slb_basic_settings_form().locator("div.el-form-item").filter(has_text=re.compile(r"集群"))
                cluster_form_item.get_by_placeholder("请选择").click()
                self.locator("li").filter(has_text=re.compile(rf"^{re.escape(cluster)}$")).click()

        # 网络配置 - VPC
        if vpc:
            if version == "V1":
                self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            else:
                self.locator("form div").filter(has_text="网络配置 子网网络 子网 IPv4 IPv6").get_by_placeholder(
                    "请选择").click()
            # 使用包含名称的项
            self.get_by_text(vpc).first.click()

        # 网络配置 - IP分配方式
        if ip_type == "自动分配":
            self.locator("label").filter(has_text="自动分配").click()
        elif ip_type in ["快速选择", "手动输入"]:
            # 当IP分配方式为手动分配的时候才能快速选择或手动输入ip，且ip是必填
            if not ip_address:
                raise ValueError("在IPv4分配方式为手动分配且选择快速选择或手动输入时，IP是必填项")

            # 先点击"手动分配"
            self.locator("label").filter(has_text="手动分配").click()
            # 在 IPv4 分配方式为手动分配的时候，选择具体的子选项并填入 IP
            self.locator("label").filter(has_text=ip_type).click()

            # 锚定包含 "快速选择/手动输入" 单选按钮的表单项容器
            container = self.locator("div.el-form-item__content").filter(has=self.get_by_role("radio", name="快速选择"))

            if ip_type == "快速选择":
                # 点击该容器内的下拉框。
                container.get_by_placeholder("请选择").click()
                self.get_by_text(ip_address, exact=True).click()
            elif ip_type == "手动输入":
                # 同理填入手动输入框
                container.get_by_placeholder("请输入", exact=True).click()
                container.get_by_placeholder("请输入", exact=True).fill(ip_address)

        # 规格设置 - 只有在V2才需要选择
        if version == "V2" and spec:
            self.get_by_role("row", name=spec).get_by_role("radio").click()

        # 描述
        if desc:
            self.locator("textarea").click()
            self.locator("textarea").fill(desc)

        # 提交
        self.btn_submit.click()

        self.logger.info(f"负载均衡创建完成: {name} ({version})")
        return name

    def _slb_lb_set_basic_config(self, lb_name, protocol, port=None, desc=None,
                                  acl_enable=False, access_policy=None, ip_group=None,
                                  auth_mode="单向认证", cert_type="国际服务器证书",
                                  server_cert=None, ca_cert=None,
                                  http_redirect=False, redirect_port=None):
        """步骤1: 基础配置"""
        # 监听器名称
        self.locator("div").filter(has_text=re.compile(r"^监听器名称$")).get_by_role("textbox").fill(lb_name)

        # 描述
        if desc:
            self.locator("textarea").fill(desc)

        # 协议
        self.get_by_label("新建监听器").get_by_role("textbox", name="请选择").click()
        self.get_by_text(protocol, exact=True).last.click() # 使用last以应对可能重复项

        # 端口
        if port:
            # 这里的 spinbutton 可能是第一个
            self.get_by_role("spinbutton").first.fill(str(port))

        # HTTPS 联动字段
        if protocol == "HTTPS":
            # 认证方式 (单向/双向)
            self.locator("label").filter(has_text=auth_mode).click()

            # 服务器证书类型选择
            # 默认两个都勾选。根据 cert_types 调整勾选状态。
            cert_types = [cert_type] if isinstance(cert_type, str) else cert_type
            for ct in ["国际服务器证书", "国密服务器证书"]:
                checkbox_label = self.get_by_label("checkbox-group").locator("label").filter(has_text=ct)
                # 检查当前是否勾选 (el-checkbox 勾选状态在父级 label 的 class 中体现)
                is_checked = "is-checked" in (checkbox_label.get_attribute("class") or "")
                should_be_checked = ct in cert_types
                if is_checked != should_be_checked:
                    checkbox_label.locator("span").nth(1).click()

            # 选择证书 (只有勾选了对应类型才进行选择)
            if server_cert:
                # server_cert 可以是一个字符串（默认国际）或者字典 {"国际": "...", "国密": "..."}
                certs_data = {"国际": server_cert} if isinstance(server_cert, str) else server_cert
                for ct_key, cert_name in certs_data.items():
                    full_ct_name = f"{ct_key}服务器证书"
                    if full_ct_name in cert_types:
                        # 使用 label 关联定位下拉框
                        self.locator("div.el-form-item").filter(has_text=full_ct_name).get_by_placeholder("请选择").click()
                        self.locator("li").filter(has_text=cert_name).click()

            # 双向认证下的 CA 证书
            if auth_mode == "双向认证" and ca_cert:
                # 使用 label 关联定位
                self.locator("div.el-form-item").filter(has_text="CA证书").get_by_placeholder("请选择").click()
                self.get_by_text(ca_cert).last.click()

            # HTTP 端口重定向
            if http_redirect:
                self.locator("div").filter(has_text=re.compile(r"^HTTP端口重定向$")).locator("span").click()
                if redirect_port:
                    # 重定向端口通常是第二个 spinbutton，在表单项内定位更准确
                    self.locator("div.el-form-item").filter(has_text="HTTP端口重定向").get_by_role("spinbutton").fill(str(redirect_port))

        # 访问控制
        acl_switch = self.locator("div.el-form-item").filter(has_text="启用访问控制").get_by_role("switch")
        is_checked = acl_switch.get_attribute("aria-checked") == "true"
        if is_checked != acl_enable:
            acl_switch.locator("span").click()

        if acl_enable:
            acl_dialog = self._find_element([
                self.get_by_role("dialog", name="新建监听器"),
                self.get_by_role("dialog").filter(has_text="新建监听器"),
            ], "新建监听器对话框", timeout=3000)
            if access_policy:
                # 选择策略类型 (针对黑白名单)
                access_policy_select = acl_dialog.locator("div.el-form-item:has(label[for='acl_type'])").get_by_placeholder("请选择")
                expect(access_policy_select).to_be_visible(timeout=3000)
                access_policy_select.click()
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(access_policy)}$")).click()

            # 选择IP地址组
            if ip_group:
                ip_group_select = acl_dialog.locator("div.el-form-item:has(label[for='ip_group_uuid'])").get_by_placeholder("请选择")
                expect(ip_group_select).to_be_visible(timeout=3000)
                ip_group_select.click()
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(ip_group)}$")).click()

        self.get_by_text("下一步").click()

    def _slb_lb_set_listener_config(self, pool_name, balance_method, health_check,
                                    session_persistence=False, session_type=None,
                                    health_type=None, health_max_retries=None,
                                    health_timeout=None, health_interval=None,
                                    http_method=None, url_path=None,
                                    health_request=None, health_expected_response=None):
        """步骤2: 监听器配置 (资源池)"""
        form_items = self.locator("div.el-form-item")

        def form_item_by_text(text):
            return form_items.filter(has_text=text)

        def form_item_by_label(label_for):
            return form_items.filter(has=self.locator(f'label[for*="{label_for}"]'))

        if not pool_name:
            pool_name = f"pool-{random_data()}"

        # 资源池名称
        self.locator("div").filter(has_text=re.compile(r"^资源池名称$")).get_by_role("textbox").fill(pool_name)

        # 均衡算法
        self.get_by_label("新建监听器").get_by_role("textbox", name="请选择").click()
        self.locator("li").filter(has_text=re.compile(fr"^{balance_method}$")).click()

        # 会话保持激活状态 (源IP算法下不设置)
        if balance_method != "源IP":
            form_item_by_text("会话保持").get_by_role("radio", name="激活" if session_persistence else "禁用").click()
            if session_persistence:
                if not session_type:
                    raise ValueError("会话保持激活时，必须提供 session_type (例如: 'SOURCE IP' 或 'HTTP_COOKIE')")
                # 当激活会话保持时，选择类型 (使用 label[for] 区别)
                form_item_by_label("session_persistence_type").get_by_placeholder("请选择").click()
                # 仅在可见的下拉弹窗中进行精确匹配选择
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(session_type)}$")).click()

        # 健康检查激活状态 (始终存在)
        form_item_by_text("健康检查").get_by_role("radio", name="激活" if health_check else "禁用").click()
        if health_check:
            if not health_type:
                raise ValueError("健康检查激活时，必须提供 health_type (例如: 'TCP', 'HTTP')")
            # 详细健康检查设置
            if health_type:
                # 使用 label[for] 定位类型下拉框，以区别于会话保持的类型
                form_item_by_label("health_monitor.type").get_by_placeholder("请选择").click()
                # 仅在可见的下拉弹窗中进行精确匹配选择
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(health_type)}$")).click()
            if health_max_retries:
                form_item_by_text("最大尝试次数").get_by_role("spinbutton").fill(str(health_max_retries))
            if health_timeout:
                form_item_by_text("超时").get_by_role("spinbutton").fill(str(health_timeout))
            if health_interval:
                form_item_by_text("检查间隔").get_by_role("spinbutton").fill(str(health_interval))
            if health_type == "HTTP":
                http_method = http_method or "GET"
                url_path = url_path or "/"

                form_item_by_text("HTTP(S)方法").get_by_placeholder("请选择").click()
                self.locator("div.el-select-dropdown:visible li").filter(has_text=re.compile(rf"^{re.escape(http_method)}$")).click()

                url_input = form_item_by_text("URL地址").get_by_role("textbox")
                url_input.click()
                url_input.fill(url_path)

            if health_type == "UDP":
                if health_request is not None:
                    request_item = form_items.filter(has_text="健康检查请求").first
                    request_item.get_by_role("textbox").fill(health_request)
                if health_expected_response is not None:
                    response_item = form_items.filter(has_text="健康检查返回结果").first
                    response_item.get_by_role("textbox").fill(health_expected_response)

        self.get_by_text("下一步").click()

    def _slb_lb_set_confirm_info(self):
        """步骤3: 确认信息"""
        # 点击最后一步的“新建”按钮（在 footer 中的容器定位更精准）
        self.dialog_confirm.click()
        # self.locator(".dialog-box-footer").get_by_text("新建", exact=True).click()

    @submenu("负载均衡（基础版）")
    def slb_lb_create(self, slb_name, lb_name, protocol="TCP", port=80,
                            desc=None, acl_enable=False, access_policy=None, ip_group=None,
                            pool_name=None, balance_method="轮询", health_check=True,
                            **kwargs):
        """为负载均衡创建监听器 (3步流程)

        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            protocol: 监听协议，默认"TCP"
            port: 监听端口号，默认80
            desc: 描述
            acl_enable: 是否启用访问控制，默认False
            access_policy: 访问策略，可选"黑名单"、"白名单"，默认None
            ip_group: IP地址组名称，在使用访问策略时必填
            pool_name: 资源池名称，如果为None则自动生成
            balance_method: 负载均衡算法，可选"源IP"、"加权轮询"、"轮询"，默认"轮询"
            health_check: 是否开启健康检查，默认True (激活)
            **kwargs: 其他 HTTPS 相关参数:
                auth_mode: "单向认证" 或 "双向认证"
                cert_type: "国际服务器证书" 或 "国密服务器证书" (支持字符串或列表)
                server_cert: 证书名称 (支持字符串或字典 {"国际": "...", "国密": "..."})
                ca_cert: CA 证书名称 (双向认证时使用)
                http_redirect: 是否开启 HTTP 端口重定向 (True/False)
                redirect_port: 重定向端口
        """
        # 进入SLB详情页并切换到监听器Tab
        self.goto_slb_detail(slb_name, tab_name="监听器")

        # 点击监听器区域的新建按钮，兼容空页面和已有列表两种状态
        self.lb_create()

        # 1. 基础配置
        self._slb_lb_set_basic_config(
            lb_name, protocol, port, desc, acl_enable, access_policy, ip_group,
            auth_mode=kwargs.get("auth_mode", "单向认证"),
            cert_type=kwargs.get("cert_type", "国际服务器证书"),
            server_cert=kwargs.get("server_cert"),
            ca_cert=kwargs.get("ca_cert"),
            http_redirect=kwargs.get("http_redirect", False),
            redirect_port=kwargs.get("redirect_port")
        )

        # 2. 监听器配置 (资源池)
        self._slb_lb_set_listener_config(
            pool_name, balance_method, health_check,
            session_persistence=kwargs.get("session_persistence", False),
            session_type=kwargs.get("session_type"),
            health_type=kwargs.get("health_type"),
            health_max_retries=kwargs.get("health_max_retries"),
            health_timeout=kwargs.get("health_timeout"),
            health_interval=kwargs.get("health_interval"),
            http_method=kwargs.get("http_method"),
            url_path=kwargs.get("url_path"),
            health_request=kwargs.get("health_request"),
            health_expected_response=kwargs.get("health_expected_response"),
        )

        # 3. 确认信息
        self._slb_lb_set_confirm_info()

        self.logger.info(f"SLB监听器创建成功: {lb_name} ({protocol}:{port})")
        return lb_name

    def assert_listener_exists(self, lb_name):
        """验证左侧列表是否存在指定名称的监听器 (针对详情页监听器Tab)"""
        # 使用用户提供的 listener-left-list-item 容器进行精确匹配
        locator = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        # 确保可见
        locator.wait_for(state="visible", timeout=5000)
        self.logger.info(f"验证监听器 {lb_name} 存在于左侧列表")

    @submenu("负载均衡（基础版）")
    def goto_slb_detail(self, slb_name, tab_name="详情"):
        """进入负载均衡详情页并切换到指定Tab页

        Args:
            slb_name: 负载均衡名称
            tab_name: 详情页中的Tab名称，如："详情"、"监听器"、"后端服务器组" 等
        """
        # @submenu 装饰器已确保在负载均衡服务下，若从子页面（如resource-pool-detail）进入，
        # 子菜单点击会导航回SLB列表页

        # 先搜索目标SLB，避免分页导致定位失败
        try:
            self.search(slb_name)
        except Exception:
            self.logger.debug(f"搜索SLB {slb_name} 失败，尝试直接定位")

        # 点击SLB名称链接进入详情页
        # 搜索后列表通常只有一条，名称列在第二列（第一列为复选框）
        target_row = self.get_row_by_name(slb_name)
        name_cell = target_row.locator("td").nth(1)
        name_link = name_cell.locator("a").first
        if name_link.count() > 0 and name_link.is_visible():
            name_link.click(force=True)
        else:
            name_cell.click(force=True)

        # 等待页面加载，增加容错避免 loading spinner 等待卡住
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            self.page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        try:
            self.wait_for_page_ready()
        except Exception as e:
            self.logger.warning(f"wait_for_page_ready 警告（继续执行）: {e}")
            self.page.wait_for_timeout(2000)

        # 兼容 tab 文本可能带计数后缀（如"监听器(1)"）
        tab = self.locator("[role='tab']").filter(has_text=re.compile(rf"^{re.escape(tab_name)}"))
        try:
            expect(tab.first).to_be_visible(timeout=15000)
        except Exception as e:
            self.logger.warning(f"Tab '{tab_name}' 未在15秒内可见（继续执行）: {e}")
        tab.first.evaluate("node => node.click()")
        # 点击tab后等待内容加载（监听器列表异步渲染）
        if tab_name == "监听器":
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            self.page.wait_for_timeout(3000)

        self.logger.info(f"进入负载均衡 {slb_name} 的 {tab_name}")

    @submenu("负载均衡（基础版）")
    def slb_list_goto_lb_detail(self, slb_name, lb_name, column_name="配置监听器(前端协议/端口)"):
        """从SLB列表页点击指定监听器入口并进入其详情页

        Args:
            slb_name: 负载均衡名称，用于精确定位所在行
            lb_name: 监听器名称，用于在目标列中精确定位对应入口
            column_name: 监听器所在列名，默认"配置监听器(前端协议/端口)"
        """
        target_row = self.get_row_by_name(slb_name)

        table_index = target_row.evaluate("""
            el => {
                const table = el.closest('.el-table');
                if (!table) return -1;
                return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
            }
        """)

        if table_index != -1:
            headers = self.locator(".el-table").nth(table_index).locator(
                ".el-table__header-wrapper th").all_text_contents()
        else:
            headers = self.table_headers

        headers = [re.sub(r"\s+", " ", item).strip() for item in headers]
        if column_name not in headers:
            raise AssertionError(f"未找到表头 '{column_name}'，当前表头: {headers}")

        target_col_index = headers.index(column_name)
        target_cell = target_row.get_by_role("cell").nth(target_col_index)
        lb_pattern = re.compile(rf"^{re.escape(lb_name)}\s*\([^)]+\)$")

        text_nodes = target_cell.locator("span.text-content")
        matched_indexes = []

        all_texts = text_nodes.all_text_contents()
        for i, text in enumerate(all_texts):
            text_value = re.sub(r"\s+", " ", text or "").strip()
            if lb_pattern.match(text_value):
                matched_indexes.append(i)

        if not matched_indexes:
            raise AssertionError(
                f"在 SLB '{slb_name}' 的列 '{column_name}' 中未找到监听器 '{lb_name}' 的跳转入口，"
                f"单元格内容: '{target_cell.text_content()}'"
            )

        if len(matched_indexes) > 1:
            matched_texts = [
                re.sub(r"\s+", " ", text or "").strip()
                for i, text in enumerate(all_texts) if i in matched_indexes
            ]
            raise AssertionError(
                f"在 SLB '{slb_name}' 的列 '{column_name}' 中找到多个匹配监听器 '{lb_name}': {matched_texts}"
            )

        target_text = text_nodes.nth(matched_indexes[0])
        clickable = target_text.locator("xpath=ancestor::div[contains(@class,'cloud-button-btn')][1]")
        if clickable.count() == 0:
            clickable = target_text.locator("xpath=ancestor::*[@title][1]")
        if clickable.count() == 0:
            clickable = target_text

        clickable.click()
        self.logger.info(f"从SLB列表页进入监听器详情成功: SLB={slb_name}, LB={lb_name}")

    def lb_create(self):
        """在SLB详情页的监听器区域点击新建按钮"""
        create_btns = [
            self.get_by_text("立即创建"),
            self.get_by_text("新建", exact=True),
        ]
        self._find_element(create_btns, "监听器新建按钮", timeout=2000).click()
        self.logger.info("点击监听器新建按钮成功")

    def select_lb_in_left_list(self, lb_name):
        """在监听器详情嵌套页左侧列表中选中指定监听器"""
        # 先等待页面加载完成（监听器列表可能异步加载）
        loader = self.locator(".cloud-loader, .el-loading-mask").first
        try:
            expect(loader).not_to_be_visible(timeout=30000)
        except AssertionError:
            self.logger.warning("加载动画未消失，继续尝试定位监听器")
        # 放宽正则表达式对前后空白符的限制，兼顾精确匹配(防止如 lb1 误匹配到 lb11 等情况)
        lb_pattern = re.compile(rf"^\s*{re.escape(lb_name)}(?:\s*\([^)]+\))?\s*$")
        target = self.locator("div.listener-left-list-item").filter(has_text=lb_pattern).first
        # 轮询等待目标监听器出现（左侧列表可能异步加载）
        try:
            expect(target).to_be_visible(timeout=30000)
        except AssertionError:
            import tempfile, os
            debug_dir = tempfile.gettempdir()
            safe_name = lb_name.replace(" ", "_").replace("/", "_")
            html_path = os.path.join(debug_dir, f"select_lb_debug_{safe_name}.html")
            png_path = os.path.join(debug_dir, f"select_lb_debug_{safe_name}.png")
            try:
                html = self.page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                self.page.screenshot(path=png_path)
                self.logger.info(f"调试文件已保存: {html_path}, {png_path}")
            except Exception as e:
                self.logger.warning(f"保存调试文件失败: {e}")
            raise
        target.click()
        self.logger.info(f"左侧监听器列表选中成功: {lb_name}")

    def _get_lb_nested_tabs(self):
        """获取监听器详情右侧的嵌套Tab容器（详情/资源池）"""
        tabs = self.locator(".el-tabs").filter(has=self.get_by_role("tab", name="详情")).filter(
            has=self.get_by_role("tab", name="资源池")).last
        expect(tabs).to_be_visible(timeout=5000)
        return tabs

    def goto_lb_detail(self, lb_name, tab_name="详情"):
        """在SLB详情页内切换到指定监听器及其右侧Tab页"""
        self.select_lb_in_left_list(lb_name)
        nested_tabs = self._get_lb_nested_tabs()
        nested_tabs.get_by_role("tab", name=tab_name).click()
        self.logger.info(f"进入监听器 '{lb_name}' 的 '{tab_name}' 页签")

    def goto_lb_pool_tab(self, lb_name):
        """切换到指定监听器的资源池页签"""
        self.goto_lb_detail(lb_name, tab_name="资源池")
        self.logger.info(f"进入监听器 {lb_name} 的资源池页签成功")

    def goto_lb_pool_detail(self, lb_name, pool_name, force=False):
        """进入指定监听器下资源池详情页"""
        # 若当前已在目标资源池详情页，避免重复导航导致 select_lb_in_left_list 在错误页面上执行
        current_url = self.page.url
        if not force and "resource-pool-detail" in current_url and pool_name in current_url:
            self.logger.info(f"当前已在资源池详情页，跳过重复导航: {pool_name}")
            return

        self.goto_lb_pool_tab(lb_name)
        active_pane = self._get_lb_nested_tabs().locator(".el-tab-pane:not([aria-hidden='true'])").last
        pool_row = active_pane.locator(".el-table__body-wrapper tr").filter(has_text=pool_name).first
        expect(pool_row).to_be_visible(timeout=5000)

        clickable = pool_row.locator("a", has_text=pool_name).first
        if clickable.count() == 0:
            clickable = pool_row.get_by_text(pool_name).first
        clickable.click()
        self.logger.info(f"进入监听器 {lb_name} 下资源池详情成功: {pool_name}")

    def lb_pool_add_vm(self, vm_names, lb_name=None, pool_name=None, resource_type="弹性云服务器 ECS", ports=None):
        """在监听器资源池详情页中新增虚机资源

        Args:
            vm_names: 虚机名称，支持单个字符串或名称列表
            lb_name: 监听器名称，传入时会先自动进入该监听器
            pool_name: 资源池名称，和 lb_name 一起传入时会自动进入资源池详情
            resource_type: 资源类型，默认"弹性云服务器 ECS"
            ports: 资源端口配置，支持单个端口值、与 vm_names 顺序对应的列表，或 {vm_name: port} 字典
        """
        if isinstance(vm_names, str):
            vm_names = [vm_names]

        def resolve_port(vm_name, index):
            if ports is None:
                return None
            if isinstance(ports, dict):
                return ports.get(vm_name)
            if isinstance(ports, (list, tuple)):
                return ports[index]
            return ports

        if lb_name and pool_name:
            self.goto_lb_pool_detail(lb_name, pool_name)
        elif lb_name or pool_name:
            raise ValueError("lb_name 和 pool_name 需要同时传入，或者都不传")

        table_container = self.locator(".cloud-table-container.table-fixed").first
        expect(table_container).to_be_visible(timeout=5000)
        table_container.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)

        create_btn = table_container.locator(
            ".cloud-table-header .cloud-button-btn"
        ).filter(has_text=re.compile(r"^\s*新建\s*$")).first
        expect(create_btn).to_be_visible(timeout=5000)
        expect(create_btn).not_to_have_class(re.compile(r"cl-btn-disabled"), timeout=15000)
        create_btn.click()

        dialog = self.locator(".el-dialog__wrapper:visible").get_by_role("dialog", name="新建资源")
        expect(dialog).to_be_visible(timeout=5000)

        resource_type_input = dialog.get_by_placeholder("请选择").first
        resource_type_input.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(resource_type)}$")
        ).first.click()

        dialog.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)

        try:
            pagination_trigger = dialog.locator(".el-pagination__sizes .el-input__inner").first
            if pagination_trigger.count() > 0 and pagination_trigger.is_visible():
                pagination_trigger.click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(r"^100条/页$")
                ).first.click()
                dialog.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)
        except Exception as e:
            self.logger.warning(f"尝试设置资源选择分页为100失败: {e}")

        missing_vms = []
        for index, vm_name in enumerate(vm_names):
            row = dialog.locator(".el-table__body-wrapper tr").filter(
                has_text=re.compile(rf"\b{re.escape(vm_name)}\b")
            ).first

            if row.count() == 0 or not row.is_visible():
                missing_vms.append(vm_name)
                continue

            checkbox = row.locator("td").first.locator(".el-checkbox").first
            checkbox_class = checkbox.get_attribute("class") or ""
            if "is-checked" not in checkbox_class:
                checkbox.click()
                self.logger.info(f"资源池新增虚机时已勾选: {vm_name}")

            target_port = resolve_port(vm_name, index)
            if target_port is not None:
                port_input = row.get_by_role("spinbutton").first
                expect(port_input).to_be_visible(timeout=3000)
                port_input.fill(str(target_port))
                self.logger.info(f"资源池新增虚机时已设置端口: {vm_name} -> {target_port}")

        if missing_vms:
            raise AssertionError(f"新建资源弹窗当前可选列表中未找到虚机: {missing_vms}")

        self.dialog_confirm.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)
        self.logger.info(f"资源池新增虚机提交成功: vm_names={vm_names}, resource_type={resource_type}, ports={ports}")

    def assert_lb_pool_basic_info(self, pool_name, protocol=None, balance_method=None,
                                  session_persistence=None, health_check=None):
        """校验资源池详情页顶部的基本信息回显。

        Args:
            pool_name: 资源池名称。
            protocol: 协议，如 ``TCP``、``HTTP``，默认不校验。
            balance_method: 负载调度算法，如 ``轮询``，默认不校验。
            session_persistence: 会话保持展示值，如 ``未开启``，默认不校验。
            health_check: 健康检查展示值，如 ``未开启``，默认不校验。
        """
        page_root = self.locator("#cloud-container-content")
        expect(page_root.get_by_text("基本信息", exact=True)).to_be_visible(timeout=5000)

        expected_texts = [pool_name, protocol, balance_method, session_persistence, health_check]
        for text in expected_texts:
            if text is not None:
                expect(page_root).to_contain_text(str(text))

        self.logger.info(
            "资源池详情基本信息校验成功: "
            f"pool_name={pool_name}, protocol={protocol}, balance_method={balance_method}, "
            f"session_persistence={session_persistence}, health_check={health_check}"
        )

    def lb_pool_config_health_check(self, lb_name, pool_name, enable=True,
                                    health_type=None, health_request=None,
                                    health_expected_response=None):
        """在资源池详情页配置健康检查。

        弹窗内健康检查主控为 ``el-switch``（label="是否开启"），
        V1/V2 的 UDP 请求/返回结果字段在配置弹窗中均为 **disabled 只读**，
        因此本方法不尝试填写这两项。

        Args:
            lb_name: 监听器名称。
            pool_name: 资源池名称。
            enable: 是否开启健康检查，默认 True。
            health_type: 健康检查类型，如 ``TCP``、``HTTP``、``UDP``。
                开启健康检查时必须提供。
            health_request: UDP 健康检查请求内容（仅创建监听器时有效，
                配置弹窗中该字段 disabled，此处忽略）。
            health_expected_response: UDP 健康检查返回结果（仅创建监听器时有效，
                配置弹窗中该字段 disabled，此处忽略）。
        """
        self.goto_lb_pool_detail(lb_name, pool_name)
        page_root = self.locator("#cloud-container-content")

        # 点击健康检查区域的"配置"按钮
        # 页面上可能有多个"配置"链接（负载调度算法、会话保持等），
        # 通过 XPath 精确定位：位于包含"健康检查"文本的容器内的"配置"链接。
        config_btn = page_root.locator(
            "xpath=.//*[contains(., '健康检查')]//a[contains(., '配置')]"
        ).first
        expect(config_btn).to_be_visible(timeout=5000)
        config_btn.click()

        # 等待"配置健康检查"弹窗出现
        # Element UI 的 el-dialog 结构为 .el-dialog__wrapper > .el-dialog[role=dialog]
        # 直接定位可见的 .el-dialog 并校验内容
        dialog = self.locator(".el-dialog:visible")
        expect(dialog).to_be_visible(timeout=5000)
        expect(dialog).to_contain_text("是否开启", timeout=3000)

        form_items = dialog.locator("div.el-form-item")

        # 切换健康检查开关（label="是否开启"，控件为 el-switch）
        switch_item = form_items.filter(has_text="是否开启")
        switch_ctrl = switch_item.locator(".el-switch").first
        expect(switch_ctrl).to_be_visible(timeout=5000)

        is_checked = switch_ctrl.evaluate("el => el.classList.contains('is-checked')")
        if enable != is_checked:
            switch_ctrl.click()

        if enable:
            if not health_type:
                raise ValueError("开启健康检查时，必须提供 health_type (例如: 'TCP', 'HTTP', 'UDP')")

            # 类型选择：V1 的 select 为 disabled（不可改），V2 可编辑
            type_select = form_items.filter(has_text="类型").get_by_placeholder("请选择")
            if type_select.is_visible() and not type_select.evaluate(
                "el => el.disabled"
            ):
                type_select.click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(rf"^{re.escape(health_type)}$")
                ).click()

            # UDP 的 hc_request / hc_response 在配置弹窗中为 disabled，不填写
            # 若未来平台放开编辑，可在此处补充 fill 逻辑

        dialog.get_by_text("确定", exact=True).click()
        # 健康检查配置的成功提示文案不固定（"关闭健康检查成功" / "配置健康检查成功" 等），
        # 因此仅断言弹窗类型为 success，不校验具体文本。
        self.assert_popup_success()
        self.logger.info(
            f"健康检查配置完成: lb={lb_name}, pool={pool_name}, "
            f"enable={enable}, health_type={health_type}"
        )

    def assert_lb_pool_member_info(self, vm_name, ip_address=None, port=None,
                                   switch_status=None, resource_status=None):
        """校验资源池成员列表中的关键信息。

        Args:
            vm_name: 资源实例名称。
            ip_address: 期望的 IP 地址，默认不校验。
            port: 期望的资源端口号，默认不校验。
            switch_status: 期望的开关状态，默认不校验。
            resource_status: 期望的资源状态，默认不校验。

        Returns:
            dict: 当前资源行解析后的表格数据。
        """
        row_data = self.get_row_data(vm_name)
        expected_mapping = {
            "实例名称": vm_name,
            "IP地址": ip_address,
            "端口号": port,
            "开关状态": switch_status,
            "资源状态": resource_status,
        }

        for field_name, expected_value in expected_mapping.items():
            if expected_value is None:
                continue

            actual_value = (row_data.get(field_name) or "").strip()
            if actual_value != str(expected_value):
                raise AssertionError(
                    f"资源池成员 '{vm_name}' 字段 '{field_name}' 校验失败，"
                    f"期望 '{expected_value}'，实际 '{actual_value}'"
                )

        for field_name in ["开关状态", "资源状态"]:
            actual_value = (row_data.get(field_name) or "").strip()
            if not actual_value:
                raise AssertionError(f"资源池成员 '{vm_name}' 字段 '{field_name}' 为空")

        self.logger.info(f"资源池成员信息校验成功: {vm_name}, row_data={row_data}")
        return row_data

    def wait_lb_pool_member_status(self, lb_name, pool_name, vm_name,
                                   expected_status="运行中", timeout=120,
                                   interval=10, refresh=True):
        """轮询等待资源池成员状态变为期望值。

        Args:
            lb_name: 监听器名称。
            pool_name: 资源池名称。
            vm_name: 目标虚机名称（资源池成员）。
            expected_status: 期望状态，默认"运行中"。
            timeout: 最大等待时间（秒），默认120。
            interval: 轮询间隔（秒），默认10。
            refresh: 是否主动点击刷新按钮，默认True。（暂仅支持True）

        Raises:
            AssertionError: 超时后状态仍未匹配。
        """
        deadline = time.time() + timeout
        navigated = False
        actual_status = ""

        while time.time() < deadline:
            if not navigated:
                self.goto_lb_pool_detail(lb_name, pool_name)
                navigated = True
            else:
                try:
                    self.btn_refresh.click()
                    self.wait_for_page_ready()
                except Exception as e:
                    self.logger.warning(f"刷新页面失败: {e}")

            try:
                row = self.get_row_by_name(vm_name)
            except AssertionError:
                self.logger.info(f"轮询成员状态: 页面暂未找到 {vm_name}，继续等待")
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(interval, remaining))
                continue

            # 行已存在，精确读取状态
            row_data = self.get_row_data_by_locator(row)
            actual_status = (row_data.get("资源状态") or "").strip()
            self.logger.info(f"轮询成员状态: {vm_name} = {actual_status}, 期望 = {expected_status}")
            if actual_status == expected_status:
                self.logger.info(f"成员状态达到期望值: {vm_name} -> {expected_status}")
                return

            remaining = deadline - time.time()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))

        raise AssertionError(
            f"成员 {vm_name} 状态在 {timeout} 秒内未达到 {expected_status}, "
            f"最后状态: {actual_status}"
        )

    def get_lb_pool_candidate_vm_names(self, lb_name=None, pool_name=None,
                                       resource_type="弹性云服务器 ECS"):
        """打开资源池"新建资源"弹窗，返回当前可选虚机名称列表后关闭弹窗。

        用于校验"对等连接前后跨 VPC 虚机是否出现在可选资源中"的场景。

        Args:
            lb_name: 监听器名称；与 ``pool_name`` 同时传入时先进入资源池详情。
            pool_name: 资源池名称；与 ``lb_name`` 同时传入时先进入资源池详情。
            resource_type: 资源类型，默认"弹性云服务器 ECS"。

        Returns:
            list[str]: 当前可选资源列表中显示的虚机名称（去重，按行顺序）。
        """
        if lb_name and pool_name:
            self.goto_lb_pool_detail(lb_name, pool_name)
        elif lb_name or pool_name:
            raise ValueError("lb_name 和 pool_name 需要同时传入，或者都不传")

        table_container = self.locator(".cloud-table-container.table-fixed").first
        expect(table_container).to_be_visible(timeout=5000)
        table_container.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)

        create_btn = table_container.locator(
            ".cloud-table-header .cloud-button-btn"
        ).filter(has_text=re.compile(r"^\s*新建\s*$")).first
        expect(create_btn).to_be_visible(timeout=5000)
        expect(create_btn).not_to_have_class(re.compile(r"cl-btn-disabled"), timeout=15000)
        create_btn.click()

        dialog = self.locator(".el-dialog__wrapper:visible").get_by_role("dialog", name="新建资源")
        expect(dialog).to_be_visible(timeout=5000)

        resource_type_input = dialog.get_by_placeholder("请选择").first
        resource_type_input.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(resource_type)}$")
        ).first.click()

        dialog.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)

        try:
            pagination_trigger = dialog.locator(".el-pagination__sizes .el-input__inner").first
            if pagination_trigger.count() > 0 and pagination_trigger.is_visible():
                pagination_trigger.click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(r"^100条/页$")
                ).first.click()
                dialog.locator(".el-loading-mask").wait_for(state="hidden", timeout=15000)
        except Exception as exc:
            self.logger.warning(f"尝试设置资源选择分页为100失败: {exc}")

        rows = dialog.locator(".el-table__body-wrapper tr")
        row_count = rows.count()
        candidate_names: list[str] = []
        for index in range(row_count):
            row_text = rows.nth(index).inner_text().strip()
            if row_text:
                candidate_names.append(row_text)

        try:
            self.dialog_cancel.click()
        except Exception:
            self.close_dialog_if_exists()

        self.logger.info(
            f"资源池可选资源读取完成: lb={lb_name}, pool={pool_name}, count={len(candidate_names)}"
        )
        return candidate_names

    def lb_pool_remove_vm(self, vm_names, lb_name=None, pool_name=None):
        """从监听器资源池详情页删除已添加的虚机资源。

        Args:
            vm_names: 待删除的虚机名称，支持单个字符串或名称列表。
            lb_name: 监听器名称；和 ``pool_name`` 一起传入时，会先自动进入资源池详情页。
            pool_name: 资源池名称；和 ``lb_name`` 一起传入时，会先自动进入资源池详情页。
        """
        if isinstance(vm_names, str):
            vm_names = [vm_names]

        if lb_name and pool_name:
            self.goto_lb_pool_detail(lb_name, pool_name)
        elif lb_name or pool_name:
            raise ValueError("lb_name 和 pool_name 需要同时传入，或者都不传")

        for vm_name in vm_names:
            self.click_action(vm_name, "删除")
            self.dialog_confirm.click()
            self.logger.info(f"资源池成员删除成功: {vm_name}")

    def assert_dialog_error(self, *expected_texts):
        """
        验证包含预期错误信息的弹窗，并关闭该弹窗

        Args:
            *expected_texts: 预期的错误提示文本，可传入多个
        """

        dialog_box = self.locator(".one-dialog-box")
        expect(dialog_box).to_be_visible(timeout=5000)
        for text in expected_texts:
            expect(dialog_box).to_contain_text(text)
        close_btn = dialog_box.locator(".cloud-button-btn", has_text="关闭")
        close_btn.click()
        expect(dialog_box).not_to_be_visible(timeout=5000)
        self.logger.info(f"成功验证并关闭错误弹窗: {expected_texts}")

    def assert_lb_basic_info(self, info_text):
        """验证监听器详情页基本信息区域包含指定监听器名称"""
        nested_tabs = self._get_lb_nested_tabs()
        nested_tabs.get_by_role("tab", name="详情").click()

        active_pane = nested_tabs.locator(".el-tab-pane:not([aria-hidden='true'])").last
        active_pane.get_by_text("基本信息", exact=True).wait_for(state="visible", timeout=5000)
        expect(active_pane).to_contain_text(info_text)
        self.logger.info(f"验证监听器详情基本信息包含 {info_text} 成功")

    def _get_lb_detail_active_pane(self):
        """获取监听器详情页当前激活的右侧内容区域"""
        nested_tabs = self._get_lb_nested_tabs()
        nested_tabs.get_by_role("tab", name="详情").click()
        active_pane = nested_tabs.locator(".el-tab-pane:not([aria-hidden='true'])").last
        active_pane.get_by_text("基本信息", exact=True).wait_for(state="visible", timeout=5000)
        return active_pane

    @submenu("负载均衡（基础版）")
    def get_available_eips(self, slb_name, network_type="public_net(基础版)", ip_version="IPv4"):
        """获取负载均衡可绑定的可用公网IP列表（不执行绑定）

        Args:
            slb_name: 负载均衡名称
            network_type: IP池名称，默认"public_net(基础版)"
            ip_version: IP版本，默认"IPv4"

        Returns:
            list[str]: 可用EIP地址列表（状态为'关闭'的IP）
        """
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        try:
            expect(rows_locator.first).to_be_visible(timeout=10000)
            available_rows = rows_locator.all()
        except AssertionError:
            available_rows = []

        eips = [row.get_by_role("cell").nth(1).text_content().strip() for row in available_rows]

        # 关闭对话框，不执行绑定
        try:
            dialog.get_by_text("取消").click()
        except Exception:
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
        self.logger.info(f"负载均衡 {slb_name} 可用公网IP: {eips}")
        return eips

    @submenu("负载均衡（基础版）")
    def slb_bind_eip(self, slb_name, network_type="public_net(基础版)", ip_version="IPv4"):
        """为负载均衡绑定公网IP，并返回绑定的EIP地址"""
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)
        available_rows = rows_locator.all()
        if not available_rows:
            raise AssertionError("当前环境无可用的弹性公网IPv4（状态为'关闭'）")

        selected_row = random.choice(available_rows)
        eip = selected_row.get_by_role("cell").nth(1).text_content().strip()
        selected_row.get_by_role("radio").click()
        dialog.get_by_text("确定").click()
        self.logger.info(f"负载均衡 {slb_name} {action_name}成功: {eip}")
        return eip

    @submenu("负载均衡（基础版）")
    def slb_bind_eip_by_ip(self, slb_name, eip, network_type="public_net(基础版)", ip_version="IPv4"):
        """为负载均衡绑定指定公网IP

        Args:
            slb_name: 负载均衡名称
            eip: 要绑定的公网IP地址
            network_type: IP池名称，默认"public_net(基础版)"
            ip_version: IP版本，默认"IPv4"

        Returns:
            str: 绑定的EIP地址
        """
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)

        available_rows = rows_locator.all()
        target_row = None
        for row in available_rows:
            cell_text = row.get_by_role("cell").nth(1).text_content().strip()
            if eip in cell_text:
                target_row = row
                break

        if target_row is None:
            raise AssertionError(
                f"在绑定公网IP对话框中未找到IP {eip}，"
                f"可用IP: {[r.get_by_role('cell').nth(1).text_content().strip() for r in available_rows]}"
            )
        target_row.get_by_role("radio").click()
        dialog.get_by_text("确定").click()
        self.logger.info(f"负载均衡 {slb_name} 绑定公网IP {eip} 成功")
        return eip

    @submenu("负载均衡（基础版）")
    def slb_unbind_eip(self, slb_name, ip_version="IPv4"):
        """解绑负载均衡绑定的公网IP"""
        action_name = f"解绑公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()
        self.assert_popup_success("执行成功")
        self.logger.info(f"负载均衡 {slb_name} {action_name}成功")

    # @submenu("负载均衡（基础版）")
    def _open_lb_basic_info_edit(self, lb_name, edit_icon_index):
        """打开监听器详情页“基本信息”区域对应位置的编辑入口。"""
        self.goto_lb_detail(lb_name)
        active_pane = self._get_lb_detail_active_pane()
        edit_icons = active_pane.locator(".el-icon-edit:visible")
        expect(edit_icons.nth(edit_icon_index)).to_be_visible(timeout=5000)
        edit_icons.nth(edit_icon_index).click()
        self.page.wait_for_timeout(300)
        return active_pane

    def _confirm_lb_inline_edit(self, active_pane):
        """提交监听器详情页的内联编辑。"""
        confirm_icons = active_pane.locator(".el-icon-check:visible")
        if confirm_icons.count() > 0:
            confirm_icons.first.click()
        else:
            input_box = active_pane.locator("input:visible, textarea:visible").first
            input_box.press("Enter")
        self.page.wait_for_timeout(500)

    def lb_edit_basic_info(self, lb_name, field, **kwargs):
        """修改监听器基本信息

        Args:
            lb_name: 监听器名称
            field: 要修改的字段，支持 "name"、"description"、"port"、"access_control"
            **kwargs: 对应字段的修改参数
        """
        if field == "name":
            new_name = kwargs.get("new_name")
            active_pane = self._open_lb_basic_info_edit(lb_name, 0)
            name_input = active_pane.locator("input:visible").first
            expect(name_input).to_be_visible(timeout=3000)
            name_input.fill(new_name)
            self._confirm_lb_inline_edit(active_pane)
            self.logger.info(f"监听器名称修改完成: {lb_name} -> {new_name}")

        elif field == "description":
            new_desc = kwargs.get("new_desc")
            active_pane = self._open_lb_basic_info_edit(lb_name, 3)
            desc_input = active_pane.locator("textarea:visible, input:visible").first
            expect(desc_input).to_be_visible(timeout=3000)
            desc_input.fill(new_desc)
            self._confirm_lb_inline_edit(active_pane)
            self.logger.info(f"监听器描述修改完成: {lb_name} -> {new_desc}")

        elif field == "port":
            protocol = kwargs.get("protocol")
            port = kwargs.get("port")
            if protocol is None and port is None:
                raise ValueError("protocol 和 port 不能同时为空")

            self._open_lb_basic_info_edit(lb_name, 1)
            dialog = self._find_element([
                self.get_by_role("dialog", name="修改端口"),
                self.get_by_role("dialog").filter(has_text="修改端口"),
            ], "修改端口对话框", timeout=5000)

            expect(dialog).to_be_visible(timeout=5000)
            if protocol:
                expect(dialog).to_contain_text(protocol)
            if port is not None:
                port_input = dialog.get_by_role("spinbutton").first
                expect(port_input).to_be_visible(timeout=3000)
                port_input.fill(str(port))

            dialog.get_by_text("确定", exact=True).click()
            self.logger.info(f"监听器前端协议/端口修改完成: {lb_name} -> {protocol}/{port}")

        elif field == "access_control":
            enable = kwargs.get("enable", False)
            access_policy = kwargs.get("access_policy")
            ip_group = kwargs.get("ip_group")

            self._open_lb_basic_info_edit(lb_name, 2)
            dialog = self._find_element([
                self.get_by_role("dialog", name="设置访问控制"),
                self.get_by_role("dialog").filter(has_text="设置访问控制"),
            ], "设置访问控制对话框", timeout=5000)

            expect(dialog).to_be_visible(timeout=5000)
            acl_switch = dialog.get_by_role("switch")
            is_enabled = acl_switch.get_attribute("aria-checked") == "true"
            if is_enabled != enable:
                acl_switch.locator("span").click()
                self.page.wait_for_timeout(300)

            if enable:
                selects = dialog.get_by_placeholder("请选择")
                if access_policy:
                    selects.first.click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text=re.compile(rf"^{re.escape(access_policy)}$")
                    ).first.click()
                if ip_group:
                    selects = dialog.get_by_placeholder("请选择")
                    expect(selects.nth(1)).to_be_visible(timeout=3000)
                    selects.nth(1).click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text=re.compile(rf"^{re.escape(ip_group)}$")
                    ).first.click()

            dialog.get_by_text("确定", exact=True).click()
            self.logger.info(
                f"监听器访问控制修改完成: {lb_name} -> enable={enable}, "
                f"access_policy={access_policy}, ip_group={ip_group}"
            )
        else:
            raise ValueError(f"不受支持的 field: {field}")

    def slb_lb_delete(self, slb_name, lb_name):
        """删除负载均衡监听器

        Args:
            slb_name: 负载均衡名称
            lb_name: 待删除的监听器名称
        """
        # 找到目标监听器项并点击删除图标
        target_item = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        target_item.locator(".el-icon-delete").click()

        # 确认删除
        self.dialog_confirm.click()

        self.logger.info(f"SLB监听器 {lb_name} 已删除 (SLB: {slb_name})")


    @submenu("负载均衡（基础版）")
    def slb_delete(self, names):
        """负载均衡

        Args:
            names: 负载均衡名称或名称列表
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作 ").click()

            # 点击批量删除选项
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

    @submenu("负载均衡（基础版）")
    def get_slb_vip(self, slb_name):
        """
        获取负载均衡的内网VIP地址。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 内网VIP地址
        """
        row_data = self.get_row_data(slb_name)
        vip = row_data.get("VIP地址") or row_data.get("内网地址") or row_data.get("网络IP") or row_data.get("地址")
        if not vip:
            headers = self.table_headers
            for key in ["VIP地址", "内网地址", "网络IP", "地址", "IPv4地址"]:
                if key in headers:
                    vip = row_data.get(key)
                    if vip:
                        break
        if not vip:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取内网VIP地址，当前行数据: {row_data}")
        self.logger.info(f"获取SLB '{slb_name}' 内网VIP地址: {vip}")
        return vip.strip()

    @submenu("负载均衡（基础版）")
    def get_slb_uuid(self, slb_name):
        """获取负载均衡的uuid。

        通过JavaScript从el-table行元素的Vue内部状态中读取uuid。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 负载均衡uuid
        """
        row = self.get_row_by_name(slb_name)
        uuid = row.evaluate("""
            el => {
                let current = el;
                while (current) {
                    if (current.__vue__ && current.__vue__.row && current.__vue__.row.uuid) {
                        return current.__vue__.row.uuid;
                    }
                    current = current.parentElement;
                }
                const tr = el.closest('tr');
                if (tr && tr.dataset && tr.dataset.uuid) return tr.dataset.uuid;
                const tableRow = el.closest('.el-table__row');
                if (tableRow && tableRow.__vue__ && tableRow.__vue__.row && tableRow.__vue__.row.uuid) {
                    return tableRow.__vue__.row.uuid;
                }
                return null;
            }
        """)
        if not uuid:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取uuid")
        self.logger.info(f"获取SLB '{slb_name}' uuid: {uuid}")
        return uuid

    @submenu("负载均衡（基础版）")
    def get_slb_project_id(self, slb_name):
        """获取负载均衡的project_id。

        通过JavaScript从el-table行元素的Vue内部状态中读取project_id。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: project_id
        """
        row = self.get_row_by_name(slb_name)
        project_id = row.evaluate("""
            el => {
                let current = el;
                while (current) {
                    if (current.__vue__ && current.__vue__.row && current.__vue__.row.project_id) {
                        return current.__vue__.row.project_id;
                    }
                    current = current.parentElement;
                }
                const tr = el.closest('tr');
                if (tr && tr.dataset && tr.dataset.projectId) return tr.dataset.projectId;
                const tableRow = el.closest('.el-table__row');
                if (tableRow && tableRow.__vue__ && tableRow.__vue__.row && tableRow.__vue__.row.project_id) {
                    return tableRow.__vue__.row.project_id;
                }
                return null;
            }
        """)
        if not project_id:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取project_id")
        self.logger.info(f"获取SLB '{slb_name}' project_id: {project_id}")
        return project_id

    @submenu("负载均衡（基础版）")
    def goto_slb_monitor(self, slb_name):
        """在SLB列表页点击"查看监控"进入监控详情页。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 监控页面URL
        """
        self.search(slb_name)
        self.click_action(slb_name, "查看监控")
        self.logger.info(f"点击SLB '{slb_name}' 查看监控")
        # 等待页面导航完成
        self.page.wait_for_timeout(3000)
        return self.page.url

    @submenu("负载均衡（基础版）")
    def get_slb_eip(self, slb_name):
        """
        获取负载均衡绑定的公网IP地址。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 公网IP地址，如果未绑定则返回None
        """
        row_data = self.get_row_data(slb_name)
        eip = row_data.get("公网IPv4") or row_data.get("公网IP") or row_data.get("弹性公网IP")
        if eip and eip.strip() and eip.strip() not in ["-", "--", "无", ""]:
            self.logger.info(f"获取SLB '{slb_name}' 公网IP地址: {eip.strip()}")
            return eip.strip()
        self.logger.info(f"SLB '{slb_name}' 未绑定公网IP")
        return None
