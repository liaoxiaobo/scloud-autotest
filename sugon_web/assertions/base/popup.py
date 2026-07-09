import time

from sugon_web.common.playwright import expect


class PopupAssertionMixin:
    """弹窗/Toast/对话框断言 Mixin。

    验证 UI 操作后的即时反馈，包括成功提示、失败提示、对话框错误信息等。
    属于 L1 Presentation 层断言。
    """

    def assert_popup_success(self, text=None, timeout=10):
        """断言操作成功 toast 出现并消失。

        等待任意 toast 出现后，一次性读取文本并判断是否为 success，
        避免 `inner_text()` 与 `evaluate()` 分两步执行时 toast 消失导致踩空。

        Args:
            text: 期望 toast 包含的文案，为 None 时仅断言弹窗出现。
            timeout: 最长等待秒数，默认 10。
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        # 一次 evaluate 同时读取文本并判断 success（替代 inner_text + evaluate 两步）
        popup_text, is_success = popup.first.evaluate("""element => {
            const parent = element.parentElement;
            return [
                (element.innerText || '').trim(),
                parent ? parent.classList.contains('el-message--success') : false
            ];
        }""")

        if not is_success:
            raise AssertionError(
                f"[PopupAssertion] 弹窗 | 操作状态不匹配 | "
                f"期望: 成功 | 实际: 失败 | 弹窗文本: {popup_text}"
            )

        if text and text not in popup_text:
            raise AssertionError(
                f"[PopupAssertion] 弹窗 | 文案不匹配 | "
                f"期望包含: {text} | 实际: {popup_text}"
            )

        expect(popup).not_to_be_visible(timeout=timeout_ms)
        self.logger.info("断言通过: 成功弹窗出现" + (f", 文案包含 '{text}'" if text else ""))

    def assert_popup_error(self, text=None, timeout=5):
        """断言操作失败弹窗/Toast 出现并消失。

        Args:
            text: 期望弹窗包含的文案，为 None 时仅断言弹窗出现。
            timeout: 最长等待秒数，默认 5。
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        popup_text = popup.inner_text().strip()
        is_error = popup.evaluate(
            "element => element.parentElement.classList.contains('el-message--error')"
        )
        if not is_error:
            raise AssertionError(
                f"[PopupAssertion] 弹窗 | 操作状态不匹配 | "
                f"期望: 失败 | 实际: 成功或其他状态 | 弹窗文本: {popup_text}"
            )

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)
        self.logger.info(f"断言通过: 失败弹窗出现" + (f", 文案包含 '{text}'" if text else ""))

    def assert_dialog_error(self, *expected_texts):
        """断言对话框内错误提示文案。

        适用于表单提交后对话框内显示的错误信息（如校验失败）。

        Args:
            *expected_texts: 期望对话框中包含的错误文案（可变参数，至少一个）。
        """
        dialog = self.page.locator(".one-dialog-box")
        dialog.wait_for(state="visible", timeout=5000)
        for text in expected_texts:
            expect(dialog).to_contain_text(text, timeout=5000)
        self.logger.info(f"断言通过: 对话框错误文案校验成功: {expected_texts}")
