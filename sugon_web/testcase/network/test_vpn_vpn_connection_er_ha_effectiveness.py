"""VPN通道-连接ER(HA)-生效性验证。

用例编号：420718
"""

from time import sleep

import allure
import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


# ---------------------------------------------------------------------------
# 模块级 helper 函数
# ---------------------------------------------------------------------------


def _cleanup_vpn_tunnel(vpn_page, name):
    """模块级 helper：删除 VPN 通道。

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
    """模块级 helper：删除 VPN 网关。

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


def _cleanup_er_route_rule(er_page, er_name, dest_cidr):
    """模块级 helper：删除 ER 下的路由表规则。

    清理失败仅记录日志，不阻断流程。
    关键导航/点击前均尝试关闭残留对话框，删除失败时重试一次。
    """
    with allure_step_log(f"清理: 删除ER {er_name} 下目的网段 {dest_cidr} 的路由表规则"):
        for attempt in range(2):
            try:
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.goto_route_table_tab(er_name)
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                try:
                    er_page.get_row_by_name(dest_cidr)
                except Exception:
                    logger.info(f"ER路由 {dest_cidr} 已不存在，跳过删除")
                    return
                er_page.er_route_rule_delete(dest_cidr)
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                logger.info(f"ER路由 {dest_cidr} 删除成功")
                return
            except Exception as e:
                logger.warning(f"第{attempt + 1}次清理ER路由 {dest_cidr} 失败: {e}")
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
        logger.warning(f"清理ER路由 {dest_cidr} 最终失败，已记录并继续后续清理")


def _cleanup_er_connection(er_page, er_name, conn_name):
    """模块级 helper：删除ER连接。

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
    """模块级 helper：删除企业路由器。

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


def _cleanup_route_rule(vpc_page, vpc_name, dest_cidr):
    """模块级 helper：删除 VPC 下的自定义路由。

    清理失败仅记录日志，不阻断流程。
    关键导航/点击前均尝试关闭残留对话框，删除失败时重试一次。
    """
    with allure_step_log(f"清理: 删除VPC {vpc_name} 下目的网段 {dest_cidr} 的自定义路由"):
        for attempt in range(2):
            try:
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.goto_service("虚拟私有云")
                vpc_page.goto_submenu("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.goto_vpc_detail(vpc_name)
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.get_by_role("tab", name="路由表").click()
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                try:
                    vpc_page.get_row_by_name(dest_cidr)
                except Exception:
                    logger.info(f"路由 {dest_cidr} 已不存在，跳过删除")
                    return
                vpc_page.route_rule_delete(dest_cidr)
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                logger.info(f"路由 {dest_cidr} 删除成功")
                return
            except Exception as e:
                logger.warning(f"第{attempt + 1}次清理路由 {dest_cidr} 失败: {e}")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
        logger.warning(f"清理路由 {dest_cidr} 最终失败，已记录并继续后续清理")


def _create_vpn_tunnel_with_retry(vpn_page, tunnel_name, max_attempts=2, **kwargs):
    """创建 VPN 通道，弹窗提示失败时关闭弹窗后重试。

    兼容产品缺陷：弹窗可能显示"VPN通道创建失败"，但后端实际已创建资源。
    重试前会先检查资源是否已存在，避免重复创建。
    """
    for attempt in range(1, max_attempts + 1):
        try:
            vpn_page._ensure_vpn_tunnel_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_tunnel_create(name=tunnel_name, **kwargs)
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN通道 {tunnel_name} 第{attempt}次创建提交成功")
            return
        except Exception as e:
            logger.warning(f"VPN通道 {tunnel_name} 第{attempt}次创建尝试失败: {e}")

            # 关闭可能残留的创建弹窗，避免阻塞后续操作
            try:
                vpn_page.close_dialog_if_exists()
                vpn_page.wait_for_page_ready()
            except Exception:
                pass

            # 兼容产品缺陷：弹窗显示失败但资源可能已创建
            try:
                vpn_page._ensure_vpn_tunnel_list()
                vpn_page.wait_for_page_ready()
                vpn_page.get_row_by_name(tunnel_name)
                logger.warning(
                    f"产品缺陷: VPN通道 {tunnel_name} 弹窗显示失败但资源已创建，继续后续步骤"
                )
                return
            except Exception:
                pass

            if attempt < max_attempts:
                logger.info(f"VPN通道 {tunnel_name} 关闭弹窗后准备第{attempt + 1}次创建")
                vpn_page.page.wait_for_timeout(2000)
            else:
                raise


# ---------------------------------------------------------------------------
# Class-scoped fixture：共享前置资源
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def vpn_tunnel_er_ha_env(browser_context, config, ssh_host):
    """创建 VPN 通道连接 ER(HA) 生效性验证所需的全套前置资源（scope=class）。

    创建顺序：
    1. VPC1 (vpn_vpc1, 176.176.13.0/24) + VM1 (vpn_vm1)
    2. VPC2 (vpn_vpc2, 176.176.14.0/24) + VM2 (vpn_vm2)
    3. 分配 3 个弹性公网 IP
    4. 创建 ER1 (vpn_er1, 开启HA) + 添加VPC1为连接
    5. 创建 ER2 (vpn_er2, 开启HA) + 添加VPC2为连接
    6. 创建 VPN 网关1 (vpn_autotest_ipsec_1, IPSEC类型, 连接ER1, 使用fip1)
    7. 创建 VPN 网关2 (vpn_autotest_ipsec_2, IPSEC类型, 连接ER2, 使用fip2)
    8. 创建 VPN 通道1 (vpn_tunnel_1, 连接gw1, 对端fip2)
    9. 创建 VPN 通道2 (vpn_tunnel_2, 连接gw2, 对端fip1)

    清理顺序（严格按需求）：
    1. 删除 ER1 和 ER2 下添加的路由表规则
    2. 删除 VPC1 和 VPC2 下添加的自定义路由
    3. 删除 VPN 通道1 和 VPN 通道2
    4. 删除 VPN 网关1 和 VPN 网关2
    5. 删除 ER1 和 ER2 下的所有连接
    6. 删除 ER1 和 ER2 实例
    7. 释放 3 个弹性公网 IP
    8. 删除 VM1 和 VM2
    9. 删除 VPC1 和 VPC2

    Yields:
        dict: 包含所有前置资源信息的字典。
    """
    from sugon_web.pages.compute import EcsPage
    from sugon_web.pages.network import VpnPage, VpcPage, ErPage
    from sugon_web.pages.ops import OpsPage

    page = _create_logged_in_page(browser_context, config)
    vpn_page = VpnPage(page)
    vpc_page = VpcPage(page)
    ecs_page = EcsPage(page)
    er_page = ErPage(page)
    ops_page = OpsPage(page)

    # 资源命名 - 使用 vpn_ 前缀
    vpc1_name = f"vpn_{random_data(length=4)}"
    vpc1_cidr = "176.176.13.0/24"
    vpc1_subnet = f"subnet-{random_data(length=4)}"
    vpc2_name = f"vpn_{random_data(length=4)}"
    vpc2_cidr = "176.176.14.0/24"
    vpc2_subnet = f"subnet-{random_data(length=4)}"
    er1_name = f"vpn_er_{random_data(length=4)}"
    er2_name = f"vpn_er_{random_data(length=4)}"
    conn1_name = f"vpn_conn_{random_data(length=4)}"
    conn2_name = f"vpn_conn_{random_data(length=4)}"
    gw1_name = f"vpn_autotest_ipsec_{random_data(length=4)}"
    gw2_name = f"vpn_autotest_ipsec_{random_data(length=4)}"
    tunnel1_name = f"vpn_tunnel_{random_data(length=4)}"
    tunnel2_name = f"vpn_tunnel_{random_data(length=4)}"
    vm1_name = f"vpn_vm_{random_data(length=4)}"
    vm2_name = f"vpn_vm_{random_data(length=4)}"
    pre_shared_key = "sugon123"

    eip_list = []
    vm1_ip = None
    vm2_ip = None
    vm1_mfip = None
    vm2_mfip = None

    try:
        # 步骤1: 创建 VPC1
        with allure_step_log("前置: 创建虚拟私有云 vpc1"):
            vpc_page.vpc_create(
                name=vpc1_name,
                subnet_name=vpc1_subnet,
                cidr=vpc1_cidr,
                desc="",
                subnet_desc="",
                network_type="Geneve",
                gateway_mode="分布式网关",
            )
            vpc_page.assert_popup_success("创建虚拟私有云成功")
            vpc_page.assert_status(vpc1_name)
            logger.info(f"VPC1 {vpc1_name} 创建成功")

        # 步骤2: 创建 VPC2
        with allure_step_log("前置: 创建虚拟私有云 vpc2"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.vpc_create(
                name=vpc2_name,
                subnet_name=vpc2_subnet,
                cidr=vpc2_cidr,
                desc="",
                subnet_desc="",
                network_type="Geneve",
                gateway_mode="分布式网关",
            )
            vpc_page.assert_popup_success("创建虚拟私有云成功")
            vpc_page.assert_status(vpc2_name)
            logger.info(f"VPC2 {vpc2_name} 创建成功")

        # 步骤3: 分配 3 个弹性公网IP
        with allure_step_log("前置: 分配3个弹性公网IP"):
            eip_list = vpc_page.eip_allocate(pool="public_net(基础版)", count=3, method="快速选择")
            logger.info(f"分配弹性公网IP: {eip_list}")

        # 步骤4: 创建 VM2 在 VPC2 中
        with allure_step_log("前置: 创建虚机 vpn_vm2"):
            ecs_page.page.set_default_timeout(30000)
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_create(
                basic={"name": vm2_name, "count": 1, "cluster": "Autotest"},
                network={"networks": [{"network": vpc2_name, "subnet": vpc2_subnet}]},
                manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(vm2_name, status="运行", timeout=300, refresh=True)
            row_data = ecs_page.get_row_data(vm2_name)
            ip_text = row_data.get("IP地址", "")
            if "固定:" in ip_text:
                vm2_ip = ip_text.split("固定:")[-1].strip()
            else:
                vm2_ip = ip_text.strip()
            logger.info(f"VM2 {vm2_name} 创建成功, 固定IP: {vm2_ip}")
            ecs_page.page.set_default_timeout(10000)

        # 步骤5: 创建 VM1 在 VPC1 中
        with allure_step_log("前置: 创建虚机 vpn_vm1"):
            ecs_page.page.set_default_timeout(30000)
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_create(
                basic={"name": vm1_name, "count": 1, "cluster": "Autotest"},
                network={"networks": [{"network": vpc1_name, "subnet": vpc1_subnet}]},
                manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(vm1_name, status="运行", timeout=300, refresh=True)
            row_data = ecs_page.get_row_data(vm1_name)
            ip_text = row_data.get("IP地址", "")
            if "固定:" in ip_text:
                vm1_ip = ip_text.split("固定:")[-1].strip()
            else:
                vm1_ip = ip_text.strip()
            logger.info(f"VM1 {vm1_name} 创建成功, 固定IP: {vm1_ip}")
            ecs_page.page.set_default_timeout(10000)

        # 步骤5.5: 为 VM 绑定 MFIP
        with allure_step_log("前置: 为VM绑定管理IP(MFIP)"):
            for vm_name, vm_ip, vm_vpc_name in [(vm1_name, vm1_ip, vpc1_name), (vm2_name, vm2_ip, vpc2_name)]:
                if not vm_ip:
                    continue
                try:
                    ops_page.goto_service("基础设施")
                    ops_page.mfip_create(project="默认项目", network=vm_vpc_name, ip=vm_ip)
                    ops_page.assert_popup_success()
                    logger.info(f"VM {vm_name} (IP: {vm_ip}) MFIP绑定成功")
                except Exception as e:
                    logger.warning(f"VM {vm_name} MFIP绑定可能已存在或失败: {e}")

        # 步骤5.6: 获取 VM 管理 IP
        with allure_step_log("前置: 获取虚机管理IP"):
            vm1_mfip = None
            vm2_mfip = None
            for _ in range(24):
                try:
                    vm1_mfip = ssh_host.find_mfip(vm1_ip)
                    if vm1_mfip:
                        break
                except Exception:
                    pass
                sleep(5)
            for _ in range(24):
                try:
                    vm2_mfip = ssh_host.find_mfip(vm2_ip)
                    if vm2_mfip:
                        break
                except Exception:
                    pass
                sleep(5)
            logger.info(f"VM1 管理IP: {vm1_mfip}, VM2 管理IP: {vm2_mfip}")
            assert vm1_mfip is not None, \
                f"[BackendAssertion] VM1管理IP未获取 | 固定IP={vm1_ip} | 无法进行SSH连接"
            assert vm2_mfip is not None, \
                f"[BackendAssertion] VM2管理IP未获取 | 固定IP={vm2_ip} | 无法进行SSH连接"

        # 步骤6: 创建 ER1（开启HA）
        with allure_step_log("前置: 创建企业路由器ER1（开启HA）"):
            er_page.er_create(name=er1_name, cluster_name="Autotest", ha_enable=True)
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER1 {er1_name} 创建提交成功")

        with allure_step_log("前置: 等待ER1状态变为运行中"):
            er_page._ensure_list_page()
            er_page.assert_status(
                er1_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        # 步骤7: 创建 ER2（开启HA）
        with allure_step_log("前置: 创建企业路由器ER2（开启HA）"):
            er_page.er_create(name=er2_name, cluster_name="Autotest", ha_enable=True)
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER2 {er2_name} 创建提交成功")

        with allure_step_log("前置: 等待ER2状态变为运行中"):
            er_page._ensure_list_page()
            er_page.assert_status(
                er2_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        # 步骤8: 添加VPC1为ER1的连接
        with allure_step_log("前置: 添加VPC1为ER1的连接"):
            er_page.goto_connection_tab(er1_name)
            er_page.er_connection_create(
                name=conn1_name,
                conn_type="VPC",
                vpc_name=vpc1_name,
                subnet_name=vpc1_subnet,
            )
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER1连接 {conn1_name} 创建提交成功")

        with allure_step_log("前置: 等待ER1连接就绪（10秒）"):
            sleep(10)

        # 步骤9: 添加VPC2为ER2的连接
        with allure_step_log("前置: 添加VPC2为ER2的连接"):
            er_page.goto_connection_tab(er2_name)
            er_page.er_connection_create(
                name=conn2_name,
                conn_type="VPC",
                vpc_name=vpc2_name,
                subnet_name=vpc2_subnet,
            )
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER2连接 {conn2_name} 创建提交成功")

        with allure_step_log("前置: 等待ER2连接就绪（10秒）"):
            sleep(10)

        # 步骤10: 创建 VPN 网关1（IPSEC类型，连接ER1，使用fip1）
        with allure_step_log("前置: 创建VPN网关1"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_gateway_create(
                name=gw1_name,
                cluster="Autotest",
                vpn_type="IPSEC",
                resource_pool="public_net(基础版)",
                fip_address=eip_list[0] if eip_list else "",
                connection_type="企业路由器",
                er_name=er1_name,
                flavor="虚拟专用网络数据型",
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN网关1 {gw1_name} 创建提交成功")

        with allure_step_log("前置: 等待VPN网关1状态变为运行中"):
            vpn_page.assert_status(
                gw1_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("前置: 等待VPN网关1就绪（10秒）"):
            vpn_page.page.wait_for_timeout(10000)

        # 步骤11: 创建 VPN 网关2（IPSEC类型，连接ER2，使用fip2）
        with allure_step_log("前置: 创建VPN网关2"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_gateway_create(
                name=gw2_name,
                cluster="Autotest",
                vpn_type="IPSEC",
                resource_pool="public_net(基础版)",
                fip_address=eip_list[1] if len(eip_list) > 1 else "",
                connection_type="企业路由器",
                er_name=er2_name,
                flavor="虚拟专用网络数据型",
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN网关2 {gw2_name} 创建提交成功")

        with allure_step_log("前置: 等待VPN网关2状态变为运行中"):
            vpn_page.assert_status(
                gw2_name,
                status="运行中",
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        with allure_step_log("前置: 等待VPN网关2就绪（10秒）"):
            vpn_page.page.wait_for_timeout(10000)

        # 获取VPN网关实际公网IP
        with allure_step_log("前置: 获取VPN网关实际公网IP"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.open_vpn_gateway_detail(gw1_name)
            vpn_page.wait_for_page_ready()
            gw1_actual_ip = vpn_page.get_vpn_gateway_detail_field("公网IP地址")
            logger.info(f"VPN网关1 {gw1_name} 实际公网IP: {gw1_actual_ip}")

            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.open_vpn_gateway_detail(gw2_name)
            vpn_page.wait_for_page_ready()
            gw2_actual_ip = vpn_page.get_vpn_gateway_detail_field("公网IP地址")
            logger.info(f"VPN网关2 {gw2_name} 实际公网IP: {gw2_actual_ip}")

        # 步骤12: 创建 VPN 通道1
        with allure_step_log("前置: 创建VPN通道1"):
            _create_vpn_tunnel_with_retry(
                vpn_page,
                tunnel1_name,
                vpn_gateway_name=gw1_name,
                encapsulation_mode="tunnel",
                peer_gateway=gw2_actual_ip,
                pre_shared_key=pre_shared_key,
                local_subnet=vpc1_cidr,
                peer_subnet=vpc2_cidr,
            )

        vpn_page.wait_for_page_ready()

        # 步骤13: 创建 VPN 通道2
        with allure_step_log("前置: 创建VPN通道2"):
            _create_vpn_tunnel_with_retry(
                vpn_page,
                tunnel2_name,
                vpn_gateway_name=gw2_name,
                encapsulation_mode="tunnel",
                peer_gateway=gw1_actual_ip,
                pre_shared_key=pre_shared_key,
                local_subnet=vpc2_cidr,
                peer_subnet=vpc1_cidr,
            )

        created_resources = {
            "vpc1_name": vpc1_name,
            "vpc1_cidr": vpc1_cidr,
            "vpc2_name": vpc2_name,
            "vpc2_cidr": vpc2_cidr,
            "er1_name": er1_name,
            "er2_name": er2_name,
            "conn1_name": conn1_name,
            "conn2_name": conn2_name,
            "eip_list": eip_list,
            "gw1_name": gw1_name,
            "gw2_name": gw2_name,
            "tunnel1_name": tunnel1_name,
            "tunnel2_name": tunnel2_name,
            "pre_shared_key": pre_shared_key,
            "vm1_name": vm1_name,
            "vm1_ip": vm1_ip,
            "vm1_mfip": vm1_mfip,
            "vm2_name": vm2_name,
            "vm2_ip": vm2_ip,
            "vm2_mfip": vm2_mfip,
        }

        yield created_resources

    except Exception:
        logger.warning("前置资源创建失败，执行紧急清理")
        raise

    finally:
        # 清理顺序（严格按需求）：
        # 1. 删除 ER1 和 ER2 下添加的路由表规则
        # 2. 删除 VPC1 和 VPC2 下添加的自定义路由
        # 3. 删除 VPN 通道1 和 VPN 通道2
        # 4. 删除 VPN 网关1 和 VPN 网关2
        # 5. 删除 ER1 和 ER2 下的所有连接
        # 6. 删除 ER1 和 ER2 实例
        # 7. 释放 3 个弹性公网IP
        # 8. 删除 VM1 和 VM2
        # 9. 删除 VPC1 和 VPC2
        with allure_step_log("Teardown: 按顺序清理资源"):
            # 1. 删除 ER 路由表规则
            _cleanup_er_route_rule(er_page, er1_name, vpc2_cidr)
            _cleanup_er_route_rule(er_page, er2_name, vpc1_cidr)
            # 2. 删除 VPC 自定义路由
            _cleanup_route_rule(vpc_page, vpc1_name, vpc2_cidr)
            _cleanup_route_rule(vpc_page, vpc2_name, vpc1_cidr)
            # 3. 删除 VPN 通道
            _cleanup_vpn_tunnel(vpn_page, tunnel1_name)
            _cleanup_vpn_tunnel(vpn_page, tunnel2_name)
            # 4. 删除 VPN 网关
            _cleanup_vpn_gateway(vpn_page, gw1_name)
            _cleanup_vpn_gateway(vpn_page, gw2_name)
            # 5. 删除 ER 连接
            _cleanup_er_connection(er_page, er1_name, conn1_name)
            _cleanup_er_connection(er_page, er2_name, conn2_name)
            # 6. 删除 ER 实例（等待40秒确保VPN网关后台资源释放）
            with allure_step_log("清理: 等待VPN网关后台资源释放（40秒）"):
                sleep(40)
            _cleanup_er(er_page, er1_name)
            _cleanup_er(er_page, er2_name)
            # 7. 释放 3 个弹性公网IP
            if eip_list:
                for eip in eip_list:
                    try:
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.goto_submenu("弹性公网IPv4")
                        vpc_page.wait_for_page_ready()
                        vpc_page.search(eip)
                        vpc_page.get_row_by_name(eip)
                        vpc_page.eip_release(eip)
                        vpc_page.assert_deleted(eip)
                    except Exception:
                        logger.info(f"EIP {eip} 已不存在，跳过释放")
                    vpc_page.btn_reset.click()
            # 8. 删除 VM1 和 VM2
            for vm_name in [vm1_name, vm2_name]:
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.goto_submenu("弹性云服务器")
                    ecs_page.wait_for_page_ready()
                    ecs_page.search(vm_name)
                    ecs_page.get_row_by_name(vm_name)
                    ecs_page.ecs_remove(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=300)
                except Exception:
                    logger.info(f"虚机 {vm_name} 已不存在，跳过删除")
                # 回收站彻底删除
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.goto_submenu("回收站")
                    ecs_page.wait_for_page_ready()
                    ecs_page.search(vm_name)
                    ecs_page.get_row_by_name(vm_name)
                    ecs_page.ecs_recover_delete(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=300)
                except Exception:
                    logger.info(f"虚机 {vm_name} 不在回收站中，可能已彻底删除")
            # 9. 删除 VPC1 和 VPC2
            for vpc_name in [vpc1_name, vpc2_name]:
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.wait_for_page_ready()
                    vpc_page.get_row_by_name(vpc_name)
                    vpc_page.vpc_delete(vpc_name)
                    vpc_page.page.reload()
                    vpc_page.wait_for_page_ready()
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.assert_deleted(vpc_name)
                except Exception:
                    logger.info(f"VPC {vpc_name} 已不存在，跳过删除")

        page.close()


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('VPN通道连接ER(HA)生效性验证')
class TestVpnVpnConnectionErHaEffectiveness:
    """VPN 通道连接 ER(HA) 生效性验证（用例 420718）。

    单一场景，测试数据不可复用，前置资源在 class-scoped fixture 中创建，
    测试完成后统一清理。
    """

    @allure.title("VPN通道-连接ER(HA)-生效性验证")
    def test_vpn_vpn_connection_er_ha_effectiveness(self, page, vpn_tunnel_er_ha_env, ssh_vm):
        """验证 VPN 通道连接 ER(HA) 的生效性（用例 420718）。

        步骤：
        1. 在 vpn_vpc1 下添加自定义路由（目的网段 vpc2_cidr，下一跳类型 ER，下一跳 er1）
        2. 在 vpn_vpc2 下添加自定义路由（目的网段 vpc1_cidr，下一跳类型 ER，下一跳 er2）
        3. 在 vpn_er1 下添加自定义路由（目的网段 vpc2_cidr，下一跳类型 VPN，下一跳 gw1）
        4. 在 vpn_er2 下添加自定义路由（目的网段 vpc1_cidr，下一跳类型 VPN，下一跳 gw2）
        5. 从 vpn_vm1 ping vpn_vm2 验证连通性
        6. 从 vpn_vm2 ping vpn_vm1 验证双向连通性
        """
        from sugon_web.pages.network import VpnPage, VpcPage, ErPage

        vpn_page = VpnPage(page)
        vpc_page = VpcPage(page)
        er_page = ErPage(page)

        vpc1_name = vpn_tunnel_er_ha_env["vpc1_name"]
        vpc1_cidr = vpn_tunnel_er_ha_env["vpc1_cidr"]
        vpc2_name = vpn_tunnel_er_ha_env["vpc2_name"]
        vpc2_cidr = vpn_tunnel_er_ha_env["vpc2_cidr"]
        er1_name = vpn_tunnel_er_ha_env["er1_name"]
        er2_name = vpn_tunnel_er_ha_env["er2_name"]
        conn1_name = vpn_tunnel_er_ha_env["conn1_name"]
        conn2_name = vpn_tunnel_er_ha_env["conn2_name"]
        gw1_name = vpn_tunnel_er_ha_env["gw1_name"]
        gw2_name = vpn_tunnel_er_ha_env["gw2_name"]
        vm1_mfip = vpn_tunnel_er_ha_env["vm1_mfip"]
        vm2_mfip = vpn_tunnel_er_ha_env["vm2_mfip"]
        vm2_ip = vpn_tunnel_er_ha_env["vm2_ip"]
        vm1_ip = vpn_tunnel_er_ha_env["vm1_ip"]

        # 步骤1: 在 vpn_vpc1 下添加自定义路由
        with allure_step_log("步骤1: 在vpn_vpc1下添加自定义路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc1_name,
                dest_cidr=vpc2_cidr,
                next_hop=er1_name,
                next_hop_type="企业路由器",
                ip_version="IPv4",
            )
            vpc_page.assert_popup_success("新建路由表规则成功")
            logger.info(f"VPC1 路由添加成功: 目的网段={vpc2_cidr}, 下一跳={er1_name}")

        # P1: 验证 VPC1 路由表列表字段值
        with allure_step_log("验证: VPC1路由表列表字段值"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.wait_for_page_ready()
            vpc_page.goto_vpc_detail(vpc1_name)
            vpc_page.wait_for_page_ready()
            vpc_page.goto_route_tab()
            vpc_page.wait_for_page_ready()
            row_data = vpc_page.get_row_data(vpc2_cidr)
            assert vpc2_cidr in (row_data.get("目的地址") or ""), \
                f"[FieldAssertion] 路由表目的地址不匹配 | 期望: {vpc2_cidr} | 实际: {row_data.get('目的地址')}"
            assert "企业路由器" in (row_data.get("下一跳类型") or ""), \
                f"[FieldAssertion] 路由表下一跳类型不匹配 | 期望包含: 企业路由器 | 实际: {row_data.get('下一跳类型')}"
            assert er1_name in (row_data.get("下一跳") or ""), \
                f"[FieldAssertion] 路由表下一跳不匹配 | 期望包含: {er1_name} | 实际: {row_data.get('下一跳')}"
            logger.info(f"VPC1 路由字段验证通过: {row_data}")

        # 步骤2: 在 vpn_vpc2 下添加自定义路由
        with allure_step_log("步骤2: 在vpn_vpc2下添加自定义路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc2_name,
                dest_cidr=vpc1_cidr,
                next_hop=er2_name,
                next_hop_type="企业路由器",
                ip_version="IPv4",
            )
            vpc_page.assert_popup_success("新建路由表规则成功")
            logger.info(f"VPC2 路由添加成功: 目的网段={vpc1_cidr}, 下一跳={er2_name}")

        # P1: 验证 VPC2 路由表列表字段值
        with allure_step_log("验证: VPC2路由表列表字段值"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.wait_for_page_ready()
            vpc_page.goto_vpc_detail(vpc2_name)
            vpc_page.wait_for_page_ready()
            vpc_page.goto_route_tab()
            vpc_page.wait_for_page_ready()
            row_data = vpc_page.get_row_data(vpc1_cidr)
            assert vpc1_cidr in (row_data.get("目的地址") or ""), \
                f"[FieldAssertion] 路由表目的地址不匹配 | 期望: {vpc1_cidr} | 实际: {row_data.get('目的地址')}"
            assert "企业路由器" in (row_data.get("下一跳类型") or ""), \
                f"[FieldAssertion] 路由表下一跳类型不匹配 | 期望包含: 企业路由器 | 实际: {row_data.get('下一跳类型')}"
            assert er2_name in (row_data.get("下一跳") or ""), \
                f"[FieldAssertion] 路由表下一跳不匹配 | 期望包含: {er2_name} | 实际: {row_data.get('下一跳')}"
            logger.info(f"VPC2 路由字段验证通过: {row_data}")

        # 步骤3: 在 vpn_er1 下添加自定义路由
        with allure_step_log("步骤3: 在vpn_er1下添加自定义路由"):
            er_page.goto_route_table_tab(er1_name)
            er_page.wait_for_page_ready()
            er_page.er_route_rule_create(
                destination=vpc2_cidr,
                next_hop_type="VPN",
                connection=conn1_name,
                next_hop=gw1_name,
            )
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER1 路由添加成功: 目的网段={vpc2_cidr}, 下一跳类型=VPN, 下一跳={gw1_name}")

        # P1: 验证 ER1 路由表列表字段值
        with allure_step_log("验证: ER1路由表列表字段值"):
            er_page.goto_route_table_tab(er1_name)
            er_page.wait_for_page_ready()
            row_data = er_page.get_row_data(vpc2_cidr)
            assert vpc2_cidr in (row_data.get("目的地址") or ""), \
                f"[FieldAssertion] ER路由表目的地址不匹配 | 期望: {vpc2_cidr} | 实际: {row_data.get('目的地址')}"
            assert "虚拟专用网络" in (row_data.get("下一跳类型") or ""), \
                f"[FieldAssertion] ER路由表下一跳类型不匹配 | 期望包含: 虚拟专用网络 | 实际: {row_data.get('下一跳类型')}"
            assert gw1_name in (row_data.get("下一跳") or ""), \
                f"[FieldAssertion] ER路由表下一跳不匹配 | 期望包含: {gw1_name} | 实际: {row_data.get('下一跳')}"
            logger.info(f"ER1 路由字段验证通过: {row_data}")

        # 步骤4: 在 vpn_er2 下添加自定义路由
        with allure_step_log("步骤4: 在vpn_er2下添加自定义路由"):
            er_page.goto_route_table_tab(er2_name)
            er_page.wait_for_page_ready()
            er_page.er_route_rule_create(
                destination=vpc1_cidr,
                next_hop_type="VPN",
                connection=conn2_name,
                next_hop=gw2_name,
            )
            er_page.assert_popup_success(timeout=30)
            logger.info(f"ER2 路由添加成功: 目的网段={vpc1_cidr}, 下一跳类型=VPN, 下一跳={gw2_name}")

        # P1: 验证 ER2 路由表列表字段值
        with allure_step_log("验证: ER2路由表列表字段值"):
            er_page.goto_route_table_tab(er2_name)
            er_page.wait_for_page_ready()
            row_data = er_page.get_row_data(vpc1_cidr)
            assert vpc1_cidr in (row_data.get("目的地址") or ""), \
                f"[FieldAssertion] ER路由表目的地址不匹配 | 期望: {vpc1_cidr} | 实际: {row_data.get('目的地址')}"
            assert "虚拟专用网络" in (row_data.get("下一跳类型") or ""), \
                f"[FieldAssertion] ER路由表下一跳类型不匹配 | 期望包含: 虚拟专用网络 | 实际: {row_data.get('下一跳类型')}"
            assert gw2_name in (row_data.get("下一跳") or ""), \
                f"[FieldAssertion] ER路由表下一跳不匹配 | 期望包含: {gw2_name} | 实际: {row_data.get('下一跳')}"
            logger.info(f"ER2 路由字段验证通过: {row_data}")

        # 步骤5: 从 vpn_vm1 ping vpn_vm2 验证连通性
        with allure_step_log("步骤5: 从vpn_vm1 ping vpn_vm2验证连通性"):
            assert vm1_mfip is not None, \
                f"[BackendAssertion] VM1管理IP未获取 | 无法进行SSH连接"
            assert vm2_ip is not None, \
                f"[BackendAssertion] VM2 IP未获取 | 无法进行ping测试"

            ssh_vm.connect(vm1_mfip)
            logger.info(f"SSH连接到 vm1 ({vm1_mfip}) 成功")

            # 使用 SSH 轮询等待 VPN 协商完成
            ping_ready = False
            for _ in range(30):
                result = ssh_vm.run(f"ping -c 1 -W 2 {vm2_ip}", return_rc=True)
                if result["rc"] == 0:
                    logger.info("VPN通道协商完成，ping已通")
                    ping_ready = True
                    break
                sleep(5)
            if not ping_ready:
                logger.warning("VPN通道协商等待超时，继续执行测试")

            ping_cmd = f"ping -c 4 {vm2_ip}"
            result = ssh_vm.run(ping_cmd, return_rc=True)
            logger.info(f"ping vm2 结果: rc={result['rc']}, stdout={result['stdout']}")

            assert result["rc"] == 0, \
                f"[BackendAssertion] ping测试失败 | 期望: 0丢包 | 实际: rc={result['rc']} | stdout: {result.get('stdout', '')}"
            assert "0% packet loss" in result["stdout"] or "4 received" in result["stdout"], \
                f"[BackendAssertion] ping丢包 | 期望: 0%丢包 | 实际: {result['stdout']}"
            logger.info(f"vm1 ping vm2 测试通过: {result['stdout']}")

        # 步骤6: 从 vpn_vm2 ping vpn_vm1 验证双向连通性
        with allure_step_log("步骤6: 从vpn_vm2 ping vpn_vm1验证双向连通性"):
            assert vm2_mfip is not None, \
                f"[BackendAssertion] VM2管理IP未获取 | 无法进行SSH连接"
            assert vm1_ip is not None, \
                f"[BackendAssertion] VM1 IP未获取 | 无法进行ping测试"

            ssh_vm.connect(vm2_mfip)
            logger.info(f"SSH连接到 vm2 ({vm2_mfip}) 成功")

            ping_cmd = f"ping -c 4 {vm1_ip}"
            result = ssh_vm.run(ping_cmd, return_rc=True)
            logger.info(f"ping vm1 结果: rc={result['rc']}, stdout={result['stdout']}")

            assert result["rc"] == 0, \
                f"[BackendAssertion] ping测试失败 | 期望: 0丢包 | 实际: rc={result['rc']} | stdout: {result.get('stdout', '')}"
            assert "0% packet loss" in result["stdout"] or "4 received" in result["stdout"], \
                f"[BackendAssertion] ping丢包 | 期望: 0%丢包 | 实际: {result['stdout']}"
            logger.info(f"vm2 ping vm1 测试通过: {result['stdout']}")
