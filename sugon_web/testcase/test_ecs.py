import allure
import pytest
from sugon_web.utils.util import random_data

@allure.epic('计算服务')
@allure.feature('云服务器 ECS')
class TestECS:

    @allure.title("弹性云服务器-创建功能验证")
    def test_ecs_create_basic(self, ecs_page):
        name = random_data()
        ecs_page.ecs_create(name)
        
        # 断言创建成功
        ecs_page.assert_popup_success()
        ecs_page.assert_status(name, status="运行")
