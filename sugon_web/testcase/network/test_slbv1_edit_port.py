import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    assert_lb_algorithm,
    collect_lb_http_responses,
    prepare_http_backend,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


PORT_8080 = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V1场景验证")
class TestSlbV1EditPort:
    """负载均衡（基础版）V1-修改监听器端口验证"""

    @allure.title("负载均衡-修改监听器端口验证")
    def test_slbv1_edit_port(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        """用例5438：修改监听器端口验证"""
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        backend_markers = {
            f"ecs{i + 1}": f"this is ecs{i + 1}" for i in range(len(backends))
        }

        lb_tcp_name = "tcp_8080"
        lb_http_name = "http_8082"
        lb_udp_name = "udp_5050"
        pool_tcp_name = "backend_1"
        pool_http_name = "backend_2"
        pool_udp_name = "backend_3"

        with allure_step_log("步骤1: 创建前置监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_tcp_name,
                protocol="TCP",
                port=PORT_8080,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_tcp_name,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_tcp_name} 成功")
            vpc_page.assert_listener_exists(lb_tcp_name)
            cleanup.add_listener({"slb_name": slb, "lb_name": lb_tcp_name, "pool_name": pool_tcp_name})

            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_http_name,
                protocol="HTTP",
                port=7070,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_http_name,
                balance_method="加权轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_http_name} 成功")
            vpc_page.assert_listener_exists(lb_http_name)
            cleanup.add_listener({"slb_name": slb, "lb_name": lb_http_name, "pool_name": pool_http_name})

            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_udp_name,
                protocol="UDP",
                port=5050,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_udp_name,
                balance_method="源IP",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_udp_name} 成功")
            vpc_page.assert_listener_exists(lb_udp_name)
            cleanup.add_listener({"slb_name": slb, "lb_name": lb_udp_name, "pool_name": pool_udp_name})

        temp_lb_8082 = f"temp-tcp-8082-{random_data()}"
        temp_pool_8082 = f"pool-{random_data()}"
        temp_lb_8083 = f"temp-tcp-8083-{random_data()}"
        temp_pool_8083 = f"pool-{random_data()}"

        with allure_step_log("步骤2: 创建临时监听器用于端口冲突测试"):
            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=temp_lb_8082,
                protocol="TCP",
                port=8082,
                pool_name=temp_pool_8082,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {temp_lb_8082} 成功")
            vpc_page.assert_listener_exists(temp_lb_8082)
            cleanup.add_listener({"slb_name": slb, "lb_name": temp_lb_8082, "pool_name": temp_pool_8082})

            vpc_page.slb_lb_create(
                slb_name=slb,
                lb_name=temp_lb_8083,
                protocol="TCP",
                port=8083,
                pool_name=temp_pool_8083,
                balance_method="轮询",
                health_check=False,
            )
            vpc_page.assert_popup_success(f"新建监听器 {temp_lb_8083} 成功")
            vpc_page.assert_listener_exists(temp_lb_8083)
            cleanup.add_listener({"slb_name": slb, "lb_name": temp_lb_8083, "pool_name": temp_pool_8083})

        with allure_step_log("步骤3: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_tcp_name,
                pool_name=pool_tcp_name,
                ports=PORT_8080,
            )
            vpc_page.assert_popup_success("提交成功")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT_8080, resource_status="运行中"
                )

        with allure_step_log("步骤4: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT_8080)
                cleanup.add_backend_server(backend, port=PORT_8080)

        lb_vip = vpc_page.get_slb_vip(slb)

        with allure_step_log("步骤5: 修改端口为8081"):
            vpc_page.goto_slb_detail(slb, "监听器")
            vpc_page.lb_edit_basic_info(lb_tcp_name, field="port", port=8081)
            vpc_page.assert_popup_success()
            vpc_page.goto_lb_detail(lb_tcp_name)
            vpc_page.assert_lb_basic_info("8081")

        with allure_step_log("步骤6: VIP访问测试（端口8081）"):
            ssh_vm.connect(requester["mfip"])
            time.sleep(5)
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:8081/index.html"
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 端口8081 轮询验证",
            )

        with allure_step_log("步骤7: 修改端口为8082（期望失败）"):
            vpc_page.lb_edit_basic_info(lb_tcp_name, field="port", port=8082)
            vpc_page.assert_popup_error("已经被使用")
            vpc_page.goto_slb_detail(slb, "监听器")
            vpc_page.goto_lb_detail(lb_tcp_name)
            vpc_page.assert_lb_basic_info("8081")

        with allure_step_log("步骤8: 修改端口为8083（期望失败）"):
            vpc_page.lb_edit_basic_info(lb_tcp_name, field="port", port=8083)
            vpc_page.assert_popup_error("已经被使用")
            vpc_page.goto_slb_detail(slb, "监听器")
            vpc_page.goto_lb_detail(lb_tcp_name)
            vpc_page.assert_lb_basic_info("8081")

        with allure_step_log("步骤9: 修改端口为5050"):
            vpc_page.lb_edit_basic_info(lb_tcp_name, field="port", port=5050)
            vpc_page.assert_popup_success()
            vpc_page.goto_lb_detail(lb_tcp_name)
            vpc_page.assert_lb_basic_info("5050")

        with allure_step_log("步骤10: VIP访问测试（端口5050）"):
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:5050/index.html"
            )
            assert_lb_algorithm(
                "round_robin",
                responses,
                backend_markers,
                "V1 TCP 端口5050 轮询验证",
            )
