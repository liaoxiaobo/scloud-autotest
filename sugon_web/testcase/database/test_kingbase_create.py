import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import load_data, random_data, random_string


@allure.epic("数据库服务")
@allure.feature("人大金仓 KingbaseES")
class TestKingbaseCreate:

    @allure.title("KingbaseES-创建并删除实例-{params[instance_type]}-{params[db_mode]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_kingbase", data_file="test_cdb.yaml"))
    def test_create_and_delete_instance(self, kingbase_page, params, ssh_host):
        """测试创建并删除KingbaseES实例（单机/集群）。"""
        instance_name = f"kingbase-{random_data()}"

        with allure_step_log(
            f"步骤一：创建实例 {instance_name} ({params['instance_type']}, 兼容模式: {params['db_mode']})"
        ):
            kingbase_page.create_instance(
                name=instance_name,
                instance_type=params["instance_type"],
                db_mode=params["db_mode"],
                disk_size=params["disk_size"],
            )

        with allure_step_log("步骤二：验证实例创建成功"):
            kingbase_page.assert_popup_success("创建实例")
            kingbase_page.assert_list_contain(instance_name)
            kingbase_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：删除实例"):
            kingbase_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证实例删除成功"):
            kingbase_page.assert_deleted(instance_name, timeout=1800, refresh=True)
            ssh_host.wait_vm_deleted(instance_name, timeout=1800)
            ssh_host.wait_volume_deleted(instance_name, timeout=1800)
