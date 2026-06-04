import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-修改名称")
class TestBmsRename:

    @allure.title("裸金属BMS-修改名称")
    def test_bms_rename(self, bms_page):
        """验证裸金属实例修改名称和描述功能正常。"""
        instance_name = "bms-0430"
        new_name = "bms-0430-修改"
        description = "名称修改"

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：修改名称和描述
        with allure_step_log("步骤2: 修改实例名称和描述"):
            bms_page.bms_instance_rename(instance_name, new_name, description)

        # 步骤3：验证列表中名称已更新
        with allure_step_log("步骤3: 验证列表中名称已更新"):
            bms_page.search(new_name)
            bms_page.assert_list_contain(new_name, "名称", exact_match=False)
            logger.info(f"列表验证通过: 实例名称已更新为 '{new_name}'")

        # 步骤4：进入详情页验证名称和描述
        with allure_step_log("步骤4: 进入详情页验证名称和描述"):
            bms_page.bms_instance_detail_assert_name(new_name, new_name, description)

        # 步骤5：将名称改回初始名称
        with allure_step_log("步骤5: 将名称恢复为初始名称"):
            bms_page.bms_instance_rename(new_name, instance_name)

        # 步骤6：验证恢复后的名称
        with allure_step_log("步骤6: 验证恢复后的名称"):
            bms_page.search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)
            logger.info(f"名称恢复验证通过: 实例名称已恢复为 '{instance_name}'")
