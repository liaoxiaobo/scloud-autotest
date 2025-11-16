from playwright.sync_api import Page, expect, BrowserContext
from sugon_web.utils.logger import logger


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
    def switch_to_new_tab(self, pageindex=-1):
        """切换到新打开的标签页"""
        try:
            # 获取当前浏览器上下文中的所有页面
            pages = self.page.context.pages
            # 切换到最新打开的页面（通常是最后一个）
            if len(pages) > 1:
                new_page = pages[pageindex]
                self.page = new_page
                self.logger.info("成功切换到新标签页")
                return new_page
            else:
                self.logger.warning("没有检测到新标签页")
                return self.page
        except Exception as e:
            self.logger.error(f"切换标签页失败: {str(e)}")
            raise