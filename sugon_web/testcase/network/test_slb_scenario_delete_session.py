import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    prepare_http_backend,
    verify_lb_unreachable,
)
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log


PORT = 8080


def _collect_and_assert_round_robin(
    ssh_vm, requester_mfip, lb_vip, port, backend_markers, scene_name, count=20
):
    """采集HTTP响应并按轮询算法断言。"""
    ssh_vm.connect(requester_mfip)
    # 预热请求：让负载均衡器建立连接后再正式采集
    ssh_vm.run(
        f"curl -s --connect-timeout 10 http://{lb_vip}:{port}/index.html",
        check_rc=False,
    )
    responses = collect_lb_http_responses(
        ssh_vm, f"http://{lb_vip}:{port}/index.html", count=count
    )
    assert_lb_algorithm(
        "round_robin", responses, backend_markers, scene_name, tolerance=0.20
    )
    return responses


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1", "ha_enable": False}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版场景验证")
class TestSlbDeleteListener:
    """负载均衡基础版-删除监听器验证（用例3510）"""

    @allure.title("SLB-删除监听器验证")
    def test_delete_listener_with_members(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
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
            vpc_page.assert_popup_success()
            vpc_page.wait_for_page_ready()
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
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)

        with allure_step_log("步骤4: VIP访问测试（删除前）"):
            _collect_and_assert_round_robin(
                ssh_vm,
                requester["mfip"],
                lb_vip,
                PORT,
                backend_markers,
                "删除前VIP轮询验证",
            )

        with allure_step_log("步骤5: 尝试删除监听器（有成员，应失败）"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            vpc_page.slb_lb_delete(slb["name"], lb_name)
            vpc_page.close_dialog_if_exists()
            # P0: 验证监听器仍然存在（删除被阻止）
            vpc_page.assert_listener_exists(lb_name)

        with allure_step_log("步骤6: 移除资源池成员"):
            vpc_page.lb_pool_remove_vm(
                [b["name"] for b in backends], lb_name=lb_name, pool_name=pool_name
            )
            vpc_page.wait_for_page_ready()

        with allure_step_log("步骤7: 再次删除监听器（无成员，应成功）"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            vpc_page.slb_lb_delete(slb["name"], lb_name)
            vpc_page.assert_popup_success()
            # P0: 验证监听器已从左侧列表中删除（停留在监听器Tab页）
            vpc_page.assert_listener_not_exists(lb_name)

        with allure_step_log("步骤8: 验证LB无法访问（删除后）"):
            result = verify_lb_unreachable(
                ssh_vm, requester["mfip"], lb_vip, PORT,
                max_retries=5, retry_interval=3,
            )
            assert result["rc"] != 0, (
                f"[BackendAssertion] 监听器已删除，应无法访问 | "
                f"实际: rc={result['rc']}, stdout={result.get('stdout', '')}"
            )


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1", "ha_enable": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版场景验证")
class TestSlbSessionPersistence:
    """负载均衡基础版-会话保持功能验证（用例5442）"""

    @allure.title("SLB-会话保持功能验证")
    def test_session_persistence(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener
    ):
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }

        with allure_step_log("步骤1: 创建HTTP监听器（SOURCE IP会话保持）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
                session_persistence=True,
                session_type="SOURCE IP",
            )
            vpc_page.assert_popup_success()
            vpc_page.wait_for_page_ready()
            vpc_page.assert_listener_exists(lb_name, timeout=10000)
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
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤4: 绑定公网IP"):
            lb_fip = vpc_page.slb_bind_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            cleanup.add_eip(slb["name"])

        with allure_step_log("步骤5: SOURCE IP会话保持验证"):
            responses = collect_lb_http_responses(
                ssh_host, f"http://{lb_fip}:{PORT}/index.html", count=15
            )
            first_response = responses[0]
            for r in responses[1:]:
                assert r == first_response, (
                    f"[ScenarioAssertion] SOURCE IP会话保持 | "
                    f"期望: 全部返回同一结果 | "
                    f"实际: {first_response} vs {r}"
                )

        with allure_step_log("步骤6: 关闭会话保持"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            vpc_page.lb_pool_config_session_persistence(
                lb_name=lb_name, pool_name=pool_name, enable=False
            )

        with allure_step_log("步骤7: 验证非会话保持效果（轮询）"):
            ssh_host.run(
                f"curl -s http://{lb_fip}:{PORT}/index.html", check_rc=False
            )
            responses = collect_lb_http_responses(
                ssh_host, f"http://{lb_fip}:{PORT}/index.html", count=20
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "关闭会话保持后轮询验证",
            )

        with allure_step_log("步骤8: 修改为HTTP COOKIE会话保持"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            vpc_page.lb_pool_config_session_persistence(
                lb_name=lb_name,
                pool_name=pool_name,
                enable=True,
                session_type="HTTP COOKIE",
            )

        with allure_step_log("步骤9: HTTP COOKIE会话保持验证"):
            responses = collect_lb_http_responses(
                ssh_host, f"http://{lb_fip}:{PORT}/index.html", count=15,
                use_cookie=True
            )
            first_response = responses[0]
            for r in responses[1:]:
                assert r == first_response, (
                    f"[ScenarioAssertion] HTTP COOKIE会话保持 | "
                    f"期望: 全部返回同一结果 | "
                    f"实际: {first_response} vs {r}"
                )
