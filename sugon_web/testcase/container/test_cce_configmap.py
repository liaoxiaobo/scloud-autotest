import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


# CSV 定义的测试数据
CONFIGMAP_DATA_NAME = "ccetest123.2312-2.3-2w"
CONFIGMAP_DATA_CONTENT = "cce_test123.2312-2.-w" * 40
EDIT_CONTENT = "cce_test-CCE123!@##"


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-配置项')
class TestCCEConfigmapList:
    """CCE 配置项列表页测试类。"""

    @allure.title("配置项-创建和删除")
    def test_configmap_create_and_delete(self, cce_page, cce_cluster):
        """测试创建配置项、验证详情、单个删除并验证清理。"""
        config_name = f"cfg-{random_data(length=4)}"
        labels = {"test": "1024"}
        datas = {"cce-test2": "cce_test-122333322"}

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(
                name=config_name,
                labels=labels,
                datas=datas
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表页包含新创建的配置项"):
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤3: 进入详情页验证数据一致性"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(
                name=config_name,
                labels=labels,
                datas=datas
            )

        with allure_step_log("步骤4: 单个删除配置项"):
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

        with allure_step_log("步骤5: 验证列表页不存在被删除的配置项"):
            cce_page.assert_list_not_contain(config_name, column_name="名称")

    @allure.title("配置项-批量删除")
    def test_configmap_delete_batch(self, cce_page, cce_cluster):
        """测试批量删除配置项并验证删除后数据一致性。"""
        config_name_1 = f"cfg-del-{random_data(length=4)}"
        config_name_2 = f"cfg-del-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建多个配置项"):
            for name in [config_name_1, config_name_2]:
                cce_page.configmap_create(name=name, datas={"key": "value"})
                cce_page.assert_popup_success()
                cce_page.assert_list_contain(name, column_name="名称")

        with allure_step_log("步骤2: 批量删除配置项"):
            cce_page.configmap_batch_delete([config_name_1, config_name_2])
            cce_page.assert_deleted(config_name_1)
            cce_page.assert_deleted(config_name_2)

        with allure_step_log("步骤3: 验证列表页不存在被删除的配置项"):
            cce_page.assert_list_not_contain(config_name_1, column_name="名称")
            cce_page.assert_list_not_contain(config_name_2, column_name="名称")


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-配置项-详情')
class TestCCEConfigmapDetail:
    """CCE 配置项详情页测试类。"""

    @allure.title("配置项-详情添加和删除数据")
    def test_configmap_data_add_and_delete(self, cce_page, cce_cluster):
        """测试配置项详情页添加数据后删除，并验证列表一致性。"""
        config_name = f"cfg-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(name=config_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(name=config_name)

        with allure_step_log("步骤3: 添加数据"):
            cce_page.configmap_data_add(CONFIGMAP_DATA_NAME, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_assert_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤4: 删除数据"):
            cce_page.configmap_data_delete(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.configmap_data_assert_not_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤6: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

    @allure.title("配置项-详情编辑数据")
    def test_configmap_data_edit(self, cce_page, cce_cluster):
        """测试配置项详情页编辑数据，并验证内容一致性。"""
        config_name = f"cfg-edit-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建带数据的配置项"):
            cce_page.configmap_create(
                name=config_name,
                datas={CONFIGMAP_DATA_NAME: CONFIGMAP_DATA_CONTENT}
            )
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(name=config_name, datas={CONFIGMAP_DATA_NAME: CONFIGMAP_DATA_CONTENT})

        with allure_step_log("步骤3: 编辑数据"):
            cce_page.configmap_data_edit(CONFIGMAP_DATA_NAME, EDIT_CONTENT)

        with allure_step_log("步骤4: 验证编辑后内容一致性"):
            cce_page.configmap_data_assert_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤5: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

    @allure.title("配置项-详情批量删除数据")
    def test_configmap_data_batch_delete(self, cce_page, cce_cluster):
        """测试配置项详情页批量删除数据，并验证列表一致性。"""
        config_name = f"cfg-batch-{random_data(length=4)}"
        data_name_1 = f"{CONFIGMAP_DATA_NAME}-1"
        data_name_2 = f"{CONFIGMAP_DATA_NAME}-2"

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(name=config_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)

        with allure_step_log("步骤3: 添加多条数据"):
            cce_page.configmap_data_add(data_name_1, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_add(data_name_2, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_assert_list([data_name_1, data_name_2])

        with allure_step_log("步骤4: 批量删除数据"):
            cce_page.configmap_data_batch_delete([data_name_1, data_name_2])

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.configmap_data_assert_not_list([data_name_1, data_name_2])

        with allure_step_log("步骤6: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)
