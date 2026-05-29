import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('计算服务')
@allure.feature('亲和组')
@allure.story('亲和组功能验证')
class TestEcsAffinityGroup:
    @allure.title("验证创建亲和组功能")
    def test_ecs_create_affinity_group(self, ecs_page):
        policy = "亲和"
        name = f"{random_data(length=3)}-{policy}"
        ecs_page.goto_service('弹性云服务器')

        with allure_step_log(f"步骤1: 创建亲和组: {name}"):
            ecs_page.ecs_create_affinity_group(name, policy)

        with allure_step_log("步骤2: 验证创建结果"):
            ecs_page.assert_popup_success("执行成功")
            assert ecs_page.get_row_data(name).get("策略") == policy, \
                f"创建亲和组失败，期望策略:{policy},实际策略:{ecs_page.get_row_data(name).get('策略')}"

        with allure_step_log(f"步骤3: 删除亲和组: {name}"):
            ecs_page.ecs_delete_affinity_group(name)
            ecs_page.assert_deleted(name, refresh=True)


    @allure.title("验证绑定/解绑亲和组功能")
    @pytest.mark.parametrize("vm", [{"inject_dependencies": False}], indirect=True)
    def test_ecs_bind_unbind_group(self, ecs_page, vm):
        """测试绑定/解绑亲和组功能"""

        policy = "亲和"
        group_name = f"{random_data(length=3)}-{policy}"
        vm_name = vm.get("name")

        with allure_step_log(f"步骤1: 创建{policy}组: {group_name}"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_create_affinity_group(group_name, policy)

        with allure_step_log(f"步骤2: 验证{policy}组创建结果"):
            ecs_page.assert_popup_success("执行成功")
            assert ecs_page.get_row_data(group_name).get("策略") == policy, \
                f"创建亲和组失败，期望策略:{policy},实际策略:{ecs_page.get_row_data(group_name).get('策略')}"

        with allure_step_log(f"步骤3: 云服务器{vm_name}绑定{policy}组并验证绑定结果"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_bind_unbind_group(vm_name, "绑定亲和组", group_name)
            ecs_page.assert_ecs_details_info(vm_name, info_items={"亲和组": group_name})

        with allure_step_log(f"步骤4: 云服务器{vm_name}解绑{policy}组并验证解绑结果"):
            ecs_page.ecs_bind_unbind_group(vm_name, "解绑亲和组", group_name)
            ecs_page.assert_ecs_details_info(vm_name, info_items={"亲和组": "--"})

        with allure_step_log(f"步骤5: 删除{policy}组: {group_name}"):
            ecs_page.ecs_delete_affinity_group(group_name)
            ecs_page.assert_deleted(group_name, refresh= True)
