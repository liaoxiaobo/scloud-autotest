from playwright.sync_api import Page, expect
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
        """根据选择器定位页面元素"""
        self.logger.info(f"定位元素: {selector}")
        return self.page.locator(selector)

    def get_by_test_id(self, test_id):
        """通过测试ID定位元素"""
        self.logger.info(f"通过测试ID定位元素: {test_id}")
        return self.page.get_by_test_id(test_id)

    def get_by_role(self, role, name=None, exact=False):
        """通过角色和名称定位元素"""
        self.logger.info(f"通过角色和名称定位元素: role={role}, name={name}")
        return self.page.get_by_role(role, name=name, exact=exact)

    def get_by_placeholder(self, text, exact=False):
        """通过占位符定位元素"""
        self.logger.info(f"通过占位符定位元素: {text}")
        return self.page.get_by_placeholder(text, exact=exact)

    def get_by_label(self, text, exact=False):
        """通过标签文本定位元素"""
        self.logger.info(f"通过标签文本定位元素: {text}")
        return self.page.get_by_label(text, exact=exact)

    def get_by_text(self, text, exact=False):
        """通过文本内容定位元素"""
        self.logger.info(f"通过文本内容定位元素: {text}")
        return self.page.get_by_text(text, exact=exact)

    def get_by_alt_text(self, text, exact=False):
        """通过ALT文本定位元素"""
        self.logger.info(f"通过ALT文本定位元素: {text}")
        return self.page.get_by_alt_text(text, exact=exact)

    def get_by_title(self, text, exact=False):
        """通过标题定位元素"""
        self.logger.info(f"通过标题定位元素: {text}")
        return self.page.get_by_title(text, exact=exact)

    def click(self, selector):
        """元素操作方法：点击"""
        try:
            original_selector = selector
            formatted_selector = _format_selector(selector)
            result = self.page.click(formatted_selector)
            self.logger.info(f"成功点击元素: {original_selector}")
            return result
        except Exception as e:
            self.logger.error(f"点击元素失败: {original_selector}")
            raise

    def fill(self, selector, value):
        """元素操作方法：输入文本"""
        # 类型安全转换
        if isinstance(value, (int, float)):
            value = str(value)
        try:
            result = self.page.fill(selector, value)
            self.logger.info(f"成功输入文本: selector={selector}, value={value}")
            return result
        except Exception as e:
            self.logger.error(f"输入文本失败: selector={selector}, value={value}")
            raise

    def hover(self, selector):
        """元素操作方法：悬停"""
        try:
            original_selector = selector
            formatted_selector = _format_selector(selector)
            result = self.page.hover(formatted_selector)
            self.logger.info(f"成功悬停元素: {original_selector}")
            return result
        except Exception as e:
            self.logger.error(f"悬停元素失败: {original_selector}")
            raise