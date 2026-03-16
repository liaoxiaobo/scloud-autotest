import pytest
import ipaddress
import random
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data

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
        sg_page.assert_popup_success("新建安全组成功")

    yield sg_name

    # 测试结束后清理
    with allure_step_log("清理安全组"):
        sg_page.goto_service("安全组")
        sg_page.sg_delete(sg_name)
        sg_page.assert_deleted(sg_name)