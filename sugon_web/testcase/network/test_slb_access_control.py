import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener, clean_ip_group
from sugon_web.testcase.network._slb_helpers import (
    prepare_http_backend,
    collect_lb_http_responses,
)
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log


PORT = 8080


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("基础版V1访问控制验证")
class TestSlbV1AccessControl:
    """负载均衡（基础版）V1访问控制验证"""

    @allure.title("SLBV1-访问控制白名单黑名单关闭切换验证")
    def test_slbv1_access_control(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener, clean_ip_group
    ):
        """用例410790：访问控制白名单/黑名单/关闭切换验证"""
        cleanup_lb = clean_lb_listener
        cleanup_ipg = clean_ip_group
        requester = vm[0]
        rejecter = vm[1]
        backends = vm[2:4]
        lb_name = f"lb-tcp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        ip_group_name = f"ipg-{random_data()}"
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 后端虚机启动web服务"):
            for i, backend in enumerate(backends):
                marker = f"ecs{i + 3}"
                prepare_http_backend(ssh_vm, backend, marker, port=PORT)
                cleanup_lb.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤2: 创建IP地址组（包含ecs0的IP）"):
            ecs0_ip = requester["ip"]
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("IP地址组")
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[ecs0_ip],
                desc="访问控制测试IP地址组",
            )
            vpc_page.assert_popup_success()
            cleanup_ipg.add(ip_group_name)

        with allure_step_log("步骤3: 创建TCP监听器"):
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
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            cleanup_lb.add_listener(
                {"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name}
            )

        with allure_step_log("步骤3.5: 配置监听器访问控制为白名单并验证"):
            vpc_page.lb_edit_basic_info(
                lb_name=lb_name,
                field="access_control",
                enable=True,
                access_policy="白名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            # lb_edit_basic_info 完成后页面已在监听器详情页，直接断言
            vpc_page.assert_lb_basic_info("白名单")
            # 等待左侧列表重新加载完成（访问控制编辑后前端可能刷新列表）
            vpc_page.page.wait_for_timeout(5000)

        with allure_step_log("步骤4: 添加资源池成员"):
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

        with allure_step_log("步骤5: 白名单访问验证-允许（ecs0）"):
            ssh_vm.connect(requester["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=6
            )
            success_count = sum(1 for r in responses if "this is ecs" in r)
            assert success_count > 0, (
                f"ecs0（白名单内）应能访问VIP，但实际无成功响应: {responses}"
            )

        with allure_step_log("步骤6: 白名单访问验证-拒绝（ecs1）"):
            ssh_vm.connect(rejecter["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                check_rc=False,
                return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"ecs1（白名单外）应被拒绝访问，"
                f"实际: rc={result['rc']}, stdout={result['stdout']}"
            )

        with allure_step_log("步骤7: 修改访问控制为黑名单"):
            vpc_page.goto_slb_detail(slb["name"], tab_name="监听器")
            vpc_page.wait_for_page_ready()
            vpc_page.lb_edit_basic_info(
                lb_name=lb_name,
                field="access_control",
                enable=True,
                access_policy="黑名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("黑名单")
            # 等待后端访问控制规则同步生效
            vpc_page.page.wait_for_timeout(10000)

        with allure_step_log("步骤8: 黑名单访问验证-拒绝（ecs0）"):
            ssh_vm.connect(requester["mfip"])
            result = ssh_vm.run(
                f"curl -s --connect-timeout 5 http://{lb_vip}:{PORT}/index.html",
                check_rc=False,
                return_rc=True,
            )
            assert result["rc"] != 0 or not result["stdout"].strip(), (
                f"ecs0（黑名单内）应被拒绝访问，"
                f"实际: rc={result['rc']}, stdout={result['stdout']}"
            )

        with allure_step_log("步骤9: 黑名单访问验证-允许（ecs1）"):
            ssh_vm.connect(rejecter["mfip"])
            responses = collect_lb_http_responses(
                ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=6
            )
            success_count = sum(1 for r in responses if "this is ecs" in r)
            assert success_count > 0, (
                f"ecs1（黑名单外）应能访问VIP，但实际无成功响应: {responses}"
            )

        with allure_step_log("步骤10: 关闭访问控制"):
            vpc_page.goto_slb_detail(slb["name"], tab_name="监听器")
            vpc_page.wait_for_page_ready()
            vpc_page.lb_edit_basic_info(
                lb_name=lb_name,
                field="access_control",
                enable=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("允许所有IP访问")
            # 等待后端访问控制规则同步生效
            vpc_page.page.wait_for_timeout(10000)

        with allure_step_log("步骤11: 关闭访问控制后验证"):
            for vm_info, vm_label in [(requester, "ecs0"), (rejecter, "ecs1")]:
                ssh_vm.connect(vm_info["mfip"])
                responses = collect_lb_http_responses(
                    ssh_vm, f"http://{lb_vip}:{PORT}/index.html", count=6
                )
                success_count = sum(1 for r in responses if "this is ecs" in r)
                assert success_count > 0, (
                    f"{vm_label}（访问控制关闭后）应能访问VIP，"
                    f"实际无成功响应: {responses}"
                )
