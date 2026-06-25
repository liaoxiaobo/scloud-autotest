"""
【职责】封装对话框的确定、取消、关闭按钮，提供关闭残留弹窗及从抽屉中选择资源的通用能力。

【层级】Page 层；被 BasePage 组合，page object 通过 BasePage 间接使用。

【接口】
- dialog_confirm -> Locator：对话框“确定”按钮。
- dialog_cancel -> Locator：对话框“取消”按钮。
- dialog_close -> Locator：对话框右上角关闭按钮。
- close_dialog_if_exists()：若存在对话框则点击关闭，静默处理不存在的情况。
- _select_from_named_drawer(drawer_title, item_name, reset_first=False, open_drawer=True)：在抽屉中搜索并选择指定资源。

【示例】
class MyPage(BasePage):
    def delete_resource(self, name):
        self.click_action(name, "删除")
        self.dialog_confirm.click()

【前置依赖】调用 dialog_confirm 等属性前，需确保目标对话框已弹出。
"""

from typing import TYPE_CHECKING

from playwright.sync_api import Locator

from sugon_web.common.playwright import expect
from sugon_web.common.components.buttons import BaseElementMixin

if TYPE_CHECKING:
    from sugon_web.common.playwright import CustomLocator


class DialogsMixin(BaseElementMixin):
    """弹窗/对话框组件 Mixin。"""

    @property
    def dialog_confirm(self) -> Locator:
        """公共元素: 对话框确定按钮"""
        locators = [
            self.get_by_role("dialog").get_by_text("确定", exact=True),
            self.get_by_role("dialog").locator("span").filter(has_text="确定"),
            self.get_by_role("dialog").get_by_text("确定", exact=True).nth(1),
            self.locator("section").get_by_text("确定"),
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").first,
            self.locator(".sure-footer > div > .cloud-button-btn").first,
            self.get_by_label("虚拟IP管理").get_by_text("确定", exact=True)
        ]
        return self._find_element(locators, "对话框'确定'按钮")

    @property
    def dialog_cancel(self) -> Locator:
        """公共元素: 对话框取消按钮"""
        locators = [
            self.get_by_role("dialog").get_by_text("取消"),
            self.locator("div:nth-child(2) > div:nth-child(2) > .cloud-button-btn")
        ]
        return self._find_element(locators, "对话框'取消'按钮")

    @property
    def dialog_close(self) -> Locator:
        """公共元素: 对话框关闭按钮"""
        return self.get_by_role("button", name="Close")

    def close_dialog_if_exists(self) -> None:
        """关闭可能存在的对话框。

        依次尝试：Close 按钮、取消/关闭文字按钮、Escape 键。
        最多轮询 3 次，确保各类对话框（含无 Close 按钮的确认框）均被关闭。
        若当前没有对话框，静默通过不抛异常。
        """
        for _ in range(3):
            closed = False

            # 1. 尝试 Close 按钮（右上角 X）
            try:
                if self.dialog_close.is_visible():
                    self.logger.info("发现未关闭的对话框，正在关闭...")
                    self.dialog_close.click(timeout=5000, force=True)
                    self.page.wait_for_timeout(300)
                    closed = True
            except Exception:
                pass

            # 2. 尝试点击可见对话框中的"取消"或"关闭"按钮
            if not closed:
                try:
                    dialogs = self.page.locator(
                        ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible, .sugon-dialog:visible, .one-dialog-container:visible, .one-dialog-box:visible"
                    )
                    for i in range(min(dialogs.count(), 5)):
                        dialog = dialogs.nth(i)
                        for btn_text in ["取消", "关闭"]:
                            btn = dialog.locator(
                                "button, .el-button, .cloud-button-btn"
                            ).filter(has=self.page.get_by_text(btn_text, exact=True)).first
                            if btn.count() > 0 and btn.is_visible():
                                btn.click(force=True)
                                self.page.wait_for_timeout(300)
                                closed = True
                                break
                        if closed:
                            break
                except Exception:
                    pass

            # 3. Escape 降级
            if not closed:
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(300)
                except Exception:
                    pass

            # 检查是否还有可见对话框，没有则退出
            try:
                remaining = self.page.locator(
                    ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible, .sugon-dialog:visible, .one-dialog-container:visible, .one-dialog-box:visible"
                )
                if remaining.count() == 0:
                    break
            except Exception:
                break

    def _select_from_named_drawer(
        self,
        drawer_title: str,
        item_name: str,
        reset_first: bool = False,
        open_drawer: bool = True,
    ):
        """在指定抽屉中搜索并按名称精确选择资源。"""
        if open_drawer:
            self.get_by_text(drawer_title).first.click()
            self.page.wait_for_load_state("domcontentloaded")

        drawer = self.locator(f"div[role='dialog'][aria-label='{drawer_title}']:visible")
        expect(drawer).to_be_visible()

        if reset_first:
            reset_btn = drawer.locator(".cloud-table-header-right").get_by_text("重置", exact=True)
            if reset_btn.count() > 0 and reset_btn.first.is_visible():
                reset_btn.first.click()

        search_input = drawer.locator(".cloud-table-header-right input[placeholder='搜索（名称）']")
        if search_input.count() > 0:
            search_input.fill(item_name)
            drawer.locator(".cloud-table-header-right").get_by_text("搜索", exact=True).click()
            self.wait_for_page_ready()

        row = drawer.locator(
            "xpath=.//div[contains(@class,'el-table__body-wrapper')]//tr[.//td[2]//*[normalize-space(text())="
            f"'{item_name}'] or .//td[2][normalize-space(.)='{item_name}']]"
        ).first
        expect(row).to_be_visible(timeout=5000)

        select_locators = [
            drawer.locator(".el-table__fixed .el-radio__inner:visible").first,
            drawer.locator(".el-table__fixed label[role='radio']:visible").first,
            row.locator(".el-radio__inner"),
            row.locator("label[role='radio']"),
            row.get_by_role("radio"),
            row.locator("td").nth(1),
            row,
        ]
        confirm_btn = drawer.get_by_text("确定", exact=True)
        last_error = None

        for select_locator in select_locators:
            if select_locator.count() == 0:
                continue
            try:
                select_locator.click(force=True)
                self.page.wait_for_timeout(300)
                confirm_btn.click()
                try:
                    expect(drawer).not_to_be_visible(timeout=3000)
                    return
                except AssertionError:
                    last_error = AssertionError(f"{drawer_title} 抽屉未关闭，继续尝试其他选择节点")
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise AssertionError(f"未找到 {drawer_title} 中的 {item_name} 可选节点")
