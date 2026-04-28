import allure

from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string


@allure.epic('数据库服务')
@allure.feature('分布式消息服务 Kafka')
class TestKafkaBasic:

    @allure.title("Kafka-重命名实例")
    def test_rename_instance(self, kafka_page, kafka):
        instance_name = kafka["name"]
        renamed_name = f"kafka-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            kafka_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证重命名结果"):
            kafka_page.assert_popup_success()
            kafka_page.assert_list_contain(renamed_name)
            kafka_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：重命名实例回退"):
            kafka_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证回退结果"):
            kafka_page.assert_popup_success()
            kafka_page.assert_list_contain(instance_name)
            kafka_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("Kafka-重启实例")
    def test_restart_instance(self, kafka_page, kafka):
        instance_name = kafka["name"]

        with allure_step_log("步骤一：重启实例"):
            kafka_page.restart_instance(instance_name)

        with allure_step_log("步骤二：验证重启结果"):
            kafka_page.assert_popup_success()
            kafka_page.assert_status(instance_name, status="重启中", timeout=600, refresh=True)
            kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

    @allure.title("Kafka-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：绑定公网IP"):
            ip = kafka_page.instance_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            kafka_page.assert_popup_success()
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            kafka_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            kafka_page.assert_popup_success()
            ssh_host.ping(ip, connected=False)

    @allure.title("Kafka-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：节点绑定公网IP"):
            ip = kafka_page.node_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            kafka_page.assert_popup_success()
            ssh_host.ping(ip)

        with allure_step_log("步骤三：节点解绑公网IP"):
            kafka_page.node_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            kafka_page.assert_popup_success()
            ssh_host.ping(ip, connected=False)

    @allure.title("Kafka-修改实例规格")
    def test_change_specification(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        node_name = f"{instance_name}-0"
        specification_name = "应用中间件标准型 kafka.d6.xlarge 4核 8GiB"
        real_specification = "kafka.d6.xlarge"

        with allure_step_log("步骤一：修改规格"):
            kafka_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格修改结果"):
            kafka_page.assert_popup_success()
            kafka_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            kafka_page.assert_status(node_name, status="运行中", timeout=3000, refresh=True)
            assert db_util.get_specification(kafka_page, node_name, ssh_host) == real_specification

    @allure.title("Kafka-节点热迁移")
    def test_kafka_node_hot_migration(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        node_name = f"{instance_name}-0"

        old_host = db_util.get_backend_host(kafka_page, ssh_host, node_name)
        allure.attach(f"迁移前物理机: {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = kafka_page.kafka_hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果"):
            kafka_page.assert_popup_success()
            kafka_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            kafka_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：后端验证物理机变更"):
            new_host = db_util.get_backend_host(kafka_page, ssh_host, node_name)
            allure.attach(f"迁移后物理机: {new_host}", name="迁移后状态")
            assert new_host != old_host, f"热迁移失败，迁移前后物理机未变化: {old_host}"
            if selected_host:
                assert selected_host in new_host, f"热迁移失败，期望 {selected_host}，实际 {new_host}"

    @allure.title("Kafka-修改云硬盘大小")
    def test_change_disk_size(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        node_name = f"{instance_name}-0"
        current_size = db_util.get_disk_size(kafka_page, node_name, ssh_host)
        new_size = current_size + 1

        with allure_step_log("步骤一：修改云硬盘大小"):
            kafka_page.change_disk_size(instance_name, node_name, new_size)

        with allure_step_log("步骤二：验证磁盘大小修改结果"):
            kafka_page.assert_popup_success("扩容硬盘中，请耐心等待")
            kafka_page.assert_status(node_name, status="调整云硬盘中", timeout=1200, refresh=True)
            kafka_page.assert_status(node_name, status="运行中", timeout=3000, refresh=True)
            assert db_util.get_disk_size(kafka_page, node_name, ssh_host) == new_size

    @allure.title("Kafka-重启节点")
    def test_restart_node(self, kafka_page, kafka):
        instance_name = kafka["name"]
        node_name = f"{instance_name}-0"

        with allure_step_log("步骤一：重启节点"):
            kafka_page.restart_node(instance_name, node_name)
            kafka_page.assert_popup_success("重启节点服务成功")

        with allure_step_log("步骤二：验证节点重启结果"):
            kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

    @allure.title("Kafka-参数编辑")
    def test_edit_instance_parameter(self, kafka_page, kafka):
        instance_name = kafka["name"]
        param_name = "num.network.threads"
        param_value = "4"

        with allure_step_log(f"步骤一：编辑参数 {param_name} 为 {param_value}"):
            kafka_page.edit_instance_parameter(instance_name, param_name, param_value)

        with allure_step_log("步骤二：验证参数编辑结果"):
            kafka_page.assert_popup_success("执行成功")

    @allure.title("Kafka-新增节点")
    def test_add_node(self, kafka_page, kafka, ssh_host):
        instance_name = kafka["name"]
        new_node_name = f"{instance_name}-3"

        with allure_step_log("步骤一：新增节点"):
            kafka_page.add_node(instance_name)
            kafka_page.assert_popup_success("执行成功")

        with allure_step_log("步骤二：验证新增节点状态"):
            kafka_page.assert_status(new_node_name, status="创建中", timeout=600, refresh=True)
            kafka_page.assert_status(new_node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证新增节点已创建"):
            db_util.assert_backend_created(kafka_page, ssh_host, new_node_name)

    @allure.title("Kafka-白名单管理")
    def test_whitelist_management(self, kafka_page, kafka):
        instance_name = kafka["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24",
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            kafka_page.reset_whitelist(instance_name)
            kafka_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            kafka_page.add_whitelist(instance_name, ip_single)
            kafka_page.assert_popup_success("添加白名单成功")
            kafka_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            kafka_page.delete_whitelist(instance_name, ip_single)
            kafka_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                kafka_page.add_whitelist(instance_name, ip)
                kafka_page.assert_popup_success("添加白名单成功")
            for ip in ip_batch:
                kafka_page.assert_list_contain(ip, "白名单", exact_match=False)

            kafka_page.batch_delete_whitelist(instance_name, ip_batch)
            kafka_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            kafka_page.add_whitelist(instance_name, ip_single)
            kafka_page.assert_popup_success("添加白名单成功")
            kafka_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            kafka_page.reset_whitelist(instance_name)
            kafka_page.assert_popup_success("重置白名单成功")

    @allure.title("Kafka-Topic创建和删除（两种时间戳类型）")
    def test_topic_create_and_delete(self, kafka_page, kafka):
        instance_name = kafka["name"]
        topic_log_append = f"topic-log-{random_string(5)}"
        topic_create_time = f"topic-ct-{random_string(5)}"

        with allure_step_log("步骤一：创建Topic（LogAppendTime）"):
            kafka_page.create_topic(
                instance_name,
                topic_name=topic_log_append,
                partition_count=3,
                replica_count=1,
                retention_days=7,
                timestamp_type="LogAppendTime",
                batch_max_mb=2,
            )
            kafka_page.assert_popup_success("创建 kafka topic成功,如果数据未更新,请刷新页面")
            kafka_page.assert_list_contain(topic_log_append, column_name="Topic名称")

        with allure_step_log("步骤二：创建Topic（CreateTime）"):
            kafka_page.create_topic(
                instance_name,
                topic_name=topic_create_time,
                partition_count=2,
                replica_count=1,
                retention_days=8,
                timestamp_type="CreateTime",
                batch_max_mb=3,
            )
            kafka_page.assert_popup_success("创建 kafka topic成功,如果数据未更新,请刷新页面")
            kafka_page.assert_list_contain(topic_create_time, column_name="Topic名称")

        with allure_step_log("步骤三：删除Topic"):
            kafka_page.delete_topic(instance_name, topic_log_append)
            kafka_page.assert_deleted(topic_log_append)

            kafka_page.delete_topic(instance_name, topic_create_time)
            kafka_page.assert_deleted(topic_create_time)

    @allure.title("Kafka-Topic修改")
    def test_topic_edit(self, kafka_page, kafka):
        instance_name = kafka["name"]
        topic_name = f"topic-edit-{random_string(5)}"

        with allure_step_log("步骤一：创建待修改Topic"):
            kafka_page.create_topic(instance_name, topic_name=topic_name, timestamp_type="LogAppendTime")
            kafka_page.assert_popup_success("创建 kafka topic成功,如果数据未更新,请刷新页面")
            kafka_page.assert_list_contain(topic_name, column_name="Topic名称")

        with allure_step_log("步骤二：修改Topic参数"):
            kafka_page.edit_topic(
                instance_name,
                topic_name=topic_name,
                partition_count=4,
                retention_days=9,
                timestamp_type="CreateTime",
                batch_max_mb=4,
            )
            kafka_page.assert_popup_success("更新 kafka topic成功,如果数据未更新,请刷新页面")

        with allure_step_log("步骤三：清理Topic"):
            kafka_page.delete_topic(instance_name, topic_name)
            kafka_page.assert_deleted(topic_name)

    @allure.title("Kafka-Topic批量删除")
    def test_topic_batch_delete(self, kafka_page, kafka):
        instance_name = kafka["name"]
        topic_names = [f"topic-batch-{random_string(4)}", f"topic-batch-{random_string(4)}"]
        detail_url = None

        with allure_step_log("步骤一：创建多个Topic"):
            for topic_name in topic_names:
                kafka_page.create_topic(instance_name, topic_name=topic_name, timestamp_type="LogAppendTime")
                kafka_page.assert_popup_success("创建 kafka topic成功,如果数据未更新,请刷新页面")
                kafka_page.assert_list_contain(topic_name, column_name="Topic名称")
            detail_url = kafka_page.page.url

        with allure_step_log("步骤二：批量删除Topic"):
            kafka_page.batch_delete_topics(instance_name, topic_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            if detail_url:
                kafka_page.page.goto(detail_url)
            else:
                kafka_page.page.reload()
            kafka_page.ensure_instance_tab(instance_name, "Topic管理")
            for topic_name in topic_names:
                kafka_page.assert_list_not_contain(topic_name, column_name="Topic名称")

    @allure.title("Kafka-实例管理列表页搜索")
    def test_instance_search(self, kafka_page, kafka):
        instance_name = kafka["name"]
        fuzzy_keyword = instance_name[:-2]

        with allure_step_log("步骤一：输入实例全名进行精确搜索"):
            kafka_page.goto_submenu("实例管理")
            kafka_page.search(instance_name)
            kafka_page.assert_list_contain(instance_name)

        with allure_step_log("步骤二：输入实例名称片段进行模糊搜索"):
            kafka_page.search(fuzzy_keyword)
            kafka_page.assert_list_contain(fuzzy_keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            kafka_page.btn_reset.click()
            assert kafka_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("Kafka-Topic列表页搜索")
    def test_topic_search(self, kafka_page, kafka):
        instance_name = kafka["name"]
        topic_name = f"topic-search-{random_string(5)}"
        fuzzy_keyword = topic_name[:-2]

        with allure_step_log("步骤一：创建待搜索Topic"):
            kafka_page.create_topic(instance_name, topic_name=topic_name, timestamp_type="LogAppendTime")
            kafka_page.assert_popup_success("创建 kafka topic成功,如果数据未更新,请刷新页面")
            kafka_page.assert_list_contain(topic_name, column_name="Topic名称")

        with allure_step_log("步骤二：输入Topic全名进行精确搜索"):
            kafka_page.ensure_instance_tab(instance_name, "Topic管理")
            kafka_page.search(topic_name)
            kafka_page.assert_list_contain(topic_name, column_name="Topic名称")

        with allure_step_log("步骤三：输入Topic名称片段进行模糊搜索"):
            kafka_page.search(fuzzy_keyword)
            kafka_page.assert_list_contain(fuzzy_keyword, column_name="Topic名称", exact_match=False)

        with allure_step_log("步骤四：重置搜索条件"):
            kafka_page.btn_reset.click()
            assert kafka_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤五：清理Topic"):
            kafka_page.delete_topic(instance_name, topic_name)
            kafka_page.assert_deleted(topic_name)

    @allure.title("Kafka-切换网络")
    def test_switch_network(self, kafka_page, kafka):
        instance_name = kafka["name"]

        with allure_step_log("步骤一：切换网络 - 快速选择"):
            kafka_page.close_service_for_switch_network(instance_name)
            kafka_page.assert_popup_success("执行成功")
            kafka_page.assert_status(instance_name, status="服务已停止", timeout=1200, refresh=True)
            kafka_page.switch_network(instance_name, network="Autotest", subnet="subnet:10.", selection_type="快速选择")
            kafka_page.assert_status(instance_name, status="VPC切换中", timeout=600, refresh=True)
            kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤二：切换网络 - 手动输入"):
            kafka_page.close_service_for_switch_network(instance_name)
            kafka_page.assert_popup_success("执行成功")
            kafka_page.assert_status(instance_name, status="服务已停止", timeout=1200, refresh=True)
            kafka_page.switch_network(instance_name, network="Autotest", subnet="Autotest:10.", selection_type="手动输入")
            kafka_page.assert_status(instance_name, status="VPC切换中", timeout=600, refresh=True)
            kafka_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)
