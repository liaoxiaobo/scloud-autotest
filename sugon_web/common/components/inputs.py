"""
【职责】封装常见输入框定位器（名称、密码、搜索框），统一处理 Element UI 表单中的文本输入场景。

【层级】Page 层；被 BasePage 组合，page object 通过 BasePage 间接使用。

【接口】
- input_name() -> Locator：实例名称输入框。
- input_password() -> Locator：管理员密码输入框。
- input_confirm_password() -> Locator：确认密码输入框。
- _input_search -> Locator：搜索框（主要供 ActionsMixin.search 使用）。

【示例】
class RedisPage(BasePage):
    def create_instance(self, name, password):
        self.btn_create.click()
        self.input_name().fill(name)
        self.input_password().fill(password)
        self.dialog_confirm.click()
"""

import re

from playwright.sync_api import Locator


class InputsMixin:
    """输入框类组件 Mixin。"""

    def input_name(self) -> Locator:
        """获取实例名称输入框定位器。"""
        return self.locator("form").filter(has_text="基本设置").get_by_role("textbox").first

    def input_password(self) -> Locator:
        """获取管理员密码输入框定位器。"""
        return self.get_by_placeholder("请输入管理员用户密码")

    def input_confirm_password(self) -> Locator:
        """获取确认密码输入框定位器。"""
        return self.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")

    @property
    def _input_search(self) -> Locator:
        """公共元素: 搜索框"""
        locators = [
            self.get_by_role("textbox", name="搜索（规格名称）"),
            self.get_by_role("textbox", name="搜索（名称）"),
            self.get_by_role("textbox", name="搜索(名称)"),
            self.get_by_role("textbox", name="搜索（固定IP）"),
            self.get_by_role("textbox", name="搜索（公网IP）"),
            self.get_by_role("textbox", name="搜索（参数名称）"),
            self.get_by_role("textbox", name="搜索（快照名称）"),
            self.locator(".input-with-select > .el-input__inner"),
            self.get_by_role("textbox", name="请输入设备名称"),
            self.get_by_role("textbox", name="搜索(实例名称)"),
            self.get_by_placeholder("搜索(目的地址)"),
            # BMS 裸金属页面搜索框
            self.get_by_role("textbox", name="搜索（网络名称）"),
            self.get_by_role("textbox", name="搜索（物理机）"),
            self.get_by_role("textbox", name="搜索（带外IP）"),
        ]
        return self._find_element(locators, "搜索框")
