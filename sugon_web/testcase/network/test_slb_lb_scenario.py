import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    is_http_reachable,
    prepare_http_backend,
    stop_http_backend,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


PORT = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V1场景验证")
class TestSlbV1LbScenario:
    """负载均衡（基础版）V1场景验证"""



    @allure.title("SLBV1-健康检查器成员离线禁用激活状态验证")
    def test_slbv1_health_check_disable_activate(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例405876：验证开启健康检查器时成员离线后再禁用，当成员上线后进行激活的状态"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤2: 创建监听器（开启健康检查）并添加资源池成员"):
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
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener(
                {"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name}
            )

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

        with allure_step_log("步骤3: 关闭ecs1、ecs2的web服务"):
            for backend in backends[:2]:
                stop_http_backend(ssh_vm, backend, port=PORT)
                # 验证端口确实已关闭
                ssh_vm.connect(backend["mfip"])
                port_check = ssh_vm.run(
                    f"ss -lntp | grep ':{PORT} '", check_rc=False, return_rc=True
                )
                assert port_check["rc"] != 0 or f":{PORT}" not in port_check["stdout"], (
                    f"后端 {backend['name']} 端口 {PORT} 未成功关闭"
                )

        with allure_step_log("步骤4: 验证成员离线状态"):
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="离线", timeout=600
                )
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], resource_status="运行中"
            )

        with allure_step_log("步骤5: 禁用ecs1、ecs2"):
            vpc_page.lb_pool_disable_vm(
                [b["name"] for b in backends[:2]], lb_name=lb_name, pool_name=pool_name
            )
            for backend in backends[:2]:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], switch_status="禁用"
                )
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], switch_status="激活"
            )

        with allure_step_log("步骤6: 重新启动ecs1、ecs2的web服务"):
            for i, backend in enumerate(backends[:2]):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)

        with allure_step_log("步骤7: 激活ecs1、ecs2"):
            vpc_page.lb_pool_activate_vm(
                [b["name"] for b in backends[:2]], lb_name=lb_name, pool_name=pool_name
            )
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], switch_status="激活"
                )

        with allure_step_log("步骤8: 等待ecs1、ecs2恢复运行中并验证VIP轮询"):
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120
                )
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html"
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 健康检查恢复后 VIP 轮询验证",
            )

    @allure.title("SLBV1-绑定解绑公网IP功能验证")
    def test_slbv1_eip_bind_unbind(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener
    ):
        """用例3509：负载均衡-绑定解绑公网IP功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

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

        with allure_step_log("步骤2: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤3: 内网VIP访问测试"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html"
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 内网 VIP 轮询验证",
            )

        with allure_step_log("步骤4: 绑定第一个公网IP"):
            available_eips = vpc_page.get_available_eips(slb["name"])
            if len(available_eips) < 2:
                pytest.skip(
                    f"环境问题：当前环境可用公网IP仅{len(available_eips)}个，"
                    f"不足2个，无法完成更换公网IP验证"
                )
            first_eip = vpc_page.slb_bind_eip_by_ip(slb["name"], available_eips[0])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == first_eip, f"绑定公网IP不一致: 期望{first_eip}, 实际{actual_eip}"

        with allure_step_log("步骤5: 通过第一个公网IP访问"):
            assert is_http_reachable(
                ssh_host, f"http://{first_eip}:{PORT}/index.html",
                timeout_sec=60, interval_sec=10, connect_timeout=5,
            ), f"公网IP {first_eip} 绑定成功但60秒内仍不可达，请检查EIP绑定状态或网络连通性"
            responses = collect_lb_http_responses(
                ssh_host,
                f"http://{first_eip}:{PORT}/index.html",
                count=30,
                interval_sec=1,
                connect_timeout=10,
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 公网IP1 轮询验证",
            )

        with allure_step_log("步骤6: 解绑公网IP"):
            vpc_page.slb_unbind_eip(slb["name"])
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip is None, f"解绑后不应还有公网IP，实际: {actual_eip}"

        with allure_step_log("步骤7: 验证解绑后无法访问"):
            result = ssh_host.run(
                f"curl -s --connect-timeout 10 http://{first_eip}:{PORT}/index.html",
                check_rc=False,
                return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"解绑后应无法访问，实际: {result['stdout']}"
            )

        with allure_step_log("步骤8: 绑定第二个公网IP"):
            second_eip = vpc_page.slb_bind_eip_by_ip(slb["name"], available_eips[1])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == second_eip, f"绑定公网IP不一致: 期望{second_eip}, 实际{actual_eip}"
            assert second_eip != first_eip, (
                f"第二次绑定应选择不同的公网IP，实际两次均为: {first_eip}"
            )

        with allure_step_log("步骤9: 通过第二个公网IP访问"):
            assert is_http_reachable(
                ssh_host, f"http://{second_eip}:{PORT}/index.html",
                timeout_sec=60, interval_sec=10, connect_timeout=5,
            ), f"公网IP {second_eip} 绑定成功但60秒内仍不可达，请检查EIP绑定状态或网络连通性"
            responses = collect_lb_http_responses(
                ssh_host,
                f"http://{second_eip}:{PORT}/index.html",
                count=30,
                interval_sec=1,
                connect_timeout=10,
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 公网IP2 轮询验证",
            )
