import re
import time
from functools import wraps
from typing import Callable
from urllib.parse import urlparse
from playwright.sync_api import Page, Locator
from sugon_web.common.playwright import expect
from sugon_web.common.playwright import Playwright
from sugon_web.config.config import Config
from sugon_web.config.constants import SERVICE_MAP, SERVICE_PATH_MAP

def submenu(name: str) -> Callable:
    """装饰器：确保进入当前服务下的指定子菜单页面。"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            service_name = getattr(self, "service_name", None)
            if service_name:
                self.goto_service(service_name)
            self.goto_submenu(name)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

class BasePage(Playwright):

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # 从内存中读取，不会重复加载文件
        self.stor = Config.get('stor')
        self.storage_pool, self.volume_type = self.stor + '-test', self.stor + '-type'

    @property
    def popup(self) -> Locator:
        """公共元素:页面顶部弹窗"""
        return self.locator(".el-message__content")

    @property
    def alert(self) -> Locator:
        """公共元素:页面右下角弹窗"""
        return self.get_by_role("alert")

    def _find_element(self, locators, element_name="元素", timeout=1000, check_visible=True, check_enabled=False):
        """
        通用方法：从多个定位器中查找满足条件的元素

        Args:
            locators: 定位器列表
            element_name: 元素名称，用于错误信息
            timeout: 等待超时时间（毫秒）
            check_visible: 是否检查元素可见
            check_enabled: 是否检查元素可用

        Returns:
            Locator: 找到的定位器

        Raises:
            Exception: 未找到满足条件的元素
        """
        for locator in locators:
            try:
                # 如果需要检查可见性
                if check_visible:
                    expect(locator).to_be_visible(timeout=timeout)

                # 如果需要检查可用性
                if check_enabled:
                    expect(locator).to_be_enabled(timeout=timeout)

                # 所有条件满足，返回定位器
                return locator

            except Exception as e:
                self.logger.debug(f"检查{element_name}状态时出错: {e}")
                continue  # 尝试下一个定位器

        # 所有定位器都失败，抛出异常
        locator_strs = [str(loc) for loc in locators]
        raise Exception(f"定位失败：{element_name}未找到。尝试的定位器: {locator_strs}")

    @property
    def btn_create(self) -> Locator:
        """公共元素:新建按钮"""
        locators = [
            self.get_by_text("新建", exact=True),
            self.get_by_text("创建集群", exact=True)
        ]

        return self._find_element(locators, "新建按钮")

    @property
    def btn_submit(self) -> Locator:
        """公共元素:表单提交按钮"""
        locators = [
            self.get_by_text("立即创建")
        ]

        return self._find_element(locators, "表单提交按钮")

    @property
    def _input_search(self) -> Locator:
        """公共元素:搜索框"""
        # 使用 Playwright 的惰性定位器（Locator）机制，只有在调用如 is_visible() 时才会真正执行DOM查询
        locators = [
            self.get_by_role("textbox", name="搜索（规格名称）"),
            self.get_by_role("textbox", name="搜索（名称）"),
            self.get_by_role("textbox", name="搜索(名称)"), # slb 列表页搜索定位器
            self.get_by_role("textbox", name="搜索（固定IP）"),
            self.get_by_role("textbox", name="搜索（公网IP）"),
            self.get_by_role("textbox", name="搜索（参数名称）"),
            self.get_by_role("textbox", name="搜索（快照名称）"),
            self.locator(".input-with-select > .el-input__inner"),
            self.get_by_role("textbox", name="请输入设备名称"),
            self.get_by_role("textbox", name="搜索(实例名称)"),
            self.get_by_placeholder("搜索(目的地址)")   # 路由表规则搜索框
        ]

        return self._find_element(locators, "搜索框")

    @property
    def _btn_search(self) -> Locator:
        """公共元素:搜索按钮"""
        locators = [
            # 1. 优先查找可见弹窗内的搜索按钮
            self.locator(".el-dialog__wrapper:visible").get_by_text("搜索", exact=True),
            # 2. 查找当前激活 Tab 页签内的搜索按钮 (排除隐藏的 tab-pane)
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("搜索", exact=True),
            # 3. 兜底：查找页面上可见的搜索按钮 (注意：如果页面仍有多个可见搜索按钮，这里可能仍会报错，但上述两步通常能解决问题)
            self.get_by_text("搜索", exact=True)
        ]
        return self._find_element(locators, "搜索按钮")

    @property
    def btn_reset(self) -> Locator:
        """公共元素:重置按钮"""
        locators = [
            # 1. 优先查找可见弹窗内的重置按钮
            self.locator(".el-dialog__wrapper:visible").get_by_text("重置", exact=True),
            # 2. 查找当前激活 Tab 页签内的重置按钮 (排除隐藏的 tab-pane)
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("重置", exact=True),
            # 3. 兜底：查找页面上可见的重置按钮
            self.get_by_text("重置", exact=True).first
        ]
        return self._find_element(locators, "重置按钮")

    @property
    def btn_refresh(self) -> Locator:
        """公共元素:刷新按钮"""
        locators = [
            self.locator("#serverRefresh"),
            self.locator("#SpecificationRefresh").nth(1),  # 详情页面的刷新按钮
            self.locator(".el-icon-refresh")
        ]

        return self._find_element(locators, "刷新按钮")

    # @property
    # def btn_batch_delete(self) -> Locator:
    #     """公共元素: 批量删除按钮"""
    #     locators = [
    #         self.get_by_text("批量删除", exact=True),
    #         self.get_by_text("删除", exact=True).first,
    #         self.get_by_text("批量删除").first,
    #         self.get_by_label("虚拟IP管理").get_by_text("批量删除"),
    #         self.get_by_label("端口", exact=True).get_by_text("批量删除"),
    #         self.get_by_label("路由表", exact=True).get_by_text("批量删除")
    #     ]

    #     return self._find_element(locators, "批量删除按钮")

    @property
    def btn_batch_delete(self) -> Locator:
        """公共元素: 批量删除按钮"""
        locators = [
            # 1. 优先在当前激活的 Tab 页签内查找（排除隐藏 tab-pane，自动兼容所有 Tab 场景）
            self.locator(".el-tab-pane:not([aria-hidden='true'])").get_by_text("批量删除", exact=True),
            # 2. 兜底：在整个页面查找第一个「批量删除」按钮
            self.get_by_text("批量删除").first,
        ]
        return self._find_element(locators, "批量删除按钮")

    @property
    def dialog_confirm(self) -> Locator:
        """公共元素:对话框确定按钮"""
        locators = [
            self.get_by_role("dialog").get_by_text("确定", exact=True),
            self.get_by_role("dialog").locator("span").filter(has_text="确定"),
            self.get_by_role("dialog").get_by_text("确定", exact=True).nth(1),
            self.locator("section").get_by_text("确定"),
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").first,   # 云硬盘删除对话框
            self.locator(".sure-footer > div > .cloud-button-btn").first,
            self.get_by_label("虚拟IP管理").get_by_text("确定", exact=True)

        ]

        return self._find_element(locators, "对话框'确定'按钮")

    @property
    def dialog_cancel(self) -> Locator:
        """公共元素:对话框取消按钮"""
        locators = [
            self.get_by_role("dialog").get_by_text("取消"),
            self.locator("div:nth-child(2) > div:nth-child(2) > .cloud-button-btn")
        ]

        return self._find_element(locators, "对话框'取消'按钮")

    @property
    def dialog_close(self) -> Locator:
        """公共元素:对话框关闭按钮"""
        return self.get_by_role("button", name="Close")

    def close_dialog_if_exists(self):
        """公共方法: 关闭可能存在的对话框"""
        if self.dialog_close.is_visible():
            self.logger.info("发现未关闭的对话框，正在关闭...")
            self.dialog_close.click()
        # 补充关闭 Element UI / sugon 弹窗
        for btn_text in ["确定", "确 定", "知道了", "关闭", "确认"]:
            for btn in self.page.locator(".el-message-box__wrapper button, .el-dialog__wrapper button, .sugon-dialog button").filter(has_text=btn_text).all():
                try:
                    if btn.is_visible():
                        btn.click()
                        self.page.wait_for_timeout(500)
                        break
                except Exception:
                    continue
        # 兜底：JS 强制移除残留的 sugon-dialog 遮罩
        self.page.evaluate("""
            () => {
                document.querySelectorAll('.sugon-dialog').forEach(d => {
                    d.style.display = 'none';
                });
            }
        """)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    def search(self, keyword: str):
        """公共方法: 搜索操作"""
        try:
            self.logger.info(f"开始搜索: {keyword}")
            self._input_search.fill(keyword)
            self._btn_search.click()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)    # 等待1秒，确保搜索结果加载完成，解决搜索用例断言不稳定的问题
            self.logger.info(f"搜索操作完成: {keyword}")
        except Exception as e:
            self.logger.error(f"搜索操作失败: keyword={keyword}")
            raise

    @staticmethod
    def _normalize_route_parts(route: str) -> tuple[str, str]:
        """将 route 统一为 path 和 hash，便于做精确比较。"""
        parsed = urlparse(route)
        path = parsed.path.rstrip("/") or "/"
        hash_value = f"#{parsed.fragment}" if parsed.fragment else ""
        return path, hash_value

    def _is_current_service_path(self, service_path: str) -> bool:
        """判断当前页面是否已位于目标服务下的任意页面。"""
        current_path, _ = self._normalize_route_parts(self.page.url)
        target_path, _ = self._normalize_route_parts(service_path)
        return current_path == target_path

    def _goto_service_by_path(self, service: str, service_path: str) -> bool:
        """通过服务入口路径直达指定服务。"""
        try:
            if self._is_current_service_path(service_path):
                self.wait_for_page_ready()
                self.logger.info(f"当前已在目标服务下，复用现有页面: {service} -> {self.page.url}")
                return True

            base_url = Config.get("base_url").rstrip("/")
            target_url = f"{base_url}{service_path}"
            self.page.goto(target_url)
            self.wait_for_page_ready()

            if not self._is_current_service_path(service_path):
                raise AssertionError(
                    f"URL 直达服务失败: current={self.page.url}, expected_service_path={service_path}"
                )

            self.logger.info(f"通过 URL 直达服务成功: {service} -> {target_url}")
            return True
        except Exception as e:
            self.logger.error(f"通过 URL 直达服务 {service} 失败: {e}")
            raise AssertionError(f"通过 URL 直达服务 {service} 失败: {e}") from e

    def _goto_service_by_menu(self, service: str) -> bool:
        """通过原有顶栏菜单导航到指定服务。"""
        # 关闭可能遮挡菜单的弹窗（由 close_dialog_if_exists 统一处理）
        self.close_dialog_if_exists()
        self.page.wait_for_timeout(500)

        navigation_path = SERVICE_MAP[service]

        if len(navigation_path) == 1:
            # 两层结构：基础设施 -> 服务
            root_menu = navigation_path[0]
            self.hover(root_menu)
            self.click(service)
            try:
                expect(self.page.locator(".el-loading-spinner")).to_be_attached(timeout=10000)
            except:
                pass
            self.wait_for_page_ready()
            self.logger.info(f"成功导航到服务: {root_menu} -> {service}")

        elif len(navigation_path) == 2:
            # 三层结构：资源中心 -> 二级菜单 -> 服务
            root_menu, category = navigation_path
            self.hover(root_menu)
            self.hover(category)
            self.page.wait_for_timeout(800)
            try:
                self.click(service)
            except Exception:
                # 部分菜单无第三层（如 运营→租户 直接进入IAM），回退点击二级菜单中可见项
                self.logger.info(f"未找到'{service}'子项，点击二级菜单中可见'{category}'")
                for el in self.page.get_by_text(category).all():
                    if el.is_visible():
                        el.click()
                        break
            try:
                expect(self.page.locator(".el-loading-spinner")).to_be_attached(timeout=10000)
            except:
                pass
            self.wait_for_page_ready()
            self.logger.info(f"成功导航到服务: {root_menu} -> {category} -> {service}")

        else:
            self.logger.error(f"服务 {service} 的导航路径配置错误: {navigation_path}")
            raise AssertionError(f"服务 {service} 的导航路径配置错误: {navigation_path}")

        return True

    def goto_service(self, service: str):
        """公共方法: 导航到指定服务，优先通过服务入口路径直达，未配置时回退到菜单导航。

        Args:
            service: 服务名称，如 '云容器引擎'、'云硬盘'、'物理服务器' 等

        Returns:
            bool: 导航是否成功
        """
        if service not in SERVICE_PATH_MAP and service not in SERVICE_MAP:
            self.logger.error(f"未知的服务: {service}，请检查服务名称或更新导航映射表")
            raise AssertionError(f"未知的服务: {service}")

        try:
            service_path = SERVICE_PATH_MAP.get(service)
            if service_path:
                return self._goto_service_by_path(service, service_path)

            self.logger.info(f"服务 {service} 未配置入口路径，继续使用菜单导航")
            return self._goto_service_by_menu(service)
        except Exception as e:
            self.logger.error(f"导航到服务 {service} 失败: {e}")
            raise AssertionError(f"导航到服务 {service} 失败: {e}") from e

    def goto_submenu(self, submenu):
        """公共方法: 切换当前服务页面的子菜单。

        Args:
            submenu: 子菜单名称，如下：
                - "概览"
                - "云硬盘"
                - "回收站"
                - "快照"
                - "弹性云服务器"
                - "虚拟私有云"
        """
        service_name = getattr(self, "service_name", None)
        service_path = SERVICE_PATH_MAP.get(service_name) if service_name else None
        if service_name and service_path and not self._is_current_service_path(service_path):
            self.goto_service(service_name)

        # # 检查是否已经在目标子菜单页面上
        # try:
        #     # 查找当前激活的菜单项
        #     active_menu = self.locator(".one-tree-active")
        #     if active_menu.count() > 0:
        #         active_text = active_menu.inner_text().strip()
        #         if active_text == submenu:
        #             self.logger.info(f"已经在目标子菜单: {submenu}，无需切换")
        #             return
        # except Exception as e:
        #     self.logger.debug(f"检查当前菜单状态时出错: {e}")

        # 处理默认收起的菜单
        expect(self.locator("#cloud-menu-left")).to_be_visible(timeout=15000)   # 确保菜单栏完全加载
        menu_left = self.locator("#cloud-menu-left")
        parent_nodes = menu_left.locator(".one-tree-parent-node")
        count = parent_nodes.count()

        for i in range(count):
            parent = parent_nodes.nth(i)
            # 检查是否已展开（有 one-tree-expand 类表示已展开）
            is_expanded = parent.evaluate("el => el.classList.contains('one-tree-expand')")
            if not is_expanded:
                parent.click()
        # 根据子菜单参数导航到对应页面（使用 first 处理菜单项重复的情况）
        self.locator("#cloud-menu-left").get_by_text(submenu, exact=True).first.click()
        self.page.wait_for_timeout(1000)    # 确保页面导航后页面加载完全
        self.wait_for_page_ready()
        self.logger.info(f"成功导航到子菜单: {submenu}")

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

    def _first_visible_locator(self, locators, element_name: str) -> Locator:
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
        row_name: str = None,
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

    def assert_popup_success(self, text=None, timeout=10):
        """公共方法: 根据弹窗文本和类型，断言操作成功

        Args:
            text: 期望的弹窗文本内容（可选）
            timeout: 超时时间（秒）
        """
        timeout_ms = timeout * 1000  # 转换为毫秒
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        # 获取弹窗文本
        popup_text = popup.inner_text().strip()

        # 通过检查元素的CSS类名判断弹窗类型
        is_success = popup.evaluate("element => element.parentElement.classList.contains('el-message--success')")

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
        timeout_ms = timeout * 1000  # 转换为毫秒
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        # 获取弹窗文本
        popup_text = popup.inner_text().strip()

        # 通过检查元素的CSS类名判断弹窗类型
        is_error = popup.evaluate("element => element.parentElement.classList.contains('el-message--error')")

        if not is_error:
            raise AssertionError(f"预期操作失败，但实际成功或其他状态。弹窗文本: {popup_text}")

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)

    def assert_list_contain(self, keyword, column_name="名称", exact_match=True):
        """
        公共方法: 验证指定列中是否包含特定关键字

        Args:
            keyword: 关键字
            column_name: 列名，默认为"名称"
            exact_match: 匹配模式（True为精准匹配，False为模糊匹配）

        Raises:
            AssertionError: 当没有找到匹配项时抛出异常
        """
        self.logger.info(f"检查列 '{column_name}' 中是否包含关键字 '{keyword}'")

        column_data = self.get_column_data(column_name)

        if not column_data:
            self.logger.warning(f"列 '{column_name}' 没有数据或不存在")
            assert False, f"列 '{column_name}' 没有数据或不存在"

        # 根据参数选择匹配方式
        if exact_match:
            # 精准匹配：检查是否有任何一个元素与关键词完全相等
            matched = any(keyword == item for item in column_data)
            match_description = "包含与关键词完全相等的数据"
        else:
            # 模糊匹配：检查是否所有元素包含关键词，适用于搜索结果页面
            matched = all(keyword in item for item in column_data)
            match_description = "包含关键词的数据"

        # 断言
        assert matched, f"验证失败：{match_description}。关键词: '{keyword}'，实际列数据: {column_data}"

    def assert_list_not_contain(self, keyword, column_name="名称", exact_match=True):
        """
        公共方法: 验证指定列中不包含特定关键字

        Args:
            keyword: 关键字
            column_name: 列名，默认为"名称"
            exact_match: 匹配模式（True为精准匹配，False为模糊匹配）

        Raises:
            AssertionError: 当找到匹配项时抛出异常
        """
        self.logger.info(f"检查列 '{column_name}' 中是否不包含关键字 '{keyword}'")

        try:
            column_data = self.get_column_data(column_name)
        except Exception:
             # 如果列不存在或获取失败，也算不包含，记录日志并返回
            self.logger.info(f"列 '{column_name}' 不存在或无数据，视为不包含关键字 '{keyword}'")
            return

        if not column_data:
             self.logger.info(f"列 '{column_name}' 为空，视为不包含关键字 '{keyword}'")
             return

        # 根据参数选择匹配方式
        if exact_match:
            # 精准匹配：检查是否有任何一个元素与关键词完全相等
            matched = any(keyword == item for item in column_data)
            match_description = "包含与关键词完全相等的数据"
        else:
            # 模糊匹配：检查是否有任何元素包含关键词
            matched = any(keyword in item for item in column_data)
            match_description = "包含关键词的数据"

        # 断言
        assert not matched, f"验证失败：预期不{match_description}。关键词: '{keyword}'，实际列数据: {column_data}"

    def assert_status(self, names, status='运行', timeout=300, refresh=False, refresh_interval=5):
        """
        公共方法：验证页面表格中指定资源的状态是否符合预期，支持单个和批量资源

        Args:
            names: 资源名称（字符串）或资源名称列表（列表）
            status: 期望状态（字符串），所有资源都将使用此状态进行验证
            timeout: 超时时间（秒）
            refresh: 是否需要定期刷新页面，默认为False
            refresh_interval: 刷新间隔时间（秒），默认为5秒，仅在refresh=True时有效
        """
        # 处理单个资源的情况（保持向后兼容）
        if isinstance(names, str):
            names = [names]

        # 收集验证失败的资源
        failed_resources = []

        # 逐个验证资源状态
        for name in names:
            try:
                if not refresh:
                    # 不刷新模式：直接使用Playwright的高效等待机制
                    timeout_ms = timeout * 1000  # 转换为毫秒
                    self.wait_for_page_ready() # 等待页面加载完成再查找元素
                    target_row = self.get_row_by_name(name)
                    # expect(target_row.locator(".icon-dengdaizhong")).not_to_be_visible(timeout=timeout_ms)
                    expect(target_row).to_contain_text(status, timeout=timeout_ms, use_inner_text=True)
                    self.logger.info(f"资源状态验证成功: {name} -> {status}")
                else:
                    # 刷新模式：定期刷新页面并检查状态
                    start_time = time.time()
                    current_status = "未知"
                    first_check = True

                    while time.time() - start_time < timeout:
                        try:
                            # 刷新页面（第一次循环跳过刷新，直接检查当前状态）
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查状态: {name}")
                                except Exception as refresh_error:
                                    self.logger.warning(f"刷新页面失败，将继续检查状态: {refresh_error}")

                            first_check = False

                            # 定位目标行并检查状态
                            target_row = self.get_row_by_name(name)
                            current_status = target_row.inner_text()

                            # 如果状态匹配，则跳出循环继续下一个资源
                            if status in current_status:
                                self.logger.info(f"资源状态验证成功: {name} -> {status}")
                                break

                        except Exception as e:
                            self.logger.debug(f"检查状态时出错: {e}")

                        # 等待下一次刷新
                        time.sleep(refresh_interval)
                    else:
                        # 超时后记录失败
                        failed_resources.append(
                            f"{name} (期望状态: {status}, 当前状态: {current_status})")

            except Exception as e:
                self.logger.error(f"资源状态验证失败: {name} -> {status}, 错误: {e}")
                failed_resources.append(f"{name} (期望状态: {status}, 错误: {str(e)})")

        # 如果有任何资源验证失败，抛出异常
        if failed_resources:
            raise AssertionError(f"以下资源状态验证失败: {'; '.join(failed_resources)}")

    def assert_deleted(self, resource_names, timeout=300, refresh=False, refresh_interval=5):
        """
        公共方法：断言资源已从列表中删除（通过表格行不可见来判断），支持单个和批量资源

        Args:
            resource_names: 资源名称（字符串）或资源名称列表（列表）
            timeout: 超时时间（秒）
            refresh: 是否需要定期刷新页面，默认为False
            refresh_interval: 刷新间隔时间（秒），默认为5秒，仅在refresh=True时有效
        """
        # 处理单个资源的情况
        if isinstance(resource_names, str):
            resource_names = [resource_names]

        # 收集验证失败的资源
        failed_resources = []

        for resource_name in resource_names:
            try:
                if not refresh:
                    # 不刷新模式：直接使用Playwright的高效等待机制
                    timeout_ms = timeout * 1000  # 转换为毫秒
                    resource_row = self.get_by_role("row", name=resource_name, exact=True)
                    expect(resource_row).not_to_be_visible(timeout=timeout_ms)
                    self.logger.info(f"资源从列表中删除成功: {resource_name}")
                else:
                    # 刷新模式：定期刷新页面并检查资源是否已删除
                    start_time = time.time()
                    first_check = True

                    while time.time() - start_time < timeout:
                        try:
                            # 刷新页面（第一次循环跳过刷新，直接检查当前状态）
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查删除状态: {resource_name}")
                                except Exception as refresh_error:
                                    self.logger.warning(f"刷新页面失败，将继续检查删除状态: {refresh_error}")

                            first_check = False

                            # 定位包含资源名称的表格行
                            resource_row = self.get_by_role("row", name=resource_name, exact=True)

                            # 检查行是否不可见（即已删除）
                            if not resource_row.is_visible():
                                self.logger.info(f"资源从列表中删除成功: {resource_name}")
                                break

                        except Exception as e:
                            # 如果定位不到资源行，则认为已删除
                            self.logger.info(f"资源从列表中删除成功: {resource_name}")
                            break

                        # 等待下一次刷新
                        time.sleep(refresh_interval)
                    else:
                        # 超时后记录失败
                        failed_resources.append(resource_name)

            except Exception as e:
                self.logger.error(f"资源删除验证失败: {resource_name}, 错误: {e}")
                failed_resources.append(resource_name)

        # 如果有任何资源验证失败，抛出异常
        if failed_resources:
            raise AssertionError(
                f"以下资源删除验证失败（可能仍然存在于列表中）: {', '.join(failed_resources)}"
            )

    def _get_interactive_row(self, row: Locator) -> Locator:
        """获取可交互的行（优先返回 fixed-right 层，避免被遮挡）"""
        try:
            # 1. 获取当前行在所属 tbody 中的物理索引
            row_index = row.evaluate("el => Array.from(el.parentNode.children).indexOf(el)")

            # 2. 获取当前所属表格在页面所有 el-table 中的索引，用于解决多表格共存时的定位偏移
            table_index = row.evaluate("""
                el => {
                    const table = el.closest('.el-table');
                    if (!table) return -1;
                    return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
                }
            """)

            if table_index != -1:
                # 3. 在对应的表格内根据索引定位固定列中心对应的行
                fixed_right = self.locator(".el-table").nth(table_index).locator(".el-table__fixed-right .el-table__row").nth(row_index)
                if fixed_right.count() > 0 and fixed_right.is_visible():
                    return fixed_right
        except Exception as e:
            self.logger.debug(f"通过索引获取可交互行时出错: {e}")
        return row

    def _btn_operation(self, name):
        """公共元素: 资源操作按钮"""

        # 定位资源行
        row = self.get_row_by_name(name)
        interactive_row = self._get_interactive_row(row)
        self.logger.info(f"成功找到资源操作行: {name}")

        # 提供两种定位方式，第二种适用于ecs列表页面
        locators = [
            interactive_row.get_by_text("更多"),
            self.get_by_role("row", name=name).get_by_role("button"),
            interactive_row.locator(".el-dropdown-selfdefine[title='操作']:has(.el-icon-setting)").last   # 组合定位器：title属性 + 类名 + 图标验证
        ]

        # 尝试定位
        for locator in locators:
            try:
                # 等待元素可见
                expect(locator).to_be_visible(timeout=2000)
                # 确保按钮既可见又可用
                if locator.is_enabled():
                    self.logger.info(f"定位资源的目标行: {name}")
                    self.logger.info(f"定位资源的操作按钮: {name}")
                    return locator
            except Exception as e:
                self.logger.debug(f"检查按钮状态时出错: {e}")

        raise Exception(f"定位失败：资源操作按钮未找到。尝试的定位器: {[str(loc) for loc in locators]}")

    def click_action(self, resource_name: str, option_text: str):
        """
        公共方法：点击指定资源行的操作选项（兼容平铺按钮和下拉菜单模式）

        Args:
            resource_name: 资源名称
            option_text: 下拉菜单选项或平铺按钮文本（如"删除"、"编辑"等）
        """
        try:
            # 1. 尝试直接点击平铺可见的操作按钮
            try:
                row = self.get_row_by_name(resource_name)
                interactive_row = self._get_interactive_row(row)
                option_btn = interactive_row.get_by_text(option_text, exact=True)

                # 有可能找到多个同名文本，遍历尝试点击第一个可见并可用的按钮
                for i in range(option_btn.count()):
                    btn = option_btn.nth(i)
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        self.logger.info(f"点击平铺操作选项: {resource_name} -> {option_text}")
                        return

                self.logger.debug(f"未找到可用且可见的平铺选项: {option_text}，将尝试下拉菜单模式")
            except Exception as e:
                self.logger.debug(f"定位平铺操作选项异常: {e}，将尝试下拉菜单模式")

            # 2. 如果平铺按钮没找到或不可见，尝试基于“更多/操作”按钮通过下拉菜单点击
            operation_btn = self._btn_operation(resource_name)
            operation_btn.hover()

            # 等待下拉菜单出现
            self.page.wait_for_timeout(1000)

            # 定义支持的下拉菜单选择器
            dropdown_selectors = [
                ('[id^="dropdown-menu-"]', 'id'),
                ('[class^="cloud-table-dropdown"]', 'class')
            ]

            # 遍历所有选择器，尝试找到并点击选项
            for selector, selector_type in dropdown_selectors:
                try:
                    # 查找所有下拉菜单
                    dropdown_menus = self.page.locator(selector)
                    menu_count = dropdown_menus.count()

                    if menu_count == 0:
                        self.logger.debug(f"使用 {selector_type} 选择器未找到下拉菜单")
                        continue

                    # 从后往前遍历，找到最后一个可见的下拉菜单
                    for i in range(menu_count - 1, -1, -1):
                        menu = dropdown_menus.nth(i)
                        if menu.is_visible():
                            # 尝试获取选项
                            option = menu.get_by_text(option_text, exact=True)

                            if option.count() > 0:
                                # 检查选项状态
                                if option.is_visible() and option.is_enabled():
                                    option.click()
                                    self.logger.info(
                                        f"点击下拉菜单操作选项: {resource_name} -> {option_text} (使用 {selector_type} 选择器)")
                                    return
                                else:
                                    self.logger.warning(f"选项 '{option_text}' 不可见或不可用")
                            else:
                                self.logger.debug(f"当前菜单中未找到选项: {option_text}")

                    # 当前选择器未找到可用选项，继续下一个
                    self.logger.debug(f"{selector_type} 选择器未找到可用选项，尝试下一个")

                except Exception as e:
                    self.logger.debug(f"{selector_type} 选择器失败: {e}")
                    continue

            # 所有选择器都失败
            raise Exception(f"所有选择器都失败，既不是可用的平铺操作按钮，也没有在下拉菜单中找到: {option_text}")

        except Exception as e:
            self.logger.error(f"点击资源操作选项失败: {resource_name} -> {option_text}, 错误: {e}")
            raise

    def wait_for_page_ready(self):
        """公共方法: 等待页面完全就绪"""
        self.page.wait_for_load_state("domcontentloaded")  # 等待DOM加载完成
        self.page.wait_for_load_state("load")  # 等待页面加载完成（如图片、样式表、脚本）
        # 等待所有 Element UI loading 遮罩消失
        loading_spinners = self.page.locator(".el-loading-spinner")
        count = loading_spinners.count()
        if count > 0:
            for i in range(count):
                loading_spinners.nth(i).wait_for(state='hidden')

    def wait_for_source_complete(self, name, loading_timeout=10, complete_timeout=180):
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

    def wait_for_operation_complete(self, timeout=60):
        """等待操作完成

        Args:
            timeout: 超时时间（秒）
        """
        start_time = time.time()
        # 组合所有的加载指示器选择器，只检查可见的
        loading_selector = ".el-icon-loading:visible, .el-button.is-loading:visible"

        while time.time() - start_time < timeout:
            try:
                # 如果没有任何可见的加载标识，认为操作完成
                if self.page.locator(loading_selector).count() == 0:
                    return

                # 等待1秒后重试
                time.sleep(1)
            except Exception as e:
                self.logger.debug(f"等待操作完成时出错: {e}")
                time.sleep(1)

        # 超时后抛出异常
        raise AssertionError(f"等待操作完成超时，超过 {timeout} 秒")

    @property
    def table_headers(self):
        """获取表头信息，返回表头列表"""

        headers = []
        # 使用更精确的定位器，只获取第一个可见表头，防止多个表格时表头信息合并（如 Doris）
        header_wrapper = self.locator("#cloud-container-content .el-table__header-wrapper:visible").first

        if header_wrapper.count() > 0:
            headers = header_wrapper.locator("th").all_text_contents()
            self.logger.info(f"页面表头信息: {headers}, 共{len(headers)}个")
        else:
            self.logger.warning(f"未找到表头信息，尝试使用备用定位方式")
            # 备用方案：如果找不到特定class的表头，使用原有方式
            if self.locator("thead").count() > 0:
                headers = self.locator("thead:visible th").first.all_text_contents() # also prefer first visible
                self.logger.info(f"使用备用方式获取表头信息: {headers}, 共{len(headers)}个")
            else:
                self.logger.error(f"未找到任何表头信息")

        return headers

    @property
    def table_rows(self)-> Locator:
        """获取表格中的数据行，返回行定位器列表"""

        locator = self.locator("#cloud-container-content .el-table__body-wrapper:visible tr")
        if locator.count() > 0:
            rows = locator.all()
            self.logger.info(f"成功获取表格行，共{len(rows)}行")
        else:
            self.logger.info(f"未找到表格行")
            rows = []
        return rows

    def get_row_by_name(self, name: str) -> Locator:
        """公共方法:根据名称查找数据行,用于获取单个或第一个匹配的行(前缀匹配优先)"""
        t_body = self.locator(".el-table__body-wrapper")
        # 兼容退化
        if t_body.count() == 0:
            t_body = self

        try:
            # 模式1: 名称后跟空白字符
            pattern = re.compile(rf"^{re.escape(name)}\s")
            target_rows = t_body.locator("tr").filter(has_text=pattern)
            if target_rows.count() > 0:
                self.logger.debug(f"找到精确匹配 {name} 的数据行(空白字符)")
                return target_rows.first

            # 模式2: 名称后跟冒号和ID
            pattern2 = re.compile(rf"^{re.escape(name)}:\w+")
            target_rows = t_body.locator("tr").filter(has_text=pattern2)
            if target_rows.count() > 0:
                self.logger.debug(f"找到带ID的匹配 {name} 的数据行(冒号)")
                return target_rows.first

            # 模式3: 名称后跟斜杠和ID
            pattern3 = re.compile(rf"^{re.escape(name)}/\w+")
            target_rows = t_body.locator("tr").filter(has_text=pattern3)
            if target_rows.count() > 0:
                self.logger.debug(f"找到带ID的匹配 {name} 的数据行(斜杠)")
                return target_rows.first

        except Exception as e:
            self.logger.debug(f"正则匹配失败: {e}")

        # 如果正则匹配失败,尝试精确匹配a
        try:
            target_rows = t_body.locator("tr")
            for i in range(target_rows.count()):
                current_row = target_rows.nth(i)
                try:
                    # 获取所有单元格并检查内容
                    cells = current_row.locator("td")
                    for j in range(cells.count()):
                        cell_text = cells.nth(j).text_content()
                        if cell_text:
                            # 第一阶段: 精确匹配
                            if cell_text.strip() == name:
                                self.logger.info(f"通过遍历找到 '{name}' 的精确匹配行")
                                return current_row
                except Exception as e:
                    self.logger.debug(f"检查行 {i} 时出错: {e}")
                    continue
            # 第二阶段: 如果精确匹配未找到,尝试前缀匹配
            for i in range(target_rows.count()):
                current_row = target_rows.nth(i)
                try:
                    # 获取所有单元格并检查内容
                    cells = current_row.locator("td")
                    for j in range(cells.count()):
                        cell_text = cells.nth(j).text_content()
                        if cell_text:
                            # 前缀匹配: 检查是否以 name 开头
                            if cell_text.strip().startswith(name):
                                self.logger.info(f"通过遍历找到 '{name}' 的前缀匹配行(单元格: {cell_text.strip()})")
                                return current_row
                except Exception as e:
                    self.logger.debug(f"检查行 {i} 时出错: {e}")
                    continue
        except Exception as e:
            self.logger.info(f"遍历表格行失败: {e}")

        # 所有方法都失败
        raise AssertionError(f"未找到名称为 '{name}' 的数据行")

    def get_rows_by_text(self, text: str) -> Locator:
        """公共方法：根据文本查找数据行，用于获取所有匹配的行（包含匹配）"""
        target_rows = self.locator(f"tr:has-text('{text}')")  # 多行匹配：只要行内容包含 text

        if target_rows.count() == 0:
            raise AssertionError(f"未找到包含'{text}' 的数据行")

        self.logger.info(f"找到 {target_rows.count()} 个包含 '{text}' 的数据行")
        return target_rows

    def _get_cell_contents(self, target_row):
        """公共方法：获取单元格内容并进行清洗"""
        cells = target_row.get_by_role("cell").all()
        # cell_contents = [cell.inner_text() for cell in cells]
        cell_contents = [cell.text_content() for cell in cells[:-1]]
        cell_contents = [re.sub(r'\s+', ' ', item).strip() for item in cell_contents]
        self.logger.info(f"页面数据行信息: {cell_contents}, 共{len(cell_contents)}个")
        return cell_contents

    def get_row_data(self, name: str) -> dict:
        """
        根据名称获取目标行数据，返回表头与单元格内容的键值对字典

        Args:
            name: 行名称，用于定位特定行

        Returns:
            dict: 表头与单元格内容的键值对字典，已移除空表头和"操作"列

        Raises:
            AssertionError: 当找不到指定名称的行时
        """
        self.logger.info(f"开始获取资源({name})的数据")

        try:
            # 定位目标行
            target_row = self.get_row_by_name(name)
        except AssertionError as e:
            self.logger.error(f"获取数据行失败: {str(e)}")
            raise

        # 获取目标行所属表格的索引，以确保获取与之匹配的表头
        table_index = target_row.evaluate("""
            el => {
                const table = el.closest('.el-table');
                if (!table) return -1;
                return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
            }
        """)

        # 获取当前表格对应的表头，兜底使用全局 table_headers
        if table_index != -1:
            headers = self.locator(".el-table").nth(table_index).locator(".el-table__header-wrapper th").all_text_contents()
        else:
            headers = self.table_headers

        # 清理表头文本中的特殊空白字符（如 \xa0、&nbsp;），与 _get_cell_contents 保持一致
        headers = [re.sub(r'\s+', ' ', h).strip() for h in headers]

        cell_contents = self._get_cell_contents(target_row)

        # 组合数据，将表头和单元格内容对应起来
        result = dict(zip(headers, cell_contents))
        self.logger.debug(f"原始数据行: {result}")

        # 移除不需要的键
        exclude_headers = ["", "操作"]
        for key in exclude_headers:
            if key in result:
                del result[key]

        self.logger.info(f"处理后的数据: {result}")
        return result

    def get_column_data(self, header_name: str, deduplicate: bool = True, context: str = "auto"):
        """根据表头名称获取该列的所有数据
            Args:
                header_name: 表头名称
                deduplicate: 是否处理合并单元格的重复值
                context: "auto" | "dialog" | "main" | "active-tab"
                    - auto: 自动判断
                    - dialog: 优先查找弹窗内的表格
                    - main: 只查找主页面表格
                    - active-tab: 只查找当前激活的tab页内的表格
        """
        # 根据上下文缩小搜索范围
        if context == "dialog":
            # 优先查找弹窗内的表格
            dialog = self.get_by_role("dialog").filter(has=self.page.locator(".el-table"))
            if dialog.count() > 0 and dialog.is_visible():
                search_root = dialog.first
            else:
                search_root = self
        elif context == "active-tab":
            # 查找当前激活的tab页
            active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])")
            if active_tab.count() > 0:
                search_root = active_tab.first
            else:
                search_root = self
        elif context == "auto":
            try:
                dialog = self.locator(".el-tab-pane:not([aria-hidden='true'])")
                search_root = dialog.first
            except Exception as e:
                try:
                    active_tab = self.get_by_role("dialog").filter(has=self.page.locator(".el-table"))
                    search_root = active_tab.first
                except Exception as e:
                    search_root = self
        else:
            search_root = self
        a = search_root
        table_wrappers = search_root.locator(".el-table").all()
        # 获取所有表格包装器，过滤出可见的
        visible_table = None
        target_header_index = None

        for table in table_wrappers:
            try:
                # 检查表格是否可见且有数据
                if not table.is_visible():
                    continue

                # 获取该表格的表头
                header_wrapper = table.locator(".el-table__header-wrapper")
                if header_wrapper.count() == 0:
                    continue

                headers = header_wrapper.locator("th").all_text_contents()

                # 检查是否包含目标表头
                if header_name in headers:
                    visible_table = table
                    target_header_index = headers.index(header_name)
                    self.logger.info(f"找到包含 '{header_name}' 的可见表格，表头: {headers}")
                    break

            except Exception as e:
                self.logger.debug(f"检查表格时出错: {e}")
                continue

        # 如果没找到包含目标表头的可见表格，使用默认方式
        if visible_table is None:
            self.logger.info(f"未找到包含 '{header_name}' 的可见表格，使用默认方式")
            headers = self.table_headers
            if header_name not in headers:
                self.logger.warning(f"表头 '{header_name}' 不存在")
                return []
            target_header_index = headers.index(header_name)
            # 使用默认的 table_rows
            all_rows = self.table_rows
        else:
            # 使用找到的表格的数据行
            body_wrapper = visible_table.locator(".el-table__body-wrapper")
            all_rows = body_wrapper.locator("tr").all()

        self.logger.info(f"表头 '{header_name}' 的索引位置: {target_header_index}")
        self.logger.info(f"获取到的数据行共{len(all_rows)}行")

        # 提取列数据
        column_data = []
        for i, row in enumerate(all_rows):
            try:
                cells = row.get_by_role("cell").all()
                if len(cells) > target_header_index:
                    cell_content = cells[target_header_index].text_content()
                    # 清洗数据，处理HTML中的空白字符、换行符等
                    cleaned_content = re.sub(r'\s+', ' ', cell_content).strip()
                    # 处理合并单元格导致的重复值
                    if deduplicate and cleaned_content:
                        parts = cleaned_content.split()
                        # 如果所有部分都相同，只保留一个
                        if len(set(parts)) == 1:
                            cleaned_content = parts[0]
                        else:
                            cleaned_content = cleaned_content
                    if cleaned_content:  # 只添加非空内容
                        column_data.append(cleaned_content)
                        self.logger.debug(f"第{i + 1}行数据: {cleaned_content}")
            except Exception as e:
                self.logger.warning(f"获取第{i + 1}行数据时出错: {e}")

        self.logger.info(f"获取到的列数据共{len(column_data)}条: {column_data}")
        return column_data

    def select_rows_by_names(self, names):
        """公共方法: 根据名称列表勾选表格行

        Args:
            names: 资源名称列表
        """

        # 选择指定的行
        for name in names:
            loc = self.get_by_role("row", name=name).locator("label span").last # 存在挂载云盘的虚机nth(1)方法不能勾选
            if not loc.is_checked():
                loc.click()
                self.logger.info(f"勾选资源 '{name}'")

    def get_row_data_by_locator(self, loc):
        """获取指定行数据"""

        # 获取表头和单元格内容
        headers = self.table_headers
        cell_contents = self._get_cell_contents(loc)
        # 组合数据，将表头和单元格内容对应起来
        result = dict(zip(headers, cell_contents))
        self.logger.debug(f"原始数据行: {result}")

        # 移除不需要的键
        exclude_headers = ["", "操作"]
        for key in exclude_headers:
            if key in result:
                del result[key]
        return result

    def assert_row_contains(self, name: str, expected_data: str, timeout=300):
        """
        断言指定行数据包含期望数据

        Args:
            name: 行名称，用于定位特定行
            expected_data: 期望数据

        Raises:
            AssertionError: 当行数据不包含期望数据时
        """

        target_row = self.get_row_by_name(name)

        # expect(target_row.text_content()).contains(expected_data, timeout=3000)
        timeout = timeout * 1000
        expect(target_row).to_contain_text(expected_data, timeout=timeout)
        self.logger.info(f"行 '{name}' 包含期望数据 '{expected_data}'")


    def set_table_header(self, names, enable=True):
        """设置表头列

        Args:
            names: 列名称
            enable: 是否展示，默认为True
        """
        if isinstance(names, str):
            names = [names]
        self.locator(".el-icon-setting").click()
        for name in names:
            locs = [
                self.get_by_label("checkbox-group").get_by_text(name, exact=True),
                self.get_by_label("checkbox-group").locator("div").filter(has_text=re.compile(fr"^{name}$")),
                self.get_by_label("设置表头").get_by_text(name, exact=True),
                self.get_by_text(name, exact=True),
            ]
            loc = self._find_element(locs, f"checkbox{name}")
            if enable and not loc.is_checked():
                loc.click()
            elif not enable and loc.is_checked():
                loc.click()
        try:
            self.dialog_confirm.click()
        except:
            self.locator(".el-icon-setting").click() # 收起下拉

        self.wait_for_page_ready()
        self.logger.info(f"表头设置完成 {'显示' if enable else '隐藏'}{names}")

    def sort_by_header(self, header_name: str, order: str = "desc"):
        """点击表头进行排序

        Args:
            header_name: 表头名称，如"创建时间"
            order: 排序方式，"asc"升序或"desc"降序，默认降序
        """
        header_cell = self.get_by_role("cell", name=header_name)
        if header_cell.count() == 0:
            self.logger.warning(f"未找到表头: {header_name}")
            return

        # 直接获取 header_cell 自身的 class 属性
        class_attr = header_cell.get_attribute("class") or ""

        is_asc_active = "ascending" in class_attr
        is_desc_active = "descending" in class_attr

        # 如果已经是目标排序状态，不再点击
        if order == "desc" and is_desc_active:
            self.logger.info(f"已经是 {header_name} 降序排列")
            return
        if order == "asc" and is_asc_active:
            self.logger.info(f"已经是 {header_name} 升序排列")
            return

        # 点击目标排序箭头
        caret_wrapper = header_cell.locator(".caret-wrapper")
        if order == "desc":
            caret_wrapper.locator("i.descending").click()
            self.logger.info(f"已按 {header_name} 降序排列")
        else:
            caret_wrapper.locator("i.ascending").click()
            self.logger.info(f"已按 {header_name} 升序排列")
