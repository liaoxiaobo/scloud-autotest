import pytest
import allure
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic('网络服务')
@allure.feature('云防火墙')
@allure.story('基本功能验证')
class TestCFWBasic:

    @allure.title("云防火墙-创建成功并处于运行中")
    def test_cfw_create(self, cfw_page, ssh_host):
        """测试创建云防火墙，并断言列表状态为运行中，最后清理资源并验证后端删除。"""
        cfw_name = random_data()

        try:
            with allure_step_log("步骤1: 创建云防火墙"):
                cfw_page.cfw_create(
                    name=cfw_name,
                    version="山石引擎-5.5",
                    cluster="Autotest",
                )

            with allure_step_log("步骤2: 验证云防火墙状态为运行中"):
                cfw_page.assert_status(cfw_name, status="运行中", timeout=1200)
        finally:
            with allure_step_log("步骤3: 删除云防火墙"):
                cfw_page.cfw_delete(cfw_name)

            with allure_step_log("步骤4: 验证列表页数据不可见"):
                cfw_page.assert_deleted(cfw_name, timeout=300, refresh=True)

            with allure_step_log("步骤5: 验证底层虚拟机已删除"):
                ssh_host.wait_vm_deleted(cfw_name, timeout=300, interval=5)

    @allure.title("云防火墙-策略创建")
    def test_cfw_strategy_create(self, cfw_page, cfw):
        """测试在指定云防火墙实例下创建策略"""
        cfw_name = cfw['name']
        strategy_name = random_data()

        with allure_step_log("步骤1: 在指定实例下创建策略"):
            cfw_page.cfw_strategy_create(
                cfw_name=cfw_name,
                strategy_name=strategy_name,
                security_domain="mgt",
                target="游戏平台",
            )

        with allure_step_log("步骤2: 验证策略出现在列表中"):
            cfw_page.assert_popup_success()
            cfw_page.assert_list_contain(strategy_name)

    @allure.title("云防火墙-搜索和重置")
    def test_cfw_search_reset(self, cfw_page, cfw):
        """测试云防火墙搜索和重置功能（依赖 cfw fixture）"""
        cfw_name = cfw['name']

        with allure_step_log("步骤1: 输入名称关键字进行搜索"):
            keyword = cfw_name[:-2]
            cfw_page.search(keyword)

        with allure_step_log("步骤2: 验证搜索结果正确"):
            cfw_page.assert_list_contain(cfw_name)

        with allure_step_log("步骤3: 重置搜索条件"):
            cfw_page.btn_reset.click()
            assert cfw_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 验证重置后列表恢复，目标云防火墙仍存在"):
            cfw_page.assert_list_contain(cfw_name)
