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
@allure.story('FIP绑定QoS限速生效性验证')
class TestQosFipEffectiveness:
    """验证虚机绑定FIP后QoS限速生效性"""

    @pytest.mark.parametrize("vpc", [{
        "cidr": "175.175.2.0/24",
        "name_prefix": "qos_",
    }], indirect=True)
    @pytest.mark.parametrize("vm", [{
        "basic": {"count": 2},
        "name_prefix": "qos_",
        "bind_mfip": True,
    }], indirect=True)
    @pytest.mark.parametrize("eip", [{
        "count": 3,
        "pool": "public_net(基础版)",
    }], indirect=True)
    @allure.title("网络QoS-FIP绑定QoS限速生效性验证")
    def test_qos_fip_effectiveness(self, vpc, vm, eip, vpc_page, ecs_page, ssh_vm):
        """验证FIP绑定QoS后，iperf3实测带宽符合预期，解绑后恢复"""
        vm1, vm2 = vm
        fips = eip if isinstance(eip, list) else [eip]
        assert len(fips) >= 3, f"[BackendAssertion] 期望分配至少3个FIP，实际: {len(fips)}"
        fip1, fip2 = fips[0], fips[1]
        qos_name = f"qos_{random_data()}"

        with allure_step_log("步骤1: 创建网络QoS"):
            vpc_page.goto_submenu("网络QoS")
            vpc_page.qos_create(
                name=qos_name,
                send_rate=200,
                recv_rate=100,
            )
            vpc_page.assert_popup_success()
            row_data = vpc_page.get_row_data(qos_name)
            assert row_data.get("发送速率") == "200Mbps", \
                f"[FieldAssertion] 发送速率校验失败 | 期望: 200Mbps | 实际: {row_data.get('发送速率')}"
            assert row_data.get("接收速率") == "100Mbps", \
                f"[FieldAssertion] 接收速率校验失败 | 期望: 100Mbps | 实际: {row_data.get('接收速率')}"

        with allure_step_log("步骤2: FIP绑定QoS"):
            vpc_page.eip_bind_qos(fip1, qos_name)
            row_data = vpc_page.get_row_data(fip1)
            assert row_data.get("发送速率") == "200Mbps", \
                f"[FieldAssertion] FIP发送速率校验失败 | 期望: 200Mbps | 实际: {row_data.get('发送速率')}"
            assert row_data.get("接收速率") == "100Mbps", \
                f"[FieldAssertion] FIP接收速率校验失败 | 期望: 100Mbps | 实际: {row_data.get('接收速率')}"

        with allure_step_log("步骤3: ECS绑定弹性公网IP"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_bind_pub_ip(vm1["name"], subnet=vpc["subnet_name"], pub_net="public_net(基础版)", eip_ip=fip1)
            ecs_page.wait_for_page_ready()
            ecs_page.page.wait_for_timeout(3000)
            ecs_page.ecs_bind_pub_ip(vm2["name"], subnet=vpc["subnet_name"], pub_net="public_net(基础版)", eip_ip=fip2)

        with allure_step_log("步骤4: 验证接收速率（QoS限制100Mbps）"):
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
                f"iperf3 -c {fip1} -t 50",
                return_rc=True,
                timeout=70,
            )
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3客户端执行失败 | stderr: {result.get('stderr', '')}"
            bandwidth = _parse_iperf3_bandwidth(result["stdout"])
            logger.info(f"接收速率实测: {bandwidth} Mbps")
            assert 90 <= bandwidth <= 110, \
                f"[BackendAssertion] 接收速率校验失败 | 期望: 100±10 Mbps | 实际: {bandwidth} Mbps"

            ssh_vm.connect(vm1["mfip"])
            ssh_vm.run("pkill iperf3")

        with allure_step_log("步骤5: 验证发送速率（QoS限制200Mbps）"):
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
                f"iperf3 -c {fip2} -t 50",
                return_rc=True,
                timeout=70,
            )
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3客户端执行失败 | stderr: {result.get('stderr', '')}"
            bandwidth = _parse_iperf3_bandwidth(result["stdout"])
            logger.info(f"发送速率实测: {bandwidth} Mbps")
            assert 180 <= bandwidth <= 220, \
                f"[BackendAssertion] 发送速率校验失败 | 期望: 200±20 Mbps | 实际: {bandwidth} Mbps"

            ssh_vm.connect(vm2["mfip"])
            ssh_vm.run("pkill iperf3")

        with allure_step_log("步骤6: 解绑FIP的QoS"):
            vpc_page.eip_unbind_qos(fip1)
            row_data = vpc_page.get_row_data(fip1)
            assert row_data.get("发送速率") == "不限制", \
                f"[FieldAssertion] 解绑后发送速率校验失败 | 期望: 不限制 | 实际: {row_data.get('发送速率')}"
            assert row_data.get("接收速率") == "不限制", \
                f"[FieldAssertion] 解绑后接收速率校验失败 | 期望: 不限制 | 实际: {row_data.get('接收速率')}"

        with allure_step_log("步骤7: 验证解绑后接收速率未受限"):
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
                f"iperf3 -c {fip1} -t 50",
                return_rc=True,
                timeout=70,
            )
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3客户端执行失败 | stderr: {result.get('stderr', '')}"
            bandwidth = _parse_iperf3_bandwidth(result["stdout"])
            logger.info(f"解绑后接收速率实测: {bandwidth} Mbps")
            assert bandwidth > 150, \
                f"[BackendAssertion] 解绑后接收速率校验失败 | 期望: >150 Mbps | 实际: {bandwidth} Mbps"

            ssh_vm.connect(vm1["mfip"])
            ssh_vm.run("pkill iperf3")

        with allure_step_log("步骤8: 清理测试数据"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_unbind_pub_ip(vm1["name"], fip1)
            ecs_page.ecs_unbind_pub_ip(vm2["name"], fip2)

            # 防御性解绑：确保FIP1的QoS已解绑，否则QoS无法删除
            try:
                vpc_page.eip_unbind_qos(fip1)
            except Exception:
                pass  # 可能已经被解绑了

            vpc_page.goto_submenu("网络QoS")
            vpc_page.qos_delete(qos_name)
            vpc_page.assert_deleted(qos_name)
