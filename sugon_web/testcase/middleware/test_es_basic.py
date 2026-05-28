import allure
from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string


@allure.epic('数据库服务')
@allure.feature('云搜索服务 CSS')
class TestESBasic:

    @allure.title("CSS-重启集群")
    def test_restart_instance(self, es_page, css):
        instance_name = css["name"]

        with allure_step_log("步骤一：重启集群"):
            es_page.restart_instance(instance_name)

        with allure_step_log("步骤二：验证重启结果"):
            es_page.assert_popup_success("重启集群成功")
            es_page.assert_status(instance_name, status="重启中", timeout=600, refresh=True)
            es_page.assert_status(instance_name, status="运行中", timeout=2400, refresh=True)

    @allure.title("CSS-修改实例名称")
    def test_rename_instance(self, es_page, css):
        instance_name = css["name"]
        renamed_name = f"css-renamed-{random_data()}"

        with allure_step_log("步骤一：修改实例名称"):
            es_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证修改实例名称结果"):
            es_page.assert_popup_success("执行成功")
            es_page.assert_list_contain(renamed_name)
            es_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：修改实例名称回退"):
            es_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证回退结果"):
            es_page.assert_popup_success("执行成功")
            es_page.assert_list_contain(instance_name)
            es_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("CSS-修改管理员密码")
    def test_change_root_password(self, es_page, css):
        instance_name = css["name"]
        new_password = f"Admin123@{random_string(4)}"

        with allure_step_log("步骤一：修改管理员密码"):
            es_page.change_root_password(instance_name, new_password)

        with allure_step_log("步骤二：验证修改管理员密码结果"):
            es_page.assert_popup_success("操作成功")
            es_page.assert_status(instance_name, status="运行中", timeout=300, refresh=True)

    @allure.title("CSS-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, es_page, css, ssh_host):
        instance_name = css["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：绑定公网IP"):
            ip = es_page.instance_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            es_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            es_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            es_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("CSS-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, es_page, css, ssh_host):
        instance_name = css["name"]
        network = "public_net(基础版)"

        with allure_step_log("步骤一：节点绑定公网IP"):
            ip = es_page.node_ip_binding(instance_name, network)

        with allure_step_log("步骤二：验证绑定结果"):
            es_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：节点解绑公网IP"):
            es_page.node_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            es_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("CSS-重启节点")
    def test_restart_node(self, es_page, css):
        instance_name = css["name"]
        node_name = f"{instance_name}-data-0"

        with allure_step_log("步骤一：重启节点"):
            es_page.restart_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点重启结果"):
            es_page.assert_popup_success("重启节点成功")
            es_page.assert_status(node_name, status="重启中", timeout=600, refresh=True)
            es_page.assert_status(node_name, status="运行中", timeout=2400, refresh=True)

    @allure.title("CSS-修改规格")
    def test_change_specification(self, es_page, css, ssh_host):
        instance_name = css["name"]
        node_name = f"{instance_name}-data-0"
        specification_name = "应用中间件标准型 es.d6.xlarge 4核 8GiB"
        real_specification = "es.d6.xlarge"

        with allure_step_log("步骤一：修改规格"):
            es_page.change_specification(instance_name, node_name, specification_name)

        with allure_step_log("步骤二：验证规格修改结果"):
            es_page.assert_popup_success("修改规格中，请耐心等待")
            es_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            es_page.assert_status(node_name, status="运行中", timeout=3000, refresh=True)
            assert db_util.get_specification(es_page, node_name, ssh_host) == real_specification

    @allure.title("CSS-修改云硬盘大小")
    def test_change_disk_size(self, es_page, css, ssh_host):
        instance_name = css["name"]
        node_name = f"{instance_name}-data-0"
        current_size = db_util.get_disk_size(es_page, node_name, ssh_host)
        new_size = current_size + 10

        with allure_step_log("步骤一：修改云硬盘大小"):
            es_page.change_disk_size(instance_name, node_name, new_size)

        with allure_step_log("步骤二：验证磁盘大小修改结果"):
            es_page.assert_popup_success("扩容硬盘中，请耐心等待")
            es_page.assert_status(node_name, status="调整云硬盘中", timeout=1200, refresh=True)
            es_page.assert_status(node_name, status="运行中", timeout=3000, refresh=True)
            assert db_util.get_disk_size(es_page, node_name, ssh_host) == new_size

    @allure.title("CSS-节点热迁移")
    def test_es_node_hot_migration(self, es_page, css, ssh_host):
        instance_name = css["name"]
        node_name = f"{instance_name}-data-0"
        old_host = db_util.get_backend_host(es_page, ssh_host, node_name)
        allure.attach(f"迁移前物理机: {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = es_page.es_hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果"):
            es_page.assert_popup_success("热迁移命令下发成功")
            es_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            es_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：后端验证物理机变更"):
            new_host = db_util.get_backend_host(es_page, ssh_host, node_name)
            allure.attach(f"迁移后物理机: {new_host}", name="迁移后状态")
            assert new_host != old_host, f"热迁移失败，迁移前后物理机未变化: {old_host}"
            if selected_host:
                assert selected_host in new_host, f"热迁移失败，期望 {selected_host}，实际 {new_host}"

    @allure.title("CSS-切换网络")
    def test_switch_network(self, es_page, css):
        instance_name = css["name"]

        with allure_step_log("步骤一：切换网络 - 情况1：快速选择"):
            es_page.switch_network(instance_name, network="Autotest", subnet="subnet:10.", selection_type="快速选择")
            es_page.assert_status(instance_name, status="VPC切换中", timeout=300, refresh=True)
            es_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤二：切换网络 - 情况2：手动输入"):
            es_page.switch_network(instance_name, network="Autotest", subnet="Autotest:10.", selection_type="手动输入")
            es_page.assert_status(instance_name, status="VPC切换中", timeout=300, refresh=True)
            es_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

    @allure.title("CSS-新建数据节点")
    def test_add_data_node(self, es_page, css, ssh_host):
        instance_name = css["name"]
        new_node_name = f"{instance_name}-data-3"

        with allure_step_log("步骤一：新建数据节点"):
            es_page.add_data_node(instance_name)
            es_page.assert_popup_success("添加数据节点")

        with allure_step_log("步骤二：验证新增节点状态"):
            es_page.assert_status(new_node_name, status="创建中", timeout=1200, refresh=True)
            es_page.assert_status(new_node_name, status="运行中", timeout=2400, refresh=True)
            db_util.assert_backend_created(es_page, ssh_host, new_node_name)

    @allure.title("CSS-白名单管理")
    def test_whitelist_management(self, es_page, css):
        instance_name = css["name"]
        whitelist_ips = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            es_page.reset_whitelist(instance_name)
            es_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单添加与删除"):
            es_page.add_whitelist(instance_name, ip_single)
            es_page.assert_popup_success("添加白名单成功")
            es_page.assert_list_contain(ip_single, "白名单", exact_match=False)
            es_page.delete_whitelist(instance_name, ip_single)
            es_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤三：测试批量白名单添加与删除"):
            for ip in ip_batch:
                es_page.add_whitelist(instance_name, ip)
                es_page.assert_popup_success("添加白名单成功")
                es_page.assert_list_contain(ip, "白名单", exact_match=False)
            es_page.batch_delete_whitelist(instance_name, ip_batch)
            es_page.assert_popup_success("删除白名单成功")

    @allure.title("CSS-实例搜索")
    def test_search_instance(self, es_page, css):
        instance_name = css["name"]
        keyword = instance_name[:-2]

        with allure_step_log("步骤一：输入实例全名进行精确搜索"):
            es_page.goto_submenu("实例管理")
            es_page.search(instance_name)
            es_page.assert_list_contain(instance_name)

        with allure_step_log("步骤二：输入实例名称片段进行模糊搜索"):
            es_page.search(keyword)
            es_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            es_page.btn_reset.click()
            assert es_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("CSS-参数配置")
    def test_edit_instance_parameter(self, es_page, css):
        instance_name = css["name"]
        param_name = "http.max_content_length"
        param_value = "201"

        with allure_step_log(f"步骤一：编辑参数 {param_name} 为 {param_value}"):
            es_page.edit_instance_parameter(instance_name, param_name, param_value)

        with allure_step_log("步骤二：验证参数编辑结果"):
            es_page.assert_popup_success("执行成功")
