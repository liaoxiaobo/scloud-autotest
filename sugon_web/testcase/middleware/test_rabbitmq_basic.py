import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('数据库服务')
@allure.feature('分布式消息服务 RabbitMQ')
class TestRabbitMQBasic:

    @allure.title("RabbitMQ-修改实例名称")
    def test_rename_instance(self, rabbitmq_page, rabbitmq):
        instance_name = rabbitmq["name"]
        renamed_name = f"rabbitmq-renamed-{random_data()}"

        with allure_step_log("步骤一：修改实例名称"):
            rabbitmq_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证修改实例名称结果"):
            rabbitmq_page.assert_popup_success("修改实例名称成功")
            rabbitmq_page.assert_list_contain(renamed_name)
            rabbitmq_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：修改实例名称回退"):
            rabbitmq_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证回退结果"):
            rabbitmq_page.assert_popup_success("修改实例名称成功")
            rabbitmq_page.assert_list_contain(instance_name)
            rabbitmq_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("RabbitMQ-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, rabbitmq_page, rabbitmq, ssh_host):
        instance_name = rabbitmq["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：实例绑定公网IP"):
            ip = rabbitmq_page.instance_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            rabbitmq_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：实例解绑公网IP"):
            rabbitmq_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            rabbitmq_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("RabbitMQ-白名单管理")
    def test_whitelist_management(self, rabbitmq_page, rabbitmq):
        instance_name = rabbitmq["name"]
        whitelist_ips = [
            "10.0.21.0/24",
            "10.0.22.0/24",
            "10.0.23.0/24",
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            rabbitmq_page.reset_whitelist(instance_name)
            rabbitmq_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            rabbitmq_page.add_whitelist(instance_name, ip_single)
            rabbitmq_page.assert_popup_success("添加白名单成功")
            rabbitmq_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            rabbitmq_page.delete_whitelist(instance_name, ip_single)
            rabbitmq_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                rabbitmq_page.add_whitelist(instance_name, ip)
                rabbitmq_page.assert_popup_success("添加白名单成功")
                rabbitmq_page.assert_list_contain(ip, "白名单", exact_match=False)

            rabbitmq_page.batch_delete_whitelist(instance_name, ip_batch)
            rabbitmq_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            rabbitmq_page.add_whitelist(instance_name, ip_single)
            rabbitmq_page.assert_popup_success("添加白名单成功")
            rabbitmq_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            rabbitmq_page.reset_whitelist(instance_name)
            rabbitmq_page.assert_popup_success("重置白名单成功")

    @allure.title("RabbitMQ-实例搜索")
    def test_search_instance(self, rabbitmq_page, rabbitmq):
        instance_name = rabbitmq["name"]
        keyword = instance_name[:-2]

        with allure_step_log(f"步骤一：搜索实例关键词 {keyword}"):
            rabbitmq_page.goto_submenu("实例管理")
            rabbitmq_page.search(keyword)

        with allure_step_log("步骤二：验证搜索结果"):
            rabbitmq_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            rabbitmq_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            assert rabbitmq_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
