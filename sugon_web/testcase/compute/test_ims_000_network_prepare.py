import json

import allure

from sugon_web.testcase.compute._ims_network_helpers import prepare_ims_network
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算服务")
@allure.feature("镜像服务 IMS")
@allure.story("IMS 镜像服务网络前置准备")
class TestIMSNetworkPrepare:

    @allure.title("镜像服务IMS-网络前置准备")
    def test_ims_network_prepare(self, page):
        """确保镜像服务创建 ECS 前需要的 VPC、ACL 和安全组已准备完成。"""
        with allure_step_log("步骤1: 准备IMS专用VPC/ACL/安全组"):
            network_env = prepare_ims_network(page)
            logger.info(f"IMS网络前置准备完成: {network_env}")
            allure.attach(
                json.dumps(network_env, ensure_ascii=False, indent=2),
                "IMS网络前置结果",
                allure.attachment_type.JSON,
            )
