"""VPN网关-基础版-连接VPC类型-新建功能验证。"""

import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _cleanup_vpn_gateway(vpn_page, name):
    """模块级helper：删除VPN网关。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除VPN网关"):
        try:
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            try:
                vpn_page.get_row_by_name(name)
            except Exception:
                logger.info(f"VPN网关 {name} 已不存在，跳过删除")
                return
            vpn_page.vpn_gateway_delete(name)
            vpn_page.assert_deleted(name, timeout=120)
        except Exception as e:
            logger.warning(f"清理VPN网关 {name} 失败: {e}")


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN网关基础版VPC新建功能验证')
class TestVpnGatewaySSL:
    """SSL类型VPN网关新建功能验证（用例5555）。"""

    @pytest.mark.parametrize(
        "vpc",
        [{"name_prefix": "vpn_", "cidr": "176.176.1.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @allure.title("VPN网关-SSL类型-连接VPC-基础版-新建功能验证")
    def test_vpn_gateway_ssl_vpc_basic_create(self, vpc, eip, vpn_page):
        """测试SSL类型VPN网关新建功能。

        前置条件（由fixture准备）：
        1. VPC（vpn_前缀，CIDR 176.176.1.0/24）
        2. 3个FIP（public_net基础版）

        清理顺序：VPN网关（方法内）→ FIP（fixture teardown）→ VPC（fixture teardown）
        """
        vpc_name = vpc["name"]
        fip_list = eip if isinstance(eip, list) else [eip]
        fip = fip_list[0] if fip_list else ""
        gw_name = f"vpn_autotest_gw_{random_data(length=4)}"

        try:
            with allure_step_log("步骤1: 进入VPN网关模块"):
                vpn_page._ensure_vpn_gateway_list()
                vpn_page.wait_for_page_ready()

            with allure_step_log("步骤2: 创建SSL类型VPN网关"):
                vpn_page.vpn_gateway_create(
                    name=gw_name,
                    cluster="Autotest",
                    vpn_type="SSL",
                    resource_pool="public_net(基础版)",
                    fip_address=fip,
                    connection_type="虚拟私有云",
                    vpc_name=vpc_name,
                    flavor="虚拟专用网络数据型",
                    resource_pool_tag="基础版",
                    client_subnet="17.17.17.0/24",
                )
                vpn_page.assert_popup_success(timeout=30)
                logger.info(f"VPN网关 {gw_name} 创建提交成功")

            with allure_step_log("步骤3: 列表页验证VPN网关信息"):
                vpn_page._ensure_vpn_gateway_list()
                vpn_page.wait_for_page_ready()
                row_data = vpn_page.get_row_data(gw_name)
                assert gw_name in (row_data.get("名称") or ""), f"列表页名称不匹配"
                assert "SSL" in (row_data.get("类型") or ""), f"列表页类型不匹配"
                assert vpc_name in (row_data.get("连接资源") or ""), f"列表页VPC不匹配"

            with allure_step_log("步骤4: 等待VPN网关状态变为运行中"):
                vpn_page.assert_status(
                    gw_name,
                    status="运行中",
                    timeout=600,
                    refresh=True,
                    refresh_interval=30,
                )

            with allure_step_log("步骤5: 详情页验证VPN网关信息"):
                vpn_page.open_vpn_gateway_detail(gw_name)
                detail_name = vpn_page.get_vpn_gateway_detail_field("名称")
                detail_type = vpn_page.get_vpn_gateway_detail_field("类型")
                detail_cluster = vpn_page.get_vpn_gateway_detail_field("集群")
                detail_status = vpn_page.get_vpn_gateway_detail_field("运行状态")
                detail_state = vpn_page.get_vpn_gateway_detail_field("状态")

                assert detail_name == gw_name, f"详情页名称不匹配: {detail_name}"
                assert detail_type == "SSL", f"详情页类型不匹配: {detail_type}"
                assert detail_cluster == "Autotest", f"详情页集群不匹配: {detail_cluster}"
                assert detail_status == "运行中", f"详情页运行状态不匹配: {detail_status}"
                assert detail_state == "正常", f"详情页状态不匹配: {detail_state}"
        finally:
            with allure_step_log("清理: 删除VPN网关"):
                _cleanup_vpn_gateway(vpn_page, gw_name)


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN网关基础版VPC新建功能验证')
class TestVpnGatewayIpsec:
    """IPSEC类型VPN网关新建功能验证（用例420713）。"""

    @pytest.mark.parametrize(
        "vpc",
        [{"name_prefix": "vpn_", "cidr": "176.176.2.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @allure.title("VPN网关-IPSEC类型-连接VPC-基础版-新建功能验证")
    def test_vpn_gateway_ipsec_vpc_basic_create(self, vpc, eip, vpn_page):
        """测试IPSEC类型VPN网关新建功能。

        前置条件（由fixture准备）：
        1. VPC（vpn_前缀，CIDR 176.176.2.0/24）
        2. 3个FIP（public_net基础版）

        清理顺序：VPN网关（方法内）→ FIP（fixture teardown）→ VPC（fixture teardown）
        """
        vpc_name = vpc["name"]
        fip_list = eip if isinstance(eip, list) else [eip]
        fip = fip_list[0] if fip_list else ""
        gw_name = f"vpn_autotest_gw_{random_data(length=4)}"

        try:
            with allure_step_log("步骤1: 进入VPN网关模块"):
                vpn_page._ensure_vpn_gateway_list()
                vpn_page.wait_for_page_ready()

            with allure_step_log("步骤2: 创建IPSEC类型VPN网关"):
                vpn_page.vpn_gateway_create(
                    name=gw_name,
                    cluster="Autotest",
                    vpn_type="IPSEC",
                    resource_pool="public_net(基础版)",
                    fip_address=fip,
                    connection_type="虚拟私有云",
                    vpc_name=vpc_name,
                    flavor="虚拟专用网络数据型",
                )
                vpn_page.assert_popup_success(timeout=30)
                logger.info(f"VPN网关 {gw_name} 创建提交成功")

            with allure_step_log("步骤3: 列表页验证VPN网关信息"):
                vpn_page._ensure_vpn_gateway_list()
                vpn_page.wait_for_page_ready()
                row_data = vpn_page.get_row_data(gw_name)
                assert gw_name in (row_data.get("名称") or ""), f"列表页名称不匹配"
                assert "IPSEC" in (row_data.get("类型") or ""), f"列表页类型不匹配"
                assert vpc_name in (row_data.get("连接资源") or ""), f"列表页VPC不匹配"

            with allure_step_log("步骤4: 等待VPN网关状态变为运行中"):
                vpn_page.assert_status(
                    gw_name,
                    status="运行中",
                    timeout=600,
                    refresh=True,
                    refresh_interval=30,
                )

            with allure_step_log("步骤5: 详情页验证VPN网关信息"):
                vpn_page.open_vpn_gateway_detail(gw_name)
                detail_name = vpn_page.get_vpn_gateway_detail_field("名称")
                detail_type = vpn_page.get_vpn_gateway_detail_field("类型")
                detail_cluster = vpn_page.get_vpn_gateway_detail_field("集群")
                detail_status = vpn_page.get_vpn_gateway_detail_field("运行状态")
                detail_state = vpn_page.get_vpn_gateway_detail_field("状态")

                assert detail_name == gw_name, f"详情页名称不匹配: {detail_name}"
                assert detail_type == "IPSEC", f"详情页类型不匹配: {detail_type}"
                assert detail_cluster == "Autotest", f"详情页集群不匹配: {detail_cluster}"
                assert detail_status == "运行中", f"详情页运行状态不匹配: {detail_status}"
                assert detail_state == "正常", f"详情页状态不匹配: {detail_state}"
        finally:
            with allure_step_log("清理: 删除VPN网关"):
                _cleanup_vpn_gateway(vpn_page, gw_name)
