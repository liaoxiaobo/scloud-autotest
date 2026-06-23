"""SSL客户端-连接VPC-修改路由控制生效性验证。

用例编号：5578
"""

import os
import tempfile
from datetime import datetime, timedelta

import allure
import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.compute import EcsPage
from sugon_web.pages.network import VpnPage, VpcPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


# ---------------------------------------------------------------------------
# 模块级 helper 函数
# ---------------------------------------------------------------------------


def _cleanup_ssl_client(vpn_page, name):
    """模块级 helper：删除 SSL 客户端。

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


def _cleanup_eip(vpc_page, eip_list, pool="public_net(基础版)"):
    """模块级 helper：释放弹性公网 IP。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 释放弹性公网IP"):
        if not eip_list:
            return
        try:
            current_ips = eip_list if isinstance(eip_list, list) else [eip_list]
            for current_ip in current_ips:
                try:
                    vpc_page.switch_eip_pool(pool)
                    vpc_page.search(current_ip)
                    if vpc_page.get_eip_list():
                        vpc_page.eip_release(current_ip)
                        vpc_page.assert_deleted(current_ip)
                    vpc_page.btn_reset.click()
                except Exception as e:
                    logger.warning(f"释放弹性公网IP {current_ip} 失败: {e}")
        except Exception as e:
            logger.warning(f"清理弹性公网IP时出错: {e}")


def _cleanup_vpc(vpc_page, name):
    """模块级 helper：删除 VPC。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log("清理: 删除VPC"):
        try:
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            try:
                vpc_page.get_row_by_name(name)
            except Exception:
                logger.info(f"VPC {name} 已不存在，跳过删除")
                return
            vpc_page.vpc_delete(name)
            vpc_page.page.reload()
            vpc_page.wait_for_page_ready()
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.assert_deleted(name)
        except Exception as e:
            logger.warning(f"清理VPC {name} 失败: {e}")


def _get_vm_ip_from_row(ecs_page, vm_name):
    """从 ECS 列表页获取虚机的固定 IP 地址。

    Args:
        ecs_page: ECS 页面对象。
        vm_name: 虚机名称。

    Returns:
        str: 虚机的固定 IP 地址。
    """
    row_data = ecs_page.get_row_data(vm_name)
    ip_text = row_data.get("IP地址", "")
    if "固定:" in ip_text:
        ip_parts = ip_text.split("固定:")
        return ip_parts[-1].strip()
    return ip_text.strip()


def _cleanup_vm(ecs_page, name):
    """模块级 helper：删除虚机并从回收站彻底删除。

    清理失败仅记录日志，不阻断流程。
    """
    with allure_step_log(f"清理: 删除虚机 {name}"):
        try:
            logger.info(f"进入 ECS 列表页删除虚机 {name}")
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.search(name)
            ecs_page.wait_for_page_ready()
            try:
                ecs_page.get_row_by_name(name)
            except Exception:
                logger.info(f"虚机 {name} 已不在 ECS 列表中，检查回收站")
            else:
                ecs_page.ecs_remove(name)
                ecs_page.assert_deleted(name, timeout=300)
                logger.info(f"虚机 {name} 已移入回收站")

            logger.info(f"进入 ECS 回收站彻底删除虚机 {name}")
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("回收站")
            ecs_page.wait_for_page_ready()
            ecs_page.search(name)
            ecs_page.wait_for_page_ready()
            try:
                ecs_page.get_row_by_name(name)
            except Exception:
                logger.info(f"虚机 {name} 不在回收站中，可能已彻底删除")
                return
            ecs_page.ecs_recover_delete(name)
            ecs_page.assert_deleted(name, timeout=300)
            logger.info(f"虚机 {name} 已从回收站彻底删除")
        except Exception as e:
            logger.warning(f"清理虚机 {name} 失败: {e}")


def _unbind_eip_from_vm(vpc_page, vm_name, eip):
    """模块级 helper：为虚机解绑弹性公网 IP。

    清理失败仅记录日志，不阻断流程。
    优先使用 ECS 页面对象标准方法解绑，失败后再回退到 EIP 列表页释放。
    """
    with allure_step_log(f"清理: 为虚机 {vm_name} 解绑弹性公网IP {eip}"):
        try:
            logger.info(f"进入 ECS 列表页为虚机 {vm_name} 解绑 EIP {eip}")
            ecs_page = EcsPage(vpc_page.page)
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.search(vm_name)
            ecs_page.wait_for_page_ready()
            try:
                ecs_page.get_row_by_name(vm_name)
            except Exception:
                logger.info(f"虚机 {vm_name} 已不在 ECS 列表中，尝试 EIP 列表页确认")
            else:
                try:
                    ecs_page.ecs_unbind_pub_ip(vm_name, eip)
                    ecs_page.wait_for_page_ready()
                    ecs_page.wait_for_operation_complete(timeout=5)
                    logger.info(f"通过 ECS 列表页解绑弹性公网IP {eip} 完成")
                    return
                except Exception as e:
                    logger.warning(f"ECS 列表页标准解绑失败，回退到 EIP 列表页: {e}")

            logger.info(f"进入 EIP 列表页确认 EIP {eip} 状态")
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("弹性公网IPv4")
            vpc_page.wait_for_page_ready()
            vpc_page.search(eip)
            vpc_page.wait_for_page_ready()
            try:
                row = vpc_page.get_row_by_name(eip)
                row_text = row.inner_text()
                if "未绑定" in row_text or "未使用" in row_text:
                    logger.info(f"EIP {eip} 已处于未绑定状态")
                    return
            except Exception:
                logger.info(f"EIP {eip} 在列表中未找到，可能已释放")
                return

            logger.warning(f"EIP {eip} 仍未解绑，尝试在 EIP 列表页直接释放")
            vpc_page.eip_release(eip)
            logger.info(f"通过 EIP 列表页释放 {eip} 完成")
        except Exception as e:
            logger.warning(f"为虚机 {vm_name} 解绑弹性公网IP {eip} 失败: {e}")


def _assert_ssl_client_created(vpn_page, ssl_name, timeout=30):
    """断言 SSL 客户端创建成功，处理产品缺陷：弹窗显示失败但资源已创建。

    产品缺陷：SSL 客户端创建弹窗可能显示"SSL客户端创建失败"，
    但后端实际已创建资源。此函数在弹窗显示失败时验证资源是否存在。
    """
    try:
        vpn_page.assert_popup_success(timeout=timeout)
    except AssertionError as e:
        error_msg = str(e)
        if "SSL客户端创建失败" in error_msg:
            try:
                vpn_page.close_dialog_if_exists()
                vpn_page.wait_for_page_ready()
            except Exception:
                pass
            try:
                vpn_page._ensure_ssl_client_list()
                vpn_page.wait_for_page_ready()
                vpn_page.get_row_by_name(ssl_name)
                logger.warning(
                    f"产品缺陷: SSL客户端创建弹窗显示失败，但资源已创建: {ssl_name}"
                )
                return
            except Exception:
                pass
        raise


def _wait_for_ssl_client_online(vpn_page, ssl_name, max_attempts=10):
    """轮询等待 SSL 客户端在线状态变为"在线"。

    Args:
        vpn_page: VPN 页面对象。
        ssl_name: SSL 客户端名称。
        max_attempts: 最大轮询次数，默认 10 次。

    Returns:
        bool: True=在线状态已恢复，False=未恢复。
    """
    for _ in range(max_attempts):
        vpn_page._ensure_ssl_client_list()
        vpn_page.wait_for_page_ready()
        vpn_page.btn_refresh.click()
        vpn_page.wait_for_page_ready()
        row_data = vpn_page.get_ssl_client_row_data(ssl_name)
        online_status = row_data.get("在线状态", "")
        if "在线" in online_status:
            logger.info(f"SSL客户端 {ssl_name} 在线状态已恢复: {online_status}")
            return True
    logger.warning(f"SSL客户端 {ssl_name} 在线状态未在预期轮询次数内恢复")
    return False


def _wait_for_ssl_client_online_with_interval(vpn_page, ssl_name, max_attempts=8):
    """按需求等待 SSL 客户端在线状态恢复，每隔约30秒刷新一次。

    使用 wait_for_page_ready 作为轮询间隔，避免 time.sleep。

    Args:
        vpn_page: VPN 页面对象。
        ssl_name: SSL 客户端名称。
        max_attempts: 最大轮询次数，默认 8 次（约 4 分钟）。

    Returns:
        bool: True=在线状态已恢复，False=未恢复。
    """
    for attempt in range(max_attempts):
        vpn_page._ensure_ssl_client_list()
        vpn_page.wait_for_page_ready()
        vpn_page.btn_refresh.click()
        vpn_page.wait_for_page_ready()
        row_data = vpn_page.get_ssl_client_row_data(ssl_name)
        online_status = row_data.get("在线状态", "")
        if "在线" in online_status:
            logger.info(f"SSL客户端 {ssl_name} 在线状态已恢复: {online_status}")
            return True
        if attempt < max_attempts - 1:
            # 使用 wait_for_page_ready 作为轮询间隔，避免 time.sleep
            for _ in range(3):
                vpn_page.wait_for_page_ready()
    logger.warning(f"SSL客户端 {ssl_name} 在线状态未在 {max_attempts} 次轮询后恢复")
    return False


# ---------------------------------------------------------------------------
# Class-scoped fixture：共享前置资源
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def ssl_client_route_env(browser_context, config):
    """创建 SSL 客户端修改路由控制生效性验证所需的全套前置资源（scope=class）。

    创建顺序：
    1. VPC1 (vpn_vpc1, 176.176.7.0/24) + VM1 (vpn_vm1)
    2. 分配 3 个弹性公网 IP
    3. 创建 VPN 网关 (vpn-gw-ssl-1, SSL类型, 基础版, 连接VPC1)
    4. 创建 SSL 客户端 (ssl-client)
    5. VPC2 (vpn_vpc2, 153.153.153.0/24) + VM2 (vpn_vm2) + 绑定EIP

    清理顺序（严格按需求）：
    1. 删除 SSL 客户端
    2. 删除 VPN 网关
    3. VM2 解绑 EIP
    4. 释放 3 个弹性公网 IP
    5. 删除 VM1 和 VM2
    6. 删除 VPC1 和 VPC2

    Yields:
        dict: 包含所有前置资源信息的字典。
    """
    page = _create_logged_in_page(browser_context, config)
    vpn_page = VpnPage(page)
    vpc_page = VpcPage(page)
    ecs_page = EcsPage(page)

    vpc1_name = f"vpn_{random_data(length=4)}"
    vpc1_cidr = "176.176.7.0/24"
    vpc1_subnet = f"subnet-{random_data(length=4)}"
    vpc2_name = f"vpn_{random_data(length=4)}"
    vpc2_cidr = "153.153.153.0/24"
    vpc2_subnet = f"subnet-{random_data(length=4)}"
    gw_name = f"vpn-gw-ssl-{random_data(length=4)}"
    ssl_name = f"ssl-client-{random_data(length=4)}"
    vm1_name = f"vpn_vm-{random_data(length=4)}"
    vm2_name = f"vpn_vm-{random_data(length=4)}"
    expiration_time = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    eip_list = []
    vm1_ip = None
    vm2_ip = None
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

        # 步骤2: 分配 3 个弹性公网 IP
        with allure_step_log("前置: 分配3个弹性公网IP"):
            eip_list = vpc_page.eip_allocate(pool="public_net(基础版)", count=3, method="快速选择")
            logger.info(f"分配弹性公网IP: {eip_list}")

        # 步骤3: 创建 VPN 网关
        with allure_step_log("前置: 创建VPN网关"):
            vpn_page._ensure_vpn_gateway_list()
            vpn_page.wait_for_page_ready()
            vpn_page.vpn_gateway_create(
                name=gw_name,
                cluster="Autotest",
                vpn_type="SSL",
                resource_pool="public_net(基础版)",
                fip_address=eip_list[0] if eip_list else "",
                connection_type="虚拟私有云",
                vpc_name=vpc1_name,
                flavor="虚拟专用网络数据型",
                resource_pool_tag="基础版",
                client_subnet="17.17.17.0/24",
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

        # 步骤4: 创建 SSL 客户端
        with allure_step_log("前置: 创建SSL客户端"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

            ssl_created = False
            for attempt in range(2):
                try:
                    vpn_page.ssl_client_create(
                        name=ssl_name,
                        vpn_gateway_name=gw_name,
                        expiration_time=expiration_time,
                        access_cidr=vpc1_cidr,
                    )
                    try:
                        vpn_page.close_dialog_if_exists()
                        vpn_page.wait_for_page_ready()
                    except Exception:
                        pass
                    _assert_ssl_client_created(vpn_page, ssl_name, timeout=30)
                    ssl_created = True
                    break
                except AssertionError:
                    if attempt == 0:
                        logger.warning(f"SSL客户端创建失败，尝试清理并重试...")
                        try:
                            vpn_page.close_dialog_if_exists()
                            vpn_page._ensure_ssl_client_list()
                            vpn_page.wait_for_page_ready()
                            vpn_page.get_row_by_name(ssl_name)
                            vpn_page.ssl_client_delete(ssl_name)
                            vpn_page.assert_deleted(ssl_name, timeout=60)
                        except Exception:
                            pass
                    else:
                        raise

            if not ssl_created:
                raise AssertionError(f"SSL客户端 {ssl_name} 创建失败，重试后仍未成功")

            logger.info(f"SSL客户端 {ssl_name} 创建提交成功")

        with allure_step_log("前置: 等待SSL客户端出现在列表中"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            vpn_page.assert_list_contain(ssl_name, column_name="名称")

        # 步骤5: 创建 VM1 在 VPC1 中
        with allure_step_log("前置: 创建虚机 vpn_vm1"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_create(
                basic={"name": vm1_name, "count": 1, "cluster": "Autotest"},
                network={"networks": [{"network": vpc1_name, "subnet": vpc1_subnet}]},
                manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(vm1_name, status="运行", timeout=300, refresh=True)
            vm1_ip = _get_vm_ip_from_row(ecs_page, vm1_name)
            logger.info(f"VM1 {vm1_name} 创建成功, IP: {vm1_ip}")

        # 步骤6: 创建 VPC2
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

        # 步骤7: 创建 VM2 在 VPC2 中并绑定 EIP
        with allure_step_log("前置: 创建虚机 vpn_vm2 并绑定EIP"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.wait_for_page_ready()
            ecs_page.ecs_create(
                basic={"name": vm2_name, "count": 1, "cluster": "Autotest"},
                network={"networks": [{"network": vpc2_name, "subnet": vpc2_subnet}]},
                manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(vm2_name, status="运行", timeout=300, refresh=True)
            vm2_ip = _get_vm_ip_from_row(ecs_page, vm2_name)
            logger.info(f"VM2 {vm2_name} 创建成功, IP: {vm2_ip}")

            if len(eip_list) >= 2:
                ecs_page.ecs_bind_pub_ip(
                    name=vm2_name,
                    subnet=vpc2_subnet,
                    pub_net="public_net(基础版)",
                    eip_ip=eip_list[1],
                )
                ecs_page.assert_popup_success("执行成功")
                vm2_mfip = eip_list[1]
                logger.info(f"VM2 {vm2_name} 绑定弹性公网IP {vm2_mfip} 成功")

        created_resources = {
            "vpc1_name": vpc1_name,
            "vpc1_cidr": vpc1_cidr,
            "vpc2_name": vpc2_name,
            "vpc2_cidr": vpc2_cidr,
            "eip_list": eip_list,
            "gw_name": gw_name,
            "ssl_name": ssl_name,
            "expiration_time": expiration_time,
            "vm1_name": vm1_name,
            "vm1_ip": vm1_ip,
            "vm2_name": vm2_name,
            "vm2_ip": vm2_ip,
            "vm2_mfip": vm2_mfip,
        }

        yield created_resources

    except Exception:
        logger.warning("前置资源创建失败，执行紧急清理")
        raise

    finally:
        with allure_step_log("Teardown: 按顺序清理资源"):
            _cleanup_ssl_client(vpn_page, ssl_name)
            _cleanup_vpn_gateway(vpn_page, gw_name)
            if vm2_mfip:
                _unbind_eip_from_vm(vpc_page, vm2_name, vm2_mfip)
            _cleanup_eip(vpc_page, eip_list, pool="public_net(基础版)")
            _cleanup_vm(ecs_page, vm1_name)
            _cleanup_vm(ecs_page, vm2_name)
            _cleanup_vpc(vpc_page, vpc1_name)
            _cleanup_vpc(vpc_page, vpc2_name)

        page.close()


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('SSL客户端连接VPC修改路由控制生效性验证')
class TestVpnSSLClientVpcRouteControlEffectiveness:
    """SSL 客户端连接 VPC 修改路由控制生效性验证（用例 5578）。

    单一场景，测试数据不可复用，前置资源在 class-scoped fixture 中创建，
    测试完成后统一清理。
    """

    @allure.title("SSL客户端-连接VPC-修改路由控制生效性验证")
    def test_ssl_client_vpc_route_control_effectiveness(self, page, ssl_client_route_env, ssh_vm):
        """验证 SSL 客户端修改路由控制对 VPN 连通性的生效性（用例 5578）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 下载 SSL 客户端配置文件
        3. 上传配置文件到 vpn_vm2 虚机
        4. 修改 SSL 客户端路由控制（新增路由）
        5. VPN 安装及连通性测试（路由新增状态基准）
        6. 验证 SSL 客户端在线状态
        7. 删除路由控制后验证连通性中断
        8. 重新添加路由控制后验证连通性恢复
        """
        vpn_page = VpnPage(page)
        ssl_name = ssl_client_route_env["ssl_name"]
        vm2_mfip = ssl_client_route_env["vm2_mfip"]
        vpc1_cidr = ssl_client_route_env["vpc1_cidr"]
        vm1_ip = ssl_client_route_env["vm1_ip"]

        # 步骤1: 进入 SSL 客户端列表页（P3 导航，无显式断言）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 下载 SSL 客户端配置文件
        download_path = None
        with allure_step_log("步骤2: 下载SSL客户端配置文件"):
            download_path = vpn_page.ssl_client_download_config(
                name=ssl_name,
                download_dir=tempfile.gettempdir(),
            )

        # 验证下载文件存在（P1 末态字段断言）
        with allure_step_log("验证: 下载文件存在"):
            assert download_path is not None, (
                f"[FieldAssertion] 下载文件 | 下载失败 | 期望: 文件路径 | 实际: None"
            )
            assert os.path.exists(download_path), (
                f"[FieldAssertion] 下载文件 | 文件不存在 | 期望: {download_path}"
            )
            file_size = os.path.getsize(download_path)
            assert file_size > 0, (
                f"[FieldAssertion] 下载文件 | 文件大小为零 | 期望: > 0 | 实际: {file_size}"
            )
            logger.info(f"配置文件下载成功: {download_path}, 大小: {file_size} bytes")

        # 步骤3: 上传配置文件到 vpn_vm2 虚机
        with allure_step_log("步骤3: 上传配置文件到vpn_vm2虚机"):
            ssh_vm.connect(vm2_mfip)
            logger.info(f"SSH连接到 vm2 ({vm2_mfip}) 成功")

            remote_path = f"/root/{ssl_name}.ovpn"
            ssh_vm.put_file(download_path, remote_path)
            logger.info(f"配置文件上传到 {remote_path} 成功")

            result = ssh_vm.run("ls /root/", return_rc=True)
            assert result["rc"] == 0, (
                f"[BackendAssertion] SSH命令执行失败 | ls /root/ | rc: {result['rc']} | stderr: {result.get('stderr', '')}"
            )
            assert ssl_name in result["stdout"], (
                f"[BackendAssertion] 文件上传验证 | 配置文件未在/root目录中找到 | "
                f"期望包含: {ssl_name} | 实际: {result['stdout']}"
            )
            logger.info(f"文件上传验证通过: {result['stdout']}")

        # 步骤4: 修改 SSL 客户端路由控制（新增路由）
        with allure_step_log("步骤4: 修改SSL客户端路由控制（新增路由）"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            vpn_page.ssl_client_modify_route_control_open(name=ssl_name)
            vpn_page.ssl_client_add_route_control(cidr=vpc1_cidr, desc="autotest-vpc1-route")
            vpn_page.ssl_client_save_route_control()
            vpn_page.assert_popup_success("修改路由控制成功")
            logger.info(f"路由控制新增成功: CIDR={vpc1_cidr}")

        # 步骤5: VPN 安装及连通性测试（路由新增状态基准）
        with allure_step_log("步骤5: VPN安装及连通性测试（路由新增状态基准）"):
            # 子步骤5.1: 安装 openvpn
            with allure_step_log("子步骤5.1: 安装openvpn"):
                result = ssh_vm.run("yum install -y openvpn", return_rc=True, timeout=120)
                assert result["rc"] == 0, (
                    f"[BackendAssertion] openvpn安装失败 | rc: {result['rc']} | stderr: {result.get('stderr', '')}"
                )
                logger.info("openvpn 安装成功")

            # 子步骤5.2: 后台启动 openvpn
            with allure_step_log("子步骤5.2: 后台启动openvpn"):
                remote_config = f"/root/{ssl_name}.ovpn"
                start_cmd = (
                    f"nohup openvpn --daemon --config {remote_config} "
                    f"--log-append /etc/openvpn/openvpn.log > /dev/null 2>&1 &"
                )
                result = ssh_vm.run(start_cmd, return_rc=True)
                assert result["rc"] == 0, (
                    f"[BackendAssertion] openvpn启动命令失败 | rc: {result['rc']} | stderr: {result.get('stderr', '')}"
                )
                logger.info("openvpn 后台启动命令执行成功")

            # 子步骤5.3: 轮询等待 openvpn 进程启动（最长60秒）
            with allure_step_log("子步骤5.3: 轮询等待openvpn进程启动"):
                poll_cmd = (
                    "for i in {1..30}; do "
                    "  ps -ef | grep openvpn | grep -v grep && exit 0; "
                    "  sleep 2; "
                    "done; exit 1"
                )
                result = ssh_vm.run(poll_cmd, return_rc=True, timeout=120)
                assert result["rc"] == 0, (
                    f"[BackendAssertion] openvpn进程未在60秒内启动 | "
                    f"期望: 进程存在 | 实际: 未找到openvpn进程"
                )
                logger.info(f"openvpn 进程已启动: {result['stdout']}")

            # 子步骤5.4: 执行 ping 测试连通性
            with allure_step_log("子步骤5.4: ping测试连通性（路由新增基准）"):
                assert vm1_ip is not None, (
                    f"[BackendAssertion] VM1 IP未获取 | 无法进行ping测试"
                )
                warmup_cmd = f"ping -c 1 -W 5 {vm1_ip}"
                ssh_vm.run(warmup_cmd, return_rc=True)
                logger.info("warm-up ping完成")

                ping_cmd = f"ping -c 4 {vm1_ip}"
                result = ssh_vm.run(ping_cmd, return_rc=True)
                logger.info(f"ping测试结果: rc={result['rc']}, stdout={result['stdout']}")

                assert result["rc"] == 0, (
                    f"[BackendAssertion] ping测试失败 | 期望: 0丢包 | "
                    f"实际: rc={result['rc']} | stdout: {result.get('stdout', '')}"
                )
                assert (
                    "0% packet loss" in result["stdout"]
                    or "25% packet loss" in result["stdout"]
                    or "3 received" in result["stdout"]
                    or "4 received" in result["stdout"]
                ), (
                    f"[BackendAssertion] ping丢包过多 | 期望: 最多25%丢包 | "
                    f"实际: {result['stdout']}"
                )
                logger.info(f"基准ping测试通过: 成功ping通 {vm1_ip}")

        # 步骤6: 验证 SSL 客户端在线状态
        with allure_step_log("步骤6: 验证SSL客户端在线状态"):
            online_restored = _wait_for_ssl_client_online(vpn_page, ssl_name, max_attempts=10)
            if not online_restored:
                logger.warning("UI在线状态未完全收敛，继续后续步骤")

            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            row_data = vpn_page.get_ssl_client_row_data(ssl_name)
            online_status = row_data.get("在线状态", "")
            logger.info(f"SSL客户端 {ssl_name} 在线状态: {online_status}")

            assert "在线" in online_status, (
                f"[FieldAssertion] SSL客户端在线状态 | 期望: 在线 | 实际: {online_status}"
            )
            logger.info(f"SSL客户端在线状态验证通过: {online_status}")

        # 步骤7: 删除路由控制后验证连通性中断
        with allure_step_log("步骤7: 删除路由控制后验证连通性中断"):
            # 子步骤7.1: 打开修改路由控制弹窗
            with allure_step_log("子步骤7.1: 打开修改路由控制弹窗"):
                vpn_page._ensure_ssl_client_list()
                vpn_page.wait_for_page_ready()
                vpn_page.ssl_client_modify_route_control_open(name=ssl_name)

            # 子步骤7.2: 删除路由控制记录
            with allure_step_log("子步骤7.2: 删除路由控制记录"):
                deleted = vpn_page.ssl_client_delete_route_control(cidr=vpc1_cidr)
                assert deleted, (
                    f"[OperationFailed] 修改路由控制弹窗内未找到 CIDR={vpc1_cidr} 的记录，"
                    f"无法执行删除操作"
                )
                vpn_page.ssl_client_save_route_control()
                vpn_page.assert_popup_success("修改路由控制成功")
                logger.info(f"路由控制删除成功: CIDR={vpc1_cidr}")

            # 子步骤7.3: 等待 SSL 客户端在线状态恢复
            with allure_step_log("子步骤7.3: 等待SSL客户端在线状态恢复"):
                online_restored = _wait_for_ssl_client_online_with_interval(
                    vpn_page, ssl_name, max_attempts=8
                )
                if not online_restored:
                    logger.warning("UI在线状态未在4分钟内恢复，继续以ping测试判定")

            # 子步骤7.4: 验证删除路由后无法 ping 通
            with allure_step_log("子步骤7.4: 删除路由后ping测试（应不通）"):
                ping_cmd = f"ping -c 4 {vm1_ip}"
                result = ssh_vm.run(ping_cmd, return_rc=True)
                logger.info(f"删除路由后ping结果: rc={result['rc']}, stdout={result['stdout']}")

                ping_failed = (
                    result["rc"] != 0
                    or "100% packet loss" in result["stdout"]
                    or "0 received" in result["stdout"]
                )
                assert ping_failed, (
                    f"[BackendAssertion] 删除路由后ping应失败 | "
                    f"期望: 无法ping通（rc!=0 或 100%丢包） | "
                    f"实际: rc={result['rc']}, stdout={result['stdout']}"
                )
                logger.info(f"删除路由后连通性中断验证通过: 无法ping通 {vm1_ip}")

        # 步骤8: 重新添加路由控制后验证连通性恢复
        with allure_step_log("步骤8: 重新添加路由控制后验证连通性恢复"):
            # 子步骤8.1: 打开修改路由控制弹窗
            with allure_step_log("子步骤8.1: 打开修改路由控制弹窗"):
                vpn_page._ensure_ssl_client_list()
                vpn_page.wait_for_page_ready()
                vpn_page.ssl_client_modify_route_control_open(name=ssl_name)

            # 子步骤8.2: 重新添加路由控制记录
            with allure_step_log("子步骤8.2: 重新添加路由控制记录"):
                vpn_page.ssl_client_add_route_control(cidr=vpc1_cidr, desc="autotest-vpc1-route")
                vpn_page.ssl_client_save_route_control()
                vpn_page.assert_popup_success("修改路由控制成功")
                logger.info(f"路由控制重新添加成功: CIDR={vpc1_cidr}")

            # 子步骤8.3: 重启 openvpn 确保客户端重新连接
            with allure_step_log("子步骤8.3: 重启openvpn客户端"):
                remote_config = f"/root/{ssl_name}.ovpn"
                # 先检查并终止旧进程
                ssh_vm.run("pkill -f 'openvpn --daemon' || true", return_rc=True)
                # 等待进程退出
                ssh_vm.run(
                    "for i in {1..10}; do ps -ef | grep openvpn | grep -v grep || exit 0; sleep 1; done; exit 1",
                    return_rc=True, timeout=30
                )
                # 重新启动 openvpn
                start_cmd = (
                    f"nohup openvpn --daemon --config {remote_config} "
                    f"--log-append /etc/openvpn/openvpn.log > /dev/null 2>&1 &"
                )
                result = ssh_vm.run(start_cmd, return_rc=True)
                assert result["rc"] == 0, (
                    f"[BackendAssertion] openvpn重启命令失败 | rc: {result['rc']}"
                )
                # 轮询等待进程启动
                poll_cmd = (
                    "for i in {1..30}; do "
                    "  ps -ef | grep openvpn | grep -v grep && exit 0; "
                    "  sleep 2; "
                    "done; exit 1"
                )
                result = ssh_vm.run(poll_cmd, return_rc=True, timeout=120)
                assert result["rc"] == 0, (
                    f"[BackendAssertion] openvpn重启后进程未启动 | "
                    f"期望: 进程存在 | 实际: 未找到openvpn进程"
                )
                logger.info(f"openvpn 重启成功: {result['stdout']}")

            # 子步骤8.4: 等待 SSL 客户端在线状态恢复
            with allure_step_log("子步骤8.4: 等待SSL客户端在线状态恢复"):
                online_restored = _wait_for_ssl_client_online_with_interval(
                    vpn_page, ssl_name, max_attempts=12
                )
                if not online_restored:
                    logger.warning("UI在线状态未在预期时间内恢复，继续以ping测试判定")

            # 子步骤8.5: 执行 warm-up ping 后正式 ping 测试
            with allure_step_log("子步骤8.5: 重新添加路由后ping测试（应恢复通）"):
                warmup_cmd = f"ping -c 1 -W 5 {vm1_ip}"
                ssh_vm.run(warmup_cmd, return_rc=True)
                logger.info("warm-up ping完成")

                ping_cmd = f"ping -c 4 {vm1_ip}"
                result = ssh_vm.run(ping_cmd, return_rc=True)
                logger.info(f"重新添加路由后ping结果: rc={result['rc']}, stdout={result['stdout']}")

                assert result["rc"] == 0, (
                    f"[BackendAssertion] 重新添加路由后ping应恢复 | "
                    f"期望: 可ping通（rc=0） | "
                    f"实际: rc={result['rc']}, stdout={result['stdout']}"
                )
                assert (
                    "0% packet loss" in result["stdout"]
                    or "25% packet loss" in result["stdout"]
                    or "3 received" in result["stdout"]
                    or "4 received" in result["stdout"]
                ), (
                    f"[BackendAssertion] 重新添加路由后ping丢包过多 | "
                    f"期望: 最多25%丢包 | 实际: {result['stdout']}"
                )
                logger.info(f"重新添加路由后连通性恢复验证通过: 成功ping通 {vm1_ip}")
