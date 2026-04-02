import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import load_data



@allure.epic("网络服务")
@allure.feature("负载均衡-IP地址组")
@allure.story("场景验证")
class TestIpGroupCreate:

    IP_GROUP_CREATE = load_data("test_ip_group_create_scenarios", "test_ip_group.yaml")

    @allure.title("创建IP地址组: {ip_group[case_desc]}")
    @pytest.mark.parametrize("ip_group", IP_GROUP_CREATE, ids=[item["case_desc"] for item in IP_GROUP_CREATE], indirect=True,)
    def test_ip_group_create_scenarios(self, ip_group_page, ip_group):
        group_name = ip_group["name"]
        ip_addresses = ip_group["ip_addresses"]
        desc = ip_group["desc"]
        expected_desc_length = ip_group["expected_desc_length"]

        with allure_step_log(f"步骤1: 校验场景 {ip_group['case_desc']} 的创建结果"):
            row_data = ip_group_page.get_row_data(group_name)
            assert row_data.get("名称") == group_name, (f"IP 地址组名称校验失败，期望: {group_name}，实际: {row_data.get('名称')}")
            assert ip_addresses[0] in row_data.get("包含IP地址", ""), (f"列表页 IP 校验失败，期望包含: {ip_addresses[0]}，实际: {row_data.get('包含IP地址')}")

        with allure_step_log(f"步骤2: 校验场景 {ip_group['case_desc']} 的详情信息"):
            ip_group_page.goto_ip_group_detail(group_name)
            ip_group_page.assert_detail_basic_info(name=group_name, desc=desc)
            detail_ips = ip_group_page.get_detail_ip_addresses()
            for ip in ip_addresses:
                assert ip in detail_ips, f"详情页 IP 校验失败，期望包含: {ip}，实际: {detail_ips}"

        with allure_step_log("步骤3: 校验描述长度符合预期边界"):
            assert len(desc) == expected_desc_length, (f"描述长度校验失败，期望: {expected_desc_length}，实际: {len(desc)}")
