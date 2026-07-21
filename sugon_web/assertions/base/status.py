import re
import time

from sugon_web.common.playwright import expect


_FAILURE_STATUSES = ("任务失败", "错误", "创建失败", "启动失败")


class StatusAssertionMixin:
    """资源状态断言 Mixin。

    验证资源从中间态到终态的收敛，以及目标状态是否正确。
    属于 L3 Consistency 层断言。
    """

    def assert_status(
        self,
        names,
        status="运行",
        timeout=300,
        refresh=False,
        refresh_interval=5,
        exit_on_failure=True,
    ):
        """断言资源状态达到预期值。

        支持轮询等待，直到状态匹配或超时；默认遇到失败终态（任务失败、错误、创建失败、
        启动失败）时立即退出，避免空等满超时时间。

        Args:
            names: 资源名称或名称列表。
            status: 期望的状态值，默认"运行"。
            timeout: 最长等待秒数，默认 300。
            refresh: 是否自动刷新列表等待状态变化，默认 False。
            refresh_interval: 刷新间隔秒数，默认 5。
            exit_on_failure: 遇到失败终态时是否立即退出，默认 True。
                设为 False 时，失败终态被视为可恢复的中间态，不提前退出，继续轮询等待
                期望状态出现或超时（适用于状态可能短暂经过"错误"再收敛的场景）。
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

                    # 监听期望状态；exit_on_failure=True 时同时监听失败终态，
                    # 任意一种文本出现即结束 expect 等待
                    patterns = [re.escape(status)]
                    if exit_on_failure:
                        patterns += [re.escape(f) for f in _FAILURE_STATUSES]
                    expect(target_row).to_contain_text(
                        re.compile("|".join(patterns)),
                        timeout=timeout_ms,
                        use_inner_text=True,
                    )

                    actual_text = target_row.inner_text()
                    if exit_on_failure:
                        detected_failure = next(
                            (f for f in _FAILURE_STATUSES if f in actual_text), None
                        )
                    else:
                        detected_failure = None
                    if detected_failure:
                        self.logger.error(
                            f"资源状态验证失败: {name} -> 检测到失败终态 '{detected_failure}'"
                        )
                        failed_resources.append(
                            f"{name} | 期望: '{status}' | 实际: '{actual_text}' | "
                            f"失败终态: '{detected_failure}'"
                        )
                    else:
                        self.logger.info(f"资源状态验证成功: {name} -> {status}")
                else:
                    start_time = time.time()
                    current_status = "未知"
                    first_check = True
                    matched = False

                    while time.time() - start_time < timeout:
                        try:
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查状态: {name}")
                                except Exception as refresh_error:
                                    self.logger.warning(
                                        f"刷新页面失败，将继续检查状态: {refresh_error}"
                                    )

                            first_check = False

                            target_row = self.get_row_by_name(name)
                            current_status = target_row.inner_text()

                            detected_failure = next(
                                (f for f in _FAILURE_STATUSES if f in current_status),
                                None,
                            )
                            if exit_on_failure and detected_failure:
                                self.logger.error(
                                    f"资源状态验证失败: {name} -> 检测到失败终态 '{detected_failure}'"
                                )
                                failed_resources.append(
                                    f"{name} | 期望: '{status}' | 实际: '{current_status}' | "
                                    f"失败终态: '{detected_failure}'"
                                )
                                break

                            if status in current_status:
                                self.logger.info(f"资源状态验证成功: {name} -> {status}")
                                matched = True
                                break

                        except Exception as e:
                            self.logger.debug(f"检查状态时出错: {e}")

                        time.sleep(refresh_interval)
                    else:
                        if not matched:
                            failed_resources.append(
                                f"{name} | 期望: '{status}' | 实际: '{current_status}' | 超时未收敛"
                            )

            except Exception as e:
                self.logger.error(f"资源状态验证失败: {name} -> {status}, 错误: {e}")
                failed_resources.append(f"{name} | 期望: '{status}' | 错误: {str(e)}")

        if failed_resources:
            raise AssertionError(
                f"[StatusAssertion] 资源状态 | 状态收敛失败 | "
                f"详情: {'; '.join(failed_resources)}"
            )
