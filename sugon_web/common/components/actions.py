import re
import time
from typing import TYPE_CHECKING

from playwright.sync_api import Locator, expect

if TYPE_CHECKING:
    from sugon_web.common.playwright import CustomLocator

class ActionsMixin:
    """页面交互操作 Mixin。

    提供搜索、详情页跳转、资源行操作等交互能力。
    设计为与 ElementsMixin、TablesMixin、WaitsMixin 组合使用。
    """

    def _dismiss_hover_tips(
        self,
        timeout: float = 2.0,
        poll_interval: float = 0.4,
        stable_rounds: int = 3,
    ) -> None:
        """清理进入页面后残留的悬浮提示，等待 tooltip/popover 稳定消失。

        Args:
            timeout: 等待悬浮提示消失的总超时时间，单位为秒
            poll_interval: 轮询检测可见悬浮提示的间隔时间，单位为秒
            stable_rounds: 连续检测到无可见悬浮提示的次数，达到后认为状态稳定
        """
        self.page.mouse.move(1, 1)

        visible_tips = self.page.locator(
            ".el-tooltip__popper:visible, .el-popper:visible, [role='tooltip']:visible"
        )
        end_time = time.time() + timeout
        stable_hits = 0

        while time.time() < end_time:
            self.page.evaluate("""
                () => {
                    const hovered = Array.from(document.querySelectorAll(':hover'));
                    hovered.reverse().forEach((el) => {
                        el.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
                        el.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }));
                    });
                    const active = document.activeElement;
                    if (active && typeof active.blur === 'function') {
                        active.blur();
                    }
                }
                """)
            self.page.keyboard.press("Escape")

            if visible_tips.count() == 0:
                stable_hits += 1
                if stable_hits >= stable_rounds:
                    return
            else:
                stable_hits = 0
            self.page.wait_for_timeout(int(poll_interval * 1000))

        remaining = visible_tips.count()
        if remaining:
            self.logger.warning(f"等待悬浮提示消失超时，当前仍有 {remaining} 个 tooltip/popper 可见")
            self.page.evaluate("""
                () => {
                    const tips = Array.from(document.querySelectorAll(
                        '.el-tooltip__popper, .el-popper, [role="tooltip"]'
                    ));
                    tips.forEach((el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        const visible = el.getAttribute('aria-hidden') !== 'true'
                            && style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && style.opacity !== '0'
                            && rect.width > 0
                            && rect.height > 0;
                        if (visible) {
                            el.style.pointerEvents = 'none';
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                            el.setAttribute('aria-hidden', 'true');
                        }
                    });
                }
                """)
            self.page.wait_for_timeout(500)

    def search(self, keyword: str) -> None:
        """搜索并等待结果加载。

        执行流程：填充搜索框 -> 点击搜索按钮 -> wait_for_page_ready()
        -> 额外等待 1 秒确保结果渲染稳定。

        Args:
            keyword: 搜索关键词

        Raises:
            Exception: 搜索框或搜索按钮定位失败时抛出
        """
        try:
            self.logger.info(f"开始搜索: {keyword}")
            self._input_search.fill(keyword)
            self._btn_search.click()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)
            self.logger.info(f"搜索操作完成: {keyword}")
        except Exception as e:
            self.logger.error(f"搜索操作失败: keyword={keyword}")
            raise

    def _first_visible_locator(self, locators: list[Locator], element_name: str) -> Locator:
        """返回多个定位器中第一个可见元素。

        Args:
            locators: 按优先级排列的定位器集合
            element_name: 元素名称，用于异常提示信息
        """
        for locator in locators:
            for i in range(locator.count()):
                candidate = locator.nth(i)
                if candidate.is_visible():
                    return candidate
        raise AssertionError(f"未找到可见的{element_name}")

    def goto_detail_page(
        self,
        instance_name: str,
        row_name: str | None = None,
        tab_name: str = "详情",
        timeout: int = 10,
        poll_interval: float = 0.2,
    ) -> Locator | None:
        """进入实例详情页，可选切换页签并等待目标行可见。

        Args:
            instance_name: 需要进入详情页的实例名称
            row_name: 详情页中期望出现的资源行名称；不传时仅进入详情页
            tab_name: 进入详情页后需要切换的页签名称；不传时不切换页签
            timeout: 等待详情页目标行出现的超时时间，单位为秒
            poll_interval: 轮询检查详情页目标行的间隔时间，单位为秒
        """
        instance_links = self.locator("#cloud-container-content").get_by_text(instance_name, exact=True)
        clicked = False

        for i in range(instance_links.count()):
            candidate = instance_links.nth(i)
            if candidate.is_visible():
                candidate.click()
                clicked = True
                break

        if not clicked:
            raise AssertionError(f"未找到可见的实例名称节点: '{instance_name}'")

        self.wait_for_page_ready()
        self._dismiss_hover_tips()

        if tab_name:
            tab_name_pattern = re.compile(rf"^\s*{re.escape(tab_name)}(?:\s.*)?$")
            tab = self._first_visible_locator(
                [
                    self.get_by_role("tab", name=tab_name_pattern),
                    self.get_by_role("tab", name=tab_name, exact=False),
                    self.page.locator(".el-tabs__item").filter(has_text=tab_name_pattern),
                ],
                f"详情页签: '{tab_name}'",
            )
            tab.scroll_into_view_if_needed()
            self._dismiss_hover_tips()
            try:
                tab.click(trial=True, timeout=3000)
                tab.click(timeout=3000)
            except Exception as exc:
                self.logger.warning(f"详情页签 {tab_name} 试点击或普通点击失败，尝试强制点击: {exc}")
                self._dismiss_hover_tips()
                tab.click(force=True)

            if tab.get_attribute("aria-selected") is not None:
                expect(tab).to_have_attribute("aria-selected", "true", timeout=10000)
            else:
                expect(tab).to_have_class(re.compile("is-active"), timeout=10000)
            self.wait_for_page_ready()
            self._dismiss_hover_tips()

        if not row_name:
            return None

        end_time = time.time() + timeout
        last_error = None

        while time.time() < end_time:
            try:
                row = self.get_row_by_name(row_name)
                self.logger.info(f"详情页目标行已就绪: {row_name}")
                return row
            except Exception as e:
                last_error = e

            self.page.wait_for_timeout(int(poll_interval * 1000))

        raise AssertionError(
            f"等待详情页资源行 '{row_name}' 超时，实例: '{instance_name}'"
        ) from last_error

    def _btn_operation(self, name: str) -> Locator:
        """公共元素: 资源操作按钮"""
        row = self.get_row_by_name(name)
        interactive_row = self._get_interactive_row(row)
        self.logger.info(f"成功找到资源操作行: {name}")

        locators = [
            interactive_row.get_by_text("更多"),
            self.get_by_role("row", name=name).get_by_role("button"),
            interactive_row.locator(".el-dropdown-selfdefine[title='操作']:has(.el-icon-setting)").last
        ]

        for locator in locators:
            try:
                expect(locator).to_be_visible(timeout=2000)
                if locator.is_enabled():
                    self.logger.info(f"定位资源的目标行: {name}")
                    self.logger.info(f"定位资源的操作按钮: {name}")
                    return locator
            except Exception as e:
                self.logger.debug(f"检查按钮状态时出错: {e}")

        raise Exception(f"定位失败：资源操作按钮未找到。尝试的定位器: {[str(loc) for loc in locators]}")

    def click_action(self, resource_name: str, option_text: str) -> None:
        """
        公共方法：点击指定资源行的操作选项（兼容平铺按钮和下拉菜单模式）

        Args:
            resource_name: 资源名称
            option_text: 下拉菜单选项或平铺按钮文本（如"删除"、"编辑"等）
        """
        try:
            try:
                row = self.get_row_by_name(resource_name)
                interactive_row = self._get_interactive_row(row)
                option_btn = interactive_row.get_by_text(option_text, exact=True)

                for i in range(option_btn.count()):
                    btn = option_btn.nth(i)
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        self.logger.info(f"点击平铺操作选项: {resource_name} -> {option_text}")
                        return

                self.logger.debug(f"未找到可用且可见的平铺选项: {option_text}，将尝试下拉菜单模式")
            except Exception as e:
                self.logger.debug(f"定位平铺操作选项异常: {e}，将尝试下拉菜单模式")

            operation_btn = self._btn_operation(resource_name)
            operation_btn.hover()
            self.page.wait_for_timeout(1000)

            dropdown_selectors = [
                ('[id^="dropdown-menu-"]', 'id'),
                ('[class^="cloud-table-dropdown"]', 'class')
            ]

            for selector, selector_type in dropdown_selectors:
                try:
                    dropdown_menus = self.page.locator(selector)
                    menu_count = dropdown_menus.count()

                    if menu_count == 0:
                        self.logger.debug(f"使用 {selector_type} 选择器未找到下拉菜单")
                        continue

                    for i in range(menu_count - 1, -1, -1):
                        menu = dropdown_menus.nth(i)
                        if menu.is_visible():
                            option = menu.get_by_text(option_text, exact=True)

                            if option.count() > 0:
                                if option.is_visible() and option.is_enabled():
                                    option.click()
                                    self.logger.info(
                                        f"点击下拉菜单操作选项: {resource_name} -> {option_text} (使用 {selector_type} 选择器)")
                                    return
                                else:
                                    self.logger.warning(f"选项 '{option_text}' 不可见或不可用")
                            else:
                                self.logger.debug(f"当前菜单中未找到选项: {option_text}")

                    self.logger.debug(f"{selector_type} 选择器未找到可用选项，尝试下一个")

                except Exception as e:
                    self.logger.debug(f"{selector_type} 选择器失败: {e}")
                    continue

            raise Exception(f"所有选择器都失败，既不是可用的平铺操作按钮，也没有在下拉菜单中找到: {option_text}")

        except Exception as e:
            self.logger.error(f"点击资源操作选项失败: {resource_name} -> {option_text}, 错误: {e}")
            raise
