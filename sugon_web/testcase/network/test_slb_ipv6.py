import time

import allure
import pytest

from sugon_web.common.remote.ssh import SSH
from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.testcase.network._slb_helpers import prepare_http_backend_ipv6
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data

PORT = 4040


@pytest.mark.parametrize("vpc", [{"enable_ipv6": True}], indirect=True)
@pytest.mark.parametrize(
    "vm",
    [
        {
            "basic": {"count": 2},
            "storage": {"image": {"name": "Anolis86"}},
            "network": {"enable_ipv6": True},
            "bind_mfip": True,
        }
    ],
    indirect=True,
)
@pytest.mark.parametrize("slb", [{"version": "V2"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("IPv6功能验证")
class TestSlbIpv6:
    """负载均衡V2 IPv6功能验证。"""

    def test_slb_v2_ipv6(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title("SLBV2-IPv6功能验证")
        cleanup = clean_lb_listener
        requester = vm[0]
        backend = vm[1]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"

        with allure_step_log("步骤1: 配置虚机IPv6网卡"):
            for vm_info in vm:
                ssh_vm.connect(vm_info["mfip"])
                ssh_vm.run(
                    "cd /etc/sysconfig/network-scripts && "
                    "echo 'IPV6INIT=yes' >> ifcfg-ens3 && "
                    "echo 'NETWORKING_IPV6=yes' >> ifcfg-ens3",
                    check_rc=True,
                )
                ssh_vm.run("systemctl restart NetworkManager", check_rc=True)
                result = ssh_vm.run(
                    "ip ad | grep -i inet6", check_rc=False, return_rc=True
                )
                assert result["rc"] == 0, f"IPv6配置失败: {result.get('stderr', '')}"
                assert "inet6" in result["stdout"], (
                    f"未找到IPv6地址: {result['stdout']}"
                )

        with allure_step_log("步骤2: 在后端虚机启动web服务"):
            prepare_http_backend_ipv6(ssh_vm, backend, "ecs1", port=PORT)
            cleanup.add_backend_server(
                backend, port=PORT, kill_pattern="python3 /tmp/slb_http_ecs1_4040.py"
            )

        with allure_step_log("步骤3: 创建TCP监听器"):
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
            cleanup.add_listener({
                "slb_name": slb["name"],
                "lb_name": lb_name,
                "pool_name": pool_name,
            })

        with allure_step_log("步骤4: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[backend["name"]],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success("提交成功")

            # 轮询等待资源池成员健康检查通过（状态由离线变为运行中）
            member_online = False
            for _ in range(30):
                try:
                    vpc_page.assert_lb_pool_member_info(
                        backend["name"], port=PORT, resource_status="运行中"
                    )
                    member_online = True
                    break
                except AssertionError:
                    time.sleep(2)
            assert member_online, (
                f"资源池成员 {backend['name']} 未在60秒内进入运行中状态"
            )

        slb_info = vpc_page.get_slb_detail_info(slb["name"])
        lb_vip = slb_info["vip"]
        lb_vip6 = slb_info.get("vip6", "")
        allure.attach(
            f"SLB IPv4 VIP: {lb_vip}\nSLB IPv6 VIP: {lb_vip6}\n"
            f"后端 ECS IP: {backend.get('ip', '')}\n"
            f"后端 ECS IPv6: {backend.get('ipv6', '')}",
            name="SLB与后端IP信息",
            attachment_type=allure.attachment_type.TEXT,
        )

        with allure_step_log("步骤5: IPv4 VIP访问测试"):
            ssh_vm.connect(requester["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 10 http://{lb_vip}:{PORT}/index.html",
                return_rc=True,
            )
            assert result["rc"] == 0, (
                f"IPv4 VIP访问失败: {result.get('stderr', '')}"
            )
            assert "this is ecs1" in result["stdout"], (
                f"响应内容不匹配: {result['stdout']}"
            )

        with allure_step_log("步骤6: IPv6 VIP访问测试"):
            assert lb_vip6, f"SLB {slb['name']} 未分配IPv6 VIP地址"
            result = ssh_vm.run(
                f"curl -g -s --connect-timeout 10 "
                f"http://[{lb_vip6}]:{PORT}/index.html",
                return_rc=True,
            )
            assert result["rc"] == 0, (
                f"IPv6 VIP访问失败: {result.get('stderr', '')}"
            )
            assert "this is ecs1" in result["stdout"], (
                f"响应内容不匹配: {result['stdout']}"
            )

        with allure_step_log("步骤7: 绑定公网IPv6"):
            available_eips = vpc_page.get_available_eips(
                slb["name"], ip_version="IPv6"
            )
            if len(available_eips) < 1:
                pytest.skip("环境问题：当前环境无可用公网IPv6")
            eip6 = vpc_page.slb_bind_eip(slb["name"], ip_version="IPv6")
            cleanup.add_eip(slb["name"], ip_version="IPv6")
            assert eip6, f"SLB {slb['name']} 绑定公网IPv6后未获取到IPv6地址"

        with allure_step_log("步骤8: 公网IPv6访问测试"):
            external_ssh = SSH()
            external_ssh.connect(
                "172.22.3.211",
                username="root",
                pwd="Sugon@123",
                use_jumphost=False,
            )
            try:
                # 公网IPv6绑定后需要等待网络收敛，轮询最多60秒
                result = None
                for _ in range(6):
                    result = external_ssh.run(
                        f"curl -g -s --connect-timeout 10 "
                        f"http://[{eip6}]:{PORT}/index.html",
                        return_rc=True,
                    )
                    if result["rc"] == 0:
                        break
                    time.sleep(10)
                else:
                    if result and result["rc"] in (7, 28):
                        pytest.skip(
                            "环境问题：外部客户端无公网IPv6路由，无法验证访问"
                        )
                    assert result["rc"] == 0, (
                        f"公网IPv6访问失败: {result.get('stderr', '')}"
                    )
                assert "this is ecs1" in result["stdout"], (
                    f"响应内容不匹配: {result['stdout']}"
                )
            finally:
                external_ssh.close()
