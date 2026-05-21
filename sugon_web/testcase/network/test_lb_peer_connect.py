"""跨 VPC 对等连接 + 负载均衡（基础版 V2）正向场景验证。

对应需求：`sugon_web/case_specs/network/lb_peer.md`（用例编号 418861）。
"""
import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._lb_peer_fixtures import (
    clean_peer_connect,
    lb_peer_vms,
    slbv2_in_vpc1,
)
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    prepare_http_backend,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


PORT = 8080
LISTENER_DESC = "1234567890edwqWDWQ中文~"


@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("对等连接跨VPC场景")
@pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
class TestLbPeerConnectScenario:
    """LB > 对等连接 > 正向基本功能验证（用例编号 418861）。"""

    @allure.title("LBv2-对等连接-跨VPC负载均衡可达性验证")
    def test_lb_peer_connect_cross_vpc(
        self,
        vpc,
        vpc_page,
        lb_peer_vms,
        slbv2_in_vpc1,
        ssh_vm,
        clean_lb_listener,
        clean_peer_connect,
    ):
        cleanup = clean_lb_listener
        peer_cleanup = clean_peer_connect
        vpc1, vpc2 = vpc[0], vpc[1]
        vpc1_backends = lb_peer_vms["vpc1"]  # ecs1-1, ecs1-2
        vpc2_real_server = lb_peer_vms["vpc2"][0]  # ecs2-1
        vpc2_client = lb_peer_vms["vpc2"][1]  # ecs2-2

        slb_name = slbv2_in_vpc1
        lb_name = f"tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        peer_name = f"pc-{random_data()}"

        backend_markers = {
            vpc1_backends[0]["name"]: f"this is {vpc1_backends[0]['name']}",
            vpc1_backends[1]["name"]: f"this is {vpc1_backends[1]['name']}",
            vpc2_real_server["name"]: f"this is {vpc2_real_server['name']}",
        }

        with allure_step_log("步骤1: 创建TCP监听器并将vpc1的虚机加入资源池"):
            vpc_page.slb_lb_create(
                slb_name=slb_name,
                lb_name=lb_name,
                protocol="TCP",
                port=PORT,
                desc=LISTENER_DESC,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="TCP",
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb_name, "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[backend["name"] for backend in vpc1_backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in vpc1_backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤2: 对等连接前，ecs2-1不应出现在资源池可选列表中"):
            candidate_text = vpc_page.get_lb_pool_candidate_vm_names(
                lb_name=lb_name, pool_name=pool_name
            )
            joined_candidates = "\n".join(candidate_text)
            assert vpc2_real_server["name"] not in joined_candidates, (
                f"对等连接前，跨VPC虚机 {vpc2_real_server['name']} 不应可选，"
                f"但实际出现在: {candidate_text}"
            )

        with allure_step_log("步骤3: 后端启动HTTP服务（仅vpc1的两台虚机）"):
            for backend in vpc1_backends:
                prepare_http_backend(ssh_vm, backend, backend["name"], port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        slb_vip = vpc_page.get_slb_vip(slb_name)

        with allure_step_log("步骤4: 对等连接前，ecs2-2跨VPC访问VIP应失败"):
            ssh_vm.connect(vpc2_client["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{slb_vip}:{PORT}/index.html",
                check_rc=False,
                return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"对等连接前 ecs2-2 跨VPC访问应失败，"
                f"实际返回: rc={result['rc']}, stdout={result['stdout']}"
            )

        with allure_step_log("步骤5: 创建对等连接 (vpc1 ↔ vpc2)"):
            vpc_page.peer_connect_create(
                name=peer_name,
                requester_vpc=vpc1["name"],
                receiver_vpc=vpc2["name"],
                desc="对等连接跨VPC负载均衡自动化测试",
            )
            vpc_page.assert_popup_success()
            peer_cleanup.add_peer_connect(peer_name)
            vpc_page.assert_list_contain(peer_name)
            row_data = vpc_page.get_row_data(peer_name)
            assert row_data["本端vpc"] == vpc1["name"], f"本端VPC断言失败: {row_data}"
            assert row_data["对端vpc"] == vpc2["name"], f"对端VPC断言失败: {row_data}"

        with allure_step_log("步骤6: 在vpc1路由表添加到vpc2的自定义路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc1["name"],
                dest_cidr=vpc2["cidr"],
                next_hop=peer_name,
                next_hop_type="对等连接",
                ip_version="IPv4",
            )
            vpc_page.assert_popup_success()
            peer_cleanup.add_route_rule(vpc1["name"], vpc2["cidr"])
            vpc_page.assert_list_contain(vpc2["cidr"], column_name="目的地址")

        with allure_step_log("步骤7: 在vpc2路由表添加到vpc1的自定义路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc2["name"],
                dest_cidr=vpc1["cidr"],
                next_hop=peer_name,
                next_hop_type="对等连接",
                ip_version="IPv4",
            )
            vpc_page.assert_popup_success()
            peer_cleanup.add_route_rule(vpc2["name"], vpc1["cidr"])
            vpc_page.assert_list_contain(vpc1["cidr"], column_name="目的地址")

        with allure_step_log("步骤8: 对等连接生效后，将ecs2-1加入资源池作为Real-Server"):
            time.sleep(10)
            vpc_page.goto_slb_detail(slb_name, "监听器")
            vpc_page.lb_pool_add_vm(
                vm_names=[vpc2_real_server["name"]],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")
            vpc_page.assert_lb_pool_member_info(
                vpc2_real_server["name"], port=PORT
            )

            prepare_http_backend(ssh_vm, vpc2_real_server, vpc2_real_server["name"], port=PORT)
            cleanup.add_backend_server(vpc2_real_server, port=PORT)

        with allure_step_log("步骤9: ecs2-2跨VPC ping ecs1-2 应可达"):
            ssh_vm.connect(vpc2_client["mfip"])
            ssh_vm.ping(vpc1_backends[1]["ip"], connected=True, count=4, retries=5, retry_delay=5)

        with allure_step_log("步骤10: ecs2-2跨VPC访问VIP应成功并命中多个后端"):
            vpc_page.wait_lb_pool_member_status(
                lb_name, pool_name, vpc2_real_server["name"],
                expected_status="运行中", timeout=120,
            )
            ssh_vm.connect(vpc2_client["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{slb_vip}:{PORT}/index.html", count=12
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "LBv2 跨VPC 轮询验证",
                tolerance=0.25,
            )
