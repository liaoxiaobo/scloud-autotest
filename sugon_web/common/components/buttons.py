from typing import TYPE_CHECKING

from playwright.sync_api import Locator

from sugon_web.common.playwright import expect

if TYPE_CHECKING:
    from sugon_web.common.playwright import CustomLocator


class BaseElementMixin:
    """基础元素 Mixin，提供通用元素定位辅助方法。"""

    def _find_element(
        self,
        locators: list[Locator],
        element_name: str = "元素",
        timeout: int = 1000,
        check_visible: bool = True,
        check_enabled: bool = False,
    ) -> "CustomLocator":
        """通用方法：从多个定位器中查找满足条件的元素。"""
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


class ButtonsMixin(BaseElementMixin):
    """按钮类组件 Mixin。"""

    @property
    def btn_create(self) -> Locator:
        """公共元素: 新建按钮"""
        locators = [
            self.get_by_text("新建", exact=True),
            self.get_by_text("创建集群", exact=True),
            self.locator("button").filter(has_text="新建"),
            self.get_by_role("button", name="新建")
        ]
        return self._find_element(locators, "新建按钮", timeout=15000)

    @property
    def btn_submit(self) -> Locator:
        """公共元素: 表单提交按钮"""
        locators = [
            self.get_by_text("立即创建")
        ]
        return self._find_element(locators, "表单提交按钮")

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
