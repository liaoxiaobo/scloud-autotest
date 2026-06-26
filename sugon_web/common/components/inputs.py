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
            # 传输策略组/机密互联页面搜索框
            self.get_by_placeholder("搜索"),
        ]
        return self._find_element(locators, "搜索框")
