import pytest
import ipaddress
import random
import time
from sugon_web.common.playwright import expect
from sugon_web.pages.sg import SgPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data
from sugon_web.pages.acl import AclPage


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

    logger.info(f"清理虚拟IP {vip_address}")
    vpc_page.vip_delete(vip_address)

@pytest.fixture(scope="class")
def sg_page(page):
    """初始化虚拟私有云页面对象"""
    vpc_page = SgPage(page)
    vpc_page.goto_service('安全组')
    return vpc_page

@pytest.fixture(scope="class")
def sg(sg_page):
    """
    创建并返回一个安全组名称，测试结束后自动清理

    Yields:
        str: 安全组名称，测试用例执行后自动清理
    """
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


@pytest.fixture(scope="class")
def sg_vm_setup(ecs_page, sg_page, ecs_create_page, vpc, request):
    """
    通用前置准备：分配公网IP、创建安全组、创建虚机并绑定IP
    支持参数化配置，可通过pytest.mark.parametrize传入参数：
    - vm_count: 创建虚机数量，默认为2
    - sg_count: 创建安全组数量，默认为2
    - fip_count: 分配并绑定公网IP的数量，默认为1
    """
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
        timestamp_suffix = str(int(time.time()))[-2:]
        for i in range(sg_count):
            sg_name = f"autotest-sg{i+1}-{timestamp_suffix}"
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
def acl(page):
    """
    创建并返回一个网络ACL名称，测试结束后自动清理
    该fixture使用function scope的page会引发ScopeMismatch异常，
    如果您的项目中 sg_page 是 function scope，而 sg(sg_page) 声明了 class scope，说明项目做了特定处理。
    为安全起见，这里提供标准实现。
    """
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
