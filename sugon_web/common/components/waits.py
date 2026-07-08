"""
【职责】提供页面加载就绪、操作完成、资源中间态完成等等待策略，以及顶部/右下角弹窗定位。

【层级】Page 层；被 BasePage 组合，page object 通过 BasePage 间接使用。

【接口】
- wait_for_page_ready()：等待 DOM、资源、Element UI loading 遮罩消失。
- wait_for_operation_complete(timeout=60)：等待 loading 图标/按钮 loading 状态消失。
- wait_for_source_complete(name, loading_timeout=10, complete_timeout=180)：等待资源行中间态图标出现并消失。
- popup -> Locator：页面顶部弹窗（.el-message__content）。
- alert -> Locator：页面右下角弹窗。

【注意】wait_for_page_ready / wait_for_operation_complete 在 Playwright 类中有同名实现，
BasePage 的 MRO 中 Playwright 优先，页面对象实际调用的是 Playwright 版本
（wait_for_operation_complete 默认 timeout=30）。本 Mixin 的同名方法仅在未继承 Playwright 时生效。

【示例】
class MyPage(BasePage):
    def create_and_wait(self, name):
        self.btn_create.click()
        self.input_name().fill(name)
        self.btn_submit.click()
        self.wait_for_operation_complete(timeout=120)
"""

import time

from playwright.sync_api import expect


class WaitsMixin:
    """页面与操作等待 Mixin。

    提供页面加载就绪、操作完成、悬浮提示清理等等待策略。
    设计为与 Playwright 组合使用，依赖 self.page 和 self.logger。
    """

    @property
    def popup(self):
        """公共元素: 页面顶部弹窗"""
        return self.locator(".el-message__content")

    @property
    def alert(self):
        """公共元素: 页面右下角弹窗"""
        return self.get_by_role("alert")

    def wait_for_page_ready(self) -> None:
        """等待页面完全就绪。

        依次等待：
        1. DOM 加载完成（domcontentloaded）
        2. 页面资源加载完成（load）
        3. 所有 Element UI loading 遮罩（.el-loading-spinner）消失

        注意：本方法在 BasePage 中优先级低于 Playwright.wait_for_page_ready()，
        实际调用的是 Playwright 中的实现（顺序略有不同）。
        保留本实现是为了在单独使用 WaitsMixin 时仍可正常工作。
        """
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_load_state("load")
        # 轮询等待所有 Element UI loading 遮罩消失（包括异步出现的）
        for _ in range(120):
            spinners = self.page.locator(".el-loading-spinner:visible")
            if spinners.count() == 0:
                break
            self.page.wait_for_timeout(500)

    def wait_for_source_complete(self, name: str, loading_timeout: int = 10, complete_timeout: int = 180) -> None:
        """等待资源状态加载完成

        Args:
            name: 资源名称
            loading_timeout: 等待loading_selector出现的超时时间（秒），默认10秒
            complete_timeout: 等待loading_selector消失的超时时间（秒），默认180秒
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        loading_timeout_ms = loading_timeout * 1000
        complete_timeout_ms = complete_timeout * 1000
        target_row = self.get_row_by_name(name)
        loading_icon = target_row.locator(".icon-dengdaizhong")
        try:
            loading_icon.wait_for(state="visible", timeout=loading_timeout_ms)
        except PlaywrightTimeoutError:
            self.logger.info(f"{name}资源中间态完成，当前无任务状态")
            return

        text = loading_icon.locator("xpath=./following-sibling::span").inner_text()
        try:
            expect(loading_icon).not_to_be_visible(timeout=complete_timeout_ms)
        except AssertionError:
            raise AssertionError(
                f"{name}资源中间态 {text} 未在 {complete_timeout} 秒内完成"
            ) from None
        self.logger.info(f"{name}资源中间态 {text} 出现并消失")

    def wait_for_batch_source_complete(
        self,
        names: list[str],
        loading_timeout: int = 15,
        complete_timeout: int = 180,
    ) -> None:
        """等待批量资源操作的中间态完成。

        与 wait_for_source_complete 不同：批量操作是并行下发的，不能串行等待
        每个资源的 loading 图标出现再消失，否则后面的资源可能已经被错过。

        Args:
            names: 资源名称列表
            loading_timeout: 轮询等待每个资源 loading 图标出现的超时（秒）
            complete_timeout: 等待所有 loading 图标消失的超时（秒）
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        start = time.time()
        rows = {name: self.get_row_by_name(name) for name in names}
        icons = {name: row.locator(".icon-dengdaizhong") for name, row in rows.items()}

        # 阶段1：轮询，尽量让每台资源都进入过 loading 状态
        pending = set(names)
        phase1_deadline = time.time() + loading_timeout
        while pending and time.time() < phase1_deadline:
            for name in list(pending):
                try:
                    if icons[name].is_visible():
                        pending.remove(name)
                except PlaywrightTimeoutError:
                    pass
            if pending:
                time.sleep(0.1)

        if pending:
            if len(pending) == len(names):
                raise AssertionError(
                    f"批量操作未触发任何资源的中间态 loading 图标: {names}，"
                    "可能操作未下发或 loading 消失过快"
                )
            self.logger.warning(
                f"以下资源未观察到中间态 loading 图标: {pending}，"
                "可能操作已完成或该资源未进入中间态"
            )

        # 阶段2：等待所有仍在 loading 的图标消失
        phase2_deadline = time.time() + complete_timeout
        while time.time() < phase2_deadline:
            try:
                visible = [name for name in names if icons[name].is_visible()]
            except PlaywrightTimeoutError:
                visible = []
            if not visible:
                self.logger.info(f"批量资源中间态完成: {names}")
                return
            time.sleep(1)

        raise AssertionError(
            f"批量资源中间态未在 {complete_timeout} 秒内完成，"
            f"仍在 loading: {visible}"
        )

    def wait_for_operation_complete(self, timeout: int = 61) -> None:
        """等待页面操作完成。

        轮询检测以下加载标识是否全部消失：
        - .el-icon-loading:visible（Element UI 加载图标）
        - .el-button.is-loading:visible（加载中按钮）

        注意：本方法在 BasePage 中优先级低于 Playwright.wait_for_operation_complete()，
        实际调用的是 Playwright 中的实现。保留本实现是为了在单独使用 WaitsMixin 时仍可正常工作。

        Args:
            timeout: 超时时间（秒）
        """
        start_time = time.time()
        loading_selector = ".el-icon-loading:visible, .el-button.is-loading:visible"

        while time.time() - start_time < timeout:
            try:
                if self.page.locator(loading_selector).count() == 0:
                    return
                time.sleep(1)
            except Exception as e:
                self.logger.debug(f"等待操作完成时出错: {e}")
                time.sleep(1)

        raise AssertionError(f"等待操作完成超时，超过 {timeout} 秒")
