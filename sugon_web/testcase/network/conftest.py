import pytest
import ipaddress
import random
import time
from sugon_web.common.playwright import expect
from sugon_web.pages.network import SgPage, VpcPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.ecs_create import EcsCreatePage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data
from sugon_web.pages.network import AclPage, SlbPage, IpGroupPage
from sugon_web.conftest import _create_logged_in_page


@pytest.fixture(scope="function")
def vpc_page(page):
    """初始化虚拟私有云页面对象"""
    vpc_page = VpcPage(page)
    vpc_page.goto_service('虚拟私有云')
    return vpc_page


def _build_vpc_create_kwargs(params=None):
    """根据参数构建VPC创建入参。"""
    params = params or {}
    name = params.get('name', random_data(length=3))

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
        "enable_ipv6": params.get('enable_ipv6', False)
    }


def _create_vpc_resource(vpc_page, params=None):
    """创建VPC并返回资源信息。"""
    create_kwargs = _build_vpc_create_kwargs(params)

    vpc_page.goto_service('虚拟私有云')
    vpc_page.vpc_create(**create_kwargs)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    vpc_page.assert_status(create_kwargs["name"])

    return create_kwargs


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


def _cleanup_vpc_resource(vpc_page, name):
    """清理VPC资源。"""
    vpc_page.goto_service('虚拟私有云')
    vpc_page.vpc_delete(name)
    vpc_page.assert_deleted(name)
    expect(vpc_page.alert).to_have_count(0, timeout=10000)


@pytest.fixture(scope="class")
def vpc(browser_context, config, request):
    """创建并返回一个VPC资源数据，测试结束后自动清理。"""
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    vpc_page.goto_service('虚拟私有云')

    params = getattr(request, 'param', {})
    count = params.get("count", 1)
    params_list = _build_vpc_batch_params(params, count)

    with allure_step_log(f"创建 {count} 个虚拟私有云"):
        vpc_list = [_create_vpc_resource(vpc_page, item_params) for item_params in params_list]

    yield vpc_list[0] if count == 1 else vpc_list

    with allure_step_log(f"清理虚拟私有云 {[item['name'] for item in vpc_list]}"):
        for item in vpc_list:
            _cleanup_vpc_resource(vpc_page, item["name"])
    page.close()


@pytest.fixture(scope="function")
def eip(vpc_page, request):
    """创建并返回弹性公网IP，测试结束后自动清理"""
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
                vpc_page.search(current_ip)
                if vpc_page.get_eip_list():
                    vpc_page.eip_release(current_ip)
                    vpc_page.assert_deleted(current_ip)
                vpc_page.btn_reset.click()
                vpc_page.wait_for_page_ready()
        except Exception as e:
            logger.warning(f"清理弹性公网IP时出错: {e}")


@pytest.fixture(scope="function")
def vip(vpc_page, vpc):
    """创建一个手动分配的虚拟IP"""
    vpc_name = vpc['name']
    subnet_name = vpc['subnet_name']
    cidr = vpc['cidr']

    # 计算可用IP，避开网关（通常是第一个IP）
    network = ipaddress.ip_network(cidr, strict=False)
    hosts = list(network.hosts())
    # 随机选择一个IP，跳过前10个IP以防冲突
    vip_address = str(random.choice(hosts[10:])) if len(hosts) > 20 else str(random.choice(hosts[2:]))

    logger.info(f"准备创建虚拟IP {vip_address}")
    vpc_page.goto_service("虚拟私有云")
    vpc_page.vip_create(vpc_name=vpc_name, subnet_name=subnet_name, ip_address=vip_address)
    vpc_page.assert_popup_success("申请虚拟IP端口成功")

    yield vip_address

    # 确保在正确的 tab 页
    vpc_page.goto_service("虚拟私有云")
    vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
    vpc_page.wait_for_page_ready()
    vpc_page.get_by_role("tab", name="虚拟IP管理").click()
    vpc_page.wait_for_page_ready()

    logger.info(f"清理虚拟IP {vip_address}")
    vpc_page.vip_delete(vip_address)


@pytest.fixture(scope="function")
def port(vpc_page, vpc, request):
    """
    创建并返回指定数量的端口，测试结束后自动清理

    Args:
        vpc_page: VPC页面对象
        vpc: VPC fixture
        request: pytest request对象

    Returns:
        list: 端口IP列表
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
            vpc_page.goto_service("虚拟私有云")

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
                vpc_page.goto_service("虚拟私有云")
                vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
                vpc_page.wait_for_page_ready()

                vpc_page.get_by_role("tab", name="端口").click()
                vpc_page.wait_for_page_ready()

                # 批量删除端口
                vpc_page.port_delete(created_ports)
                vpc_page.assert_deleted(created_ports)
                logger.info("端口清理完成")
            except Exception as e:
                logger.warning(f"清理端口时出错: {e}")


@pytest.fixture(scope="function")
def nat(vpc_page, vpc, request):
    """创建一个NAT网关，测试结束后自动删除

    Args:
        vpc_page: VPC页面对象
        vpc: VPC fixture，提供 vpc_name
        request: pytest request对象，可通过 indirect 传入 eip 等参数

    Returns:
        dict: 包含 nat_name、vpc_name 的字典
    """
    from sugon_web.utils.util import random_data

    params = getattr(request, 'param', {})
    eip = params.get('eip', None)
    public_ip_pool = params.get('public_ip_pool', 'public_net(基础版)')
    desc = params.get('desc', 'NAT网关fixture自动创建')

    vpc_name = vpc['name']
    nat_name = random_data()

    with allure_step_log(f"Setup: 创建NAT网关 {nat_name}"):
        vpc_page.goto_service("NAT网关")
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
            vpc_page.goto_service("NAT网关")
            vpc_page.nat_delete(current_name)
            logger.info(f"NAT网关 {current_name} 删除成功")
        except Exception as e:
            logger.warning(f"清理NAT网关时出错: {e}")

@pytest.fixture(scope="function")
def sg_page(page):
    """初始化虚拟私有云页面对象"""
    vpc_page = SgPage(page)
    vpc_page.goto_service('安全组')
    return vpc_page


@pytest.fixture(scope="function")
def qos_page(page):
    """初始化网络QoS页面对象"""
    vpc_page = VpcPage(page)
    vpc_page.goto_service("网络QoS")
    return vpc_page


@pytest.fixture(scope="function")
def qos(qos_page):
    """创建并返回一个网络QoS，测试结束后自动清理"""
    qos_info = {
        "name": f"qos-{random_data()}",
        "send_rate": 10,
        "recv_rate": 20,
        "desc": "网络QoS fixture 自动创建",
    }

    with allure_step_log("Setup: 创建网络QoS"):
        qos_page.qos_create(
            name=qos_info["name"],
            send_rate=qos_info["send_rate"],
            recv_rate=qos_info["recv_rate"],
            desc=qos_info["desc"]
        )
        qos_page.assert_popup_success()

    yield qos_info

    with allure_step_log(f"Teardown: 删除网络QoS {qos_info['name']}"):
        try:
            qos_page.goto_service("网络QoS")
            qos_page.qos_delete(qos_info["name"])
            qos_page.assert_deleted(qos_info["name"])
        except Exception as e:
            logger.warning(f"清理网络QoS时出错: {e}")

@pytest.fixture(scope="class")
def sg(browser_context, config):
    """
    创建并返回一个安全组名称，测试结束后自动清理

    Yields:
        str: 安全组名称，测试用例执行后自动清理
    """
    page = _create_logged_in_page(browser_context, config)
    sg_page = SgPage(page)
    sg_page.goto_service('安全组')
    sg_name = random_data()

    # 创建安全组
    with allure_step_log("创建安全组"):
        sg_page.goto_service("安全组")
        sg_page.sg_create(sg_name, desc=f"{sg_name}自动创建的安全组")

    yield sg_name

    # 测试结束后清理
    with allure_step_log("清理安全组"):
        sg_page.goto_service("安全组")
        sg_page.sg_delete(sg_name)
        sg_page.assert_deleted(sg_name)
    page.close()


@pytest.fixture(scope="class")
def sg_vm_setup(browser_context, config, vpc, request):
    """
    通用前置准备：分配公网IP、创建安全组、创建虚机并绑定IP
    支持参数化配置，可通过pytest.mark.parametrize传入参数：
    - vm_count: 创建虚机数量，默认为2
    - sg_count: 创建安全组数量，默认为2
    - fip_count: 分配并绑定公网IP的数量，默认为1
    """
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    sg_page = SgPage(page)
    ecs_create_page = EcsCreatePage(page)

    params = getattr(request, 'param', {})
    vm_count = params.get('vm_count', 2)
    sg_count = params.get('sg_count', 2)
    fip_count = params.get('fip_count', 1)

    network_name = vpc.get("name")
    subnet_name = vpc.get("subnet_name")

    # 分配公网IP
    if fip_count > 0:
        with allure_step_log(f"Fixture: 分配 {fip_count} 个公网IP"):
            ecs_page.assign_ip(count=str(fip_count))

    # 平台创建安全组
    sgs = []
    with allure_step_log(f"Fixture: 平台创建 {sg_count} 个安全组"):
        sg_page.goto_service("安全组")
        timestamp_suffix = time.strftime("%M%S")
        for i in range(sg_count):
            sg_name = f"autotest-sg{i + 1}-{timestamp_suffix}"
            sg_page.sg_create(sg_name, desc=f"{sg_name}自动化测试")
            expect(sg_page.popup).to_have_count(0)
            sgs.append(sg_name)

    # 在同一子网下创建虚机并将它们分发到安全组中
    vms = []
    vm_names = []
    sg_strategy = params.get('sg_strategy', 'unique')  # 默认 'unique'

    with allure_step_log(f"Fixture: 在vpc同一子网下创建 {vm_count} 个虚机 (策略: {sg_strategy})"):
        ecs_create_page.goto_service("弹性云服务器")
        for i in range(vm_count):
            # 根据策略分配安全组
            if sg_strategy == 'shared':
                # 所有虚机绑定第一个安全组
                current_sg = sgs[0]
            else:
                # 默认 'unique': 每个虚机循环分配安全组
                current_sg = sgs[i % len(sgs)]

            network_vm = {"networks": [{"network": network_name, "subnet": subnet_name}], "安全组": [current_sg]}
            vm_info = ecs_create_page.ecs_create(basic={}, storage={}, network=network_vm, manage={}, advanced={})
            vm_names.append(vm_info.get("name"))

        for vm_name in vm_names:
            ecs_create_page.assert_status(vm_name)

            # 获取虚机元数据
            row_data = ecs_create_page.get_row_data(vm_name)
            ip_list = row_data["IP地址"].split("固定: ")
            vm_metadata = {
                "name": vm_name,
                "id": row_data["名称/ID"].split(":")[1].strip(),
                "ip": ip_list[-1].strip(),
                "row_data": row_data
            }
            vms.append(vm_metadata)

    yield {
        "vms": vms,
        "sgs": sgs,
    }

    # 清理释放资源
    with allure_step_log("Fixture: 清理测试资源"):
        ecs_create_page.goto_service("弹性云服务器")
        ecs_create_page.ecs_remove(vm_names)
        # ecs_delete 时选择释放 IP
        ecs_create_page.ecs_delete(vm_names, release_ip=True)
        ecs_create_page.assert_deleted(vm_names)

        sg_page.goto_service("安全组")
        sg_page.sg_delete(sgs)
        sg_page.assert_deleted(sgs)
        page.close()
#
#
# @pytest.fixture(autouse=True)
# def sg_rule_cleanup(sg_page, request):
#     """
#     自动使用的 fixture，恢复安全组默认规则。
#
#     """
#     yield
#
#     if 'sg_vm_setup' in request.fixturenames:
#         # 只有当测试用例使用了 sg_vm_setup 这个 class 作用域的 fixture 时才执行
#         try:
#             sg_vm_setup_data = request.getfixturevalue('sg_vm_setup')
#             sgs = sg_vm_setup_data.get("sgs", [])
#             with allure_step_log(f"Fixture Cleanup: 还原安全组 {sgs} 的规则为默认"):
#                 for sg_name in sgs:
#                     # 调用新增加的恢复默认规则方法
#                     sg_page.sg_rule_restore_defaults(sg_name)
#         except Exception as e:
#             logger.error(f"Cleanup fixture failed: {e}")

@pytest.fixture(scope="function")
def acl_page(page):
    """返回网络AclPage实例"""
    vpc_page = AclPage(page)
    vpc_page.goto_service('网络ACL')
    return vpc_page

@pytest.fixture(scope="class")
def acl(browser_context, config):
    """
    创建并返回一个网络ACL名称，测试结束后自动清理
    该fixture使用function scope的page会引发ScopeMismatch异常，
    如果您的项目中 sg_page 是 function scope，而 sg(sg_page) 声明了 class scope，说明项目做了特定处理。
    为安全起见，这里提供标准实现。
    """
    page = _create_logged_in_page(browser_context, config)
    acl_page = AclPage(page)
    acl_name = f"acl-{random_data()}"

    # 创建网络ACL
    with allure_step_log(f"fixture前置: 创建网络ACL{acl_name}"):
        acl_page.goto_service("网络ACL")
        acl_page.acl_create(acl_name, desc=f"{acl_name} 自动化测试创建")

    yield acl_name

    # 测试结束后清理
    with allure_step_log(f"fixture后置: 清理网络ACL{acl_name}"):
        acl_page.goto_service("网络ACL")
        acl_page.acl_batch_delete([acl_name])
    page.close()

def _do_setup_acl_vpc_vms(acl, sg, vpc_page, sg_page, ecs_create_page, params):
    """提取的预置环境核心逻辑，支持给不同scope的fixture复用"""
    vpc_acl_name = acl if params.get('vpc_acl', True) else None

    base_name = random_data()
    vpc_name = f"vpc-{base_name}"
    sub1_name = f"sub1-{base_name}"
    sub2_name = f"sub2-{base_name}"
    n = random.randint(1, 240)
    cidr1 = f"10.{n}.1.0/24"
    cidr2 = f"10.{n}.2.0/24"

    # 创建VPC和sub1，并关联ACL
    with allure_step_log(f"前置步骤1: 创建VPC {vpc_name} 和子网 {sub1_name} (关联ACL: {vpc_acl_name})"):
        vpc_page.goto_service("虚拟私有云")
        vpc_page.vpc_create(
            name=vpc_name,
            subnet_name=sub1_name,
            cidr=cidr1,
            network_type="Geneve",
            acl_policy=vpc_acl_name
        )
        vpc_page.assert_status(vpc_name, refresh=True)

    # 创建sub2，并关联ACL
    sub2_acl_name = acl if params.get('sub2_acl', False) else None
    with allure_step_log(f"前置步骤2: 为 {vpc_name} 创建子网 {sub2_name} (关联ACL: {sub2_acl_name})"):
        vpc_page.subnet_create(
            vpc_name=vpc_name,
            subnet_name=sub2_name,
            cidr=cidr2,
            acl_policy=sub2_acl_name
        )

    # 放开安全组入方向所有流量 (IPv4 & IPv6)
    with allure_step_log(f"前置步骤3: 在安全组 {sg} 中放开所有入方向流量"):
        rules = sg_page.sg_get_all_rules(sg_name=sg)

        has_ipv4 = any(r.get("方向", "") == "入口" and r.get("以太网类型", "") == "IPv4" for r in rules)
        has_ipv6 = any(r.get("方向", "") == "入口" and r.get("以太网类型", "") == "IPv6" for r in rules)

        if not has_ipv4:
            sg_page.sg_rule_create(sg_name=sg, direction="入口", protocol="所有", ip_version="IPv4", remote_type="CIDR", from_list=False, detail_mode=True)
        if not has_ipv6:
            sg_page.sg_rule_create(sg_name=sg, direction="入口", protocol="所有", ip_version="IPv6", remote_type="CIDR", from_list=False, detail_mode=True)

    vms_per_subnet = params.get("vms_per_subnet", 1)
    vms_list = []
    for tag, subnet in [("a", sub1_name), ("b", sub2_name)]:
        for i in range(vms_per_subnet):
            vm_tag = tag.upper() if vms_per_subnet == 1 else f"{tag.upper()}-{i}"
            with allure_step_log(f"前置步骤: 创建ECS {vm_tag} 在 {subnet} 并关联安全组 {sg}"):
                ecs_create_page.goto_service("弹性云服务器")
                vm_base = random_data()
                vm_name = f"vm{tag}{i}-{vm_base}" if vms_per_subnet > 1 else f"vm{tag}-{vm_base}"
                basic = {"name": vm_name}
                network = {"networks": [{"network": vpc_name, "subnet": subnet}], "安全组": [sg]}
                ecs_create_page.ecs_create(basic=basic, network=network)
                ecs_create_page.assert_status(vm_name)

                # 绑定MFIP
                row_data = ecs_create_page.get_row_data(vm_name)
                fixed_ip = row_data["IP地址"].split("固定: ")[-1].strip()
                mfip = ecs_create_page.bind_mfip(fixed_ip, network=vpc_name)
                from sugon_web.utils.logger import logger
                logger.info(f"VM {vm_name} 已绑定 MFIP: {mfip}")

                vms_list.append({
                    "tag": vm_tag,
                    "name": vm_name,
                    "ip": fixed_ip,
                    "mfip": mfip
                })

    env_data = {
        "vpc_name": vpc_name,
        "sub1_name": sub1_name,
        "sub2_name": sub2_name,
        "cidr1": cidr1,
        "cidr2": cidr2,
        "vms": vms_list,
        "acl_name": acl,
        "sg_name": sg
    }

    yield env_data

    # 清理
    vm_names = [vm["name"] for vm in vms_list]
    with allure_step_log(f"Fixture清理: 删除ECS实例 {vm_names}"):
        ecs_create_page.goto_service("弹性云服务器")
        ecs_create_page.ecs_remove(vm_names)
        ecs_create_page.ecs_delete(vm_names)
        ecs_create_page.assert_deleted(vm_names)

    with allure_step_log(f"Fixture清理: 删除VPC {vpc_name}"):
        vpc_page.goto_service("虚拟私有云")
        vpc_page.vpc_delete(vpc_name)
        vpc_page.assert_deleted(vpc_name)


@pytest.fixture(scope="function")
def acl_vpc_vms(acl, sg, vpc_page, sg_page, ecs_create_page, request):
    """
    环境预置 (Function 级别): 每个用例单独创建虚机和VPC
    """
    params = getattr(request, 'param', {})
    yield from _do_setup_acl_vpc_vms(acl, sg, vpc_page, sg_page, ecs_create_page, params)


@pytest.fixture(scope="class")
def acl_in_out_bound_rules(browser_context, config, acl, sg):
    """
    专门为具备复杂内外网规则场景定制的 class 级别夹具：
    固化了参数，确保该 fixture 在类中仅运行且缓存一次，不再需要用例进行 parametrize
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    sg_page = SgPage(page)
    ecs_create_page = EcsCreatePage(page)
    params = {"vpc_acl": False, "sub2_acl": True, "vms_per_subnet": 2}
    yield from _do_setup_acl_vpc_vms(acl, sg, vpc_page, sg_page, ecs_create_page, params)
    page.close()

def _do_clean_acl_inbound_rules(acl_page, acl_name):
    """执行清理ACL入方向规则的核心逻辑"""
    with allure_step_log(f"Fixture清理: acl规则 {acl_name}"):
        try:
            acl_page.goto_service("网络ACL")
            acl_page.goto_acl_detail(acl_name, tab_name="入方向规则")
            # 循环删除所有带“删除”按钮的入方向规则
            while acl_page.get_by_role("row").filter(has=acl_page.get_by_text("删除", exact=True)).count() > 0:
                acl_page.acl_rule_delete(acl_name, direction="入方向")
        except Exception as e:
            from sugon_web.utils.logger import logger
            logger.warning(f"清理ACL入方向规则失败: {e}")

@pytest.fixture(scope="function")
def clean_acl_inbound_rules(acl_page, acl_vpc_vms):
    """每条测试用例执行前/后，清理ACL的入方向规则 (Function 级别)"""
    yield
    _do_clean_acl_inbound_rules(acl_page, acl_vpc_vms["acl_name"])

@pytest.fixture(scope="class")
def clean_acl_inbound_rules_4vms(browser_context, config, acl_in_out_bound_rules):
    """跟 acl_vpc_vms_4vms 配套使用的类级别清理，测试末尾一次性执行清理 (Class 级别)"""
    yield
    page = _create_logged_in_page(browser_context, config)
    acl_page = AclPage(page)
    try:
        _do_clean_acl_inbound_rules(acl_page, acl_in_out_bound_rules["acl_name"])
    finally:
        page.close()

def _do_clean_acl_outbound_rules(acl_page, acl_name):
    """执行清理ACL出方向规则的核心逻辑"""
    with allure_step_log(f"Fixture清理: acl规则出方向 {acl_name}"):
        try:
            acl_page.goto_service("网络ACL")
            acl_page.goto_acl_detail(acl_name, tab_name="出方向规则")
            # 循环删除所有带“删除”按钮的出方向规则
            while acl_page.get_by_role("row").filter(has=acl_page.get_by_text("删除", exact=True)).count() > 0:
                acl_page.acl_rule_delete(acl_name, direction="出方向")
        except Exception as e:
            from sugon_web.utils.logger import logger
            logger.warning(f"清理ACL出方向规则失败: {e}")

@pytest.fixture(scope="class")
def clean_acl_outbound_rules(browser_context, config, acl_in_out_bound_rules):
    """跟 acl_in_out_bound_rules 配套使用的类级别清理，测试末尾一次性执行出方向清理 (Class 级别)"""
    yield
    page = _create_logged_in_page(browser_context, config)
    acl_page = AclPage(page)
    try:
        _do_clean_acl_outbound_rules(acl_page, acl_in_out_bound_rules["acl_name"])
    finally:
        page.close()

@pytest.fixture(scope="function")
def slb_page(page):
    """初始化负载均衡页面对象"""
    slb_page = SlbPage(page)
    slb_page.goto_service("负载均衡")
    return slb_page


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
    slb_page = SlbPage(page)
    slb_page.goto_service("负载均衡")
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
        slb_page.goto_service("负载均衡")
        slb_page.slb_create(
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
        slb_page.assert_status(slb_name, status="运行中")

    yield slb_name

    with allure_step_log(f"Teardown: 清理负载均衡 {slb_name}"):
        try:
            slb_page.goto_service("负载均衡")
            slb_page.slb_delete(slb_name)
            slb_page.assert_deleted(slb_name)
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
    slb_page = SlbPage(page)
    slb_page.goto_service("负载均衡")
    params = getattr(request, "param", {})

    params.setdefault("slb_name", slb)
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
        slb_page.slb_lb_create(**params)
        slb_page.assert_popup_success()
        slb_page.assert_listener_exists(lb_name)

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
            slb_page.goto_service("负载均衡")
            slb_page.goto_slb_detail(listener_info["slb_name"], "监听器")
            slb_page.assert_listener_exists(current_name)
            slb_page.slb_lb_delete(listener_info["slb_name"], current_name)
            slb_page.assert_popup_success()
        except Exception as exc:
            logger.warning(f"listener cleanup failed: {current_name}, error={exc}")
        finally:
            page.close()


@pytest.fixture(scope="class")
def lb_pool_candidate_vms(browser_context, config, vpc, request):
    """创建资源池可选 ECS 列表，供监听器资源池新增资源用例复用。"""
    page = _create_logged_in_page(browser_context, config)
    ecs_create_page = EcsCreatePage(page)

    params = getattr(request, "param", {})
    count = params.get("count", 2)
    cluster = params.get("cluster", "Autotest")
    vm_prefix = params.get("name_prefix", "lb-pool-vm")
    created_vms = []

    with allure_step_log(f"Setup: 创建 {count} 台资源池候选虚机"):
        for _ in range(count):
            vm_name = f"{vm_prefix}-{random_data(length=4)}"
            ecs_create_page.goto_service("弹性云服务器")
            ecs_create_page.ecs_create(
                basic={"name": vm_name, "集群": cluster},
                storage={},
                network={"networks": [{"network": vpc["name"], "subnet": vpc["subnet_name"]}]},
                manage={},
                advanced={}
            )
            ecs_create_page.assert_popup_success("创建实例命令下发成功")
            ecs_create_page.assert_status(vm_name)

            row_data = ecs_create_page.get_row_data(vm_name)
            fixed_ip = row_data["IP地址"].split("固定: ")[-1].strip()
            created_vms.append({
                "name": vm_name,
                "ip": fixed_ip,
            })

    yield created_vms

    vm_names = [vm["name"] for vm in created_vms]
    with allure_step_log(f"Teardown: 清理资源池候选虚机 {vm_names}"):
        try:
            if created_vms:
                ecs_create_page.goto_service("弹性云服务器")
                ecs_create_page.ecs_remove(vm_names)
                ecs_create_page.ecs_delete(vm_names)
                ecs_create_page.assert_deleted(vm_names)
        except Exception as exc:
            logger.warning(f"清理资源池候选虚机失败: {vm_names}, error={exc}")
        finally:
            page.close()


@pytest.fixture(scope="function")
def ip_group_page(page):
    """初始化 IP 地址组页面对象。"""
    page_obj = IpGroupPage(page)
    page_obj.goto_service("负载均衡")
    return page_obj


@pytest.fixture(scope="class")
def ip_group(browser_context, config, request):
    """创建 IP 地址组，并在测试结束后自动清理。"""
    page = _create_logged_in_page(browser_context, config)
    ip_group_page = IpGroupPage(page)
    ip_group_page.goto_service("负载均衡")

    params = getattr(request, "param", {})
    group_info = {
        "name": f"ipg-{random_data()}",
        "ip_addresses": ["10.10.10.10"],
        "desc": "IP地址组 fixture 自动创建",
        "enable_ipv6": False,
    }
    group_info.update(params)

    with allure_step_log(f"Setup: 创建 IP 地址组 {group_info['name']}"):
        ip_group_page.ip_group_create(
            name=group_info["name"],
            ip_addresses=group_info["ip_addresses"],
            desc=group_info["desc"],
            enable_ipv6=group_info["enable_ipv6"],
        )
        ip_group_page.assert_popup_success()

    yield group_info

    with allure_step_log(f"Teardown: 清理 IP 地址组 {group_info['name']}"):
        try:
            ip_group_page.goto_service("负载均衡")
            ip_group_page.ip_group_search(group_info["name"])
            names = ip_group_page.get_column_data("名称")
            if group_info["name"] in names:
                ip_group_page.ip_group_delete(group_info["name"])
                ip_group_page.assert_deleted(group_info["name"])
        except Exception as exc:
            logger.warning(f"清理 IP 地址组失败: {exc}")
        finally:
            page.close()
