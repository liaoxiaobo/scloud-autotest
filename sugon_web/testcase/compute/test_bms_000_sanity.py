import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS回归前置检查")
class TestBmsSanity:

    @allure.title("裸金属BMS-回归前置检查")
    def test_bms_sanity(self, bms_page, bms_env, ssh_host):
        """检查 BMS 回归依赖的基线资源是否可用。"""
        instance_name = bms_env["instance_name"]
        bmc_ip = bms_env["bmc_ip"]
        preferred_node = bms_env["preferred_node"]

        with allure_step_log("步骤1: 检查目标物理节点 Ready"):
            node_status = ssh_host.run(f"sudo kubectl get nodes {preferred_node} --no-headers", return_rc=True)
            if node_status.get("rc") != 0 or "Ready" not in node_status.get("stdout", ""):
                pytest.skip(f"BMS目标节点 {preferred_node} 不在线或不为 Ready")

        with allure_step_log("步骤2: 检查裸金属实例存在"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            assert row_data is not None, f"未找到BMS实例 '{instance_name}'"
            status = row_data.get("状态", "")
            assert not any(bad in status for bad in ["删除", "错误"]), f"BMS实例状态异常: {status}"
            logger.info(f"BMS实例 '{instance_name}' 状态: {status}")

        with allure_step_log("步骤3: 检查注册信息状态"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            register_data = bms_page.get_row_data(bmc_ip)
            assert register_data is not None, f"未找到BMC注册信息 '{bmc_ip}'"
            register_status = register_data.get("状态", "")
            assert any(ok in register_status for ok in ["已使用", "就绪", "注册完成"]), (
                f"BMC注册状态不满足回归要求: {register_status}"
            )
            logger.info(f"BMC '{bmc_ip}' 注册状态: {register_status}")
