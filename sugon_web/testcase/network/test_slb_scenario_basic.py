import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_and_assert_with_retry,
    collect_lb_http_responses,
    prepare_http_backend,
    verify_curl_backend,
)
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log


PORT_8080 = 8080
PORT_7070 = 7070


def _collect_and_assert(ssh_vm, requester_mfip, lb_vip, port, backend_markers,
                        policy, scene_name, weights=None, count=15, tolerance=0.15):
    """采集HTTP响应并按算法策略断言。

    Args:
        ssh_vm: SSH客户端。
        requester_mfip: 请求者虚机的MFIP。
        lb_vip: 负载均衡VIP。
        port: 访问端口。
        backend_markers: 后端标识字典。
        policy: 算法策略名称。
        scene_name: 场景描述。
        weights: 权重字典，默认None。
        count: curl请求次数，默认15。
        tolerance: 命中比例允许偏差，默认0.15。

    Returns:
        list[str]: 响应列表。
    """
    ssh_vm.connect(requester_mfip)
    responses = collect_lb_http_responses(
        ssh_vm, f"http://{lb_vip}:{port}/index.html", count=count
    )
    assert_lb_algorithm(
        policy,
        responses,
        backend_markers,
        scene_name,
        weights=weights,
        tolerance=tolerance,
    )
    return responses


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V1场景验证")
class TestSlbScenarioBasic:
    """负载均衡基础版-资源池成员管理与调度算法验证（用例3520、405855）"""

    @allure.title("SLBV1-资源池成员管理验证")
    def test_slb_member_management(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例3520：管理资源池成员"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建TCP监听器（加权轮询）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=PORT_8080,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener(
                {"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name}
            )

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT_8080,
                weights=1,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT_8080, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT_8080)
                cleanup.add_backend_server(backend, port=PORT_8080)

        with allure_step_log("步骤4: VIP访问测试（基线验证1:1:1）"):
            _collect_and_assert(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, backend_markers,
                "weighted_round_robin", "V1 TCP 加权轮询基线验证",
                weights={"ecs1": 1, "ecs2": 1, "ecs3": 1}, count=30,
                tolerance=0.20,
            )

        with allure_step_log("步骤5: 禁用云服务器实例ecs1"):
            vpc_page.lb_pool_disable_vm(
                backends[0]["name"], lb_name=lb_name, pool_name=pool_name
            )
            vpc_page.assert_lb_pool_member_info(
                backends[0]["name"], switch_status="禁用"
            )

        with allure_step_log("步骤6: 验证禁用后VIP访问（无ecs1）"):
            verify_curl_backend(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, backend_markers,
                "禁用ecs1后", excluded_backend="ecs1"
            )

        with allure_step_log("步骤7: 激活云服务器实例ecs1"):
            vpc_page.lb_pool_activate_vm(
                backends[0]["name"], lb_name=lb_name, pool_name=pool_name
            )
            vpc_page.assert_lb_pool_member_info(
                backends[0]["name"], switch_status="激活"
            )

        with allure_step_log("步骤8: 验证激活后VIP访问（包含ecs1）"):
            verify_curl_backend(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, backend_markers,
                "激活ecs1后", expected_backend="ecs1"
            )

        with allure_step_log("步骤9: 删除云服务器实例ecs3"):
            vpc_page.lb_pool_remove_vm(
                backends[2]["name"], lb_name=lb_name, pool_name=pool_name
            )
            vpc_page.wait_for_page_ready()

        with allure_step_log("步骤10: 验证删除后VIP访问（无ecs3）"):
            verify_curl_backend(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, backend_markers,
                "删除ecs3后", excluded_backend="ecs3"
            )

        with allure_step_log("步骤11: 修改ecs1、ecs2权重为2:3"):
            vpc_page.lb_pool_edit_weight(
                [backends[0]["name"], backends[1]["name"]],
                weights={backends[0]["name"]: 2, backends[1]["name"]: 3},
                lb_name=lb_name,
                pool_name=pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤12: 验证修改权重后VIP访问（ecs1:ecs2=2:3）"):
            active_markers = {
                k: v for k, v in backend_markers.items() if k in ("ecs1", "ecs2")
            }
            collect_and_assert_with_retry(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, active_markers,
                "weighted_round_robin", "V1 TCP 修改权重后验证(2:3)",
                weights={"ecs1": 2, "ecs2": 3},
            )

        with allure_step_log("步骤13: 新建成员ecs3"):
            vpc_page.lb_pool_add_vm(
                vm_names=[backends[2]["name"]],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT_8080,
                weights=1,
            )
            vpc_page.assert_popup_success("提交成功")
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], port=PORT_8080, resource_status="运行中"
            )

        with allure_step_log("步骤14: 验证添加成员后VIP访问（ecs1:ecs2:ecs3=2:3:1）"):
            collect_and_assert_with_retry(
                ssh_vm, requester["mfip"], lb_vip, PORT_8080, backend_markers,
                "weighted_round_robin", "V1 TCP 添加成员后验证(2:3:1)",
                weights={"ecs1": 2, "ecs2": 3, "ecs3": 1},
            )

    @allure.title("SLBV1-负载调度算法验证")
    def test_slb_balance_algorithm(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例405855：修改负载调度算法验证是否生效"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-http-{random_data()}"
        pool_name = f"pool-{random_data()}"
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建HTTP监听器（轮询）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTP",
                port=PORT_7070,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener(
                {"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name}
            )

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT_7070,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT_7070, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT_7070)
                cleanup.add_backend_server(backend, port=PORT_7070)

        with allure_step_log("步骤4: VIP访问测试（轮询基线1:1:1）"):
            _collect_and_assert(
                ssh_vm, requester["mfip"], lb_vip, PORT_7070, backend_markers,
                "round_robin", "V1 HTTP 轮询基线验证"
            )

        with allure_step_log("步骤5: 修改为加权轮询算法（权重1:2:2）"):
            vpc_page.lb_pool_config_balance_method(
                balance_method="加权轮询",
                lb_name=lb_name,
                pool_name=pool_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.lb_pool_edit_weight(
                [b["name"] for b in backends],
                weights={backends[0]["name"]: 1, backends[1]["name"]: 2, backends[2]["name"]: 2},
                lb_name=lb_name,
                pool_name=pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤6: 验证加权轮询（1:2:2）"):
            collect_and_assert_with_retry(
                ssh_vm, requester["mfip"], lb_vip, PORT_7070, backend_markers,
                "weighted_round_robin", "V1 HTTP 加权轮询验证(1:2:2)",
                weights={"ecs1": 1, "ecs2": 2, "ecs3": 2},
            )

        with allure_step_log("步骤7: 修改为源IP算法"):
            vpc_page.lb_pool_config_balance_method(
                balance_method="源IP",
                lb_name=lb_name,
                pool_name=pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤8: 验证源IP算法（同一结果）"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT_7070}/index.html", count=15
            )
            first_response = responses[0]
            for r in responses[1:]:
                assert r == first_response, (
                    f"源IP算法应返回同一结果，但出现不同: {first_response} vs {r}"
                )

        with allure_step_log("步骤9: 修改为最少连接数算法"):
            vpc_page.lb_pool_config_balance_method(
                balance_method="最小连接数",
                lb_name=lb_name,
                pool_name=pool_name,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤10: 验证最少连接数算法"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT_7070}/index.html", count=15
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 HTTP 最少连接数验证",
            )
