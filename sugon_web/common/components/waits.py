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
        loading_spinners = self.page.locator(".el-loading-spinner")
        count = loading_spinners.count()
        if count > 0:
            for i in range(count):
                loading_spinners.nth(i).wait_for(state='hidden')

    def wait_for_source_complete(self, name: str, loading_timeout: int = 10, complete_timeout: int = 180) -> None:
        """等待资源状态加载完成

        Args:
            name: 资源名称
            loading_timeout: 等待loading_selector出现的超时时间（秒），默认10秒
            complete_timeout: 等待loading_selector消失的超时时间（秒），默认180秒
        """
        loading_timeout_ms = loading_timeout * 1000
        complete_timeout_ms = complete_timeout * 1000
        target_row = self.get_row_by_name(name)
        loading_icon = target_row.locator(".icon-dengdaizhong")
        try:
            loading_icon.wait_for(state="visible", timeout=loading_timeout_ms)
            text = loading_icon.locator("xpath=./following-sibling::span").inner_text()
            expect(loading_icon).not_to_be_visible(timeout=complete_timeout_ms)
            self.logger.info(f"{name}资源中间态 {text} 出现并消失")
        except:
            self.logger.info(f"{name}资源中间态完成，当前无任务状态")

        expect(loading_icon).not_to_be_visible(timeout=complete_timeout_ms)

    def wait_for_operation_complete(self, timeout: int = 60) -> None:
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
