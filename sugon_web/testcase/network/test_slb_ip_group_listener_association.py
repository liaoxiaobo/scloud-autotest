import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic("网络服务")
@allure.feature("负载均衡-IP地址组")
@allure.story("关联监听器验证")
@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
class TestIpGroupListenerAssociation:
    """IP地址组关联监听器功能验证"""

    @allure.title("IP地址组-创建监听器的同时关联IP地址组")
    def test_create_listener_with_ip_group(self, vpc_page, slb, ip_group, clean_lb_listener):
        """场景1：创建监听器的同时关联IP地址组（用例410585）"""
        slb_name = slb["name"]
        group_name = ip_group["name"]
        lb_name = f"lb-{random_data()}"
        pool_name = "backend_1"
        desc = "1234567890edwqWDWQ中文~"

        with allure_step_log("步骤1: 创建TCP监听器并同时关联IP地址组"):
            vpc_page.slb_lb_create(
                slb_name=slb_name,
                lb_name=lb_name,
                protocol="TCP",
                port=1000,
                desc=desc,
                acl_enable=True,
                access_policy="黑名单",
                ip_group=group_name,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="TCP",
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            clean_lb_listener.add_listener({"slb_name": slb_name, "lb_name": lb_name})

        with allure_step_log("步骤2: 进入IP地址组详情页查看关联监听器"):
            vpc_page.goto_ip_group_detail(group_name)
            vpc_page.wait_for_page_ready()
            vpc_page.page.wait_for_timeout(3000)

            row_data = vpc_page.get_row_data(lb_name)
            access_policies = vpc_page.get_column_data("访问策略", context="active-tab")
            # get_row_data 会移除末列数据导致 访问策略 被移除，使用get_column_data获取 访问策略 列数据
            listener_names = vpc_page.get_column_data("名称", context="active-tab")
            assert row_data.get("协议") == "TCP", \
                f"协议校验失败，期望: TCP，实际: {row_data.get("协议")}"
            assert row_data.get("类型") == "负载均衡(基础版)", \
                f"类型校验失败，期望: 负载均衡(基础版)，实际: {row_data.get("类型")}"
            assert row_data.get("负载均衡端口") == "1000", \
                f"负载均衡端口校验失败，期望: 1000，实际: {row_data.get("负载均衡端口")}"
            assert access_policies[listener_names.index(lb_name)] == "黑名单", \
                f"访问策略校验失败，期望: 黑名单，实际: {row_data.get("访问策略")}"

    @allure.title("IP地址组-先创建监听器再关联IP地址组")
    def test_create_listener_then_associate_ip_group(self, vpc_page, slb, ip_group, clean_lb_listener):
        """场景2：先创建监听器再关联IP地址组（用例410587）"""
        slb_name = slb["name"]
        group_name = ip_group["name"]
        lb_name = f"lb-{random_data()}"
        pool_name = "backend_1"
        desc = "1234567890edwqWDWQ中文~"

        with allure_step_log("步骤1: 创建TCP监听器（不启用访问控制）"):
            vpc_page.slb_lb_create(
                slb_name=slb_name,
                lb_name=lb_name,
                protocol="TCP",
                port=1000,
                desc=desc,
                acl_enable=False,
                pool_name=pool_name,
                balance_method="轮询",
                health_check=True,
                health_type="TCP",
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)

        with allure_step_log("步骤2: 进入IP地址组详情页，验证关联监听器列表不包含新监听器"):
            vpc_page.goto_ip_group_detail(group_name)
            vpc_page.wait_for_page_ready()
            listener_names = vpc_page.get_column_data("名称", context="active-tab")
            assert lb_name not in listener_names, \
                f"关联监听器列表不应包含 {lb_name}，实际: {listener_names}"
            clean_lb_listener.add_listener({"slb_name": slb_name, "lb_name": lb_name})

        with allure_step_log("步骤3: 编辑监听器，启用访问控制并关联IP地址组"):
            vpc_page.goto_slb_detail(slb_name, "监听器")
            vpc_page.lb_edit_basic_info(
                lb_name=lb_name,
                field="access_control",
                enable=True,
                access_policy="白名单",
                ip_group=group_name,
            )

        with allure_step_log("步骤4: 再次进入IP地址组详情页，验证关联监听器正确展示"):
            vpc_page.goto_ip_group_detail(group_name)
            vpc_page.wait_for_page_ready()
            vpc_page.page.wait_for_timeout(3000)

            row_data = vpc_page.get_row_data(lb_name)
            access_policies = vpc_page.get_column_data("访问策略", context="active-tab")
            # get_row_data 会移除末列数据导致 访问策略 被移除，使用get_column_data获取 访问策略 列数据
            listener_names = vpc_page.get_column_data("名称", context="active-tab")
            assert row_data.get("协议") == "TCP", \
                f"协议校验失败，期望: TCP，实际: {row_data.get("协议")}"
            assert row_data.get("类型") == "负载均衡(基础版)", \
                f"类型校验失败，期望: 负载均衡(基础版)，实际: {row_data.get("类型")}"
            assert row_data.get("负载均衡端口") == "1000", \
                f"负载均衡端口校验失败，期望: 1000，实际: {row_data.get("负载均衡端口")}"
            assert access_policies[listener_names.index(lb_name)] == "白名单", \
                f"访问策略校验失败，期望: 黑名单，实际: {row_data.get("访问策略")}"
