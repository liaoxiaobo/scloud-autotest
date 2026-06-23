"""SSL客户端-下载配置文件&修改路由控制验证。

用例编号：5563、5579、15579
"""

import os
import tempfile
from datetime import datetime, timedelta

import allure
import pytest

from sugon_web.conftest import _create_logged_in_page
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


# ---------------------------------------------------------------------------
# Class-scoped fixture：共享前置资源
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def ssl_client_env(browser_context, config):
    """创建 SSL 客户端测试所需的全套前置资源（scope=class）。

    创建顺序：VPC -> EIP -> VPN网关 -> SSL客户端
    清理顺序：SSL客户端 -> VPN网关 -> EIP -> VPC（严格按需求顺序）

    参数:
        无外部参数，内部固定配置。

    Yields:
        dict: 包含所有前置资源信息的字典：
            - vpc_name (str): VPC 名称
            - vpc_cidr (str): VPC CIDR
            - eip_list (list[str]): 分配的公网 IP 列表
            - gw_name (str): VPN 网关名称
            - ssl_name (str): SSL 客户端名称
            - ssl_client_info (dict): SSL 客户端详情信息
    """
    page = _create_logged_in_page(browser_context, config)
    vpn_page = VpnPage(page)
    vpc_page = VpcPage(page)

    # 资源命名
    vpc_name = f"vpn_{random_data(length=4)}"
    vpc_cidr = "176.176.5.0/24"
    gw_name = f"vpn-gw-ssl-{random_data(length=4)}"
    ssl_name = f"ssl-client-{random_data(length=4)}"
    expiration_time = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    eip_list = []
    created_resources = {}

    try:
        # 步骤1: 创建 VPC
        with allure_step_log("前置: 创建虚拟私有云"):
            vpc_page.vpc_create(
                name=vpc_name,
                subnet_name=f"subnet-{random_data(length=4)}",
                cidr=vpc_cidr,
                desc="",
                subnet_desc="",
                network_type="Geneve",
                gateway_mode="分布式网关",
            )
            vpc_page.assert_popup_success("创建虚拟私有云成功")
            vpc_page.assert_status(vpc_name)
            logger.info(f"VPC {vpc_name} 创建成功")

        # 步骤2: 分配 2 个弹性公网 IP
        with allure_step_log("前置: 分配弹性公网IP"):
            eip_list = vpc_page.eip_allocate(pool="public_net(基础版)", count=2, method="快速选择")
            logger.info(f"分配弹性公网IP: {eip_list}")

        # 步骤3: 创建 VPN 网关（SSL 类型、基础版、连接 VPC）
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
                vpc_name=vpc_name,
                flavor="虚拟专用网络数据型",
                resource_pool_tag="基础版",
                client_subnet="17.17.17.0/24",
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"VPN网关 {gw_name} 创建提交成功")

        # 等待 VPN 网关状态变为运行中
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
            vpn_page.ssl_client_create(
                name=ssl_name,
                vpn_gateway_name=gw_name,
                expiration_time=expiration_time,
                access_cidr=vpc_cidr,
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"SSL客户端 {ssl_name} 创建提交成功")

        # 等待 SSL 客户端出现在列表中
        with allure_step_log("前置: 等待SSL客户端出现在列表中"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            vpn_page.assert_list_contain(ssl_name, column_name="名称")

        created_resources = {
            "vpc_name": vpc_name,
            "vpc_cidr": vpc_cidr,
            "eip_list": eip_list,
            "gw_name": gw_name,
            "ssl_name": ssl_name,
            "expiration_time": expiration_time,
        }

        yield created_resources

    except Exception:
        # setup 失败时，按反向顺序清理已创建的资源
        logger.warning("前置资源创建失败，执行紧急清理")
        raise

    finally:
        # 清理顺序：SSL客户端 -> VPN网关 -> EIP -> VPC（严格按需求顺序）
        with allure_step_log("Teardown: 按顺序清理资源"):
            _cleanup_ssl_client(vpn_page, ssl_name)
            _cleanup_vpn_gateway(vpn_page, gw_name)
            _cleanup_eip(vpc_page, eip_list, pool="public_net(基础版)")
            _cleanup_vpc(vpc_page, vpc_name)

        page.close()


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


@allure.epic('网络服务')
@allure.feature('虚拟专用网络VPN')
@allure.story('SSL客户端下载配置文件&修改路由控制验证')
class TestVpnSSLClientDownloadConfigAndRouteControl:
    """SSL 客户端下载配置文件及修改路由控制功能验证（用例 5563、5579、15579）。

    三个场景共享同一套前置资源，资源在 class-scoped fixture 中创建，
    全部场景执行完成后统一清理。
    """

    @allure.title("SSL客户端-下载配置文件验证")
    def test_ssl_client_download_config(self, page, ssl_client_env):
        """验证下载 SSL 客户端配置文件功能（用例 5563）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 点击下载配置文件按钮，下载 .ovpn 文件
        3. 验证文件存在、大小非零、文件名与 SSL 客户端名称一致
        """
        vpn_page = VpnPage(page)
        ssl_name = ssl_client_env["ssl_name"]

        # 步骤1: 进入 SSL 客户端列表页（P3 导航，无显式断言）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 下载配置文件
        download_path = None
        with allure_step_log("步骤2: 下载配置文件"):
            download_path = vpn_page.ssl_client_download_config(
                name=ssl_name,
                download_dir=tempfile.gettempdir(),
            )

        # 步骤3: 验证下载文件（P1 末态字段断言）
        with allure_step_log("步骤3: 验证下载文件"):
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

            file_name = os.path.basename(download_path)
            expected_name = f"{ssl_name}.ovpn"
            assert expected_name == file_name or ssl_name in file_name, (
                f"[FieldAssertion] 下载文件 | 文件名不匹配 | 期望: {expected_name} | 实际: {file_name}"
            )
            logger.info(f"配置文件下载成功: {download_path}, 大小: {file_size} bytes")

    @allure.title("SSL客户端-修改路由控制验证-新增")
    def test_ssl_client_modify_route_control_add(self, page, ssl_client_env):
        """验证修改路由控制新增功能（用例 5579）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 打开修改路由控制弹窗
        3. 新增路由控制记录（CIDR: 173.3.3.0/24, 备注: autotestl测试输入）
        4. 验证详情页路由控制栏目显示新增记录
        """
        vpn_page = VpnPage(page)
        ssl_name = ssl_client_env["ssl_name"]
        route_cidr = "173.3.3.0/24"
        route_desc = "autotestl测试输入"

        # 步骤1: 进入 SSL 客户端列表页（P3 导航）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 打开修改路由控制弹窗（P3 操作）
        with allure_step_log("步骤2: 打开修改路由控制弹窗"):
            vpn_page.ssl_client_modify_route_control_open(name=ssl_name)

        # 步骤3: 新增路由控制记录并保存（P0 操作成功断言）
        with allure_step_log("步骤3: 新增路由控制记录"):
            vpn_page.ssl_client_add_route_control(cidr=route_cidr, desc=route_desc)
            vpn_page.ssl_client_save_route_control()
            vpn_page.assert_popup_success("修改路由控制成功")
            logger.info(f"路由控制记录新增成功: CIDR={route_cidr}, 备注={route_desc}")

        # 步骤4: 验证详情页路由控制栏目（P1 末态字段断言）
        with allure_step_log("步骤4: 验证详情页路由控制信息"):
            vpn_page.open_ssl_client_detail(ssl_name)
            route_controls = vpn_page.get_ssl_client_route_control_from_detail()

            # 验证新增的路由信息存在
            cidr_found = False
            desc_found = False
            for route in route_controls:
                if route.get("routing_cidr") == route_cidr:
                    cidr_found = True
                if route.get("desc") == route_desc:
                    desc_found = True

            assert cidr_found, (
                f"[FieldAssertion] 路由控制 | CIDR未找到 | 期望: {route_cidr} | 实际: {route_controls}"
            )
            assert desc_found, (
                f"[FieldAssertion] 路由控制 | 备注未找到 | 期望: {route_desc} | 实际: {route_controls}"
            )
            logger.info(f"详情页路由控制验证通过: {route_controls}")

    @allure.title("SSL客户端-修改路由控制验证-删除")
    def test_ssl_client_modify_route_control_delete(self, page, ssl_client_env):
        """验证修改路由控制删除功能（用例 15579）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 打开修改路由控制弹窗
        3. 新增 CIDR 为 173.3.4.0/24 的路由控制记录并保存
        4. 再次打开修改路由控制弹窗
        5. 删除 CIDR 为 173.3.4.0/24 的路由控制记录并保存
        6. 验证详情页路由控制栏目不显示该记录
        """
        vpn_page = VpnPage(page)
        ssl_name = ssl_client_env["ssl_name"]
        route_cidr = "173.3.4.0/24"
        route_desc = "autotestl测试输入"

        # 步骤1: 进入 SSL 客户端列表页（P3 导航）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 打开修改路由控制弹窗（P3 操作）
        with allure_step_log("步骤2: 打开修改路由控制弹窗"):
            vpn_page.ssl_client_modify_route_control_open(name=ssl_name)

        # 步骤3: 新增路由控制记录并保存（P0 操作成功断言）
        with allure_step_log("步骤3: 新增待删除的路由控制记录"):
            vpn_page.ssl_client_add_route_control(cidr=route_cidr, desc=route_desc)
            vpn_page.ssl_client_save_route_control()
            vpn_page.assert_popup_success("修改路由控制成功")
            logger.info(f"路由控制记录新增成功: CIDR={route_cidr}, 备注={route_desc}")

        # 步骤4: 再次打开修改路由控制弹窗（P3 操作）
        with allure_step_log("步骤4: 再次打开修改路由控制弹窗"):
            vpn_page.ssl_client_modify_route_control_open(name=ssl_name)

        # 步骤5: 删除路由控制记录并保存（P0 操作成功断言）
        with allure_step_log("步骤5: 删除路由控制记录"):
            deleted = vpn_page.ssl_client_delete_route_control(cidr=route_cidr)
            assert deleted, (
                f"[OperationFailed] 修改路由控制弹窗内未找到 CIDR={route_cidr} 的记录，"
                f"无法执行删除操作"
            )
            vpn_page.ssl_client_save_route_control()
            vpn_page.assert_popup_success("修改路由控制成功")
            logger.info(f"路由控制记录删除成功: CIDR={route_cidr}")

        # 步骤6: 验证详情页路由控制栏目（P1 末态字段断言）
        with allure_step_log("步骤6: 验证详情页路由控制信息"):
            vpn_page.open_ssl_client_detail(ssl_name)
            route_controls = vpn_page.get_ssl_client_route_control_from_detail()

            # 验证删除的路由信息不存在
            cidr_still_exists = any(
                route.get("routing_cidr") == route_cidr for route in route_controls
            )
            assert not cidr_still_exists, (
                f"[FieldAssertion] 路由控制 | CIDR应已删除但仍存在 | 期望: 不包含 {route_cidr} | 实际: {route_controls}"
            )
            logger.info(f"详情页路由控制删除验证通过: {route_controls}")
