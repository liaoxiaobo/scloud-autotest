import re
from typing import TYPE_CHECKING

from playwright.sync_api import Locator

from sugon_web.common.playwright import expect

if TYPE_CHECKING:
    from sugon_web.common.playwright import CustomLocator


class ElementsMixin:
    """公共页面元素定位器 Mixin。

    提供页面通用 UI 元素的惰性定位器，支持多定位器兜底策略。
    设计为与 Playwright 组合使用，依赖 self.locator / self.get_by_text 等定位方法。
    """

    def _find_element(self, locators, element_name: str = "元素", timeout: int = 1000,
                      check_visible: bool = True, check_enabled: bool = False) -> "CustomLocator":
        """通用方法：从多个定位器中查找满足条件的元素。

        Args:
            locators: 定位器列表
            element_name: 元素名称，用于错误信息
            timeout: 等待超时时间（毫秒）
            check_visible: 是否检查元素可见
            check_enabled: 是否检查元素可用

        Returns:
            找到的定位器（CustomLocator）

        Raises:
            Exception: 未找到满足条件的元素
        """
        for locator in locators:
            try:
                if check_visible:
                    expect(locator).to_be_visible(timeout=timeout)
                if check_enabled:
                    expect(locator).to_be_enabled(timeout=timeout)
                return locator
            except Exception as e:
                self.logger.debug(f"检查{element_name}状态时出错: {e}")
                continue

        locator_strs = [str(loc) for loc in locators]
        raise Exception(f"定位失败：{element_name}未找到。尝试的定位器: {locator_strs}")

    @property
    def popup(self) -> Locator:
        """公共元素: 页面顶部弹窗"""
        return self.locator(".el-message__content")

    @property
    def alert(self) -> Locator:
        """公共元素: 页面右下角弹窗"""
        return self.get_by_role("alert")

    @property
    def btn_create(self) -> Locator:
        """公共元素: 新建按钮"""
        locators = [
            self.get_by_text("新建", exact=True),
            self.get_by_text("创建集群", exact=True)
        ]
        return self._find_element(locators, "新建按钮")

    @property
    def btn_submit(self) -> Locator:
        """公共元素: 表单提交按钮"""
        locators = [
            self.get_by_text("立即创建")
        ]
        return self._find_element(locators, "表单提交按钮")

    @property
    def _input_search(self) -> Locator:
        """公共元素: 搜索框"""
        locators = [
            self.get_by_role("textbox", name="搜索（规格名称）"),
            self.get_by_role("textbox", name="搜索（名称）"),
            self.get_by_role("textbox", name="搜索(名称)"),
            self.get_by_role("textbox", name="搜索（固定IP）"),
            self.get_by_role("textbox", name="搜索（公网IP）"),
            self.get_by_role("textbox", name="搜索（参数名称）"),
            self.get_by_role("textbox", name="搜索（快照名称）"),
            self.locator(".input-with-select > .el-input__inner"),
            self.get_by_role("textbox", name="请输入设备名称"),
            self.get_by_role("textbox", name="搜索(实例名称)"),
            self.get_by_placeholder("搜索(目的地址)")
        ]
        return self._find_element(locators, "搜索框")

    @property
    def _btn_search(self) -> Locator:
        """公共元素: 搜索按钮"""
        locators = [
            self.locator(".el-dialog__wrapper:visible").get_by_text("搜索", exact=True),
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("搜索", exact=True),
            self.get_by_text("搜索", exact=True)
        ]
        return self._find_element(locators, "搜索按钮")

    @property
    def btn_reset(self) -> Locator:
        """公共元素: 重置按钮"""
        locators = [
            self.locator(".el-dialog__wrapper:visible").get_by_text("重置", exact=True),
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("重置", exact=True),
            self.get_by_text("重置", exact=True).first
        ]
        return self._find_element(locators, "重置按钮")

    @property
    def btn_refresh(self) -> Locator:
        """公共元素: 刷新按钮"""
        locators = [
            self.locator("#serverRefresh"),
            self.locator("#SpecificationRefresh").nth(1),
            self.locator(".el-icon-refresh")
        ]
        return self._find_element(locators, "刷新按钮")

    @property
    def btn_batch_delete(self) -> Locator:
        """公共元素: 批量删除按钮"""
        locators = [
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("批量删除", exact=True),
            self.get_by_text("批量删除").first,
        ]
        return self._find_element(locators, "批量删除按钮")

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

    def close_dialog_if_exists(self):
        """公共方法: 关闭可能存在的对话框"""
        if self.dialog_close.is_visible():
            self.logger.info("发现未关闭的对话框，正在关闭...")
            self.dialog_close.click()
