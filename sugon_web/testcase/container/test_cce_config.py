import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理')
class TestCCEConfigmap:
    """CCE配置管理-配置项新建与删除测试类"""

    @allure.title("配置管理-新建配置项并删除")
    def test_configmap_create_and_delete(self, cce_page, cce_cluster):
        """测试创建配置项、验证详情、单个删除并验证清理"""
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

    @allure.title("配置管理-批量删除配置项")
    def test_configmap_delete_batch(self, cce_page, cce_cluster):
        """测试批量删除配置项并验证删除后数据一致性"""
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
