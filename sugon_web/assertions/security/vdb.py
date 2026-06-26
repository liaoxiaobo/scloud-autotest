import time


class VdbAssertionMixin:
    """数据库审计 VDB 业务断言 Mixin。

    验证 VDB 实例的服务状态与虚拟机状态收敛。
    属于 L3 Consistency 层断言。
    """

    def assert_vdb_status(self, name: str, service_status: str = "运行", vm_status: str = "运行", timeout: int = 300) -> dict:
        """断言 VDB 实例的服务状态与虚拟机状态。

        创建后若服务状态为"授权失败"，自动执行授权操作（选择1个月购买时长）后继续等待。
        若出现"虚拟机=创建中"且"服务=不可用"，则判定创建失败并自动清理。

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
        authorized = False
        while time.time() - start_time < timeout:
            iteration += 1
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                last_data = row_data

                svc = str(row_data.get("服务状态", "")).strip()
                vmst = str(row_data.get("虚拟机状态", "")).strip()

                self.logger.info(
                    f"VDB 状态检查 #{iteration}: 服务状态='{svc}', 虚拟机状态='{vmst}', "
                    f"期望=({service_status},{vm_status}), 耗时={int(time.time()-start_time)}s"
                )

                svc_match = service_status in svc or svc in service_status or service_status == svc
                vm_match = vm_status in vmst or vmst in vm_status or vm_status == vmst
                if svc_match and vm_match:
                    self.logger.info(f"VDB 实例 {name} 状态符合预期: 服务={svc}, 虚拟机={vmst}")
                    return row_data

                # 创建失败快速退出：虚拟机=创建中 且 服务=不可用
                if "创建中" in vmst and "不可用" in svc:
                    self.logger.warning(
                        f"VDB 实例 {name} 创建失败（虚拟机=创建中, 服务=不可用），将自动清理并抛出异常"
                    )
                    try:
                        self.vdb_delete(name)
                        self.assert_deleted(name, timeout=120)
                        self.logger.info(f"VDB 实例 {name} 已自动删除")
                    except Exception as del_err:
                        self.logger.warning(f"VDB 实例 {name} 自动删除失败: {del_err}")
                    raise AssertionError(
                        f"VDB 实例 {name} 创建失败（虚拟机状态=创建中, 服务状态=不可用），"
                        f"已自动清理，请重新创建"
                    )

                # 授权失败自动重授权一次
                if not authorized and "授权失败" in svc and "创建中" not in vmst:
                    self.logger.info(f"VDB 实例 {name} 服务状态为'授权失败'，执行授权操作")
                    authorized = True
                    try:
                        self.vdb_authorize(name, "1个月")
                        continue
                    except Exception as e:
                        self.logger.warning(f"VDB 实例 {name} 自动授权失败: {e}")

            except Exception as e:
                self.logger.warning(f"读取 VDB 实例 {name} 状态失败 (第{iteration}次): {e}")
            time.sleep(5)
        raise AssertionError(
            f"[StatusAssertion] VDB '{name}' | 状态未收敛 | "
            f"期望: 服务={service_status}, 虚拟机={vm_status} | "
            f"实际={last_data}, 共检查{iteration}次, 耗时{int(time.time()-start_time)}s"
        )
