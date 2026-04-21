from time import sleep

import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('数据仓库 Doris')
class TestDorisBasic:

    @allure.title("Doris-重命名实例")
    def test_rename_instance(self, doris_page, doris):
        """测试重命名Doris实例"""
        instance_name = doris["name"]
        renamed_name = f"doris-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            doris_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证重命名结果"):
            doris_page.assert_popup_success("修改实例名称成功")
            doris_page.assert_list_contain(renamed_name)
            doris_page.assert_status(renamed_name, status="就绪", refresh=True)

        with allure_step_log("步骤三：重命名实例回退"):
            doris_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证重命名回退结果"):
            doris_page.assert_popup_success("修改实例名称成功")
            doris_page.assert_list_contain(instance_name)
            doris_page.assert_status(instance_name, status="就绪", refresh=True)

    @allure.title("Doris-重置管理员密码")
    def test_reset_admin_password(self, doris_page, doris, ssh_host, ssh_vm):
        """测试重置Doris实例的管理员密码"""
        instance_name = doris["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：重置管理员密码"):
            doris_page.reset_admin_password(instance_name, new_password)

        with allure_step_log("步骤二：验证密码重置结果"):
            doris_page.assert_popup_success("执行成功")
            doris_page.assert_status(instance_name, status="就绪", timeout=300, refresh=True)

        with allure_step_log("步骤三：验证新密码生效"):
            node_name = f"{instance_name}_fe_node01"
            ip_from_db = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            # 验证新密码可以成功登录Doris
            cmd_new = f"mysql -uadmin -p'{new_password}' -P9030 -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new)
            assert result_new.splitlines()[-1] == "1"

    @allure.title("Doris-停止和启动实例")
    def test_stop_and_start_instance(self, doris_page, doris):
        """测试停止和启动Doris实例"""
        instance_name = doris["name"]

        with allure_step_log("步骤一：停止实例"):
            doris_page.stop_instance(instance_name)

        with allure_step_log("步骤二：验证停止结果"):
            doris_page.assert_popup_success("实例停止任务创建完成")
            doris_page.assert_status(instance_name, status="停止中", timeout=1200, refresh=True)
            doris_page.assert_status(instance_name, status="就绪", timeout=1800, refresh=True)

        with allure_step_log("步骤三：状态重置"):
            doris_page.reset_instance(instance_name)

        with allure_step_log("步骤四：验证状态重置结果"):
            doris_page.assert_popup_success("实例数据库状态重置成功")
            doris_page.assert_status(instance_name, status="就绪", timeout=1200, refresh=True)

        with allure_step_log("步骤三：启动实例"):
            doris_page.start_instance(instance_name)

        with allure_step_log("步骤四：验证启动结果"):
            doris_page.assert_popup_success("实例重启任务创建完成")
            doris_page.assert_status(instance_name, status="重启中", timeout=1200, refresh=True)
            doris_page.assert_status(instance_name, status="正常", timeout=1200, refresh=True)

    @allure.title("DORIS-实例管理列表页搜索")
    def test_instance_search(self, doris_page, doris):
        """测试实例管理列表页的搜索功能"""
        instance_name = doris["name"]

        with allure_step_log("步骤一：输入实例名称进行搜索"):
            doris_page.goto_submenu("实例管理")
            keyword = instance_name[:-2]
            doris_page.search(keyword)
            doris_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            doris_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert doris_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("Doris-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, doris_page, doris, ssh_host):
        """测试实例绑定和解绑Doris实例的公网IP"""
        instance_name = doris["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = doris_page.instance_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            doris_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(doris_page, ip, ssh_host)
            assert return_code == 0

        with allure_step_log("步骤三：解绑公网IP"):
            doris_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            # 解绑后，IP地址信息应该不再显示
            doris_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(doris_page, ip, ssh_host)
            assert return_code != 0

    @allure.title("Doris-修改节点云硬盘大小")
    def test_change_disk_size(self, doris_page, doris, ssh_host):
        """测试调整Doris节点的云盘大小"""
        instance_name = doris["name"]
        new_disk_size = 60  # FE节点从50扩容到60

        with allure_step_log(f"步骤一：调整FE节点云硬盘大小为 {new_disk_size}GB"):
            doris_page.change_disk_size(instance_name, node_type="fe", new_size=new_disk_size)

        with allure_step_log("步骤二：验证调整结果"):
            node_name = f"{instance_name}_fe_node01"
            doris_page.assert_popup_success("调整云硬盘中")
            doris_page.assert_status(node_name, status="调整云硬盘中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="就绪", timeout=500, refresh=True)
            assert db_util.get_disk_size(doris_page, node_name, ssh_host) == new_disk_size

    @allure.title("Doris-修改节点规格")
    def test_change_specification(self, doris_page, doris, ssh_host):
        """测试修改Doris节点的规格"""
        instance_name = doris["name"]
        specification_name = "doris.d1 doris.d1.4c8g 4核"
        real_specification = "doris.d1.4c8g"

        with allure_step_log("步骤一：执行修改规格操作"):
            doris_page.change_specification(instance_name, specification_name, node_type="be")

        with allure_step_log("步骤二：验证规格是否修改成功"):
            node_name = f"{instance_name}_be_node01"
            doris_page.assert_popup_success("调整规格中")
            doris_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="就绪", timeout=5000, refresh=True)
            assert db_util.get_specification(doris_page, node_name, ssh_host) == real_specification

    @allure.title("Doris-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, doris_page, doris, ssh_host):
        """测试节点绑定和解绑Doris节点的公网IP"""
        instance_name = doris["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP到FE节点"):
            ip = doris_page.node_ip_binding(instance_name, network=network, node_type="fe")

        with allure_step_log("步骤二：验证绑定结果"):
            doris_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(doris_page, ip, ssh_host)
            assert return_code == 0

        with allure_step_log("步骤三：解绑公网IP"):
            doris_page.node_ip_unbinding(instance_name, node_type="fe")

        with allure_step_log("步骤四：验证解绑结果"):
            doris_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(doris_page, ip, ssh_host)
            assert return_code != 0

    @allure.title("Doris-添加BE节点")
    def test_add_be_node(self, doris_page, doris, ssh_host):
        """测试为Doris实例添加BE节点"""
        instance_name = doris["name"]
        node_name = f"{instance_name}_be_node04"

        with allure_step_log("步骤一：为实例添加新BE节点"):
            doris_page.add_be_node(instance_name)

        with allure_step_log("步骤二：验证BE节点是否添加成功"):
            doris_page.assert_popup_success("BE节点扩容中")
            doris_page.assert_status(node_name, status="创建中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

    @allure.title("Doris-停止BE节点")
    def test_stop_be_node(self, doris_page, doris, ssh_host, ssh_vm):
        """测试停止Doris BE节点"""
        instance_name = doris["name"]
        node_name = f"{instance_name}_be_node04"

        with allure_step_log("步骤一：停止BE节点"):
            doris_page.stop_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点停止结果"):
            doris_page.assert_popup_success("节点停止任务提交完成")
            doris_page.assert_status(node_name, status="节点停止中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="关机", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证Doris BE服务已停止"):
            # 连接到BE节点，检查doris_be服务状态
            node_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(node_ip, port=22022, pwd="admin1234@sugon")
            service_status = db_util.get_service_status(doris_page, ssh_vm, "doris-be")
            assert service_status == "stopped", f"Doris BE服务状态异常: {service_status}"
            ssh_vm.close()

    @allure.title("Doris-启动BE节点")
    def test_start_be_node(self, doris_page, ssh_host, doris, ssh_vm):
        """测试启动Doris BE节点"""
        instance_name = doris["name"]
        # 使用第二个BE节点进行测试
        node_name = f"{instance_name}_be_node04"

        with allure_step_log("步骤一：启动BE节点"):
            doris_page.start_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点启动结果"):
            doris_page.assert_popup_success("节点启动任务提交完成")
            doris_page.assert_status(node_name, status="节点启动中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证节点在后端已运行"):
            # 通过后端验证节点确实已恢复运行
            node_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(node_ip, port=22022, pwd="admin1234@sugon")
            service_status = db_util.get_service_status(doris_page, ssh_vm, "doris-be")
            assert service_status == "running", f"Doris BE服务状态异常: {service_status}"
            ssh_vm.close()

    @allure.title("Doris-下线BE节点")
    def test_offline_be_node(self, doris_page, doris):
        """测试下线Doris BE节点（下线后无法再上线）"""
        instance_name = doris["name"]
        # 使用第二个BE节点进行测试
        node_name = f"{instance_name}_be_node04"

        with allure_step_log("步骤一：下线BE节点"):
            doris_page.offline_be_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点下线结果"):
            doris_page.assert_popup_success("节点下线任务提交完成")
            doris_page.assert_status(node_name, status="节点下线中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="节点已下线", timeout=1200, refresh=True)

    @allure.title("Doris-删除BE节点")
    def test_delete_be_node(self, doris_page, doris, ssh_host):
        """测试删除Doris BE节点"""
        instance_name = doris["name"]
        # 删除已下线的第二个BE节点
        node_name = f"{instance_name}_be_node04"

        with allure_step_log("步骤一：删除BE节点"):
            doris_page.delete_node(instance_name, node_name)

        with allure_step_log("步骤二：验证BE节点是否删除成功"):
            doris_page.assert_deleted(node_name, timeout=1800, refresh=True)
            db_util.assert_backend_deleted(doris_page, ssh_host, node_name)

    @allure.title("Doris-重启FE节点")
    def test_restart_fe_node(self, doris_page, doris, ssh_host, ssh_vm):
        """测试重启Doris FE节点"""
        instance_name = doris["name"]
        # 使用第一个FE节点进行测试
        node_name = f"{instance_name}_fe_node01"

        with allure_step_log("步骤一：重启FE节点"):
            doris_page.restart_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点重启结果"):
            doris_page.assert_popup_success("节点重启任务提交完成")
            doris_page.assert_status(node_name, status="节点重启中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="就绪", timeout=1800, refresh=True)

        with allure_step_log("步骤三：验证节点在后端已运行"):
            # 通过后端验证节点确实已恢复运行
            node_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(node_ip, port=22022, pwd="admin1234@sugon")
            service_status = db_util.get_service_status(doris_page, ssh_vm, "doris-fe")
            assert service_status == "running", f"Doris BE服务状态异常: {service_status}"
            ssh_vm.close()

    @allure.title("Doris-重启BE节点")
    def test_restart_be_node(self, doris_page, doris, ssh_host, ssh_vm):
        """测试重启Doris BE节点"""
        instance_name = doris["name"]
        # 使用第一个BE节点进行测试
        node_name = f"{instance_name}_be_node01"

        with allure_step_log("步骤一：重启BE节点"):
            doris_page.restart_node(instance_name, node_name)

        with allure_step_log("步骤二：验证节点重启结果"):
            doris_page.assert_popup_success("节点重启任务提交完成")
            doris_page.assert_status(node_name, status="节点重启中", timeout=1200, refresh=True)
            doris_page.assert_status(node_name, status="就绪", timeout=1800, refresh=True)

        with allure_step_log("步骤三：验证节点在后端已运行"):
            # 通过后端验证节点确实已恢复运行
            node_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(node_ip, port=22022, pwd="admin1234@sugon")
            service_status = db_util.get_service_status(doris_page, ssh_vm, "doris-be")
            assert service_status == "running", f"Doris BE服务状态异常: {service_status}"
            ssh_vm.close()

    @allure.title("Doris-节点热迁移")
    def test_doris_node_hot_migration(self, doris_page, doris, ssh_host, ssh_vm):
        """测试Doris节点的热迁移功能"""
        instance_name = doris["name"]
        node_name = f"{instance_name}_fe_node01"
        password = "admin1234@sugon"

        # 记录迁移前的物理机 (后端校验)
        old_host = db_util.get_backend_host(doris_page, ssh_host, node_name)
        allure.attach(f"迁移前物理机 (后端): {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = doris_page.hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果"):
            doris_page.assert_popup_success("热迁移命令下发成功")
            doris_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            doris_page.assert_status(node_name, status="就绪", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证物理机节点变更 (后端校验)"):
            # 热迁移后，通过后端 gova list 命令验证节点是否真正切换
            new_host = db_util.get_backend_host(doris_page, ssh_host, node_name)
            allure.attach(f"迁移后物理机 (后端): {new_host}", name="迁移后状态")

            assert new_host != old_host, f"热迁移失败，后端查询迁移前后物理机节点未变更: {old_host}"
            if selected_host:
                # selected_host 是 UI 上选中的名称，后端返回的可能带域名，所以用 in 判断
                assert selected_host in new_host, f"热迁移失败，期望迁移至节点:{selected_host},实际迁移至节点:{new_host}"

        with allure_step_log("步骤四：验证迁移后数据库连接"):
            ip_from_db = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=password)
            # 验证Doris服务是否正常
            service_status = db_util.get_service_status(doris_page, ssh_vm, "doris-fe")
            assert service_status == "running", f"热迁移后Doris FE服务状态异常: {service_status}"
            ssh_vm.close()

    @allure.title("Doris-创建和删除数据库")
    def test_create_and_delete_database(self, doris_page, doris, ssh_host, ssh_vm):
        """测试在实例下创建和删除数据库，并验证其在后端生效与失效"""
        instance_name = doris["name"]
        db_name = f"autodb_{random_string(k=5)}"
        admin_password = "admin1234@sugon"

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建数据库 {db_name}"):
            doris_page.create_database(instance_name, db_name)

        with allure_step_log("步骤二：验证数据库是否创建成功"):
            doris_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            doris_page.assert_database_exist(db_name)

        with allure_step_log("步骤三：验证新创建的数据库在后端生效"):
            fe_node_name = f"{instance_name}_fe_node01"
            fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
            ssh_vm.connect(fe_ip, port=22022, pwd="admin1234@sugon")
            cmd_check_exist = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
            result_exist = ssh_vm.run(cmd_check_exist)
            allure.attach(result_exist, name=f"查询数据库 {db_name} 的存在性",
                          attachment_type=allure.attachment_type.TEXT)
            assert db_name in result_exist, f"在数据库后端未找到新创建的数据库 '{db_name}'"

        with allure_step_log(f"步骤四：在实例 {instance_name} 下删除数据库 {db_name}"):
            doris_page.delete_database(instance_name, db_name)

        with allure_step_log("步骤五：验证数据库删除成功"):
            doris_page.assert_deleted(db_name, refresh=True)
            sleep(2)
        with allure_step_log("步骤六：验证数据库在后端已失效"):
            fe_node_name = f"{instance_name}_fe_node01"
            fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
            ssh_vm.connect(fe_ip, port=22022, pwd="admin1234@sugon")
            cmd_check_gone = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
            result_gone = ssh_vm.run(cmd_check_gone)
            allure.attach(result_gone, name=f"再次查询数据库 {db_name} 的存在性",
                          attachment_type=allure.attachment_type.TEXT)
            assert db_name not in result_gone, f"数据库 '{db_name}' 在后端删除失败，仍然存在。"
            ssh_vm.close()

    @allure.title("Doris-数据库列表页搜索")
    def test_database_search(self, doris_page, doris):
        """测试数据库列表页的搜索功能"""
        instance_name = doris["name"]
        db_name = doris["db_name"]

        with allure_step_log("步骤一：输入数据库名称进行搜索"):
            doris_page.goto_submenu("实例管理")
            doris_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            doris_page.get_by_role("tab", name="数据库", exact=True).click()
            keyword = db_name[:-2]
            doris_page.search(keyword)
            doris_page.assert_database_exist(keyword)

        with allure_step_log("步骤二：重置搜索条件"):
            doris_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert doris_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("Doris-用户列表页搜索")
    def test_user_search(self, doris_page, doris):
        """测试用户列表页的搜索功能"""
        instance_name = doris["name"]
        user_name = doris["user_name"]

        with allure_step_log("步骤一：输入用户名称进行搜索"):
            doris_page.goto_submenu("实例管理")
            doris_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            doris_page.get_by_role("tab", name="用户").click()
            keyword = user_name[:-2]
            doris_page.search(keyword)
            doris_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            doris_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert doris_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("Doris-创建和删除用户")
    def test_create_and_delete_user(self, doris_page, doris, ssh_host, ssh_vm):
        """测试创建和删除Doris用户，并进行后端验证"""
        instance_name = doris["name"]
        db_name = doris["db_name"]
        user_name = f"user_{random_string(k=5)}"
        user_password = f"Pwd@1{random_string(k=5)}"
        admin_password = "admin1234@sugon"

        with allure_step_log(f"步骤一：在实例 {instance_name} 中为数据库 {db_name} 创建用户 {user_name}"):
            doris_page.create_user(instance_name, user_name, user_password)

        with allure_step_log("步骤二：验证用户是否创建成功"):
            doris_page.assert_popup_success("操作成功")
            doris_page.assert_list_contain(user_name, "用户名")

        with allure_step_log(f"步骤三：后端验证：使用新用户登录并执行查询"):
            fe_node_name = f"{instance_name}_fe_node01"
            fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
            ssh_vm.connect(fe_ip, port=22022, pwd=admin_password)
            # 验证新用户可以成功登录
            cmd_login = f"mysql -u{user_name} -p'{user_password}' -P9030 -h127.0.0.1 -e 'SELECT 1;'"
            result = ssh_vm.run(cmd_login)
            assert result.splitlines()[-1] == "1", f"用户 {user_name} 登录失败"

        with allure_step_log(f"步骤四：删除用户 {user_name}"):
            doris_page.delete_user(instance_name, user_name)

        with allure_step_log("步骤五：验证用户删除成功"):
            doris_page.assert_deleted(user_name)
            # 后端验证：确认用户已不存在
            cmd_check = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"SELECT user FROM mysql.user WHERE user = '{user_name}';\""
            result_check = ssh_vm.run(cmd_check)
            allure.attach(result_check, name=f"后端查询已删除用户 {user_name}",
                          attachment_type=allure.attachment_type.TEXT)
            assert user_name not in result_check, f"用户 {user_name} 在后端删除失败，仍然存在。"
            ssh_vm.close()

    @allure.title("Doris-修改用户密码")
    def test_change_user_password(self, doris_page, doris, ssh_host, ssh_vm):
        """测试修改Doris用户密码，并进行后端验证"""
        instance_name = doris["name"]
        user_name = f"user_{random_string(k=5)}"
        old_password = f"OldPwd@1{random_string(k=5)}"
        new_password = f"NewPwd@1{random_string(k=5)}"
        admin_password = "admin1234@sugon"

        with allure_step_log(f"步骤一：创建测试用户 {user_name}"):
            doris_page.create_user(instance_name, user_name, old_password)
            doris_page.assert_popup_success("操作成功")

        with allure_step_log("步骤二：后端验证：使用旧密码登录成功"):
            fe_node_name = f"{instance_name}_fe_node01"
            fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
            ssh_vm.connect(fe_ip, port=22022, pwd=admin_password)
            cmd_old_pwd = f"mysql -u{user_name} -p'{old_password}' -P9030 -h127.0.0.1 -e 'SELECT 1;'"
            result_old = ssh_vm.run(cmd_old_pwd)
            assert result_old.splitlines()[-1] == "1", "旧密码登录失败"

        with allure_step_log(f"步骤三：修改用户 {user_name} 的密码"):
            doris_page.change_user_password(instance_name, user_name, new_password)

        with allure_step_log("步骤四：验证密码修改成功"):
            doris_page.assert_popup_success("执行成功,若数据未更新请刷新页面")

        with allure_step_log("步骤五：后端验证：新密码登录成功"):
            cmd_new_pwd = f"mysql -u{user_name} -p'{new_password}' -P9030 -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new_pwd)
            assert result_new.splitlines()[-1] == "1", "新密码登录失败"
            ssh_vm.close()

    @allure.title("Doris-批量删除用户")
    def test_batch_delete_users(self, doris_page, doris, ssh_host, ssh_vm):
        """测试批量删除Doris用户，并进行后端验证"""
        instance_name = doris["name"]
        admin_password = "admin1234@sugon"

        # 创建3个测试用户
        users_to_create = []
        for i in range(3):
            user_data = {
                "name": f"batch_user_{random_string(k=4)}",
                "password": f"Pwd@1{random_string(k=5)}"
            }
            users_to_create.append(user_data)

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建3个测试用户"):
            for user in users_to_create:
                doris_page.create_user(instance_name, user["name"], user["password"])
                doris_page.assert_popup_success("操作成功")
                doris_page.assert_list_contain(user["name"], "用户名")

        with allure_step_log("步骤二：批量删除这3个用户"):
            user_names = [user["name"] for user in users_to_create]
            doris_page.batch_delete_users(instance_name, user_names)

        with allure_step_log("步骤三：验证批量删除成功"):
            for user_name in user_names:
                doris_page.assert_deleted(user_name)

        with allure_step_log("步骤四：后端验证：所有用户已删除"):
            fe_node_name = f"{instance_name}_fe_node01"
            fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
            ssh_vm.connect(fe_ip, port=22022, pwd=admin_password)
            for user_name in user_names:
                cmd_check = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"SELECT user FROM mysql.user WHERE user = '{user_name}';\""
                result = ssh_vm.run(cmd_check)
                allure.attach(result, name=f"后端查询已删除用户 {user_name}",
                              attachment_type=allure.attachment_type.TEXT)
                assert user_name not in result, f"用户 {user_name} 在后端批量删除失败，仍然存在。"
            ssh_vm.close()

    @allure.title("Doris-用户授权和解除授权的后端验证")
    def test_authorize_and_deauthorize_user(self, doris_page, doris, ssh_host, ssh_vm):
        """测试用户的各种权限授权及解除授权，并进行完整的后端生效性验证"""
        instance_name = doris["name"]
        user_name = doris["user_name"]
        password = doris["user_password"]
        admin_password = "admin1234@sugon"

        # 使用两个测试数据库
        db_readonly = doris["db_name"]
        db_readwrite = doris["db_name1"]

        # 获取FE节点IP，用于后端验证
        fe_node_name = f"{instance_name}_fe_node01"
        fe_ip = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", fe_node_name)
        ssh_vm.connect(fe_ip, port=22022, pwd=admin_password)

        # 测试1: 对数据库、表的只读权限
        with allure_step_log(f"步骤一：为用户 {user_name} 授予对 {db_readonly} 的只读权限"):
            doris_page.authorize_user(instance_name, user_name, db_readonly, "对数据库、表的只读权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤二：后端确认只读权限生效 - 写入失败，读取成功"):
            # 尝试创建表（应失败）
            cmd_write_fail = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"CREATE TABLE {db_readonly}.test_ro(id int);\""
            result_write_fail = ssh_vm.run(cmd_write_fail, True, True)
            assert "denied" in result_write_fail['stderr'].lower(), "只读用户执行写入操作未按预期失败。"

            # 尝试读取（应成功）
            cmd_read_ok = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"SHOW TABLES FROM {db_readonly};\""
            result_read_ok = ssh_vm.run(cmd_read_ok, True, True)
            assert "error" not in result_read_ok['stderr'].lower(), "只读用户执行读取操作未按预期成功。"

        # 测试2: 对数据库、表的写权限
        with allure_step_log(f"步骤三：为用户 {user_name} 授予对 {db_readwrite} 的写权限"):
            doris_page.authorize_user(instance_name, user_name, db_readwrite, "对数据库、表的写权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤四：后端确认写权限生效 - 可以插入数据"):
            # 先用admin创建表
            cmd_admin_create = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"CREATE TABLE IF NOT EXISTS {db_readwrite}.test_write(id int);\""
            ssh_vm.run(cmd_admin_create)

            # 用户尝试写入数据（应成功）
            cmd_write_ok = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"INSERT INTO {db_readwrite}.test_write VALUES (1);\""
            result_write_ok = ssh_vm.run(cmd_write_ok, True, True)
            assert "error" not in result_write_ok['stderr'].lower(), f"写权限用户执行插入操作失败"

        # 测试3: 对数据库、表的更改权限
        with allure_step_log(f"步骤五：为用户 {user_name} 授予对 {db_readwrite} 的更改权限"):
            doris_page.deauthorize_user(instance_name, user_name, db_readwrite)
            doris_page.assert_popup_success("操作成功")
            doris_page.authorize_user(instance_name, user_name, db_readwrite, "对数据库、表的更改权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤六：后端确认更改权限生效 - 可以修改表结构"):
            # 尝试修改表结构（应成功）
            cmd_alter = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"ALTER TABLE {db_readwrite}.test_write ADD COLUMN name VARCHAR(50);\""
            result_alter = ssh_vm.run(cmd_alter, True, True)
            assert "error" not in result_alter['stderr'].lower(), "更改权限用户执行ALTER操作失败"

        # 测试4: 创建数据库、表的权限
        with allure_step_log(f"步骤七：为用户 {user_name} 授予对 {db_readwrite} 的创建权限"):
            doris_page.deauthorize_user(instance_name, user_name, db_readwrite)
            doris_page.assert_popup_success("操作成功")
            doris_page.authorize_user(instance_name, user_name, db_readwrite, "创建数据库、表的权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤八：后端确认创建权限生效 - 可以创建表"):
            # 尝试创建新表（应成功）
            cmd_create = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"CREATE TABLE {db_readwrite}.test_create(id int);\""
            result_create = ssh_vm.run(cmd_create, True, True)
            assert "error" not in result_create['stderr'].lower(), "创建权限用户执行CREATE TABLE操作失败"

        # 测试5: 删除对数据库、表的权限
        with allure_step_log(f"步骤九：为用户 {user_name} 授予对 {db_readwrite} 的删除权限"):
            doris_page.deauthorize_user(instance_name, user_name, db_readwrite)
            doris_page.assert_popup_success("操作成功")
            doris_page.authorize_user(instance_name, user_name, db_readwrite, "删除对数据库、表的权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤十：后端确认删除权限生效 - 可以删除表"):
            # 尝试删除表（应成功）
            cmd_drop = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"DROP TABLE IF EXISTS {db_readwrite}.test_create;\""
            result_drop = ssh_vm.run(cmd_drop, True, True)
            assert "error" not in result_drop['stderr'].lower(), "删除权限用户执行DROP TABLE操作失败"

        # 测试6: 执行 SHOW CREATE VIEW 的权限
        with allure_step_log(f"步骤十一：为用户 {user_name} 授予对 {db_readwrite} 的 SHOW CREATE VIEW 权限"):
            doris_page.deauthorize_user(instance_name, user_name, db_readwrite)
            doris_page.assert_popup_success("操作成功")
            doris_page.authorize_user(instance_name, user_name, db_readwrite, "执行 SHOW CREATE VIEW 的权限")
            doris_page.assert_popup_success("操作成功,若数据未更新请刷新页面")

        with allure_step_log("步骤十二：后端确认 SHOW CREATE VIEW 权限已授予"):
            # 先用admin创建一个视图
            cmd_admin_view = f"mysql -uadmin -p'{admin_password}' -P9030 -h127.0.0.1 -e \"CREATE TABLE IF NOT EXISTS {db_readwrite}.base_table(id int); CREATE VIEW IF NOT EXISTS {db_readwrite}.test_view AS SELECT * FROM {db_readwrite}.base_table;\""
            ssh_vm.run(cmd_admin_view, True, True)

            # 用户尝试执行SHOW CREATE VIEW（应成功）
            cmd_show_view = f"mysql -u{user_name} -p'{password}' -P9030 -h127.0.0.1 -e \"SHOW CREATE VIEW {db_readwrite}.test_view;\""
            result_show_view = ssh_vm.run(cmd_show_view, True, True)
            assert "error" not in result_show_view['stderr'].lower(), "SHOW CREATE VIEW 权限用户执行操作失败"

        ssh_vm.close()

    @allure.title("Doris-开启和关闭审计日志")
    def test_toggle_audit_log(self, doris_page, doris):
        """测试为Doris实例开启和关闭审计日志功能"""
        instance_name = doris["name"]

        with allure_step_log(f"步骤一：为实例 {instance_name} 开启审计日志"):
            doris_page.enable_audit_log(instance_name)

        with allure_step_log("步骤二：验证开启结果"):
            doris_page.assert_popup_success("开启doris审计日志成功")

        with allure_step_log(f"步骤三：为实例 {instance_name} 关闭审计日志"):
            doris_page.disable_audit_log(instance_name)

        with allure_step_log("步骤四：验证关闭结果"):
            doris_page.assert_popup_success("关闭doris审计日志成功")

    @allure.title("Doris-白名单管理")
    def test_whitelist_management(self, doris_page, doris):
        """测试白名单的添加、删除、批量删除和重置功能"""
        instance_name = doris["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24"
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log(f"步骤一：重置白名单，确保环境干净"):
            doris_page.reset_whitelist(instance_name)
            doris_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            doris_page.add_whitelist(instance_name, ip_single)
            doris_page.assert_popup_success("创建白名单成功")
            doris_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            doris_page.delete_whitelist(instance_name, ip_single)
            doris_page.assert_popup_success("删除白名单成功")

        with allure_step_log(f"步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                doris_page.add_whitelist(instance_name, ip)
                doris_page.assert_popup_success("创建白名单成功")
            for ip in ip_batch:
                doris_page.assert_list_contain(ip, "白名单", exact_match=False)

            doris_page.batch_delete_whitelist(instance_name, ip_batch)
            doris_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            # 先添加一个，确保有内容可重置
            doris_page.add_whitelist(instance_name, ip_single)
            doris_page.assert_popup_success("创建白名单成功")
            doris_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            # 执行重置
            doris_page.reset_whitelist(instance_name)
            doris_page.assert_popup_success("重置白名单成功")

    @allure.title("Doris-编辑FE和BE参数")
    def test_edit_fe_and_be_parameters(self, doris_page, doris):
        """测试编辑Doris实例的FE和BE节点参数"""
        instance_name = doris["name"]
        fe_param_name = "table_name_length_limit"
        fe_param_value = "127"
        be_param_name = "doris_scanner_thread_pool_thread_num"
        be_param_value = "47"

        with allure_step_log(f"步骤一：编辑FE参数 {fe_param_name} 值为 {fe_param_value}"):
            doris_page.edit_fe_parameter(instance_name, fe_param_name, fe_param_value)

        with allure_step_log("步骤二：验证FE参数编辑结果"):
            doris_page.assert_popup_success("执行成功")
            doris_page.assert_list_contain("127", "运行值", exact_match=True)

        with allure_step_log(f"步骤三：编辑BE参数 {be_param_name} 值为 {be_param_value}"):
            doris_page.edit_be_parameter(instance_name, be_param_name, be_param_value)
            doris_page.assert_list_contain("47", "运行值", exact_match=True)

        with allure_step_log("步骤四：验证BE参数编辑结果"):
            doris_page.assert_popup_success("执行成功")

    @allure.title("Doris-参数设置页搜索")
    def test_parameter_search(self, doris_page, doris):
        """测试实例参数设置页的搜索功能"""
        instance_name = doris["name"]
        param_keyword = "table_name"

        with allure_step_log("步骤一：输入参数名称进行搜索"):
            doris_page.goto_submenu("实例管理")
            doris_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            sleep(2)
            doris_page.get_by_role("tab", name="参数设置").click()
            sleep(3)
            keyword = param_keyword
            doris_page.search(keyword)
            doris_page.assert_list_contain(keyword, "参数名称", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            doris_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert doris_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
