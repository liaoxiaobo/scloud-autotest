import time


class UsmAssertionMixin:
    """云堡垒机高级版 USM 业务断言 Mixin。

    验证 USM 实例的服务状态与虚拟机状态收敛。
    创建后若服务状态为"授权失败"，自动执行授权操作后继续等待。
    属于 L3 Consistency 层断言。
    """

    def assert_usm_status(self, name: str, service_status: str = "运行", vm_status: str = "运行", timeout: int = 300) -> dict:
        """断言 USM 实例的服务状态与虚拟机状态。

        创建后若服务状态为"授权失败"，自动执行授权操作（选择1个月购买时长），
        然后继续等待目标状态。

        Args:
            name: 实例名称
            service_status: 期望的服务状态，默认"运行"
            vm_status: 期望的虚拟机状态，默认"运行"
            timeout: 超时时间（秒），默认 300

        Returns:
            dict: 匹配时的行数据字典
        """
        start_time = time.time()
        last_data = {}
        authorized = False
        while time.time() - start_time < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                last_data = row_data
                svc = row_data.get("服务状态", "")
                vmst = row_data.get("虚拟机状态", "")
                if service_status in svc and vm_status in vmst:
                    self.logger.info(f"USM 实例 {name} 状态符合预期: 服务={svc}, 虚拟机={vmst}")
                    return row_data
                if "创建中" in vmst and "不可用" in svc:
                    self.logger.warning(f"USM 实例 {name} 创建失败（虚拟机=创建中, 服务=不可用），将自动清理并抛出异常供重新创建")
                    try:
                        self.usm_delete(name)
                        self.assert_deleted(name, timeout=120)
                        self.logger.info(f"USM 实例 {name} 已自动删除")
                    except Exception as del_err:
                        self.logger.warning(f"USM 实例 {name} 自动删除失败: {del_err}")
                    raise AssertionError(
                        f"USM 实例 {name} 创建失败（虚拟机状态=创建中, 服务状态=不可用），"
                        f"已自动清理，请重新创建"
                    )
                if not authorized and "授权失败" in svc and "创建中" not in vmst:
                    self.logger.info(f"USM 实例 {name} 服务状态为'授权失败'，执行授权操作")
                    authorized = True
                    try:
                        self._usm_authorize(name)
                        continue
                    except Exception as e:
                        self.logger.warning(f"USM 实例 {name} 自动授权失败: {e}")
            except Exception as e:
                self.logger.debug(f"读取 USM 实例 {name} 状态失败: {e}")
            time.sleep(5)
        raise AssertionError(
            f"[StatusAssertion] USM '{name}' | 状态未收敛 | "
            f"期望: 服务={service_status}, 虚拟机={vm_status} | "
            f"实际={last_data}"
        )
