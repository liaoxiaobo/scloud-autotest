import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import load_data, random_data, random_string


@allure.epic('数据库服务')
@allure.feature('监控服务 Prometheus')
class TestPrometheusCreate:

    @allure.title("Prometheus-创建并删除集群-{params[disk_type]}-{params[disk_size]}GiB")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_prometheus", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, prometheus_page, params, ssh_host):
        """测试按云硬盘类型和大小组合创建并删除 Prometheus 集群"""
        instance_name = f"prom-{random_data()}"

        with allure_step_log(
            f"步骤一：创建 Prometheus 集群: {instance_name} "
            f"(云硬盘类型={params['disk_type']}, 云硬盘大小={params['disk_size']}GiB)"
        ):
            prometheus_page.create_instance(
                name=instance_name,
                disk_type=params["disk_type"],
                disk_size=params["disk_size"],
            )

        with allure_step_log("步骤二：验证创建结果"):
            prometheus_page.assert_popup_success("创建prom成功")
            prometheus_page.assert_list_contain(instance_name)
            prometheus_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤三：删除集群"):
            prometheus_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            prometheus_page.assert_deleted(instance_name, timeout=1800, refresh=True)
            ssh_host.wait_vm_deleted(instance_name)
            ssh_host.wait_volume_deleted(instance_name)

    @allure.title("Prometheus-批量删除集群")
    def test_batch_delete_instances(self, prometheus_page, ssh_host):
        """测试批量创建并删除 Prometheus 集群"""
        instance_names = [f"prom-batch-{random_string(5)}", f"prom-batch-{random_string(5)}"]

        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建 Prometheus 集群: {instance_name}"):
                prometheus_page.create_instance(name=instance_name)
                prometheus_page.assert_popup_success("创建prom成功")
                prometheus_page.assert_list_contain(instance_name)
                prometheus_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤二：批量删除集群"):
            prometheus_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                prometheus_page.assert_deleted(instance_name, timeout=1800, refresh=True)
                ssh_host.wait_vm_deleted(instance_name)
                ssh_host.wait_volume_deleted(instance_name)
