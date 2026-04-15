import re
import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string
from sugon_web.utils import db_util

NODE_TYPES = ["元数据节点", "日志节点", "计算节点", "存储节点"]


def _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm):
    """连接 XScale 计算节点，用于后端数据库校验。"""
    node_name = f"{instance_name}-cn-0"
    ip_from_db = db_util.get_node_mfip_from_db(
        xscale_page,
        ssh_host,
        "sugoncloud_xscale",
        node_name,
        table_name="xscale_instance_node",
    )
    ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")


def _build_xscale_mysql_cmd(admin_password, sql):
    """构造 XScale 管理员执行 SQL 的命令。"""
    return f"/anhandbx/anhandbx-engine/bin/mysql -uadmin -P8527 -p'{admin_password}' -h127.0.0.1 -e \"{sql}\""


def _build_xscale_gova_name(node_name: str) -> str:
    """将前端节点名转换为 gova 中的 XScale 节点命名。"""
    mapping = {
        "-cn-": "-CN-",
        "-dn-": "-DN-",
        "-gms-": "-GMS-",
        "-cdc-": "-CDC-",
    }
    result = node_name
    for old, new in mapping.items():
        result = result.replace(old, new)
    return result


@allure.epic("数据库服务")
@allure.feature("AnhanDB-XScale")
class TestXScaleBasic:

    @allure.title("XScale-重命名实例")
    def test_rename_instance(self, xscale_page, xscale):
        """测试重命名XScale实例"""
        instance_name = xscale["name"]
        renamed_name = f"xscale-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            xscale_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证重命名结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(renamed_name)
            xscale_page.assert_status(renamed_name, status="就绪")

        with allure_step_log("步骤三：重命名实例回退"):
            xscale_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证重命名回退结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(instance_name)
            xscale_page.assert_status(instance_name, status="就绪")

    @allure.title("XScale-重启实例")
    def test_restart_instance(self, xscale_page, xscale):
        """测试重启XScale实例"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：重启实例"):
            xscale_page.restart_instance(instance_name)

        with allure_step_log("步骤二：验证重启结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(instance_name, status="重启中")
            xscale_page.assert_status(instance_name, status="就绪")

    @allure.title("XScale-修改管理员密码")
    def test_change_admin_password(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试修改XScale实例管理员密码"""
        instance_name = xscale["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：修改管理员密码"):
            xscale_page.change_admin_password(instance_name, new_password)

        with allure_step_log("步骤二：验证密码修改结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(instance_name, status="就绪")

        with allure_step_log("步骤三：验证新密码生效"):
            node_name = f"{instance_name}-cn-0"
            ip_from_db = db_util.get_node_mfip_from_db(xscale_page, ssh_host, "sugoncloud_xscale", node_name, table_name="xscale_instance_node")
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            # 验证新密码可以成功登录
            cmd_new = f"/anhandbx/anhandbx-engine/bin/mysql -uadmin -P8527 -p'{new_password}' -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new)
            assert result_new.splitlines()[-1] == "1"
            xscale["admin_password"] = new_password

    @allure.title("XScale-状态重置")
    def test_reset_instance_status(self, xscale_page, xscale):
        """测试重置XScale实例状态"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：检查实例是否满足状态重置条件"):
            row_data = xscale_page.get_row_data(instance_name)
            current_status = row_data.get("状态", "")
            if current_status not in ["不可用", "警告"]:
                pytest.skip(f"当前实例状态为“{current_status}”，不满足状态重置前置条件。")

        with allure_step_log("步骤二：执行状态重置"):
            xscale_page.reset_instance_status(instance_name)

        with allure_step_log("步骤三：验证状态重置结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(instance_name, status="就绪")

    @allure.title("XScale-JDBC连接串")
    def test_jdbc_connection_string(self, xscale_page, xscale):
        """测试查看XScale实例JDBC连接串"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：打开JDBC连接串弹窗"):
            jdbc = xscale_page.get_jdbc_connection_string(instance_name)

        with allure_step_log("步骤二：验证JDBC连接串内容"):
            assert jdbc.startswith("jdbc:mysql:loadbalance://"), f"JDBC连接串格式错误: {jdbc}"
            assert "readOnlyPropagatesToServer=false" in jdbc
            assert "useSSL=false" in jdbc
            assert re.search(r":\d+/", jdbc), f"JDBC连接串中未找到端口信息: {jdbc}"

        with allure_step_log("步骤三：关闭JDBC连接串弹窗"):
            xscale_page.close_jdbc_dialog()

    @allure.title("XScale-{node_type}-修改规格")
    @pytest.mark.parametrize("node_type", NODE_TYPES, ids=NODE_TYPES)
    def test_change_node_specification(self, xscale_page, xscale, ssh_host, node_type):
        instance_name = xscale["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页，获取{node_type}列表第一条节点并执行修改规格"):
            node_name, target_spec = xscale_page.change_node_specification(instance_name, node_type=node_type)

        with allure_step_log("步骤二：验证修改规格任务下发成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(node_name, status="就绪")

        with allure_step_log("步骤三：验证节点规格已更新"):
            backend_spec = db_util.get_specification(xscale_page, node_name, ssh_host)
            assert target_spec in backend_spec or backend_spec in target_spec, (
                f"节点规格校验失败，期望规格: {target_spec}，实际规格: {backend_spec}"
            )

    @allure.title("XScale-{node_type}-修改云硬盘大小")
    @pytest.mark.parametrize("node_type", NODE_TYPES, ids=NODE_TYPES)
    def test_change_node_disk_size(self, xscale_page, xscale, ssh_host, node_type):
        instance_name = xscale["name"]
        new_size = 110

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页，获取{node_type}列表第一条节点并调整云硬盘到 {new_size}GiB"):
            node_name = xscale_page.change_node_disk_size(instance_name, new_size, node_type=node_type)

        with allure_step_log("步骤二：验证调整云硬盘任务下发成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(node_name, status="调整云硬盘中")
            xscale_page.assert_status(node_name, status="就绪")

        with allure_step_log("步骤三：验证节点云硬盘大小已更新"):
            assert db_util.get_disk_size(xscale_page, node_name, ssh_host) == new_size

    @allure.title("XScale-{node_type}-绑定和解绑公网IP")
    @pytest.mark.parametrize("node_type", NODE_TYPES, ids=NODE_TYPES)
    def test_node_bind_and_unbind_public_ip(self, xscale_page, xscale, ssh_host, node_type):
        instance_name = xscale["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页，获取{node_type}列表第一条节点并绑定公网IP"):
            node_name, ip = xscale_page.node_ip_binding(instance_name, node_type=node_type)

        with allure_step_log("步骤二：验证公网IP绑定成功"):
            xscale_page.assert_popup_success()
            ssh_host.ping(ip)

        with allure_step_log("步骤三：执行解绑公网IP"):
            xscale_page.node_ip_unbinding(instance_name, node_type=node_type)

        with allure_step_log("步骤四：验证公网IP解绑成功"):
            xscale_page.assert_popup_success()
            ssh_host.ping(ip, connected=False)

    @allure.title("XScale-{node_type}-重启节点")
    @pytest.mark.parametrize("node_type", NODE_TYPES, ids=NODE_TYPES)
    def test_restart_node(self, xscale_page, xscale, node_type):
        instance_name = xscale["name"]

        with allure_step_log(f"步骤一：进入实例 {instance_name} 详情页，获取{node_type}列表第一条节点并执行重启"):
            node_name = xscale_page.restart_node(instance_name, node_type=node_type)

        with allure_step_log("步骤二：验证节点重启结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(node_name, status="节点重启中")
            xscale_page.assert_status(node_name, status="就绪")

    @allure.title("XScale-{node_type}-热迁移")
    @pytest.mark.parametrize("node_type", NODE_TYPES, ids=NODE_TYPES)
    def test_hot_migration_node(self, xscale_page, xscale, ssh_host, node_type):
        instance_name = xscale["name"]
        xscale_page.goto_detail_page(instance_name)
        node_name = xscale_page.get_first_node_name_by_type(instance_name, node_type)

        with allure_step_log("步骤一：记录迁移前节点所在物理机"):
            old_host = db_util.get_backend_host(xscale_page, ssh_host, node_name)

        with allure_step_log(f"步骤二：进入实例 {instance_name} 详情页，获取{node_type}列表第一条节点并执行热迁移"):
            node_name, selected_host = xscale_page.hot_migration_node(instance_name, node_type=node_type)

        with allure_step_log("步骤三：验证热迁移任务下发成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(node_name, status="迁移中")
            xscale_page.assert_status(node_name, status="就绪")

        with allure_step_log("步骤四：验证节点实际迁移到了新的物理机"):
            new_host = db_util.get_backend_host(xscale_page, ssh_host, node_name)
            assert new_host != old_host, f"热迁移前后物理机未变化，迁移前后均为: {old_host}"
            assert selected_host in new_host, f"期望迁移到 {selected_host}，实际迁移到 {new_host}"

    @allure.title("XScale-创建和删除数据库")
    def test_create_and_delete_database(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试在 XScale 实例详情页数据库 Tab 下创建和删除数据库，并验证后端生效与失效。"""
        instance_name = xscale["name"]
        admin_password = xscale["admin_password"]
        db_name = f"autodb_{random_string(k=5)}"

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建数据库 {db_name}"):
            xscale_page.create_database(instance_name, db_name)

        with allure_step_log("步骤二：验证数据库创建成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(db_name)

        with allure_step_log("步骤三：验证新创建的数据库在后端生效"):
            _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm)
            result_exist = ssh_vm.run(_build_xscale_mysql_cmd(admin_password, f"SHOW DATABASES LIKE '{db_name}';"))
            allure.attach(result_exist, name=f"查询数据库 {db_name} 的存在性")
            assert db_name in result_exist, f"在数据库后端未找到新创建的数据库 '{db_name}'。"

        with allure_step_log(f"步骤四：在实例 {instance_name} 下删除数据库 {db_name}"):
            xscale_page.delete_database(instance_name, db_name)

        with allure_step_log("步骤五：验证数据库删除成功"):
            xscale_page.assert_deleted(db_name)

        with allure_step_log("步骤六：验证数据库在后端已失效"):
            result_gone = ssh_vm.run(_build_xscale_mysql_cmd(admin_password, f"SHOW DATABASES LIKE '{db_name}';"))
            allure.attach(result_gone, name=f"再次查询数据库 {db_name} 的存在性")
            assert db_name not in result_gone, f"数据库 '{db_name}' 在后端删除失败，仍然存在。"

        ssh_vm.close()

    @allure.title("XScale-批量创建和删除数据库")
    def test_batch_create_and_delete_databases(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试在 XScale 实例详情页数据库 Tab 下批量创建和删除数据库，并验证后端生效与失效。"""
        instance_name = xscale["name"]
        admin_password = xscale["admin_password"]
        db_names = [f"autodb_batch_{random_string(k=4)}", f"autodb_batch_{random_string(k=4)}"]

        with allure_step_log(f"步骤一：在实例 {instance_name} 下批量创建数据库"):
            for db_name in db_names:
                xscale_page.create_database(instance_name, db_name)
                xscale_page.assert_popup_success()
                xscale_page.assert_list_contain(db_name)

        with allure_step_log("步骤二：验证新创建的数据库均在后端生效"):
            _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm)
            for db_name in db_names:
                result_exist = ssh_vm.run(_build_xscale_mysql_cmd(admin_password, f"SHOW DATABASES LIKE '{db_name}';"))
                allure.attach(result_exist, name=f"查询数据库 {db_name} 的存在性")
                assert db_name in result_exist, f"在数据库后端未找到新创建的数据库 '{db_name}'。"

        with allure_step_log(f"步骤三：在实例 {instance_name} 下批量删除数据库"):
            xscale_page.batch_delete_databases(instance_name, db_names)

        with allure_step_log("步骤四：验证数据库均被删除"):
            for db_name in db_names:
                xscale_page.assert_deleted(db_name)

        with allure_step_log("步骤五：验证数据库在后端均已失效"):
            for db_name in db_names:
                result_gone = ssh_vm.run(_build_xscale_mysql_cmd(admin_password, f"SHOW DATABASES LIKE '{db_name}';"))
                allure.attach(result_gone, name=f"再次查询数据库 {db_name} 的存在性")
                assert db_name not in result_gone, f"数据库 '{db_name}' 在后端删除失败，仍然存在。"

        ssh_vm.close()

    @allure.title("XScale-数据库列表页搜索")
    def test_database_search(self, xscale_page, xscale):
        """测试 XScale 实例详情页数据库 Tab 的搜索功能。"""
        instance_name = xscale["name"]
        db_name = f"autodb_search_{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建测试数据库 {db_name}"):
            xscale_page.create_database(instance_name, db_name)
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(db_name)

        with allure_step_log("步骤二：输入数据库名称进行搜索"):
            keyword = db_name[:-2]
            xscale_page.search(keyword)
            xscale_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            xscale_page.btn_reset.click()
            assert xscale_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log(f"步骤四：删除测试数据库 {db_name}"):
            xscale_page.delete_database(instance_name, db_name)

        with allure_step_log("步骤五：验证测试数据库清理成功"):
            xscale_page.assert_deleted(db_name)

    @allure.title("XScale-创建和修改用户")
    def test_create_and_change_user(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试创建用户、验证其有效性，然后修改密码并验证新旧密码的有效性。"""
        instance_name = xscale["name"]
        db_name = f"autodb_user_{random_string(k=5)}"
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd@1{random_string(k=5)}"
        new_password = f"NewPwd@1{random_string(k=5)}"

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建数据库 {db_name}"):
            xscale_page.create_database(instance_name, db_name)
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(db_name)

        with allure_step_log(f"步骤二：在实例 {instance_name} 中为数据库 {db_name} 创建用户 {user_name}"):
            xscale_page.create_user(instance_name, user_name, password, db_name, "读写")

        with allure_step_log("步骤三：验证用户是否创建成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(user_name, "用户名")

        with allure_step_log(f"步骤四：后端验证：使用初始密码登录用户 {user_name}"):
            _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm)
            cmd_login_initial = f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' -h127.0.0.1 -e 'SELECT 1;'"
            result = ssh_vm.run(cmd_login_initial)
            assert result.splitlines()[-1] == "1"

        with allure_step_log(f"步骤五：修改用户 {user_name} 的密码"):
            xscale_page.change_user_privileges(instance_name, user_name, new_password)

        with allure_step_log("步骤六：确认密码修改成功"):
            xscale_page.assert_popup_success()

        with allure_step_log("步骤七：后端验证：确认新密码生效"):
            cmd_new_pwd = f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{new_password}' -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new_pwd)
            assert result_new.splitlines()[-1] == "1"
            ssh_vm.close()

        with allure_step_log(f"步骤八：清理用户 {user_name} 和数据库 {db_name}"):
            xscale_page.delete_user(instance_name, user_name)
            xscale_page.assert_deleted(user_name)
            xscale_page.delete_database(instance_name, db_name)
            xscale_page.assert_deleted(db_name)

    @allure.title("XScale-删除和批量删除用户")
    def test_delete_and_batch_delete_users(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试用户的单个删除和批量删除功能，并进行后端验证。"""
        instance_name = xscale["name"]
        admin_password = xscale["admin_password"]
        db_name = f"autodb_del_{random_string(k=5)}"
        users_to_create = [f"del_user_{random_string(k=4)}" for _ in range(3)]
        user_to_delete_single = users_to_create[0]
        users_to_delete_batch = users_to_create[1:]

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建数据库 {db_name}"):
            xscale_page.create_database(instance_name, db_name)
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(db_name)

        with allure_step_log(f"步骤二：在实例 {instance_name} 下创建 3 个测试用户"):
            for user in users_to_create:
                xscale_page.create_user(instance_name, user, f"Pwd@1{random_string(k=5)}", db_name, "只读")
                xscale_page.assert_popup_success()
                xscale_page.assert_list_contain(user, "用户名")

        with allure_step_log(f"步骤三：删除单个用户 {user_to_delete_single}"):
            xscale_page.delete_user(instance_name, user_to_delete_single)

        with allure_step_log("步骤四：确认单个用户已删除"):
            xscale_page.assert_deleted(user_to_delete_single)
            _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm)
            cmd_check_single = _build_xscale_mysql_cmd(
                admin_password,
                f"SELECT user FROM mysql.user WHERE user = '{user_to_delete_single}';",
            )
            result_single = ssh_vm.run(cmd_check_single)
            allure.attach(result_single, name=f"后端查询已删除用户 {user_to_delete_single}")
            assert user_to_delete_single not in result_single, f"用户 {user_to_delete_single} 在后端删除失败，仍然存在。"

        with allure_step_log(f"步骤五：批量删除用户 {', '.join(users_to_delete_batch)}"):
            xscale_page.batch_delete_users(instance_name, users_to_delete_batch)

        with allure_step_log("步骤六：确认批量用户已删除"):
            for user in users_to_delete_batch:
                xscale_page.assert_deleted(user)
                cmd_check_batch = _build_xscale_mysql_cmd(admin_password, f"SELECT user FROM mysql.user WHERE user = '{user}';")
                result_batch = ssh_vm.run(cmd_check_batch)
                allure.attach(result_batch, name=f"后端查询已删除用户 {user}")
                assert user not in result_batch, f"用户 {user} 在后端批量删除失败，仍然存在。"
            ssh_vm.close()

        with allure_step_log(f"步骤七：清理数据库 {db_name}"):
            xscale_page.delete_database(instance_name, db_name)
            xscale_page.assert_deleted(db_name)

    @allure.title("XScale-用户授权和解除授权的后端验证")
    def test_authorize_and_deauthorize_user(self, xscale_page, xscale, ssh_host, ssh_vm):
        """测试用户的只读、读写权限授权及解除授权，并进行完整的后端生效性验证。"""
        instance_name = xscale["name"]
        seed_db = f"autodb_seed_{random_string(k=4)}"
        db_readonly = f"autodb_ro_{random_string(k=4)}"
        db_readwrite = f"autodb_rw_{random_string(k=4)}"
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd@1{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建测试数据库 {seed_db}、{db_readonly} 和 {db_readwrite}"):
            for db_name in [seed_db, db_readonly, db_readwrite]:
                xscale_page.create_database(instance_name, db_name)
                xscale_page.assert_popup_success()
                xscale_page.search(db_name)
                xscale_page.assert_list_contain(db_name)

        with allure_step_log(f"步骤二：创建测试用户 {user_name}"):
            xscale_page.create_user(instance_name, user_name, password, seed_db, "只读")
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(user_name, "用户名")

        with allure_step_log(f"步骤三：为用户 {user_name} 授予对 {db_readonly} 的只读权限"):
            xscale_page.authorize_user(instance_name, user_name, db_readonly, "只读")
            xscale_page.assert_popup_success("执行成功,若数据未更新请刷新页面")

        with allure_step_log("步骤四：后端确认只读权限生效"):
            _connect_xscale_backend(xscale_page, instance_name, ssh_host, ssh_vm)
            cmd_write_fail = f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' -h127.0.0.1 -e \"CREATE TABLE {db_readonly}.test(id int);\""
            result_write_fail = ssh_vm.run(cmd_write_fail, True, True)
            assert "does not have 'CREATE' privilege" in result_write_fail["stderr"], "只读用户执行写入操作未按预期失败。"

            cmd_read_ok = f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' -h127.0.0.1 -e \"SELECT 1;\""
            result_read_ok = ssh_vm.run(cmd_read_ok)
            assert result_read_ok.splitlines()[-1] == "1", "只读用户执行读取操作未按预期成功。"

        with allure_step_log(f"步骤五：为用户 {user_name} 授予对 {db_readwrite} 的读写权限"):
            xscale_page.authorize_user(instance_name, user_name, db_readwrite, "读写")
            xscale_page.assert_popup_success("执行成功,若数据未更新请刷新页面")

        with allure_step_log("步骤六：后端确认读写权限生效"):
            cmd_write_ok = (
                f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' -h127.0.0.1 "
                f"-e \"CREATE TABLE {db_readwrite}.test(id int); INSERT INTO {db_readwrite}.test VALUES (1);\""
            )
            result_write_ok = ssh_vm.run(cmd_write_ok, True, True)
            assert "ERROR" not in result_write_ok["stderr"], f"读写用户执行写入操作失败: {result_write_ok}"

            cmd_read_write_ok = f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' -h127.0.0.1 -e \"SELECT * FROM {db_readwrite}.test;\""
            result_read_write_ok = ssh_vm.run(cmd_read_write_ok)
            assert result_read_write_ok.splitlines()[-1] == "1", "读写用户执行读取操作未能查到刚写入的数据。"

        with allure_step_log(f"步骤七：解除用户 {user_name} 对 {db_readonly} 和 {db_readwrite} 的权限"):
            xscale_page.deauthorize_user(instance_name, user_name, db_readonly)
            xscale_page.assert_popup_success()
            xscale_page.deauthorize_user(instance_name, user_name, db_readwrite)
            xscale_page.assert_popup_success()

        with allure_step_log("步骤八：后端确认用户权限已被解除"):
            cmd_access_denied = (
                f"/anhandbx/anhandbx-engine/bin/mysql -u{user_name} -P8527 -p'{password}' "
                f"-h127.0.0.1 -e \"SELECT * FROM {db_readwrite}.test;\""
            )
            result_access_denied = ssh_vm.run(cmd_access_denied, True, True)
            stderr = result_access_denied["stderr"]
            assert (
                "Access denied" in stderr
                or "does not have 'SELECT' privilege" in stderr
            ), f"访问已解除授权的数据库 {db_readwrite} 时未返回预期错误。实际输出: {stderr}"
            ssh_vm.close()

        with allure_step_log(f"步骤九：清理用户 {user_name} 和测试数据库"):
            xscale_page.delete_user(instance_name, user_name)
            xscale_page.assert_deleted(user_name)
            for db_name in [seed_db, db_readonly, db_readwrite]:
                xscale_page.delete_database(instance_name, db_name)
                xscale_page.assert_deleted(db_name)

    @allure.title("XScale-用户列表页搜索")
    def test_user_search(self, xscale_page, xscale):
        """测试 XScale 实例详情页用户 Tab 的搜索功能。"""
        instance_name = xscale["name"]
        db_name = f"autodb_user_search_{random_string(k=5)}"
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd@1{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建测试数据库 {db_name} 和测试用户 {user_name}"):
            xscale_page.create_database(instance_name, db_name)
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(db_name)
            xscale_page.create_user(instance_name, user_name, password, db_name, "读写")
            xscale_page.assert_popup_success()
            xscale_page.assert_list_contain(user_name, "用户名")

        with allure_step_log("步骤二：输入用户名称进行搜索"):
            keyword = user_name[:-2]
            xscale_page.search(keyword)
            xscale_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            xscale_page.btn_reset.click()
            assert xscale_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log(f"步骤四：清理测试用户 {user_name} 和数据库 {db_name}"):
            xscale_page.delete_user(instance_name, user_name)
            xscale_page.assert_deleted(user_name)
            xscale_page.delete_database(instance_name, db_name)
            xscale_page.assert_deleted(db_name)

    @allure.title("XScale-开启和关闭慢日志")
    def test_toggle_slow_log(self, xscale_page, xscale):
        """测试为 XScale 实例开启和关闭慢日志功能。"""
        instance_name = xscale["name"]

        with allure_step_log(f"步骤一：为实例 {instance_name} 开启慢日志"):
            xscale_page.enable_slow_log(instance_name)

        with allure_step_log("步骤二：验证开启结果"):
            xscale_page.assert_popup_success("开启慢日志成功")

        with allure_step_log(f"步骤三：为实例 {instance_name} 关闭慢日志"):
            xscale_page.disable_slow_log(instance_name)

        with allure_step_log("步骤四：验证关闭结果"):
            xscale_page.assert_popup_success("关闭慢日志成功")

    @allure.title("XScale-白名单管理")
    def test_whitelist_management(self, xscale_page, xscale):
        """测试白名单的添加、删除、批量删除和重置功能。"""
        instance_name = xscale["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24",
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            xscale_page.reset_whitelist(instance_name)
            xscale_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            xscale_page.add_whitelist(instance_name, ip_single)
            xscale_page.assert_popup_success("创建白名单成功")
            xscale_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            xscale_page.delete_whitelist(instance_name, ip_single)
            xscale_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                xscale_page.add_whitelist(instance_name, ip)
                xscale_page.assert_popup_success("创建白名单成功")
            for ip in ip_batch:
                xscale_page.assert_list_contain(ip, "白名单", exact_match=False)

            xscale_page.batch_delete_whitelist(instance_name, ip_batch)
            xscale_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            xscale_page.add_whitelist(instance_name, ip_single)
            xscale_page.assert_popup_success("创建白名单成功")
            xscale_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            xscale_page.reset_whitelist(instance_name)
            xscale_page.assert_popup_success("重置白名单成功")

    @allure.title("XScale-计算节点扩容与缩容")
    def test_scale_out_and_scale_in_compute_node(self, xscale_page, xscale, ssh_host):
        """测试 XScale 实例详情页计算节点扩容与缩容功能。"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：通过详情页按钮扩容一个计算节点"):
            new_node_name = xscale_page.scale_out_compute_node(instance_name)

        with allure_step_log("步骤二：验证计算节点扩容成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(new_node_name, status="创建中", timeout=600)
            xscale_page.assert_status(new_node_name, status="就绪", timeout=600)
            db_util.assert_backend_created(
                xscale_page,
                ssh_host,
                _build_xscale_gova_name(new_node_name),
                timeout=2400,
            )

        with allure_step_log("步骤三：通过详情页按钮缩容新增的计算节点"):
            deleted_node_name = xscale_page.scale_in_compute_node(instance_name)

        with allure_step_log("步骤四：验证计算节点缩容成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_deleted(deleted_node_name, timeout=2400)
            db_util.assert_backend_deleted(
                xscale_page,
                ssh_host,
                _build_xscale_gova_name(deleted_node_name),
                timeout=2400,
            )

    @allure.title("XScale-重启计算节点")
    def test_restart_compute_nodes(self, xscale_page, xscale):
        """测试 XScale 实例详情页重启计算节点功能。"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：通过详情页按钮重启计算节点"):
            compute_nodes = xscale_page.restart_compute_nodes(instance_name)

        with allure_step_log("步骤二：验证计算节点重启结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(compute_nodes, status="节点重启中")
            xscale_page.assert_status(compute_nodes, status="就绪")

    @allure.title("XScale-存储节点扩容")
    def test_scale_out_storage_node(self, xscale_page, xscale, ssh_host):
        """测试 XScale 实例详情页存储节点扩容功能。"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：通过详情页按钮扩容一个存储节点"):
            new_node_name = xscale_page.scale_out_storage_node(instance_name)

        with allure_step_log("步骤二：验证存储节点扩容成功"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(new_node_name, status="创建中", timeout=600)
            xscale_page.assert_status(new_node_name, status="就绪", timeout=1800)
            db_util.assert_backend_created(
                xscale_page,
                ssh_host,
                _build_xscale_gova_name(new_node_name),
                timeout=2400,
            )

    @allure.title("XScale-批量重启存储节点")
    def test_restart_storage_nodes(self, xscale_page, xscale):
        """测试 XScale 实例详情页批量重启存储节点功能。"""
        instance_name = xscale["name"]

        with allure_step_log("步骤一：通过详情页按钮批量重启存储节点"):
            storage_nodes = xscale_page.restart_storage_nodes(instance_name)

        with allure_step_log("步骤二：验证存储节点批量重启结果"):
            xscale_page.assert_popup_success()
            xscale_page.assert_status(storage_nodes, status="节点重启中", timeout=300)
            xscale_page.assert_status(storage_nodes, status="就绪", timeout=1800)
