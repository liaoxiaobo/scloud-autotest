import re

from sugon_web.common.base import submenu
from sugon_web.common.playwright import expect
from sugon_web.utils.util import random_data
from .slb_list import SlbListMixin


class SlbDetailMixin(SlbListMixin):
    """SLB详情页（监听器列表层）。"""

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

            # 服务器证书类型选择 (V2 展示 checkbox-group，V1 直接展示下拉框)
            checkbox_group = self.get_by_label("checkbox-group")
            cert_types = [cert_type] if isinstance(cert_type, str) else cert_type
            if checkbox_group.count() > 0:
                for ct in ["国际服务器证书", "国密服务器证书"]:
                    checkbox_label = checkbox_group.locator("label").filter(has_text=ct)
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
                self.page.wait_for_timeout(500)
                if redirect_port:
                    # spinbutton 在独立的 "HTTP重定向端口" 表单项内，不在 "HTTP端口重定向" 中
                    self.locator("div.el-form-item").filter(
                        has_text=re.compile(r"HTTP重定向端口")
                    ).get_by_role("spinbutton").fill(str(redirect_port))

        # 访问控制（V1 的 HTTP/HTTPS 协议下不展示该选项）
        acl_form_item = self.locator("div.el-form-item").filter(has_text="启用访问控制")
        if acl_form_item.count() > 0 and acl_form_item.get_by_role("switch").count() > 0:
            acl_switch = acl_form_item.get_by_role("switch").first
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
        # 点击最后一步的"新建"按钮（在 footer 中的容器定位更精准）
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
