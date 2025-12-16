import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('计算服务')
@allure.feature('标签')
@allure.story('标签功能验证')
class TestECSLbaels:
    @allure.title("验证创建 & 搜索 & 删除标签功能")
    def test_ecs_create_label(self, ecs_page):
        """测试创建标签功能"""
        label_name = f"label-{random_data()}"
        with allure_step_log(f"步骤1: 创建新标签{label_name}"):
            label_name = ecs_page.create_label(label_name)
            ecs_page.assert_popup_success("新建标签成功")

        with allure_step_log(f"步骤2: 搜索标签{label_name}"):
            ecs_page.search(label_name)
            assert ecs_page.get_row_data(label_name).get("名称") == label_name

        with allure_step_log(f"步骤3: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
            assert len(ecs_page.table_rows) > 0, "重置后列表数据为空"

        with allure_step_log(f"步骤4: 删除标签{label_name}"):
            ecs_page.delete_label(label_name)
            ecs_page.assert_deleted(label_name)

    @allure.title("验证编辑标签功能")
    def test_ecs_edit_label(self, ecs_page, labels, vm):
        """测试编辑标签功能"""
        vm_name = vm.get("name")
        with allure_step_log(f"步骤1: {vm_name}绑定标签{labels}"):
            ecs_page.bind_labels(vm_name, labels, bind=True)

        with allure_step_log(f"步骤2: 验证标签绑定结果"):
            ecs_page.assert_ecs_details_info([vm_name], info_items={"标签": labels[0]})

        with allure_step_log(f"步骤3: 编辑标签{labels}"):
            new_names = []
            for label in labels:
                new_name = f"{label}-new"
                ecs_page.edit_label(label, new_name)
                assert ecs_page.get_row_data(new_name).get("名称") == new_name
                new_names.append(new_name)

        with allure_step_log(f"步骤4: 验证标签修改结果"):
            ecs_page.assert_ecs_details_info([vm_name], info_items={"标签": new_names[0]})

        with allure_step_log(f"步骤5: 解绑标签{new_names}"):
            ecs_page.bind_labels(vm_name, new_names, bind=False)
            ecs_page.assert_ecs_details_info([vm_name], info_items={"标签": "--"})

        with allure_step_log(f"步骤6: 编辑标签{labels}"):
            for new_name,label in zip(new_names, labels):
                ecs_page.edit_label(new_name, label)
                assert ecs_page.get_row_data(label).get("名称") == label

    @allure.title("验证标签设置功能")
    @pytest.mark.parametrize("label_name", [
        [f"label-{random_data()}"],
        [f"label-{random_data()}", f"label-{random_data()}-1"]
    ])
    def test_ecs_bind_labels(self, ecs_page, vm, label_name):
        """测试标签管理功能：创建标签、绑定标签、解绑标签"""
        label_names = []
        vm_name = vm.get("name")

        with allure_step_log("步骤1: 创建新标签"):
            for name in label_name:
                label_name = ecs_page.create_label(name)
                label_names.append(label_name)

        with allure_step_log("步骤2: 获取云服务器信息"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.bind_labels(vm_name, label_names, bind=True)

        with allure_step_log("步骤3: 验证标签绑定结果"):
            ecs_page.assert_ecs_details_info(vm_name, info_items={"标签": label_names[-1]})

        with allure_step_log("步骤4: 解绑标签"):
            ecs_page.bind_labels(vm_name, label_names, bind=False)

        with allure_step_log("步骤5: 验证标签解绑结果"):
            ecs_page.assert_ecs_details_info(vm_name, info_items={"标签": "--"})

        with allure_step_log("步骤6: 删除标签"):
            for label_name in label_names:
                ecs_page.delete_label(label_name)

    @allure.title("验证标签解绑实例功能")
    def test_ecs_unbind_vm_from_label(self, ecs_page, vm, labels):
        """标签解绑实例"""
        vm_name = vm.get("name")
        with allure_step_log(f"步骤1: {vm_name}绑定标签{labels}"):
            ecs_page.bind_labels(vm_name, labels, bind=True)

        with allure_step_log(f"步骤2: 验证标签绑定结果"):
            ecs_page.assert_ecs_details_info([vm_name], info_items={"标签": labels[0]})

        with allure_step_log(f"步骤3: 解绑标签{labels}"):
            ecs_page.unbind_vm_from_label(vm_name, labels[0])

        with allure_step_log(f"步骤4: 验证标签解绑结果"):
            assert ecs_page.get_row_data(labels[0]).get("绑定资源数量") == "0"
            ecs_page.assert_ecs_details_info([vm_name], info_items={"标签": "--"})

    @allure.title("验证批量标签设置功能")
    @pytest.mark.parametrize("vm", [{"count": 2, "bind_mfip": False}], indirect=True)
    @pytest.mark.parametrize("labels", [{"count": 3}], indirect=True)
    def test_ecs_batch_bind_labels(self, ecs_page, vm, labels):
        """批量标签设置"""

        vm_names = [vm[i].get("name") for i in range(len(vm))]

        with allure_step_log("步骤1: 批量绑定标签"):
            ecs_page.ecs_batch_bind_labels(vm_names, labels)

        with allure_step_log("步骤2: 验证标签绑定结果"):
            ecs_page.assert_ecs_details_info(vm_names, info_items={"标签": labels[-1]})

        with allure_step_log("步骤3: 批量解绑标签"):
            ecs_page.delete_batch_unbind_label(vm_names, labels)
