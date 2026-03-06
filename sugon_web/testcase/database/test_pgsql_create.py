import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for PostgreSQL)')
class TestPgSQLCreate:

    @allure.title("PostgreSQL-创建并删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_pgsql", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, pgsql_page, params, ssh_host):
        """测试创建并删除PostgreSQL实例（参数化）"""
        instance_name = f"pgsql-{random_data()}"

        with allure_step_log(f"步骤一：创建实例: {instance_name} ({params['instance_type']})"):
            pgsql_page.create_instance(
                name=instance_name,
                instance_type=params['instance_type'],
                version=params['version'],
                disk_size=params['disk_size']
            )

        with allure_step_log("步骤二：验证创建结果"):
            pgsql_page.assert_popup_success("创建PostgreSQL资源成功")
            pgsql_page.assert_list_contain(instance_name)
            pgsql_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤三：删除实例"):
            pgsql_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            pgsql_page.assert_deleted(instance_name, timeout=1200)
            db_util.assert_backend_deleted(pgsql_page, ssh_host, instance_name)

    @allure.title("PostgreSQL-批量删除实例")
    def test_batch_delete_instances(self, pgsql_page, ssh_host):
        """测试批量删除PostgreSQL实例"""
        instance_names = [f"pgsql-batch-delete-{random_string(5)}", f"pgsql-batch-delete-{random_string(5)}"]
        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {instance_name}"):
                pgsql_page.create_instance(name=instance_name)
                pgsql_page.assert_popup_success("创建实例")
                pgsql_page.assert_list_contain(instance_name)
                pgsql_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤二：批量删除实例"):
            pgsql_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                pgsql_page.assert_deleted(instance_name, timeout=1200)
                db_util.assert_backend_deleted(pgsql_page, ssh_host, instance_name)
