import pytest
import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data, random_string


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for MongoDB)')
class TestMongoDBCreate:

    @allure.title("MongoDB-创建和删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_mongodb", data_file='test_cdb.yaml'))
    def test_create_and_delete_mongodb(self, mongodb_page, params, ssh_host):
        """测试创建和删除MongoDB实例（单机/副本集/分片集群）"""
        instance_type = params["instance_type"]
        version = params["version"]
        disk_size = params["disk_size"]

        name = f"mongo-{random_data()}"
        password = "Admin1234#sugon"

        # 分片集群创建时间较长，设置更长的超时时间
        create_timeout = 2400 if instance_type == "分片集群" else 1800

        with allure_step_log(f"步骤一：创建实例: {name} ({instance_type})"):
            mongodb_page.create_instance(
                name=name,
                instance_type=instance_type,
                version=version,
                password=password,
                disk_size=disk_size
            )

        with allure_step_log("步骤二：验证创建结果"):
            mongodb_page.assert_popup_success("创建实例")
            mongodb_page.assert_list_contain(name)
            mongodb_page.assert_status(name, status="运行中", timeout=create_timeout, refresh=True)
            ssh_host.assert_resource_created(name)

        with allure_step_log("步骤三：删除实例"):
            mongodb_page.delete_instance(name)

        with allure_step_log("步骤四：验证删除结果"):
            mongodb_page.assert_deleted(name, timeout=1200, refresh=True)
            ssh_host.wait_vm_deleted(name)
            ssh_host.wait_volume_deleted(name)

    @allure.title("MongoDB-批量删除实例")
    def test_batch_delete_mongodb(self, mongodb_page, ssh_host):
        """测试批量删除MongoDB实例"""
        instance_names = [f"mongo-batch-{random_data()}", f"mongo-batch-{random_data()}"]
        password = "Admin1234#sugon"
        for name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {name}"):
                mongodb_page.create_instance(name=name, instance_type="单机", password=password)

            with allure_step_log("步骤二：验证创建结果"):
                mongodb_page.assert_popup_success("创建实例")
                mongodb_page.assert_list_contain(name)
                mongodb_page.assert_status(name, status="运行中", timeout=1800, refresh=True)
                ssh_host.assert_resource_created(name)

        with allure_step_log("步骤三：批量删除实例"):
            mongodb_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤四：验证批量删除结果"):
            for name in instance_names:
                mongodb_page.assert_deleted(name, timeout=1200, refresh=True)
                ssh_host.wait_vm_deleted(name)
                ssh_host.wait_volume_deleted(name)
