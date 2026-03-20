import pytest
import ipaddress
import random
from sugon_web.utils.logger import logger, allure_step_log

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
