import re

import allure
import pytest

from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log


@allure.epic("网络服务")
@allure.feature("内网解析")
@allure.story("业务场景覆盖验证")
class TestInternalDnsScenario:

    @allure.title("内网解析详情页-解析记录-主机记录与SRV记录解析生效验证")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_internal_dns_record_resolution_scenario(self, vpc_page, internal_dns, vm, ssh_vm):
        """验证 A 记录与 SRV 记录创建后，可在同 VPC 云主机内被正确解析。"""
        vm_client = vm[0]
        vm_target = vm[1]
        domain = internal_dns["domain"]
        target_ip = vm_target["ip"]
        www_alias = vpc_page.internal_dns_record_alias(domain, "www")
        root_alias = vpc_page.internal_dns_record_alias(domain, "")
        cdn_alias = vpc_page.internal_dns_record_alias(domain, "cdn")
        srv_alias = vpc_page.internal_dns_record_alias(domain, "testsrv")
        srv_value = f"1 99 3306 {target_ip}"

        with allure_step_log("步骤1: 打开内网解析详情页并校验基础信息"):
            vpc_page.goto_internal_dns_detail(domain)
            page_body = vpc_page.page.locator("body")
            expect(page_body).to_contain_text(domain)
            expect(page_body).to_contain_text(internal_dns["email"])
            expect(page_body).to_contain_text("正常")

        with allure_step_log("步骤2: 创建 www A 记录并验证解析生效"):
            vpc_page.internal_dns_record_create(
                domain=domain,
                host_record="www",
                record_type="A",
                ttl=300,
                values=target_ip,
                desc="主机记录解析验证",
            )
            vpc_page.assert_popup_success()
            vpc_page.goto_internal_dns_detail(domain, tab_name="解析记录")
            row_data = vpc_page.get_row_data(www_alias)
            assert row_data.get("域名") == www_alias, f"域名断言失败: {row_data}"
            assert row_data.get("类型") == "A", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == "300", f"TTL 断言失败: {row_data}"
            assert target_ip in row_data.get("值", ""), f"记录值断言失败: {row_data}"
            ssh_vm.connect(vm_client["mfip"])
            ping_output = ssh_vm.run(f"ping -c 4 {www_alias}", check_rc=True)
            assert target_ip in ping_output, f"www 记录解析结果未命中目标 IP: {ping_output}"

        with allure_step_log("步骤3: 创建根域 A 记录并验证解析生效"):
            vpc_page.internal_dns_record_create(
                domain=domain,
                host_record="",
                record_type="A",
                ttl=300,
                values=target_ip,
                desc="根域解析验证",
            )
            vpc_page.assert_popup_success()
            vpc_page.goto_internal_dns_detail(domain, tab_name="解析记录")
            active_tab = vpc_page.locator(".el-tab-pane:not([aria-hidden='true'])").first
            row_data = {}
            root_rows = active_tab.locator("tbody tr")
            for index in range(root_rows.count()):
                current_row = vpc_page.get_row_data_by_locator(root_rows.nth(index))
                if (
                    current_row.get("域名") == root_alias
                    and current_row.get("类型") == "A"
                    and current_row.get("TTL") == "300"
                    and target_ip in current_row.get("值", "")
                ):
                    row_data = current_row
                    break
            assert row_data.get("域名") == root_alias, f"根域名断言失败: {row_data}"
            assert row_data.get("类型") == "A", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == "300", f"TTL 断言失败: {row_data}"
            assert target_ip in row_data.get("值", ""), f"记录值断言失败: {row_data}"
            ssh_vm.connect(vm_client["mfip"])
            ping_output = ssh_vm.run(f"ping -c 4 {domain}", check_rc=True)
            assert target_ip in ping_output, f"根域记录解析结果未命中目标 IP: {ping_output}"

        with allure_step_log("步骤4: 创建 cdn 子域 A 记录并验证解析生效"):
            vpc_page.internal_dns_record_create(
                domain=domain,
                host_record="cdn",
                record_type="A",
                ttl=300,
                values=target_ip,
                desc="子域解析验证",
            )
            vpc_page.assert_popup_success()
            vpc_page.goto_internal_dns_detail(domain, tab_name="解析记录")
            row_data = vpc_page.get_row_data(cdn_alias)
            assert row_data.get("域名") == cdn_alias, f"域名断言失败: {row_data}"
            assert row_data.get("类型") == "A", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == "300", f"TTL 断言失败: {row_data}"
            assert target_ip in row_data.get("值", ""), f"记录值断言失败: {row_data}"
            ssh_vm.connect(vm_client["mfip"])
            ping_output = ssh_vm.run(f"ping -c 4 {cdn_alias}", check_rc=True)
            assert target_ip in ping_output, f"cdn 记录解析结果未命中目标 IP: {ping_output}"

        with allure_step_log("步骤5: 创建 SRV 记录并验证列表展示"):
            vpc_page.internal_dns_record_create(
                domain=domain,
                host_record="testsrv",
                record_type="SRV",
                ttl=300,
                values=srv_value,
                desc="SRV 记录解析验证",
            )
            vpc_page.assert_popup_success()
            vpc_page.goto_internal_dns_detail(domain, tab_name="解析记录")
            row_data = vpc_page.get_row_data(srv_alias)
            assert row_data.get("域名") == srv_alias, f"域名断言失败: {row_data}"
            assert row_data.get("类型") == "SRV", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == "300", f"TTL 断言失败: {row_data}"
            assert "3306" in row_data.get("值", ""), f"SRV 端口断言失败: {row_data}"
            assert target_ip in row_data.get("值", ""), f"SRV 目标地址断言失败: {row_data}"

        with allure_step_log("步骤6: 在云主机内执行 dig 验证 SRV 解析结果"):
            ssh_vm.connect(vm_client["mfip"])
            dig_output = ssh_vm.run(f"dig @169.254.169.253 {srv_alias} srv", check_rc=True)
            assert re.search(rf"1\s+99\s+3306\s+{re.escape(target_ip)}\.?", dig_output), (
                f"SRV 解析结果断言失败: {dig_output}"
            )
