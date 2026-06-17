from sugon_web.common.playwright import expect


class SlbAssertionMixin:
    """SLB 业务断言 Mixin。

    验证监听器存在性、资源池信息、对话框错误等。
    属于 L2 Business 层断言。
    """

    def assert_listener_exists(self, lb_name, timeout=5000):
        """验证左侧列表是否存在指定名称的监听器（针对详情页监听器Tab）。

        Args:
            lb_name: 监听器名称。
            timeout: 等待超时时间（毫秒），默认 5000。
        """
        # 使用用户提供的 listener-left-list-item 容器进行精确匹配
        locator = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        # 确保可见
        locator.wait_for(state="visible", timeout=timeout)
        self.logger.info(f"验证监听器 {lb_name} 存在于左侧列表")

    def assert_listener_not_exists(self, lb_name, timeout=5000):
        """验证左侧列表不存在指定名称的监听器（针对详情页监听器Tab）。

        Args:
            lb_name: 监听器名称。
            timeout: 等待超时时间（毫秒），默认 5000。
        """
        locator = self.locator("div.listener-left-list-item").filter(has_text=lb_name)
        expect(locator).not_to_be_visible(timeout=timeout)
        self.logger.info(f"验证监听器 {lb_name} 已从左侧列表删除")

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
                    f"[FieldAssertion] 资源池成员 '{vm_name}' | 字段 '{field_name}' 不匹配 | "
                    f"期望: '{expected_value}' | 实际: '{actual_value}'"
                )

        for field_name in ["开关状态", "资源状态"]:
            actual_value = (row_data.get(field_name) or "").strip()
            if not actual_value:
                raise AssertionError(
                f"[FieldAssertion] 资源池成员 '{vm_name}' | 字段 '{field_name}' 为空 | "
                f"期望: 非空 | 实际: 空"
            )

        self.logger.info(f"资源池成员信息校验成功: {vm_name}, row_data={row_data}")
        return row_data

    def assert_slb_dialog_error(self, *expected_texts):
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
        """验证监听器详情页基本信息区域包含指定文本。

        Args:
            info_text: 期望在基本信息区域出现的文本。
        """
        nested_tabs = self._get_lb_nested_tabs()
        nested_tabs.get_by_role("tab", name="详情").click()

        active_pane = nested_tabs.locator(".el-tab-pane:not([aria-hidden='true'])").last
        active_pane.get_by_text("基本信息", exact=True).wait_for(state="visible", timeout=5000)
        expect(active_pane).to_contain_text(info_text)
        self.logger.info(f"验证监听器详情基本信息包含 {info_text} 成功")
