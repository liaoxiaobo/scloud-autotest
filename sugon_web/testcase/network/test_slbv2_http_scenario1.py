"""负载均衡V2-HTTP对等连接与转发规则及UDP监控验证。

对应需求：
- 用例436756：v2-lbv1 > 对等连接 > http结合转发规则
- 用例436993：v2-lb基础版 > lb监控 > 数据有效性验证 > 节点
"""
import re
import time

import allure
import pytest
from playwright.sync_api import expect

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._lb_peer_fixtures import (
    clean_peer_connect,
    lb_peer_vms,
    slbv2_in_vpc1,
)
from sugon_web.testcase.network._slb_helpers import (
    collect_lb_http_responses,
    count_lb_responses,
    prepare_http_backend,
    prepare_udp_backend,
    send_udp_message,
    stop_http_backend,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


PORT_HTTP = 7070
PORT_UDP = 5050
LISTENER_DESC = "1234567890edwqWDWQ中文~"


# ==============================================================================
# 场景1：v2-lbv1 > 对等连接 > http结合转发规则（用例436756）
# ==============================================================================
@pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V2-HTTP对等连接与转发规则")
class TestSlbV2HttpPeerForwardScenario:
    """用例436756：v2-lbv1 > 对等连接 > http结合转发规则"""

    @allure.title("SLB-V2-HTTP对等连接与转发规则验证")
    def test_slbv2_http_peer_forward(
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
        vpc2_backends = lb_peer_vms["vpc2"]  # ecs2-1, ecs2-2
        vpc2_client = vpc2_backends[1]  # ecs2-2

        slb_name = slbv2_in_vpc1
        lb_name = f"http-{random_data()}"
        pool_name_1 = f"pool-{random_data()}"
        pool_name_2 = f"pool-{random_data()}"
        peer_name = f"pc-{random_data()}"

        # 步骤1: 创建HTTP监听器并添加资源池成员
        with allure_step_log("步骤1: 创建HTTP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb_name,
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT_HTTP,
                desc=LISTENER_DESC,
                pool_name=pool_name_1,
                balance_method="加权轮询",
                health_check=True,
                health_type="HTTP",
                http_method="GET",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb_name,
                "lb_name": lb_name,
                "pool_name": pool_name_1,
            })

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in vpc1_backends],
                lb_name=lb_name,
                pool_name=pool_name_1,
                ports=PORT_HTTP,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in vpc1_backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT_HTTP, resource_status="运行中"
                )

        # 步骤2: 后端虚机启动web服务
        with allure_step_log("步骤2: 后端虚机启动web服务"):
            for backend in vpc1_backends:
                prepare_http_backend(ssh_vm, backend, backend["name"], port=PORT_HTTP)
                cleanup.add_backend_server(backend, port=PORT_HTTP)
            # ecs2-1也需要启动web服务（后续作为backend_2成员）
            prepare_http_backend(
                ssh_vm, vpc2_backends[0], vpc2_backends[0]["name"], port=PORT_HTTP
            )

        slb_vip = vpc_page.get_slb_vip(slb_name)

        # 步骤2后: 进入监听器详情页，确保后续页面操作状态正确
        with allure_step_log("步骤2后: 进入监听器详情页"):
            vpc_page.goto_slb_detail(slb_name, "监听器")

        # 步骤3: 验证跨VPC资源池成员不可见
        with allure_step_log("步骤3: 验证跨VPC资源池成员不可见"):
            candidate_names = vpc_page.get_lb_pool_candidate_vm_names(
                lb_name=lb_name, pool_name=pool_name_1
            )
            joined = "\n".join(candidate_names)
            assert vpc2_backends[0]["name"] not in joined, (
                f"跨VPC虚机 {vpc2_backends[0]['name']} 不应出现在可选列表中，"
                f"实际: {candidate_names}"
            )

        # 步骤4: 验证跨VPC无法直接访问
        with allure_step_log("步骤4: 验证跨VPC无法直接访问"):
            ssh_vm.connect(vpc2_client["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{slb_vip}:{PORT_HTTP}/index.html",
                check_rc=False,
                return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"对等连接前跨VPC访问应失败，"
                f"实际: rc={result['rc']}, stdout={result['stdout']}"
            )

        # 步骤5: 创建对等连接
        with allure_step_log("步骤5: 创建对等连接"):
            vpc_page.peer_connect_create(
                name=peer_name,
                requester_vpc=vpc1["name"],
                receiver_vpc=vpc2["name"],
            )
            vpc_page.assert_popup_success()
            peer_cleanup.add_peer_connect(peer_name)
            vpc_page.assert_list_contain(peer_name)
            row_data = vpc_page.get_row_data(peer_name)
            assert row_data["本端vpc"] == vpc1["name"], f"本端VPC断言失败: {row_data}"
            assert row_data["对端vpc"] == vpc2["name"], f"对端VPC断言失败: {row_data}"

        # 步骤6: 配置VPC1到VPC2的自定义路由
        with allure_step_log("步骤6: 配置VPC1到VPC2的自定义路由"):
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

        # 步骤7: 配置VPC2到VPC1的自定义路由
        with allure_step_log("步骤7: 配置VPC2到VPC1的自定义路由"):
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

        # 步骤8: 从backend_1删除ecs1-1
        with allure_step_log("步骤8: 从backend_1删除ecs1-1"):
            # 从VPC路由表页导航回监听器详情页，确保lb_pool_remove_vm的导航链正确
            vpc_page.goto_slb_detail(slb_name, "监听器")
            vpc_page.lb_pool_remove_vm(
                vm_names=[vpc1_backends[0]["name"]],
                lb_name=lb_name,
                pool_name=pool_name_1,
            )
            # lb_pool_remove_vm 内部已处理确认弹窗，此处无需额外断言

        # 步骤8后: 回到SLB列表页，确保后续页面操作状态正确
        with allure_step_log("步骤8后: 回到SLB列表页"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("负载均衡（基础版）")

        # 步骤9: 创建资源池backend_2
        with allure_step_log("步骤9: 创建资源池backend_2"):
            vpc_page.lb_pool_create(
                slb_name=slb_name,
                lb_name=lb_name,
                pool_name=pool_name_2,
                balance_method="源IP",
                session_persistence=False,
                health_check=True,
                health_type="HTTP",
                http_method="HEAD",
                url_path="/index.html",
            )
            vpc_page.assert_popup_success()
            # 登记非默认资源池以便 teardown 阶段清理
            cleanup.listeners[0]["extra_pools"] = [pool_name_2]

        # 步骤10: 为backend_2添加资源池成员
        with allure_step_log("步骤10: 为backend_2添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[vpc1_backends[0]["name"], vpc2_backends[0]["name"]],
                lb_name=lb_name,
                pool_name=pool_name_2,
                ports=PORT_HTTP,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in [vpc1_backends[0], vpc2_backends[0]]:
                # 成员刚添加时可能为"离线"，需等待健康检查变为"运行中"
                vpc_page.wait_lb_pool_member_status(
                    lb_name=lb_name,
                    pool_name=pool_name_2,
                    vm_name=backend["name"],
                    expected_status="运行中",
                    timeout=120,
                )

        # 步骤10后: 回到SLB列表页，确保后续页面操作状态正确
        with allure_step_log("步骤10后: 回到SLB列表页"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("负载均衡（基础版）")

        # 步骤11: 创建转发规则
        with allure_step_log("步骤11: 创建转发规则"):
            vpc_page.lb_forward_rule_create(
                slb_name=slb_name,
                lb_name=lb_name,
                rule_name="test_domain",
                condition_type="域名",
                judge_condition="精确匹配相等",
                condition_value="1example.com",
                forward_pool_name=pool_name_2,
            )
            vpc_page.assert_popup_success()
            # 验证转发规则出现在列表中
            vpc_page.goto_lb_detail(lb_name, tab_name="转发规则")
            rule_item = vpc_page.locator(".list-group-item-box").filter(
                has_text=re.compile(r"test_domain")
            ).first
            expect(rule_item).to_be_visible(timeout=5000)
            rule_text = rule_item.inner_text()
            assert "1example.com" in rule_text, f"转发规则条件值未显示: {rule_text}"
            assert pool_name_2 in rule_text, f"转发规则目标资源池未显示: {rule_text}"
            # 登记转发规则以便 teardown 阶段清理
            cleanup.listeners[0]["forward_rules"] = ["test_domain"]

        # 步骤12: 配置客户端hosts文件
        with allure_step_log("步骤12: 配置客户端hosts文件"):
            ssh_vm.connect(vpc2_client["mfip"])
            ssh_vm.run(
                f"echo '{slb_vip} 1example.com example.com1' >> /etc/hosts",
                check_rc=True,
            )
            result = ssh_vm.run("grep '1example.com' /etc/hosts", check_rc=True)
            assert "1example.com" in result, f"hosts文件配置失败: {result}"

        # 步骤13: 验证域名转发规则
        with allure_step_log("步骤13: 验证域名转发规则"):
            ssh_vm.connect(vpc2_client["mfip"])

            # 13.1: curl http://1example.com:7070 -> backend_2 (源IP算法)
            # 源IP算法下同一客户端固定到一台后端，所有响应应相同
            responses_1 = collect_lb_http_responses(
                ssh_vm, f"http://1example.com:{PORT_HTTP}", count=6
            )
            assert len(responses_1) == 6, f"请求次数不足: {len(responses_1)}"
            assert all("this is ecs" in r for r in responses_1), (
                f"1example.com访问失败: {responses_1}"
            )
            # 验证源IP固定：所有响应内容应完全一致
            unique_responses = set(r.strip() for r in responses_1)
            assert len(unique_responses) == 1, (
                f"源IP算法应固定到同一后端，实际响应不一致: {unique_responses}"
            )

            # 13.2: curl http://example.com1:7070 -> backend_1 (默认，仅剩ecs1-2)
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://example.com1:{PORT_HTTP}/index.html",
                check_rc=False,
                return_rc=True,
            )
            stdout = (result.get("stdout") or "").strip()
            # backend_1仅剩ecs1-2，应返回ecs1-2的标识
            expected_backend = vpc1_backends[1]["name"]  # ecs1-2
            assert expected_backend in stdout, (
                f"example.com1应返回backend_1的唯一成员 {expected_backend}, "
                f"实际: {stdout}"
            )


# ==============================================================================
# 场景2：v2-lb基础版 > lb监控 > 数据有效性验证 > 节点（用例436993）
# ==============================================================================
@pytest.mark.parametrize("vm", [{"basic": {"count": 3}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V2"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V2-UDP监听器监控验证")
class TestSlbV2UdpMonitorScenario:
    """用例436993：v2-lb基础版 > lb监控 > 数据有效性验证 > 节点"""

    @allure.title("SLB-V2-UDP监听器监控数据验证")
    def test_slbv2_udp_monitor(
        self, page, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        cleanup = clean_lb_listener
        requester = vm[0]  # ecs0
        backends = vm[1:3]  # ecs1, ecs2

        lb_name = f"udp-{random_data()}"
        pool_name = f"pool-{random_data()}"

        # 步骤1: 创建UDP监听器并添加资源池成员
        with allure_step_log("步骤1: 创建UDP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_name,
                protocol="UDP",
                port=PORT_UDP,
                desc=LISTENER_DESC,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb,
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT_UDP,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT_UDP, resource_status="运行中"
                )

        # 步骤2: 后端虚机启动UDP服务
        with allure_step_log("步骤2: 后端虚机启动UDP服务"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=PORT_UDP)
                cleanup.add_backend_server(
                    backend, port=PORT_UDP, kill_pattern=f"UDP_server.py.*{PORT_UDP}"
                )

        lb_vip = vpc_page.get_slb_vip(slb)
        slb_uuid = vpc_page.get_slb_uuid(slb)
        project_id = vpc_page.get_slb_project_id(slb)

        # 步骤3: 验证UDP连通性
        with allure_step_log("步骤3: 验证UDP连通性"):
            ssh_vm.connect(requester["mfip"])
            # 使用内联Python发送UDP消息验证连通性
            result = send_udp_message(ssh_vm, lb_vip, PORT_UDP, "test_msg")
            assert result["rc"] == 0, f"UDP连通性验证失败: {result}"

        # 步骤4: 进入CMS监控服务的负载均衡详情页
        with allure_step_log("步骤4: 进入CMS监控服务的负载均衡详情页"):
            from sugon_web.pages.cms import CmsPage
            cms_page = CmsPage(page)
            cms_page.goto_submenu("负载均衡（基础版）")
            cms_page.click_slb_in_list(slb, slb_uuid=slb_uuid)
            cms_page.wait_for_page_ready()
            cms_page.page.wait_for_timeout(3000)
            cms_page.select_time_range("实时")

        # 步骤5: 发送UDP流量（1分钟）
        with allure_step_log("步骤5: 发送UDP流量（1分钟）"):
            ssh_vm.connect(requester["mfip"])
            start_time = time.time()
            msg_count = 0
            while time.time() - start_time < 60:
                send_udp_message(ssh_vm, lb_vip, PORT_UDP, f"msg_{msg_count}")
                msg_count += 1
                time.sleep(1)

        # 步骤6: 查看实例级别监控曲线（运维监控）
        with allure_step_log("步骤6: 查看实例级别监控曲线（运维监控）"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 步骤7: 查看监听器级别监控曲线（运维监控）
        with allure_step_log("步骤7: 查看监听器级别监控曲线（运维监控）"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量并验证数据不为零
        with allure_step_log("补充流量数据并等待监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                send_udp_message(ssh_vm, lb_vip, PORT_UDP, "burst_msg")
                time.sleep(1)
            time.sleep(15)

        with allure_step_log("验证CMS实例监控数据不为零"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证CMS监听器监控数据不为零"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        # 步骤8: 验证流量停止后监控归零
        with allure_step_log("步骤8: 验证流量停止后监控归零"):
            # 停止发送流量，等待150秒让监控数据充分回落
            # 实时模式下监控数据每10秒刷新，且有1~2分钟聚合窗口，
            # 需要足够时间让历史聚合值被清空
            time.sleep(150)
            # 验证实例级别监控数据已显著回落
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)
            cms_page.assert_monitor_data_zero(wait_sec=20, tolerance=60)
            # 验证监听器级别监控数据已显著回落
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)
            cms_page.assert_monitor_data_zero(wait_sec=20, tolerance=60)

        # 步骤9: 查看实例级别监控曲线（网络服务）
        with allure_step_log("步骤9: 查看实例级别监控曲线（网络服务）"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.click_action(slb, "查看监控")
            vpc_page.select_time_range("实时")
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # 步骤10: 查看监听器级别监控曲线（网络服务）
        with allure_step_log("步骤10: 查看监听器级别监控曲线（网络服务）"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_charts_visible(min_charts=1)
