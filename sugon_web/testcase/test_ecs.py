import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
class TestECS:

    @allure.title("云服务器-创建功能验证")
    def test_ecs_create(self, ecs_page):
        name = random_data()

        with allure.step("创建云服务器"):
            ecs_page.ecs_create(name=name)

        with allure.step("验证创建结果"):
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name, status="当前无任务", timeout=300)

        with allure.step("清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title("云服务器-编辑功能验证")
    @pytest.mark.parametrize("name", load_data('test_ecs_edit',"ecs_operation_data.yaml"))
    def test_ecs_edit(self, ecs_page, name):
        newname = random_data('string', 5)
        with allure.step("编辑云服务器"):
            ecs_page.ecs_edit(name, newname)

        with allure.step("验证创建结果"):
            ecs_page.assert_popup_success("更新实例成功")

        with allure.step("清理测试数据"):
            ecs_page.ecs_edit(newname, name)

    @allure.title("弹性云服务器-登录VNC功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_expand'))
    def test_ecs_vnc(self, ecs_page, name, vncpws):
        with allure.step("登录VNC"):
            ecs_page.ecs_vnc(name, vncpws)

    @allure.title("弹性云服务器-克隆功能验证")
    @pytest.mark.parametrize("name", load_data('test_ecs_clone',"ecs_operation_data.yaml"))
    def test_ecs_clone(self, ecs_page, name):
        with allure.step(f"克隆云服务器{name}"):
            clone_name = random_data('string', 5)
            ecs_page.ecs_clone(name, clone_name, 'Autotest', 'Autotest', {})

        with allure.step(f"验证克隆结果{clone_name}"):
            ecs_page.assert_popup_success(f"{name}实例克隆成功")
            image_name = ecs_page.get_row_data(name).get("镜像名称")
            ecs_page.assert_image_name(clone_name, image_name)
            ecs_page.assert_status(name, status="当前无任务", timeout=300)

        with allure.step(f"清理测试数据{clone_name}"):
            ecs_page.ecs_remove(clone_name)
            ecs_page.ecs_delete(clone_name)
            ecs_page.assert_deleted(clone_name)

    @allure.title("弹性云服务器-重建云服务器功能验证")
    @pytest.mark.parametrize("name", load_data('test_ecs_rebuild', "ecs_operation_data.yaml"))
    def test_ecs_rebuild(self, ecs_page, name):
        with allure.step("重建云服务器"):
            ecs_page.ecs_rebuild(name, 'CentOS 7.9', '64位', 'lxr-xstor')

        with allure.step("验证重建结果"):
            ecs_page.assert_popup_success("重建实例成功")
            ecs_page.assert_status(name, status="当前无任务", timeout=300)
