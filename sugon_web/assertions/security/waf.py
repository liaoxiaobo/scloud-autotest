import time


class WafAssertionMixin:
    """WEB应用防火墙WAF 业务断言 Mixin。

    验证 WAF 实例的服务状态与虚拟机状态收敛。
    属于 L3 Consistency 层断言。
    """

    def assert_waf_status(self, name: str, service_status: str = "运行", vm_status: str = "运行", timeout: int = 300) -> dict:
        """断言 WAF 实例的服务状态与虚拟机状态。

        Args:
            name: 实例名称
            service_status: 期望的服务状态，默认"运行"
            vm_status: 期望的虚拟机状态，默认"运行"
            timeout: 超时时间（秒），默认 300

        Returns:
            dict: 状态收敛时的行数据字典

        Raises:
            AssertionError: 超时后状态仍未收敛到期望值
        """
        start_time = time.time()
        last_data = {}
        while time.time() - start_time < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                last_data = row_data
                svc = row_data.get("服务状态", "")
                vmst = row_data.get("虚拟机状态", "")
                if service_status in svc and vm_status in vmst:
                    self.logger.info(f"WAF 实例 {name} 状态符合预期: 服务={svc}, 虚拟机={vmst}")
                    return row_data
            except Exception as e:
                self.logger.debug(f"读取 WAF 实例 {name} 状态失败: {e}")
            time.sleep(5)
        raise AssertionError(
            f"[StatusAssertion] WAF '{name}' | 状态未收敛 | "
            f"期望: 服务={service_status}, 虚拟机={vm_status} | "
            f"实际={last_data}"
        )
