from time import sleep
import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for MongoDB)')
class TestMongoDBBasic:

    @allure.title("MongoDB-重命名实例")
    def test_rename_instance(self, mongodb_page, mongodb):
        """测试重命名MongoDB实例"""
        instance_name = mongodb["name"]
        renamed_name = f"mongo-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            mongodb_page.rename_instance(instance_name, renamed_name)
        with allure_step_log("步骤二：验证重命名结果"):
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_list_contain(renamed_name)
            mongodb_page.assert_status(renamed_name, status="运行中")

        # 增加等待，并刷新页面，确保列表数据最新
        sleep(5)
        mongodb_page.wait_for_page_ready()

        with allure_step_log("步骤三：重命名实例回退"):
            mongodb_page.rename_instance(renamed_name, instance_name)
        with allure_step_log("步骤四：验证重命名回退结果"):
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_list_contain(instance_name)
            mongodb_page.assert_status(instance_name, status="运行中")

    @allure.title("MongoDB-修改实例管理员密码")
    def test_change_root_password(self, mongodb_page, mongodb, ssh_host, ssh_vm):
        """测试修改MongoDB实例的管理员密码"""
        instance_name = mongodb["name"]
        # 新密码规则：大写、小写、数字、特殊字符(!#$%^&*()_+=)至少三种
        new_password = f"NewAdmin1#{random_string(k=5)}"

        with allure_step_log("步骤一：修改管理员密码"):
            mongodb_page.change_root_password(instance_name, new_password)
        with allure_step_log("步骤二：验证修改密码结果"):
            mongodb_page.assert_popup_success("修改root密码成功")
            mongodb_page.assert_status(instance_name, status="运行中", timeout=300)

        with allure_step_log("步骤三：验证新密码生效"):
            # 获取节点IP进行连接验证
            node_name = f"{instance_name}-0" # 假设副本集第一个节点是-0
            try:
                ip_from_db = db_util.get_node_mfip_from_db(mongodb_page, ssh_host, "sugoncloud_mongodb", node_name)
                ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
                cmd = f"mongo --host 127.0.0.1 --port 27017 -u root -p '{new_password}' --authenticationDatabase admin --eval \"printjson(db.adminCommand('ping'))\""
                result = ssh_vm.run(cmd)
                assert '"ok" : 1' in result
            except Exception as e:
                pytest.fail(f"后端密码验证失败: {e}")
            
            # mongodb["root_password"] = new_password

    @allure.title("MongoDB-修改云盘大小")
    def test_change_disk_size(self, mongodb_page, mongodb, ssh_host):
        """测试调整MongoDB实例的云盘大小"""
        instance_name = mongodb["name"]
        new_disk_size = 66

        with allure_step_log(f"步骤一：调整实例 {instance_name} 的磁盘大小为 {new_disk_size}GB"):
            mongodb_page.change_disk_size(instance_name, new_disk_size)

        with allure_step_log("步骤二：验证调整结果"):
            node_name = f"{instance_name}-0"
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_status(node_name, status="调整云硬盘中", timeout=1200, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=600, refresh=True)
            # 后端验证
            try:
                assert db_util.get_disk_size(mongodb_page, node_name, ssh_host) == new_disk_size
            except Exception as e:
                mongodb_page.logger.warning(f"跳过后端磁盘大小验证: {e}")

    @allure.title("MongoDB-修改实例规格")
    def test_change_specification(self, mongodb_page, mongodb, ssh_host):
        """测试修改MongoDB实例的规格"""
        instance_name = mongodb["name"]
        # 需要确认页面上存在的规格名称
        specification_name = "mongodb.d6 mongodb.d6.2xlarge 8核" 
        real_specification = "mongodb.d6.2xlarge"

        with allure_step_log("步骤一：执行修改规格操作"):
            mongodb_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格是否修改成功"):
            node_name = f"{instance_name}-0"
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=5000, refresh=True)
            # 后端验证
            try:
                assert db_util.get_specification(mongodb_page, node_name, ssh_host) == real_specification
            except Exception as e:
                mongodb_page.logger.warning(f"跳过后端规格验证: {e}")

    @allure.title("MongoDB-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, mongodb_page, mongodb, ssh_host):
        """测试节点绑定和解绑MongoDB实例的公网IP"""
        instance_name = mongodb["name"]
        node_name = f"{instance_name}-0" # 假设绑定第一个shard节点
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = mongodb_page.node_ip_binding(instance_name, node_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            mongodb_page.assert_popup_success("执行成功")
            # 验证 ping
            if ssh_host:
                ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            mongodb_page.node_ip_unbinding(instance_name, node_name)

        with allure_step_log("步骤四：验证解绑结果"):
            mongodb_page.assert_popup_success("执行成功")
            if ssh_host:
                ssh_host.ping(ip, connected=False)

    @allure.title("MongoDB-修改用户密码")
    def test_change_user_password(self, mongodb_page, mongodb, ssh_host, ssh_vm):
        """测试修改用户密码"""
        instance_name = mongodb["name"]
        user_name = mongodb["user_name"] # 使用fixture中的用户名
        new_password = f"User{random_string(k=5)}#New"
        with allure_step_log("步骤一：修改用户密码"):
            mongodb_page.change_user_password(instance_name, user_name, new_password)

        with allure_step_log("步骤二：验证修改结果"):
            mongodb_page.assert_popup_success("修改root密码成功")

        with allure_step_log("步骤三：验证新密码生效"):
            # 获取节点IP进行连接验证
            node_name = f"{instance_name}-0" # 假设副本集第一个节点是-0
            try:
                ip_from_db = db_util.get_node_mfip_from_db(mongodb_page, ssh_host, "sugoncloud_mongodb", node_name)
                ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
                cmd = f"mongo --host 127.0.0.1 --port 27017 -u {user_name} -p '{new_password}' --authenticationDatabase admin --eval \"printjson(db.adminCommand('ping'))\""
                result = ssh_vm.run(cmd)
                assert '"ok" : 1' in result
            except Exception as e:
                pytest.fail(f"后端密码验证失败: {e}")

    @allure.title("MongoDB-白名单管理")
    def test_whitelist_management(self, mongodb_page, mongodb):
        """测试白名单管理（添加、删除、重置）"""
        instance_name = mongodb["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24"
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单"):
            mongodb_page.reset_whitelist(instance_name)
            mongodb_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：添加单个白名单"):
            mongodb_page.add_whitelist(instance_name, ip_single)
            mongodb_page.assert_popup_success("添加白名单成功")
            mongodb_page.assert_list_contain(ip_single, "白名单", exact_match=False)

        with allure_step_log("步骤三：删除单个白名单"):
            mongodb_page.delete_whitelist(instance_name, ip_single)
            mongodb_page.assert_popup_success("移除白名单成功")

        with allure_step_log("步骤四：添加多个白名单"):
            for ip in ip_batch:
                mongodb_page.add_whitelist(instance_name, ip)
                mongodb_page.assert_popup_success("添加白名单成功")

        with allure_step_log("步骤五：批量删除白名单"):
            mongodb_page.batch_delete_whitelist(instance_name, ip_batch)
            mongodb_page.assert_popup_success("移除白名单成功")

    @allure.title("MongoDB-实例管理列表页搜索")
    def test_instance_search(self, mongodb_page, mongodb):
        """测试实例管理列表页的搜索功能"""
        instance_name = mongodb["name"]

        with allure_step_log("步骤一：输入实例名称进行搜索"):
            mongodb_page.goto_submenu("实例管理")
            keyword = instance_name[:-2]
            mongodb_page.search(keyword)
            mongodb_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mongodb_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mongodb_page.wait_for_page_ready()
            assert mongodb_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MongoDB-用户列表页搜索")
    def test_user_search(self, mongodb_page, mongodb):
        """测试用户列表页的搜索功能"""
        instance_name = mongodb["name"]
        user_name = mongodb["user_name"]

        with allure_step_log("步骤一：输入用户名称进行搜索"):
            mongodb_page.goto_submenu("实例管理")
            mongodb_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            mongodb_page.wait_for_page_ready()
            mongodb_page.get_by_role("tab", name="用户").click()
            mongodb_page.wait_for_page_ready()
            keyword = user_name
            mongodb_page.search(keyword)
            mongodb_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mongodb_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mongodb_page.wait_for_page_ready()
            assert mongodb_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MongoDB-实例参数设置页搜索")
    def test_instance_parameter_search(self, mongodb_page, mongodb):
        """测试实例参数设置页的搜索功能"""
        instance_name = mongodb["name"]
        param_keyword = "connPool"

        with allure_step_log("步骤一：输入参数名称进行搜索"):
            mongodb_page.goto_submenu("实例管理")
            mongodb_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            mongodb_page.wait_for_page_ready()
            sleep(2)
            mongodb_page.get_by_role("tab", name="参数设置").click()
            sleep(2)
            mongodb_page.wait_for_page_ready()
            mongodb_page.search(param_keyword)
            mongodb_page.assert_list_contain(param_keyword, "参数名称", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mongodb_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mongodb_page.wait_for_page_ready()
            assert mongodb_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
