import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-移除标签")
class TestBmsRemoveLabel:

    @allure.title("裸金属BMS-移除标签")
    def test_bms_remove_label(self, bms_page, bms_instance_name):
        """验证裸金属实例移除标签功能正常，测试结束后恢复原始标签状态。"""
        instance_name = bms_instance_name
        temp_label = None
        original_label = None
        unbound = False

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：获取实例当前绑定的标签
        with allure_step_log("步骤2: 获取实例当前绑定的标签"):
            bound_labels = bms_page.bms_instance_get_labels(instance_name)
            if bound_labels:
                original_label = bound_labels[0]
                logger.info(f"实例当前绑定标签: '{original_label}'")
            else:
                logger.warning("实例当前未绑定标签，创建临时标签用于测试")
                original_label = None
                temp_label = random_data()
                bms_page.bms_label_create(temp_label)
                bms_page._goto_submenu_safe("裸金属实例")
                bms_page.bms_search(instance_name)
                bms_page.bms_instance_bind_label(instance_name, temp_label)
                original_label = temp_label

        try:
            # 步骤3：移除实例标签
            with allure_step_log("步骤3: 移除实例标签"):
                bms_page._goto_submenu_safe("裸金属实例")
                bms_page.bms_search(instance_name)
                bms_page.bms_instance_unbind_label(instance_name, original_label)
                unbound = True

            # 步骤4：进入详情页验证标签已移除
            with allure_step_log("步骤4: 进入详情页验证标签已移除"):
                bms_page.bms_instance_detail_assert_label_absent(instance_name, original_label)

            # 步骤5：在标签页验证绑定状态为未绑定
            with allure_step_log("步骤5: 在标签页验证绑定状态"):
                bms_page.bms_label_assert_bind_status(original_label, bound=False)
        finally:
            if unbound and original_label:
                with allure_step_log("清理: 恢复原始标签绑定"):
                    try:
                        bms_page._goto_submenu_safe("裸金属实例")
                        bms_page.bms_search(instance_name)
                        bms_page.bms_instance_bind_label(instance_name, original_label)
                        bms_page.bms_instance_detail_assert_label(instance_name, original_label)
                    except Exception as e:
                        logger.warning(f"恢复标签 '{original_label}' 失败: {e}")

            if temp_label:
                with allure_step_log("清理: 删除临时标签"):
                    try:
                        bms_page.bms_instance_unbind_label(instance_name, temp_label)
                    except Exception as e:
                        logger.warning(f"解绑临时标签 '{temp_label}' 失败: {e}")
                    try:
                        bms_page.bms_label_delete(temp_label)
                        logger.info(f"临时标签 '{temp_label}' 已删除")
                    except Exception as e:
                        logger.warning(f"删除临时标签 '{temp_label}' 失败: {e}")
