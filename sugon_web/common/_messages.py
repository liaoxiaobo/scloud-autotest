from sugon_web.common.playwright import expect


class MessagesMixin:
    """页面消息/弹窗断言 Mixin。

    提供对 Element UI 消息提示（顶部 toast 和右下角 alert）的断言能力。
    设计为与 ElementsMixin 组合使用，依赖 self.popup。
    """

    def assert_popup_success(self, text=None, timeout=10):
        """公共方法: 根据弹窗文本和类型，断言操作成功

        Args:
            text: 期望的弹窗文本内容（可选）
            timeout: 超时时间（秒）
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        popup_text = popup.inner_text().strip()
        is_success = popup.evaluate(
            "element => element.parentElement.classList.contains('el-message--success')"
        )

        if not is_success:
            raise AssertionError(f"预期操作成功，但实际失败。弹窗文本: {popup_text}")

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)

    def assert_popup_error(self, text=None, timeout=5):
        """公共方法: 根据弹窗文本和类型，断言操作失败

        Args:
            text: 期望的弹窗文本内容（可选）
            timeout: 超时时间（秒）
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        popup_text = popup.inner_text().strip()
        is_error = popup.evaluate(
            "element => element.parentElement.classList.contains('el-message--error')"
        )

        if not is_error:
            raise AssertionError(f"预期操作失败，但实际成功或其他状态。弹窗文本: {popup_text}")

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)
