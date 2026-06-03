"""负载均衡（基础版）V1 - 监听器监控功能验证。

三个场景共享同一套测试资源（vpc、4台vm、slbv1），每个方法独立创建/清理监听器，
通过 class-scoped fixture 复用 VM 和 SLB 资源。

包含三个场景的测试：
- 用例414240：L7LB-HTTP监听器监控正向功能验证
- 用例414218：L4LB-TCP监听器监控正向功能验证
- 用例421567：L4LB-UDP监听器监控正向功能验证
"""

import allure
import pytest
import time

from sugon_web.pages.cms import CmsPage
from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_udp_recipients,
    prepare_http_backend,
    prepare_udp_backend,
    send_udp_message,
)
from sugon_web.utils.logger import allure_step_log


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1", "ha_enable": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监控功能验证")
class TestSlbv1Monitor:
    """负载均衡（基础版）V1 - 监听器监控功能验证

    三个测试方法共享 class-scoped 的 vm（4台虚机）和 slb（V1+HA）资源，
    每个方法通过 clean_lb_listener 独立清理自己的监听器。
    """

    @allure.title("SLB-HTTP监听器监控功能验证")
    def test_slbv1_http_monitor(self, page, vpc_page, slb, vm, ssh_vm, clean_lb_listener):
        """用例414240：lb基础版 > lb监控 > L7LB > http监听器正向功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = "http_7070"
        pool_name = "backend_1"
        port = 7070

        # --------------------------------------------------------------
        # 步骤1: 创建HTTP监听器并添加资源池成员
        # --------------------------------------------------------------
        with allure_step_log("步骤1: 创建HTTP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=port,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=port,
                weights=[1, 2, 2],
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=port)

        # --------------------------------------------------------------
        # 步骤2: 后端虚机启动web服务
        # --------------------------------------------------------------
        with allure_step_log("步骤2: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=port)
                cleanup.add_backend_server(backend, port=port)

        # 在离开VPC页面前获取所需信息
        slb_uuid = vpc_page.get_slb_uuid(slb["name"])
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        # --------------------------------------------------------------
        # 步骤3: 进入SLB监控详情页（network模块）
        # --------------------------------------------------------------
        with allure_step_log("步骤3: 进入SLB监控详情页"):
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.click_action(slb["name"], "查看监控")
            vpc_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤4: VIP访问测试（生成流量数据，验证加权轮询）
        # --------------------------------------------------------------
        with allure_step_log("步骤4: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = []
            for _ in range(15):
                response = ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                responses.append(response)
                time.sleep(1)

        with allure_step_log("验证加权轮询分布"):
            backend_markers = {
                "ecs1": "this is ecs1",
                "ecs2": "this is ecs2",
                "ecs3": "this is ecs3",
            }
            assert_lb_algorithm(
                "weighted_round_robin",
                responses,
                backend_markers,
                scene_name="HTTP加权轮询",
                weights={"ecs1": 1, "ecs2": 2, "ecs3": 2},
                tolerance=0.15,
            )

        # --------------------------------------------------------------
        # 步骤5: 实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤5: 实例级别监控验证"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤6: 监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤6: 监听器级别监控验证"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并等待监控数据刷新
        with allure_step_log("补充流量数据并等待监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            time.sleep(15)

        # 验证监控数据不为零
        with allure_step_log("验证实例监控数据不为零"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证监听器监控数据不为零"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        # --------------------------------------------------------------
        # 步骤7: 进入CMS监控服务的负载均衡详情页
        # --------------------------------------------------------------
        with allure_step_log("步骤7: 进入CMS监控服务的负载均衡详情页"):
            cms_page = CmsPage(page)
            cms_page.goto_submenu("负载均衡（基础版）")
            cms_page.click_slb_in_list(slb["name"], slb_uuid=slb_uuid)
            cms_page.wait_for_page_ready()
            cms_page.page.wait_for_timeout(3000)
            cms_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤8: VIP访问测试（生成流量数据）
        # --------------------------------------------------------------
        with allure_step_log("步骤8: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(10):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)

        # --------------------------------------------------------------
        # 步骤9: CMS监控-实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤9: CMS监控-实例级别监控验证"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤10: CMS监控-监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤10: CMS监控-监听器级别监控验证"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并验证CMS监控数据不为零
        with allure_step_log("补充流量数据并等待CMS监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            time.sleep(15)

        with allure_step_log("验证CMS实例监控数据不为零"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证CMS监听器监控数据不为零"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

    @allure.title("SLB-TCP监听器监控功能验证")
    def test_slbv1_tcp_monitor(self, page, vpc_page, slb, vm, ssh_vm, clean_lb_listener):
        """用例414218：lb基础版 > lb监控 > L4LB > tcp监听器正向功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = "tcp_8080"
        pool_name = "backend_1"
        port = 8080

        # --------------------------------------------------------------
        # 步骤1: 创建TCP监听器并添加资源池成员
        # --------------------------------------------------------------
        with allure_step_log("步骤1: 创建TCP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=port,
                desc="1234567890edwqWDWQ中文~",
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
                ports=port,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=port)

        # --------------------------------------------------------------
        # 步骤2: 后端虚机启动web服务
        # --------------------------------------------------------------
        with allure_step_log("步骤2: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=port)
                cleanup.add_backend_server(backend, port=port)

        # 在离开VPC页面前获取所需信息
        slb_uuid = vpc_page.get_slb_uuid(slb["name"])
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        # --------------------------------------------------------------
        # 步骤3: 进入SLB监控详情页（network模块）
        # --------------------------------------------------------------
        with allure_step_log("步骤3: 进入SLB监控详情页"):
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.click_action(slb["name"], "查看监控")
            vpc_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤4: VIP访问测试（生成流量数据，验证轮询）
        # --------------------------------------------------------------
        with allure_step_log("步骤4: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            responses = []
            for _ in range(15):
                response = ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                responses.append(response)
                time.sleep(1)

        with allure_step_log("验证轮询分布"):
            backend_markers = {
                "ecs1": "this is ecs1",
                "ecs2": "this is ecs2",
                "ecs3": "this is ecs3",
            }
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                scene_name="TCP轮询",
                tolerance=0.15,
            )

        # --------------------------------------------------------------
        # 步骤5: 实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤5: 实例级别监控验证"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤6: 监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤6: 监听器级别监控验证"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并等待监控数据刷新
        with allure_step_log("补充流量数据并等待监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            time.sleep(15)

        # 验证监控数据不为零
        with allure_step_log("验证实例监控数据不为零"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证监听器监控数据不为零"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        # --------------------------------------------------------------
        # 步骤7: 进入CMS监控服务的负载均衡详情页
        # --------------------------------------------------------------
        with allure_step_log("步骤7: 进入CMS监控服务的负载均衡详情页"):
            cms_page = CmsPage(page)
            cms_page.goto_submenu("负载均衡（基础版）")
            cms_page.click_slb_in_list(slb["name"], slb_uuid=slb_uuid)
            cms_page.wait_for_page_ready()
            cms_page.page.wait_for_timeout(3000)
            cms_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤8: VIP访问测试（生成流量数据）
        # --------------------------------------------------------------
        with allure_step_log("步骤8: VIP访问测试生成流量数据"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(10):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)

        # --------------------------------------------------------------
        # 步骤9: CMS监控-实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤9: CMS监控-实例级别监控验证"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤10: CMS监控-监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤10: CMS监控-监听器级别监控验证"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并验证CMS监控数据不为零
        with allure_step_log("补充流量数据并等待CMS监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(20):
                ssh_vm.run(
                    f"curl -s --connect-timeout 5 http://{lb_vip}:{port}/index.html",
                    check_rc=False,
                )
                time.sleep(1)
            time.sleep(15)

        with allure_step_log("验证CMS实例监控数据不为零"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证CMS监听器监控数据不为零"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

    @allure.title("SLB-UDP监听器监控功能验证")
    def test_slbv1_udp_monitor(self, page, vpc_page, slb, vm, ssh_vm, clean_lb_listener):
        """用例421567：lb基础版 > lb监控 > L4LB > udp监听器正向功能验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = "udp_5050"
        pool_name = "backend_1"
        port = 5050

        # --------------------------------------------------------------
        # 步骤1: 创建UDP监听器并添加资源池成员
        # --------------------------------------------------------------
        with allure_step_log("步骤1: 创建UDP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="UDP",
                port=port,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="源IP",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=port,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(backend["name"], port=port)

        # --------------------------------------------------------------
        # 步骤2: 后端虚机启动UDP服务
        # --------------------------------------------------------------
        with allure_step_log("步骤2: 后端虚机启动UDP服务"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=port)
                cleanup.add_backend_server(
                    backend, port=port, kill_pattern=f"UDP_server.py.*{port}"
                )

        # 在离开VPC页面前获取所需信息
        slb_uuid = vpc_page.get_slb_uuid(slb["name"])
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        # --------------------------------------------------------------
        # 步骤3~4: UDP客户端访问测试，验证源IP粘性
        # --------------------------------------------------------------
        with allure_step_log("步骤3~4: UDP客户端访问测试并验证源IP粘性"):
            ssh_vm.connect(requester["mfip"])
            messages = ["111", "222", "333", "444", "555"]
            for msg in messages:
                send_udp_message(ssh_vm, lb_vip, port, msg, timeout=5)
                time.sleep(0.5)

            # 等待UDP消息转发到后端
            time.sleep(3)

            hit_map = collect_udp_recipients(ssh_vm, backends, port, messages)
            # 源IP算法下，同一客户端的所有消息应命中同一台后端
            hit_backends = {backend for backend in hit_map.values() if backend is not None}
            assert len(hit_backends) == 1, (
                f"源IP算法应命中同一台后端，实际命中: {hit_backends} | 分布: {hit_map}"
            )
            # 所有消息都应命中
            missing = [msg for msg, backend in hit_map.items() if backend is None]
            assert not missing, (
                f"存在未命中消息: {missing} | 完整分布: {hit_map}"
            )

        # --------------------------------------------------------------
        # 步骤5: 实例级别监控验证（network模块）
        # --------------------------------------------------------------
        with allure_step_log("步骤5: 实例级别监控验证(network模块)"):
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.click_action(slb["name"], "查看监控")
            vpc_page.select_time_range("实时")
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤6: 监听器级别监控验证（network模块）
        # --------------------------------------------------------------
        with allure_step_log("步骤6: 监听器级别监控验证(network模块)"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并等待监控数据刷新
        with allure_step_log("补充流量数据并等待监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(10):
                send_udp_message(ssh_vm, lb_vip, port, "monitor_data", timeout=5)
                time.sleep(0.5)
            # 实时模式每10秒刷新一次，等待数据刷新
            time.sleep(15)

        # 验证监控数据不为零
        with allure_step_log("验证实例监控数据不为零"):
            vpc_page.select_object_tab("实例")
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证监听器监控数据不为零"):
            vpc_page.select_object_tab("监听器")
            vpc_page.select_listener(lb_name)
            vpc_page.assert_monitor_data_not_zero(wait_sec=5)

        # --------------------------------------------------------------
        # 步骤7: 进入CMS监控服务的负载均衡详情页
        # --------------------------------------------------------------
        with allure_step_log("步骤7: 进入CMS监控服务的负载均衡详情页"):
            cms_page = CmsPage(page)
            cms_page.goto_submenu("负载均衡（基础版）")
            cms_page.click_slb_in_list(slb["name"], slb_uuid=slb_uuid)
            cms_page.wait_for_page_ready()
            cms_page.page.wait_for_timeout(3000)
            cms_page.select_time_range("实时")

        # --------------------------------------------------------------
        # 步骤8: 补充流量数据
        # --------------------------------------------------------------
        with allure_step_log("步骤8: 补充流量数据"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(10):
                send_udp_message(ssh_vm, lb_vip, port, "cms_monitor", timeout=5)
                time.sleep(0.5)

        # --------------------------------------------------------------
        # 步骤9: CMS监控-实例级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤9: CMS监控-实例级别监控验证"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # --------------------------------------------------------------
        # 步骤10: CMS监控-监听器级别监控验证
        # --------------------------------------------------------------
        with allure_step_log("步骤10: CMS监控-监听器级别监控验证"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_charts_visible(min_charts=1)

        # 补充流量数据并验证CMS监控数据不为零
        with allure_step_log("补充流量数据并等待CMS监控数据刷新"):
            ssh_vm.connect(requester["mfip"])
            for _ in range(15):
                send_udp_message(ssh_vm, lb_vip, port, "cms_data", timeout=5)
                time.sleep(0.5)
            time.sleep(15)

        with allure_step_log("验证CMS实例监控数据不为零"):
            cms_page.select_object_tab("实例")
            cms_page.assert_monitor_data_not_zero(wait_sec=5)

        with allure_step_log("验证CMS监听器监控数据不为零"):
            cms_page.select_object_tab("监听器")
            cms_page.select_listener(lb_name)
            cms_page.assert_monitor_data_not_zero(wait_sec=5)
