import pytest
import allure
from sugon_web.utils.util import random_data


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