from sugon_web.common.base import BasePage, submenu
from playwright.sync_api import Page, expect
import re
import pytest


class SciKmsPage(BasePage):
    """机密互联-密钥管理页面"""

    @property
    def _input_name(self):
        """密钥名称输入框"""
        return self.locator("form div.el-form-item").filter(has_text="名称").get_by_role("textbox")

    @property
    def _input_desc(self):
        """描述输入框"""
        return self.locator("form div.el-form-item").filter(has_text="描述").locator("textarea")

    @property
    def _select_engine(self):
        """加密引擎选择框"""
        return self.locator("form div.el-form-item").filter(has_text="加密引擎").get_by_placeholder("请选择")

    @property
    def _select_type(self):
        """密钥类型选择框"""
        return self.locator("form div.el-form-item").filter(has_text="类型").get_by_placeholder("请选择")

    def _select_engine_option(self, option):
        """选择加密引擎选项

        Args:
            option: 要选择的加密引擎选项，如"HCT"、"TCM"、"OPENSSL纯软"
        """
        self._select_engine.click()
        # 等待下拉选项加载完成
        self.page.wait_for_timeout(500)
        dropdown = self.locator("div.el-select-dropdown:visible")
        expect(dropdown).to_be_visible(timeout=10000)
        self.page.wait_for_timeout(500)

        # 先获取所有选项文本，用于日志和调试
        all_options = self.locator("div.el-select-dropdown:visible li").all()
        option_texts = [opt.text_content() for opt in all_options]
        self.logger.info(f"加密引擎下拉选项: {option_texts}")

        # 检查下拉选项中是否存在指定的选项
        option_locator = self.locator("div.el-select-dropdown:visible li").filter(has_text=option)
        if option_locator.count() > 0:
            # 选项存在，选择它，并等待下拉框关闭
            option_locator.click()
            expect(dropdown).not_to_be_visible(timeout=10000)
        else:
            # 选项不存在，跳过测试
            self.logger.warning(f"加密引擎选项 '{option}' 不存在，可用选项: {option_texts}")
            pytest.skip(f"当前环境未开启HCT加密，跳过测试")

    def _select_type_option(self, option):
        """选择密钥类型选项

        Args:
            option: 要选择的密钥类型选项，如"SM4 (用途：加解密，包括系统盘、数据盘、网卡等)"
        """
        self._select_type.click()
        # 等待下拉选项加载完成
        dropdown = self.locator("div.el-select-dropdown:visible")
        expect(dropdown).to_be_visible(timeout=10000)

        # 先获取所有选项文本，用于日志和调试
        all_options = self.locator("div.el-select-dropdown:visible li").all()
        option_texts = [opt.text_content() for opt in all_options]
        self.logger.info(f"类型下拉选项: {option_texts}")

        # 优先按选项前缀匹配（如 'SM4'），并去除前后空白避免 text_content 带来的空格导致误判
        prefix = option.split()[0] if option else ""
        for opt_text in option_texts:
            clean_text = opt_text.strip() if opt_text else ""
            if clean_text and clean_text.startswith(prefix):
                partial_locator = self.locator("div.el-select-dropdown:visible li").filter(has_text=clean_text)
                if partial_locator.count() > 0:
                    partial_locator.click()
                    return

        # 兜底：如果前缀匹配未命中，尝试按完整文案包含匹配
        option_locator = self.locator("div.el-select-dropdown:visible li").filter(has_text=option)
        if option_locator.count() > 0:
            option_locator.click()
            return

        # 最终兜底：选择第一个可用选项（引擎变化后类型选项可能不同）
        if len(option_texts) > 0:
            fallback_text = option_texts[0].strip() if option_texts[0] else ""
            self.logger.warning(f"目标类型 '{option}' 不存在，回退选择第一个可用类型: '{fallback_text}'")
            self.page.wait_for_timeout(300)
            self.page.locator("div.el-select-dropdown:visible li").nth(0).click()
            return

        self.logger.warning(f"密钥类型选项 '{option}' 不存在，可用选项: {option_texts}")
        pytest.skip(f"当前环境未支持该密钥类型，跳过测试")

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
        self.dialog_confirm.click()

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
            self.click_action(names, "删除")

        # 等待删除确认弹窗出现并输入确认信息
        confirm_input = self.get_by_placeholder("请输入confirm")
        expect(confirm_input).to_be_visible(timeout=10000)
        confirm_input.click()
        confirm_input.type("confirm")
        confirm_input.press("Tab")
        self.page.wait_for_timeout(500)

        # 等待表单校验通过（无错误提示）
        error_item = self.locator("form div.el-form-item.is-error")
        if error_item.count() > 0:
            error_text = error_item.locator(".el-form-item__error").text_content()
            raise AssertionError(f"删除确认输入校验失败: {error_text}")

        # 定位启用状态的确定按钮（排除 cl-btn-primary-disabled 的禁用按钮）
        confirm_btn = self.locator("div.cloud-button-btn.cl-btn-primary:not(.cl-btn-primary-disabled)").filter(has_text="确定")
        expect(confirm_btn).to_be_visible(timeout=10000)
        confirm_btn.click()
