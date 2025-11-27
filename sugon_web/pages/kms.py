from sugon_web.common.base import BasePage, submenu
from playwright.sync_api import Page
import re
import pytest


class KmsPage(BasePage):
    """密钥管理服务页面"""

    def __init__(self, page: Page, env: dict) -> None:
        super().__init__(page, env)

    @property
    def _input_name(self):
        """密钥名称输入框"""
        return self.locator("form div").filter(has_text="名称").get_by_role("textbox")

    @property
    def _input_desc(self):
        """描述输入框"""
        return self.locator("textarea")

    @property
    def _select_engine(self):
        """加密引擎选择框"""
        return self.locator("div").filter(has_text=re.compile(r"^加密引擎")).get_by_placeholder("请选择")

    @property
    def _select_type(self):
        """密钥类型选择框"""
        return self.locator("div").filter(has_text=re.compile(
            r"^类型SM2 \(用途：签名验签\)HMAC_SM3 \(用途：生成验证MAC\)SM4 \(用途：加解密，包括系统盘、数据盘、网卡等\)$")).get_by_placeholder("请选择")

    def _select_engine_option(self, option):
        """选择加密引擎选项

        Args:
            option: 要选择的加密引擎选项，如"HCT"、"TCM"、"OPENSSL纯软"
        """
        self._select_engine.click()
        self.page.wait_for_timeout(2000)    # 等待下拉选项加载完成

        # 检查下拉选项中是否存在指定的选项
        option_locator = self.locator("li").filter(has_text=option)
        if option_locator.count() > 0:
            # 选项存在，选择它
            option_locator.click()
        else:
            # 选项不存在，跳过测试
            self.logger.warning(f"加密引擎选项 '{option}' 不存在")
            pytest.skip(f"当前环境未开启HCT加密，跳过测试")

    def _select_type_option(self, option):
        """选择密钥类型选项"""
        self._select_type.click()
        self.get_by_text(option).click()

    @submenu("密钥管理")
    def kms_create(self, name, engine="HCT", key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)", desc=""):
        """创建密钥

        Args:
            name: 密钥名称
            engine: 加密引擎，支持"HCT"、"TCM"、"OPENSSL纯软"，默认为"HCT"
            key_type: 密钥类型，默认为"SM4 (用途：加解密，包括系统盘、数据盘、网卡等)"
            desc: 密钥描述，默认为空
        """
        self.get_by_text("创建密钥").click()

        # 填写密钥信息
        self._input_name.fill(name)
        self._select_engine_option(engine)
        self._select_type_option(key_type)
        self._input_desc.fill(desc)

        # 确认创建
        self.get_by_text("确定").nth(1).click()

    @submenu("密钥管理")
    def kms_delete(self, names):
        """删除密钥，支持单个和批量操作

        Args:
            names: 密钥名称（字符串）或密钥名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_dropdown_option(names, "删除")

        # 输入确认信息
        self.get_by_placeholder("请输入confirm").fill("confirm")
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

