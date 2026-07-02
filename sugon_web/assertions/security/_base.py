"""安全合规模块通用断言 Mixin。"""
import time


class SecurityStatusAssertionMixin:
    """安全服务实例状态收敛的通用断言 Mixin。

    原 AptAssertionMixin / RasAssertionMixin / UsmAssertionMixin /
    VdbAssertionMixin / VerAssertionMixin / WafAssertionMixin / WptAssertionMixin
    均基于本类提供各自同名方法，保持现有 Page Object 调用方式不变。

    属于 L3 Consistency 层断言。
    """

    def assert_security_status(
        self,
        name: str,
        service_status: str = "运行",
        vm_status: str = "运行",
        timeout: int = 300,
        service_label: str = "Security",
    ) -> dict:
        """断言安全服务实例的服务状态与虚拟机状态收敛。

        Args:
            name: 实例名称。
            service_status: 期望的服务状态，默认"运行"。
            vm_status: 期望的虚拟机状态，默认"运行"。
            timeout: 超时时间（秒），默认 300。
            service_label: 服务标识，仅用于日志/错误信息。

        Returns:
            dict: 状态匹配时的行数据字典。
        """
        start_time = time.time()
        last_data = {}
        iteration = 0
        while time.time() - start_time < timeout:
            iteration += 1
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                last_data = row_data

                svc = str(row_data.get("服务状态", "")).strip()
                vmst = str(row_data.get("虚拟机状态", "")).strip()

                self.logger.info(
                    f"{service_label} 状态检查 #{iteration}: "
                    f"服务状态='{svc}', 虚拟机状态='{vmst}', "
                    f"期望=({service_status},{vm_status}), "
                    f"耗时={int(time.time() - start_time)}s"
                )
                svc_match = (
                    service_status in svc
                    or svc in service_status
                    or service_status == svc
                )
                vm_match = (
                    vm_status in vmst
                    or vmst in vm_status
                    or vm_status == vmst
                )
                if svc_match and vm_match:
                    self.logger.info(
                        f"{service_label} 实例 {name} 状态符合预期: "
                        f"服务={svc}, 虚拟机={vmst}"
                    )
                    return row_data
            except Exception as e:
                self.logger.warning(
                    f"读取 {service_label} 实例 {name} 状态失败 "
                    f"(第{iteration}次): {e}"
                )
            time.sleep(5)
        raise AssertionError(
            f"[StatusAssertion] {service_label} '{name}' | 状态未收敛 | "
            f"期望: 服务={service_status}, 虚拟机={vm_status} | "
            f"实际={last_data}, 共检查{iteration}次, "
            f"耗时{int(time.time() - start_time)}s"
        )
