"""LB 对等连接跨 VPC 场景专用 fixture。

为 `test_slb_peer_connect.py` 提供：

- `lb_peer_vms`: class 级别 fixture，在 vpc[0] 与 vpc[1] 下各创建 2 台虚机（共 4 台）并绑定 MFIP
- `slbv2_in_vpc1`: class 级别 fixture，在 vpc[0] 下创建 V2 负载均衡实例
- `clean_peer_connect`: function 级别 fixture，统一回收对等连接与跨 VPC 自定义路由规则

实现策略与 `lb_pool_candidate_vms`、`_lb_fixtures.py` 一致：
复用 `testcase/conftest.py` 中的 vm 辅助函数与 `testcase/network/conftest.py` 中的 vpc/slb 资源协议，
不重复封装 ECS 创建逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.compute import EcsPage
from sugon_web.pages.network import VpcPage
from sugon_web.pages.ops import OpsPage
from sugon_web.testcase.conftest import (
    _bind_vm_fixture_mfips,
    _build_vm_fixture_names,
    _cleanup_vm_resources,
    _collect_vm_fixture_metadata,
    _create_vm_resources,
)
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@dataclass
class PeerConnectCleanupRegistry:
    """记录单个用例创建的对等连接与跨 VPC 路由规则。

    Attributes:
        peer_connects: 待删除的对等连接名称列表。
        route_rules: 待删除的路由规则，元素为 ``(vpc_name, dest_cidr)``。
    """

    peer_connects: list[str] = field(default_factory=list)
    route_rules: list[tuple[str, str]] = field(default_factory=list)

    def add_peer_connect(self, name: str) -> None:
        self.peer_connects.append(name)

    def add_route_rule(self, vpc_name: str, dest_cidr: str) -> None:
        self.route_rules.append((vpc_name, dest_cidr))


@pytest.fixture(scope="class")
def lb_peer_vms(browser_context, config, vpc, request):
    """为跨 VPC 负载均衡场景在两个 VPC 下各创建 2 台虚机。

    依赖 `vpc` fixture 返回长度为 2 的列表，分别作为 vpc1、vpc2。
    返回值结构：

        {
            "vpc1": [vm1_1, vm1_2],
            "vpc2": [vm2_1, vm2_2],
        }

    每台虚机绑定 MFIP，并保留与 `vm` fixture 相同的元数据字段
    （`name` / `ip` / `mfip` / `network` / `subnet` 等）。
    """
    if not isinstance(vpc, list) or len(vpc) < 2:
        raise AssertionError("lb_peer_vms 需要 vpc fixture 返回至少 2 个 VPC")

    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ops_page = OpsPage(page)

    all_vm_names: list[str] = []
    grouped: dict[str, list[dict]] = {"vpc1": [], "vpc2": []}

    try:
        for group_key, vpc_info in zip(("vpc1", "vpc2"), vpc[:2]):
            base_name = f"ecs-{group_key}-{random_data(length=4)}"
            count = 2
            create_request = {
                "basic": {
                    "name": base_name,
                    "count": count,
                },
                "network": {
                    "networks": [
                        {"network": vpc_info["name"], "subnet": vpc_info["subnet_name"]}
                    ],
                    "enable_ipv6": False,
                }
            }
            vm_names = _build_vm_fixture_names(base_name, count)

            with allure_step_log(f"Setup: 在 {vpc_info['name']} 下创建 {count} 台虚机"):
                _create_vm_resources(ecs_page, create_request, vm_names)

            metadata_list = _collect_vm_fixture_metadata(
                ecs_page, vm_names, vpc_info["name"], vpc_info["subnet_name"]
            )
            _bind_vm_fixture_mfips(ecs_page, ops_page, metadata_list, vpc_info["name"])

            grouped[group_key].extend(metadata_list)
            all_vm_names.extend(vm_names)

        yield grouped
    finally:
        try:
            _cleanup_vm_resources(ecs_page, all_vm_names)
        finally:
            page.close()


@pytest.fixture(scope="class")
def slbv2_in_vpc1(browser_context, config, vpc):
    """在 vpc[0] 下创建一个 V2 负载均衡实例，测试结束后自动清理。"""
    if not isinstance(vpc, list) or len(vpc) < 1:
        raise AssertionError("slbv2_in_vpc1 需要 vpc fixture 返回列表")

    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    slb_name = f"slbv2-{random_data()}"
    target_vpc = vpc[0]["name"]

    with allure_step_log(f"Setup: 在 {target_vpc} 下创建负载均衡 V2 {slb_name}"):
        vpc_page.slb_create(
            name=slb_name,
            version="V2",
            ip_type="自动分配",
            vpc=target_vpc,
            cluster="Autotest",
            spec="slb.d6.large 2核 4GiB 内网带宽",
        )
        vpc_page.search(slb_name)
        vpc_page.assert_status(slb_name, status="运行中")

    yield slb_name

    with allure_step_log(f"Teardown: 删除负载均衡 {slb_name}"):
        try:
            vpc_page.slb_delete(slb_name)
            vpc_page.assert_deleted(slb_name)
        except Exception as exc:
            logger.warning(f"清理负载均衡 {slb_name} 失败: {exc}")
        finally:
            page.close()


def _safe_delete_route_rule(vpc_page, vpc_name, dest_cidr):
    """清理 VPC 路由表中的单条自定义路由规则，失败仅记录日志。"""
    with allure_step_log(f"Fixture清理: 删除路由规则 vpc={vpc_name}, cidr={dest_cidr}"):
        try:
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.search(vpc_name)
            vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="路由表").click()
            vpc_page.route_rule_delete(dest_cidr)
        except Exception as exc:
            logger.warning(f"清理路由规则失败: vpc={vpc_name}, cidr={dest_cidr}, error={exc}")


def _safe_delete_peer_connect(vpc_page, peer_name):
    """清理对等连接，失败仅记录日志。"""
    with allure_step_log(f"Fixture清理: 删除对等连接 {peer_name}"):
        try:
            vpc_page.goto_submenu("对等连接")
            vpc_page.peer_connect_delete(peer_name)
            vpc_page.assert_deleted(peer_name)
        except Exception as exc:
            logger.warning(f"清理对等连接失败: {peer_name}, error={exc}")


@pytest.fixture(scope="function")
def clean_peer_connect(page):
    """对等连接与跨 VPC 路由规则的统一清理注册器。

    用例只负责通过 ``add_peer_connect()`` / ``add_route_rule()`` 登记资源，
    teardown 阶段按"先路由后对等连接"的顺序自动清理（路由依赖对等连接）。
    """
    registry = PeerConnectCleanupRegistry()
    yield registry

    if not registry.peer_connects and not registry.route_rules:
        return

    vpc_page = VpcPage(page)
    for vpc_name, dest_cidr in registry.route_rules:
        _safe_delete_route_rule(vpc_page, vpc_name, dest_cidr)
    for peer_name in registry.peer_connects:
        _safe_delete_peer_connect(vpc_page, peer_name)
