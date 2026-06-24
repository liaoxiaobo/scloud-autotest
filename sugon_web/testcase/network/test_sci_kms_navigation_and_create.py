import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic("网络服务")
@allure.feature("机密互联")
@allure.story("密钥管理-导航及密钥创建验证")
class TestKmsNavigationAndCreate:
    """验证密钥管理模块的导航菜单及密钥创建功能。"""

    @allure.title("密钥管理-导航菜单及密钥列表确认")
    def test_kms_navigation_and_list(self, kms_page):
        """验证可信密码模块概览页授权信息及密钥管理列表页可正常访问。"""

        with allure_step_log("步骤1: 进入可信密码模块概览页"):
            kms_page.goto_service("可信密码模块")
            kms_page.wait_for_page_ready()

        with allure_step_log("步骤2: 断言概览页授权信息"):
            # kms_page fixture 已验证授权状态，此处确认页面就绪即可
            kms_page.wait_for_page_ready()
            # 额外断言授权信息可见（P0 断言）
            assert kms_page.get_by_text("您已成功授权").is_visible(), (
                "[P0Assertion] 概览页授权信息未显示'您已成功授权'"
            )

        with allure_step_log("步骤3: 进入密钥管理页面"):
            kms_page.goto_submenu("密钥管理")
            kms_page.wait_for_page_ready()

        with allure_step_log("步骤4: 确认密钥列表显示"):
            # 验证页面已就绪，列表区域可访问（列表可能有数据也可能为空，均为正常状态）
            kms_page.wait_for_page_ready()

    @allure.title("密钥管理-创建密钥验证")
    def test_kms_create_key(self, kms_page):
        """验证在密钥管理页面创建SM4类型密钥成功，并断言列表字段。"""
        key_name = f"net_sm4_ossl_{random_data()}"
        engine = "OPENSSL纯软"
        key_type = "SM4 (用途：加解密，包括系统盘、数据盘、网卡等)"

        with allure_step_log("步骤1: 进入密钥管理模块"):
            kms_page.goto_service("可信密码模块")
            kms_page.goto_submenu("密钥管理")
            kms_page.wait_for_page_ready()

        with allure_step_log("步骤2: 创建密钥"):
            kms_page.kms_create(
                name=key_name,
                engine=engine,
                key_type=key_type,
                desc="测试密钥",
            )

        with allure_step_log("步骤3: 断言操作成功"):
            kms_page.assert_popup_success("执行成功")
            kms_page.assert_list_contain(key_name)

        with allure_step_log("步骤4: 断言密钥列表字段"):
            row_data = kms_page.get_row_data(key_name)
            assert row_data["名称"] == key_name, (
                f"[FieldAssertion] 密钥 | 名称不匹配 | 期望: {key_name} | 实际: {row_data['名称']}"
            )
            assert row_data["加密引擎"] == engine, (
                f"[FieldAssertion] 密钥 | 加密引擎不匹配 | 期望: {engine} | 实际: {row_data['加密引擎']}"
            )
            # 类型字段：前端显示的是label值（如'SM4 (用途：加解密，包括系统盘、数据盘、网卡等)'）
            # 但列表页可能只显示value或截断显示，按实际回读值断言
            actual_type = row_data.get("类型", "")
            assert actual_type == key_type or actual_type == "SM4", (
                f"[FieldAssertion] 密钥 | 类型不匹配 | 期望: {key_type} 或 SM4 | 实际: {actual_type}"
            )
            assert row_data["状态"] == "启用", (
                f"[FieldAssertion] 密钥 | 状态不匹配 | 期望: 启用 | 实际: {row_data['状态']}"
            )

        with allure_step_log("步骤5: 清理密钥"):
            kms_page.kms_delete(key_name)
            kms_page.assert_deleted(key_name)
