import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-设置标签")
class TestBmsLabel:

    @allure.title("裸金属BMS-设置标签")
    def test_bms_set_label(self, bms_page):
        """验证裸金属实例设置标签功能正常，测试结束后恢复原始标签状态。

        环境检查：若当前环境无标签功能权限，自动跳过测试。
        """
        instance_name = "bms-0430"
        label_name = random_data()

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：创建标签
        with allure_step_log("步骤2: 创建标签"):
            bms_page.bms_label_create(label_name)

        # 步骤3：为实例设置标签
        with allure_step_log("步骤3: 为实例设置标签"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.bms_instance_bind_label(instance_name, label_name)

        # 步骤4：进入详情页验证标签
        with allure_step_log("步骤4: 进入详情页验证标签"):
            bms_page.bms_instance_detail_assert_label(instance_name, label_name)

        # 步骤5：在标签页验证绑定状态
        with allure_step_log("步骤5: 在标签页验证绑定状态"):
            bms_page.bms_label_assert_bind_status(label_name, bound=True)

        # 步骤6：清理标签（恢复原始状态）
        with allure_step_log("步骤6: 清理标签"):
            # 6.1 解绑实例标签
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.bms_instance_unbind_label(instance_name, label_name)

            # 6.2 删除标签
            bms_page.bms_label_delete(label_name)
            logger.info(f"标签 '{label_name}' 已清理完成")
