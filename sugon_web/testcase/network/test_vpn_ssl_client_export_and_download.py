"""SSL客户端-导出客户端信息&下载客户端验证。

用例编号：5561、5562
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


def _create_ssl_client_with_retry(
    vpn_page, name, vpn_gateway_name, expiration_time, access_cidr, max_attempts=2
):
    """创建 SSL 客户端，弹窗提示失败时关闭弹窗后重试。

    兼容产品缺陷：弹窗可能显示"SSL客户端创建失败"，但后端实际已创建资源。
    重试前会先检查资源是否已存在，避免重复创建。
    """
    for attempt in range(max_attempts):
        try:
            vpn_page.ssl_client_create(
                name=name,
                vpn_gateway_name=vpn_gateway_name,
                expiration_time=expiration_time,
                access_cidr=access_cidr,
            )
            vpn_page.assert_popup_success(timeout=30)
            logger.info(f"SSL客户端 {name} 创建成功")
            return
        except AssertionError as e:
            logger.warning(f"SSL客户端 {name} 第 {attempt + 1} 次创建失败: {e}")

            # 关闭可能残留的创建弹窗，避免阻塞后续操作
            try:
                vpn_page.close_dialog_if_exists()
                vpn_page.wait_for_page_ready()
            except Exception:
                pass

            # 兼容产品缺陷：弹窗显示失败但资源可能已创建
            try:
                vpn_page._ensure_ssl_client_list()
                vpn_page.wait_for_page_ready()
                vpn_page.get_row_by_name(name)
                logger.warning(
                    f"产品缺陷: SSL客户端 {name} 弹窗显示失败但资源已创建，继续后续步骤"
                )
                return
            except Exception:
                pass

            if attempt < max_attempts - 1:
                logger.info(f"SSL客户端 {name} 关闭弹窗后准备重试创建")
            else:
                raise AssertionError(f"SSL客户端 {name} 创建失败，重试后仍未成功")


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
    gw_name = f"vpn_autotest_gw_{random_data(length=4)}"
    ssl_name = f"vpn_autotest_ssl_{random_data(length=4)}"
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
                timeout=1200,
                refresh=True,
                refresh_interval=30,
            )

        # 步骤4: 创建 SSL 客户端
        with allure_step_log("前置: 等待10秒后创建SSL客户端"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()
            # VPN 网关变为运行中后，显式等待 10 秒确保状态稳定
            vpn_page.page.wait_for_timeout(10000)
            _create_ssl_client_with_retry(
                vpn_page,
                name=ssl_name,
                vpn_gateway_name=gw_name,
                expiration_time=expiration_time,
                access_cidr=vpc_cidr,
            )
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
@allure.story('SSL客户端导出客户端信息&下载客户端验证')
class TestVpnSSLClientExportAndDownload:
    """SSL 客户端导出客户端信息及下载客户端功能验证（用例 5561、5562）。

    两个场景共享同一套前置资源，资源在 class-scoped fixture 中创建，
    全部场景执行完成后统一清理。
    """

    @allure.title("SSL客户端-导出客户端信息功能验证")
    def test_ssl_client_export_info(self, page, ssl_client_env):
        """验证导出客户端信息功能（用例 5561）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 点击导出客户端信息按钮，打开导出弹窗
        3. 选择 VPN 网关为"所有"，点击确定下载
        4. 验证导出的 Excel 文件内容正确
        """
        vpn_page = VpnPage(page)
        ssl_name = ssl_client_env["ssl_name"]
        gw_name = ssl_client_env["gw_name"]
        vpc_name = ssl_client_env["vpc_name"]

        # 步骤1: 进入 SSL 客户端列表页（P3 导航，无显式断言）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 打开导出客户端信息弹窗
        with allure_step_log("步骤2: 打开导出客户端信息弹窗"):
            vpn_page.ssl_client_export_dialog_open()

        # 步骤3: 配置导出选项并下载
        download_path = None
        with allure_step_log("步骤3: 配置导出选项并下载"):
            download_path = vpn_page.ssl_client_export_download(
                vpn_gateway="所有",
                download_dir=tempfile.gettempdir(),
            )

        # 步骤4: 验证导出文件内容（P1 末态字段断言）
        with allure_step_log("步骤4: 验证导出文件内容"):
            assert download_path is not None, (
                f"[FieldAssertion] 导出文件 | 下载失败 | 期望: 文件路径 | 实际: None"
            )
            assert os.path.exists(download_path), (
                f"[FieldAssertion] 导出文件 | 文件不存在 | 期望: {download_path}"
            )
            file_size = os.path.getsize(download_path)
            assert file_size > 0, (
                f"[FieldAssertion] 导出文件 | 文件大小为零 | 期望: > 0 | 实际: {file_size}"
            )
            logger.info(f"导出文件下载成功: {download_path}, 大小: {file_size} bytes")

            # 验证文件名包含 SSL 客户端相关标识（实际为中文文件名 "SSL客户端信息.xlsx"）
            file_name = os.path.basename(download_path)
            assert "SSL" in file_name or "ssl" in file_name.lower() or "client" in file_name.lower() or "客户端" in file_name, (
                f"[FieldAssertion] 导出文件 | 文件名不匹配 | 期望包含 'SSL'/'ssl'/'client'/'客户端' | 实际: {file_name}"
            )

            # 尝试读取 Excel 内容并验证关键字段
            # openpyxl 为可选依赖，未安装时仅记录日志，不阻断测试
            _has_openpyxl = __import__('importlib').util.find_spec('openpyxl') is not None
            if not _has_openpyxl:
                logger.warning("openpyxl 未安装，跳过 Excel 内容验证")

            if _has_openpyxl:
                import openpyxl
                wb = openpyxl.load_workbook(download_path)
                ws = wb.active
                # 获取所有单元格文本
                all_texts = []
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            all_texts.append(str(cell))

                all_text = " ".join(all_texts)
                logger.info(f"Excel 内容摘要: {all_text[:200]}...")

                # 验证 Excel 中包含 SSL 客户端名称、VPN 网关名称等关键信息
                assert ssl_name in all_text, (
                    f"[FieldAssertion] Excel内容 | 未找到SSL客户端名称 | 期望: {ssl_name}"
                )
                assert gw_name in all_text, (
                    f"[FieldAssertion] Excel内容 | 未找到VPN网关名称 | 期望: {gw_name}"
                )
                logger.info("Excel 文件内容验证通过")

    @allure.title("SSL客户端-下载客户端功能验证")
    def test_ssl_client_download_package(self, page, ssl_client_env):
        """验证下载客户端安装包功能（用例 5562）。

        步骤：
        1. 进入 SSL 客户端列表页
        2. 点击下载客户端按钮
        3. 验证下载文件存在、文件名正确、大小非零
        """
        vpn_page = VpnPage(page)

        # 步骤1: 进入 SSL 客户端列表页（P3 导航，无显式断言）
        with allure_step_log("步骤1: 进入SSL客户端列表页"):
            vpn_page._ensure_ssl_client_list()
            vpn_page.wait_for_page_ready()

        # 步骤2: 下载客户端安装包
        download_path = None
        with allure_step_log("步骤2: 下载客户端安装包"):
            download_path = vpn_page.ssl_client_download_package(
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
            assert "vpn-client" in file_name or "client" in file_name, (
                f"[FieldAssertion] 下载文件 | 文件名不匹配 | 期望包含 'vpn-client' | 实际: {file_name}"
            )
            logger.info(f"客户端安装包下载成功: {download_path}, 大小: {file_size} bytes")
