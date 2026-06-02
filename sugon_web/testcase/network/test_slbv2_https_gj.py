"""负载均衡V2-HTTPS双向认证-最小连接数-访问控制白名单 测试用例

用例436799: v2-新建监听器-HTTPS(双向认证)-最小连接数-国际服务器证书-HA验证
用例436822: v2-访问控制-白名单场景-外网LB
"""

from collections import Counter

import allure
import pytest

from sugon_web.testcase.network._ca_fixtures import ca_cert, mtls_certs, server_cert
from sugon_web.testcase.network._lb_fixtures import clean_ip_group, clean_lb_listener
from sugon_web.testcase.network._slb_helpers import (
    collect_lb_responses,
    count_lb_responses,
    get_ssh_host_source_ip,
    prepare_http_backend,
    wait_for_curl_match,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data

PORT = 7070
CERT_DIR = "/root/mtls-certificates"
HOST_CERT_DIR = "/tmp/mtls-certificates"


def _copy_ca_cert_to_host(ssh_vm, vm_info, ssh_host):
    """将CA证书从虚机复制到ssh_host。

    Args:
        ssh_vm: ssh_vm fixture。
        vm_info: 虚机信息字典。
        ssh_host: ssh_host fixture。
    """
    ssh_vm.connect(vm_info["mfip"])
    b64_ca = ssh_vm.run(f"base64 -w 0 {CERT_DIR}/ca.crt", check_rc=True).strip()
    ssh_host.run(f"mkdir -p {HOST_CERT_DIR}", check_rc=True)
    ssh_host.run(f"echo '{b64_ca}' | base64 -d > {HOST_CERT_DIR}/ca.crt", check_rc=True)


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V2", "ha_enable": False}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("HTTPS监听器场景验证")
class TestSlbV2HttpsGj:
    """负载均衡V2 HTTPS双向认证及访问控制白名单场景验证。"""

    def test_slbv2_https_bidirectional_cert(
        self, vpc_page, slb, vm, ssh_vm, server_cert, ca_cert,
        clean_lb_listener,
    ):
        """用例436799: v2-新建监听器-HTTPS(双向认证)-最小连接数-国际服务器证书。"""
        allure.dynamic.title(
            "v2-新建监听器-HTTPS(双向认证)-最小连接数-国际服务器证书"
        )
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-https-{random_data()}"
        pool_name = f"pool-{random_data()}"

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建HTTPS监听器（双向认证）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTPS",
                port=443,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="最小连接数",
                health_check=False,
                auth_mode="双向认证",
                cert_type="国际服务器证书",
                server_cert=server_cert,
                ca_cert=ca_cert,
                http_redirect=True,
                redirect_port=7374,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤3: 启动后端web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 1}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤4: 内网VIP访问测试（双向认证）"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_responses(
                ssh_vm,
                f"curl -s --connect-timeout 10 --cacert {CERT_DIR}/ca.crt "
                f"https://{lb_vip}:443",
                count=6,
                check_rc=False,
            )
            counter = Counter(responses)
            assert any("this is ecs" in key for key in counter), (
                f"访问失败: {dict(counter)}"
            )

        with allure_step_log("步骤5: 验证证书绑定关系"):
            bound_listeners = vpc_page.cert_get_bound_listeners(server_cert)
            assert lb_name in bound_listeners, (
                f"证书未绑定监听器 {lb_name}，实际绑定: {bound_listeners}"
            )

        with allure_step_log("步骤6: 修改监听器重定向入口"):
            vpc_page.goto_slb_detail(slb["name"], tab_name="监听器")
            vpc_page.lb_edit_redirect_port(lb_name, redirect_port=7374)
            vpc_page.assert_popup_success()
            # 离开详情页避免对话框残留遮挡后续操作
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("负载均衡（基础版）")

        with allure_step_log("步骤7: 验证重定向"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_responses(
                ssh_vm,
                f"curl -s -L --connect-timeout 10 --cacert {CERT_DIR}/ca.crt "
                f"http://{lb_vip}:7374",
                count=6,
                check_rc=False,
            )
            counter = Counter(responses)
            assert any("this is ecs" in key for key in counter), (
                f"重定向访问失败: {dict(counter)}"
            )

    def test_slbv2_https_acl_whitelist_external(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, server_cert, ca_cert,
        clean_ip_group, clean_lb_listener,
    ):
        """用例436822: v2-访问控制-白名单场景-外网LB。"""
        allure.dynamic.title("v2-访问控制-白名单场景-外网LB")
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        excluded = vm[1]
        backends = vm[2:4]
        lb_name = f"lb-https-acl-{random_data()}"
        pool_name = f"pool-{random_data()}"
        ip_group_name = f"ipg-{random_data()}"

        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建IP地址组并添加ecs0的IP"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1b: IP地址组添加ecs1的IP"):
            vpc_page.ip_group_add_ip_addresses(ip_group_name, [excluded["ip"]])
            vpc_page.assert_popup_success()
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert excluded["ip"] in actual_ips, (
                f"IP地址组中未找到ecs1的IP {excluded['ip']}，实际: {actual_ips}"
            )

        with allure_step_log("步骤2: 创建HTTPS监听器（启用访问控制白名单）"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="HTTPS",
                port=443,
                desc="1234567890edwqWDWQ中文~",
                pool_name=pool_name,
                balance_method="最小连接数",
                health_check=False,
                auth_mode="双向认证",
                cert_type="国际服务器证书",
                server_cert=server_cert,
                ca_cert=ca_cert,
                acl_enable=True,
                access_policy="白名单",
                ip_group=ip_group_name,
                http_redirect=True,
                redirect_port=7374,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

        with allure_step_log("步骤3: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤4: 启动后端web服务"):
            for i, backend in enumerate(backends):
                prepare_http_backend(ssh_vm, backend, f"ecs{i + 2}", port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤5: 白名单内客户端访问（ecs0）"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_responses(
                ssh_vm,
                f"curl -s --connect-timeout 10 --cacert {CERT_DIR}/ca.crt "
                f"https://{lb_vip}:443",
                count=6,
                check_rc=False,
            )
            counter = Counter(responses)
            assert any("this is ecs" in key for key in counter), (
                f"访问失败: {dict(counter)}"
            )

        with allure_step_log("步骤6: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == eip, (
                f"绑定公网IP不一致: 期望{eip}, 实际{actual_eip}"
            )

        with allure_step_log("步骤7: 白名单外访问测试（ssh_host）"):
            _copy_ca_cert_to_host(ssh_vm, requester, ssh_host)
            result = ssh_host.run(
                f"curl -sk --connect-timeout 10 --cacert {HOST_CERT_DIR}/ca.crt "
                f"https://{eip}:443",
                check_rc=False,
                return_rc=True,
            )
            stdout = (result.get("stdout") or "").strip()
            # 排除 SSL 证书问题(rc=60)，验证网络层拒绝
            is_rejected = (
                result["rc"] != 0 or not stdout or "Forbidden" in stdout
            )
            assert is_rejected, (
                f"应被拒绝，实际: rc={result['rc']}, stdout={stdout[:200]}"
            )

        with allure_step_log("步骤8: IP地址组添加本机ip"):
            host_ips = get_ssh_host_source_ip(ssh_host, eip)
            assert host_ips, "无法识别ssh_host访问EIP的源IP"
            host_ip = host_ips[0]
            vpc_page.ip_group_add_ip_addresses(ip_group_name, [host_ip])
            vpc_page.assert_popup_success()
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert host_ip in actual_ips, (
                f"IP地址组未成功添加源IP {host_ip}，实际: {actual_ips}"
            )

        with allure_step_log("步骤9: 等待ACL规则同步并验证白名单内访问"):
            curl_cmd = (
                f"curl -sk --connect-timeout 10 --cacert {HOST_CERT_DIR}/ca.crt "
                f"https://{eip}:443"
            )
            wait_for_curl_match(ssh_host, curl_cmd, "this is ecs", timeout_sec=60, interval_sec=5)

        with allure_step_log("步骤9b: 白名单内再次访问测试"):
            responses = collect_lb_responses(
                ssh_host,
                f"curl -sk --connect-timeout 10 --cacert {HOST_CERT_DIR}/ca.crt "
                f"https://{eip}:443",
                count=6,
                check_rc=False,
            )
            counter = Counter(responses)
            assert any("this is ecs" in key for key in counter), (
                f"访问失败: {dict(counter)}"
            )
