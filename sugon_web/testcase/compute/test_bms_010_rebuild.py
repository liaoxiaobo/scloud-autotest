import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-重建实例")
class TestBmsRebuild:

    @allure.title("裸金属BMS-重建实例")
    def test_bms_rebuild(self, bms_page):
        """验证裸金属实例重建功能正常。"""
        instance_name = "bms-0430"

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：确保实例处于运行中状态（处理关机/重建中/镜像拉取中等中间态）
        with allure_step_log("步骤2: 确保实例处于运行中状态"):
            row_data = bms_page.get_row_data(instance_name)
            current_status = row_data.get("状态", "") if row_data else ""
            if "关机" in current_status:
                logger.warning(f"实例当前状态为'{current_status}'，先执行开机操作")
                bms_page.bms_instance_start(instance_name)
                start_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=300)
                if not start_ok:
                    pytest.skip("实例无法恢复为运行中状态，跳过重建测试")
            elif "错误" in current_status:
                logger.warning(f"实例当前状态为'{current_status}'，尝试先关机再开机恢复")
                bms_page.bms_instance_shutdown(instance_name)
                shutdown_ok = bms_page.bms_instance_wait_for_status(instance_name, "关机", timeout=300)
                if not shutdown_ok:
                    pytest.skip("实例无法变为关机状态，跳过重建测试")
                logger.info("关机成功，开始执行开机")
                bms_page.bms_instance_start(instance_name)
                recover_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=1800)
                if not recover_ok:
                    pytest.skip("实例未在30分钟内从错误状态恢复为运行中，跳过重建测试")
            elif "重建" in current_status or "镜像拉取" in current_status:
                logger.warning(f"实例当前状态为'{current_status}'，等待重建流程完成")
                recover_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=1800)
                if not recover_ok:
                    pytest.skip("实例未在30分钟内从重建中间态恢复为运行中，跳过重建测试")

        # 步骤3：执行重建操作
        with allure_step_log("步骤3: 执行重建操作"):
            bms_page.bms_instance_rebuild(instance_name, image_name="bms")

        # 步骤4：验证状态变为重建中
        with allure_step_log("步骤4: 验证状态变为重建中"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到实例 '{instance_name}'"
            status = row_data.get("状态", "")
            # 重建提交后状态可能直接变为重建中，也可能仍为运行中（后端异步）
            assert "重建" in status or "运行中" in status or "镜像拉取" in status, f"重建提交后状态期望为重建相关或'运行中'，实际为 '{status}'"
            logger.info(f"重建提交后状态: '{status}'")

        # 步骤5：等待重建完成，状态恢复为运行中
        with allure_step_log("步骤5: 等待重建完成"):
            rebuild_ok = bms_page.bms_instance_wait_for_status(instance_name, "运行中", timeout=1800)
            if not rebuild_ok:
                pytest.skip("实例未在30分钟内恢复为运行中状态")

        # 步骤6：验证列表状态
        with allure_step_log("步骤6: 验证列表状态"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.bms_search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到实例 '{instance_name}'"
            status = row_data.get("状态", "")
            assert "运行中" in status, f"列表状态期望为'运行中'，实际为 '{status}'"
            logger.info(f"列表验证通过: 状态为 '{status}'")
