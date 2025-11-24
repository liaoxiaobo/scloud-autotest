import re
import time
from functools import wraps
from typing import Callable
from playwright.sync_api import expect, Page, Locator
from sugon_web.common.playwright import Playwright


# 服务导航映射表 - 支持不同层级结构
SERVICE_MAP = {
    # 资源中心 -> 二级菜单 -> 服务 (三层结构)

    # 计算服务
    '弹性云服务器': ('资源中心', '计算'),
    '裸金属': ('资源中心', '计算'),

    # 网络服务
    '虚拟私有云': ('资源中心', '网络'),
    '云防火墙': ('资源中心', '网络'),
    '专有网络VPN': ('资源中心', '网络'),

    # 存储服务
    '云硬盘': ('资源中心', '存储'),
    '对象存储': ('资源中心', '存储'),
    '对象存储专业版': ('资源中心', '存储'),
    '文件存储': ('资源中心', '存储'),


    # 容器服务
    '云容器引擎': ('资源中心', '容器'),
    '应用市场': ('资源中心', '容器'),
    '容器镜像服务': ('资源中心', '容器'),
    '服务治理': ('资源中心', '容器'),

    # 数据库服务
    'AnhanDB(for MySQL)': ('资源中心', '数据库'),
    'AnhanDB(for PostgreSQL)': ('资源中心', '数据库'),
    'AnhanDB(for MongoDB)': ('资源中心', '数据库'),
    '数据仓库 Doris': ('资源中心', '数据库'),

    # 中间件服务
    'AnhanDB(for Redis)': ('资源中心', '中间件'),
    '分布式消息服务 Kafka': ('资源中心', '中间件'),
    '分布式消息服务 RabbitMQ': ('资源中心', '中间件'),
    '云搜索服务': ('资源中心', '中间件'),
    '监控服务': ('资源中心', '中间件'),

    # 基础设施 -> 服务 (两层结构)
    '区域资源': ('基础设施',),
    '计算设施': ('基础设施',),
    '网络设施': ('基础设施',),
    '存储设施': ('基础设施',),
    '备份设施': ('基础设施',),

    # 运维 -> 服务 (两层结构)
    '监控': ('运维',),
    '告警': ('运维',),
    '消息日志': ('运维',),
    '智能搜索': ('运维',),
    '一键巡检': ('运维',),
    '平台升级': ('运维',),
}

def submenu(name: str) -> Callable:
    """装饰器：确保在指定的EVS子菜单页面"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.goto_submenu(name)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

class BasePage(Playwright):

    def __init__(self, page: Page, env: dict) -> None:
        super().__init__(page)
        self.env = env
        self.storage_pool, self.volume_type = env['stor'] + '-test', env['stor'] + '-type'

    @property
    def popup(self) -> Locator:
        """公共元素:页面弹窗"""
        return self.locator(".el-message__content")

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
            self.get_by_role("textbox", name="搜索（固定IP）"),
            self.locator(".input-with-select > .el-input__inner")
        ]

        return self._find_element(locators, "搜索框")

    @property
    def _btn_search(self) -> Locator:
        """公共元素:搜索按钮"""
        return self.get_by_text("搜索", exact=True)

    @property
    def btn_reset(self) -> Locator:
        """公共元素:重置按钮"""
        return self.get_by_text("重置", exact=True)

    @property
    def btn_refresh(self) -> Locator:
        """公共元素:刷新按钮"""
        locators = [
            self.locator("#serverRefresh"),
            self.locator(".el-icon-refresh")
        ]

        return self._find_element(locators, "刷新按钮")

    @property
    def btn_batch_delete(self) -> Locator:
        """公共元素: 批量删除按钮"""
        locators = [
            self.get_by_text("批量删除", exact=True),
            self.get_by_text("删除")
        ]

        return self._find_element(locators, "批量删除按钮")

    @property
    def dialog_confirm(self) -> Locator:
        """公共元素:对话框确定按钮"""
        locators = [
            self.get_by_role("dialog").get_by_text("确定", exact=True),
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span")   # 云硬盘删除对话框
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
            # self.page.keyboard.press("Escape")    # 也可以按ESC键

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


    def goto_service(self, service: str):
        """公共方法: 智能导航到指定服务，支持不同层级结构

        Args:
            service: 服务名称，如 '云容器引擎'、'云硬盘'、'物理服务器' 等

        Returns:
            bool: 导航是否成功
        """
        if service not in SERVICE_MAP:
            self.logger.error(f"未知的服务: {service}，请检查服务名称或更新导航映射表")
            return False

        try:
            navigation_path = SERVICE_MAP[service]

            if len(navigation_path) == 1:
                # 两层结构：基础设施 -> 服务
                root_menu = navigation_path[0]
                self.hover(root_menu)
                self.click(service)
                self.wait_for_page_ready()
                self.logger.info(f"成功导航到服务: {root_menu} -> {service}")

            elif len(navigation_path) == 2:
                # 三层结构：资源中心 -> 二级菜单 -> 服务
                root_menu, category = navigation_path
                self.hover(root_menu)
                self.hover(category)
                self.click(service)
                self.wait_for_page_ready()
                self.logger.info(f"成功导航到服务: {root_menu} -> {category} -> {service}")

            else:
                self.logger.error(f"服务 {service} 的导航路径配置错误: {navigation_path}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"导航到服务 {service} 失败: {e}")
            return False

    def goto_submenu(self, submenu):
        """公共方法: 切换当前服务页面的子菜单

        Args:
            submenu: 子菜单名称，如下：
                - "概览"
                - "云硬盘"
                - "回收站"
                - "快照"
                - "弹性云服务器"
                - "虚拟私有云"
        """

        # 根据子菜单参数导航到对应页面
        self.locator("#cloud-menu-left").get_by_text(submenu, exact=True).click()
        self.page.wait_for_timeout(1000)    # 确保页面导航后页面加载完全
        self.wait_for_page_ready()
        self.logger.info(f"成功导航到子菜单: {submenu}")

    def assert_popup_success(self, text=None, timeout=5):
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

    def assert_status(self, name: str, status='运行', timeout=300, refresh=False, refresh_interval=5):
        """
        公共方法: 验证页面表格中指定资源的状态是否符合预期，支持定期刷新页面。

        Args:
            name: 资源名称
            status: 期望状态
            timeout: 超时时间（秒）
            refresh: 是否需要定期刷新页面，默认为False
            refresh_interval: 刷新间隔时间（秒），默认为5秒，仅在refresh=True时有效
        """

        # 不刷新模式：直接使用Playwright的高效等待机制
        if not refresh:
            timeout_ms = timeout * 1000  # 转换为毫秒
            target_row = self.get_row_by_name(name)
            expect(target_row).to_contain_text(status, timeout=timeout_ms, use_inner_text=True)
            self.logger.info(f"资源状态验证成功: {name} -> {status}")
            return

        # 刷新模式：定期刷新页面并检查状态
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 刷新页面
                if time.time() - start_time > 0:
                    self.btn_refresh.click()
                    self.wait_for_page_ready()

                # 定位目标行并检查状态
                target_row = self.get_row_by_name(name)
                current_status = target_row.inner_text()

                # 如果状态匹配，则返回
                if status in current_status:
                    self.logger.info(f"资源状态验证成功: {name} -> {status}")
                    return

            except Exception as e:
                self.logger.debug(f"检查状态时出错: {e}")

            # 等待下一次刷新
            time.sleep(refresh_interval)

        # 超时后抛出异常
        raise AssertionError(
            f"在{timeout}秒内未能获取到期望状态 '{status}'，当前状态: '{current_status if 'current_status' in locals() else '未知'}'")

    def assert_deleted(self, resource_name: str, timeout=300):
        """
        公共方法: 断言资源已从列表中删除（通过表格行不可见来判断）

        Args:
            resource_name: 资源名称
            timeout: 超时时间（秒）
        """
        timeout_ms = timeout * 1000  # 转换为毫秒
        try:
            # 定位包含资源名称的表格行
            resource_row = self.get_by_role("row", name=resource_name)

            # 断言行不可见（即删除成功）
            expect(resource_row).not_to_be_visible(timeout=timeout_ms)

            self.logger.info(f"资源从列表中删除成功: {resource_name}")

        except Exception as e:
            self.logger.error(f"资源删除验证失败: {resource_name}, 错误: {e}")
            raise AssertionError(f"资源 '{resource_name}' 仍在列表中，删除失败")

    def _btn_operation(self, name):
        """公共元素: 资源操作按钮"""

        # 定位资源行
        row = self.locator(f"tr:has-text('{name}')")

        # 提供两种定位方式，第二种适用于ecs列表页面
        locators = [
            self.get_by_role("row", name=name).get_by_role("button"),
            row.locator(".el-dropdown-selfdefine[title='操作']:has(.el-icon-setting)").last   # 组合定位器：title属性 + 类名 + 图标验证
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

    def click_dropdown_option(self, resource_name: str, option_text: str):
        """
        公共方法：点击指定资源行的下拉菜单选项

        Args:
            resource_name: 资源名称
            option_text: 下拉菜单选项文本（如"删除"、"编辑"等）
        """
        try:
            # 点击指定行资源的操作按钮
            operation_btn=self._btn_operation(resource_name)
            operation_btn.click()

            # 等待下拉菜单出现
            self.page.wait_for_timeout(1000)

            # 方法1：通过 aria-controls 属性精确定位
            try:
                dropdown_id = operation_btn.evaluate("element => element.getAttribute('aria-controls')")
                if dropdown_id:
                    specific_dropdown = self.page.locator(f"#{dropdown_id}")
                    option = specific_dropdown.get_by_text(option_text, exact=True)
                    if option.is_visible() and option.is_enabled():
                        option.click()
                        self.logger.info(f"点击资源操作选项: {resource_name} -> {option_text}")
                        return
                    else:
                        raise Exception(f"选项不可见或不可用: {option_text}")
                else:
                    raise Exception("未找到aria-controls属性")

            except Exception as e:
                # 方法2：备用方案 - 找到最后一个可见的下拉菜单
                self.logger.warning(f"主要方法失败，使用备用方案: {e}")

                dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')

                # 从后往前遍历，找到最后一个可见的下拉菜单
                for i in range(dropdown_menus.count() - 1, -1, -1):
                    menu = dropdown_menus.nth(i)
                    if menu.is_visible():
                        option = menu.get_by_text(option_text, exact=True)
                        if option.count() > 0 and option.is_visible() and option.is_enabled():
                            option.click()
                            self.logger.info(f"通过备用方案点击选项: {resource_name} -> {option_text}")
                            return

                raise Exception(f"所有方法都失败，未找到可用的选项: {option_text}")

        except Exception as e:
            self.logger.error(f"点击资源操作选项失败: {resource_name} -> {option_text}, 错误: {e}")
            raise

    def wait_for_page_ready(self):
        """公共方法: 等待页面完全就绪"""
        self.page.wait_for_load_state("load")  # 等待页面加载完成（如图片、样式表、脚本）
        self.page.wait_for_load_state("domcontentloaded")  # 等待DOM加载完成
        # self.page.wait_for_load_state("networkidle")    # 等待网络活动静止

    def wait_for_operation_complete(self, timeout=30):
        """等待操作完成

        Args:
            timeout: 超时时间（秒）
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 检查是否有加载中的元素
                loading_elements = [
                    self.locator(".el-icon-loading"),
                    self.locator(".el-button.is-loading")
                ]

                # 如果没有加载中的元素，认为操作完成
                if not any(element.count() > 0 for element in loading_elements):
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
        # 使用更精确的定位器，只获取可见表头
        header_wrapper = self.locator(".el-table__header-wrapper")  # 页面存在多个表格或弹窗表格，该定位器也会获取到重复表头

        if header_wrapper.count() > 0:
            headers = header_wrapper.locator("th").all_text_contents()
            self.logger.info(f"表头信息: {headers}, 共{len(headers)}个")
        else:
            self.logger.warning(f"未找到表头信息，尝试使用备用定位方式")
            # 备用方案：如果找不到特定class的表头，使用原有方式
            if self.locator("thead").count() > 0:
                headers = self.locator("thead th").all_text_contents()
                self.logger.info(f"使用备用方式获取表头信息: {headers}, 共{len(headers)}个")
            else:
                self.logger.error(f"未找到任何表头信息")

        return headers

    @property
    def table_rows(self)-> Locator:
        """获取表格中的数据行，返回行定位器列表"""

        locator = self.locator(".el-table__body-wrapper tr")   # 解决tbody tr选择器可能会获取到重复表格的问题
        if locator.count() > 0:
            rows = locator.all()
            self.logger.info(f"成功获取表格行，共{len(rows)}行")
        else:
            self.logger.info(f"未找到表格行")
            rows = []
        return rows

    def get_row_by_name(self, name: str) -> Locator:
        """公共方法：根据名称查找数据行，用于获取单个或第一个匹配的行（前缀匹配优先）"""
        target_row = self.get_by_role("row", name=re.compile(rf"^{re.escape(name)}\s"))

        if target_row.count() == 0:
            raise AssertionError(f"未找到名称为 '{name}' 的数据行")

        return target_row

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
        cell_contents = [cell.text_content() for cell in cells]
        cell_contents = [re.sub(r'\s+', ' ', item).strip() for item in cell_contents]
        self.logger.info(f"获取到的单元格内容: {cell_contents}, 共{len(cell_contents)}个")
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
        self.logger.info(f"开始获取行数据: {name}")

        try:
            # 定位目标行
            target_row = self.get_row_by_name(name)
        except AssertionError as e:
            self.logger.error(f"获取行数据失败: {str(e)}")
            raise

        # 获取表头和单元格内容
        headers = self.table_headers
        cell_contents = self._get_cell_contents(target_row)

        # 组合数据，将表头和单元格内容对应起来
        result = dict(zip(headers, cell_contents))
        self.logger.debug(f"原始行数据: {result}")

        # 移除不需要的键
        exclude_headers = ["", "操作"]
        for key in exclude_headers:
            if key in result:
                del result[key]

        self.logger.info(f"处理后的行数据: {result}")
        return result

    def get_column_data(self, header_name: str):
        """根据表头名称获取该列的所有数据"""
        self.logger.info(f"获取列数据: {header_name}")

        # 获取表头信息
        headers = self.table_headers

        # 检查目标表头是否存在
        if header_name not in headers:
            self.logger.warning(f"表头 '{header_name}' 不存在")
            return []

        # 获取目标表头的列索引
        header_index = headers.index(header_name)
        self.logger.info(f"表头 '{header_name}' 的索引位置: {header_index}")

        # 获取所有数据行
        all_rows = self.table_rows

        # 提取列数据
        column_data = []
        for i, row in enumerate(all_rows):
            try:
                cells = row.get_by_role("cell").all()
                if len(cells) > header_index:
                    cell_content = cells[header_index].text_content()
                    # 清洗数据，处理HTML中的空白字符、换行符等
                    cleaned_content = re.sub(r'\s+', ' ', cell_content).strip()
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
            self.get_by_role("row", name=name).locator("label span").nth(1).click()
