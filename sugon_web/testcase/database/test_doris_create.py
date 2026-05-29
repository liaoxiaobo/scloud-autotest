import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data, random_string



@allure.epic('数据库服务')
@allure.feature('数据仓库 Doris')
class TestDorisCreate:

    @allure.title("Doris-创建并删除实例-{params[ha_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_doris", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, doris_page, params, ssh_host):
        """测试创建并删除Doris实例（参数化）"""
        instance_name = f"doris-{random_data()}"

        with allure_step_log(f"步骤一：创建实例: {instance_name} ({params['ha_type']})"):
            doris_page.create_instance(
                name=instance_name,
                ha_type=params['ha_type'],
                fe_disk_size=params['fe_disk_size'],
                be_disk_size=params['be_disk_size'],
                case_sensitivity=params['case_sensitivity']
            )

        with allure_step_log("步骤二：验证创建结果"):
            doris_page.assert_popup_success("Doris创建任务提交成功")
            doris_page.assert_list_contain(instance_name)
            doris_page.assert_status(instance_name, status="就绪", timeout=1800, refresh=True)

        with allure_step_log("步骤三：删除实例"):
            doris_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            doris_page.assert_deleted(instance_name, timeout=1200)
            ssh_host.wait_vm_deleted(instance_name)
            ssh_host.wait_volume_deleted(instance_name)

    @allure.title("Doris-批量删除实例")
    def test_batch_delete_instances(self, doris_page, ssh_host):
        """测试批量删除Doris实例"""
        instance_names = [f"doris-batch-{random_data()}", f"doris-batch-{random_data()}"]

        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {instance_name}"):
                doris_page.create_instance(name=instance_name)
                doris_page.assert_popup_success("Doris创建任务提交成功")
                doris_page.assert_list_contain(instance_name)
                doris_page.assert_status(instance_name, status="就绪", timeout=1800, refresh=True)

        with allure_step_log("步骤二：批量删除实例"):
            doris_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                doris_page.assert_deleted(instance_name, timeout=1200)
                ssh_host.wait_vm_deleted(instance_name)
                ssh_host.wait_volume_deleted(instance_name)
