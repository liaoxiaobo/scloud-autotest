"""VPN网关-基础版-连接ER类型-新建功能验证。"""

import time

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


def _cleanup_er(er_page, name):
    """模块级helper：删除企业路由器。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除企业路由器"):
        try:
            er_page._ensure_list_page()
            er_page.wait_for_page_ready()
            try:
                er_page.get_row_by_name(name)
            except Exception:
                logger.info(f"企业路由器 {name} 已不存在，跳过删除")
                return
            er_page.er_delete(name)
            er_page.assert_deleted(name, timeout=120)
        except Exception as e:
            logger.warning(f"清理企业路由器 {name} 失败: {e}")


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN网关基础版ER新建功能验证')
class TestVpnGatewaySSLER:
    """SSL类型VPN网关连接ER新建功能验证（用例420712）。"""

    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @allure.title("VPN网关-SSL类型-连接ER-基础版-新建功能验证")
    def test_vpn_gateway_ssl_er_basic_create(self, eip, er_page, vpn_page):
        """测试SSL类型VPN网关连接ER新建功能。

        前置条件（由fixture准备）：
        1. 3个FIP（public_net基础版）

        清理顺序：VPN网关（方法内）-> FIP（fixture teardown）-> ER（方法内）
        """
        # 创建开启HA的企业路由器
        er_name = f"vpn_er_{random_data(length=4)}"
        with allure_step_log("前置: 创建开启HA的企业路由器"):
            er_page.er_create(name=er_name, cluster_name="Autotest", ha_enable=True)
            er_page.assert_popup_success(timeout=30)
            logger.info(f"企业路由器 {er_name} 创建提交成功")

        # 等待ER状态变为运行中
        with allure_step_log("前置: 等待企业路由器状态变为运行中"):
            er_page._ensure_list_page()
            er_page.assert_status(
                er_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        fip_list = eip if isinstance(eip, list) else [eip]
        fip = fip_list[0] if fip_list else ""
        gw_name = f"vpn_autotest_er_{random_data(length=4)}"

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
                connection_type="企业路由器",
                er_name=er_name,
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
            # 连接资源在创建刚完成时可能尚未显示（ER关联是异步的），
            # 此处不做强断言，留到状态稳定后验证

        with allure_step_log("步骤4: 等待VPN网关状态变为运行中"):
            vpn_page.assert_status(
                gw_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("步骤4.5: 状态稳定后验证列表页连接资源"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            row_data = vpn_page.get_row_data(gw_name)
            assert er_name in (row_data.get("连接资源") or ""), f"列表页ER不匹配"

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

        with allure_step_log("清理: 删除VPN网关"):
            _cleanup_vpn_gateway(vpn_page, gw_name)
        with allure_step_log("清理: 等待VPN网关彻底删除（避免ER删除时报错）"):
            time.sleep(40)
        with allure_step_log("清理: 删除企业路由器"):
            _cleanup_er(er_page, er_name)


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN网关基础版ER新建功能验证')
class TestVpnGatewayIpsecER:
    """IPSEC类型VPN网关连接ER新建功能验证（用例420714）。"""

    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @allure.title("VPN网关-IPSEC类型-连接ER-基础版-新建功能验证")
    def test_vpn_gateway_ipsec_er_basic_create(self, eip, er_page, vpn_page):
        """测试IPSEC类型VPN网关连接ER新建功能。

        前置条件（由fixture准备）：
        1. 3个FIP（public_net基础版）

        清理顺序：VPN网关（方法内）-> FIP（fixture teardown）-> ER（方法内）
        """
        # 创建不开启HA的企业路由器
        er_name = f"vpn_er_{random_data(length=4)}"
        with allure_step_log("前置: 创建不开启HA的企业路由器"):
            er_page.er_create(name=er_name, cluster_name="Autotest", ha_enable=False)
            er_page.assert_popup_success(timeout=30)
            logger.info(f"企业路由器 {er_name} 创建提交成功")

        # 等待ER状态变为运行中
        with allure_step_log("前置: 等待企业路由器状态变为运行中"):
            er_page._ensure_list_page()
            er_page.assert_status(
                er_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        fip_list = eip if isinstance(eip, list) else [eip]
        fip = fip_list[0] if fip_list else ""
        gw_name = f"vpn_autotest_er_{random_data(length=4)}"

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
                connection_type="企业路由器",
                er_name=er_name,
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
            # 连接资源在创建刚完成时可能尚未显示（ER关联是异步的），
            # 此处不做强断言，留到状态稳定后验证

        with allure_step_log("步骤4: 等待VPN网关状态变为运行中"):
            vpn_page.assert_status(
                gw_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("步骤4.5: 状态稳定后验证列表页连接资源"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            row_data = vpn_page.get_row_data(gw_name)
            assert er_name in (row_data.get("连接资源") or ""), f"列表页ER不匹配"

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

        with allure_step_log("清理: 删除VPN网关"):
            _cleanup_vpn_gateway(vpn_page, gw_name)
        with allure_step_log("清理: 等待VPN网关彻底删除（避免ER删除时报错）"):
            time.sleep(40)
        with allure_step_log("清理: 删除企业路由器"):
            _cleanup_er(er_page, er_name)
