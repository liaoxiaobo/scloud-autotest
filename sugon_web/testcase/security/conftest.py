import pytest
from sugon_web.conftest import _create_logged_in_page
from sugon_web.config.constants import SECURITY_DEFAULT_FIP_POOL
from sugon_web.pages.security.apt import AptPage
from sugon_web.pages.security.ras import RasPage
from sugon_web.pages.security.usm import UsmPage
from sugon_web.pages.security.ver import VerPage
from sugon_web.pages.security.vdb import VdbPage
from sugon_web.pages.security.waf import WafPage
from sugon_web.pages.security.wpt import WptPage
from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data

import os
import time
from pathlib import Path


_FIP_CLAIM_DIR = Path(".security_fip_claims").resolve()
_FIP_CLAIM_MAX_AGE = 7200  # 2小时，超过此时间的占用标记视为失效


class _FipClaimLock:
    """跨 xdist worker 的 EIP 占用标记锁。

    通过本地文件标记某个 EIP 已被当前 worker 占用，避免多个 worker 复用同一个已有 EIP。
    标记文件带超时失效机制，异常退出后不会永久占用。
    """

    def __init__(self, claim_dir: Path | str = None, max_age: int = _FIP_CLAIM_MAX_AGE):
        self.claim_dir = Path(claim_dir or _FIP_CLAIM_DIR).resolve()
        self.max_age = max_age

    def _claim_file(self, ip: str) -> Path:
        safe_name = ip.replace(".", "_") + ".claimed"
        return self.claim_dir / safe_name

    def is_claimed(self, ip: str) -> bool:
        """判断指定 EIP 是否被其他活跃 worker 占用（未过期）。"""
        f = self._claim_file(ip)
        if not f.exists():
            return False
        try:
            age = time.time() - f.stat().st_mtime
            if age > self.max_age:
                return False
        except Exception:
            pass
        return True

    def claim(self, ip: str, owner: str = "") -> bool:
        """原子地占用指定 EIP，成功返回 True，已被占用返回 False。"""
        self.claim_dir.mkdir(parents=True, exist_ok=True)
        f = self._claim_file(ip)
        try:
            if f.exists():
                age = time.time() - f.stat().st_mtime
                if age > self.max_age:
                    try:
                        f.unlink()
                    except Exception:
                        pass
                else:
                    return False
            f.write_text(f"{owner}\n{time.time()}", encoding="utf-8")
            logger.info(f"FIP 占用标记: {ip} -> {owner}")
            return True
        except FileExistsError:
            return False
        except Exception as e:
            logger.warning(f"FIP {ip} 占用标记失败: {e}")
            return False

    def release(self, ip: str) -> None:
        """释放指定 EIP 的占用标记。"""
        f = self._claim_file(ip)
        try:
            if f.exists():
                f.unlink()
                logger.info(f"FIP 占用标记已释放: {ip}")
        except Exception as e:
            logger.warning(f"FIP {ip} 占用标记释放失败: {e}")

    def release_all(self, ips: list[str]) -> None:
        """批量释放占用标记。"""
        for ip in ips:
            self.release(ip)


@pytest.fixture(scope="session")
def security_vpc(browser, config, request):
    """创建安全合规测试专用 VPC，session 级共享，所有 session fixture 结束后自动清理。

    若 session 中存在失败用例，保留 VPC 不清理，便于人工排查残留资源。
    """
    from sugon_web.pages.network import VpcPage

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vpc_page = VpcPage(page)
    vpc_page.goto_service("虚拟私有云")

    vpc_name = random_data().replace("autotest-", "autotest-vpc-")
    subnet_name = random_data()
    cidr = random_data("cidr")

    vpc_page.vpc_create(name=vpc_name, subnet_name=subnet_name, cidr=cidr)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    logger.info(f"安全合规专用 VPC 创建成功: {vpc_name}, CIDR={cidr}")

    yield {"name": vpc_name, "subnet_name": subnet_name, "cidr": cidr}

    failed_count = request.session.testsfailed
    if failed_count > 0:
        logger.warning(
            f"session 中存在 {failed_count} 个失败用例，跳过 VPC 清理以保留现场: {vpc_name}"
        )
    else:
        vpc_page.goto_service("虚拟私有云")
        try:
            vpc_page.vpc_delete(vpc_name)
            vpc_page.assert_deleted(vpc_name)
            logger.info(f"安全合规专用 VPC 已删除: {vpc_name}")
        except Exception as e:
            logger.error(f"安全合规专用 VPC 删除失败: {e}")
    page.close()
    context.close()


@pytest.fixture(scope="session")
def usm_instance(browser, config, security_vpc, security_fip_pool):
    """创建 USM 实例并自动清理（scope=session）。

    所有 USM 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 usm_instance 参数即可接入，通过 usm_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._usm_helpers import create_usm_instance, delete_usm_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    usm_page_obj = UsmPage(page)
    usm_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-usm-")
    result = None
    eip = security_fip_pool.acquire()

    try:
        result = create_usm_instance(page, usm_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"],
                                     eip_ip=eip)
        result["original_name"] = result["name"]
        yield result
    except Exception:
        if eip:
            security_fip_pool.release(eip)
        raise
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, usm_page_obj, cleanup_name,
                delete_usm_instance, "usm_unbind_eip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="function")
def apt_page(page):
    """初始化攻击预警APT页对象"""
    page_object = AptPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def ras_page(page):
    """初始化漏洞扫描RAS页对象"""
    page_object = RasPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def waf_page(page):
    """初始化WEB应用防火墙WAF页对象"""
    page_object = WafPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def usm_page(page):
    """初始化云堡垒机高级版USM页对象"""
    page_object = UsmPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="session")
def ver_instance(browser, config, security_vpc):
    """创建 VER 实例并自动清理（scope=session）。

    所有 VER 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 ver_instance 参数即可接入，通过 ver_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._ver_helpers import create_ver_instance, delete_ver_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    ver_page_obj = VerPage(page)
    ver_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-ver-")
    result = None

    try:
        result = create_ver_instance(page, ver_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, ver_page_obj, cleanup_name,
                delete_ver_instance, "ver_unbind_eip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="session")
def vdb_instance(browser, config, security_vpc):
    """创建 VDB 实例并自动清理（scope=session）。

    所有 VDB 操作类测试共享同一个实例，session 结束时自动删除。
    测试方法声明 vdb_instance 参数即可接入，通过 vdb_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._vdb_helpers import create_vdb_instance, delete_vdb_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vdb_page_obj = VdbPage(page)
    vdb_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-vdb-")
    result = None

    try:
        result = create_vdb_instance(page, vdb_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, vdb_page_obj, cleanup_name,
                delete_vdb_instance, "vdb_unbind_public_ip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="function")
def ver_page(page):
    """初始化日志审计VER页对象"""
    page_object = VerPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def vdb_page(page):
    """初始化数据库审计VDB页对象"""
    page_object = VdbPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="function")
def wpt_page(page):
    """初始化网页防篡改WPT页对象"""
    page_object = WptPage(page)
    page_object.goto_list_page()
    return page_object


@pytest.fixture(scope="class")
def wpt_instance(browser, config, security_vpc, request):
    """创建网页防篡改WPT实例并自动清理（scope=class）。

    所有 WPT 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 wpt_instance 参数即可接入，通过 wpt_instance["name"] 获取实例名。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._wpt_helpers import create_wpt_instance, delete_wpt_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    wpt_page_obj = WptPage(page)
    wpt_page_obj.goto_list_page()

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-wpt-")
    result = None

    try:
        result = create_wpt_instance(page, wpt_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, wpt_page_obj, cleanup_name,
                delete_wpt_instance, "wpt_unbind_floating_ip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="class")
def ras_instance(browser, config, security_vpc):
    """创建 漏洞扫描RAS 实例并自动清理（scope=class）。

    所有 RAS 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 ras_instance 参数即可接入，通过 ras_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._ras_helpers import create_ras_instance, delete_ras_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    ras_page_obj = RasPage(page)
    ras_page_obj.goto_list_page()

    name = random_data().replace("autotest-", "autotest-ras-")
    result = None

    try:
        result = create_ras_instance(page, ras_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, ras_page_obj, cleanup_name,
                delete_ras_instance, "ras_unbind_eip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="class")
def waf_instance(browser, config, security_vpc, request):
    """创建 WEB应用防火墙WAF 实例并自动清理（scope=class）。

    所有 WAF 测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 waf_instance 参数即可接入，通过 waf_instance["name"] 获取实例名。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._waf_helpers import create_waf_instance, delete_waf_instance
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    waf_page_obj = WafPage(page)
    waf_page_obj.goto_list_page()

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-waf-")
    result = None

    try:
        result = create_waf_instance(page, waf_page_obj, name,
                                     network=security_vpc["name"],
                                     subnet=security_vpc["subnet_name"])
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, waf_page_obj, cleanup_name,
                delete_waf_instance, "waf_unbind_floating_ip",
                current_name=result["name"],
            )
        else:
            page.close()
            context.close()


@pytest.fixture(scope="class")
def apt_instance(browser, config, request):
    """创建 攻击预警APT 实例并自动清理（scope=class）。

    所有 APT 操作类测试共享同一个实例，类内所有测试执行完成后自动清理。
    测试方法声明 apt_instance 参数即可接入，通过 apt_instance["name"] 获取实例名。

    由于一个项目下只能创建一台 APT，本 fixture 通过跨进程文件锁保证同一时刻
    只有一个 worker 在创建/持有 APT 实例，避免并行冲突。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.testcase.security._apt_helpers import (
        create_apt_instance, delete_apt_instance, AptProjectLock,
    )
    from sugon_web.testcase.security._security_helpers import cleanup_security_instance

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    apt_page_obj = AptPage(page)

    params = request.param if hasattr(request, 'param') and request.param else {}
    name = params.get("name") or random_data().replace("autotest-", "autotest-apt-")
    result = None
    lock = AptProjectLock()

    try:
        lock.acquire(owner=f"apt_instance_{name}")
        apt_page_obj.goto_list_page()
        result = create_apt_instance(page, apt_page_obj, name)
        result["original_name"] = result["name"]
        yield result
    finally:
        if result is not None:
            cleanup_name = result.get("original_name", result["name"])
            cleanup_security_instance(
                context, config, page, apt_page_obj, cleanup_name,
                delete_apt_instance, lock=lock,
                current_name=result["name"],
            )
        else:
            try:
                lock.release()
            except Exception as e:
                logger.warning(f"释放 APT 项目锁时忽略异常: {e}")
            page.close()
            context.close()


def _fip_pool_count(request) -> int:
    """根据 pytest 并发数计算每个 worker 需要预占用的 FIP 数量。

    在 loadscope 调度下，单个 worker 同一时刻最多同时运行一个 session/class fixture 与一到两个
    绑定测试，因此保底 3 个；额外 +1 作为释放/重试余量。
    """
    numprocesses = request.config.getoption("numprocesses")
    if numprocesses is None or str(numprocesses).lower() == "none":
        workerinput = getattr(request.config, "workerinput", {}) or {}
        numprocesses = workerinput.get("numprocesses")
    if str(numprocesses).lower() == "auto":
        numprocesses = os.cpu_count() or 1
    else:
        try:
            numprocesses = int(numprocesses or 1)
        except (TypeError, ValueError):
            numprocesses = 1
    return max(3, numprocesses + 1)


def _scan_closed_unbound_eips(vpc_page, pool_name: str) -> list[str]:
    """扫描目标资源池中状态为'关闭'但实际未绑定的 EIP，作为可复用补充。

    当前环境部分 EIP 虽然状态显示为'关闭'，但绑定设备列为'--'，实际处于可用状态。
    该函数在 `get_unbound_eips()` 的基础上额外补充这类 IP，且不会与正常未绑定 IP 重复。
    """
    import re

    try:
        vpc_page.switch_eip_pool(pool_name)
        vpc_page._expand_page_size("100")
        vpc_page.page.wait_for_timeout(1000)
    except Exception as e:
        logger.warning(f"security_fip_pool: 扫描'关闭'状态 EIP 时切换资源池失败: {e}")
        return []

    headers = vpc_page.table_headers
    ip_index = device_index = status_index = None
    for i, header in enumerate(headers):
        if header == "IP地址":
            ip_index = i
        elif header == "绑定设备":
            device_index = i
        elif header == "状态":
            status_index = i

    if ip_index is None:
        logger.warning("security_fip_pool: 扫描'关闭'状态 EIP 时未找到 IP地址 列")
        return []

    closed_ips = []
    seen = set()
    for row in vpc_page.table_rows:
        cells = row.get_by_role("cell").all()
        if len(cells) <= ip_index:
            continue
        ip_text = cells[ip_index].text_content() or ""
        ip_match = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", ip_text)
        if not ip_match:
            continue
        ip = ip_match.group(1)
        if ip in seen:
            continue
        seen.add(ip)

        device_text = ""
        if device_index is not None and len(cells) > device_index:
            device_text = (cells[device_index].text_content() or "").strip()

        status_text = ""
        if status_index is not None and len(cells) > status_index:
            status_text = (cells[status_index].text_content() or "").strip()

        # 状态为'关闭'且绑定设备为空/--，视为可用未绑定
        if status_text == "关闭" and device_text in ("", "--"):
            closed_ips.append(ip)

    logger.info(f"security_fip_pool: 扫描到 {len(closed_ips)} 个状态'关闭'的可复用 EIP")
    return closed_ips


class _SecurityFipPool:
    """安全合规测试 FIP 池。

    在同 worker 内提供 acquire/release，优先复用环境中已有的未绑定 EIP，
    不足时再新建。session 结束时会解绑所有 FIP，并释放由本池创建的 EIP，
    同时清除占用标记。
    """

    def __init__(
        self,
        borrowed: list[str],
        created: list[str],
        vpc_page,
        pool_name: str,
        claim_lock: _FipClaimLock,
    ):
        self.borrowed = list(borrowed)
        self.created = list(created)
        self.fips = self.borrowed + self.created
        self.available = list(self.fips)
        self.vpc_page = vpc_page
        self.pool_name = pool_name
        self.claim_lock = claim_lock
        self.acquired = set()

    def acquire(self) -> str:
        """从池中获取一个空闲 FIP。"""
        if not self.available:
            raise RuntimeError(
                f"security_fip_pool 没有可用的 FIP，总量={len(self.fips)}"
            )
        fip = self.available.pop(0)
        self.acquired.add(fip)
        logger.info(
            f"security_fip_pool: 分配 FIP {fip}，已分配/剩余: "
            f"{len(self.acquired)}/{len(self.available)}"
        )
        return fip

    def release(self, fip: str) -> None:
        """将 FIP 归还到池中（不解绑/不释放，供后续测试复用）。"""
        if fip in self.acquired:
            self.acquired.discard(fip)
            self.available.append(fip)
            logger.info(
                f"security_fip_pool: 归还 FIP {fip}，已分配/剩余: "
                f"{len(self.acquired)}/{len(self.available)}"
            )

    def release_all(self) -> None:
        """session 结束时：解绑所有 FIP、释放本池创建的 EIP、清除占用标记。"""
        for fip in self.fips:
            try:
                _unbind_fip_if_needed(self.vpc_page, fip)
            except Exception as e:
                logger.warning(f"security_fip_pool: 解绑 FIP {fip} 失败或无需解绑: {e}")

        for fip in self.created:
            try:
                _goto_eip_list(self.vpc_page)
                self.vpc_page.search(fip)
                if fip in self.vpc_page.get_eip_list():
                    self.vpc_page.eip_release(fip)
                    logger.info(f"security_fip_pool: 已释放 FIP {fip}")
            except Exception as e:
                logger.error(f"security_fip_pool: 释放 FIP {fip} 失败: {e}")

        self.claim_lock.release_all(self.fips)
        self.acquired.clear()
        self.available = list(self.fips)


def _goto_eip_list(vpc_page) -> None:
    """导航到弹性公网IPv4列表页。

    释放/解绑 FIP 时必须先进入 EIP 列表页，不能停留在 VPC 概览页，
    否则搜索框等定位元素不存在会导致清理失败。
    """
    vpc_page.goto_submenu("弹性公网IPv4")


def _unbind_fip_if_needed(vpc_page, fip: str) -> None:
    """在 EIP 列表页尝试解绑指定的 FIP（如果处于已绑定状态）。"""
    _goto_eip_list(vpc_page)
    vpc_page.search(fip)
    for action_name in ("解绑", "解除绑定"):
        try:
            vpc_page.click_action(fip, action_name)
            vpc_page.dialog_confirm.click()
            vpc_page.page.wait_for_timeout(3000)
            logger.info(f"FIP {fip} 已通过 '{action_name}' 解绑")
            return
        except Exception:
            continue
    logger.info(f"FIP {fip} 无需解绑或不存在解绑操作")


@pytest.fixture(scope="session")
def security_fip_pool(browser, config, request):
    """安全合规测试 FIP 池。

    优先复用目标资源池中已存在的未绑定 EIP，不足时再逐个新分配，
    通过本地文件标记避免多个 xdist worker 复用同一个 EIP。
    """
    from sugon_web.pages.network import VpcPage

    pool_name = config.get("network") or SECURITY_DEFAULT_FIP_POOL
    count = _fip_pool_count(request)
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", "master")
    owner = f"worker-{worker_id}-{os.getpid()}"

    context = browser.new_context(ignore_https_errors=True, timezone_id="Asia/Shanghai")
    page = _create_logged_in_page(context, config)
    vpc_page = VpcPage(page)
    vpc_page.goto_service("虚拟私有云")

    claim_lock = _FipClaimLock()

    # 1) 扫描目标资源池中已有的未绑定 EIP（含状态为'关闭'但实际未绑定的补充）
    try:
        unbound_ips = vpc_page.get_unbound_eips(pool_name)
    except Exception as e:
        logger.warning(f"security_fip_pool: 扫描未绑定 EIP 失败: {e}")
        unbound_ips = []

    try:
        closed_ips = _scan_closed_unbound_eips(vpc_page, pool_name)
    except Exception as e:
        logger.warning(f"security_fip_pool: 扫描'关闭'状态 EIP 失败: {e}")
        closed_ips = []

    candidate_ips = list(dict.fromkeys(unbound_ips + closed_ips))

    borrowed = []
    for ip in candidate_ips:
        if len(borrowed) >= count:
            break
        if claim_lock.claim(ip, owner):
            borrowed.append(ip)
            logger.info(f"security_fip_pool: 复用已有未绑定 EIP {ip}")
        else:
            logger.debug(f"security_fip_pool: EIP {ip} 已被其他 worker 占用，跳过")

    # 2) 复用不足时，逐个新分配 EIP
    created = []
    missing = count - len(borrowed)
    if missing > 0:
        logger.info(f"security_fip_pool: 已有 EIP 不足，尝试从 {pool_name} 新分配 {missing} 个")
        for i in range(missing):
            try:
                new_ips = vpc_page.eip_allocate(pool=pool_name, count=1, method="快速选择")
                if new_ips:
                    ip = new_ips[0]
                    claim_lock.claim(ip, owner)
                    created.append(ip)
                    logger.info(f"security_fip_pool: 新分配 EIP {ip}")
                else:
                    raise RuntimeError("eip_allocate 返回空")
            except Exception as e:
                logger.error(f"security_fip_pool: 第 {i + 1}/{missing} 个新 EIP 分配失败: {e}")
                break

    if not borrowed and not created:
        page.close()
        context.close()
        raise RuntimeError(f"security_fip_pool: 无法从 {pool_name} 获取任何 FIP")

    pool = _SecurityFipPool(borrowed, created, vpc_page, pool_name, claim_lock)
    logger.info(f"security_fip_pool: 池初始化完成，借用={borrowed}，新建={created}")
    try:
        yield pool
    finally:
        try:
            pool.release_all()
        except Exception as e:
            logger.error(f"security_fip_pool teardown 异常: {e}")
        page.close()
        context.close()
