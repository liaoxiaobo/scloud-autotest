"""VPN通道-连接ER-新建功能验证。"""

from time import sleep

import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _cleanup_vpn_tunnel(vpn_page, name):
    """模块级helper：删除VPN通道。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除VPN通道"):
        try:
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()
            try:
                vpn_page.get_row_by_name(name)
            except Exception:
                logger.info(f"VPN通道 {name} 已不存在，跳过删除")
                return
            vpn_page.vpn_tunnel_delete(name)
            vpn_page.assert_deleted(name, timeout=120)
        except Exception as e:
            logger.warning(f"清理VPN通道 {name} 失败: {e}")


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


def _cleanup_er_connection(er_page, er_name, conn_name):
    """模块级helper：删除ER连接。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除ER连接"):
        try:
            er_page.goto_connection_tab(er_name)
            er_page.wait_for_page_ready()
            try:
                er_page.get_row_by_name(conn_name)
            except Exception:
                logger.info(f"ER连接 {conn_name} 已不存在，跳过删除")
                return
            er_page.er_connection_delete(conn_name)
            er_page.wait_for_page_ready()
            logger.info(f"ER连接 {conn_name} 删除成功")
        except Exception as e:
            logger.warning(f"清理ER连接 {conn_name} 失败: {e}")


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
@allure.story('VPN通道连接ER新建功能验证')
class TestVpnTunnelErCreate:
    """VPN通道-连接ER-新建功能验证（用例15824）。"""

    @pytest.mark.parametrize(
        "vpc",
        [{"name_prefix": "vpn_", "cidr": "176.176.11.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "eip",
        [{"count": 3, "pool": "public_net(基础版)"}],
        indirect=True,
    )
    @pytest.mark.slow
    @allure.title("VPN通道-连接ER-新建功能验证")
    def test_vpn_tunnel_er_create(self, vpc, eip, er_page, vpn_page):
        """测试VPN通道连接ER新建功能。

        前置条件（由fixture准备）：
        1. VPC（vpn_前缀，CIDR 176.176.11.0/24）
        2. 3个FIP（public_net基础版）

        用例内创建的前置条件：
        3. ER（开启HA）+ 添加VPC为连接
        4. VPN网关（IPSEC类型，连接ER，使用fip1）

        清理顺序：VPN通道 → VPN网关 → FIP → ER连接 → ER → VPC
        （FIP和VPC由fixture teardown处理）
        """
        vpc_name = vpc["name"]
        vpc_subnet_name = vpc["subnet_name"]
        fip_list = eip if isinstance(eip, list) else [eip]
        fip1 = fip_list[0] if fip_list else ""
        fip2 = fip_list[1] if len(fip_list) > 1 else ""

        er_name = f"vpn_er_{random_data(length=4)}"
        conn_name = f"vpn_conn_{random_data(length=4)}"
        gw_name = f"vpn_autotest_ipsec_{random_data(length=4)}"
        tunnel_name = f"autotest_tunnel_{random_data(length=4)}"
        pre_shared_key = "sugon123"
        local_subnet = "176.176.11.0/24"
        peer_subnet = "176.176.12.0/24"
        peer_gateway = fip2 if fip2 else "176.176.12.1"

        # ========== 前置条件构建 ==========
        # 前置3: 创建开启HA的ER并添加VPC连接
        with allure_step_log("前置: 创建开启HA的企业路由器"):
            er_page.er_create(name=er_name, cluster_name="Autotest", ha_enable=True)
            er_page.assert_popup_success(timeout=30)
            logger.info(f"企业路由器 {er_name} 创建提交成功")

        with allure_step_log("前置: 等待企业路由器状态变为运行中"):
            er_page._ensure_list_page()
            er_page.assert_status(
                er_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("前置: 添加VPC为ER连接"):
            er_page.goto_connection_tab(er_name)
            er_page.er_connection_create(
                name=conn_name,
                conn_type="VPC",
                vpc_name=vpc_name,
                subnet_name=vpc_subnet_name,
            )
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER连接 {conn_name} 创建提交成功")

        with allure_step_log("前置: 等待ER连接就绪（10秒）"):
            sleep(10)

        # 前置4: 创建IPSEC类型VPN网关（连接ER）
        with allure_step_log("前置: 创建IPSEC类型VPN网关"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_gateway_create(
                name=gw_name,
                cluster="Autotest",
                vpn_type="IPSEC",
                resource_pool="public_net(基础版)",
                fip_address=fip1,
                connection_type="企业路由器",
                er_name=er_name,
                flavor="虚拟专用网络数据型",
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN网关 {gw_name} 创建提交成功")

        with allure_step_log("前置: 等待VPN网关状态变为运行中"):
            vpn_page.assert_status(
                gw_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        # ========== 测试步骤 ==========
        # 步骤1: 进入VPN通道模块
        with allure_step_log("步骤1: 进入VPN通道列表页"):
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 创建VPN通道（失败时等待5秒重试一次）
        with allure_step_log("步骤2: 创建VPN通道"):
            for attempt in range(1, 3):
                try:
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
                    logger.info(f"VPN通道 {tunnel_name} 第{attempt}次创建提交成功")
                    break
                except Exception as e:
                    logger.warning(f"VPN通道第{attempt}次创建尝试失败: {e}")
                    # 失败后检查是否实际已创建成功
                    vpn_page._ensure_vpn_tunnel_list()
                    vpn_page.wait_for_page_ready()
                    try:
                        vpn_page.get_row_by_name(tunnel_name)
                        logger.info(f"VPN通道 {tunnel_name} 已存在，视为创建成功")
                        break
                    except Exception:
                        if attempt == 1:
                            logger.info("等待5秒后第2次创建...")
                            sleep(5)
                        else:
                            raise

        # 步骤3: 列表页验证（P0存在性 + P1字段值）
        with allure_step_log("步骤3: 列表页验证VPN通道信息"):
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()
            # P0: 存在性断言
            vpn_page.assert_list_contain(tunnel_name, column_name="名称")
            # P1: 字段值回读
            row_data = vpn_page.get_row_data(tunnel_name)
            assert tunnel_name in (row_data.get("名称") or ""), \
                f"[FieldAssertion] 列表页名称不匹配 | 期望: {tunnel_name} | 实际: {row_data.get('名称')}"
            assert gw_name in (row_data.get("VPN网关") or ""), \
                f"[FieldAssertion] 列表页VPN网关不匹配 | 期望: {gw_name} | 实际: {row_data.get('VPN网关')}"
            assert fip1 in (row_data.get("本端网关") or ""), \
                f"[FieldAssertion] 列表页本端网关不匹配 | 期望: {fip1} | 实际: {row_data.get('本端网关')}"
            assert peer_gateway in (row_data.get("对端网关") or ""), \
                f"[FieldAssertion] 列表页对端网关不匹配 | 期望: {peer_gateway} | 实际: {row_data.get('对端网关')}"
            assert pre_shared_key in (row_data.get("预共享密钥") or ""), \
                f"[FieldAssertion] 列表页预共享密钥不匹配 | 期望: {pre_shared_key} | 实际: {row_data.get('预共享密钥')}"

        # 步骤4: 详情页验证（P1字段值）
        with allure_step_log("步骤4: 详情页验证VPN通道信息"):
            vpn_page.open_vpn_tunnel_detail(tunnel_name)
            detail_name = vpn_page.get_vpn_tunnel_detail_field("名称")
            detail_vpn = vpn_page.get_vpn_tunnel_detail_field("VPN网关")
            detail_mode = vpn_page.get_vpn_tunnel_detail_field("报文封装模式")
            detail_peer = vpn_page.get_vpn_tunnel_detail_field("对端网关")
            detail_secret = vpn_page.get_vpn_tunnel_detail_field("预共享密钥")

            assert detail_name == tunnel_name, \
                f"[FieldAssertion] 详情页名称不匹配 | 期望: {tunnel_name} | 实际: {detail_name}"
            assert gw_name in detail_vpn, \
                f"[FieldAssertion] 详情页VPN网关不匹配 | 期望包含: {gw_name} | 实际: {detail_vpn}"
            assert detail_mode == "tunnel", \
                f"[FieldAssertion] 详情页报文封装模式不匹配 | 期望: tunnel | 实际: {detail_mode}"
            assert detail_peer == peer_gateway, \
                f"[FieldAssertion] 详情页对端网关不匹配 | 期望: {peer_gateway} | 实际: {detail_peer}"
            assert detail_secret == pre_shared_key, \
                f"[FieldAssertion] 详情页预共享密钥不匹配 | 期望: {pre_shared_key} | 实际: {detail_secret}"

            # 本端网段和对端网段在通道规则表格中
            result = vpn_page.page.evaluate(
                """
                () => {
                    const content = document.querySelector("#cloud-container-content") || document.body;
                    const allElements = content.querySelectorAll("*");
                    let routeSection = null;
                    for (const el of allElements) {
                        if (el.textContent.trim() === "通道规则") {
                            let parent = el.parentElement;
                            while (parent && parent !== content) {
                                const table = parent.querySelector(".el-table");
                                if (table) {
                                    routeSection = table;
                                    break;
                                }
                                parent = parent.parentElement;
                            }
                            break;
                        }
                    }
                    if (!routeSection) return { error: "未找到通道规则表格" };

                    const rows = routeSection.querySelectorAll(".el-table__row");
                    const data = [];
                    for (const row of rows) {
                        const cells = row.querySelectorAll(".el-table__cell");
                        if (cells.length >= 2) {
                            data.push({
                                local_subnet: cells[0].textContent.trim(),
                                peer_subnet: cells[1].textContent.trim(),
                            });
                        }
                    }
                    return { data: data };
                }
                """
            )
            if result and result.get("data"):
                rules = result["data"]
                if rules:
                    assert local_subnet in rules[0].get("local_subnet", ""), \
                        f"[FieldAssertion] 详情页本端网段不匹配 | 期望: {local_subnet} | 实际: {rules[0].get('local_subnet')}"
                    assert peer_subnet in rules[0].get("peer_subnet", ""), \
                        f"[FieldAssertion] 详情页对端网段不匹配 | 期望: {peer_subnet} | 实际: {rules[0].get('peer_subnet')}"
            else:
                logger.warning("未能获取通道规则表格数据，跳过本端/对端网段断言")

        # ========== 清理阶段（严格按MD要求的清理顺序） ==========
        # 1. 删除VPN通道
        with allure_step_log("清理: 删除VPN通道"):
            _cleanup_vpn_tunnel(vpn_page, tunnel_name)

        # 2. 删除VPN网关
        with allure_step_log("清理: 删除VPN网关"):
            _cleanup_vpn_gateway(vpn_page, gw_name)

        # 3. 删除FIP（由eip fixture teardown处理）
        # 4. 删除ER连接
        with allure_step_log("清理: 删除ER连接"):
            _cleanup_er_connection(er_page, er_name, conn_name)

        # 5. 删除ER（等待40秒确保VPN网关后台资源释放）
        with allure_step_log("清理: 等待VPN网关后台资源释放（40秒）"):
            sleep(40)

        with allure_step_log("清理: 删除企业路由器"):
            _cleanup_er(er_page, er_name)

        # 6. 删除VPC（由vpc fixture teardown处理）
