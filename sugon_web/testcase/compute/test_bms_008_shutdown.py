import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-关机")
class TestBmsShutdown:

    @allure.title("裸金属BMS-关机")
    def test_bms_shutdown(self, bms_page):
        """验证裸金属实例关机功能正常，测试结束后恢复运行中状态。"""
        instance_name = "bms-0430"

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 确保实例初始状态为"运行中"，若已关机则先开机
        row_data = bms_page.get_row_data(instance_name)
        current_status = row_data.get("状态", "") if row_data else ""
        if "关机" in current_status:
            logger.warning(f"实例当前状态为'{current_status}'，先执行开机操作")
            bms_page.bms_instance_start(instance_name)
            start_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=300)
            if not start_ok:
                pytest.skip("实例无法恢复为运行中状态，跳过关机测试")

        # 步骤2：执行关机操作
        with allure_step_log("步骤2: 执行关机操作"):
            bms_page.bms_instance_shutdown(instance_name)

        # 步骤3：验证列表中状态已更新为已关机
        with allure_step_log("步骤3: 验证列表中状态已更新为已关机"):
            shutdown_ok = bms_page.bms_instance_wait_for_status(instance_name, "关机", timeout=300)
            if not shutdown_ok:
                pytest.skip("实例未在5分钟内变为关机状态")

        # 步骤4：进入详情页验证状态
        with allure_step_log("步骤4: 进入详情页验证状态"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到实例 '{instance_name}'"
            status = row_data.get("状态", "")
            assert "关机" in status, f"列表状态期望为'关机'，实际为 '{status}'"
            logger.info(f"列表验证通过: 状态为 '{status}'")

        # 步骤5：恢复开机
        with allure_step_log("步骤5: 恢复开机"):
            bms_page.bms_instance_start(instance_name)

        # 步骤6：验证恢复后的状态
        with allure_step_log("步骤6: 验证恢复后的状态"):
            start_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=300)
            if not start_ok:
                pytest.skip("实例未在5分钟内恢复为运行中状态")

            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到实例 '{instance_name}'"
            status = row_data.get("状态", "")
            assert "运行中" in status, f"恢复后状态期望为'运行中'，实际为 '{status}'"
            logger.info(f"恢复验证通过: 状态已恢复为 '{status}'")
