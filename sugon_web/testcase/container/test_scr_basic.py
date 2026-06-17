import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('容器服务')
@allure.feature('容器镜像服务SCR')
@allure.story('实例管理功能验证')
class TestSCRInstanceManagement:
    """SCR 实例管理测试类：搜索、修改名称、删除、批量删除。"""

    @allure.title("实例管理-列表页搜索和重置")
    def test_scr_search_reset(self, scr_page, scr_instance):
        """验证实例列表页搜索和重置功能。"""
        instance_name = scr_instance["name"]

        with allure_step_log("步骤1: 按实例名称搜索"):
            scr_page.goto_service(scr_page.service_name)
            scr_page.goto_submenu("实例管理")
            scr_page.search(instance_name)
            scr_page.assert_list_contain(instance_name, column_name="名称")

        with allure_step_log("步骤2: 重置搜索条件"):
            scr_page.btn_reset.click()
            assert scr_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("实例管理-修改实例名称")
    def test_scr_edit_name(self, scr_page, scr_instance):
        """修改 SCR 实例名称并验证列表更新。"""
        instance_name = scr_instance["name"]
        new_name = f"{instance_name}-edited"

        with allure_step_log("步骤1: 修改实例名称"):
            scr_page.scr_edit_name(instance_name, new_name)
            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表显示新名称"):
            scr_page.assert_list_contain(new_name, column_name="名称")

        with allure_step_log("步骤3: 恢复原始名称"):
            scr_page.scr_edit_name(new_name, instance_name)
            scr_page.assert_popup_success()
            scr_page.assert_list_contain(instance_name, column_name="名称")

    @allure.title("实例管理-删除 SCR 实例")
    def test_scr_delete(self, scr_page, ssh_host):
        """创建临时 SCR 实例后删除，验证 UI 列表和后台虚机均清理。"""
        instance_name = f"scr-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建临时 SCR 实例"):
            scr_page.scr_create(name=instance_name, instance_type="ALONE", flavor="4C8G")
            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 等待实例状态收敛到运行中"):
            scr_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤3: 删除实例"):
            scr_page.scr_delete(instance_name)
            scr_page.assert_deleted(instance_name, timeout=600)

        with allure_step_log("步骤4: 后台验证虚机已删除"):
            ssh_host.wait_vm_deleted(instance_name, timeout=600)

