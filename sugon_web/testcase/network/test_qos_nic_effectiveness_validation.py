import re
import time

import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


def _parse_iperf3_bandwidth(output: str) -> float:
    """从iperf3输出中解析平均带宽（Mbps）

    纯函数，只比较数据，不操作页面。
    匹配格式如:
        [  5]   0.00-50.00  sec   357 MBytes  59.9 Mbits/sec  0.000 ms  0/252758 (0%)

    Args:
        output: iperf3命令的stdout输出。

    Returns:
        float: 带宽值，单位Mbps。

    Raises:
        ValueError: 无法从输出中解析带宽。
    """
    lines = output.strip().split("\n")
    for line in reversed(lines):
        match = re.search(r"([\d.]+)\s+Mbits/sec", line)
        if match:
            return float(match.group(1))
        match = re.search(r"([\d.]+)\s+Gbits/sec", line)
        if match:
            return float(match.group(1)) * 1000
        match = re.search(r"([\d.]+)\s+Kbits/sec", line)
        if match:
            return float(match.group(1)) / 1000
    raise ValueError(f"无法从iperf3输出中解析带宽: {output}")


@allure.epic('网络服务')
@allure.feature('网络QoS')
@allure.story('网卡QoS限速生效性验证')
class TestQosNicEffectiveness:
    """验证虚机网卡QoS限速生效性"""

    @pytest.mark.parametrize("vpc", [{
        "cidr": "175.175.1.0/24",
        "name_prefix": "qos_",
    }], indirect=True)
    @pytest.mark.parametrize("vm", [{
        "basic": {"count": 2},
        "name_prefix": "qos_",
        "bind_mfip": True,
    }], indirect=True)
    @allure.title("网络QoS-网卡QoS限速生效性验证")
    def test_qos_nic_effectiveness(self, vpc, vm, vpc_page, ecs_page, ssh_vm):
        """验证网卡QoS限速后，iperf3实测带宽符合预期"""
        vm1, vm2 = vm
        qos_name = f"qos_{random_data()}"

        with allure_step_log("步骤1: 创建网络QoS"):
            vpc_page.qos_create(
                name=qos_name,
                send_rate=30,
                recv_rate=60,
            )
            vpc_page.assert_popup_success()
            row_data = vpc_page.get_row_data(qos_name)
            assert row_data.get("发送速率") == "30Mbps", \
                f"[FieldAssertion] 发送速率校验失败 | 期望: 30Mbps | 实际: {row_data.get('发送速率')}"
            assert row_data.get("接收速率") == "60Mbps", \
                f"[FieldAssertion] 接收速率校验失败 | 期望: 60Mbps | 实际: {row_data.get('接收速率')}"

        with allure_step_log("步骤2: 设置网卡QoS"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_nic_set_qos(vm1["name"], qos_name)
            ecs_page.assert_popup_success()

        with allure_step_log("步骤3: 验证接收速率"):
            ssh_vm.connect(vm1["mfip"])
            ssh_vm.run("pkill iperf3; nohup iperf3 -s > /dev/null 2>&1 &")
            for _ in range(30):
                result = ssh_vm.run("ss -lntp | grep 5201", return_rc=True)
                if result["rc"] == 0 and "5201" in result["stdout"]:
                    break
                time.sleep(2)
            else:
                raise AssertionError("[BackendAssertion] iperf3服务端未在60秒内就绪")

            ssh_vm.connect(vm2["mfip"])
            result = ssh_vm.run(
                f"iperf3 -c {vm1['ip']} -t 50",
                return_rc=True,
                timeout=70,
            )
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3客户端执行失败 | stderr: {result.get('stderr', '')}"
            bandwidth = _parse_iperf3_bandwidth(result["stdout"])
            logger.info(f"接收速率实测: {bandwidth} Mbps")
            assert 54 <= bandwidth <= 66, \
                f"[BackendAssertion] 接收速率校验失败 | 期望: 60±6 Mbps | 实际: {bandwidth} Mbps"

        with allure_step_log("步骤4: 验证发送速率"):
            ssh_vm.connect(vm2["mfip"])
            ssh_vm.run("pkill iperf3; nohup iperf3 -s > /dev/null 2>&1 &")
            for _ in range(30):
                result = ssh_vm.run("ss -lntp | grep 5201", return_rc=True)
                if result["rc"] == 0 and "5201" in result["stdout"]:
                    break
                time.sleep(2)
            else:
                raise AssertionError("[BackendAssertion] iperf3服务端未在60秒内就绪")

            ssh_vm.connect(vm1["mfip"])
            result = ssh_vm.run(
                f"iperf3 -c {vm2['ip']} -t 50",
                return_rc=True,
                timeout=70,
            )
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3客户端执行失败 | stderr: {result.get('stderr', '')}"
            bandwidth = _parse_iperf3_bandwidth(result["stdout"])
            logger.info(f"发送速率实测: {bandwidth} Mbps")
            assert 27 <= bandwidth <= 33, \
                f"[BackendAssertion] 发送速率校验失败 | 期望: 30±3 Mbps | 实际: {bandwidth} Mbps"

        with allure_step_log("步骤5: 清理网卡QoS并删除QoS"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_nic_set_qos(vm1["name"], "不限制")
            vpc_page.goto_submenu("网络QoS")
            vpc_page.qos_delete(qos_name)
            vpc_page.assert_deleted(qos_name)
