from time import sleep
import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, random_string


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for PostgreSQL)')
class TestPgSQLBasic:

    @allure.title("PostgreSQL-升级实例")
    def test_upgrade_instance(self, pgsql_page, pgsql, ssh_host):
        """测试PostgreSQL实例从单机升级到高可用，再升级到集群"""
        instance_name = pgsql["name"]

        # --- 第一阶段：单机 -> 高可用 ---
        with allure_step_log("步骤一：执行升级操作（单机 -> 高可用）"):
            pgsql_page.upgrade_instance(instance_name, target_type="高可用")
            pgsql_page.assert_popup_success("升级", timeout=10)

        with allure_step_log("步骤二：验证升级过程及结果（单机 -> 高可用）"):
            # 验证状态变为升级中
            pgsql_page.assert_status(instance_name, status="升级中", timeout=1200, refresh=True)
            # 验证最终状态变为运行中
            pgsql_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)
            # 验证节点状态变为运行中
            pgsql_page.locator(f"#cloud-container-content").get_by_text(instance_name).first.click()
            sleep(3)
            pgsql_page.assert_status(f"{instance_name}-1", status="运行中", timeout=1200, refresh=True)
            # 后端验证：检查新节点是否已创建
            ssh_host.assert_resource_created(f"{instance_name}-1")

        # --- 第二阶段：高可用 -> 集群 ---
        with allure_step_log("步骤三：执行升级操作（高可用 -> 集群）"):
            pgsql_page.upgrade_instance(instance_name, target_type="集群")
            pgsql_page.assert_popup_success("升级", timeout=10)

        with allure_step_log("步骤四：验证升级过程及结果（高可用 -> 集群）"):
            # 验证状态变为升级中
            pgsql_page.assert_status(instance_name, status="升级中", timeout=1200, refresh=True)
            # 验证最终状态变为运行中
            pgsql_page.assert_status(instance_name, status="运行中", timeout=1800, refresh=True)
            # 验证节点状态变为运行中
            pgsql_page.locator(f"#cloud-container-content").get_by_text(instance_name).first.click()
            sleep(3)
            pgsql_page.assert_status(f"{instance_name}-2", status="运行中", timeout=1200, refresh=True)

            # 后端验证：检查新节点是否已创建
            ssh_host.assert_resource_created(f"{instance_name}-2")

    @allure.title("PostgreSQL-重命名实例")
    def test_rename_instance(self, pgsql_page, pgsql):
        """测试重命名PostgreSQL实例"""
        instance_name = pgsql["name"]
        renamed_name = f"pgsql-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            pgsql_page.rename_instance(instance_name, renamed_name)
        with allure_step_log("步骤二：验证重命名结果"):
            pgsql_page.assert_popup_success("修改实例名称成功")
            pgsql_page.assert_list_contain(renamed_name)
            pgsql_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：重命名实例回退"):
            pgsql_page.rename_instance(renamed_name, instance_name)
        with allure_step_log("步骤四：验证重命名回退结果"):
            pgsql_page.assert_popup_success("修改实例名称成功")
            pgsql_page.assert_list_contain(instance_name)
            pgsql_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("PostgreSQL-修改实例管理员密码")
    def test_change_root_password(self, pgsql_page, pgsql, ssh_host, ssh_vm):
        """测试修改PostgreSQL实例的管理员密码"""
        instance_name = pgsql["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：修改管理员密码"):
            pgsql_page.change_root_password(instance_name, new_password)
        with allure_step_log("步骤二：验证修改密码结果"):
            pgsql_page.assert_popup_success("执行成功", timeout=10)
            pgsql_page.assert_status(instance_name, status="运行中", timeout=300, refresh=True)

        with allure_step_log("步骤三：验证新密码生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = ssh_host.get_node_mfip("sugoncloud_pgsql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            # 验证新密码可以成功登录
            cmd_new = f"PGPASSWORD='{new_password}' psql -U postgres -h127.0.0.1 -c 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new)
            assert "1 row" in result_new or "(1 row)" in result_new
            pgsql["admin_password"] = new_password

    @allure.title("PostgreSQL-修改云盘大小")
    def test_change_disk_size(self, pgsql_page, pgsql, ssh_host):
        """测试调整PostgreSQL实例的云盘大小"""
        instance_name = pgsql["name"]
        new_disk_size = 66

        with allure_step_log(f"步骤一：调整实例 {instance_name} 的磁盘大小为 {new_disk_size}GB"):
            pgsql_page.change_disk_size(instance_name, new_disk_size)

        with allure_step_log("步骤二：验证调整结果"):
            node_name = f"{instance_name}-0"
            pgsql_page.assert_popup_success("执行成功")
            pgsql_page.assert_status(node_name, status="调整云硬盘中", timeout=1200, refresh=True)
            pgsql_page.assert_status(node_name, status="运行中", timeout=500, refresh=True)
            assert ssh_host.get_volume_size(node_name) == new_disk_size

    @allure.title("PostgreSQL-修改实例规格")
    def test_change_specification(self, pgsql_page, pgsql, ssh_host):
        """测试修改PostgreSQL实例的规格"""
        instance_name = pgsql["name"]
        specification_name = "云数据库标准型 postgresql.d6.xlarge 4核"
        real_specification = "postgresql.d6.xlarge"

        with allure_step_log("步骤一：执行修改规格操作"):
            pgsql_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格是否修改成功"):
            node_name = f"{instance_name}-0"
            pgsql_page.assert_popup_success("执行成功")
            pgsql_page.assert_status(node_name, status="调整规格中", timeout=1200, refresh=True)
            pgsql_page.assert_status(node_name, status="运行中", timeout=5000, refresh=True)
            assert ssh_host.guest_show(node_name).get("flavor_name") == real_specification

    @allure.title("PostgreSQL-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, pgsql_page, pgsql, ssh_host):
        """测试实例绑定和解绑PostgreSQL实例的公网IP"""
        instance_name = pgsql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = pgsql_page.instance_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            pgsql_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            pgsql_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            pgsql_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("PostgreSQL-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, pgsql_page, pgsql, ssh_host):
        """测试节点绑定和解绑PostgreSQL实例的公网IP"""
        instance_name = pgsql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = pgsql_page.node_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            pgsql_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：解绑公网IP"):
            pgsql_page.node_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            pgsql_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("PostgreSQL-添加只读节点")
    def test_add_readonly_node(self, pgsql_page, pgsql, ssh_host):
        """测试为PostgreSQL实例添加只读节点"""
        instance_name = pgsql["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页并点击新建只读节点"):
            pgsql_page.add_node(instance_name)
            pgsql_page.assert_popup_success("添加只读节点")

        with allure_step_log("步骤二：验证节点状态变化"):
            new_node_name = f"{instance_name}-3"
            pgsql_page.assert_status(new_node_name, status="创建中", timeout=1200, refresh=True)
            pgsql_page.assert_status(new_node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：后端验证节点存在"):
            ssh_host.assert_resource_created(new_node_name)

    @allure.title("PostgreSQL-创建用户")
    def test_create_user(self, pgsql_page, pgsql):
        """测试创建用户并授权"""
        instance_name = pgsql["name"]
        user_name = f"testuser_{random_string(k=5)}"
        user_password = f"sugon1234@{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建用户 {user_name}"):
            pgsql_page.create_user(instance_name, user_name, user_password)

        with allure_step_log("步骤二：验证创建结果"):
            pgsql_page.assert_popup_success("创建用户成功", 10)
            pgsql_page.assert_list_contain(user_name, "用户名")

        with allure_step_log("步骤三：清理-删除用户"):
            pgsql_page.delete_user(instance_name, user_name)
            pgsql_page.assert_deleted(user_name)

    @allure.title("PostgreSQL-修改用户密码")
    def test_change_user_password(self, pgsql_page, pgsql):
        """测试修改用户密码"""
        instance_name = pgsql["name"]
        user_name = pgsql["user_name"]
        new_password = f"NewPass@{random_string(k=6)}"

        with allure_step_log("步骤一：修改用户密码"):
            pgsql_page.change_user_privileges(instance_name, user_name, new_password)

        with allure_step_log("步骤二：验证修改结果"):
            pgsql_page.assert_popup_success("更新用户成功")
            pgsql["user_password"] = new_password

    @allure.title("PostgreSQL-批量删除用户")
    def test_batch_delete_users(self, pgsql_page, pgsql):
        """测试批量删除用户"""
        instance_name = pgsql["name"]
        user_names = [f"testuser_{random_string(k=5)}", f"testuser_{random_string(k=5)}"]
        user_password = f"sugon1234@{random_string(k=5)}"
        user_to_delete_single = user_names[0]
        with allure_step_log("步骤一：创建多个用户"):
            for user_name in user_names:
                pgsql_page.create_user(instance_name, user_name, user_password)
                pgsql_page.assert_popup_success("创建用户成功", 10)

        with allure_step_log("步骤二：批量删除用户"):
            pgsql_page.batch_delete_users(instance_name, user_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            pgsql_page.assert_deleted(user_to_delete_single)

    @allure.title("PostgreSQL-白名单管理")
    def test_whitelist_management(self, pgsql_page, pgsql):
        """测试白名单的添加、删除、批量删除和重置功能"""
        instance_name = pgsql["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24"
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log(f"步骤一：重置白名单，确保环境干净"):
            pgsql_page.reset_whitelist(instance_name)
            pgsql_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            pgsql_page.add_whitelist(instance_name, ip_single)
            pgsql_page.assert_popup_success("添加白名单成功")
            pgsql_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            pgsql_page.delete_whitelist(instance_name, ip_single)
            pgsql_page.assert_popup_success("删除白名单成功")

        with allure_step_log(f"步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                pgsql_page.add_whitelist(instance_name, ip)
                pgsql_page.assert_popup_success("添加白名单成功")
            for ip in ip_batch:
                pgsql_page.assert_list_contain(ip, "白名单", exact_match=False)

            pgsql_page.batch_delete_whitelist(instance_name, ip_batch)
            pgsql_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            # 先添加一个，确保有内容可重置
            pgsql_page.add_whitelist(instance_name, ip_single)
            pgsql_page.assert_popup_success("添加白名单成功")
            pgsql_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            # 执行重置
            pgsql_page.reset_whitelist(instance_name)
            pgsql_page.assert_popup_success("重置白名单成功")

    @allure.title("PostgreSQL-修改实例参数")
    def test_edit_instance_parameter(self, pgsql_page, pgsql):
        """测试修改实例参数"""
        instance_name = pgsql["name"]
        param_name = "archive_timeout"
        param_value = "299"

        with allure_step_log(f"步骤一：修改参数 {param_name} 为 {param_value}"):
            pgsql_page.edit_instance_parameter(instance_name, param_name, param_value)

        with allure_step_log("步骤二：验证修改结果"):
            pgsql_page.assert_popup_success("修改实例参数成功")

    @allure.title("PostgreSQL-实例管理列表页搜索")
    def test_instance_search(self, pgsql_page, pgsql):
        """测试实例管理列表页的搜索功能"""
        instance_name = pgsql["name"]

        with allure_step_log("步骤一：输入实例名称进行搜索"):
            pgsql_page.goto_submenu("实例管理")
            keyword = instance_name[:-2]
            pgsql_page.search(keyword)
            pgsql_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            pgsql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert pgsql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("PostgreSQL-用户列表页搜索")
    def test_user_search(self, pgsql_page, pgsql):
        """测试用户列表页的搜索功能"""
        instance_name = pgsql["name"]
        user_name = pgsql["user_name"]

        with allure_step_log("步骤一：输入用户名称进行搜索"):
            pgsql_page.goto_submenu("实例管理")
            pgsql_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            pgsql_page.get_by_role("tab", name="用户").click()
            keyword = user_name[:-2]
            pgsql_page.search(keyword)
            pgsql_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            pgsql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert pgsql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("PostgreSQL-实例参数设置页搜索")
    def test_instance_parameter_search(self, pgsql_page, pgsql):
        """测试实例参数设置页的搜索功能"""
        instance_name = pgsql["name"]
        param_keyword = "archive"

        with allure_step_log("步骤一：输入参数名称进行搜索"):
            pgsql_page.goto_submenu("实例管理")
            pgsql_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            sleep(2)
            pgsql_page.get_by_role("tab", name="参数设置").click()
            sleep(2)
            pgsql_page.search(param_keyword)
            pgsql_page.assert_list_contain(param_keyword, "参数名称", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            pgsql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            # 断言搜索输入框已清空
            assert pgsql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("PostgreSQL-节点热迁移")
    def test_pgsql_node_hot_migration(self, pgsql_page, pgsql, ssh_host, ssh_vm):
        """测试PostgreSQL节点的热迁移功能"""
        instance_name = pgsql["name"]
        node_name = f"{instance_name}-0"
        password = "admin1234@sugon"
        admin_password = pgsql["admin_password"]

        # 记录迁移前的物理机 (后端校验)
        old_host = ssh_host.guest_show(node_name).get("node")
        allure.attach(f"迁移前物理机 (后端): {old_host}", name="迁移前状态")

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            selected_host = pgsql_page.pgsql_hot_migration(instance_name, node_name)

        with allure_step_log("步骤二：验证迁移结果"):
            pgsql_page.assert_popup_success("热迁移命令下发成功")
            pgsql_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            pgsql_page.assert_status(node_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log("步骤三：验证物理机节点变更 (后端校验)"):
            # 热迁移后，通过后端 gova list 命令验证节点是否真正切换
            new_host = ssh_host.guest_show(node_name).get("node")
            allure.attach(f"迁移后物理机 (后端): {new_host}", name="迁移后状态")

            assert new_host != old_host, f"热迁移失败，后端查询迁移前后物理机节点未变更: {old_host}"
            if selected_host:
                # selected_host 是 UI 上选中的名称，后端返回的可能带域名，所以用 in 判断
                assert selected_host in new_host, f"热迁移失败，期望迁移至节点:{selected_host},实际迁移至节点:{new_host}"

        with allure_step_log("步骤四：验证迁移后数据库连接"):
            ip_from_db = ssh_host.get_node_mfip("sugoncloud_pgsql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=password)
            cmd_check = f"PGPASSWORD='{admin_password}' psql -U postgres -h127.0.0.1 -c 'SELECT 1;'"
            result = ssh_vm.run(cmd_check)
            assert "1 row" in result or "(1 row)" in result, f"热迁移后数据库连接失败: {result}"
            ssh_vm.close()
