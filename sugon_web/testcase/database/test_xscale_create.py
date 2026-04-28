import allure

from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic("数据库服务")
@allure.feature("AnhanDB-XScale")
class TestXScaleCreate:

    @allure.title("XScale-创建和删除实例")
    def test_create_and_delete_instance(self, xscale_page, ssh_host):
        """测试创建并删除XScale实例"""
        instance_name = f"xscale-{random_data()}"

        with allure_step_log(f"步骤一：创建实例 {instance_name}"):
            xscale_page.create_instance(name=instance_name)

        with allure_step_log("步骤二：验证创建结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(instance_name)
            xscale_page.assert_status(instance_name, status="就绪", timeout=2400)

        with allure_step_log("步骤三：删除实例"):
            xscale_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            xscale_page.assert_deleted(instance_name)
            db_util.assert_backend_deleted(xscale_page, ssh_host, instance_name)
