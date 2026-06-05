import time


class VdbAssertionMixin:
    """数据库审计 VDB 业务断言 Mixin。

    验证 VDB 实例的服务状态与虚拟机状态收敛。
    属于 L3 Consistency 层断言。
    """

    def assert_vdb_status(self, name: str, service_status: str = "运行", vm_status: str = "运行", timeout: int = 300) -> dict:
        """断言 VDB 实例的服务状态与虚拟机状态。

        Args:
            name: 实例名称
            service_status: 期望的服务状态
            vm_status: 期望的虚拟机状态
            timeout: 超时时间（秒）

        Returns:
            dict: 匹配时的行数据字典
        """
        start_time = time.time()
        last_data = {}
        iteration = 0
        while time.time() - start_time < timeout:
            iteration += 1
            try:
                current_url = self.page.url
                if "/vdb" not in current_url or "create-vdb" in current_url or "detail" in current_url:
                    self.goto_service(self.service_name)
                else:
                    self.page.reload()
                self.wait_for_page_ready()
                try:
                    self.page.wait_for_selector(".el-table__body-wrapper table tbody tr td:nth-child(2)", timeout=10000)
                except Exception:
                    pass
                row_data = self.get_row_data(name)
                last_data = row_data

                svc = str(row_data.get("服务状态", "")).strip()
                vmst = str(row_data.get("虚拟机状态", "")).strip()

                self.logger.info(f"VDB 状态检查 #{iteration}: 服务状态='{svc}', 虚拟机状态='{vmst}', 期望=({service_status},{vm_status}), 耗时={int(time.time()-start_time)}s")
                svc_match = service_status in svc or svc in service_status or service_status == svc
                vm_match = vm_status in vmst or vmst in vm_status or vm_status == vmst
                if svc_match and vm_match:
                    self.logger.info(f"VDB 实例 {name} 状态符合预期: 服务={svc}, 虚拟机={vmst}")
                    return row_data
            except Exception as e:
                self.logger.warning(f"读取 VDB 实例 {name} 状态失败 (第{iteration}次): {e}")
            time.sleep(5)
        raise AssertionError(
            f"[StatusAssertion] VDB '{name}' | 状态未收敛 | "
            f"期望: 服务={service_status}, 虚拟机={vm_status} | "
            f"实际={last_data}, 共检查{iteration}次, 耗时{int(time.time()-start_time)}s"
        )
