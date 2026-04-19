import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import load_data


@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监听器资源池")
class TestSlbPool:

    @allure.title("监听器资源池新增资源: {params[case_desc]}")
    @pytest.mark.parametrize("params", load_data("test_lb_pool_add_resource", "test_slb.yaml"))
    def test_lb_pool_add_resource(self, slb_page, lb, lb_pool_candidate_vms, params):
        selected_vms = lb_pool_candidate_vms[:params["vm_count"]]
        vm_names = [vm["name"] for vm in selected_vms]
        expected_ports = slb_page._resolve_expected_ports(params, selected_vms)
        added_vm_names = []

        with allure_step_log(f"步骤1: 进入监听器 {lb['name']} 的资源池详情页"):
            slb_page.goto_service("负载均衡")
            slb_page.goto_slb_detail(lb["slb_name"], "监听器")
            slb_page.goto_lb_pool_detail(lb["name"], lb["pool_name"])
            slb_page.assert_lb_pool_basic_info(
                pool_name=lb["pool_name"],
                protocol=lb["protocol"],
                balance_method=lb["balance_method"],
                session_persistence="未开启",
                health_check="未开启",
            )

        with allure_step_log(f"步骤2: 为资源池 {lb['pool_name']} 新增资源 {vm_names}"):
            slb_page.lb_pool_add_vm(vm_names=vm_names, ports=params["ports"])
            slb_page.assert_popup_success("提交成功")
            added_vm_names = vm_names.copy()

        with allure_step_log("步骤3: 校验资源池成员列表信息"):
            for vm_info, expected_port in zip(selected_vms, expected_ports):
                slb_page.assert_lb_pool_member_info(
                    vm_name=vm_info["name"],
                    ip_address=vm_info["ip"],
                    port=expected_port,
                )

        if added_vm_names:
            with allure_step_log(f"步骤4: 清理资源池成员 {added_vm_names}"):
                slb_page.lb_pool_remove_vm(added_vm_names)
                slb_page.assert_deleted(added_vm_names)
