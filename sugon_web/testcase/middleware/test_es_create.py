import allure
import pytest

from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import load_data, random_data, random_string


@allure.epic('数据库服务')
@allure.feature('云搜索服务 CSS')
class TestESCreate:

    @allure.title("CSS-创建并删除集群-{params[version]}-{params[disk_size]}GiB-安全模式{params[security_mode]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_es", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, es_page, params, ssh_host):
        instance_name = f"css-{random_data()}"

        with allure_step_log(
            f"步骤一：创建集群: {instance_name} "
            f"(版本{params['version']}, 云硬盘{params['disk_size']}GiB, 安全模式={params['security_mode']})"
        ):
            es_page.create_instance(
                name=instance_name,
                version=params["version"],
                disk_size=params["disk_size"],
                security_mode=params["security_mode"],
            )

        with allure_step_log("步骤二：验证创建结果"):
            es_page.assert_popup_success("创建ElasticSearch资源成功")
            es_page.assert_list_contain(instance_name)
            es_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤三：删除集群"):
            es_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            es_page.assert_deleted(instance_name, timeout=1800, refresh=True)
            db_util.assert_backend_deleted(es_page, ssh_host, instance_name)

    @allure.title("CSS-批量删除集群")
    def test_batch_delete_instances(self, es_page, ssh_host):
        """测试批量创建并删除 CSS 集群"""
        instance_names = [f"css-batch-{random_string(5)}", f"css-batch-{random_string(5)}"]

        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建集群: {instance_name}"):
                es_page.create_instance(name=instance_name)
                es_page.assert_popup_success("创建ElasticSearch资源成功")
                es_page.assert_list_contain(instance_name)
                es_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤二：批量删除集群"):
            es_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                es_page.assert_deleted(instance_name, timeout=1800, refresh=True)
                db_util.assert_backend_deleted(es_page, ssh_host, instance_name)
