import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('数据库服务')
@allure.feature('监控服务 Prometheus')
class TestPrometheusBasic:

    @allure.title("Prometheus-修改实例名称")
    def test_rename_instance(self, prometheus_page, prometheus):
        instance_name = prometheus["name"]
        renamed_name = f"prometheus-renamed-{random_data()}"

        with allure_step_log("步骤一：修改实例名称"):
            prometheus_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证修改实例名称结果"):
            prometheus_page.assert_popup_success("修改实例名称成功")
            prometheus_page.assert_list_contain(renamed_name)
            prometheus_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：修改实例名称回退"):
            prometheus_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证回退结果"):
            prometheus_page.assert_popup_success("修改实例名称成功")
            prometheus_page.assert_list_contain(instance_name)
            prometheus_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("Prometheus-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, prometheus_page, prometheus, ssh_host):
        instance_name = prometheus["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：实例绑定公网IP"):
            ip = prometheus_page.instance_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            prometheus_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：实例解绑公网IP"):
            prometheus_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            prometheus_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("Prometheus-实例搜索")
    def test_search_instance(self, prometheus_page, prometheus):
        instance_name = prometheus["name"]
        keyword = instance_name[:-2]

        with allure_step_log(f"步骤一：搜索实例关键词 {keyword}"):
            prometheus_page.goto_submenu("集群管理")
            prometheus_page.search(keyword)

        with allure_step_log("步骤二：验证搜索结果"):
            prometheus_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            prometheus_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            assert prometheus_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
