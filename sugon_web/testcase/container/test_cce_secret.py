import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


# CSV 定义的测试数据
SECRET_DATA_NAME = "cce-test123-2312-2-w"
SECRET_DATA_CONTENT = "cce_test123.2312-2.-w" * 40
EDIT_CONTENT = "cce_test-CCE123!@##"

# 密钥创建用例（5968）固定测试数据
SECRET_CREATE_NAME = "test-est123"
SECRET_LABELS = {
    "test": "1024",
    "cce_test-12312345FF678901234567890a.bcdefghijklnmopqrs890":
        "cce_test-12312345678901234567890abcdefghijklnmopqrst1234567890",
}
SECRET_DATAS = {
    "cce-test2": "cce_test-122333322",
    "cce-.-test1": (
        "cce_./test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
    ),
}


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-密钥')
class TestCCESecretList:
    """CCE 密钥列表页测试类。"""

    @allure.title("密钥-创建和删除")
    def test_secret_create_and_delete(self, cce_page, cce_cluster):
        """测试创建密钥并验证列表数据，然后删除并验证清理。"""
        with allure_step_log("步骤1: 创建密钥"):
            cce_page.secret_create(
                name=SECRET_CREATE_NAME,
                secret_type="Opaque",
                labels=SECRET_LABELS,
                datas=SECRET_DATAS,
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表页数据一致性"):
            cce_page.secret_assert_list(SECRET_CREATE_NAME, secret_type="Opaque")

        with allure_step_log("步骤3: 删除密钥"):
            cce_page.secret_delete(SECRET_CREATE_NAME)

        with allure_step_log("步骤4: 验证被删除的密钥不存在"):
            cce_page.assert_list_not_contain(SECRET_CREATE_NAME, column_name="名称")


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-密钥-详情')
class TestCCESecretDetail:
    """CCE 密钥详情页测试类。"""

    @allure.title("密钥-详情添加和删除数据")
    def test_secret_data_add_and_delete(self, cce_page, cce_cluster):
        """测试密钥详情页添加数据后删除，并验证列表一致性。"""
        secret_name = f"sec-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建密钥"):
            cce_page.secret_create(name=secret_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 进入密钥详情页"):
            cce_page.secret_goto_detail(secret_name)

        with allure_step_log("步骤3: 添加数据"):
            cce_page.secret_data_add(SECRET_DATA_NAME, SECRET_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤4: 删除数据"):
            cce_page.secret_data_delete(SECRET_DATA_NAME)

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.secret_data_assert_not_list(SECRET_DATA_NAME)

        with allure_step_log("步骤6: 清理密钥"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.secret_delete(secret_name)
            cce_page.assert_deleted(secret_name)

    @allure.title("密钥-详情编辑数据")
    def test_secret_data_edit(self, cce_page, cce_cluster):
        """测试密钥详情页编辑数据，并验证内容一致性。"""
        secret_name = f"sec-edit-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建带数据的密钥"):
            cce_page.secret_create(
                name=secret_name,
                datas={SECRET_DATA_NAME: SECRET_DATA_CONTENT}
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 进入密钥详情页"):
            cce_page.secret_goto_detail(secret_name)
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤3: 编辑数据"):
            cce_page.secret_data_edit(SECRET_DATA_NAME, EDIT_CONTENT)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证编辑后内容一致性"):
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤5: 清理密钥"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.secret_delete(secret_name)
            cce_page.assert_deleted(secret_name)
