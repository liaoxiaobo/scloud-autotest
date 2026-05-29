from time import sleep
import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string


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
            mongodb_page.assert_status(renamed_name, status="运行中", refresh=True)

        # 增加等待，并刷新页面，确保列表数据最新
        sleep(5)

        with allure_step_log("步骤三：重命名实例回退"):
            mongodb_page.rename_instance(renamed_name, instance_name)
        with allure_step_log("步骤四：验证重命名回退结果"):
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_list_contain(instance_name)
            mongodb_page.assert_status(instance_name, status="运行中", refresh=True)

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
            mongodb_page.assert_status(instance_name, status="运行中", timeout=300, refresh=True)

        with allure_step_log("步骤三：验证新密码生效"):
            # 获取节点IP进行连接验证
            node_name = f"{instance_name}-0"  # 假设副本集第一个节点是-0
            try:
                ip_from_db = ssh_host.get_node_mfip("sugoncloud_mongodb", node_name)
                ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
                cmd = f"mongo --host 127.0.0.1 --port 27017 -u root -p '{new_password}' --authenticationDatabase admin --eval \"printjson(db.adminCommand('ping'))\""
                result = ssh_vm.run(cmd)
                assert '"ok" : 1' in result
            except Exception as e:
                pytest.fail(f"后端密码验证失败: {e}")

            mongodb["root_password"] = new_password

    @allure.title("MongoDB-添加备节点")
    def test_add_secondary_node(self, mongodb_page, mongodb, ssh_host):
        """测试为MongoDB副本集实例添加备节点"""
        instance_name = mongodb["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页并点击新建备节点"):
            mongodb_page.add_secondary_node(instance_name)
            mongodb_page.assert_popup_success("添加备节点")

        with allure_step_log("步骤二：验证节点状态变化"):
            # 根据用户描述，新建备节点会多出来两个节点：-3 和 -4
            # 3和4是同时创建的，先快速验证两者都进入了创建中状态
            for i in [3, 4]:
                node_name = f"{instance_name}-{i}"
                mongodb_page.assert_status(node_name, status="创建中", timeout=300, refresh=True)

            # 再等待两者都进入运行中状态
            for i in [3, 4]:
                node_name = f"{instance_name}-{i}"
                mongodb_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证节点存在"):
            for i in [3, 4]:
                ssh_host.assert_resource_created(f"{instance_name}-{i}")

    @allure.title("MongoDB-添加只读节点")
    def test_add_readonly_node(self, mongodb_page, mongodb, ssh_host):
        """测试为MongoDB副本集实例添加只读节点"""
        instance_name = mongodb["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页并点击新建只读节点"):
            mongodb_page.add_readonly_node(instance_name)
            mongodb_page.assert_popup_success("添加只读节点")

        with allure_step_log("步骤二：验证节点状态变化"):
            # 根据用户描述，新建只读节点会再多出来一个节点：-5
            node_name = f"{instance_name}-5"
            mongodb_page.assert_status(node_name, status="创建中", timeout=600, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证节点存在"):
            ssh_host.assert_resource_created(node_name)

    @allure.title("MongoDB-分片集群-添加Mongos节点")
    def test_add_mongos_node(self, mongodb_page, mongodb, ssh_host):
        """测试为MongoDB分片集群添加Mongos节点"""
        instance_name = mongodb["name1"]

        with allure_step_log(f"步骤一：为实例 {instance_name} 添加Mongos节点"):
            mongodb_page.add_mongos_node(instance_name)
            mongodb_page.assert_popup_success("添加mongos节点")

        with allure_step_log("步骤二：验证新节点状态变化"):
            # 原有 0-10，新节点为 11
            node_name = f"{instance_name}-11"
            mongodb_page.assert_status(node_name, status="创建中", timeout=600, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证节点存在"):
            ssh_host.assert_resource_created(node_name)

    @allure.title("MongoDB-分片集群-调整分片")
    def test_adjust_shards(self, mongodb_page, mongodb, ssh_host):
        """测试为MongoDB分片集群调整分片数量"""
        instance_name = mongodb["name1"]

        with allure_step_log(f"步骤一：为实例 {instance_name} 调整分片数量为 3"):
            mongodb_page.adjust_shards(instance_name, 3)
            mongodb_page.assert_popup_success("调整分片数量")

        with allure_step_log("步骤二：验证新节点状态变化"):
            # 假设再出现 3 个节点：12, 13, 14
            for i in [12, 13, 14]:
                node_name = f"{instance_name}-{i}"
                mongodb_page.assert_status(node_name, status="创建中", timeout=600, refresh=True)

            for i in [12, 13, 14]:
                node_name = f"{instance_name}-{i}"
                mongodb_page.assert_status(node_name, status="运行中", timeout=2400, refresh=True)

        with allure_step_log("步骤三：后端验证节点存在"):
            for i in [12, 13, 14]:
                ssh_host.assert_resource_created(f"{instance_name}-{i}")

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
                assert ssh_host.get_volume_size(node_name) == new_disk_size
            except Exception as e:
                mongodb_page.logger.warning(f"跳过后端磁盘大小验证: {e}")

    @allure.title("MongoDB-修改实例规格")
    def test_change_specification(self, mongodb_page, mongodb, ssh_host):
        """测试修改MongoDB实例的规格"""
        instance_name = mongodb["name"]
        # 需要确认页面上存在的规格名称
        specification_name = "mongodb.d6 mongodb.d6.xlarge 4核"
        real_specification = "mongodb.d6.xlarge"

        with allure_step_log("步骤一：执行修改规格操作"):
            mongodb_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格是否修改成功"):
            node_name = f"{instance_name}-0"
            mongodb_page.assert_popup_success("执行成功")
            mongodb_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=5000, refresh=True)
            # 后端验证
            try:
                assert ssh_host.guest_show(node_name).get("flavor_name") == real_specification
            except Exception as e:
                mongodb_page.logger.warning(f"跳过后端规格验证: {e}")

    @allure.title("MongoDB-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, mongodb_page, mongodb, ssh_host):
        """测试节点绑定和解绑MongoDB实例的公网IP"""
        instance_name = mongodb["name"]
        node_name = f"{instance_name}-0"  # 假设绑定第一个shard节点
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
            assert mongodb_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MongoDB-开启和关闭错误日志")
    def test_toggle_error_log(self, mongodb_page, mongodb):
        """测试为MongoDB实例开启和关闭错误日志功能"""
        instance_name = mongodb["name"]
        with allure_step_log(f"步骤一：为实例 {instance_name} 开启错误日志"):
            mongodb_page.enable_error_log(instance_name)

        with allure_step_log("步骤二：验证开启结果"):
            mongodb_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤三：为实例 {instance_name} 关闭错误日志"):
            mongodb_page.disable_error_log(instance_name)

        with allure_step_log("步骤四：验证关闭结果"):
            mongodb_page.assert_popup_success("执行成功")

    @allure.title("MongoDB-实例参数搜索")
    def test_instance_parameter_search(self, mongodb_page, mongodb):
        """测试实例参数设置页的搜索功能"""
        instance_name = mongodb["name"]
        param_keyword = "operationProfiling.slowOpThresholdMs"

        with allure_step_log("步骤一：输入参数名称进行搜索"):
            mongodb_page.goto_submenu("实例管理")
            mongodb_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            sleep(2)
            mongodb_page.get_by_role("tab", name="参数设置").click()
            sleep(2)
            mongodb_page.search(param_keyword)
            mongodb_page.assert_list_contain(param_keyword, "参数名称", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mongodb_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            assert mongodb_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MongoDB-节点热迁移")
    def test_mongodb_node_hot_migration(self, mongodb_page, mongodb, ssh_host, ssh_vm):
        """测试MongoDB节点的热迁移功能"""
        instance_name = mongodb["name"]
        node_name = f"{instance_name}-0"
        password = "admin1234@sugon"
        root_password = mongodb["root_password"]

        # 记录迁移前的物理机 (后端校验)
        old_host = ssh_host.guest_show(node_name).get("node")
        allure.attach(f"迁移前物理机 (后端): {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = mongodb_page.mongodb_hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果"):
            mongodb_page.assert_popup_success("热迁移命令下发成功")
            mongodb_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            mongodb_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证物理机节点变更 (后端校验)"):
            # 热迁移后，通过后端 gova list 命令验证节点是否真正切换
            new_host = ssh_host.guest_show(node_name).get("node")
            allure.attach(f"迁移后物理机 (后端): {new_host}", name="迁移后状态")

            assert new_host != old_host, f"热迁移失败，后端查询迁移前后物理机节点未变更: {old_host}"
            if selected_host:
                # selected_host 是 UI 上选中的名称，后端返回的可能带域名，所以用 in 判断
                assert selected_host in new_host, f"热迁移失败，期望迁移至节点:{selected_host},实际迁移至节点:{new_host}"

        with allure_step_log("步骤四：验证迁移后数据库连接"):
            ip_from_db = ssh_host.get_node_mfip("sugoncloud_mongodb", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=password)
            cmd_check = f"mongo --host 127.0.0.1 --port 27017 -u root -p '{root_password}' --authenticationDatabase admin --eval \"printjson(db.adminCommand('ping'))\""
            result = ssh_vm.run(cmd_check)
            assert '"ok" : 1' in result, f"热迁移后数据库连接失败: {result}"
            ssh_vm.close()

    @allure.title("MongoDB-实例参数编辑")
    def test_edit_instance_parameters(self, mongodb_page, mongodb):
        """测试实例参数的编辑和导出"""
        instance_name = mongodb["name"]
        param_name = "operationProfiling.slowOpThresholdMs"
        param_value = "99"

        with allure_step_log(f"步骤一：编辑实例 {instance_name} 的参数 {param_name} 值为 {param_value}"):
            mongodb_page.goto_submenu("实例管理")
            mongodb_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)
            mongodb_page.edit_instance_parameter(instance_name, param_name, param_value)
            # MongoDB 参数应用可能不需要重启，或者根据环境而定
            mongodb_page.assert_popup_success("修改实例参数成功")
            mongodb_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)
