import time

from playwright.sync_api import Page, expect, BrowserContext, Locator
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
        self.logger = logger

    def locator(self, selector):
        """创建页面元素定位器，返回自定义包装的定位器

        Args:
            selector: 元素选择器

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"创建定位器: {selector}")
        original_locator = self.page.locator(selector)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_test_id(self, test_id):
        """通过测试ID创建定位器

        Args:
            test_id: 测试ID

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过测试ID创建定位器: {test_id}")
        original_locator = self.page.get_by_test_id(test_id)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_role(self, role, name=None, exact=False):
        """通过角色和名称创建定位器

        Args:
            role: 元素角色
            name: 元素名称
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过角色创建定位器: role={role}, name={name}")
        original_locator = self.page.get_by_role(role, name=name, exact=exact)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_placeholder(self, text, exact=False):
        """通过占位符创建定位器

        Args:
            text: 占位符文本
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过占位符创建定位器: text={text}, exact={exact}")
        original_locator = self.page.get_by_placeholder(text, exact=exact)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_label(self, text, exact=False):
        """通过标签文本创建定位器

        Args:
            text: 标签文本
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过标签文本创建定位器: text={text}, exact={exact}")
        original_locator = self.page.get_by_label(text, exact=exact)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_text(self, text, exact=False):
        """通过文本内容创建定位器

        Args:
            text: 文本内容
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过文本内容创建定位器: text={text}, exact={exact}")
        original_locator = self.page.get_by_text(text, exact=exact)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_alt_text(self, text, exact=False):
        """通过ALT文本创建定位器

        Args:
            text: ALT文本
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过ALT文本创建定位器: text={text}, exact={exact}")
        original_locator = self.page.get_by_alt_text(text, exact=exact)
        return CustomLocator(original_locator, self, self.logger)

    def get_by_title(self, text, exact=False):
        """通过标题创建定位器

        Args:
            text: 标题文本
            exact: 是否精确匹配

        Returns:
            CustomLocator: 自定义包装的定位器对象
        """
        self.logger.debug(f"通过标题创建定位器: text={text}, exact={exact}")
        original_locator = self.page.get_by_title(text, exact=exact)
        return CustomLocator(original_locator, self, self.logger)


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
            try:
                self.page.click(formatted_selector)
            except Exception:
                # 回退1：使用精确文本匹配
                try:
                    self.page.get_by_text(original_selector, exact=True).first.click()
                except Exception:
                    # 回退2：force=True 强制点击（处理不可见但被折叠的元素）
                    try:
                        self.page.get_by_text(original_selector, exact=True).first.click(force=True)
                    except Exception:
                        # 回退3：JavaScript 点击
                        self.page.evaluate(
                            f"() => {{ const el = document.evaluate(\"//*[contains(text(), '{original_selector}')]\", document).iterateNext(); if(el) el.click(); }}"
                        )
            self.logger.info(f"成功点击元素: {original_selector}")
            self.wait_for_page_ready()
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
    def new_tab_context(self, trigger_action=None, wait_for_selector=None, timeout=30, wait_for_load_state="domcontentloaded"):
        """
        上下文管理器，用于在新标签页中执行操作

        Args:
            trigger_action (callable): 触发新标签页打开的操作（如：lambda: self.click_action(name, "登录")）
            wait_for_selector (str): 可选，等待特定选择器元素出现后再返回
            timeout (int): 等待超时时间（毫秒），默认为30秒
            wait_for_load_state (str): 等待页面加载状态，可选值为"domcontentloaded"、"load"或"networkidle"，默认为"domcontentloaded"
        """
        timeoutms = timeout * 1000
        original_page = self.page
        new_page = None

        try:
            if trigger_action:
                # 使用 expect_page 在触发操作前开始监听
                with self.page.context.expect_page() as new_page_info:
                    trigger_action()  # 执行触发(打开新页面的操作)
                    new_page = new_page_info.value  # 等待新页面
                    self.page = new_page
            else:
                # 直接等待已打开的新页面
                new_page = self.switch_to_new_tab(wait_for_selector, timeoutms, wait_for_load_state)

            yield new_page

        finally:
            # 确保返回原始页面并关闭新页面
            try:
                original_page.bring_to_front()
                self.page = original_page
                if new_page and new_page != original_page and not new_page.is_closed():
                    new_page.close()
                    self.logger.info("已自动关闭新标签页")
            except Exception as e:
                self.logger.warning(f"关闭新标签页时出错: {str(e)}")

    def wait_for_page_ready(self):
        """公共方法: 等待页面完全就绪"""
        self.page.wait_for_load_state("load")  # 等待页面加载完成（如图片、样式表、脚本）
        self.page.wait_for_load_state("domcontentloaded")  # 等待DOM加载完成
        # self.page.wait_for_load_state("networkidle")    # 等待网络活动静止
        # self.page.wait_for_selector(".el-loading-spinner", state='hidden')
        # 等待所有 .el-loading-spinner 元素隐藏
        loading_spinners = self.page.locator(".el-loading-spinner")
        count = loading_spinners.count()
        if count > 0:
            for i in range(count):
                loading_spinners.nth(i).wait_for(state='hidden')

    def wait_for_operation_complete(self, timeout=30):
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

class CustomLocator:
    """自定义定位器包装器，用于拦截 Locator 的方法调用"""

    def __init__(self, locator: Locator, playwright_instance, logger_instance):
        self._locator = locator
        self._playwright = playwright_instance
        self._logger = logger_instance

    def __str__(self):
        """返回定位器的字符串表示，便于调试"""
        try:
            # 获取原始 locator 的字符串表示
            original_str = str(self._locator)

            # 去除关键字后面的多余反斜杠
            cleaned_str = original_str.replace("url=\\'", "url='")
            cleaned_str = cleaned_str.replace('selector=\\\'', "selector='")
            cleaned_str = cleaned_str.replace('name=\\\'', "name='")
            cleaned_str = cleaned_str.replace('role=\\\'', "role='")
            cleaned_str = cleaned_str.replace('url=\\"', 'url="')
            cleaned_str = cleaned_str.replace('selector=\\"', 'selector="')
            cleaned_str = cleaned_str.replace('name=\\"', 'name="')
            cleaned_str = cleaned_str.replace('role=\\"', 'role="')

            return cleaned_str
        except Exception as e:
            # 如果出错，返回包含对象ID的信息
            self._logger.debug(f"生成定位器字符串表示时出错: {e}")
            return f"<Locator id={id(self._locator)}>"

    def __repr__(self):
        """返回定位器的正式字符串表示"""
        return self.__str__()

    def click(self, **kwargs):
        """点击元素，直接在内部 locator 上调用"""
        try:
            # 直接在内部 locator 上调用 click
            self._locator.click(**kwargs)
            # 触发等待（确保页面加载完成）
            self._playwright.wait_for_page_ready()
            self._playwright.wait_for_operation_complete()
        except Exception as e:
            self._logger.error(f"[CustomLocator.click] 点击失败: {e}")
            raise


    def __getattr__(self, name):
        """拦截所有属性访问，返回包装后的方法或属性"""
        # 直接委托给原始 locator
        attr = getattr(self._locator, name)

        # 如果是可调用对象（方法），则包装它
        if callable(attr):
            def wrapped_method(*args, **kwargs):
                result = attr(*args, **kwargs)

                # 如果返回的是 Locator，则继续包装
                if isinstance(result, Locator):
                    return CustomLocator(result, self._playwright, self._logger)

                return result

            return wrapped_method

        # 如果是属性且返回 Locator，则包装
        if isinstance(attr, Locator):
            return CustomLocator(attr, self._playwright, self._logger)

        return attr

# 让 expect() 能够识别 CustomLocator, 保存原始的 expect 函数
_original_expect = expect


def patched_expect(value, message=None):
    """
    补丁版本的 expect 函数，能够处理 CustomLocator 对象
    """
    # 如果传入的是 CustomLocator，提取其内部的 _locator
    if isinstance(value, CustomLocator):
        value = value._locator
    return _original_expect(value, message)


# 应用补丁到 playwright.sync_api 模块
try:
    import playwright.sync_api as playwright_sync_api
    playwright_sync_api.expect = patched_expect
    logger.info("成功应用 expect() 补丁，支持 CustomLocator")
except Exception as e:
    logger.error(f"应用 expect() 补丁失败: {e}")

# 导出补丁后的 expect
expect = patched_expect