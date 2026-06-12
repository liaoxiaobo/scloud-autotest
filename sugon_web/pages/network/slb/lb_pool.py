import re
import time

from sugon_web.common.playwright import expect
from sugon_web.utils.data import random_data
from .lb_detail import LbDetailMixin


class LbPoolMixin(LbDetailMixin):
    """资源池详情页。"""

    def lb_pool_create(self, slb_name, lb_name, pool_name, balance_method="轮询",
                       session_persistence=False, health_check=False,
                       health_type=None, http_method=None, url_path=None):
        """在监听器详情页的资源池tab中创建新的资源池。

        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            pool_name: 资源池名称
            balance_method: 负载调度算法，可选"轮询"、"加权轮询"、"源IP"、"最小连接数"
            session_persistence: 是否开启会话保持
            health_check: 是否开启健康检查
            health_type: 健康检查类型，如"TCP"、"HTTP"
            http_method: HTTP健康检查方法，如"GET"、"HEAD"
            url_path: HTTP健康检查URL路径，如"/index.html"
        """
        # 先导航到SLB详情页的监听器tab，确保页面状态正确
        self.goto_slb_detail(slb_name, tab_name="监听器")
        # 额外等待监听器左侧列表异步加载完成
        self.page.wait_for_timeout(5000)
        self.goto_lb_pool_tab(lb_name)

        # 点击"新建"按钮（在资源池列表区域）
        nested_tabs = self._get_lb_nested_tabs()
        active_pane = nested_tabs.locator(".el-tab-pane:not([aria-hidden='true'])").last
        create_btn = None

        # 先尝试在 cloud-table-container 中定位（资源池详情页样式）
        try:
            table_container = active_pane.locator(".cloud-table-container").first
            if table_container.count() > 0 and table_container.is_visible():
                btn = table_container.locator(
                    ".cloud-table-header .cloud-button-btn"
                ).filter(has_text=re.compile(r"^\s*新建\s*$")).first
                if btn.count() > 0 and btn.is_visible():
                    create_btn = btn
        except Exception:
            pass

        # 降级：在激活的 tab pane 中直接查找
        if create_btn is None:
            create_btn = active_pane.locator(".cloud-button-btn").filter(
                has_text=re.compile(r"^\s*新建\s*$")
            ).first

        expect(create_btn).to_be_visible(timeout=5000)
        create_btn.click()

        # 等待"新建资源池"对话框
        dialog = self.get_by_role("dialog", name="新建资源池")
        expect(dialog).to_be_visible(timeout=5000)

        try:
            # 填写资源池名称
            dialog.locator("div.el-form-item").filter(
                has_text=re.compile(r"资源池名称")
            ).get_by_role("textbox").fill(pool_name)

            # 选择负载调度算法
            algorithm_select = dialog.locator("div.el-form-item").filter(
                has_text=re.compile(r"负载调度算法")
            ).get_by_placeholder("请选择")
            algorithm_select.click()
            self.locator("div.el-select-dropdown:visible li").filter(
                has_text=re.compile(rf"^{re.escape(balance_method)}$")
            ).click()

            # 会话保持（仅非源IP算法时）
            if balance_method != "源IP":
                session_radio = dialog.locator("div.el-form-item").filter(
                    has_text=re.compile(r"会话保持")
                )
                if session_persistence:
                    session_radio.get_by_role("radio", name="激活").click()
                    # 选择会话保持类型
                    type_select = dialog.locator("div.el-form-item").filter(
                        has_text=re.compile(r"类型")
                    ).get_by_placeholder("请选择")
                    type_select.click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text="SOURCE IP"
                    ).click()
                else:
                    session_radio.get_by_role("radio", name="禁用").click()

            # 健康检查器
            health_radio = dialog.locator("div.el-form-item").filter(
                has_text=re.compile(r"健康检查器")
            )
            if health_check:
                health_radio.get_by_role("radio", name="激活").click()
                # 选择健康检查类型
                type_select = dialog.locator("div.el-form-item").filter(
                    has_text=re.compile(r"类型")
                ).get_by_placeholder("请选择")
                type_select.click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(rf"^{re.escape(health_type)}$")
                ).click()

                if health_type in ("HTTP", "HTTPS"):
                    # HTTP(S)方法
                    method_select = dialog.locator("div.el-form-item").filter(
                        has_text=re.compile(r"HTTP\(S\)方法")
                    ).get_by_placeholder("请选择")
                    method_select.click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text=re.compile(rf"^{re.escape(http_method)}$")
                    ).click()

                    # URL地址
                    dialog.locator("div.el-form-item").filter(
                        has_text=re.compile(r"URL地址")
                    ).get_by_role("textbox").fill(url_path)
            else:
                health_radio.get_by_role("radio", name="禁用").click()

            # 点击确定
            dialog.get_by_text("确定", exact=True).click()
            self.logger.info(
                f"资源池创建完成: {pool_name}, 算法={balance_method}, "
                f"健康检查={health_check}"
            )
        except Exception:
            # 失败时关闭对话框，避免遮挡后续teardown操作
            try:
                dialog.get_by_text("取消", exact=True).click()
            except Exception:
                pass
            raise

    def lb_pool_add_vm(self, vm_names, lb_name=None, pool_name=None, resource_type="弹性云服务器 ECS", ports=None, weights=None):
        """在监听器资源池详情页中新增虚机资源

        Args:
            vm_names: 虚机名称，支持单个字符串或名称列表
            lb_name: 监听器名称，传入时会先自动进入该监听器
            pool_name: 资源池名称，和 lb_name 一起传入时会自动进入资源池详情
            resource_type: 资源类型，默认"弹性云服务器 ECS"
            ports: 资源端口配置，支持单个端口值、与 vm_names 顺序对应的列表，或 {vm_name: port} 字典
            weights: 成员权重配置，支持单个权重值、与 vm_names 顺序对应的列表，或 {vm_name: weight} 字典。
                仅在负载调度算法为"加权轮询"时生效，权重范围1~100。
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

        def resolve_weight(vm_name, index):
            if weights is None:
                return None
            if isinstance(weights, dict):
                return weights.get(vm_name)
            if isinstance(weights, (list, tuple)):
                return weights[index]
            return weights

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
            self._expand_page_size("50")
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

            target_weight = resolve_weight(vm_name, index)
            if target_weight is not None:
                spinbuttons = row.get_by_role("spinbutton").all()
                if len(spinbuttons) >= 2:
                    weight_input = spinbuttons[1]
                    weight_input.fill(str(target_weight))
                    self.logger.info(f"资源池新增虚机时已设置权重: {vm_name} -> {target_weight}")

        if missing_vms:
            raise AssertionError(f"新建资源弹窗当前可选列表中未找到虚机: {missing_vms}")

        self.dialog_confirm.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)
        self.logger.info(f"资源池新增虚机提交成功: vm_names={vm_names}, resource_type={resource_type}, ports={ports}")

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
            self.wait_for_page_ready()
            self.logger.info(f"资源池成员删除成功: {vm_name}")

    def lb_pool_disable_vm(self, vm_names, lb_name=None, pool_name=None):
        """在资源池详情页禁用已添加的虚机成员。

        Args:
            vm_names: 待禁用的虚机名称，支持单个字符串或名称列表。
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
            self.click_action(vm_name, "禁用")
            self.dialog_confirm.click()
            self.wait_for_page_ready()
            self.logger.info(f"资源池成员禁用成功: {vm_name}")

    def lb_pool_activate_vm(self, vm_names, lb_name=None, pool_name=None):
        """在资源池详情页激活已禁用的虚机成员。

        Args:
            vm_names: 待激活的虚机名称，支持单个字符串或名称列表。
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
            self.click_action(vm_name, "激活")
            self.dialog_confirm.click()
            self.wait_for_page_ready()
            self.logger.info(f"资源池成员激活成功: {vm_name}")

    def lb_pool_config_health_check(self, lb_name, pool_name, enable=True,
                                    health_type=None, health_request=None,
                                    health_expected_response=None,
                                    http_method=None, url_path=None):
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
            http_method: HTTP/HTTPS 类型时的 HTTP 方法，如 ``GET``、``HEAD``。
            url_path: HTTP/HTTPS 类型时的 URL 地址，如 ``/index.html``。
        """
        self.goto_lb_pool_detail(lb_name, pool_name)
        page_root = self.locator("#cloud-container-content")

        # 点击健康检查区域的"配置"按钮
        # 页面上有两个"配置"链接（会话保持、健康检查），
        # 健康检查的在 DOM 顺序中排在第二个，使用 nth(1) 精确定位。
        config_btn = page_root.locator("a:has-text('配置')").nth(1)
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

            # HTTP/HTTPS 类型时配置 HTTP 方法和 URL 地址
            if health_type in ("HTTP", "HTTPS"):
                if http_method:
                    method_select = form_items.filter(has_text="HTTP(S)方法").get_by_placeholder("请选择")
                    if method_select.is_visible() and not method_select.evaluate("el => el.disabled"):
                        method_select.click()
                        self.locator("div.el-select-dropdown:visible li").filter(
                            has_text=re.compile(rf"^{re.escape(http_method)}$")
                        ).click()
                if url_path:
                    url_input = form_items.filter(has_text="URL地址").get_by_role("textbox")
                    if url_input.is_visible() and not url_input.evaluate("el => el.disabled"):
                        url_input.fill(url_path)

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
            refresh: 是否主动点击刷新按钮，默认True。

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
                except Exception:
                    # 刷新按钮不可用时，降级为重新导航
                    self.goto_lb_pool_detail(lb_name, pool_name, force=True)

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

    def lb_pool_edit_weight(self, vm_names, weights, lb_name=None, pool_name=None):
        """在资源池详情页修改已添加虚机成员的权重。

        Args:
            vm_names: 待修改权重的虚机名称，支持单个字符串或名称列表。
            weights: 权重配置，支持单个权重值、与 vm_names 顺序对应的列表，
                或 {vm_name: weight} 字典。权重范围 1~100。
            lb_name: 监听器名称；和 ``pool_name`` 一起传入时，会先自动进入资源池详情页。
            pool_name: 资源池名称；和 ``lb_name`` 一起传入时，会先自动进入资源池详情页。
        """
        if isinstance(vm_names, str):
            vm_names = [vm_names]

        def resolve_weight(vm_name, index):
            if weights is None:
                return None
            if isinstance(weights, dict):
                return weights.get(vm_name)
            if isinstance(weights, (list, tuple)):
                return weights[index]
            return weights

        if lb_name and pool_name:
            self.goto_lb_pool_detail(lb_name, pool_name)
        elif lb_name or pool_name:
            raise ValueError("lb_name 和 pool_name 需要同时传入，或者都不传")

        for index, vm_name in enumerate(vm_names):
            target_weight = resolve_weight(vm_name, index)
            if target_weight is None:
                continue

            self.click_action(vm_name, "修改权重")

            dialog = self.get_by_role("dialog", name="修改资源权重")
            expect(dialog).to_be_visible(timeout=5000)

            weight_input = dialog.locator("div.el-form-item").filter(
                has_text=re.compile(r"权重")
            ).get_by_role("spinbutton")
            expect(weight_input).to_be_visible(timeout=3000)
            weight_input.fill(str(target_weight))

            dialog.get_by_text("确定", exact=True).click()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1500)
            self.logger.info(f"资源池成员权重修改成功: {vm_name} -> {target_weight}")

    def lb_pool_config_session_persistence(self, lb_name, pool_name, enable=True, session_type=None):
        """在资源池详情页配置会话保持。

        弹窗内会话保持主控为 ``el-switch``（label="是否开启"），
        开启后显示类型选择下拉框。

        Args:
            lb_name: 监听器名称。
            pool_name: 资源池名称。
            enable: 是否开启会话保持，默认 True。
            session_type: 会话保持类型，如 ``SOURCE IP``、``HTTP COOKIE``。
                开启会话保持时必须提供。
        """
        self.goto_lb_pool_detail(lb_name, pool_name)
        page_root = self.locator("#cloud-container-content")

        # 点击会话保持区域的"配置"按钮
        # 资源池详情页的"配置"链接按 DOM 顺序为：会话保持、健康检查、负载调度算法
        # 会话保持的配置链接始终是第一个
        config_links = page_root.locator("a").filter(
            has_text=re.compile(r"^\s*配置\s*$")
        )
        count = config_links.count()
        self.logger.info(f"会话保持配置: 页面找到 {count} 个'配置'链接")
        if count == 0:
            raise RuntimeError("无法定位会话保持的'配置'链接")
        config_link = config_links.nth(0)

        expect(config_link).to_be_visible(timeout=5000)
        config_link.click()

        dialog = self.get_by_role("dialog", name="配置会话保持")
        expect(dialog).to_be_visible(timeout=10000)

        # 切换会话保持开关（控件为 el-switch，直接在弹窗内查找）
        switch_ctrl = dialog.locator(".el-switch").first
        expect(switch_ctrl).to_be_visible(timeout=10000)

        is_checked = switch_ctrl.evaluate("el => el.classList.contains('is-checked')")
        if enable != is_checked:
            switch_ctrl.click()

        if enable:
            if not session_type:
                raise ValueError("开启会话保持时，必须提供 session_type (例如: 'SOURCE IP', 'HTTP COOKIE')")
            # 类型选择：在包含"类型"标签的 form-item 中查找下拉框
            type_select = dialog.locator("div.el-form-item").filter(has_text="类型").get_by_placeholder("请选择")
            if type_select.is_visible() and not type_select.evaluate("el => el.disabled"):
                type_select.click()
                self.locator("div.el-select-dropdown:visible li").filter(
                    has_text=re.compile(rf"^{re.escape(session_type)}$")
                ).click()

        dialog.get_by_text("确定", exact=True).click()
        self.assert_popup_success()
        self.logger.info(
            f"会话保持配置完成: lb={lb_name}, pool={pool_name}, "
            f"enable={enable}, session_type={session_type}"
        )

    def lb_pool_config_balance_method(self, balance_method, lb_name=None, pool_name=None):
        """在资源池详情页修改负载调度算法。

        Args:
            balance_method: 负载调度算法中文名，可选"轮询"、"加权轮询"、"源IP"、"最小连接数"。
            lb_name: 监听器名称；和 ``pool_name`` 一起传入时，会先自动进入资源池详情页。
            pool_name: 资源池名称；和 ``lb_name`` 一起传入时，会先自动进入资源池详情页。
        """
        if lb_name and pool_name:
            self.goto_lb_pool_detail(lb_name, pool_name)
        elif lb_name or pool_name:
            raise ValueError("lb_name 和 pool_name 需要同时传入，或者都不传")

        page_root = self.locator("#cloud-container-content")

        # 在"负载调度算法"行点击"配置"链接
        # 资源池详情页的"配置"链接按 DOM 顺序为：会话保持、健康检查、负载调度算法
        # 负载调度算法的配置链接始终是最后一个
        config_links = page_root.locator("a").filter(
            has_text=re.compile(r"^\s*配置\s*$")
        )
        count = config_links.count()
        self.logger.info(f"负载调度算法配置: 页面找到 {count} 个'配置'链接")
        if count == 0:
            raise RuntimeError("无法定位负载调度算法的'配置'链接")
        config_link = config_links.nth(count - 1)

        expect(config_link).to_be_visible(timeout=5000)
        config_link.click()

        dialog = self.get_by_role("dialog", name="修改负载调度算法")
        expect(dialog).to_be_visible(timeout=5000)

        # 选择负载调度算法
        algorithm_select = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"负载调度算法")
        ).get_by_placeholder("请选择")
        algorithm_select.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(balance_method)}$")
        ).click()

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()
        self.logger.info(f"负载调度算法修改成功: {balance_method}")

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
            self._expand_page_size("50")
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
