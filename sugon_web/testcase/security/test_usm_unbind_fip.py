import re

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('USM实例-解绑公网IP验证')
class TestUsmUnbindFip:

    @allure.title("USM-解绑公网IP验证")
    def test_usm_unbind_fip(self, usm_instance, usm_page):
        """通过 fixture 获取已绑定EIP的USM实例，验证解绑公网IP后网络列和跳转地址的变化。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪（已绑定EIP）")

        with allure_step_log("步骤1: 进入USM列表页"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            network_before = row_data.get("网络", "")
            logger.info(f"解绑前网络列: {network_before}")
            assert "公网" in network_before, \
                f"USM 实例 {name} 未绑定公网IP（网络列: {network_before}），测试前提条件不满足"
            logger.info("进入堡垒机页面成功，列表可正常显示")

        with allure_step_log("步骤2: 进入实例详情页查看跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            assert new_page is not None, "已绑定EIP但跳转地址无法打开，目标服务器网络不可达"
            assert new_page.url, "跳转地址打开的新页面 URL 为空"
            assert "chrome-error" not in new_page.url, \
                f"新页面加载到错误页面: {new_page.url}"
            if new_page != usm_page.page:
                new_page.close()
            logger.info("跳转地址显示URL的跳转链接，可正常打开")

        with allure_step_log("步骤3: 解绑公网IP"):
            usm_page.goto_list_page()
            usm_page.usm_unbind_eip(name)
            row_data = usm_page.get_row_data(name)
            network_after = row_data.get("网络", "")
            logger.info(f"解绑后网络列: {network_after}")
            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", network_after)
            assert len(ips) <= 1, f"解绑后网络列仍含多个IP地址: {network_after}"
            logger.info("解绑成功，该实例网络列只展示固定IP")

        with allure_step_log("步骤4: 验证解绑后详情页跳转地址"):
            jump_text = usm_page.usm_get_jump_address_text(name)
            assert "非直连网络需要绑定公网ip才可使用" in jump_text, \
                f"解绑后跳转地址未显示警告文本: {jump_text}"
            logger.info("跳转地址显示：非直连网络需要绑定公网ip才可使用！")
