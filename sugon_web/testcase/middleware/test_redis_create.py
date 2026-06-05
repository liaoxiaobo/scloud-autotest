import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data, random_string


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for Redis)')
class TestRedisCreate:

    @allure.title("Redis-创建并删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_redis", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, redis_page, params, ssh_host):
        """测试创建并删除Redis实例（参数化）"""
        instance_name = f"redis-{random_data()}"

        with allure_step_log(f"步骤一：创建实例: {instance_name} ({params['instance_type']})"):
            redis_page.create_instance(
                name=instance_name,
                instance_type=params['instance_type'],
                version=params['version'],
                disk_size=params['disk_size']
            )

        with allure_step_log("步骤二：验证创建结果"):
            redis_page.assert_popup_success("创建redis资源成功")
            redis_page.assert_list_contain(instance_name)
            redis_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤三：删除实例"):
            redis_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            redis_page.assert_deleted(instance_name, timeout=1200)
            ssh_host.wait_vm_deleted(instance_name)
            ssh_host.wait_volume_deleted(instance_name)

    @allure.title("Redis-批量删除实例")
    def test_batch_delete_instances(self, redis_page, ssh_host):
        """测试批量删除Redis实例"""
        instance_names = [f"redis-batch-delete-{random_data()}", f"redis-batch-delete-{random_data()}"]
        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {instance_name}"):
                redis_page.create_instance(name=instance_name)
                redis_page.assert_popup_success("创建redis资源成功")
                redis_page.assert_list_contain(instance_name)
                redis_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤二：批量删除实例"):
            redis_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                redis_page.assert_deleted(instance_name, timeout=1200)
                ssh_host.wait_vm_deleted(instance_name)
                ssh_host.wait_volume_deleted(instance_name)
