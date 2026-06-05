import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('USM实例-修改名称验证')
class TestUsmRename:

    @allure.title("USM-实例-修改名称验证")
    def test_usm_rename(self, usm_instance, usm_page):
        """验证 USM 实例修改名称功能：
        修改名称后列表页和详情页均展示新名称。"""
        name = usm_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-usm-")
        logger.info(f"准备将 USM 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            usm_page.usm_rename(name, new_name)
            usm_page.assert_popup_success("执行成功")
            usm_instance["name"] = new_name  # 更新供后续验证及 teardown 使用
            logger.info(f"USM 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            usm_page.usm_verify_detail_name(new_name)
            logger.info("详情页验证通过: 名称与修改后一致")
