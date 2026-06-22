import threading
import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


PORT = 5050
DESC = "1234567890edwqWDWQ中文~"
HEALTH_REQUEST = "hello"
HEALTH_RESPONSE = "world"
BAD_RESPONSE = "w2orld"
UDP2_LOG = "/tmp/udp2_{port}.log"


def _start_udp_server(ssh_vm, vm_info, port, response):
    """在后端虚机上启动 test-udp2.py UDP server。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典，需包含 mfip 和 name。
        port: UDP server 监听端口。
        response: server 收到请求后的响应内容。

    Raises:
        AssertionError: 服务未在60秒内就绪。
    """
    mfip = vm_info["mfip"]
    log_path = UDP2_LOG.format(port=port)
    ssh_vm.connect(mfip)
    ssh_vm.run(f"pkill -f 'test-udp2.py -s {port}'", check_rc=False)
    ssh_vm.run(f": > {log_path}", check_rc=False)
    ssh_vm.run(
        f"nohup python -u /opt/network_tool/test-udp2.py -s {port} {response} > {log_path} 2>&1 &",
        check_rc=False,
        wait_for_exit=False,
    )
    end_time = time.time() + 60
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lunp | grep ':{port} ' || netstat -lnup 2>/dev/null | grep ':{port} '",
            check_rc=False,
            return_rc=True,
        )
        if result["rc"] == 0 and f":{port}" in result["stdout"]:
            return
        threading.Event().wait(5)
    raise AssertionError(
        f"[BackendAssertion] 虚机 {vm_info['name']} 的 UDP server 端口 {port} 在60秒内未就绪"
    )


def _stop_udp_server(ssh_vm, vm_info, port):
    """停止后端虚机上的 test-udp2.py UDP server。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典，需包含 mfip 和 name。
        port: UDP server 监听端口。

    Raises:
        AssertionError: 端口在60秒内未释放。
    """
    ssh_vm.connect(vm_info["mfip"])
    ssh_vm.run(f"pkill -f 'test-udp2.py -s {port}'", check_rc=False)
    end_time = time.time() + 60
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lunp | grep ':{port} ' || netstat -lnup 2>/dev/null | grep ':{port} '",
            check_rc=False,
            return_rc=True,
        )
        if result["rc"] != 0:
            return
        threading.Event().wait(2)
    raise AssertionError(
        f"[BackendAssertion] 虚机 {vm_info['name']} 的 UDP server 端口 {port} 在60秒内未释放"
    )


def _read_udp2_log(ssh_vm, vm_info, port):
    """读取 test-udp2.py UDP server 的输出日志。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典，需包含 mfip。
        port: UDP server 监听端口。

    Returns:
        str: 日志内容，若日志不存在返回空字符串。
    """
    ssh_vm.connect(vm_info["mfip"])
    result = ssh_vm.run(
        f"cat {UDP2_LOG.format(port=port)} 2>/dev/null",
        check_rc=False,
        return_rc=True,
    )
    return result.get("stdout", "") if isinstance(result, dict) else ""


def _send_udp_via_test_udp2(ssh_vm, vm_info, target_ip, port, message):
    """使用 test-udp2.py client 发送 UDP 消息。

    Args:
        ssh_vm: 用于连接客户端虚机的 SSH 客户端。
        vm_info: 虚机信息字典，需包含 mfip。
        target_ip: 目标 IP 地址（VIP）。
        port: 目标端口。
        message: 待发送的消息内容。

    Returns:
        dict: SSH 命令执行结果，包含 rc、stdout、stderr。
    """
    ssh_vm.connect(vm_info["mfip"])
    return ssh_vm.run(
        f"python /opt/network_tool/test-udp2.py -c {target_ip} {port} {message}",
        check_rc=False,
        return_rc=True,
        timeout=20,
    )


def _run_udp_health_check(vpc_page, slb, vm, ssh_vm, clean_lb_listener, version, custom_hc=True):
    """执行 UDP 健康检查可用性验证的公共步骤。

    Args:
        vpc_page: VPC 页面对象。
        slb: SLB fixture 返回的负载均衡信息。
        vm: VM fixture 返回的虚机列表。
        ssh_vm: SSH 虚拟机客户端 fixture。
        clean_lb_listener: 监听器清理注册表 fixture。
        version: SLB 版本字符串，"V1" 或 "V2"。
        custom_hc: 是否使用自定义健康检查（V1支持，V2不支持）。
    """
    cleanup = clean_lb_listener
    requester = vm[0]
    backends = vm[1:4]
    lb_name = f"lb-udp-custom-{random_data()}"
    pool_name = f"pool-{random_data()}"
    lb_vip = vpc_page.get_slb_vip(slb["name"])

    with allure_step_log("步骤1: 创建UDP监听器(自定义健康检查)" if custom_hc else "步骤1: 创建UDP监听器(基础健康检查)"):
        create_kwargs = {
            "slb_name": slb["name"],
            "lb_name": lb_name,
            "protocol": "UDP",
            "port": PORT,
            "desc": DESC,
            "pool_name": pool_name,
            "balance_method": "源IP",
            "health_check": True,
            "health_type": "UDP",
        }
        if custom_hc:
            create_kwargs["health_request"] = HEALTH_REQUEST
            create_kwargs["health_expected_response"] = HEALTH_RESPONSE
        vpc_page.slb_lb_create(**create_kwargs)
        vpc_page.assert_popup_success()
        vpc_page.assert_listener_exists(lb_name)
        cleanup.add_listener(
            {"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name}
        )

    with allure_step_log("步骤2: 添加资源池成员"):
        vpc_page.lb_pool_add_vm(
            vm_names=[b["name"] for b in backends],
            lb_name=lb_name,
            pool_name=pool_name,
            ports=PORT,
        )
        vpc_page.assert_popup_success()
        for backend in backends:
            vpc_page.assert_lb_pool_member_info(
                backend["name"], port=PORT, resource_status="运行中"
            )

    with allure_step_log("步骤3: 后端启动UDP server(正确响应)"):
        for backend in backends:
            _start_udp_server(ssh_vm, backend, PORT, HEALTH_RESPONSE)
            cleanup.add_backend_server(
                backend, port=PORT, kill_pattern=f"test-udp2.py -s {PORT}"
            )

    with allure_step_log("步骤4: VIP访问测试"):
        result = _send_udp_via_test_udp2(
            ssh_vm, requester, lb_vip, PORT, HEALTH_REQUEST
        )
        assert result["rc"] == 0, (
            f"[BackendAssertion] UDP 消息发送失败 | stderr: {result.get('stderr', '')}"
        )

    with allure_step_log("步骤5: 验证Real-Server初始状态"):
        for backend in backends:
            vpc_page.wait_lb_pool_member_status(
                lb_name, pool_name, backend["name"],
                expected_status="运行中", timeout=60,
            )

    with allure_step_log("步骤6: 模拟健康检查失败(ecs1)"):
        _stop_udp_server(ssh_vm, backends[0], PORT)
        if custom_hc:
            _start_udp_server(ssh_vm, backends[0], PORT, BAD_RESPONSE)

    with allure_step_log("步骤7: 验证ecs1变为离线"):
        vpc_page.wait_lb_pool_member_status(
            lb_name, pool_name, backends[0]["name"],
            expected_status="离线", timeout=60,
        )
        for backend in backends[1:3]:
            vpc_page.assert_lb_pool_member_info(
                backend["name"], resource_status="运行中"
            )

    with allure_step_log("步骤8: VIP访问(仅ecs2/ecs3应接收)"):
        result = _send_udp_via_test_udp2(
            ssh_vm, requester, lb_vip, PORT, HEALTH_REQUEST
        )
        assert result["rc"] == 0, (
            f"[BackendAssertion] UDP 消息发送失败 | stderr: {result.get('stderr', '')}"
        )

        client_response = (result.get("stdout") or "").strip()
        logger.info("UDP client response: %r", client_response)

        # client stdout format: "Client send: hello\nClient recv: world\n..."
        # 健康检查请求也会写入后端日志，因此后端日志不能作为VIP流量分发依据，
        # 必须以客户端收到的响应为准：收到 world 说明流量到达健康后端，
        # 收到 w2orld 说明流量被错误路由到已离线的 ecs1。
        has_healthy = f"Client recv: {HEALTH_RESPONSE}" in client_response
        has_bad = f"Client recv: {BAD_RESPONSE}" in client_response

        if has_healthy and not has_bad:
            logger.info(
                "VIP 流量仅到达健康后端: 客户端全部收到 '%s' 响应", HEALTH_RESPONSE
            )
        elif has_bad:
            raise AssertionError(
                f"[ScenarioAssertion] 客户端收到错误响应 '{BAD_RESPONSE}'，"
                f"说明 VIP 消息被路由到已离线的 ecs1 | client_response={client_response!r}"
            )
        else:
            raise AssertionError(
                f"[ScenarioAssertion] 客户端未收到预期的健康响应 '{HEALTH_RESPONSE}' | "
                f"client_response={client_response!r}"
            )


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("UDP自定义健康检查验证")
class TestSlbUdpCustomHealthCheckV1:
    def test_udp_custom_health_check(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title("lbv1 > udp自定义健康检查验证 > 可用性验证")
        _run_udp_health_check(vpc_page, slb, vm, ssh_vm, clean_lb_listener, "V1", custom_hc=True)


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V2"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("UDP自定义健康检查验证")
class TestSlbUdpCustomHealthCheckV2:
    def test_udp_custom_health_check(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title("v2-lbv1 > udp自定义健康检查验证 > 可用性验证")
        _run_udp_health_check(vpc_page, slb, vm, ssh_vm, clean_lb_listener, "V2", custom_hc=False)
