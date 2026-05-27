import time
from dataclasses import dataclass, field

import pytest

from sugon_web.pages.network import VpcPage
from sugon_web.testcase.network._slb_helpers import stop_http_backend
from sugon_web.utils.logger import allure_step_log, logger


@dataclass
class LbCleanupRegistry:
    """记录单个测试用例创建的监听器与公网 IP 绑定信息。

    该对象由 `clean_lb_listener` fixture 返回，测试用例只负责登记
    需要在 teardown 阶段回收的资源，不直接承担清理动作。

    Attributes:
        listeners: 待删除的监听器信息列表。每项通常包含 `slb_name`、
            `lb_name`，可选包含 `pool_name`。
        eip_bound_slbs: 已绑定公网 IP、需要在 teardown 阶段解绑的
            SLB 名称列表。
    """

    listeners: list[dict] = field(default_factory=list)
    eip_bound_slbs: list[str] = field(default_factory=list)
    backend_servers: list[dict] = field(default_factory=list)

    def add_listener(self, listener_info):
        """登记一个待清理的监听器。

        Args:
            listener_info: 监听器信息字典，至少包含 `slb_name` 与 `lb_name`。
                若同时提供 `pool_name`，清理阶段会先尝试删除资源池成员。
                可选字段:
                - `extra_pools`: 非默认资源池名称列表，清理时会先删除这些资源池。
                - `forward_rules`: 转发规则名称列表，清理时会先删除这些规则。

        Returns:
            None.
        """
        self.listeners.append(listener_info)

    def add_eip(self, slb_name):
        """登记一个待解绑公网 IP 的 SLB。

        Args:
            slb_name: 已绑定公网 IP 的 SLB 名称。

        Returns:
            None.
        """
        self.eip_bound_slbs.append(slb_name)

    def add_backend_server(self, vm_info, port=8080, kill_pattern=None):
        """登记一个待停止的后端服务。

        Args:
            vm_info: 启动了服务的虚机信息字典或连接地址字符串。
            port: 服务监听端口。
            kill_pattern: 用于 ``pkill -f`` 的进程匹配模式；
                未提供时默认使用 ``stop_http_backend`` 停止 HTTP 服务。

        Returns:
            None.
        """
        self.backend_servers.append({"vm_info": vm_info, "port": port, "kill_pattern": kill_pattern})


@dataclass
class IpGroupCleanupRegistry:
    """记录单个测试用例创建的 IP 地址组名称。"""

    groups: list[str] = field(default_factory=list)

    def add(self, group_name):
        """登记一个待删除的 IP 地址组。

        Args:
            group_name: 待删除的 IP 地址组名称。

        Returns:
            None.
        """
        self.groups.append(group_name)


def _wait_pool_member_names(page, vpc_page, timeout_ms=20000, interval_ms=2000):
    """等待资源池成员列表完成加载。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        vpc_page: 与当前页面绑定的 `VpcPage` 实例。
        timeout_ms: 最大等待时间，单位为毫秒。
        interval_ms: 轮询间隔，单位为毫秒。

    Returns:
        list[str]: 当前页面可读取到的资源池成员名称列表。若超时仍未读取到，
        返回最后一次读取结果，通常为空列表。
    """
    deadline = time.monotonic() + timeout_ms / 1000
    last_member_names = []

    while time.monotonic() < deadline:
        try:
            page.wait_for_load_state("networkidle")
        except Exception:
            logger.debug("等待资源池页面 networkidle 超时，继续按轮询兜底")

        try:
            last_member_names = vpc_page.get_column_data("实例名称")
        except Exception as exc:
            logger.debug(f"读取资源池成员列表失败，继续重试: {exc}")
            last_member_names = []

        if last_member_names:
            logger.info(f"资源池成员列表加载完成: {last_member_names}")
            return last_member_names

        logger.info("资源池成员列表暂未加载完成，继续等待")
        page.wait_for_timeout(interval_ms)

    logger.warning("等待资源池成员列表加载超时，按当前读取结果继续清理")
    return last_member_names


def _safe_unbind_slb_eip(vpc_page, slb_name):
    """尝试解绑指定 SLB 的公网 IP，失败仅记录日志。

    Args:
        vpc_page: 与当前页面绑定的 `VpcPage` 实例。
        slb_name: 目标 SLB 名称。

    Returns:
        None.
    """
    with allure_step_log(f"Fixture清理: 解绑SLB {slb_name} 的公网IP"):
        try:
            vpc_page.slb_unbind_eip(slb_name)
        except Exception as exc:
            logger.warning(f"解绑公网IP失败: {slb_name}, error={exc}")


def _safe_remove_pool_members(page, vpc_page, listener_info):
    """尝试删除监听器资源池中的全部成员。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        vpc_page: 与当前页面绑定的 `VpcPage` 实例。
        listener_info: 监听器信息字典。

    Returns:
        None.
    """
    pool_name = listener_info.get("pool_name")
    if not pool_name:
        return

    try:
        vpc_page.goto_lb_pool_detail(listener_info["lb_name"], pool_name)
        member_names = _wait_pool_member_names(page, vpc_page)
        if not member_names:
            logger.warning(f"资源池成员列表最终仍为空，跳过成员删除: {listener_info}")
            return
        vpc_page.lb_pool_remove_vm(member_names)
        page.wait_for_timeout(2000)
    except Exception as exc:
        logger.warning(f"清理资源池成员失败: {listener_info}, error={exc}")


def _safe_delete_listener(page, vpc_page, listener_info):
    """尝试删除监听器及其关联资源，失败仅记录日志。

    清理顺序（与资源依赖关系相反）：
    1. 转发规则（引用资源池）
    2. 非默认资源池
    3. 默认资源池成员
    4. 监听器本身

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        vpc_page: 与当前页面绑定的 `VpcPage` 实例。
        listener_info: 监听器信息字典。

    Returns:
        None.
    """
    with allure_step_log(f"Fixture清理: 删除监听器 {listener_info['lb_name']}"):
        try:
            slb_name = listener_info["slb_name"]
            lb_name = listener_info["lb_name"]

            # 1. 先删除转发规则（转发规则引用资源池，需先删）
            for rule_name in listener_info.get("forward_rules", []):
                try:
                    vpc_page.lb_forward_rule_delete(slb_name, lb_name, rule_name)
                    page.wait_for_timeout(2000)
                except Exception as exc:
                    logger.warning(f"清理转发规则失败: {rule_name}, error={exc}")

            # 2. 删除非默认资源池：先删成员，再删资源池
            for pool_name in listener_info.get("extra_pools", []):
                try:
                    vpc_page.goto_lb_pool_detail(lb_name, pool_name)
                    member_names = _wait_pool_member_names(page, vpc_page)
                    if member_names:
                        vpc_page.lb_pool_remove_vm(member_names)
                        page.wait_for_timeout(2000)
                    vpc_page.goto_slb_detail(slb_name, "监听器")
                    vpc_page.lb_pool_delete(slb_name, lb_name, pool_name)
                    page.wait_for_timeout(2000)
                except Exception as exc:
                    logger.warning(f"清理非默认资源池失败: {pool_name}, error={exc}")

            # 3. 删除默认资源池成员
            vpc_page.goto_slb_detail(slb_name, "监听器")
            _safe_remove_pool_members(page, vpc_page, listener_info)

            # 4. 删除监听器本身
            vpc_page.goto_slb_detail(slb_name, "监听器")
            page.wait_for_load_state("networkidle")
            vpc_page.slb_lb_delete(slb_name, lb_name)
            vpc_page.assert_popup_success()
            time.sleep(3)
        except Exception as exc:
            logger.warning(f"清理监听器失败: {listener_info}, error={exc}")
        finally:
            # 确保清理过程中打开的弹窗被关闭，避免影响后续清理
            try:
                vpc_page.close_dialog_if_exists()
            except Exception:
                pass


def _safe_stop_backend_server(ssh_vm, backend_server_info):
    """尝试停止单个后端服务，失败仅记录日志。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        backend_server_info: 后端服务信息字典，包含 ``vm_info``、
            ``port``，以及可选的 ``kill_pattern``。

    Returns:
        None.
    """
    vm_info = backend_server_info["vm_info"]
    port = backend_server_info["port"]
    kill_pattern = backend_server_info.get("kill_pattern")
    vm_name = vm_info.get("name", vm_info.get("mfip")) if isinstance(vm_info, dict) else str(vm_info)
    with allure_step_log(f"Fixture清理: 停止后端服务 {vm_name}:{port}"):
        try:
            if kill_pattern:
                ssh_vm.connect(
                    vm_info["mfip"] if isinstance(vm_info, dict) else str(vm_info)
                )
                ssh_vm.run(f"pkill -f '{kill_pattern}'", check_rc=False)
            else:
                stop_http_backend(ssh_vm, vm_info, port=port)
        except Exception as exc:
            logger.warning(f"停止后端服务失败: {backend_server_info}, error={exc}")


def _cleanup_backend_servers(ssh_vm, registry):
    """统一执行后端 HTTP 服务清理流程。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        registry: `LbCleanupRegistry` 实例。

    Returns:
        None.
    """
    seen = set()
    for backend_server_info in registry.backend_servers:
        vm_info = backend_server_info["vm_info"]
        port = backend_server_info["port"]
        vm_key = vm_info["mfip"] if isinstance(vm_info, dict) else str(vm_info)
        dedupe_key = (vm_key, port)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        _safe_stop_backend_server(ssh_vm, backend_server_info)


def _cleanup_listeners_and_eips(page, ssh_vm, registry):
    """统一执行监听器、公网 IP 的清理流程。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        registry: `LbCleanupRegistry` 实例。

    Returns:
        None.
    """
    if not registry.listeners and not registry.eip_bound_slbs:
        logger.info("clean_lb_listener: 无资源需清理，直接返回")
        return

    vpc_page = VpcPage(page)
    try:
        # 如果当前在监控详情页（/vpc/#/cloud-server-slb-detail），
        # goto_service 会复用页面但 #cloud-menu-left 不存在，
        # 导致 goto_submenu 失败。因此先判断当前URL，必要时直接goto列表页。
        current_url = page.url
        if "cloud-server-slb-detail" in current_url:
            base_url = page.url.split("/vpc/")[0]
            page.goto(f"{base_url}/vpc/#/vpc-load-balance-list")
            vpc_page.wait_for_page_ready()
        else:
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("负载均衡（基础版）")
        _cleanup_backend_servers(ssh_vm, registry)
        for slb_name in registry.eip_bound_slbs:
            _safe_unbind_slb_eip(vpc_page, slb_name)
        for listener_info in registry.listeners:
            _safe_delete_listener(page, vpc_page, listener_info)
    except Exception as exc:
        logger.warning(f"clean_lb_listener teardown 异常: {exc}")


def _safe_delete_ip_group(page, vpc_page, group_name):
    """尝试删除单个 IP 地址组，失败仅记录日志。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        vpc_page: 与当前页面绑定的 `VpcPage` 实例。
        group_name: 目标 IP 地址组名称。

    Returns:
        None.
    """
    with allure_step_log(f"Fixture清理: 删除IP地址组 {group_name}"):
        try:
            vpc_page.goto_submenu("IP地址组")
            page.wait_for_load_state("networkidle")
            vpc_page.ip_group_search(group_name)
            names = vpc_page.get_column_data("名称")
            if group_name in names:
                vpc_page.ip_group_delete(group_name)
                vpc_page.assert_deleted(group_name)
        except Exception as exc:
            logger.warning(f"清理IP地址组失败: {group_name}, error={exc}")


def _cleanup_ip_groups(page, registry):
    """统一执行 IP 地址组清理流程。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        registry: `IpGroupCleanupRegistry` 实例。

    Returns:
        None.
    """
    if not registry.groups:
        return

    vpc_page = VpcPage(page)
    try:
        vpc_page.goto_service("虚拟私有云")
        for group_name in registry.groups:
            _safe_delete_ip_group(page, vpc_page, group_name)
    except Exception as exc:
        logger.warning(f"clean_ip_group teardown 异常: {exc}")


@pytest.fixture(scope="function")
def clean_lb_listener(page, ssh_vm):
    """为单个测试用例提供负载均衡相关资源的清理注册器。

    直接使用测试中的 `page` 对象执行 teardown，避免新页面登录态或缓存
    状态不一致。测试阶段只需通过返回的注册器登记资源，fixture 会在
    用例结束后自动完成清理。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。
        ssh_vm: 用于连接后端虚机的 SSH 客户端。

    Yields:
        LbCleanupRegistry: 监听器与公网 IP 的清理注册器。
    """
    registry = LbCleanupRegistry()
    yield registry

    _cleanup_listeners_and_eips(page, ssh_vm, registry)


@pytest.fixture(scope="function")
def clean_ip_group(page):
    """为单个测试用例提供 IP 地址组清理注册器。

    Args:
        page: 当前测试用例使用的 Playwright page 对象。

    Yields:
        IpGroupCleanupRegistry: IP 地址组清理注册器。
    """
    registry = IpGroupCleanupRegistry()
    yield registry

    _cleanup_ip_groups(page, registry)
