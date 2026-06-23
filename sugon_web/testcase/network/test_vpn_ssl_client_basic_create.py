"""SSL客户端-基础版-新建功能验证。"""

import pytest
import allure
from datetime import datetime, timedelta

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


def _cleanup_ssl_client(vpn_page, name):
    """模块级helper：删除SSL客户端。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除SSL客户端"):
        try:
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            try:
                vpn_page.get_row_by_name(name)
            except Exception:
                logger.info(f"SSL客户端 {name} 已不存在，跳过删除")
                return
            vpn_page.ssl_client_delete(name)
            vpn_page.assert_deleted(name, timeout=120)
        except Exception as e:
            logger.warning(f"清理SSL客户端 {name} 失败: {e}")


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('SSL客户端基础版新建功能验证')
class TestVpnSSLClientBasic:
    """SSL客户端基础版新建功能验证（用例5559）。"""

    @pytest.mark.parametrize(
        "vpc",
        [{"name_prefix": "vpn_", "cidr": "176.176.4.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @allure.title("SSL客户端-基础版-新建功能验证")
    def test_vpn_ssl_client_basic_create(self, vpc, eip, vpn_page):
        """测试SSL客户端基础版新建功能。

        前置条件（由fixture准备）：
        1. VPC（vpn_前缀，CIDR 176.176.4.0/24）
        2. 3个FIP（public_net基础版）

        清理顺序：SSL客户端（方法内）→ VPN网关（方法内）→ FIP（fixture teardown）→ VPC（fixture teardown）
        """
        vpc_name = vpc["name"]
        fip_list = eip if isinstance(eip, list) else [eip]
        fip = fip_list[0] if fip_list else ""
        gw_name = f"vpn_autotest_gw_{random_data(length=4)}"
        ssl_name = f"vpn_autotest_ssl_{random_data(length=4)}"
        # 过期时间：一个月后
        expiration_time = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        access_cidr = "176.176.4.0/24"

        # 步骤1-2: 前置条件 — 创建VPN网关（SSL类型、基础版、连接VPC）
        with allure_step_log("步骤1: 创建前置条件VPN网关"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
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

        with allure_step_log("步骤2: 等待VPN网关状态变为运行中"):
            vpn_page.assert_status(
                gw_name,
                status="运行中",
                timeout=600,
                refresh=True,
                refresh_interval=30,
            )

        # 步骤3-4: 进入SSL客户端页面并创建
        with allure_step_log("步骤3: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        with allure_step_log("步骤4: 创建SSL客户端"):
            vpn_page.ssl_client_create(
                name=ssl_name,
                vpn_gateway_name=gw_name,
                expiration_time=expiration_time,
                access_cidr=access_cidr,
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"SSL客户端 {ssl_name} 创建提交成功")

        # 步骤5: 列表页验证（P0存在性 + P1字段值）
        with allure_step_log("步骤5: 列表页验证SSL客户端信息"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            # P0: 存在性断言
            vpn_page.assert_list_contain(ssl_name, column_name="名称")
            # P1: 字段值回读
            row_data = vpn_page.get_row_data(ssl_name)
            assert ssl_name in (row_data.get("名称") or ""), f"[FieldAssertion] 列表页名称不匹配 | 期望: {ssl_name} | 实际: {row_data.get('名称')}"
            assert gw_name in (row_data.get("VPN网关") or ""), f"[FieldAssertion] 列表页VPN网关不匹配 | 期望: {gw_name} | 实际: {row_data.get('VPN网关')}"
            # 客户端状态：已开启（创建后默认开启）
            assert "已开启" in (row_data.get("客户端状态") or ""), f"[FieldAssertion] 列表页客户端状态不匹配 | 期望: 已开启 | 实际: {row_data.get('客户端状态')}"
            # 在线状态：离线（刚创建未连接）
            assert "离线" in (row_data.get("在线状态") or ""), f"[FieldAssertion] 列表页在线状态不匹配 | 期望: 离线 | 实际: {row_data.get('在线状态')}"

        # 步骤6: 详情页验证（P1字段值）
        with allure_step_log("步骤6: 详情页验证SSL客户端信息"):
            vpn_page.open_ssl_client_detail(ssl_name)
            detail_name = vpn_page.get_ssl_client_detail_field("名称")
            detail_status = vpn_page.get_ssl_client_detail_field("客户端状态")
            detail_vpn = vpn_page.get_ssl_client_detail_field("VPN网关")

            assert detail_name == ssl_name, f"[FieldAssertion] 详情页名称不匹配 | 期望: {ssl_name} | 实际: {detail_name}"
            assert detail_status == "已开启", f"[FieldAssertion] 详情页客户端状态不匹配 | 期望: 已开启 | 实际: {detail_status}"
            assert gw_name in detail_vpn, f"[FieldAssertion] 详情页VPN网关不匹配 | 期望包含: {gw_name} | 实际: {detail_vpn}"

        # 清理顺序：SSL客户端 → VPN网关 → FIP → VPC（FIP和VPC由fixture teardown处理）
        with allure_step_log("清理: 删除SSL客户端"):
            _cleanup_ssl_client(vpn_page, ssl_name)

        with allure_step_log("清理: 删除VPN网关"):
            _cleanup_vpn_gateway(vpn_page, gw_name)
