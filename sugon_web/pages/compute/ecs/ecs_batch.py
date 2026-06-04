from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsBatchMixin(BasePage):
    """ECS 批量操作。"""
    @submenu("弹性云服务器")
    def ecs_batch_bind_labels(self, names: list, label_names: list):
        self.select_rows_by_names(names)
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("批量标签设置")
        self.get_by_placeholder("请选择标签").click()
        for label_name in label_names:
            self.locator("li").filter(has_text=label_name).click()
        self.locator("form i").nth(3).click()
        self.dialog_confirm.click()
        logger.info(f"标签{label_names}绑定到云服务器{names}成功")


    @submenu("弹性云服务器")
    def ecs_batch_operations(self, names: list, operation: str):
        """批量操作云服务器

        Args:
            names: 云服务器名称列表
            operation: 操作类型，支持"批量重启"、"批量关机"、"批量启动"、"批量强制重启"等
        """
        try:
            # 选择指定的云服务器
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作").click()

            # 根据操作类型点击相应的选项
            self._click_batch_operation_option(operation)

            # 确认操作
            self._confirm_batch_operation(operation)

            logger.info(f"批量操作完成: {operation}, 云服务器: {names}")

        except Exception as e:
            logger.error(f"批量操作失败: {operation}, 云服务器: {names}, 错误: {e}")
            raise


    def _click_batch_operation_option(self, operation: str):
        """点击批量操作选项

        Args:
            operation: 操作类型
        """
        # 方法1: 通过aria-controls属性精确定位下拉菜单，然后查找选项
        try:
            operation_btn = self.get_by_role("button", name="更多操作")
            dropdown_id = operation_btn.evaluate("element => element.getAttribute('aria-controls')")
            if dropdown_id:
                specific_dropdown = self.page.locator(f"#{dropdown_id}")
                batch_option = specific_dropdown.get_by_text(operation, exact=True)
                if batch_option.is_visible() and batch_option.is_enabled():
                    batch_option.click()
                    return
                else:
                    raise Exception(f"{operation}选项不可见或不可用")
            else:
                raise Exception("未找到aria-controls属性")
        except Exception as e:
            # 方法2: 备用方案 - 找到最后一个可见的下拉菜单
            logger.warning(f"主要方法失败，使用备用方案: {e}")
            dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')

            # 从后往前遍历，找到最后一个可见的下拉菜单
            for i in range(dropdown_menus.count() - 1, -1, -1):
                menu = dropdown_menus.nth(i)
                if menu.is_visible():
                    option = menu.get_by_text(operation, exact=True)
                    if option.count() > 0 and option.is_visible() and option.is_enabled():
                        option.click()
                        return
            raise Exception(f"所有方法都失败，未找到可用的{operation}选项")


    def _confirm_batch_operation(self, operation: str):
        """确认批量操作

        Args:
            operation: 操作类型
        """
        # 根据不同的操作类型，使用不同的确认方式
        if operation == "批量重启":
            self.get_by_label("批量重启").get_by_text("确定").click()
        elif operation in ["批量关机", "批量启动"]:
            self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()
        elif operation == "批量强制重启":
            self.get_by_label("批量强制重启").get_by_text("确定").click()
        else:
            # 默认使用通用确认按钮
            self.dialog_confirm.click()


    @submenu("弹性云服务器")
    def ecs_batch_set_startup_order(self, names: list, order: int, delay):
        """批量设置云服务器启动顺序

        Args:
            names: 云服务器名称列表
            order: 启动顺序
            delay: 启动延迟时间(秒)
        """
        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击设置启动顺序按钮
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("设置启动顺序")

        # 设置每台服务器的启动顺序
        self.get_by_role("dialog", name="设置启动顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="启动延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"批量设置云服务器启动顺序完成: {names}")


    @submenu("弹性云服务器")
    def ecs_batch_set_shutdown_order(self, names: list, order: int, delay):
        """批量设置云服务器关机顺序

        Args:
            names: 云服务器名称列表
            order: 关机顺序
            delay: 启动延迟时间(秒)
        """
        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击设置关机顺序按钮
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option("设置关机顺序")

        # 设置每台服务器的启动顺序
        self.get_by_label("设置关机顺序").get_by_role("textbox").first.fill(str(order))

        # 设置启动延迟时间
        self.locator("form div").filter(has_text="关机延迟时间(秒)").get_by_role("textbox").fill(delay)

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"批量设置云服务器关机顺序完成: {names}")


    @submenu("弹性云服务器")
    def ecs_batch_agent_version(self, names: list, agent_conf: list):
        """批量Agent版本设置
        Args:
            names: 云服务器名称
            agent_conf: Agent版本设置
        """
        self.select_rows_by_names(names)

        self.get_by_role("button", name="更多操作").click()

        self._click_batch_operation_option("批量Agent版本设置")
        for conf in agent_conf:
            for agent_type, agent_version in conf.items():
                self.locator("label").filter(has_text=agent_type).click()
                self.page.wait_for_timeout(1000) # 等待页面加载完成
                locator = self.get_by_role("row",
                                           name=f"默认{agent_type} {agent_version} 系统默认，禁止修改").get_by_role(
                    "radio")
                if not locator.is_checked():
                    locator.click()

        self.dialog_confirm.click()
        logger.info(f"云服务器 {names}批量设置Agent版本{agent_conf}成功")
