import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import load_data, random_data, random_string


@allure.epic('数据库服务')
@allure.feature('分布式消息服务 Kafka')
class TestKafkaCreate:

    @allure.title("Kafka-创建并删除实例-{params[version]}-安全模式{params[security_mode]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_kafka", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, kafka_page, params, ssh_host):
        """测试创建并删除Kafka实例（版本+安全模式参数化）"""
        instance_name = f"kafka-{random_data()}"

        with allure_step_log(f"步骤一：创建实例: {instance_name} (版本{params['version']}, 安全模式={params['security_mode']})"):
            kafka_page.create_instance(
                name=instance_name,
                version=params['version'],
                security_mode=params['security_mode']
            )

        with allure_step_log("步骤二：验证创建结果"):
            kafka_page.assert_popup_success("Kafka实例创建成功")
            kafka_page.assert_list_contain(instance_name)
            kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：删除实例"):
            kafka_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            kafka_page.assert_deleted(instance_name, timeout=1200, refresh=True)
            ssh_host.wait_vm_deleted(instance_name)
            ssh_host.wait_volume_deleted(instance_name)

    @allure.title("Kafka-批量删除实例")
    def test_batch_delete_instances(self, kafka_page, ssh_host):
        """测试批量删除Kafka实例"""
        instance_names = [f"kafka-batch-{random_data()}", f"kafka-batch-{random_data()}"]

        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {instance_name}"):
                kafka_page.create_instance(name=instance_name)
                kafka_page.assert_popup_success("Kafka实例创建成功")
                kafka_page.assert_list_contain(instance_name)
                kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤二：批量删除实例"):
            kafka_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                kafka_page.assert_deleted(instance_name, timeout=1200, refresh=True)
                ssh_host.wait_vm_deleted(instance_name)
                ssh_host.wait_volume_deleted(instance_name)
