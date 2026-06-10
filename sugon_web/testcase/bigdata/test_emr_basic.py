import allure

from sugon_web.utils.logger import allure_step_log


@allure.epic("大数据计算")
@allure.feature("E-MapReduce")
class TestEMRBasic:

    @allure.title("E-MapReduce-实例绑定公网IP")
    def test_instance_bind_ip(self, emr_page, emr, ssh_host):
        cluster_name = emr["name"]

        with allure_step_log("步骤一：基础信息页绑定公网IP"):
            ip = emr_page.instance_ip_binding(cluster_name, "public_net")

        with allure_step_log("步骤二：验证绑定结果"):
            emr_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

    @allure.title("E-MapReduce-添加服务")
    def test_add_service(self, emr_page, emr):
        with allure_step_log("步骤一：添加服务"):
            emr_page.add_service(emr["name"])

        with allure_step_log("步骤二：验证添加服务结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-卸载服务")
    def test_uninstall_service(self, emr_page, emr):
        with allure_step_log("步骤一：卸载服务"):
            emr_page.uninstall_service(emr["name"])

        with allure_step_log("步骤二：验证卸载服务结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-停止所有服务")
    def test_stop_all_services(self, emr_page, emr):
        with allure_step_log("步骤一：停止所有服务"):
            emr_page.operate_all_services(emr["name"], "停止所有服务")

        with allure_step_log("步骤二：验证停止所有服务结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-启动所有服务")
    def test_start_all_services(self, emr_page, emr):
        with allure_step_log("步骤一：启动所有服务"):
            emr_page.operate_all_services(emr["name"], "启动所有服务")

        with allure_step_log("步骤二：验证启动所有服务结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-重启所有服务")
    def test_restart_all_services(self, emr_page, emr):
        with allure_step_log("步骤一：重启所有服务"):
            emr_page.operate_all_services(emr["name"], "重启所有服务")

        with allure_step_log("步骤二：验证重启所有服务结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-节点修改规格")
    def test_change_specification(self, emr_page, emr):
        with allure_step_log("步骤一：节点组修改规格"):
            emr_page.change_specification(emr["name"])

        with allure_step_log("步骤二：验证修改规格结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-节点磁盘扩容")
    def test_expand_disk(self, emr_page, emr):
        with allure_step_log("步骤一：节点组磁盘扩容"):
            emr_page.expand_disk(emr["name"])

        with allure_step_log("步骤二：验证磁盘扩容结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-扩容新增节点")
    def test_add_node(self, emr_page, emr):
        with allure_step_log("步骤一：节点组扩容新增节点"):
            emr_page.add_node(emr["name"], emr["password"])

        with allure_step_log("步骤二：验证扩容结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-缩容删除节点")
    def test_delete_node(self, emr_page, emr):
        with allure_step_log("步骤一：节点组缩容删除节点"):
            emr_page.delete_node(emr["name"])

        with allure_step_log("步骤二：验证缩容结果"):
            emr_page.assert_popup_success()

    @allure.title("E-MapReduce-节点绑定公网IP")
    def test_node_bind_ip(self, emr_page, emr, ssh_host):
        with allure_step_log("步骤一：节点绑定公网IP"):
            ip = emr_page.node_ip_binding(emr["name"], "public_net")

        with allure_step_log("步骤二：验证节点绑定公网IP结果"):
            emr_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)
