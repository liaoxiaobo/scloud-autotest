import time

from sugon_web.common.playwright import expect


class StatusAssertionMixin:
    """资源状态断言 Mixin。

    验证资源从中间态到终态的收敛，以及目标状态是否正确。
    属于 L3 Consistency 层断言。
    """

    def assert_status(self, names, status="运行", timeout=300, refresh=False, refresh_interval=5):
        """断言资源状态达到预期值。

        支持轮询等待，直到状态匹配或超时。

        Args:
            names: 资源名称或名称列表。
            status: 期望的状态值，默认"运行"。
            timeout: 最长等待秒数，默认 300。
            refresh: 是否自动刷新列表等待状态变化，默认 False。
            refresh_interval: 刷新间隔秒数，默认 5。
        """
        if isinstance(names, str):
            names = [names]

        failed_resources = []

        for name in names:
            try:
                if not refresh:
                    timeout_ms = timeout * 1000
                    self.wait_for_page_ready()
                    target_row = self.get_row_by_name(name)
                    expect(target_row).to_contain_text(
                        status, timeout=timeout_ms, use_inner_text=True
                    )
                    self.logger.info(f"资源状态验证成功: {name} -> {status}")
                else:
                    start_time = time.time()
                    current_status = "未知"
                    first_check = True

                    while time.time() - start_time < timeout:
                        try:
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查状态: {name}")
                                except Exception as refresh_error:
                                    self.logger.warning(f"刷新页面失败，将继续检查状态: {refresh_error}")

                            first_check = False

                            target_row = self.get_row_by_name(name)
                            current_status = target_row.inner_text()

                            if status in current_status:
                                self.logger.info(f"资源状态验证成功: {name} -> {status}")
                                break

                        except Exception as e:
                            self.logger.debug(f"检查状态时出错: {e}")

                        time.sleep(refresh_interval)
                    else:
                        failed_resources.append(
                            f"{name} | 期望: '{status}' | 实际: '{current_status}'"
                        )

            except Exception as e:
                self.logger.error(f"资源状态验证失败: {name} -> {status}, 错误: {e}")
                failed_resources.append(f"{name} | 期望: '{status}' | 错误: {str(e)}")

        if failed_resources:
            raise AssertionError(
                f"[StatusAssertion] 资源状态 | 状态收敛失败 | "
                f"详情: {'; '.join(failed_resources)}"
            )
