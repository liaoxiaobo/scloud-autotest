import pytest
import ipaddress
import random
import re
from sugon_web.common.playwright import expect
from sugon_web.pages.compute import EcsPage
from sugon_web.pages.network import VpcPage, DcPage, ErPage, TmPage
from sugon_web.pages.network.sci_kms import SciKmsPage
from sugon_web.testcase.compute.vm_fixture.cleanup_manager import _cleanup_vm_resources
from sugon_web.testcase.compute.vm_fixture.metadata_collector import _collect_vm_fixture_metadata
from sugon_web.testcase.compute.vm_fixture.request_builder import _build_vm_create_request
from sugon_web.testcase.compute.vm_fixture.resource_creator import _build_vm_fixture_names, _create_vm_resources
from sugon_web.pages.network import VpcPage, DcPage, ErPage, TmPage, VpnPage, CfwPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page


@pytest.fixture(scope="function")
def vpc_page(page):
    """初始化虚拟私有云页面对象。

    本 fixture 用于创建 VpcPage 实例，为后续的 VPC 相关测试操作提供页面对象基础。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        VpcPage: 网络服务页面对象实例。

    Note:
        - scope 为 function 级别，每个测试函数创建独立的页面对象
        - 页面导航按需由页面方法自身完成

    Example:
        def test_vpc_create(vpc_page):
            vpc_page.vpc_create(name="test-vpc", cidr="10.0.0.0/24")
    """
    return VpcPage(page)


@pytest.fixture(scope="function")
def cfw_page(page):
    """初始化云防火墙页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        CfwPage: 云防火墙页面对象实例。
    """
    return CfwPage(page)


@pytest.fixture(scope="function")
def dc_page(page):
    """初始化云专线DC页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        DcPage: 云专线DC页面对象实例。
    """
    return DcPage(page)


@pytest.fixture(scope="function")
def er_page(page):
    """初始化企业路由器页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        ErPage: 企业路由器页面对象实例。
    """
    return ErPage(page)


@pytest.fixture(scope="function")
def tm_page(page):
    """初始化流量镜像页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        TmPage: 流量镜像页面对象实例。
    """
    return TmPage(page)


@pytest.fixture(scope="function")
def vpn_page(page):
    """初始化虚拟专用网络VPN页面对象。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        VpnPage: 虚拟专用网络VPN页面对象实例。
    """
    return VpnPage(page)


def _build_vpc_create_kwargs(params=None):
    """根据参数构建VPC创建入参。"""
    params = params or {}
    name_prefix = params.get('name_prefix', '')
    name = params.get('name', random_data(length=3))
    if name_prefix:
        name = f"{name_prefix}{name}"

    return {
        "name": name,
        "subnet_name": params.get('subnet_name', random_data()),
        "cidr": params.get('cidr', random_data("cidr")),
        "desc": params.get('desc', ''),
        "subnet_desc": params.get('subnet_desc', ''),
        "network_type": params.get('network_type', 'Geneve'),
        "gateway_mode": params.get('gateway_mode', "分布式网关"),
        "vlan_id": params.get('vlan_id'),
        "gateway_ip": params.get('gateway_ip'),
        "mac": params.get('mac'),
        "enable_ipv6": params.get('enable_ipv6', False),
        "acl_policy": params.get('acl_policy'),
    }


def _resolve_param_refs(value, request):
    """递归解析参数中的 `@fixture.path` 引用。

    Args:
        value: 待解析的原始值，可以是标量、字典或列表。
        request: 当前 pytest 请求对象，用于动态获取 fixture 返回值。

    Returns:
        Any: 解析后的值。若字符串不符合引用语法，则直接返回原值。
    """
    if isinstance(value, dict):
        return {key: _resolve_param_refs(item, request) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_param_refs(item, request) for item in value]
    if not isinstance(value, str) or not value.startswith("@"):
        return value

    expression = value[1:]
    match = re.match(r"^(?P<fixture>[a-zA-Z_]\w*)(?P<path>(?:\.[^. \[\]]+|\[\d+\])*)$", expression)
    if not match:
        return value

    resolved = request.getfixturevalue(match.group("fixture"))
    path = match.group("path")
    if not path:
        return resolved

    token_pattern = re.compile(r"\.(?P<key>[^.\[\]]+)|\[(?P<index>\d+)\]")
    for token in token_pattern.finditer(path):
        key = token.group("key")
        index = token.group("index")
        if key is not None:
            resolved = resolved[key]
        else:
            resolved = resolved[int(index)]
    return resolved


def _create_vpc_resource(vpc_page, params=None):
    """创建VPC并返回资源信息。"""
    create_kwargs = _build_vpc_create_kwargs(params)
    vpc_page.vpc_create(**create_kwargs)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    vpc_page.assert_status(create_kwargs["name"])

    return create_kwargs


def _build_extra_subnet_create_kwargs(vpc_name, params=None):
    """根据参数构建额外子网创建入参。

    Args:
        vpc_name: 目标 VPC 名称。
        params: 额外子网参数，支持 `subnet_name`、`cidr`、`acl_policy`。

    Returns:
        dict: 可直接传给 `subnet_create` 的子网创建参数字典。
    """
    params = params or {}
    return {
        "vpc_name": vpc_name,
        "subnet_name": params.get("subnet_name", random_data()),
        "cidr": params.get("cidr", random_data("cidr")),
        "acl_policy": params.get("acl_policy"),
    }


def _create_extra_subnets(vpc_page, vpc_name, extra_subnets=None):
    """为指定 VPC 批量创建额外子网并返回最小元数据。

    Args:
        vpc_page: VPC 页面对象。
        vpc_name: 目标 VPC 名称。
        extra_subnets: 额外子网参数列表。

    Returns:
        list[dict]: 已创建子网的最小描述列表，包含名称、CIDR 和 ACL 策略。
    """
    created_subnets = []
    for subnet_params in extra_subnets or []:
        create_kwargs = _build_extra_subnet_create_kwargs(vpc_name, subnet_params)
        vpc_page.subnet_create(**create_kwargs)
        created_subnets.append({
            "name": create_kwargs["subnet_name"],
            "cidr": create_kwargs["cidr"],
            "acl_policy": create_kwargs.get("acl_policy"),
        })
    return created_subnets


def _build_vpc_batch_params(params, count):
    """构建批量创建VPC时每个资源的参数列表。"""
    params = params or {}
    if count == 1:
        return [params]

    base_name = params.get("name")
    batch_params = []
    for index in range(count):
        item_params = dict(params)
        if base_name:
            item_params["name"] = f"{base_name}-{index}"
        batch_params.append(item_params)
    return batch_params


def _cleanup_vpc_resource(vpc_page, name, extra_subnets=None):
    """清理 VPC 及其关联资源。

    本函数在删除 VPC 之前，先拆除由本 VPC 创建/引入的对外依赖，
    避免把残留依赖留给后续 teardown 的其他 fixture。

    Args:
        vpc_page: VpcPage 页面对象，兼具 VPC 与 ACL 的操作能力。
        name: 待删除的 VPC 名称。
        extra_subnets: VPC 创建时生成的额外子网元数据列表，元素格式示例：
            [{"name": "sub-xxx", "cidr": "10.0.1.0/24", "acl_policy": "acl-yyy"}, ...]
            当子网配置了 acl_policy 时，表示该子网在创建时已绑定到指定 ACL。

    典型问题场景（已修复）：
        test_acl_enable_disable 通过参数化 vpc 创建了一个绑定到 class 级 acl 的额外子网：
            @pytest.mark.parametrize(
                "vpc",
                [{"extra_subnets": [{"cidr": "10.241.2.0/24", "acl_policy": "@acl"}]}],
                indirect=True,
            )
    使用原则：
        - 只要通过 vpc fixture 的 extra_subnets 给子网配置了 acl_policy，本函数会自动在
          删除 VPC 前调用 acl_disassociate_subnet 解除绑定，无需在用例或 acl fixture 里额外处理。
        - 如果后续新增类似的「VPC 创建时建立、但会阻塞后续 fixture 清理」的依赖，
          应在本函数中统一前置拆除，而不是分散到各个用例里。
        - try/except 是故意设计：解关联失败（如已解绑、ACL 已不存在）不应阻塞 VPC 删除。

    前端规则参考：
        src/page/vpc/acl/index-table.js 中 aclCanDelete 要求 row.rel_subnets.length == 0，
        否则 src/page/vpc/acl/index.vue 中 batchDeleteDisabled 为 true，批量删除置灰。
    """
    extra_subnets = extra_subnets or []
    for subnet in extra_subnets:
        acl_policy = subnet.get("acl_policy")
        subnet_name = subnet.get("name")
        if acl_policy and subnet_name:
            try:
                with allure_step_log(f"清理VPC {name}: 解关联子网 {subnet_name} 与 ACL {acl_policy}"):
                    vpc_page.acl_disassociate_subnet(acl_policy, subnets=[subnet_name])
            except Exception as e:
                logger.warning(f"解关联子网 {subnet_name} 与 ACL {acl_policy} 失败（可能已解关联）: {e}")

    # 先导航到VPC列表页确保状态正确
    vpc_page._ensure_vpc_network_list()
    try:
        vpc_page.get_row_by_name(name)
    except Exception:
        logger.info(f"VPC {name} 已不存在，跳过清理")
        return
    vpc_page.vpc_delete(name)
    # 刷新页面并验证删除，避免前端缓存导致误判
    vpc_page.page.reload()
    vpc_page.wait_for_page_ready()
    vpc_page._ensure_vpc_network_list()
    vpc_page.assert_deleted(name)
    expect(vpc_page.alert).to_have_count(0, timeout=10000)


@pytest.fixture(scope="class")
def vpc(browser_context, config, request):
    """创建并返回虚拟私有云资源，测试结束后自动清理。

    本 fixture 支持单个或批量创建 VPC，并为每个 VPC 自动创建默认子网。
    创建的资源在测试结束后自动清理，确保测试环境干净。

    Args:
        browser_context: Playwright 浏览器上下文，由 pytest fixture 提供。
        config: 测试配置对象，由 pytest fixture 提供。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        name (str): VPC 名称，未提供时自动生成随机名称。
        subnet_name (str): 默认子网名称，未提供时自动生成。
        cidr (str): 子网 CIDR，未提供时自动生成随机 CIDR。
        desc (str): VPC 描述，默认为空。
        subnet_desc (str): 子网描述，默认为空。
        network_type (str): 网络类型，默认为 "Geneve"。
        gateway_mode (str): 网关模式，默认为 "分布式网关"。
        enable_ipv6 (bool): 是否启用 IPv6，默认为 False。
        acl_policy (str): ACL 策略名称，可选。
        count (int): 创建 VPC 数量，默认为 1。
        extra_subnets (list[dict]): 额外子网参数列表，每个元素支持 subnet_name、cidr、acl_policy。

    Yields:
        dict | list[dict]: 创建单个 VPC 时返回资源字典，批量创建时返回列表。
        每个资源字典包含：
            - name (str): VPC 名称
            - subnet_name (str): 默认子网名称
            - cidr (str): 子网 CIDR
            - desc (str): VPC 描述
            - extra_subnets (list[dict]): 额外子网元数据列表（如有）

    Note:
        - scope 为 class 级别，在整个测试类内共享复用
        - 支持通过 `@fixture.path` 语法引用其他 fixture（如 `@vpc[0].name`）
        - 批量创建时名称自动添加 `-index` 后缀

    Example:
        @pytest.mark.parametrize("vpc", [{"name": "test-vpc", "cidr": "192.168.0.0/16"}], indirect=True)
        def test_vpc_single(vpc):
            assert vpc["name"] == "test-vpc"

        @pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
        def test_vpc_batch(vpc):
            # vpc 返回包含 2 个 VPC 的列表
            assert len(vpc) == 2
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)

    params = _resolve_param_refs(getattr(request, 'param', {}) or {}, request)
    count = params.get("count", 1)
    params_list = _build_vpc_batch_params(params, count)

    with allure_step_log(f"创建 {count} 个虚拟私有云"):
        vpc_list = []
        for item_params in params_list:
            extra_subnets = item_params.pop("extra_subnets", [])
            vpc_resource = _create_vpc_resource(vpc_page, item_params)
            vpc_resource["extra_subnets"] = _create_extra_subnets(vpc_page, vpc_resource["name"], extra_subnets)
            vpc_list.append(vpc_resource)

    yield vpc_list[0] if count == 1 else vpc_list

    with allure_step_log(f"清理虚拟私有云 {[item['name'] for item in vpc_list]}"):
        for item in vpc_list:
            _cleanup_vpc_resource(vpc_page, item["name"], item.get("extra_subnets", []))
    page.close()


@pytest.fixture(scope="function")
def eip(vpc_page, request):
    """创建并返回弹性公网 IP，测试结束后自动清理。

    本 fixture 支持从指定 IP 池分配单个或多个弹性公网 IP，
    并在测试结束后自动释放已分配的 IP 资源。

    Args:
        vpc_page: VPC 页面对象，由 vpc_page fixture 提供。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        count (int): 需分配的 EIP 数量，默认为 1。
        pool (str): IP 池名称，默认为 "public_net(基础版)"。
        method (str): 分配方式，支持 "快速选择"、"手动输入"，默认为 "快速选择"。
        ip (str): 手动分配时指定的 IP 地址，可选。

    Yields:
        str | list[str]: 分配单个 IP 时返回 IP 地址字符串，批量分配时返回 IP 地址列表。

    Note:
        - scope 为 function 级别，每个测试函数分配独立的 IP 资源
        - 清理时会自动切换到对应的 IP 池进行释放操作

    Example:
        @pytest.mark.parametrize("eip", [{"count": 2}], indirect=True)
        def test_eip_batch(eip):
            # eip 返回包含 2 个 IP 地址的列表
            for ip in eip:
                print(f"分配的 IP: {ip}")
    """
    params = getattr(request, 'param', {})
    count = params.get('count', 1)
    pool = params.get('pool', 'public_net(基础版)')
    method = params.get('method', '快速选择')
    ip = params.get('ip')

    with allure_step_log(f"Setup: 分配 {count} 个弹性公网IP"):
        created_ips = vpc_page.eip_allocate(pool=pool, count=count, method=method, ip=ip)

    yield created_ips[0] if count == 1 else created_ips

    with allure_step_log(f"Teardown: 释放弹性公网IP {created_ips}"):
        if not created_ips:
            return
        try:
            current_ips = created_ips if isinstance(created_ips, list) else [created_ips]
            for current_ip in current_ips:
                vpc_page.switch_eip_pool(pool)
                vpc_page.search(current_ip)
                if vpc_page.get_eip_list():
                    vpc_page.eip_release(current_ip)
                    vpc_page.assert_deleted(current_ip)
                vpc_page.btn_reset.click()
        except Exception as e:
            logger.warning(f"清理弹性公网IP时出错: {e}")


@pytest.fixture(scope="function")
def vip(vpc_page, vpc):
    """创建并返回手动分配的虚拟 IP，测试结束后自动清理。

    本 fixture 在指定 VPC 的子网中创建一个虚拟 IP 端口，
    IP 地址从子网可用 IP 段中随机选择，避开前 10 个地址以防冲突。

    Args:
        vpc_page: VPC 页面对象，由 vpc_page fixture 提供。
        vpc: VPC 资源字典，由 vpc fixture 提供，包含 name、subnet_name、cidr。

    Yields:
        str: 创建的虚拟 IP 地址。

    Note:
        - scope 为 function 级别，每个测试函数创建独立的虚拟 IP
        - IP 地址从子网 hosts 中随机选择，跳过前 10 个地址
        - 适用于高可用场景或需要固定 IP 的测试用例

    Example:
        def test_vip_usage(vip, vpc):
            # vip 返回虚拟 IP 地址字符串
            print(f"虚拟 IP: {vip}, 所属 VPC: {vpc['name']}")
    """
    vpc_name = vpc['name']
    subnet_name = vpc['subnet_name']
    cidr = vpc['cidr']

    # 计算可用IP，避开网关（通常是第一个IP）
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = list(network.hosts())
    # 随机选择一个IP，跳过前10个IP以防冲突
    vip_address = str(random.choice(hosts[10:])) if len(hosts) > 20 else str(random.choice(hosts[2:]))

    logger.info(f"准备创建虚拟IP {vip_address}")
    vpc_page.goto_submenu("虚拟私有云")
    vpc_page.vip_create(vpc_name=vpc_name, subnet_name=subnet_name, ip_address=vip_address)
    vpc_page.assert_popup_success("申请虚拟IP端口成功")

    yield vip_address

    # 确保在正确的 tab 页
    vpc_page.goto_submenu("虚拟私有云")
    vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
    vpc_page.get_by_role("tab", name="虚拟IP管理").click()

    logger.info(f"清理虚拟IP {vip_address}")

    # 先获取一次行数据，检查是否仍有绑定关系
    # 避免对已解绑的VIP重复点击禁用状态的按钮浪费时间
    try:
        row_data = vpc_page.get_row_data(vip_address)
    except Exception:
        logger.info(f"VIP {vip_address} 已从列表中消失，无需清理")
        return

    bound_instance = row_data.get("绑定的实例") or ""
    bound_eip = row_data.get("绑定的公网IP") or ""

    # 仅在有实际绑定值时才执行解绑（按钮可用状态）
    if bound_instance and bound_instance != "--":
        instance_name = bound_instance.split("(")[0] if "(" in bound_instance else bound_instance
        logger.info(f"VIP {vip_address} 仍绑定实例 {instance_name}，先解绑")
        try:
            vpc_page.vip_unbind_instance(vip_address, instance_name)
            vpc_page.wait_for_page_ready()
            vpc_page.page.wait_for_timeout(2000)
        except Exception as e:
            logger.debug(f"VIP解绑实例时出错: {e}")

    if bound_eip and bound_eip != "--":
        logger.info(f"VIP {vip_address} 仍绑定公网IP {bound_eip}，先解绑")
        try:
            vpc_page.vip_unbind_eip(vip_address)
            vpc_page.wait_for_page_ready()
            vpc_page.page.wait_for_timeout(2000)
        except Exception as e:
            logger.debug(f"VIP解绑公网IP时出错: {e}")

    try:
        vpc_page.vip_delete(vip_address)
    except Exception as e:
        logger.warning(f"清理虚拟IP失败: {e}")


@pytest.fixture(scope="function")
def port(vpc_page, vpc, request):
    """创建并返回指定数量的端口，测试结束后自动清理。

    本 fixture 在指定 VPC 的子网中创建多个端口，IP 地址从子网可用 IP 段
    中随机选择，跳过前 20 个地址以避开网关、DHCP 和系统保留地址。

    Args:
        vpc_page: VPC 页面对象，由 vpc_page fixture 提供。
        vpc: VPC 资源字典，由 vpc fixture 提供，包含 name、subnet_name、cidr。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        count (int): 需创建的端口数量，默认为 1。

    Yields:
        list[str]: 创建的端口 IP 地址列表。

    Raises:
        ValueError: 当子网 IP 资源不足以创建指定数量的端口时抛出。

    Note:
        - scope 为 function 级别，每个测试函数创建独立的端口
        - IP 地址使用手动分配-快速选择模式创建
        - 批量删除在 teardown 时自动执行

    Example:
        @pytest.mark.parametrize("port", [{"count": 3}], indirect=True)
        def test_port_batch(port):
            # port 返回包含 3 个端口 IP 的列表
            for ip in port:
                print(f"端口 IP: {ip}")
    """
    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    count = params.get('count', 1)

    vpc_name = vpc['name']
    subnet_name = vpc['subnet_name']
    cidr = vpc['cidr']

    created_ports = []

    # 准备IP池，避开网关和可能的VIP
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = list(network.hosts())
    # 随机选择一个IP，跳过前20个IP以防冲突（保留给网关、DHCP、系统组件等）
    start_index = 20 if len(hosts) > 30 else 2
    if len(hosts) - start_index < count:
        raise ValueError(f"子网IP资源不足，无法创建 {count} 个端口")

    available_hosts = hosts[start_index:]
    selected_ips = random.sample(available_hosts, count)

    # 步骤1: 创建端口
    with allure_step_log(f"Setup: 创建 {count} 个端口"):
        for i, ip_obj in enumerate(selected_ips):
            port_ip = str(ip_obj)

            # 使用手动分配-快速选择模式创建端口
            vpc_page.port_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                ip_address=port_ip,
                quick_select=True
            )
            vpc_page.assert_popup_success("添加端口成功")

            # 验证新建的端口IP是否在列表中
            # 注意：port_create执行后已经位于端口Tab页
            # 虽然我们指定了IP，但为了保险起见，还是从页面确认一下
            # port_list = vpc_page.get_column_data('固定IP', context="active-tab")
            # if port_ip in port_list:
            created_ports.append(port_ip)
            logger.info(f"已创建端口[{i+1}/{count}]: {port_ip}")
            # else:
            #     logger.warning(f"未能获取到新建端口的IP: {port_ip}")

    yield created_ports

    # 步骤2: 清理端口
    if created_ports:
        with allure_step_log(f"Teardown: 清理端口 {created_ports}"):
            try:
                # 确保在正确的页面（VPC详情 -> 端口Tab）
                vpc_page.goto_detail_page(vpc_name, tab_name="端口")

                # 批量删除端口
                vpc_page.port_delete(created_ports)
                vpc_page.assert_deleted(created_ports)
                logger.info("端口清理完成")
            except Exception as e:
                logger.warning(f"清理端口时出错: {e}")


@pytest.fixture(scope="function")
def nat(vpc_page, vpc, request):
    """创建并返回 NAT 网关，测试结束后自动清理。

    本 fixture 在指定 VPC 中创建 NAT 网关，支持绑定弹性公网 IP。
    网关名称自动生成，资源在测试结束后自动删除。

    Args:
        vpc_page: VPC 页面对象，由 vpc_page fixture 提供。
        vpc: VPC 资源字典，由 vpc fixture 提供，包含 name。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        eip (str): 绑定的弹性公网 IP，可选。
        public_ip_pool (str): 公网 IP 池名称，默认为 "public_net(基础版)"。
        desc (str): NAT 网关描述，默认为 "NAT网关fixture自动创建"。

    Yields:
        dict: NAT 网关信息字典，包含：
            - name (str): NAT 网关名称

    Note:
        - scope 为 function 级别，每个测试函数创建独立的 NAT 网关
        - teardown 从返回字典中读取名称，支持测试中修改名称后正确清理
        - 名称使用 random_data 自动生成

    Example:
        @pytest.mark.parametrize("nat", [{"eip": "1.2.3.4"}], indirect=True)
        def test_nat_with_eip(nat):
            print(f"NAT 网关: {nat['name']}")
    """
    from sugon_web.utils.data import random_data

    params = getattr(request, 'param', {})
    eip = params.get('eip', None)
    public_ip_pool = params.get('public_ip_pool', 'public_net(基础版)')
    desc = params.get('desc', 'NAT网关fixture自动创建')

    vpc_name = vpc['name']
    nat_name = random_data()

    with allure_step_log(f"Setup: 创建NAT网关 {nat_name}"):
        vpc_page.nat_create(
            name=nat_name,
            vpc_name=vpc_name,
            public_ip_pool=public_ip_pool,
            eip=eip,
            desc=desc
        )
        vpc_page.assert_popup_success("新建NAT网关成功")
        logger.info(f"NAT网关 {nat_name} 创建成功")

    nat_info = {"name": nat_name}
    yield nat_info

    # 注意：teardown 从 nat_info['name'] 读取，而不是闭包变量 nat_name
    # 这样测试里执行 nat['name'] = new_name 后，teardown 能感知到新名称
    current_name = nat_info['name']
    with allure_step_log(f"Teardown: 删除NAT网关 {current_name}"):
        try:
            vpc_page.nat_delete(current_name)
            logger.info(f"NAT网关 {current_name} 删除成功")
        except Exception as e:
            logger.warning(f"清理NAT网关时出错: {e}")


@pytest.fixture(scope="function")
def cfw(cfw_page, request):
    """创建并返回云防火墙。

    本 fixture 仅负责创建云防火墙，创建成功后即交由测试使用，
    测试结束后不执行删除（按业务需求保留实例）。

    Args:
        cfw_page: 云防火墙页面对象，由 cfw_page fixture 提供。
        request: pytest 请求对象，用于获取参数化配置。

    request.param 支持的参数：
        name (str): 云防火墙名称，默认自动生成。
        version (str): 防火墙版本，默认"山石引擎-5.5"。
        cluster (str): 部署集群，默认"Autotest"。
        protected_resource (str): 待防护资源标识，可选。

    Yields:
        dict: 云防火墙信息字典，包含：
            - name (str): 云防火墙名称

    Example:
        @pytest.mark.parametrize("cfw", [{"version": "山石引擎-5.5", "cluster": "Autotest"}], indirect=True)
        def test_cfw_with_cluster(cfw):
            print(f"云防火墙: {cfw['name']}")
    """
    params = getattr(request, 'param', {})
    name = params.get('name', random_data())
    version = params.get('version', '山石引擎-5.5')
    cluster = params.get('cluster', 'Autotest')
    protected_resource = params.get('protected_resource')

    with allure_step_log(f"Setup: 创建云防火墙 {name}"):
        cfw_page.cfw_create(
            name=name,
            version=version,
            cluster=cluster,
            protected_resource=protected_resource,
        )
        logger.info(f"云防火墙 {name} 创建成功")

    with allure_step_log(f"Setup: 等待云防火墙 {name} 状态变为运行中"):
        cfw_page.assert_status(name, status="运行中", timeout=1200, refresh=True, refresh_interval=10)

    yield {"name": name}


@pytest.fixture(scope="function")
def qos(vpc_page):
    """创建并返回网络 QoS 策略，测试结束后自动清理。

    本 fixture 创建一个网络 QoS 策略，用于限制虚机的网络带宽。
    QoS 名称自动生成，资源在测试结束后自动删除。

    Args:
        vpc_page: VPC 页面对象，由 vpc_page fixture 提供。

    Yields:
        dict: QoS 策略信息字典，包含：
            - name (str): QoS 策略名称
            - send_rate (int): 发送速率限制（Mbps），默认为 10
            - recv_rate (int): 接收速率限制（Mbps），默认为 20
            - desc (str): QoS 描述

    Note:
        - scope 为 function 级别，每个测试函数创建独立的 QoS 策略
        - QoS 参数固定为 send_rate=10, recv_rate=20
        - 名称格式为 "qos-{random_data()}"

    Example:
        def test_qos_create(qos):
            print(f"QoS 名称: {qos['name']}, 发送速率: {qos['send_rate']} Mbps")
    """
    qos_info = {
        "name": f"qos-{random_data()}",
        "send_rate": 10,
        "recv_rate": 20,
        "desc": "网络QoS fixture 自动创建",
    }

    with allure_step_log("Setup: 创建网络QoS"):
        vpc_page.qos_create(
            name=qos_info["name"],
            send_rate=qos_info["send_rate"],
            recv_rate=qos_info["recv_rate"],
            desc=qos_info["desc"]
        )
        vpc_page.assert_popup_success()

    yield qos_info

    with allure_step_log(f"Teardown: 删除网络QoS {qos_info['name']}"):
        try:
            vpc_page.qos_delete(qos_info["name"])
            vpc_page.assert_deleted(qos_info["name"])
        except Exception as e:
            logger.warning(f"清理网络QoS时出错: {e}")


def _normalize_sg_names(value):
    """将安全组名称统一转换为列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_vm_items(value):
    """将 vm fixture 返回值统一转换为列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _create_security_groups(vpc_page, count):
    """创建指定数量的安全组并返回名称列表。"""
    if count <= 0:
        return []

    names = []
    with allure_step_log(f"创建 {count} 个安全组"):
        for _ in range(count):
            sg_name = random_data()
            vpc_page.sg_create(sg_name, desc=f"{sg_name}自动创建的安全组")
            expect(vpc_page.popup).to_have_count(0)
            names.append(sg_name)
    return names


def _cleanup_security_groups(vpc_page, names):
    """删除安全组。"""
    if not names:
        return
    with allure_step_log(f"清理安全组 {names}"):
        vpc_page.sg_delete(names)
        vpc_page.assert_deleted(names)


def _bind_security_groups_to_vms(ecs_page, vm_data, sg_names):
    """将安全组绑定到虚机。"""
    vm_items = _normalize_vm_items(vm_data)
    current_sgs = _normalize_sg_names(sg_names)
    if not vm_items or not current_sgs:
        return

    with allure_step_log(f"绑定安全组 {current_sgs} 到虚机 {[item['name'] for item in vm_items]}"):
        for item in vm_items:
            ecs_page.ecs_to_sg_tab(item["name"])
            bound_sgs = ecs_page.ecs_get_bound_security_groups()
            # VM 创建后通常会自动绑定 default，先解绑以避免干扰安全组生效性验证。
            if "default" in bound_sgs and "default" not in current_sgs:
                ecs_page.ecs_set_security_groups(["default"], bind=False)
            ecs_page.ecs_set_security_groups(current_sgs, bind=True)


def _unbind_security_groups_from_vms(ecs_page, vm_data, sg_names):
    """从虚机解绑安全组。"""
    vm_items = _normalize_vm_items(vm_data)
    current_sgs = _normalize_sg_names(sg_names)
    if not vm_items or not current_sgs:
        return

    with allure_step_log(f"从虚机 {[item['name'] for item in vm_items]} 解绑安全组 {current_sgs}"):
        for item in vm_items:
            ecs_page.ecs_to_sg_tab(item["name"])
            bound_sgs = ecs_page.ecs_get_bound_security_groups()
            target_sgs = [name for name in current_sgs if name in bound_sgs]
            if target_sgs:
                ecs_page.ecs_set_security_groups(target_sgs, bind=False)


@pytest.fixture(scope="function")
def sg(vpc_page, request):
    """创建并返回安全组名称，测试结束后自动清理。

    本 fixture 支持创建单个或多个安全组，安全组名称自动生成。
    资源在测试结束后自动删除，确保测试环境干净。

    Args:
        vpc_page: VpcPage 实例，由 pytest fixture 提供。
        request: pytest 请求对象，用于获取参数化配置。

    request.param:
        int: 需要创建的安全组数量，默认为 1。若值为 <= 0，则返回空列表。

    Yields:
        str | list[str]: 创建单个安全组时返回名称字符串，批量创建时返回名称列表。
        若 count <= 0，返回空列表。

    Note:
        - scope 为 function 级别，每个测试函数创建独立的安全组
        - 安全组描述自动设置为 "{name}自动创建的安全组"
        - 名称使用 random_data 自动生成
        - 使用独立的浏览器页面，避免与其他 fixture 的页面冲突

    Example:
        @pytest.mark.parametrize("sg", [2], indirect=True)
        def test_sg_batch(sg):
            # sg 返回包含 2 个安全组名称的列表
            for name in sg:
                print(f"安全组: {name}")
    """

    count = getattr(request, "param", 1)
    if count <= 0:
        yield []
        return

    names = _create_security_groups(vpc_page, count)

    yield names[0] if count == 1 else names

    _cleanup_security_groups(vpc_page, names)


@pytest.fixture(scope="function")
def vm_sg_binding(ecs_page, vm, sg):
    """将 function 级 sg 显式绑定到 class 级 vm，并在测试结束后自动解绑。"""
    _bind_security_groups_to_vms(ecs_page, vm, sg)
    try:
        yield {"vm": vm, "sg": sg}
    finally:
        _unbind_security_groups_from_vms(ecs_page, vm, sg)

@pytest.fixture(scope="class")
def acl(browser_context, config):
    """
    创建并返回一个网络ACL名称，测试结束后自动清理
    该fixture使用function scope的page会引发ScopeMismatch异常，
    如果您的项目中 vpc_page 是 function scope，而 sg(vpc_page) 声明了 class scope，说明项目做了特定处理。
    为安全起见，这里提供标准实现。
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    acl_name = f"acl-{random_data()}"

    # 创建网络ACL
    with allure_step_log(f"fixture前置: 创建网络ACL{acl_name}"):
        vpc_page.acl_create(acl_name, desc=f"{acl_name} 自动化测试创建")

    yield acl_name

    # 测试结束后清理
    with allure_step_log(f"fixture后置: 清理网络ACL{acl_name}"):
        vpc_page.acl_batch_delete([acl_name])
    page.close()


@pytest.fixture(scope="class")
def slb(browser_context, config, vpc, request):
    """
    创建并返回一个负载均衡名称，测试结束后自动清理

    可通过 pytest.mark.parametrize("slb", [{"version": "V1", ...}], indirect=True) 传参：
    - version: "V1" 或 "V2" (默认 "V2")
    - ha_enable: True 或 False (默认 False)
    - ip_type: "自动分配", "快速选择", "手动输入" (默认 "自动分配")
    - ip_address: 手动分配时的 IP 地址。如果不提供且 ip_type 为手动，则动态获取
    - cluster: V2 时的集群名称 (默认 "Autotest")
    - spec: V2 时的规格 (默认 "slb.d6.large 2核 4GiB 内网带宽")
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    params = getattr(request, 'param', {})
    version = params.get('version', "V2")
    ha_enable = params.get('ha_enable', False)
    ip_type = params.get('ip_type', "自动分配")
    ip_address = params.get('ip_address', None)
    cluster = params.get('cluster', "Autotest") if version == "V2" else None
    spec = params.get('spec', "slb.d6.large 2核 4GiB 内网带宽") if version == "V2" else None

    # 动态处理 IP（如果 ip_type 是手动但没给明确 IP）
    if ip_type in ["快速选择", "手动输入"] and not ip_address:
        cidr = vpc['cidr']
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 避开前10个和最后10个地址以防网关或系统保留 IP 冲突
        safe_hosts = hosts[10:-10] if len(hosts) > 20 else hosts
        ip_address = str(random.choice(safe_hosts))

    slb_name = params.get("name", f"slb-{random_data()}")

    with allure_step_log(f"Setup: 创建负载均衡 {slb_name}"):
        vpc_page.slb_create(
            name=slb_name,
            version=version,
            ha_enable=ha_enable,
            ip_type=ip_type,
            ip_address=ip_address,
            vpc=vpc['name'],
            cluster=cluster,
            spec=spec
        )
        # 等待创建成功并验证状态入运行中
        vpc_page.search(slb_name)
        vpc_page.assert_status(slb_name, status="运行中")

    # 进入详情页获取完整信息（列表页信息不全）
    with allure_step_log(f"Setup: 获取负载均衡 {slb_name} 详情信息"):
        detail_info = vpc_page.get_slb_detail_info(slb_name)

    yield {
        "name": slb_name,
        "vip": detail_info.get("vip"),
        "id": detail_info.get("id"),
        "status": detail_info.get("status"),
        "version": detail_info.get("version"),
        "ha": detail_info.get("ha"),
        "ha_enable": ha_enable,
    }

    with allure_step_log(f"Teardown: 清理负载均衡 {slb_name}"):
        try:
            vpc_page.slb_delete(slb_name)
            vpc_page.assert_deleted(slb_name)
        except Exception as e:
            logger.warning(f"清理负载均衡 {slb_name} 失败: {e}")
        finally:
            page.close()

@pytest.fixture(scope="class")
def lb(browser_context, config, slb, request):
    """
    按需创建并返回一个默认的监听器实例字典，在整个类内共享复用测试结束后自动清理。
    可以通过 pytest.mark.parametrize("lb", [{"port": 81}], indirect=True) 传参定制。
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    params = getattr(request, "param", {})

    params.setdefault("slb_name", slb["name"])
    params.setdefault("protocol", "TCP")
    params.setdefault("port", 80)

    protocol = params["protocol"]
    params.setdefault("lb_name", f"lb-{protocol.lower()}-{random_data()}")
    params.setdefault("pool_name", f"pool-{random_data()}")

    if params.get("desc") is None:
        params["desc"] = f"Autotest listener {params['lb_name']}"

    params.setdefault("health_check", False)

    lb_name = params["lb_name"]

    with allure_step_log(f"Setup: 创建默认监听器 {lb_name}"):
        vpc_page.slb_lb_create(**params)
        vpc_page.assert_popup_success()
        vpc_page.assert_listener_exists(lb_name)

    listener_info = {
        "slb_name": params["slb_name"],
        "name": params["lb_name"],
        "protocol": params["protocol"],
        "port": params["port"],
        "desc": params["desc"],
        "pool_name": params["pool_name"],
        "balance_method": params.get("balance_method", "轮询"),
        "health_check": params.get("health_check", False),
        "session_persistence": params.get("session_persistence", False),
        "acl_enable": params.get("acl_enable", False),
        "access_policy": params.get("access_policy"),
        "ip_group": params.get("ip_group"),
    }

    yield listener_info

    with allure_step_log(f"Teardown: 删除监听器 {listener_info['name']}"):
        try:
            current_name = listener_info["name"]
            vpc_page.goto_slb_detail(listener_info["slb_name"], "监听器")
            vpc_page.assert_listener_exists(current_name)
            vpc_page.slb_lb_delete(listener_info["slb_name"], current_name)
            vpc_page.assert_popup_success()
        except Exception as exc:
            logger.warning(f"listener cleanup failed: {current_name}, error={exc}")
        finally:
            page.close()


@pytest.fixture(scope="class")
def ip_group(browser_context, config, request):
    """创建 IP 地址组，并在测试结束后自动清理。"""
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)

    params = getattr(request, "param", {})
    group_info = {
        "name": f"ipg-{random_data()}",
        "ip_addresses": ["10.10.10.10"],
        "desc": "IP地址组 fixture 自动创建",
        "enable_ipv6": False,
    }
    group_info.update(params)
    # 空 IP 列表可能导致表单验证失败，回退为默认 IP
    if not group_info.get("ip_addresses"):
        group_info["ip_addresses"] = ["10.10.10.10"]

    with allure_step_log(f"Setup: 创建 IP 地址组 {group_info['name']}"):
        vpc_page.ip_group_create(
            name=group_info["name"],
            ip_addresses=group_info["ip_addresses"],
            desc=group_info["desc"],
            enable_ipv6=group_info["enable_ipv6"],
        )
        # 验证创建成功：在列表中搜索并确认存在
        vpc_page.ip_group_search(group_info["name"])
        names = vpc_page.get_column_data("名称")
        if group_info["name"] not in names:
            raise AssertionError(f"IP地址组 {group_info['name']} 创建后在列表中未找到")

    yield group_info

    with allure_step_log(f"Teardown: 清理 IP 地址组 {group_info['name']}"):
        try:
            vpc_page.ip_group_search(group_info["name"])
            names = vpc_page.get_column_data("名称")
            if group_info["name"] in names:
                vpc_page.ip_group_delete(group_info["name"])
                vpc_page.assert_deleted(group_info["name"])
        except Exception as exc:
            logger.warning(f"清理 IP 地址组失败: {exc}")
        finally:
            page.close()


@pytest.fixture(scope="function")
def internal_dns(vpc_page, vpc):
    """创建并返回一个内网解析，测试结束后自动清理。"""
    dns_info = {
        "domain": f"dns-{random_data()}.com",
        "vpc_name": vpc["name"],
        "email": "admin@test.com",
        "desc": f"内网解析自动化测试-{random_data(length=4)}",
    }

    with allure_step_log(f"Setup: 创建内网解析 {dns_info['domain']}"):
        vpc_page.internal_dns_create(
            domain=dns_info["domain"],
            vpc_name=dns_info["vpc_name"],
            email=dns_info["email"],
            desc=dns_info["desc"]
        )
        vpc_page.assert_popup_success()

    yield dns_info

    with allure_step_log(f"Teardown: 删除内网解析 {dns_info['domain']}"):
        try:
            vpc_page.internal_dns_search(dns_info["domain"])
            domains = vpc_page.get_column_data("域名")
            if dns_info["domain"] in domains:
                vpc_page.internal_dns_delete(dns_info["domain"])
                vpc_page.assert_deleted(dns_info["domain"])
        except Exception as exc:
            logger.warning(f"清理内网解析失败: {exc}")


@pytest.fixture(scope="function")
def internal_dns_record(vpc_page, internal_dns):
    """创建并返回一个解析记录，测试结束后自动清理。"""
    record_info = {
        "domain": internal_dns["domain"],
        "host_record": f"www-{random_data(length=4)}",
        "record_type": "A",
        "ttl": 600,
        "value": f"10.10.{random.randint(10, 200)}.{random.randint(10, 200)}",
        "desc": f"解析记录自动化测试-{random_data(length=4)}",
    }
    record_info["alias"] = vpc_page.internal_dns_record_alias(record_info["domain"], record_info["host_record"])

    with allure_step_log(f"Setup: 创建解析记录 {record_info['alias']}"):
        vpc_page.internal_dns_record_create(
            domain=record_info["domain"],
            host_record=record_info["host_record"],
            record_type=record_info["record_type"],
            ttl=record_info["ttl"],
            values=record_info["value"],
            desc=record_info["desc"]
        )
        vpc_page.assert_popup_success()

    yield record_info

    with allure_step_log(f"Teardown: 删除解析记录 {record_info['alias']}"):
        try:
            vpc_page.goto_internal_dns_detail(record_info["domain"], tab_name="解析记录")
            aliases = vpc_page.get_column_data("域名", context="active-tab")
            if record_info["alias"] in aliases:
                vpc_page.internal_dns_record_delete(record_info["domain"], record_info["alias"])
                vpc_page.assert_deleted(record_info["alias"])
        except Exception as exc:
            logger.warning(f"清理解析记录失败: {exc}")

@pytest.fixture(scope="class")
def lb_pool_candidate_vms(browser_context, config, request):
    """创建资源池候选虚机列表，供监听器资源池新增资源用例复用。

    本 fixture 通过复用 vm fixture 的辅助函数实现批量创建，遵循最小可复用原则：
    - 使用 `_build_vm_create_request` 构建标准 ECS 创建请求
    - 使用 `_create_vm_resources` 执行批量创建
    - 使用 `_collect_vm_fixture_metadata` 收集元数据
    - 使用 `_cleanup_vm_resources` 执行清理

    Args:
        browser_context: Playwright 浏览器上下文，由 pytest fixture 提供。
        config: 测试配置对象，由 pytest fixture 提供。
        request: pytest 请求对象，用于获取参数化配置和其他 fixture。

    request.param 支持的参数：
        count (int): 需创建的虚机数量，默认为 2。
        cluster (str): 目标集群名称，默认为 "Autotest"。
        name_prefix (str): 虚机名称前缀，默认为 "lb-pool-vm"。

    Yields:
        list[dict]: 已创建虚机的最小元数据列表，每个元素包含：
            - name (str): 虚机名称，格式为 "{prefix}-{random}-{index}"
            - ip (str): 虚机固定 IP 地址

    Note:
        - 虚机命名采用批量创建风格（带数字后缀），而非独立随机名
        - 自动使用 vpc fixture 提供的网络和子网
        - 不绑定 MFIP（bind_mfip=False），适用于内网场景
        - scope 为 class 级别，在整个测试类内共享复用

    Example:
        @pytest.mark.parametrize(
            "lb_pool_candidate_vms",
            [{"count": 3, "cluster": "Production", "name_prefix": "test-vm"}],
            indirect=True,
        )
        def test_example(lb_pool_candidate_vms):
            # lb_pool_candidate_vms 返回 3 台虚机的元数据列表
            for vm in lb_pool_candidate_vms:
                print(f"VM: {vm['name']}, IP: {vm['ip']}")
    """

    params = getattr(request, "param", {})
    count = params.get("count", 2)
    cluster = params.get("cluster", "Autotest")
    vm_prefix = params.get("name_prefix", "lb-pool-vm")
    base_name = f"{vm_prefix}-{random_data(length=4)}"

    vm_params = {"basic": {"count": count, "cluster": cluster}, "bind_mfip": False}

    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)

    create_request, actual_count, network, subnet = _build_vm_create_request(request, vm_params, base_name)
    vm_names = _build_vm_fixture_names(create_request["basic"]["name"], actual_count)

    with allure_step_log(f"Setup: 创建 {count} 台资源池候选虚机"):
        _create_vm_resources(ecs_page, create_request, vm_names)

    metadata_list = _collect_vm_fixture_metadata(ecs_page, vm_names, network, subnet)
    created_vms = [{"name": m["name"], "ip": m["ip"]} for m in metadata_list]

    yield created_vms

    _cleanup_vm_resources(ecs_page, vm_names)
    page.close()


@pytest.fixture(scope="function")
def kms_page(page):
    """创建机密互联-密钥管理页面对象并检查授权状态。

    Args:
        page: Playwright 页面对象，由 pytest fixture 提供。

    Returns:
        SciKmsPage: 密钥管理页面对象实例。
    """
    kms = SciKmsPage(page)
    kms.goto_service("可信密码模块")

    try:
        text_locator = kms.get_by_text("您已成功授权")
        expect(text_locator).to_be_visible(timeout=10000)
        kms.logger.info("可信密码模块已授权")
    except Exception:
        kms.logger.warning("可信密码模块未授权或授权信息未显示")

    kms.wait_for_page_ready()
    return kms
