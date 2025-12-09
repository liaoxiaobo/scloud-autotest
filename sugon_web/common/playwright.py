import time

from playwright.sync_api import Page, expect, BrowserContext
from sugon_web.utils.logger import logger
from contextlib import contextmanager


def _format_selector(selector):
    """格式化选择器，自动处理文本选择器的引号

    Args:
        selector: 原始选择器

    Return:
        str: 格式化后的选择器
    """
    # 如果已经有引号，保持原样
    if selector.startswith(('"', "'")):
        return selector

    # 如果是明显的CSS选择器，保持原样
    if selector.startswith(('#', '.', '[', '(')) or '//' in selector:
        return selector

    # 其他情况当作文本处理，添加双引号
    return f'"{selector}"'


class Playwright:

    def __init__(self, page: Page):
        self.page = page
        self.logger = logger  # 传递日志工具

    def locator(self, selector):
        """创建页面元素定位器

        Args:
            selector: 元素选择器

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"创建定位器: {selector}")
        return self.page.locator(selector)

    def get_by_test_id(self, test_id):
        """通过测试ID创建定位器

        Args:
            test_id: 测试ID

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过测试ID创建定位器: {test_id}")
        return self.page.get_by_test_id(test_id)

    def get_by_role(self, role, name=None, exact=False):
        """通过角色和名称创建定位器

        Args:
            role: 元素角色
            name: 元素名称
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过角色创建定位器: role={role}, name={name}")
        return self.page.get_by_role(role, name=name, exact=exact)

    def get_by_placeholder(self, text, exact=False):
        """通过占位符创建定位器

        Args:
            text: 占位符文本
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过占位符创建定位器: text={text}, exact={exact}")
        return self.page.get_by_placeholder(text, exact=exact)

    def get_by_label(self, text, exact=False):
        """通过标签文本创建定位器

        Args:
            text: 标签文本
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过标签文本创建定位器: text={text}, exact={exact}")
        return self.page.get_by_label(text, exact=exact)

    def get_by_text(self, text, exact=False):
        """通过文本内容创建定位器

        Args:
            text: 文本内容
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过文本内容创建定位器: text={text}, exact={exact}")
        return self.page.get_by_text(text, exact=exact)

    def get_by_alt_text(self, text, exact=False):
        """通过ALT文本创建定位器

        Args:
            text: ALT文本
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过ALT文本创建定位器: text={text}, exact={exact}")
        return self.page.get_by_alt_text(text, exact=exact)

    def get_by_title(self, text, exact=False):
        """通过标题创建定位器

        Args:
            text: 标题文本
            exact: 是否精确匹配

        Returns:
            Locator: 定位器对象
        """
        self.logger.debug(f"通过标题创建定位器: text={text}, exact={exact}")
        return self.page.get_by_title(text, exact=exact)

    def click(self, selector):
        """点击元素

        Args:
            selector: 元素选择器

        Raises:
            Exception: 点击失败时抛出异常
        """
        try:
            original_selector = selector
            formatted_selector = _format_selector(selector)
            self.page.click(formatted_selector)
            self.logger.info(f"成功点击元素: {original_selector}")
        except Exception as e:
            self.logger.error(f"点击元素失败: {original_selector}, 错误: {str(e)}")
            raise

    def fill(self, selector, value):
        """输入文本

        Args:
            selector: 元素选择器
            value: 输入值

        Raises:
            Exception: 输入失败时抛出异常
        """
        # 类型安全转换
        if isinstance(value, (int, float)):
            value = str(value)
        try:
            self.page.fill(selector, value)
            self.logger.info(f"成功输入文本: selector={selector}, value={value}")
        except Exception as e:
            self.logger.error(f"输入文本失败: selector={selector}, value={value}, 错误: {str(e)}")
            raise

    def hover(self, selector):
        """悬停在元素上

        Args:
            selector: 元素选择器

        Raises:
            Exception: 悬停失败时抛出异常
        """
        try:
            original_selector = selector
            formatted_selector = _format_selector(selector)
            self.page.hover(formatted_selector)
            self.logger.info(f"成功悬停元素: {original_selector}")
        except Exception as e:
            self.logger.error(f"悬停元素失败: {original_selector}, 错误: {str(e)}")
            raise

    # 切换浏览器tab页
    def switch_to_new_tab(self, wait_for_selector=None,timeout=30000, wait_for_load_state="domcontentloaded"):
        """
        切换到新打开的标签页，并等待页面加载完成
        Args:
            timeout (int): 等待超时时间（毫秒），默认为30秒
            wait_for_selector (str): 可选，等待特定选择器元素出现后再返回
            wait_for_load_state (str): 等待页面加载状态，可选值为"domcontentloaded"、"load"或"networkidle"，默认为"domcontentloaded"

        Returns:
            Page: 新切换到的页面对象
        """
        try:
            # 使用Promise方式等待新页面
            self.logger.info("尝试使用Promise方式等待新页面")
            with self.page.context.expect_page() as new_page_info:
                # 如果页面还没完全加载，可能需要短暂等待
                time.sleep(0.5)
            new_page = new_page_info.value
            # 更新当前页面对象引用
            self.page = new_page
            self.logger.info(f"成功切换到新标签页: {new_page.url}")
        except Exception as e:
            self.logger.error(f"使用Promise方式等待新页面失败: {str(e)}")
            raise Exception("无法检测到新标签页，请确认新标签页已正确打开")

        # 等待页面加载状态
        if wait_for_load_state:
            new_page.wait_for_load_state(wait_for_load_state, timeout=timeout)
            self.logger.debug(f"页面加载状态 '{wait_for_load_state}' 已完成")

        # 等待特定选择器出现（如果指定）
        if wait_for_selector:
            try:
                new_page.wait_for_selector(wait_for_selector, timeout=timeout)
                self.logger.debug(f"选择器 '{wait_for_selector}' 已出现")
            except Exception as e:
                self.logger.warning(f"等待选择器 '{wait_for_selector}' 超时: {e}")

        # 记录页面信息
        page_title = new_page.title() or "无标题"
        page_url = new_page.url or "无URL"
        self.logger.info(f"成功切换到标签页: 标题='{page_title}', URL='{page_url}'")
        return new_page

    @contextmanager
    def new_tab_context(self, wait_for_selector=None, timeout=30000, wait_for_load_state="domcontentloaded"):
        """
        上下文管理器，用于在新标签页中执行操作，并在操作完成后自动关闭标签页

        Args:
            wait_for_selector (str): 可选，等待特定选择器元素出现
            timeout (int): 等待超时时间（毫秒），默认为30秒
            wait_for_load_state (str): 等待页面加载状态，默认为"domcontentloaded"

        用法:
            with page.new_tab_context() as new_page:
                new_page.goto("https://example.com")
                # 在新页面上执行操作
                # 操作完成后，标签页会自动关闭
        """
        # 记录原始页面
        original_page = self.page

        try:
            # 切换到新标签页
            new_page = self.switch_to_new_tab(wait_for_selector, timeout, wait_for_load_state)
            yield new_page
        finally:
            # 确保返回原始页面并关闭新页面
            try:
                # 切换回原始页面
                original_page.bring_to_front()
                self.page = original_page

                # 关闭新页面
                if new_page != original_page:
                    new_page.close()
                    self.logger.info("已自动关闭新标签页")
            except Exception as e:
                self.logger.warning(f"关闭新标签页时出错: {str(e)}")