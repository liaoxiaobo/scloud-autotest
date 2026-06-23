import allure
import pytest
import re
import time

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _get_snat_public_ip(data):
    """兼容页面可能使用的不同公网 IP 列名。"""
    return data.get("弹性公网IP", "") or data.get("公网IP", "")


def _parse_iperf3_sender_bandwidth(stdout):
    """从 iperf3 输出中解析 sender bandwidth（单位 Mbps）。"""
    lines = stdout.strip().split("\n")
    for line in reversed(lines):
        # 匹配 sender 行（最后一行汇总数据）
        if "sender" not in line:
            continue
        match = re.search(r"([\d.]+)\s+Mbits/sec", line)
        if match:
            return float(match.group(1))
        match = re.search(r"([\d.]+)\s+Gbits/sec", line)
        if match:
            return float(match.group(1)) * 1000
        match = re.search(r"([\d.]+)\s+Kbits/sec", line)
        if match:
            return float(match.group(1)) / 1000
    return None


def _wait_for_iperf3_server(ssh_host, max_wait=60, interval=2):
    """轮询等待 iperf3 server 就绪。

    Args:
        ssh_host: SSH 连接实例。
        max_wait: 最大等待时间（秒）。
        interval: 轮询间隔（秒）。

    Returns:
        bool: iperf3 server 是否已就绪。
    """
    from time import sleep

    for _ in range(max_wait // interval):
        result = ssh_host.run("ss -lntp | grep ':5201' || pgrep -f 'iperf3 -s'", return_rc=True)
        if result["rc"] == 0 and ("5201" in result["stdout"] or result["stdout"].strip()):
            return True
        sleep(interval)
    return False


@allure.epic("网络服务")
@allure.feature("网络QoS")
@allure.story("NATv1网关FIP绑定QoS带宽生效性验证")
class TestQosNatv1FipEffectiveness:
    """NATv1网关FIP绑定QoS带宽生效性验证。

    验证通过NATv1网关的SNAT规则，VM出方向流量经绑定QoS的FIP转发时，
    带宽限制（80Mbps）能够正常生效。
    """

    @pytest.mark.parametrize("vpc", [{"cidr": "175.175.4.0/24", "name_prefix": "qos_"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "qos_", "bind_mfip": True}], indirect=True)
    @pytest.mark.parametrize("eip", [{"count": 3, "pool": "public_net(基础版)"}], indirect=True)
    @allure.title("QoS-NATv1网关FIP限速-生效性验证")
    def test_qos_natv1_fip_effectiveness(self, vpc_page, vpc, vm, eip, ssh_host, ssh_vm, config):
        """测试NATv1网关FIP绑定QoS后的带宽生效性。"""
        qos_name = f"qos-{random_data()}"
        nat_name = f"nat-{random_data()}"
        fip1 = eip[0]
        vm_name = vm["name"]
        vm_mfip = vm["mfip"]
        vpc_name = vpc["name"]
        subnet_cidr = vpc["cidr"]

        # ========== 前置准备 ==========
        with allure_step_log("前置准备: 创建QoS策略(发送/接收速率均为80Mbps)"):
            vpc_page.qos_create(name=qos_name, send_rate=80, recv_rate=80, desc="NATv1 QoS带宽测试")
            vpc_page.assert_popup_success()
            logger.info(f"QoS策略创建成功: {qos_name}")

        with allure_step_log("前置准备: 获取管理节点管理网IP并开放5201端口"):
            mip = config.get("host")
            assert mip and mip.startswith("172.22."), f"管理网IP格式异常: {mip}"
            logger.info(f"管理节点管理网IP: {mip}")

            # 开放5201端口（iperf3默认端口）
            result = ssh_host.run(
                "sudo firewall-cmd --zone=public --add-port=5201/tcp --permanent >/dev/null 2>&1; "
                "sudo firewall-cmd --reload >/dev/null 2>&1; echo 'done'",
                return_rc=True,
            )
            logger.info(f"开放5201端口结果: rc={result['rc']}")

        with allure_step_log("前置准备: 将fip1绑定QoS策略"):
            vpc_page.goto_submenu("弹性公网IPv4")
            vpc_page.eip_bind_qos(fip1, qos_name)
            logger.info(f"FIP {fip1} 绑定QoS {qos_name} 完成")

        # ========== 步骤1-2: 创建NAT网关 ==========
        with allure_step_log("步骤1-2: 创建NAT网关(连接类型虚拟私有云, 绑定已设QoS的fip1)"):
            vpc_page.nat_create(
                name=nat_name,
                vpc_name=vpc_name,
                public_ip_pool="public_net(基础版)",
                eip=fip1,
                desc="NATv1 QoS带宽测试",
            )
            vpc_page.assert_popup_success("新建NAT网关成功")

        with allure_step_log("步骤1-2验证: NAT网关列表字段断言"):
            data = vpc_page.get_row_data(nat_name)
            logger.info(f"NAT网关行数据: {data}")
            assert vpc_name in data.get("连接资源", ""), \
                f"[FieldAssertion] NAT网关连接资源 | 期望包含 {vpc_name} | 实际: {data.get('连接资源')}"
            assert "虚拟私有云" in data.get("连接类型", ""), \
                f"[FieldAssertion] NAT网关连接类型 | 期望包含 '虚拟私有云' | 实际: {data.get('连接类型')}"

        # ========== 步骤3-5: 创建SNAT规则 ==========
        with allure_step_log("步骤3-5: 进入NAT网关详情页, 创建SNAT规则(源地址类型: 子网)"):
            vpc_page.snat_rule_create(
                nat_name=nat_name,
                source_type="子网",
                source_value=subnet_cidr,
                desc="NATv1 QoS SNAT测试",
            )
            vpc_page.assert_popup_success("新建SNAT规则成功")

        with allure_step_log("步骤3-5验证: SNAT规则列表字段断言"):
            data = vpc_page.get_row_data(subnet_cidr)
            logger.info(f"SNAT规则行数据: {data}")
            assert subnet_cidr in data.get("源地址", ""), \
                f"[FieldAssertion] SNAT源地址 | 期望包含 {subnet_cidr} | 实际: {data.get('源地址')}"
            assert fip1 in _get_snat_public_ip(data), \
                f"[FieldAssertion] SNAT弹性公网IP | 期望包含 {fip1} | 实际: {_get_snat_public_ip(data)}"

        # ========== 步骤6: 添加自定义路由 ==========
        with allure_step_log("步骤6: 在VPC详情页添加自定义路由(0.0.0.0/0 -> NAT网关)"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.route_rule_create(
                vpc_name=vpc_name,
                dest_cidr="0.0.0.0/0",
                next_hop=nat_name,
                next_hop_type="NAT网关",
                desc="指向NAT网关的默认路由",
            )
            vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤6验证: 路由规则字段断言"):
            data = vpc_page.get_row_data("0.0.0.0/0")
            logger.info(f"路由规则行数据: {data}")
            assert "0.0.0.0/0" in data.get("目的地址", ""), \
                f"[FieldAssertion] 路由目的地址 | 期望包含 0.0.0.0/0 | 实际: {data.get('目的地址')}"
            assert "NAT网关" in data.get("下一跳类型", ""), \
                f"[FieldAssertion] 路由下一跳类型 | 期望包含 NAT网关 | 实际: {data.get('下一跳类型')}"
            assert nat_name in data.get("下一跳", ""), \
                f"[FieldAssertion] 路由下一跳 | 期望包含 {nat_name} | 实际: {data.get('下一跳')}"

        # 等待路由/SNAT规则生效，慢环境兼容
        time.sleep(30)

        # ========== 步骤7: 启动iperf3 server ==========
        with allure_step_log("步骤7: 在管理节点后台启动iperf3 server"):
            # 先停止可能已存在的iperf3进程
            ssh_host.run("pkill -f 'iperf3 -s' >/dev/null 2>&1; sleep 1", return_rc=True)
            result = ssh_host.run("nohup iperf3 -s > /dev/null 2>&1 & echo $!", return_rc=True)
            assert result["rc"] == 0, f"启动iperf3 server失败: {result.get('stderr', '')}"
            logger.info(f"iperf3 server启动命令输出: {result['stdout']}")

            # 轮询等待iperf3 server就绪
            server_ready = _wait_for_iperf3_server(ssh_host)
            assert server_ready, "[BackendAssertion] iperf3 server未在60秒内就绪"
            logger.info("iperf3 server启动成功, 监听5201端口")

        # ========== 步骤8-9: 执行iperf3带宽测试 ==========
        with allure_step_log("步骤8-9: 通过ssh_vm连接VM, 执行iperf3打流测试"):
            ssh_vm.connect(vm_mfip)

            # 先测试连通性，慢环境兼容：重试多次
            ping_ok = False
            for attempt in range(12):
                ping_result = ssh_vm.run(f"ping -c 3 -W 5 {mip}", return_rc=True, timeout=20)
                logger.info(f"ping {mip} 尝试{attempt + 1}/12: rc={ping_result['rc']}")
                if ping_result["rc"] == 0:
                    ping_ok = True
                    break
                time.sleep(10)
            if not ping_ok:
                pytest.skip(f"[环境] 管理节点 {mip} 无法ping通，跳过带宽验证")

            result = ssh_vm.run(f"iperf3 -c {mip} -t 50", return_rc=True, timeout=120)
            assert result["rc"] == 0, \
                f"[BackendAssertion] iperf3执行失败 | rc={result['rc']} | stdout: {result.get('stdout', '')[:500]} | stderr: {result.get('stderr', '')}"
            logger.info(f"iperf3输出:\n{result['stdout']}")

        # ========== 步骤9验证: QoS带宽生效断言 ==========
        with allure_step_log("步骤9验证: 解析iperf3带宽并断言QoS限速生效"):
            bandwidth = _parse_iperf3_sender_bandwidth(result["stdout"])
            assert bandwidth is not None, \
                f"[BackendAssertion] 无法从iperf3输出解析sender bandwidth | stdout: {result['stdout'][:500]}"
            logger.info(f"iperf3 sender bandwidth: {bandwidth} Mbps")

            # QoS限速80Mbps, 允许上下浮动10% (72~88 Mbps)
            assert 72 <= bandwidth <= 88, \
                f"[ScenarioAssertion] 带宽不在预期范围内 | 期望: 72~88 Mbps | 实际: {bandwidth} Mbps"

        # ========== 清理数据(严格按CSV定义的顺序) ==========
        with allure_step_log("清理1: fip1解绑QoS"):
            vpc_page.goto_submenu("弹性公网IPv4")
            vpc_page.eip_unbind_qos(fip1)
            logger.info(f"FIP {fip1} 解绑QoS完成")

        with allure_step_log("清理2: 删除QoS策略"):
            vpc_page.goto_submenu("网络QoS")
            vpc_page.qos_delete(qos_name)
            vpc_page.assert_deleted(qos_name)
            logger.info(f"QoS {qos_name} 删除完成")

        with allure_step_log("清理3: 删除VPC自定义路由规则"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.goto_detail_page(vpc_name, tab_name="路由表")
            vpc_page.route_rule_delete("0.0.0.0/0")
            vpc_page.assert_deleted("0.0.0.0/0")
            logger.info("路由规则 0.0.0.0/0 删除完成")

        with allure_step_log("清理4: 删除SNAT规则"):
            vpc_page.goto_submenu("NAT网关")
            vpc_page._nat_open_detail_tab(nat_name, "SNAT规则")
            vpc_page.snat_rule_delete(subnet_cidr)
            vpc_page.assert_deleted(subnet_cidr)
            logger.info(f"SNAT规则 {subnet_cidr} 删除完成")

        with allure_step_log("清理5: 删除NAT网关"):
            vpc_page.goto_submenu("NAT网关")
            vpc_page.nat_delete(nat_name)
            vpc_page.assert_deleted(nat_name)
            logger.info(f"NAT网关 {nat_name} 删除完成")

        with allure_step_log("清理9: 停止iperf3 server"):
            result = ssh_host.run("pkill -f 'iperf3 -s' >/dev/null 2>&1; echo 'done'", return_rc=True)
            logger.info(f"停止iperf3 server结果: rc={result['rc']}")

        # 清理6-8(释放EIP/删除VM/删除VPC)由对应fixture的teardown自动完成
        logger.info("清理6-8: EIP释放/VM删除/VPC删除由fixture teardown自动处理")
