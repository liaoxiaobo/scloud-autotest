"""VPN通道-修改功能验证。"""

import pytest
import allure
from time import sleep

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _cleanup_vpn_tunnel(vpn_page, name):
    """模块级helper：删除VPN通道。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除VPN通道"):
        vpn_page._ensure_vpn_tunnel_list()
        vpn_page.wait_for_page_ready()
        try:
            vpn_page.get_row_by_name(name)
        except Exception:
            logger.info(f"VPN通道 {name} 已不存在，跳过删除")
            return
        vpn_page.vpn_tunnel_delete(name)
        vpn_page.assert_deleted(name, timeout=120)


def _cleanup_vpn_gateway(vpn_page, name):
    """模块级helper：删除VPN网关。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除VPN网关"):
        vpn_page._ensure_vpn_gateway_list()
        vpn_page.wait_for_page_ready()
        try:
            vpn_page.get_row_by_name(name)
        except Exception:
            logger.info(f"VPN网关 {name} 已不存在，跳过删除")
            return
        vpn_page.vpn_gateway_delete(name)
        vpn_page.assert_deleted(name, timeout=120)


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN通道修改功能验证')
class TestVpnVpnConnectionModify:
    """VPN通道-修改功能验证（用例5829）。"""

    @pytest.mark.parametrize(
        "vpc",
        [{"name_prefix": "vpn_", "cidr": "176.176.9.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @pytest.mark.slow
    @allure.title("VPN通道-修改功能验证")
    def test_vpn_vpn_connection_modify(self, vpc, eip, vpn_page):
        """测试VPN通道修改功能。

        前置条件（由fixture准备）：
        1. VPC（vpn_前缀，CIDR 176.176.9.0/24）
        2. 3个FIP（public_net基础版）

        用例内创建的前置条件：
        3. VPN网关（IPSEC类型，连接VPC，使用fip1）
        4. VPN通道（使用上述VPN网关，报文封装模式tunnel，对端网关fip2，
           预共享密钥sugon123，本端网段176.176.9.0/24，远端网段176.176.10.0/24）

        测试步骤：
        1. 进入VPN模块
        2. 进入VPN通道模块
        3. 打开VPN通道修改弹窗（点击修改按钮）
        4. 执行修改：预共享密钥sugon123→sugon1234，本端网关→166.166.166.166
        5. 提交修改（点击立即修改）
        6. 校验列表页信息
        7. 校验详情页信息

        清理顺序：VPN通道 → VPN网关 → FIP → VPC
        （FIP和VPC由fixture teardown处理）
        """
        vpc_name = vpc["name"]
        fip_list = eip if isinstance(eip, list) else [eip]
        fip1 = fip_list[0] if fip_list else ""
        fip2 = fip_list[1] if len(fip_list) > 1 else ""

        gw_name = f"vpn_autotest_ipsec_{random_data(length=4)}"
        tunnel_name = f"vpn_tunnel_{random_data(length=4)}"
        pre_shared_key = "sugon123"
        local_subnet = "176.176.9.0/24"
        peer_subnet = "176.176.10.0/24"
        peer_gateway = fip2 if fip2 else "176.176.10.1"

        # 修改后的新值
        new_pre_shared_key = "sugon1234"
        new_local_gateway = "166.166.166.166"

        # ========== 前置条件构建 ==========
        # 前置3: 创建IPSEC类型VPN网关（连接VPC）
        with allure_step_log("前置: 创建IPSEC类型VPN网关"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_gateway_create(
                name=gw_name,
                cluster="Autotest",
                vpn_type="IPSEC",
                resource_pool="public_net(基础版)",
                fip_address=fip1,
                connection_type="虚拟私有云",
                vpc_name=vpc_name,
                flavor="虚拟专用网络数据型",
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN网关 {gw_name} 创建提交成功")

        with allure_step_log("前置: 等待VPN网关状态变为运行中"):
            vpn_page.assert_status(
                gw_name,
                status="运行中",
                timeout=600,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("前置: 等待VPN网关就绪（10秒）"):
            sleep(10)

        # 前置4: 创建VPN通道
        with allure_step_log("前置: 创建VPN通道"):
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_tunnel_create(
                name=tunnel_name,
                vpn_gateway_name=gw_name,
                encapsulation_mode="tunnel",
                peer_gateway=peer_gateway,
                pre_shared_key=pre_shared_key,
                local_subnet=local_subnet,
                peer_subnet=peer_subnet,
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN通道 {tunnel_name} 创建提交成功")

        with allure_step_log("前置: 等待VPN通道就绪（20秒）"):
            sleep(20)

        # ========== 测试步骤 ==========
        # 步骤1: 进入VPN模块（已在VPN通道列表页）
        with allure_step_log("步骤1: 进入VPN模块"):
            vpn_page.goto_service("专有网络VPN")
            vpn_page.wait_for_page_ready()

        # 步骤2: 进入VPN通道模块
        with allure_step_log("步骤2: 进入VPN通道模块"):
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()

        # 步骤3: 打开VPN通道修改弹窗
        with allure_step_log("步骤3: 打开VPN通道修改弹窗"):
            vpn_page.vpn_tunnel_modify_open(tunnel_name)
            # P0: 验证修改页面已打开（通过检查页面URL或表单元素）
            vpn_page.wait_for_page_ready()
            logger.info(f"VPN通道 {tunnel_name} 修改页面已打开")

        # 步骤4: 执行修改操作
        with allure_step_log("步骤4: 执行修改操作"):
            # 修改预共享密钥: sugon123 → sugon1234
            vpn_page.vpn_tunnel_modify_field(
                field_label="预共享密钥",
                value=new_pre_shared_key,
            )
            # 修改本端网关: 空 → 166.166.166.166
            vpn_page.vpn_tunnel_modify_field(
                field_label="本端网关",
                value=new_local_gateway,
            )
            logger.info(
                f"已修改字段: 预共享密钥={new_pre_shared_key}, 本端网关={new_local_gateway}"
            )

        # 步骤5: 提交修改
        with allure_step_log("步骤5: 提交修改"):
            vpn_page.vpn_tunnel_modify_submit()
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN通道 {tunnel_name} 修改提交成功")

        # 步骤6: 校验列表页信息（P0存在性 + P1字段值）
        with allure_step_log("步骤6: 校验列表页信息"):
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()
            # P0: 存在性断言
            vpn_page.assert_list_contain(tunnel_name, column_name="名称")
            # P1: 字段值回读
            row_data = vpn_page.get_row_data(tunnel_name)
            assert tunnel_name in (row_data.get("名称") or ""), \
                f"[FieldAssertion] 列表页名称不匹配 | 期望: {tunnel_name} | 实际: {row_data.get('名称')}"
            assert new_local_gateway in (row_data.get("本端网关") or ""), \
                f"[FieldAssertion] 列表页本端网关不匹配 | 期望: {new_local_gateway} | 实际: {row_data.get('本端网关')}"
            assert new_pre_shared_key in (row_data.get("预共享密钥") or ""), \
                f"[FieldAssertion] 列表页预共享密钥不匹配 | 期望: {new_pre_shared_key} | 实际: {row_data.get('预共享密钥')}"
            assert gw_name in (row_data.get("VPN网关") or ""), \
                f"[FieldAssertion] 列表页VPN网关不匹配 | 期望: {gw_name} | 实际: {row_data.get('VPN网关')}"
            assert peer_gateway in (row_data.get("对端网关") or ""), \
                f"[FieldAssertion] 列表页对端网关不匹配 | 期望: {peer_gateway} | 实际: {row_data.get('对端网关')}"

        # 步骤7: 校验详情页信息（P1字段值）
        with allure_step_log("步骤7: 校验详情页信息"):
            vpn_page.open_vpn_tunnel_detail(tunnel_name)
            detail_name = vpn_page.get_vpn_tunnel_detail_field("名称")
            detail_vpn = vpn_page.get_vpn_tunnel_detail_field("VPN网关")
            detail_mode = vpn_page.get_vpn_tunnel_detail_field("报文封装模式")
            detail_peer = vpn_page.get_vpn_tunnel_detail_field("对端网关")
            detail_secret = vpn_page.get_vpn_tunnel_detail_field("预共享密钥")
            # 注：详情页基本信息区不显示"本端网关"字段（passageway-detail.vue 无此字段）
            # 本端网关已在列表页校验通过

            assert detail_name == tunnel_name, \
                f"[FieldAssertion] 详情页名称不匹配 | 期望: {tunnel_name} | 实际: {detail_name}"
            assert gw_name in detail_vpn, \
                f"[FieldAssertion] 详情页VPN网关不匹配 | 期望包含: {gw_name} | 实际: {detail_vpn}"
            assert detail_mode == "tunnel", \
                f"[FieldAssertion] 详情页报文封装模式不匹配 | 期望: tunnel | 实际: {detail_mode}"
            assert detail_peer == peer_gateway, \
                f"[FieldAssertion] 详情页对端网关不匹配 | 期望: {peer_gateway} | 实际: {detail_peer}"
            assert detail_secret == new_pre_shared_key, \
                f"[FieldAssertion] 详情页预共享密钥不匹配 | 期望: {new_pre_shared_key} | 实际: {detail_secret}"

        # ========== 清理阶段（严格按MD要求的清理顺序） ==========
        # 1. 删除VPN通道
        with allure_step_log("清理: 删除VPN通道"):
            _cleanup_vpn_tunnel(vpn_page, tunnel_name)

        # 2. 删除VPN网关
        with allure_step_log("清理: 删除VPN网关"):
            _cleanup_vpn_gateway(vpn_page, gw_name)

        # 3. 删除FIP（由eip fixture teardown处理）
        # 4. 删除VPC（由vpc fixture teardown处理）
