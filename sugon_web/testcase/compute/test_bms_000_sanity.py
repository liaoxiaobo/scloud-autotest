import allure
import json
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS创建产物验收")
class TestBmsSanity:

    @allure.title("裸金属BMS-回归准入验收")
    def test_bms_sanity(self, bms_page, bms_env, ssh_host):
        """检查软装创建产物是否满足后续 BMS 回归准入条件。"""
        instance_name = bms_env["instance_name"]
        bmc_ip = bms_env["bmc_ip"]
        preferred_node = bms_env["preferred_node"]
        network_name = bms_env["network_name"]

        with allure_step_log("步骤0: 校验BMS基线配置完整"):
            baseline = {
                "instance_name": instance_name,
                "bmc_ip": bmc_ip,
                "preferred_node": preferred_node,
                "network_name": network_name,
                "image_name": bms_env.get("image_name"),
            }
            allure.attach(
                json.dumps(baseline, ensure_ascii=False, indent=2),
                "BMS基线配置",
                allure.attachment_type.JSON,
            )
            missing = [key for key, value in baseline.items() if value in (None, "")]
            assert not missing, f"BMS基线配置缺失: {', '.join(missing)}"

        with allure_step_log("步骤1: 检查目标物理节点 Ready"):
            node_status = ssh_host.run(f"sudo kubectl get nodes {preferred_node} --no-headers", return_rc=True)
            node_output = node_status.get("stdout", "")
            assert node_status.get("rc") == 0, f"BMS目标节点 {preferred_node} 查询失败: {node_status}"
            assert "Ready" in node_output, f"BMS目标节点 {preferred_node} 不为 Ready: {node_output}"

        with allure_step_log("步骤2: 检查BMS网络存在"):
            bms_page._goto_submenu_safe("网络")
            assert "#/error" not in bms_page.page.url, f"进入BMS网络页失败: {bms_page.page.url}"
            bms_page.search(network_name)
            network_data = bms_page.get_row_data(network_name)
            assert network_data is not None, f"未找到BMS网络 '{network_name}'"
            allure.attach(
                json.dumps(network_data, ensure_ascii=False, indent=2),
                "BMS网络数据",
                allure.attachment_type.JSON,
            )

        with allure_step_log("步骤3: 检查BMC注册信息已被实例占用"):
            bms_page._goto_submenu_safe("注册")
            assert "#/error" not in bms_page.page.url, f"进入BMS注册页失败: {bms_page.page.url}"
            bms_page.search(bmc_ip)
            register_data = bms_page.get_row_data(bmc_ip)
            assert register_data is not None, f"未找到BMC注册信息 '{bmc_ip}'"
            register_status = register_data.get("状态", "")
            assert "已使用" in register_status, (
                f"BMC注册状态不满足回归准入要求，期望已使用，实际: {register_status}"
            )
            incomplete_fields = [
                key
                for key in ("CPU", "内存", "架构")
                if register_data.get(key) in (None, "", "--")
            ]
            assert not incomplete_fields, f"BMC注册硬件信息不完整: {incomplete_fields}, row={register_data}"
            allure.attach(
                json.dumps(register_data, ensure_ascii=False, indent=2),
                "BMC注册数据",
                allure.attachment_type.JSON,
            )
            logger.info(f"BMC '{bmc_ip}' 注册状态: {register_status}")

        with allure_step_log("步骤4: 检查裸金属实例运行中"):
            bms_page._goto_submenu_safe("裸金属实例")
            assert "#/error" not in bms_page.page.url, f"进入BMS实例页失败: {bms_page.page.url}"
            bms_page.search(instance_name)
            instance_data = bms_page.get_row_data(instance_name)
            assert instance_data is not None, f"未找到BMS实例 '{instance_name}'"
            status = instance_data.get("状态", "")
            assert not any(bad in status for bad in ["删除", "错误"]), f"BMS实例状态异常: {status}"
            assert "运行中" in status, f"BMS实例未达到回归准入状态，期望运行中，实际: {status}"
            allure.attach(
                json.dumps(instance_data, ensure_ascii=False, indent=2),
                "BMS实例数据",
                allure.attachment_type.JSON,
            )
            logger.info(f"BMS实例 '{instance_name}' 状态: {status}")
