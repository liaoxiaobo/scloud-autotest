import time

from sugon_web.common.playwright import expect


class PopupAssertionMixin:
    """弹窗/Toast/对话框断言 Mixin。

    验证 UI 操作后的即时反馈，包括成功提示、失败提示、对话框错误信息等。
    属于 L1 Presentation 层断言。
    """

    def assert_popup_success(self, text=None, timeout=10):
        """断言操作成功 toast 出现（兼容自动消失的瞬时 toast）。

        成功类与文案在同一轮询循环内一次性校验，避免对寿命约 3s 的 toast
        做多段串行往返（visible→inner_text→evaluate→contain_text）而中途踩空。

        Args:
            text: 期望 toast 包含的文案，为 None 时仅断言出现成功 toast。
            timeout: 最长等待秒数，默认 10。
        """
        timeout_ms = timeout * 1000
        # 同时锁定「成功类 + 目标文案」
        success_popup = self.locator(".el-message--success .el-message__content")
        try:
            if text:
                expect(success_popup).to_contain_text(text, timeout=timeout_ms)
            else:
                expect(success_popup).to_be_visible(timeout=timeout_ms)
        except AssertionError:
            # 兜底诊断：区分「出现了错误 toast」与「压根没等到 toast」
            any_popup = self.popup
            if any_popup.count() > 0:
                raise AssertionError(
                    f"[PopupAssertion] 弹窗 | 操作状态不匹配 | "
                    f"期望: 成功{f'(含 {text})' if text else ''} | "
                    f"实际 toast: {any_popup.first.inner_text().strip()}"
                )
            raise AssertionError(
                f"[PopupAssertion] 弹窗 | 未捕获成功 toast | "
                f"期望: 成功{f'(含 {text})' if text else ''} | "
                f"{timeout}s 内未出现 .el-message--success"
            )
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
