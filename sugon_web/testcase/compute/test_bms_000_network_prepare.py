import json

import allure

from sugon_web.pages.network import VpcPage
from sugon_web.testcase.compute.test_bms_001_soft_create import _prepare_bms_instance_vpc
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS网络前置准备")
class TestBmsNetworkPrepare:

    @allure.title("裸金属BMS-网络前置准备")
    def test_bms_network_prepare(self, page):
        """确保创建 BMS 实例前需要的 VPC、ACL 和安全组已准备完成。"""
        with allure_step_log("步骤1: 准备BMS实例专用VPC/ACL/安全组"):
            vpc_page = VpcPage(page)
            network_env = _prepare_bms_instance_vpc(vpc_page)
            logger.info(f"BMS网络前置准备完成: {network_env}")
            allure.attach(
                json.dumps(network_env, ensure_ascii=False, indent=2),
                "BMS网络前置结果",
                allure.attachment_type.JSON,
            )
