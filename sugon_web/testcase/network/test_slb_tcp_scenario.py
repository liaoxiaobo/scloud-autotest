import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener, clean_ip_group
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    count_lb_responses,
    is_http_reachable,
    prepare_http_backend,
    stop_http_backend,
    wait_for_ping_reachable,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


PORT = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监听器场景验证")
class _BaseTestLbTcpScenario:
    SLB_VERSION = ""

    def test_lb_tcp_round_robin(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-新建监听器-TCP+轮询基本功能验证")
        """验证 TCP 监听器创建、资源池成员添加、轮询算法及公网访问。"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建TCP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤4: 内网VIP访问测试"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html"
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} TCP 内网 VIP 轮询验证",
            )

        with allure_step_log("步骤5: 绑定公网IP"):
            available_eips = vpc_page.get_available_eips(slb["name"])
            if len(available_eips) < 1:
                pytest.skip("环境问题：当前环境无可用公网IP")
            eip = vpc_page.slb_bind_eip_by_ip(slb["name"], available_eips[0])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == eip, f"绑定公网IP不一致: 期望{eip}, 实际{actual_eip}"

        with allure_step_log("步骤6: 公网IP访问测试"):
            assert is_http_reachable(
                ssh_host, f"http://{eip}:{PORT}/index.html",
                timeout_sec=60, interval_sec=5, connect_timeout=5,
            ), f"公网IP {eip} 绑定成功但60秒内仍不可达，请检查EIP绑定状态或网络连通性"
            responses = collect_lb_http_responses(
                ssh_host,
                f"http://{eip}:{PORT}/index.html",
                count=30,
                interval_sec=1,
                connect_timeout=10,
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} TCP 公网 EIP 轮询验证",
                tolerance=0.25,
            )

    def test_lb_tcp_health_check(self, vpc_page, slb, vm, ssh_vm, clean_lb_listener):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-健康检查器-TCP基本功能验证")
        """验证 TCP 健康检查的开启、关闭及状态变化对流量分发的影响。"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-tcp-hc-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }

        with allure_step_log("步骤1: 创建TCP监听器（开启健康检查）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="TCP",
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤4: 确认Real-Server初始状态为运行中"):
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], resource_status="运行中"
                )

        with allure_step_log("步骤5: 停止ecs1和ecs2的web服务"):
            stop_http_backend(ssh_vm, backends[0], port=PORT)
            stop_http_backend(ssh_vm, backends[1], port=PORT)

        with allure_step_log("步骤6: 确认只有ecs3健康"):
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="离线", timeout=120,
                )
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], resource_status="运行中"
            )

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤7: 内网VIP访问只返回ecs3"):
            ssh_vm.connect(requester["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=6
            )
            assert counter.get("this is ecs3", 0) > 0, f"期望ecs3响应，实际: {dict(counter)}"
            assert counter.get("this is ecs1", 0) == 0, f"ecs1不应响应，实际: {dict(counter)}"
            assert counter.get("this is ecs2", 0) == 0, f"ecs2不应响应，实际: {dict(counter)}"

        with allure_step_log("步骤8: 恢复ecs1和ecs2的web服务"):
            prepare_http_backend(ssh_vm, backends[0], "ecs1", port=PORT)
            prepare_http_backend(ssh_vm, backends[1], "ecs2", port=PORT)
            cleanup.add_backend_server(backends[0], port=PORT)
            cleanup.add_backend_server(backends[1], port=PORT)

        with allure_step_log("步骤9: 确认全部节点恢复运行中"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], resource_status="运行中"
                )

        with allure_step_log("步骤10: 关闭健康检查"):
            vpc_page.lb_pool_config_health_check(lb_name, pool_name, enable=False)

        with allure_step_log("步骤11: 停止web服务，确认健康状态不变"):
            stop_http_backend(ssh_vm, backends[0], port=PORT)
            stop_http_backend(ssh_vm, backends[1], port=PORT)
            time.sleep(5)
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], resource_status="运行中"
                )

        with allure_step_log("步骤12: 内网VIP访问测试（关闭健康检查）"):
            ssh_vm.connect(requester["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=12
            )
            assert counter.get("this is ecs3", 0) > 0, f"期望ecs3响应，实际: {dict(counter)}"
            assert counter.get("this is ecs1", 0) == 0, f"ecs1不应直接响应，实际: {dict(counter)}"
            assert counter.get("this is ecs2", 0) == 0, f"ecs2不应直接响应，实际: {dict(counter)}"

        with allure_step_log("步骤13: 确认健康检查为关闭状态"):
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            vpc_page.assert_lb_pool_basic_info(pool_name, health_check="未开启")

        with allure_step_log("步骤14: 重新开启健康检查"):
            vpc_page.lb_pool_config_health_check(
                lb_name, pool_name, enable=True, health_type="TCP"
            )
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="离线", timeout=120,
                )
            vpc_page.wait_lb_pool_member_status(
                lb_name, pool_name, backends[2]["name"],
                expected_status="运行中", timeout=120,
            )

        with allure_step_log("步骤15: 恢复ecs1和ecs2的web服务"):
            prepare_http_backend(ssh_vm, backends[0], "ecs1", port=PORT)
            prepare_http_backend(ssh_vm, backends[1], "ecs2", port=PORT)
            cleanup.add_backend_server(backends[0], port=PORT)
            cleanup.add_backend_server(backends[1], port=PORT)

        with allure_step_log("步骤16: 确认全部节点恢复运行中"):
            for backend in backends:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )

        with allure_step_log("步骤17: 内网VIP访问测试（恢复正常）"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=12
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} TCP 健康检查恢复后轮询验证",
            )

    def test_lb_tcp_acl_whitelist_internal(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener, clean_ip_group
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-访问控制-白名单场景（内网）")
        """验证访问控制白名单功能在内网场景下的生效与动态变更。"""
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        excluded = vm[1]
        backends = vm[2:4]
        lb_name = f"lb-tcp-acl-{random_data()}"
        pool_name = f"pool-{random_data()}"

        ip_group_name = f"ipg-{random_data()}"
        with allure_step_log("前置: 创建IP地址组（包含ecs0的IP）"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 创建TCP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员（ecs2、ecs3）"):
            vpc_page.lb_pool_add_vm(
                vm_names=[backend["name"] for backend in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 2}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤4: 配置访问控制（白名单）"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(
                lb_name,
                "access_control",
                enable=True,
                access_policy="白名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("白名单")

        with allure_step_log("步骤5: 白名单内客户端访问（ecs0）"):
            ssh_vm.connect(requester["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=3
            )
            assert any("this is ecs" in key for key in counter), f"ecs0访问失败: {dict(counter)}"

        with allure_step_log("步骤6: 白名单外客户端访问（ecs1）"):
            ssh_vm.connect(excluded["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html",
                check_rc=False, return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"ecs1应被拒绝，实际: {result['stdout']}"
            )

        with allure_step_log("步骤7: IP地址组添加ecs1的IP"):
            vpc_page.ip_group_add_ip_addresses(ip_group_name, [excluded["ip"]])
            vpc_page.assert_popup_success()
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert excluded["ip"] in actual_ips

        with allure_step_log("步骤8: ecs1再次访问成功"):
            ssh_vm.connect(excluded["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=3
            )
            assert any("this is ecs" in key for key in counter), f"ecs1访问失败: {dict(counter)}"

        with allure_step_log("步骤9: IP地址组删除ecs1的IP"):
            vpc_page.ip_group_delete_ip_addresses(ip_group_name, [excluded["ip"]])
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert excluded["ip"] not in actual_ips

        with allure_step_log("步骤10: ecs1再次访问失败"):
            ssh_vm.connect(excluded["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html",
                check_rc=False, return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip()

        with allure_step_log("步骤11: 修改为允许所有IP"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(lb_name, "access_control", enable=False)
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("允许所有IP访问")

        with allure_step_log("步骤12: 允许所有IP访问测试"):
            for vm_data in [requester, excluded]:
                ssh_vm.connect(vm_data["mfip"])
                counter = count_lb_responses(
                    ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=3
                )
                assert any("this is ecs" in key for key in counter), (
                    f"{vm_data['name']}访问失败: {dict(counter)}"
                )

    def test_lb_tcp_acl_whitelist_external(
        self, vpc_page, slb, vm, ssh_vm, ssh_host,
        clean_lb_listener, clean_ip_group,
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-访问控制-白名单场景-外网LB")
        """验证访问控制白名单功能在外网LB场景下的生效与动态变更。"""
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        backends = vm[2:4]
        lb_name = f"lb-tcp-acl-ext-{random_data()}"
        pool_name = f"pool-{random_data()}"

        ip_group_name = f"ipg-{random_data()}"
        with allure_step_log("前置: 创建IP地址组（包含ecs0的IP）"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 创建TCP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[backend["name"] for backend in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 2}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤4: 配置访问控制（白名单）"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(
                lb_name,
                "access_control",
                enable=True,
                access_policy="白名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("白名单")

        with allure_step_log("步骤5: 内网客户端访问成功"):
            ssh_vm.connect(requester["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=3
            )
            assert any("this is ecs" in key for key in counter), f"ecs0访问失败: {dict(counter)}"

        with allure_step_log("步骤6: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")

        with allure_step_log("步骤7: 外网客户端访问失败（白名单外）"):
            # wait_for_ping_reachable(ssh_host, eip)
            result = ssh_host.run(
                f"curl -s --connect-timeout 10 http://{eip}:{PORT}/index.html",
                check_rc=False, return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"应被拒绝，实际: {result['stdout']}"
            )

        with allure_step_log("步骤8: 识别并添加本机源IP"):
            host_ip_cmd = f"ip route get {eip} | grep -oP 'src \\K\\S+'"
            host_ip_result = ssh_host.run(
                host_ip_cmd, check_rc=False, return_rc=True,
            )
            route_src_ip = host_ip_result["stdout"].strip()

            assert route_src_ip, (
                f"未能通过 'ip route get {eip}' 识别 ssh_host 的源IP"
            )

            actual_ips = vpc_page.get_detail_ip_addresses()
            if route_src_ip not in actual_ips:
                vpc_page.ip_group_add_ip_addresses(ip_group_name, [route_src_ip])
                vpc_page.assert_popup_success()
                actual_ips = vpc_page.get_detail_ip_addresses()

            assert route_src_ip in actual_ips, (
                f"IP地址组未成功添加源IP {route_src_ip}，当前列表: {actual_ips}"
            )

            time.sleep(5)
            matched_host_ip = None
            for _ in range(3):
                counter = count_lb_responses(
                    ssh_host, f"http://{eip}:{PORT}/index.html", count=2
                )
                if any("this is ecs" in key for key in counter):
                    matched_host_ip = route_src_ip
                    break
                time.sleep(2)

            allure.attach(
                (
                    f"route_src_ip={route_src_ip}\n"
                    f"matched_host_ip={matched_host_ip or '<none>'}"
                ),
                name="外网源IP识别结果",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure_step_log("步骤9: 外网客户端访问成功"):
            if matched_host_ip:
                assert any("this is ecs" in key for key in counter), (
                    f"外网访问失败: {dict(counter)}"
                )
            else:
                raise AssertionError(
                    f"已将 ssh_host 源IP {route_src_ip} 加入白名单，但外网访问仍未恢复。"
                    f"last_counter={dict(counter)}。"
                    "更倾向于 ACL 放通未生效或公网链路存在产品侧问题。"
                )


@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
class TestLbV1TcpScenario(_BaseTestLbTcpScenario):
    SLB_VERSION = "V1"


@pytest.mark.parametrize("slb", [{"version": "V2"}], indirect=True)
class TestLbV2TcpScenario(_BaseTestLbTcpScenario):
    SLB_VERSION = "V2"
