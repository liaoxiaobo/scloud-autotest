import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_ip_group, clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    count_lb_responses,
    get_ssh_host_source_ip,
    prepare_http_backend,
    stop_http_backend,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


PORT = 7070


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监听器场景验证")
class _BaseTestLbHttpScenario:
    """负载均衡 HTTP 监听器场景验证基类"""

    SLB_VERSION = ""
    def _lb_http_acl_whitelist_internal(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener, clean_ip_group
    ):
        allure.dynamic.title("v2-访问控制-白名单场景-内网LB")
        """验证访问控制白名单功能在内网场景下的生效与动态变更。"""
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        excluded = vm[1]
        backends = vm[2:4]
        lb_name = f"lb-http-acl-{random_data()}"
        pool_name = f"pool-{random_data()}"

        ip_group_name = f"ipg-{random_data()}"
        with allure_step_log("前置: 创建IP地址组（包含ecs0的IP）"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 创建HTTP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
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
            stdout = (result.get("stdout") or "").strip()
            is_rejected = result["rc"] != 0 or not stdout or "Forbidden" in stdout
            assert is_rejected, f"ecs1应被拒绝，实际: {stdout[:200]}"

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
            stdout = (result.get("stdout") or "").strip()
            is_rejected = result["rc"] != 0 or not stdout or "Forbidden" in stdout
            assert is_rejected, f"ecs1应被拒绝，实际: {stdout[:200]}"

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
    def _lb_http_acl_whitelist_external(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener, clean_ip_group
    ):
        allure.dynamic.title("v2-访问控制-白名单场景-外网LB")
        """验证访问控制白名单功能在外网LB场景下的生效与动态变更。"""
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        backends = vm[2:4]
        lb_name = f"lb-http-acl-ext-{random_data()}"
        pool_name = f"pool-{random_data()}"

        ip_group_name = f"ipg-{random_data()}"
        with allure_step_log("前置: 创建IP地址组（包含ecs0的IP）"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 创建HTTP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
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

        with allure_step_log("步骤6: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")

        with allure_step_log("步骤7: 外网客户端访问失败（白名单外）"):
            result = ssh_host.run(
                f"curl -s --connect-timeout 10 http://{eip}:{PORT}/index.html",
                check_rc=False, return_rc=True,
            )
            stdout = result["stdout"].strip()
            is_rejected = result["rc"] != 0 or not stdout or "Forbidden" in stdout
            assert is_rejected, f"应被拒绝，实际: {stdout}"

        with allure_step_log("步骤8: 识别并添加本机源IP"):
            host_ips = get_ssh_host_source_ip(ssh_host, eip)
            assert host_ips, "无法识别 ssh_host 访问 EIP 的源 IP"
            host_ip = host_ips[0]
            vpc_page.ip_group_add_ip_addresses(ip_group_name, [host_ip])
            vpc_page.assert_popup_success()
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert host_ip in actual_ips, f"IP地址组未成功添加源IP {host_ip}"
            time.sleep(2)
            counter = count_lb_responses(
                ssh_host, f"http://{eip}:{PORT}/index.html", count=3
            )
            matched_host_ip = None
            if any("this is ecs" in key for key in counter):
                matched_host_ip = host_ip

        with allure_step_log("步骤9: 外网客户端访问成功"):
            assert matched_host_ip, (
                f"已将 ssh_host 源IP {host_ip} 加入白名单，但外网访问仍未恢复。"
                f"counter={dict(counter)}。"
            )
            assert any("this is ecs" in key for key in counter), (
                f"外网访问失败: {dict(counter)}"
            )


    def test_lb_http_weighted_round_robin(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener
    ):
        allure.dynamic.title(
            f"{self.SLB_VERSION.lower()}-新建监听器-HTTP+加权轮询基本功能验证"
        )
        """验证 HTTP 监听器创建、资源池成员添加、加权轮询算法及公网访问。"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        weights = {"ecs1": 1, "ecs2": 2, "ecs3": 2}

        with allure_step_log("步骤1: 创建HTTP监听器（加权轮询）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员（权重1:2:2）"):
            vm_weights = {backends[i]["name"]: weights[f"ecs{i + 1}"] for i in range(len(backends))}
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
                weights=vm_weights,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=PORT)

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤4: 内网VIP访问测试"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=20
            )
            assert_lb_algorithm(
                "weighted_round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} HTTP 内网VIP 加权轮询验证",
                weights={k: v for k, v in weights.items()},
            )

        with allure_step_log("步骤5: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == eip, f"绑定公网IP不一致: 期望{eip}, 实际{actual_eip}"

        with allure_step_log("步骤6: 公网IP访问测试"):
            time.sleep(10)
            responses = collect_lb_http_responses(
                ssh_host, f"http://{eip}:{PORT}/index.html", count=20
            )
            assert_lb_algorithm(
                "weighted_round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} HTTP 公网EIP 加权轮询验证",
                weights={k: v for k, v in weights.items()},
            )

        if self.SLB_VERSION == "V2":
            with allure_step_log("步骤7: 检查pod数量"):
                lb_uuid = vpc_page.get_slb_uuid(slb["name"])
                pod_count = 0
                for i in range(12):
                    result = ssh_host.run(
                        f"sudo kubectl get pods -A | grep {lb_uuid} | wc -l",
                        check_rc=False,
                        return_rc=True,
                    )
                    pod_count = int(result["stdout"].strip()) if result["rc"] == 0 else 0
                    if pod_count >= 1:
                        break
                    time.sleep(5)
                assert pod_count == 1, f"预期有1个pod，实际有{pod_count}个"

    def test_lb_http_health_check(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title(
            f"{self.SLB_VERSION.lower()}-健康检查器-HTTP基本功能验证"
        )
        """验证 HTTP 健康检查的开启、关闭及状态变化对流量分发的影响。"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-http-hc-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        weights = {"ecs1": 1, "ecs2": 2, "ecs3": 2}

        with allure_step_log("步骤1: 创建HTTP监听器（开启健康检查）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=True,
                health_type="HTTP",
                http_method="GET",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员（权重1:2:2）"):
            vm_weights = {backends[i]["name"]: weights[f"ecs{i + 1}"] for i in range(len(backends))}
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
                weights=vm_weights,
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

        with allure_step_log("步骤11: 停止ecs1和ecs2的web服务"):
            stop_http_backend(ssh_vm, backends[0], port=PORT)
            stop_http_backend(ssh_vm, backends[1], port=PORT)

        with allure_step_log("步骤12: 确认健康状态不变（关闭健康检查）"):
            time.sleep(5)
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], resource_status="运行中"
                )

        with allure_step_log("步骤13: 内网VIP访问测试（关闭健康检查）"):
            ssh_vm.connect(requester["mfip"])
            counter = count_lb_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=12
            )
            assert counter.get("this is ecs3", 0) > 0, f"期望ecs3响应，实际: {dict(counter)}"

        with allure_step_log("步骤14: 确认健康检查为关闭状态"):
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            vpc_page.assert_lb_pool_basic_info(pool_name, health_check="未开启")

        with allure_step_log("步骤15: 重新开启健康检查"):
            vpc_page.lb_pool_config_health_check(
                lb_name, pool_name, enable=True, health_type="HTTP",
                http_method="GET", url_path="/index.html",
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

        with allure_step_log("步骤16: 再次恢复ecs1和ecs2的web服务"):
            prepare_http_backend(ssh_vm, backends[0], "ecs1", port=PORT)
            prepare_http_backend(ssh_vm, backends[1], "ecs2", port=PORT)
            cleanup.add_backend_server(backends[0], port=PORT)
            cleanup.add_backend_server(backends[1], port=PORT)

        with allure_step_log("步骤17: 确认全部节点恢复运行中"):
            for backend in backends:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )

        with allure_step_log("步骤18: 内网VIP访问测试（恢复正常）"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=20
            )
            assert_lb_algorithm(
                "weighted_round_robin",
                responses,
                backend_markers,
                f"{self.SLB_VERSION} HTTP 健康检查恢复后加权轮询验证",
                weights={k: v for k, v in weights.items()},
            )

    def test_slb_http_forward_url_path(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title(
            f"{self.SLB_VERSION}-HTTP转发规则-URL路径条件验证"
        )
        """用例436766：转发规则-URL路径条件验证"""
        cleanup = clean_lb_listener
        vm1 = vm[0]
        vm2 = vm[1]
        vm3 = vm[2]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        forward_pool_name = f"fwd-pool-{random_data()}"
        rule1_name = f"rule-{random_data()}"
        rule2_name = f"rule-{random_data()}"

        with allure_step_log("步骤1: 创建HTTP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
                "extra_pools": [forward_pool_name],
                "forward_rules": [rule1_name, rule2_name],
            })

        with allure_step_log("步骤2: 添加默认资源池成员vm1"):
            vpc_page.lb_pool_add_vm(
                vm_names=[vm1["name"]],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            vpc_page.assert_lb_pool_member_info(vm1["name"], port=PORT)

        with allure_step_log("步骤3: 创建转发目标资源池backend_2"):
            vpc_page.lb_pool_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="HTTP",
                http_method="HEAD",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤4: 添加backend_2成员vm2"):
            vpc_page.lb_pool_add_vm(
                vm_names=[vm2["name"]],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")

        with allure_step_log("步骤5: 创建转发规则rule_1（URL路径包含111→backend_1）"):
            vpc_page.lb_forward_rule_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                rule_name=rule1_name,
                condition_type="URL路径",
                judge_condition="包含（区分大小写）",
                condition_value="111",
                forward_pool_name=pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤6: 创建转发规则rule_2（URL路径包含222→backend_2）"):
            vpc_page.lb_forward_rule_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                rule_name=rule2_name,
                condition_type="URL路径",
                judge_condition="包含（区分大小写）",
                condition_value="222",
                forward_pool_name=forward_pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤7: 配置vm1后端服务"):
            prepare_http_backend(ssh_vm, vm1, "vm1", port=PORT)
            cleanup.add_backend_server(vm1, port=PORT)
            ssh_vm.connect(vm1["mfip"])
            workdir = f"/root/slb-http-vm1-{PORT}"
            ssh_vm.run(
                f"cp {workdir}/index.html {workdir}/index111.html",
                check_rc=True,
            )

        with allure_step_log("步骤8: 配置vm2后端服务"):
            prepare_http_backend(ssh_vm, vm2, "vm2", port=PORT)
            cleanup.add_backend_server(vm2, port=PORT)
            ssh_vm.connect(vm2["mfip"])
            workdir = f"/root/slb-http-vm2-{PORT}"
            ssh_vm.run(
                f"cp {workdir}/index.html {workdir}/index222.html",
                check_rc=True,
            )

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤9: vm3验证转发规则生效"):
            ssh_vm.connect(vm3["mfip"])
            time.sleep(5)

            resp_default = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html",
                check_rc=False,
            ).strip()
            assert resp_default == "this is vm1", (
                f"默认路径应返回vm1内容，实际: {resp_default}"
            )

            resp_rule1 = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index111.html",
                check_rc=False,
            ).strip()
            assert resp_rule1 == "this is vm1", (
                f"rule_1应转发至backend_1(vm1)，实际: {resp_rule1}"
            )

            resp_rule2 = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index222.html",
                check_rc=False,
            ).strip()
            assert resp_rule2 == "this is vm2", (
                f"rule_2应转发至backend_2(vm2)，实际: {resp_rule2}"
            )

    def test_slb_http_forward_domain(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title(
            f"{self.SLB_VERSION}-HTTP转发规则-域名条件验证"
        )
        """用例436767：转发规则-域名条件验证"""
        cleanup = clean_lb_listener
        vm1 = vm[0]
        vm2 = vm[1]
        vm3 = vm[2]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        forward_pool_name = f"fwd-pool-{random_data()}"
        rule_name = f"rule-{random_data()}"

        with allure_step_log("步骤1: 创建HTTP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
                "extra_pools": [forward_pool_name],
                "forward_rules": [rule_name],
            })

        with allure_step_log("步骤2: 添加默认资源池成员vm1"):
            vpc_page.lb_pool_add_vm(
                vm_names=[vm1["name"]],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            vpc_page.assert_lb_pool_member_info(vm1["name"], port=PORT)

        with allure_step_log("步骤3: 创建转发目标资源池backend_2"):
            vpc_page.lb_pool_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="HTTP",
                http_method="HEAD",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤4: 添加backend_2成员vm2"):
            vpc_page.lb_pool_add_vm(
                vm_names=[vm2["name"]],
                lb_name=lb_name,
                pool_name=forward_pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")

        with allure_step_log("步骤5: 创建转发规则rule_1（域名精确匹配→backend_2）"):
            vpc_page.lb_forward_rule_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                rule_name=rule_name,
                condition_type="域名",
                judge_condition="精确匹配相等",
                condition_value="1example.com",
                forward_pool_name=forward_pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤6: 配置vm1后端服务"):
            prepare_http_backend(ssh_vm, vm1, "vm1", port=PORT)
            cleanup.add_backend_server(vm1, port=PORT)

        with allure_step_log("步骤7: 配置vm2后端服务"):
            prepare_http_backend(ssh_vm, vm2, "vm2", port=PORT)
            cleanup.add_backend_server(vm2, port=PORT)

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤8: vm3验证域名转发规则生效"):
            ssh_vm.connect(vm3["mfip"])

            ssh_vm.run(
                f'echo "{lb_vip} 1example.com example.com1" >> /etc/hosts',
                check_rc=True,
            )
            time.sleep(5)

            resp_match = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://1example.com:{PORT}",
                check_rc=False,
            ).strip()
            assert resp_match == "this is vm2", (
                f"域名1example.com应匹配rule_1转发至backend_2(vm2)，实际: {resp_match}"
            )

            resp_no_match = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://example.com1:{PORT}",
                check_rc=False,
            ).strip()
            assert resp_no_match == "this is vm1", (
                f"域名example.com1不匹配rule_1应走默认backend_1(vm1)，实际: {resp_no_match}"
            )



@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
class TestSlbV1HttpScenario(_BaseTestLbHttpScenario):
    SLB_VERSION = "V1"


@pytest.mark.parametrize("slb", [{"version": "V2", "ha_enable": True}], indirect=True)
class TestSlbV2HttpScenario(_BaseTestLbHttpScenario):
    SLB_VERSION = "V2"
    test_lb_http_acl_whitelist_external = _BaseTestLbHttpScenario._lb_http_acl_whitelist_external
    test_lb_http_acl_whitelist_internal = _BaseTestLbHttpScenario._lb_http_acl_whitelist_internal
