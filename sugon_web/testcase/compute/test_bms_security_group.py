import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-设置安全组")
class TestBmsSecurityGroup:

    @allure.title("裸金属BMS-设置安全组")
    def test_bms_set_security_group(self, bms_page, sg):
        """验证裸金属实例设置安全组功能正常，测试结束后恢复原始安全组。"""
        instance_name = "bms-0430"
        new_sg = sg if isinstance(sg, str) else sg[0]

        # 步骤0：获取实例当前安全组（用于测试结束后恢复）
        with allure_step_log("步骤0: 获取实例当前安全组"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.page.wait_for_timeout(2000)
            original_sg = bms_page.bms_instance_get_security_group(instance_name)
            logger.info(f"实例当前安全组: '{original_sg}'")

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：设置安全组为前置条件创建的安全组
        with allure_step_log("步骤2: 设置安全组"):
            bms_page.bms_instance_set_security_group(instance_name, new_sg)

        # 步骤3：验证列表中安全组已更新（列表若无安全组列则跳过，依赖详情页验证）
        with allure_step_log("步骤3: 验证列表中安全组已更新"):
            bms_page.page.wait_for_timeout(3000)
            bms_page.close_dialog_if_exists()
            bms_page.page.keyboard.press("Escape")
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.page.wait_for_timeout(4000)
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            sg_field = row_data.get("安全组", "")
            if sg_field:
                assert new_sg in sg_field, f"列表安全组字段期望包含 '{new_sg}'，实际为 '{sg_field}'"
                logger.info(f"列表验证通过: 安全组已更新为 '{new_sg}'")
            else:
                logger.warning("列表中无安全组字段，跳过列表验证，依赖详情页验证")

        # 步骤4：进入详情页验证安全组
        with allure_step_log("步骤4: 进入详情页验证安全组"):
            bms_page.bms_instance_detail_assert_security_group(instance_name, new_sg)

        # 步骤5：恢复原始安全组
        with allure_step_log("步骤5: 恢复原始安全组"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.bms_instance_set_security_group(instance_name, original_sg)

        # 步骤6：验证恢复后的安全组（列表若无安全组列则跳过，依赖详情页验证）
        with allure_step_log("步骤6: 验证恢复后的安全组"):
            bms_page.page.wait_for_timeout(3000)
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            sg_field = row_data.get("安全组", "")
            if sg_field:
                assert original_sg in sg_field, f"列表安全组字段期望包含 '{original_sg}'，实际为 '{sg_field}'"
                logger.info(f"列表验证通过: 已恢复为 '{original_sg}'")
            else:
                logger.warning("列表中无安全组字段，跳过列表验证，依赖详情页验证")

        # 步骤7：进入详情页验证已恢复为原始安全组
        with allure_step_log("步骤7: 进入详情页验证已恢复为原始安全组"):
            bms_page.bms_instance_detail_assert_security_group(instance_name, original_sg)
