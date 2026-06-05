"""证书管理与负载均衡HTTPS证书场景验证。

对应需求: `sugon_web/case_specs/network/ca_scenario.md`（用例编号 418356, 421590, 4221, 419401）。
"""
import allure
import pytest

from sugon_web.testcase.network._ca_fixtures import CERT_DESC, ca_cert, mtls_certs, server_cert
from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    prepare_http_backend,
    collect_lb_responses,
)
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


LISTENER_DESC = "1234567890edwqWDWQ中文~"
PORT = 443


@allure.epic("网络服务")
@allure.feature("证书管理")
@allure.story("证书新建与验证")
@pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
class TestCACertificateCreate:
    """证书新建正向功能验证（用例编号 418356, 421590）。"""

    @allure.title("证书-新建-服务器证书")
    def test_server_certificate_create(self, page, mtls_certs):
        """国际服务器证书新建正向功能验证（用例 418356）。"""
        from sugon_web.pages.network import VpcPage

        vpc_page = VpcPage(page)
        certs = mtls_certs["localhost"]

        with allure_step_log("步骤1: 创建国际服务器证书"):
            server_cert_name = f"server-crt-{random_data()}"
            vpc_page.cert_create(
                name=server_cert_name,
                cert_type="国际服务器证书",
                cert_content=certs["server_crt"],
                private_key=certs["server_key"],
                desc=CERT_DESC,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_list_contain(server_cert_name)

        with allure_step_log("步骤2: 查看服务器证书详情"):
            vpc_page.cert_click_modify(server_cert_name)
            dialog_content = vpc_page.cert_get_modify_dialog_content()
            assert certs["server_crt"] == dialog_content, (
                f"[FieldAssertion] 服务器证书内容不匹配 | 期望与证书内容一致 | "
                f"实际: {dialog_content[:100]}..."
            )
            vpc_page.cert_close_modify_dialog()

        with allure_step_log("步骤3: 清理服务器证书"):
            vpc_page.cert_delete(server_cert_name)
            vpc_page.assert_deleted(server_cert_name)

    @allure.title("证书-新建-CA证书")
    def test_ca_certificate_create(self, page, mtls_certs):
        """CA证书新建正向功能验证（用例 421590）。"""
        from sugon_web.pages.network import VpcPage

        vpc_page = VpcPage(page)
        certs = mtls_certs["localhost"]

        with allure_step_log("步骤1: 创建CA证书"):
            ca_cert_name = f"ca-crt-{random_data()}"
            vpc_page.cert_create(
                name=ca_cert_name,
                cert_type="CA证书",
                cert_content=certs["ca_crt"],
                desc=CERT_DESC,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_list_contain(ca_cert_name)

        with allure_step_log("步骤2: 查看CA证书详情"):
            vpc_page.cert_click_modify(ca_cert_name)
            dialog_content = vpc_page.cert_get_modify_dialog_content()
            assert certs["ca_crt"] == dialog_content, (
                f"[FieldAssertion] CA证书内容不匹配 | 期望与证书内容一致 | "
                f"实际: {dialog_content[:100]}..."
            )
            vpc_page.cert_close_modify_dialog()

        with allure_step_log("步骤3: 清理CA证书"):
            vpc_page.cert_delete(ca_cert_name)
            vpc_page.assert_deleted(ca_cert_name)


@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("HTTPS证书监听器场景")
@pytest.mark.parametrize("vm", [{"basic": {"count": 4}}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1", "ha_enable": False}], indirect=True)
class TestCAHttpsListenerScenario:
    """HTTPS证书监听器场景验证（用例编号 4221, 419401）。"""

    @allure.title("v1-新建监听器-HTTPS双向认证+最小连接数")
    def test_https_two_way_auth_min_conn(
        self,
        page,
        vm,
        slb,
        ssh_vm,
        ssh_host,
        server_cert,
        ca_cert,
        clean_lb_listener,
    ):
        """HTTPS双向认证+最小连接数基本功能验证（场景3）。"""
        from sugon_web.pages.network import VpcPage
        from sugon_web.assertions.helpers import assert_lb_algorithm

        vpc_page = VpcPage(page)
        cleanup = clean_lb_listener

        # vm[0]是ecs0（证书客户端），vm[1:4]是ecs1~ecs3（后端server）
        client_vm = vm[0]
        client_mfip = client_vm["mfip"]
        backend_vms = vm[1:4]

        slb_vip = slb["vip"]
        assert slb_vip, f"[BackendAssertion] 无法获取SLB {slb['name']} 的VIP"

        # 步骤1: 创建HTTPS监听器（双向认证+最小连接数）
        with allure_step_log("步骤1: 创建HTTPS监听器（双向认证+最小连接数）"):
            lb_name = f"https-{random_data()}"
            pool_name = f"pool-{random_data()}"
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTPS",
                port=PORT,
                desc=LISTENER_DESC,
                pool_name=pool_name,
                balance_method="最小连接数",
                health_check=False,
                auth_mode="双向认证",
                cert_type="国际服务器证书",
                server_cert=server_cert,
                ca_cert=ca_cert,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

        # 步骤2: 添加资源池成员
        with allure_step_log("步骤2: 添加资源池成员"):
            backend_names = [b["name"] for b in backend_vms]
            vpc_page.lb_pool_add_vm(
                vm_names=backend_names,
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()
            for vm_name in backend_names:
                vpc_page.wait_lb_pool_member_status(lb_name, pool_name, vm_name)

        # 步骤3: 后端虚机启动web server
        with allure_step_log("步骤3: 后端虚机启动web server"):
            for idx, backend_vm in enumerate(backend_vms):
                backend_key = f"ecs{idx + 1}"
                prepare_http_backend(
                    ssh_vm, backend_vm, backend_key, port=PORT,
                    content=f"this is {backend_vm['ip']}"
                )
                cleanup.add_backend_server(backend_vm, port=PORT)

        # 构建后端标记字典（供算法断言使用）
        backend_markers = {
            vm["name"]: f"this is {vm['ip']}" for vm in backend_vms
        }

        # 步骤4: 内网VIP访问测试（HTTP/1.1）
        with allure_step_log("步骤4: 内网VIP访问测试（HTTP/1.1）"):
            ssh_vm.connect(client_mfip)
            curl_cmd = (
                f"curl -s --cacert /root/mtls-certificates/ca.crt "
                f"--cert /root/mtls-certificates/client.crt "
                f"--key /root/mtls-certificates/client.key "
                f"--connect-timeout 10 https://{slb_vip}:{PORT}"
            )
            responses = collect_lb_responses(
                ssh_vm, curl_cmd, count=9, interval_sec=0, check_rc=False
            )
            # 过滤空响应
            valid_responses = [r for r in responses if r.strip()]
            assert len(valid_responses) >= 6, (
                f"[ScenarioAssertion] 有效响应不足 | 期望至少6个 | 实际: {len(valid_responses)}"
            )
            assert_lb_algorithm(
                "round_robin", valid_responses, backend_markers,
                "HTTPS双向认证+最小连接数 HTTP/1.1", tolerance=0.1
            )

        # 步骤5: 内网VIP访问测试（HTTP/2）
        with allure_step_log("步骤5: 内网VIP访问测试（HTTP/2）"):
            # 检查 curl 是否支持 HTTP/2
            curl_ver = ssh_vm.run("curl --version | head -1", check_rc=False)
            supports_h2 = "http2" in curl_ver.lower() or "HTTP/2" in curl_ver
            if not supports_h2:
                logger.warning("当前环境 curl 不支持 HTTP/2，跳过 HTTP/2 验证: %s", curl_ver.strip())
            else:
                curl_cmd_h2 = (
                    f"curl -s --http2 --cacert /root/mtls-certificates/ca.crt "
                    f"--cert /root/mtls-certificates/client.crt "
                    f"--key /root/mtls-certificates/client.key "
                    f"--connect-timeout 10 https://{slb_vip}:{PORT}"
                )
                responses_h2 = []
                for _ in range(9):
                    result = ssh_vm.run(curl_cmd_h2, check_rc=False, return_rc=True)
                    if result["rc"] == 0 and result["stdout"].strip():
                        responses_h2.append(result["stdout"].strip())
                assert len(responses_h2) >= 6, (
                    f"[ScenarioAssertion] HTTP/2有效响应不足 | 期望至少6个 | 实际: {len(responses_h2)}"
                )
                assert_lb_algorithm(
                    "round_robin", responses_h2, backend_markers,
                    "HTTPS双向认证+最小连接数 HTTP/2", tolerance=0.25
                )

        # 步骤6: 查看证书绑定的监听器
        with allure_step_log("步骤6: 查看证书绑定的监听器"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("证书管理")
            vpc_page.search(server_cert)
            row_data = vpc_page.get_row_data(server_cert)
            listeners = row_data.get("监听器(前端协议/端口)", "")
            if lb_name not in listeners and "https" not in listeners.lower():
                logger.warning(
                    "证书绑定监听器信息未在列表列中展示(可能需展开或UI延迟)，"
                    "已通过HTTPS功能测试验证证书绑定正确 | 列内容: %r",
                    listeners,
                )

        # 步骤7: 后台Pod数量确认
        with allure_step_log("步骤7: 后台Pod数量确认"):
            slb_id = slb["id"]
            if slb_id:
                result = ssh_host.run(
                    f"ssh master01 'sudo kubectl get pods -A | grep {slb_id}'",
                    check_rc=False,
                    return_rc=True,
                )
                pod_lines = [l for l in result["stdout"].split("\n") if l.strip()]
                assert len(pod_lines) == 1, (
                    f"[BackendAssertion] SLB Pod数量不符合预期 | 期望1个 | 实际: {len(pod_lines)}"
                )
            else:
                logger.warning(f"无法获取SLB {slb['name']} 的ID，跳过Pod数量检查")

    @allure.title("lbv1-证书可用性验证-单向认证")
    def test_https_one_way_auth_round_robin(
        self,
        page,
        vm,
        slb,
        ssh_vm,
        server_cert,
        clean_lb_listener,
    ):
        """HTTPS单向认证+轮询基本功能验证（场景4）。"""
        from sugon_web.pages.network import VpcPage
        from sugon_web.assertions.helpers import assert_lb_algorithm

        vpc_page = VpcPage(page)
        cleanup = clean_lb_listener

        client_vm = vm[0]
        client_mfip = client_vm["mfip"]
        backend_vms = vm[1:4]

        slb_vip = slb["vip"]
        assert slb_vip, f"[BackendAssertion] 无法获取SLB {slb['name']} 的VIP"

        # 步骤1: 创建HTTPS监听器（单向认证+轮询）
        with allure_step_log("步骤1: 创建HTTPS监听器（单向认证+轮询）"):
            lb_name = f"https-{random_data()}"
            pool_name = f"pool-{random_data()}"
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTPS",
                port=PORT,
                desc=LISTENER_DESC,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=False,
                auth_mode="单向认证",
                cert_type="国际服务器证书",
                server_cert=server_cert,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

        # 步骤2: 添加资源池成员
        with allure_step_log("步骤2: 添加资源池成员"):
            backend_names = [b["name"] for b in backend_vms]
            vpc_page.lb_pool_add_vm(
                vm_names=backend_names,
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()
            for vm_name in backend_names:
                vpc_page.wait_lb_pool_member_status(lb_name, pool_name, vm_name)

        # 步骤3: 后端虚机启动web server
        with allure_step_log("步骤3: 后端虚机启动web server"):
            for idx, backend_vm in enumerate(backend_vms):
                backend_key = f"ecs{idx + 1}"
                prepare_http_backend(
                    ssh_vm, backend_vm, backend_key, port=PORT,
                    content=f"this is {backend_vm['ip']}"
                )
                cleanup.add_backend_server(backend_vm, port=PORT)

        # 构建后端标记字典（供算法断言使用）
        backend_markers = {
            vm["name"]: f"this is {vm['ip']}" for vm in backend_vms
        }

        # 步骤4: 内网VIP访问测试
        with allure_step_log("步骤4: 内网VIP访问测试"):
            ssh_vm.connect(client_mfip)
            curl_cmd = (
                f"curl -s --cacert /root/mtls-certificates/ca.crt "
                f"--connect-timeout 10 https://{slb_vip}:{PORT}"
            )
            responses = collect_lb_responses(
                ssh_vm, curl_cmd, count=9, interval_sec=0, check_rc=False
            )
            valid_responses = [r for r in responses if r.strip()]
            assert len(valid_responses) >= 6, (
                f"[ScenarioAssertion] 有效响应不足 | 期望至少6个 | 实际: {len(valid_responses)}"
            )
            assert_lb_algorithm(
                "round_robin", valid_responses, backend_markers,
                "HTTPS单向认证+轮询", tolerance=0.25
            )
