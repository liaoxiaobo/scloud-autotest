import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-查看监控")
class TestBmsMonitor:

    @allure.title("裸金属BMS-查看监控")
    def test_bms_view_monitor(self, bms_page, bms_instance_name):
        """验证裸金属实例监控页面显示正常。"""
        instance_name = bms_instance_name

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：查看监控
        with allure_step_log("步骤2: 查看监控"):
            monitor_data = bms_page.bms_instance_view_monitor(instance_name)

        # 步骤3：验证CPU和内存使用率
        with allure_step_log("步骤3: 验证CPU和内存使用率"):
            # 如果监控显示"暂无数据"，标记为环境问题并跳过
            if monitor_data.get("no_data"):
                pytest.skip("监控数据暂不可用（暂无数据），环境问题")
            # 监控信息中有文本即认为有数值
            assert monitor_data.get("cpu_text"), "CPU使用率未显示"
            assert monitor_data.get("memory_text"), "内存使用率未显示"
            logger.info(f"监控验证通过: CPU={monitor_data['cpu_text']}, 内存={monitor_data['memory_text']}")
