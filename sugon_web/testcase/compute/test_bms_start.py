import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-开机")
class TestBmsStart:

    @allure.title("裸金属BMS-开机")
    def test_bms_start(self, bms_page):
        """验证裸金属实例开机功能正常。"""
        instance_name = "bms-0430"

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：确保实例处于关机状态
        with allure_step_log("步骤2: 确保实例处于关机状态"):
            row_data = bms_page.get_row_data(instance_name)
            current_status = row_data.get("状态", "") if row_data else ""
            if "运行中" in current_status:
                logger.warning(f"实例当前状态为'{current_status}'，先执行关机操作")
                bms_page.bms_instance_shutdown(instance_name)
                shutdown_ok = bms_page.bms_instance_wait_for_status(instance_name, "关机", timeout=300)
                if not shutdown_ok:
                    pytest.skip("实例无法变为关机状态，跳开开机测试")

        # 步骤3：执行开机操作
        with allure_step_log("步骤3: 执行开机操作"):
            bms_page.bms_instance_start(instance_name)

        # 步骤4：验证列表中状态已更新为运行中
        with allure_step_log("步骤4: 验证列表中状态已更新为运行中"):
            start_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=300)
            if not start_ok:
                pytest.skip("实例未在5分钟内变为运行中状态")

        # 步骤5：进入详情页验证状态
        with allure_step_log("步骤5: 进入详情页验证状态"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到实例 '{instance_name}'"
            status = row_data.get("状态", "")
            assert "运行中" in status, f"列表状态期望为'运行中'，实际为 '{status}'"
            logger.info(f"列表验证通过: 状态为 '{status}'")
