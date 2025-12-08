import allure
from sugon_web.testcase.conftest import ecs_page
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('创建功能验证')
class TestECSCreate:

    @allure.title("弹性云服务器-创建功能验证")
    def test_ecs_create(self, ecs_page):
        name = random_data()

        with allure_step_log("步骤1: 创建云服务器"):
            ecs_page.ecs_create(name=name)

        with allure_step_log("步骤2: 验证创建结果"):
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title("弹性云服务器-快照方式创建功能验证")
    def test_ecs_create_with_snapshot(self, ecss, ecs_page, ssh_vm):
        name = random_data()
        snapshot_name = ecss.get("name")
        with allure_step_log("步骤1: 创建启动方式为 快照 的云服务器"):
            ecs_page.ecs_create(name=name, image_source="快照", image_name=snapshot_name)

        with allure_step_log("步骤2: 验证创建结果"):
            # 页面验证
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)
            assert ecs_page.get_row_data(name).get("镜像名称") == snapshot_name, "镜像名称快照不一致"

            # 登录虚机验证
            ip = ecs_page.get_row_data(name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(ip.strip())
            ssh_vm.connect(mfip)
            ecs_page.assert_ecs_enable(name, ssh_vm)

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)
