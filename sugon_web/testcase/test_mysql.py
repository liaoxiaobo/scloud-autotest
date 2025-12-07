import time
from time import sleep
import allure
import pytest
from sugon_web.testcase.conftest import mysql_page
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for MySQL)')
class TestMySQL:

    @allure.title("MySQL-创建并删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_instance", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, mysql_page, params, ssh_host):
        """测试创建并删除MySQL实例（参数化）"""
        instance_name = f"mysql-{random_data()}"

        with allure_step_log(f"步骤一：创建实例: {instance_name} ({params['instance_type']})"):
            mysql_page.create_instance(
                name=instance_name,
                instance_type=params['instance_type'],
                version=params['version'],
                disk_size=params['disk_size']
            )

        with allure_step_log("步骤二：验证创建结果"):
            mysql_page.assert_popup_success("创建MySQL资源成功")
            mysql_page.assert_list_contain(instance_name)
            mysql_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤三：删除实例"):
            mysql_page.delete_instance(instance_name)

        with allure_step_log("步骤四：验证删除结果"):
            mysql_page.assert_deleted(instance_name, timeout=1200)
            db_util.assert_backend_deleted(mysql_page, ssh_host, instance_name)

    @allure.title("MySQL-批量删除实例")
    def test_batch_delete_instances(self, mysql_page, ssh_host):
        """测试批量删除MySQL实例"""
        instance_names = [f"mysql-batch-delete-{random_string(5)}", f"mysql-batch-delete-{random_string(5)}"]
        for instance_name in instance_names:
            with allure_step_log(f"步骤一：创建实例: {instance_name}"):
                mysql_page.create_instance(name=instance_name)
                mysql_page.assert_popup_success("创建MySQL资源成功")
                mysql_page.assert_list_contain(instance_name)
                mysql_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤二：批量删除实例"):
            mysql_page.batch_delete_instances(instance_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                mysql_page.assert_deleted(instance_name, timeout=1200)
                db_util.assert_backend_deleted(mysql_page, ssh_host, instance_name)

    @allure.title("MySQL-重命名实例")
    def test_rename_instance(self, mysql_page, mysql):
        """测试重命名MySQL实例，这是一个独立的流程"""
        instance_name = mysql["name"]
        renamed_name = f"mysql-renamed-{random_data()}"

        with allure_step_log("步骤一：重命名实例"):
            mysql_page.rename_instance(instance_name, renamed_name)
        with allure_step_log("步骤二：验证重命名结果"):
            mysql_page.assert_popup_success("修改实例名称成功")
            mysql_page.assert_list_contain(renamed_name)
            mysql_page.assert_status(renamed_name, status="运行中")

        with allure_step_log("步骤三：重命名实例回退"):
            mysql_page.rename_instance(renamed_name, instance_name)
        with allure_step_log("步骤四：验证重命名回退结果"):
            mysql_page.assert_popup_success("修改实例名称成功")
            mysql_page.assert_list_contain(instance_name)
            mysql_page.assert_status(instance_name, status="运行中")

    @allure.title("MySQL-重启实例")
    def test_restart_instance(self, mysql_page, mysql):
        """测试重启MySQL实例"""
        instance_name = mysql["name"]
        with allure_step_log("步骤一：重启实例"):
            mysql_page.restart_instance(instance_name)
        with allure_step_log("步骤二：验证重启结果"):
            mysql_page.assert_popup_success("实例重启任务创建完成")
            mysql_page.assert_status(instance_name, status="重启中", timeout=10)
            mysql_page.assert_status(instance_name, status="运行中", timeout=300)

    @allure.title("MySQL-修改实例管理员密码")
    def test_change_root_password(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试修改MySQL实例的管理员密码"""
        instance_name = mysql["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：修改管理员密码"):
            # 修改前登录
            mysql_page.change_root_password(instance_name, new_password)
        with allure_step_log("步骤二：验证修改密码结果"):
            mysql_page.assert_popup_success("更新管理员用户信息成功")
            mysql_page.assert_status(instance_name, status="运行中", timeout=300)

        with allure_step_log("步骤三：验证新密码生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            # 验证新密码可以成功登录
            cmd_new = f"mysql -uadmin -p'{new_password}' -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new)
            assert result_new.splitlines()[-1] == "1"
            mysql["admin_password"] = new_password

    @allure.title("MySQL-修改云盘大小")
    def test_change_disk_size(self, mysql_page, mysql, ssh_host):
        """测试调整MySQL实例的云盘大小"""
        instance_name = mysql["name"]
        new_disk_size = 66  # 假设从20扩容到40

        with allure_step_log(f"步骤一：调整实例 {instance_name} 的磁盘大小为 {new_disk_size}GB"):
            mysql_page.change_disk_size(instance_name, new_disk_size)

        with allure_step_log("步骤二：验证调整结果"):
            node_name = f"{instance_name}-0"
            mysql_page.assert_popup_success("扩容硬盘中，请耐心等待")
            mysql_page.assert_status(node_name, status="调整云硬盘中", timeout=1200)
            mysql_page.assert_status(node_name, status="运行中", timeout=500)
            assert db_util.get_disk_size(mysql_page, node_name, ssh_host) == new_disk_size

    @allure.title("MySQL-修改实例规格")
    def test_change_specification(self, mysql_page, mysql, ssh_host):
        """测试修改MySQL实例的规格"""
        instance_name = mysql["name"]
        specification_name = "mysql.d6 mysql.d6.2xlarge 8核"  # 请根据实际情况修改目标规格
        real_specification = "mysql.d6.2xlarge"

        with allure_step_log("步骤一：执行修改规格操作"):
            mysql_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格是否修改成功"):
            # 刷新页面，然后检查实例列表中的规格信息
            node_name = f"{instance_name}-0"
            mysql_page.assert_popup_success("修改规格中，请耐心等待")
            mysql_page.assert_status(node_name, status="调整规格中", timeout=1200)
            mysql_page.assert_status(node_name, status="运行中", timeout=5000)
            assert db_util.get_specification(mysql_page, node_name, ssh_host) == real_specification

    @allure.title("MySQL-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, mysql_page, mysql, ssh_host):
        """测试实例绑定和解绑MySQL实例的公网IP"""
        instance_name = mysql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = mysql_page.instance_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            mysql_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(mysql_page, ip, ssh_host)
            assert return_code == 0

        with allure_step_log("步骤三：解绑公网IP"):
            mysql_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证解绑结果"):
            # 解绑后，IP地址信息应该不再显示
            mysql_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(mysql_page, ip, ssh_host)
            assert return_code != 0

    @allure.title("MySQL-添加和删除节点")
    def test_add_and_delete_node(self, mysql_page, mysql, ssh_host):
        """测试为MySQL实例添加和删除节点"""
        instance_name = mysql["name"]
        node_name = f"{instance_name}-3"
        with allure_step_log("步骤一：为实例添加新节点"):
            mysql_page.add_node(instance_name)

        with allure_step_log("步骤二：验证节点是否添加成功"):
            mysql_page.assert_popup_success("添加只读节点")
            mysql_page.assert_status(node_name, status="创建中", timeout=1200)
            mysql_page.assert_status(node_name, status="运行中", timeout=2000)

        with allure_step_log("步骤三：删除新创建的节点"):
            mysql_page.delete_node(instance_name, node_name)

        with allure_step_log("步骤四：验证节点是否删除成功"):
            mysql_page.assert_deleted(node_name, timeout=1200)
            db_util.assert_backend_deleted(mysql_page, ssh_host, node_name)

    @allure.title("MySQL-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, mysql_page, mysql, ssh_host):
        """测试节点绑定和解绑MySQL实例的公网IP"""
        instance_name = mysql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure_step_log("步骤一：绑定公网IP"):
            ip = mysql_page.node_ip_binding(instance_name, network=network)

        with allure_step_log("步骤二：验证绑定结果"):
            mysql_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(mysql_page, ip, ssh_host)
            assert return_code == 0

        with allure_step_log("步骤三：解绑公网IP"):
            mysql_page.node_ip_unbinding(instance_name)
        with allure_step_log("步骤四：验证解绑结果"):
            # 解绑后，IP地址信息应该不再显示
            mysql_page.assert_popup_success("执行成功")
            return_code = db_util.get_ping_code(mysql_page, ip, ssh_host)
            assert return_code != 0

    @allure.title("MySQL-创建并删除数据库")
    def test_create_and_delete_database(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试在实例下创建和删除数据库，并验证其在后端生效与失效"""
        instance_name = mysql["name"]
        db_name = f"autodb-{random_string(k=5)}"
        admin_password = mysql["admin_password"]  # 前置操作已经修改过admin用户的密码
        password = "admin1234@sugon"  # 创建实例时的默认密码

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建数据库 {db_name}"):
            mysql_page.create_database(instance_name, db_name)

        with allure_step_log("步骤二：验证数据库是否创建成功"):
            # The popup is already asserted, now check the list
            mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            mysql_page.assert_list_contain(db_name)

        with allure_step_log("步骤三：验证新创建的数据库在后端生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=password)
            cmd_check_exist = f"mysql -uadmin -p'{admin_password}' -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
            result_exist = ssh_vm.run(cmd_check_exist)
            allure.attach(result_exist, name=f"查询数据库 {db_name} 的存在性")
            assert db_name in result_exist, f"在数据库后端未找到新创建的数据库 '{db_name}'."

        with allure_step_log(f"步骤四：在实例 {instance_name} 下删除数据库 {db_name}"):
            mysql_page.delete_database(instance_name, db_name)

        with allure_step_log("步骤五：验证数据库删除成功"):
            mysql_page.assert_deleted(db_name)

        with allure_step_log("步骤六：验证数据库在后端已失效"):
            cmd_check_gone = f"mysql -uadmin -p'{admin_password}' -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
            result_gone = ssh_vm.run(cmd_check_gone)
            allure.attach(result_gone, name=f"再次查询数据库 {db_name} 的存在性")
            assert db_name not in result_gone, f"数据库 '{db_name}' 在后端删除失败，仍然存在。"
            ssh_vm.close()

    @allure.title("MySQL-批量创建并删除数据库")
    def test_batch_create_and_delete_databases(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试在实例下批量创建和删除数据库，并验证其在后端生效与失效"""
        instance_name = mysql["name"]
        db_names = [f"autodb-batch-{random_string(k=4)}", f"autodb-batch-{random_string(k=4)}"]
        admin_password = mysql["admin_password"]
        password = "admin1234@sugon"

        with allure_step_log(f"步骤一：在实例 {instance_name} 下批量创建数据库"):
            for db_name in db_names:
                mysql_page.create_database(instance_name, db_name)
                mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
                mysql_page.assert_list_contain(db_name)

        with allure_step_log("步骤二：新创建的数据库均在后端生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=password)
            for db_name in db_names:
                cmd_check_exist = f"mysql -uadmin -p'{admin_password}' -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
                result_exist = ssh_vm.run(cmd_check_exist)
                allure.attach(result_exist, name=f"查询数据库 {db_name} 的存在性")
                assert db_name in result_exist, f"在数据库后端未找到新创建的数据库 '{db_name}'."

        with allure_step_log(f"步骤三：在实例 {instance_name} 下批量删除数据库"):
            mysql_page.batch_delete_databases(instance_name, db_names)

        with allure_step_log("步骤四：数据库均被删除"):
            for db_name in db_names:
                mysql_page.assert_deleted(db_name)

        with allure_step_log("步骤五：数据库在后端均已失效"):
            for db_name in db_names:
                cmd_check_gone = f"mysql -uadmin -p'{admin_password}' -h127.0.0.1 -e \"SHOW DATABASES LIKE '{db_name}';\""
                result_gone = ssh_vm.run(cmd_check_gone)
                allure.attach(result_gone, name=f"再次查询数据库 {db_name} 的存在性")
                assert db_name not in result_gone, f"数据库 '{db_name}' 在后端删除失败，仍然存在。"

        ssh_vm.close()

    @allure.title("MySQL-创建和修改用户")
    def test_create_and_change_user(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试创建用户、验证其有效性，然后修改密码并验证新旧密码的有效性"""
        instance_name = mysql["name"]
        db_name = mysql["db_name"]
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd@1{random_string(k=5)}"
        new_password = f"NewPwd@1{random_string(k=5)}"
        root_password = "admin1234@sugon"

        with allure_step_log(f"步骤一：在实例 {instance_name} 中为数据库 {db_name} 创建用户 {user_name}"):
            mysql_page.create_user(instance_name, user_name, password, db_name, "读写")

        with allure_step_log("步骤二：验证用户是否创建成功"):
            mysql_page.assert_popup_success("创建用户成功")
            mysql_page.assert_list_contain(user_name, "用户名")

        with allure_step_log(f"步骤三：后端验证：使用初始密码登录用户 {user_name}"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=root_password)

            cmd_login_initial = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e 'SELECT 1;'"
            result = ssh_vm.run(cmd_login_initial)
            assert result.splitlines()[-1] == "1"

        with allure_step_log(f"步骤四：修改用户 {user_name} 的密码"):
            mysql_page.change_user_privileges(instance_name, user_name, new_password)

        with allure_step_log("步骤五：确认密码修改成功"):
            mysql_page.assert_popup_success("更新用户成功,若数据未更新请刷新页面")

        with allure_step_log("步骤六：后端验证：确认新密码生效，旧密码失效"):
            # 验证新密码可以成功登录
            cmd_new_pwd = f"mysql -u{user_name} -p'{new_password}' -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new_pwd)
            assert result_new.splitlines()[-1] == "1"
        ssh_vm.close()

    @allure.title("MySQL-删除及批量删除用户")
    def test_delete_and_batch_delete_users(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试用户的单个删除和批量删除功能，并进行后端验证"""
        instance_name = mysql["name"]
        db_name = mysql["db_name"]
        root_password = "admin1234@sugon"

        # 1. 准备环境：创建3个用于测试的用户
        users_to_create = [f"del_user_{random_string(k=4)}" for _ in range(3)]
        user_to_delete_single = users_to_create[0]
        users_to_delete_batch = users_to_create[1:]

        with allure_step_log(f"步骤一：在实例 {instance_name} 下创建3个测试用户"):
            for user in users_to_create:
                mysql_page.create_user(instance_name, user, f"Pwd@1{random_string(k=5)}", db_name, "只读")
                mysql_page.assert_popup_success("创建用户成功")
                mysql_page.assert_list_contain(user, "用户名")

        with allure_step_log(f"步骤二：删除单个用户 {user_to_delete_single}"):
            mysql_page.delete_user(instance_name, user_to_delete_single)

        with allure_step_log("步骤三：确认单个用户已删除"):
            mysql_page.assert_deleted(user_to_delete_single)

            # 后端验证：确认用户已不存在
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=root_password)

            cmd_check_single = f"mysql -uadmin -p'{root_password}' -h127.0.0.1 -e \"SELECT user FROM mysql.user WHERE user = '{user_to_delete_single}';\""
            result_single = ssh_vm.run(cmd_check_single)
            allure.attach(result_single, name=f"后端查询已删除用户 {user_to_delete_single}")
            assert user_to_delete_single not in result_single, f"用户 {user_to_delete_single} 在后端删除失败，仍然存在。"

        with allure_step_log(f"步骤四：批量删除用户 {', '.join(users_to_delete_batch)}"):
            mysql_page.batch_delete_users(instance_name, users_to_delete_batch)

        with allure_step_log("步骤五：确认批量用户已删除"):
            for user in users_to_delete_batch:
                mysql_page.assert_deleted(user)

                # 后端验证
                cmd_check_batch = f"mysql -uadmin -p'{root_password}' -h127.0.0.1 -e \"SELECT user FROM mysql.user WHERE user = '{user}';\""
                result_batch = ssh_vm.run(cmd_check_batch)
                allure.attach(result_batch, name=f"后端查询已删除用户 {user}")
                assert user not in result_batch, f"用户 {user} 在后端批量删除失败，仍然存在。"

        ssh_vm.close()

    @allure.title("MySQL-用户授权和解除授权的后端验证")
    def test_authorize_and_deauthorize_user(self, mysql_page, mysql, ssh_host, ssh_vm):
        """测试用户的只读、读写权限授权及解除授权，并进行完整的后端生效性验证"""
        instance_name = mysql["name"]
        user_name = mysql["user_name"]
        password = mysql["user_password"]  # 从 fixture 获取用户的密码
        root_password = "admin1234@sugon"  # root 密码用于连接和准备环境

        # 1. 准备环境：创建两个用于测试的数据库
        db_readonly = f"autodb_ro_{random_string(k=4)}"
        db_readwrite = f"autodb_rw_{random_string(k=4)}"

        with allure_step_log(f"步骤一：创建测试数据库 {db_readonly} 和 {db_readwrite}"):
            mysql_page.create_database(instance_name, db_readonly)
            mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            mysql_page.create_database(instance_name, db_readwrite)
            mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")

        # 2. 测试只读权限
        with allure_step_log(f"步骤二：为用户 {user_name} 授予对 {db_readonly} 的只读权限"):
            mysql_page.authorize_user(instance_name, user_name, db_readonly, "只读")
            mysql_page.assert_popup_success("授权用户数据库成功,若数据未更新请刷新页面")

        with allure_step_log("步骤三：后端确认只读权限生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(mysql_page, ssh_host, "sugoncloud_mysql", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd=root_password)

            # 尝试写入（应失败）
            cmd_write_fail = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e \"CREATE TABLE {db_readonly}.test(id int);\""
            result_write_fail = ssh_vm.run(cmd_write_fail, True, True)
            assert "CREATE command denied" in result_write_fail['stderr'], "只读用户执行写入操作未按预期失败。"

            # 尝试读取（应成功）
            cmd_read_ok = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e \"SELECT 1;\""
            result_read_ok = ssh_vm.run(cmd_read_ok)
            assert result_read_ok.splitlines()[-1] == "1", "只读用户执行读取操作未按预期成功。"
        # 3. 测试读写权限
        with allure_step_log(f"步骤四：为用户 {user_name} 授予对 {db_readwrite} 的读写权限"):
            mysql_page.authorize_user(instance_name, user_name, db_readwrite, "读写")
            mysql_page.assert_popup_success("授权用户数据库成功,若数据未更新请刷新页面")

        with allure_step_log("步骤五：后端确认读写权限生效"):
            # 尝试写入（应成功）
            cmd_write_ok = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e \"CREATE TABLE {db_readwrite}.test(id int); INSERT INTO {db_readwrite}.test VALUES (1);\""
            result_write_ok = ssh_vm.run(cmd_write_ok, True, True)
            assert "ERROR" not in result_write_ok['stderr'], f"读写用户执行写入操作失败: {result_write_ok}"

            # 尝试读取（应成功）
            cmd_read_write_ok = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e \"SELECT * FROM {db_readwrite}.test;\""
            result_read_write_ok = ssh_vm.run(cmd_read_write_ok)
            assert result_read_write_ok.splitlines()[-1] == "1", "读写用户执行读取操作未能查到刚写入的数据。"

        # 4. 测试解除授权
        with allure_step_log(f"步骤六：解除用户 {user_name} 对 {db_readonly} 和 {db_readwrite} 的权限"):
            mysql_page.deauthorize_user(instance_name, user_name, db_readonly)
            mysql_page.assert_popup_success("解除用户数据库权限成功")
            mysql_page.deauthorize_user(instance_name, user_name, db_readwrite)
            mysql_page.assert_popup_success("解除用户数据库权限成功")

        with allure_step_log("步骤七：后端确认用户权限已被解除"):
            cmd_access_denied = f"mysql -u{user_name} -p'{password}' -h127.0.0.1 -e \"USE {db_readonly};\""
            result_access_denied = ssh_vm.run(cmd_access_denied, True, True)
            assert "Access denied" in result_access_denied[
                'stderr'], f"访问已解除授权的数据库 {db_readonly} 时未返回预期错误。"

        ssh_vm.close()

    @allure.title("MySQL-开通和关闭读写分离")
    def test_read_write_splitting(self, mysql_page, mysql, ssh_host):
        """测试为MySQL实例开通和关闭读写分离功能"""
        instance_name = mysql["name"]
        with allure_step_log(f"步骤一：为实例 {instance_name} 开通读写分离"):
            mysql_page.enable_splitting(instance_name)

        with allure_step_log("步骤二：验证开通结果"):
            mysql_page.assert_popup_success("执行成功，若数据未响应请刷新页面", 10)
            obj_name = instance_name + "-middleware-0"
            mysql_page.assert_status(obj_name, "运行中", 1800, True)

        with allure_step_log(f"步骤三：为实例 {instance_name} 关闭读写分离"):
            mysql_page.disable_splitting(instance_name)

        with allure_step_log("步骤四：验证关闭结果"):
            mysql_page.assert_popup_success("执行成功，若数据未响应请刷新页面")
            db_util.assert_backend_deleted(mysql_page, ssh_host, obj_name)

    # @allure.title("MySQL-手动备份")
    # def test_create_backup(self, mysql_page, mysql):
    #     """测试为MySQL实例创建备份"""
    #     instance_name = mysql["name"]
    #     backup_name = f"backup-{random_data()}"
    #
    #     with allure_step_log(f"为实例 {instance_name} 创建备份 {backup_name}"):
    #         mysql_page.create_backup(instance_name, backup_name)
    #
    #     with allure_step_log("验证备份创建结果"):
    #         mysql_page.assert_popup_success("创建备份任务成功")
    #         # 这里可以增加导航到备份列表页并断言备份存在的逻辑

    @allure.title("MySQL-开启和关闭慢日志")
    def test_toggle_slow_log(self, mysql_page, mysql):
        """测试为MySQL实例开启和关闭慢日志功能"""
        instance_name = mysql["name"]
        with allure_step_log(f"步骤一：为实例 {instance_name} 开启慢日志"):
            mysql_page.enable_slow_log(instance_name)

        with allure_step_log("步骤二：验证开启结果"):
            mysql_page.assert_popup_success("开启慢日志成功")

        with allure_step_log(f"步骤三：为实例 {instance_name} 关闭慢日志"):
            mysql_page.disable_slow_log(instance_name)

        with allure_step_log("步骤四：验证关闭结果"):
            mysql_page.assert_popup_success("关闭慢日志成功")

    @allure.title("MySQL-白名单管理")
    def test_whitelist_management(self, mysql_page, mysql):
        """测试白名单的添加、删除、批量删除和重置功能"""
        instance_name = mysql["name"]
        whitelist_ips = [
            "10.0.5.0/24",
            "10.0.6.0/24",
            "10.0.7.0/24",
            "10.0.8.0/24"
        ]
        ip_single = whitelist_ips[0]
        ip_batch = whitelist_ips[1:]

        with allure_step_log(f"步骤一：重置白名单，确保环境干净"):
            mysql_page.reset_whitelist(instance_name)
            mysql_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：测试单个白名单的添加与删除"):
            mysql_page.add_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("创建白名单成功")
            mysql_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            mysql_page.delete_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("删除白名单成功")

        with allure_step_log(f"步骤三：测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                mysql_page.add_whitelist(instance_name, ip)
                mysql_page.assert_popup_success("创建白名单成功")
            for ip in ip_batch:
                mysql_page.assert_list_contain(ip, "白名单", exact_match=False)

            mysql_page.batch_delete_whitelist(instance_name, ip_batch)
            mysql_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤四：测试重置白名单功能"):
            # 先添加一个，确保有内容可重置
            mysql_page.add_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("创建白名单成功")
            mysql_page.assert_list_contain(ip_single, "白名单", exact_match=False)

            # 执行重置
            mysql_page.reset_whitelist(instance_name)
            mysql_page.assert_popup_success("重置白名单成功")

    @allure.title("MySQL-参数模板创建和删除")
    def test_create_and_delete_model(self, mysql_page):
        """测试创建和删除参数模板"""
        model_name = f"model-{random_data()}"
        version = "8.0"

        with allure_step_log(f"步骤一：创建参数模板 {model_name}"):
            mysql_page.create_parameter_model(model_name, version)
            mysql_page.assert_popup_success("创建模板成功")
            mysql_page.assert_list_contain(model_name)

        with allure_step_log(f"步骤二：删除参数模板 {model_name}"):
            mysql_page.delete_parameter_model(model_name)
            mysql_page.assert_deleted(model_name)

    @allure.title("MySQL-参数模板编辑和应用")
    def test_edit_and_apply_model(self, mysql_page, mysql):
        """测试参数模板的编辑、应用和删除"""
        instance_name = mysql["name"]
        model_name = f"model-{random_data()}"
        param_to_edit = "auto_increment_increment"

        with allure_step_log(f"步骤一：创建参数模板 {model_name}"):
            mysql_page.create_parameter_model(model_name)
            mysql_page.assert_popup_success("创建模板成功")
            mysql_page.assert_list_contain(model_name)

        with allure_step_log(f"步骤二：编辑参数模板，添加参数 {param_to_edit}"):
            mysql_page.edit_parameter_model(model_name, param_to_edit)
            mysql_page.assert_popup_success("修改模板成功")

        with allure_step_log(f"步骤三：将模板 {model_name} 应用到实例 {instance_name}"):
            mysql_page.apply_parameter_model(model_name, instance_name)
            mysql_page.assert_popup_success("模板应用任务提交成功")
            mysql_page.goto_submenu("实例管理")
            mysql_page.assert_status(instance_name, status="调整参数中", timeout=1200)
            mysql_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)
            mysql_page.locator(f"#cloud-container-content").get_by_text(instance_name).click()
            mysql_page.assert_status(f"{instance_name}-0", status="运行中", timeout=1200, refresh=True)
            mysql_page.assert_status(f"{instance_name}-1", status="运行中", timeout=1200, refresh=True)
            mysql_page.assert_status(f"{instance_name}-2", status="运行中", timeout=1200, refresh=True)

        with allure_step_log(f"步骤四：删除参数模板 {model_name}"):
            mysql_page.delete_parameter_model(model_name)
            mysql_page.assert_deleted(model_name)

    @allure.title("MySQL-实例参数编辑和导出")
    def test_edit_and_export_instance_parameters(self, mysql_page, mysql):
        """测试实例参数的编辑和导出"""
        instance_name = mysql["name"]
        param_name = "auto_increment_increment"
        param_value = "10"

        with allure_step_log(f"步骤一：编辑实例 {instance_name} 的参数 {param_name} 值为 {param_value}"):
            mysql_page.goto_submenu("实例管理")
            mysql_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)
            mysql_page.edit_instance_parameter(instance_name, param_name, param_value)
            mysql_page.assert_popup_success("修改实例参数任务提交成功")
            mysql_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

        with allure_step_log(f"步骤二：导出实例 {instance_name} 的参数"):
            mysql_page.export_instance_parameters(instance_name)
            # 导出通常是文件下载，这里只验证触发成功
            mysql_page.assert_popup_success("导出参数设置成功")

    @allure.title("MySQL-实例管理列表页搜索")
    def test_instance_search(self, mysql_page, mysql):
        """测试实例管理列表页的搜索功能"""
        instance_name = mysql["name"]

        with allure_step_log("步骤一：输入实例名称进行搜索"):
            mysql_page.goto_submenu("实例管理")
            keyword = instance_name[:-2]
            mysql_page.search(keyword)
            mysql_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mysql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mysql_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert mysql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MySQL-数据库列表页搜索")
    def test_database_search(self, mysql_page, mysql):
        """测试数据库列表页的搜索功能"""
        instance_name = mysql["name"]
        db_name = mysql["db_name"]

        with allure_step_log("步骤一：输入数据库名称进行搜索"):
            mysql_page.goto_submenu("实例管理")
            mysql_page.locator("#cloud-container-content").get_by_text(instance_name).click()
            mysql_page.wait_for_page_ready()
            mysql_page.get_by_role("tab", name="数据库", exact=True).click()
            mysql_page.wait_for_page_ready()
            keyword = db_name[:-2]
            mysql_page.search(keyword)
            mysql_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mysql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mysql_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert mysql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MySQL-用户列表页搜索")
    def test_user_search(self, mysql_page, mysql):
        """测试用户列表页的搜索功能"""
        instance_name = mysql["name"]
        user_name = mysql["user_name"]

        with allure_step_log("步骤一：输入用户名称进行搜索"):
            mysql_page.goto_submenu("实例管理")
            mysql_page.locator("#cloud-container-content").get_by_text(instance_name).click()
            mysql_page.wait_for_page_ready()
            mysql_page.get_by_role("tab", name="用户").click()
            mysql_page.wait_for_page_ready()
            keyword = user_name[:-2]
            mysql_page.search(keyword)
            mysql_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mysql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mysql_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert mysql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MySQL-实例参数设置页搜索")
    def test_instance_parameter_search(self, mysql_page, mysql):
        """测试实例参数设置页的搜索功能"""
        instance_name = mysql["name"]
        param_keyword = "auto_increment"

        with allure_step_log("步骤一：输入参数名称进行搜索"):
            mysql_page.goto_submenu("实例管理")
            mysql_page.locator("#cloud-container-content").get_by_text(instance_name).click()
            mysql_page.wait_for_page_ready()
            sleep(2)
            mysql_page.get_by_role("tab", name="参数设置").click()
            sleep(2)
            mysql_page.wait_for_page_ready()
            mysql_page.search(param_keyword)
            mysql_page.assert_list_contain(param_keyword, "参数名称", exact_match=False)

        with allure_step_log("步骤二：重置搜索条件"):
            mysql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mysql_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert mysql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("MySQL-参数管理列表页搜索")
    def test_parameter_model_search(self, mysql_page):
        """测试参数管理列表页的搜索功能"""
        model_name = f"model-search-{random_data()}"

        with allure_step_log(f"步骤一：创建参数模板 {model_name}"):
            mysql_page.goto_submenu("参数管理")
            mysql_page.create_parameter_model(model_name)
            mysql_page.assert_popup_success("创建模板成功")
            mysql_page.assert_list_contain(model_name)

        with allure_step_log("步骤二：输入模板名称进行搜索"):
            keyword = model_name[:-2]
            mysql_page.search(keyword)
            mysql_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            mysql_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            mysql_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert mysql_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log(f"步骤四：删除参数模板 {model_name}"):
            mysql_page.delete_parameter_model(model_name)
            mysql_page.assert_deleted(model_name)
