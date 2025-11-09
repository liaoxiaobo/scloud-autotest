import re
from functools import wraps
from time import sleep
from playwright.sync_api import expect
from sugon_web.utils.logger import logger
from sugon_web.common.playwright import Playwright


# 服务导航映射表 - 支持不同层级结构
SERVICE_MAP = {
    # 资源中心 -> 二级菜单 -> 服务 (三层结构)

    # 计算服务
    '云服务器': ('资源中心', '计算'),
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

def submenu(name):
    """装饰器：确保在指定的EVS子菜单页面"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.goto_submenu(name)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

class BasePage(Playwright):

    def __init__(self, page, env, auto_login=True):
        super().__init__(page)
        self.env = env
        self.storage_pool, self.volume_type = env['stor'] + '-test', env['stor'] + '-type'
        if auto_login:
            self._auto_login()  # 根据参数决定是否自动登录

    def _auto_login(self):
        """自动登录"""
        if not self._is_logged_in():
            self._login()
            self.wait_for_page_ready()
            self.close_dialog_if_exists()

    def _is_logged_in(self):
        """检查是否已登录"""
        try:
            # 检查登录表单是否存在，如果存在说明未登录
            login_form = self.get_by_placeholder("请输入登录账号")
            login_form.wait_for(timeout=2000)
            return False
        except:
            # 找不到登录表单，说明已登录
            return True

    def _login(self):
        """执行登录操作"""
        username = self.env.get("username")
        password = self.env.get("password")
        
        if not username or not password:
            raise ValueError("环境配置中缺少用户名或密码")

        # 填写登录信息
        self._input_username.fill(username)
        self._input_password.fill(password)
        self._btn_login.click()

    @property
    def _input_username(self):
        """登录页面元素:用户名输入框"""
        return self.get_by_placeholder("请输入登录账号")

    @property
    def _input_password(self):
        """登录页面元素:密码输入框"""
        return self.get_by_placeholder("请输入登录密码")

    @property
    def _btn_login(self):
        """登录页面元素:登录按钮"""
        return self.get_by_text("登 录")

    @property
    def popup(self):
        """公共元素:页面弹窗"""
        return self.locator(".el-message__content")

    @property
    def btn_create(self):
        """公共元素:新建按钮"""
        button_texts = ["新建", "创建集群"]  # 优先匹配更具体的文本

        for text in button_texts:
            sleep(2)  # 确保页面按钮元素完全加载
            buttons = self.get_by_text(text, exact=True)
            if buttons.count() > 0:
                return buttons

        raise Exception("未找到新建按钮")

    @property
    def btn_submit(self):
        """公共元素:表单提交按钮"""
        button_texts = ["立即创建"]  # 优先匹配更具体的文本

        for text in button_texts:
            buttons = self.get_by_text(text)
            if buttons.count() > 0:
                return buttons

        raise Exception("未找到新建按钮")

    @property
    def _input_search(self):
        """公共元素:搜索框"""
        # 仅适用于规格搜索
        try:
            button = self.get_by_role("textbox", name="搜索（规格名称）")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过角色定位失败: {e}")

        # CSS定位(适用于列表页)
        try:
            button = self.locator(".input-with-select > .el-input__inner")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过CSS定位失败: {e}")

        raise Exception("定位失败：无法找到可见的搜索按钮")

    @property
    def _btn_search(self):
        """公共元素:搜索按钮"""
        return self.get_by_text("搜索", exact=True)

    @property
    def btn_reset(self):
        """公共元素:重置按钮"""
        return self.get_by_text("重置")

    @property
    def btn_refresh(self):
        """公共元素:刷新按钮"""
        return self.locator("#serverRefresh")

    @property
    def dialog_confirm(self):
        """公共元素:对话框确定按钮"""
        # 方法1：通过角色和名称定位
        try:
            button = self.get_by_role("dialog").get_by_text("确定")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过角色定位失败: {e}")

        # 方法二：CSS定位(适用于删除云盘对话框)
        try:
            button = self.locator("div:nth-child(2) > div > .cloud-button-btn > span")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过CSS定位失败: {e}")

        # 如果所有方法都失败，抛出异常
        raise Exception(f"无法定位‘确定’操作按钮")

    @property
    def dialog_cancel(self):
        """公共元素:对话框取消按钮"""
        # 方法1：通过角色和名称定位
        try:
            button = self.get_by_role("dialog").get_by_text("取消")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过角色定位失败: {e}")

        # 方法二：CSS定位(适用于删除云盘对话框)
        try:
            button = self.locator("div:nth-child(2) > div:nth-child(2) > .cloud-button-btn")
            if button.is_visible():
                return button
        except Exception as e:
            logger.debug(f"通过CSS定位失败: {e}")

        # 如果所有方法都失败，抛出异常
        raise Exception(f"无法定位‘取消’操作按钮")

    @property
    def dialog_close(self):
        """公共元素:对话框关闭按钮"""
        return self.get_by_role("button", name="Close")

    def close_dialog_if_exists(self):
        """公共方法: 关闭可能存在的对话框"""
        if self.dialog_close.is_visible():
            logger.info("发现未关闭的对话框，正在关闭...")
            self.dialog_close.click()
            # self.page.keyboard.press("Escape")    # 也可以按ESC键

    def search(self, keyword: str):
        """公共方法: 搜索操作"""
        try:
            self.logger.info(f"开始搜索: {keyword}")
            self._input_search.fill(keyword)
            self._btn_search.click()
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
                self.logger.info(f"成功导航到服务: {root_menu} -> {service}")

            elif len(navigation_path) == 2:
                # 三层结构：资源中心 -> 二级菜单 -> 服务
                root_menu, category = navigation_path
                self.hover(root_menu)
                self.hover(category)
                self.click(service)
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
        self.wait_for_page_ready()

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

    def assert_list_contain(self, keyword, name_column_index=2):
        """公共方法: 断言页面表格列表中某一列至少有一个元素包含指定关键字"""

        # 先获取所有行
        rows = self.locator("tbody tr")

        # 获取每行的资源名称
        actual_names = []
        if rows.count() > 0:
            for row in rows.all():
                name_cell = row.locator(f"td:nth-child({name_column_index})")
                name = name_cell.inner_text().strip()
                actual_names.append(name)

        matched = any(keyword in name for name in actual_names)
        assert matched, f"未找到包含关键字 '{keyword}' 的名称，实际名称列表: {actual_names}"

    def assert_status(self, name: str, status='运行中', timeout=60, name_column=2, target_column=0):
        """
        公共方法: 验证页面表格中指定资源的状态是否符合预期。

        Args:
            name: 资源名称
            status: 期望状态
            timeout: 超时时间（秒）
            name_column: 名称所在列（从1开始）
            target_column: 状态所在列（0表示整行匹配）
        """
        timeout_ms = timeout * 1000  # 转换为毫秒

        # 使用 getByRole 精确匹配行名称
        target_row = self.get_by_role("row", name=re.compile(rf"^{re.escape(name)}\s"))

        # 检查行是否存在，避免后续长时间等待
        try:
            expect(target_row).to_be_visible(timeout=5000)  # 短超时检查存在性
        except Exception:
            raise AssertionError(f"未找到名称为 '{name}' 的资源行")

        if target_column:
            column = target_row.locator(f"td:nth-child({target_column})")
            expect(column).to_contain_text(status, timeout=timeout_ms)
        else:
            expect(target_row).to_contain_text(status, timeout=timeout_ms)

    def assert_deleted(self, resource_name: str, timeout=60):
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
        # 两种定位方式，第二种适用于ecs列表页面
        buttons = [
            self.get_by_role("row", name=name).get_by_role("button"),
            self.locator(".el-table__fixed-body-wrapper > .el-table__body > tbody > tr:nth-child(1) > .el-table_1_column_13 > .cell > .el-dropdown > .cloud-button")
        ]
        for button in buttons:
            sleep(1)  # 确保页面按钮元素完全加载
            if button.is_visible():
                return button
        raise Exception("未找到资源操作按钮")


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
            self.logger.info(f"找到目标行: {resource_name}")
            self.logger.info(f"点击操作按钮: {resource_name}")
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
                        self.logger.info(f"通过aria-controls点击选项: {resource_name} -> {option_text}")
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
            self.logger.error(f"点击下拉菜单选项失败: {resource_name} -> {option_text}, 错误: {e}")
            raise

    def wait_for_page_ready(self):
        """公共方法: 等待页面完全就绪"""
        self.page.wait_for_load_state("networkidle", timeout=10000)  # 等待网络空闲
        self.page.wait_for_load_state("domcontentloaded", timeout=10000)  # 等待DOM加载完成
