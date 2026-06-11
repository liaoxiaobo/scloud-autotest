import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import load_data, random_data, random_string


@allure.epic('数据库服务')
@allure.feature('分布式消息服务 RabbitMQ')
class TestRabbitMQCreate:

    @allure.title("RabbitMQ-创建并删除集群-{params[disk_type]}-{params[disk_size]}GiB")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_rabbitmq", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, rabbitmq_page, params, ssh_host):
        """测试按云硬盘类型和大小组合创建并删除 RabbitMQ 集群实例"""
        instance_name = f"rabbitmq-{random_data()}"

        with allure_step_log(
            f"步骤一：创建 RabbitMQ 集群: {instance_name} "
            f"(云硬盘类型={params['disk_type']}, 云硬盘大小={params['disk_size']}GiB)"
        ):
            rabbitmq_page.create_instance(
                name=instance_name,
                instance_type="集群",
                disk_type=params["disk_type"],
                disk_size=params["disk_size"],
            )

        with allure_step_log("步骤二：验证创建结果"):
            rabbitmq_page.assert_popup_success("创建Rabbitmq资源成功")
            rabbitmq_page.assert_list_contain(instance_name)
            rabbitmq_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤三：删除实例"):
            rabbitmq_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            rabbitmq_page.assert_deleted(instance_name, timeout=1800, refresh=True)
            ssh_host.wait_vm_deleted(instance_name)
            ssh_host.wait_volume_deleted(instance_name)

    @allure.title("RabbitMQ-批量删除实例")
    def test_batch_delete_instances(self, rabbitmq_page):
        """测试批量创建并删除 RabbitMQ 实例"""
        instance_names = [f"rabbitmq-batch-{random_string(5)}", f"rabbitmq-batch-{random_string(5)}"]

        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建 RabbitMQ 集群: {instance_name}"):
                rabbitmq_page.create_instance(name=instance_name)
                rabbitmq_page.assert_popup_success("创建Rabbitmq资源成功")
                rabbitmq_page.assert_list_contain(instance_name)
                rabbitmq_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤二：批量删除实例"):
            rabbitmq_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                rabbitmq_page.assert_deleted(instance_name, timeout=1800, refresh=True)
