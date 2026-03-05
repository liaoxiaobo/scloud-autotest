from time import sleep
import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for PostgreSQL)')
class TestPgSQLBasic:

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
            pgsql_page.assert_status(renamed_name, status="运行中")

        with allure_step_log("步骤三：重命名实例回退"):
            pgsql_page.rename_instance(renamed_name, instance_name)
        with allure_step_log("步骤四：验证重命名回退结果"):
            pgsql_page.assert_popup_success("修改实例名称成功")
            pgsql_page.assert_list_contain(instance_name)
            pgsql_page.assert_status(instance_name, status="运行中")

    @allure.title("PostgreSQL-重启实例")
    def test_restart_instance(self, pgsql_page, pgsql):
        """测试重启PostgreSQL实例"""
        instance_name = pgsql["name"]
        with allure_step_log("步骤一：重启实例"):
            pgsql_page.restart_instance(instance_name)
        with allure_step_log("步骤二：验证重启结果"):
            pgsql_page.assert_popup_success("实例重启任务创建完成")
            pgsql_page.assert_status(instance_name, status="重启中", timeout=10)
            pgsql_page.assert_status(instance_name, status="运行中", timeout=300)

    @allure.title("PostgreSQL-修改实例管理员密码")
    def test_change_root_password(self, pgsql_page, pgsql, ssh_host, ssh_vm):
        """测试修改PostgreSQL实例的管理员密码"""
        instance_name = pgsql["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure_step_log("步骤一：修改管理员密码"):
            pgsql_page.change_root_password(instance_name, new_password)
        with allure_step_log("步骤二：验证修改密码结果"):
            pgsql_page.assert_popup_success("更新管理员用户信息成功")
            pgsql_page.assert_status(instance_name, status="运行中", timeout=300)

        with allure_step_log("步骤三：验证新密码生效"):
            node_name = f"{instance_name}-0"
            ip_from_db = db_util.get_node_mfip_from_db(pgsql_page, ssh_host, "sugoncloud_postgresql", node_name)
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
            pgsql_page.assert_popup_success("扩容硬盘中，请耐心等待")
            pgsql_page.assert_status(node_name, status="调整云硬盘中", timeout=1200)
            pgsql_page.assert_status(node_name, status="运行中", timeout=500)
            assert db_util.get_disk_size(pgsql_page, node_name, ssh_host) == new_disk_size

    @allure.title("PostgreSQL-修改实例规格")
    def test_change_specification(self, pgsql_page, pgsql, ssh_host):
        """测试修改PostgreSQL实例的规格"""
        instance_name = pgsql["name"]
        specification_name = "pgsql.d6 pgsql.d6.2xlarge 8核"
        real_specification = "pgsql.d6.2xlarge"

        with allure_step_log("步骤一：执行修改规格操作"):
            pgsql_page.change_specification(instance_name, specification_name)

        with allure_step_log("步骤二：验证规格是否修改成功"):
            node_name = f"{instance_name}-0"
            pgsql_page.assert_popup_success("修改规格中，请耐心等待")
            pgsql_page.assert_status(node_name, status="调整规格中", timeout=1200)
            pgsql_page.assert_status(node_name, status="运行中", timeout=5000)
            assert db_util.get_specification(pgsql_page, node_name, ssh_host) == real_specification

    @allure.title("PostgreSQL-创建数据库")
    def test_create_database(self, pgsql_page, pgsql):
        """测试创建数据库"""
        instance_name = pgsql["name"]
        db_name = f"testdb_{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建数据库 {db_name}"):
            pgsql_page.create_database(instance_name, db_name)

        with allure_step_log("步骤二：验证创建结果"):
            pgsql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            pgsql_page.assert_list_contain(db_name)

        with allure_step_log("步骤三：清理-删除数据库"):
            pgsql_page.delete_database(instance_name, db_name)
            pgsql_page.assert_popup_success("删除数据库成功,如果数据未更新,请刷新页面")

    @allure.title("PostgreSQL-批量删除数据库")
    def test_batch_delete_databases(self, pgsql_page, pgsql):
        """测试批量删除数据库"""
        instance_name = pgsql["name"]
        db_names = [f"testdb_{random_string(k=5)}", f"testdb_{random_string(k=5)}"]

        with allure_step_log("步骤一：创建多个数据库"):
            for db_name in db_names:
                pgsql_page.create_database(instance_name, db_name)
                pgsql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")

        with allure_step_log("步骤二：批量删除数据库"):
            pgsql_page.batch_delete_databases(instance_name, db_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            pgsql_page.assert_popup_success("删除数据库成功,如果数据未更新,请刷新页面")

    @allure.title("PostgreSQL-创建用户并授权")
    def test_create_user(self, pgsql_page, pgsql):
        """测试创建用户并授权"""
        instance_name = pgsql["name"]
        db_name = pgsql["db_name"]
        user_name = f"testuser_{random_string(k=5)}"
        user_password = f"sugon1234@{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建用户 {user_name}"):
            pgsql_page.create_user(instance_name, user_name, user_password, db_name, "读写")

        with allure_step_log("步骤二：验证创建结果"):
            pgsql_page.assert_popup_success("创建用户成功", 10)
            pgsql_page.assert_list_contain(user_name, "用户名")

        with allure_step_log("步骤三：清理-删除用户"):
            pgsql_page.delete_user(instance_name, user_name)
            pgsql_page.assert_popup_success("删除用户成功")

    @allure.title("PostgreSQL-修改用户密码")
    def test_change_user_password(self, pgsql_page, pgsql):
        """测试修改用户密码"""
        instance_name = pgsql["name"]
        user_name = pgsql["user_name"]
        new_password = f"NewPass@{random_string(k=6)}"

        with allure_step_log("步骤一：修改用户密码"):
            pgsql_page.change_user_privileges(instance_name, user_name, new_password)

        with allure_step_log("步骤二：验证修改结果"):
            pgsql_page.assert_popup_success("修改用户成功")
            pgsql["user_password"] = new_password

    @allure.title("PostgreSQL-用户授权与解除授权")
    def test_authorize_and_deauthorize_user(self, pgsql_page, pgsql):
        """测试用户授权与解除授权"""
        instance_name = pgsql["name"]
        user_name = pgsql["user_name"]
        db_name = pgsql["db_name"]

        with allure_step_log("步骤一：为用户授权数据库"):
            pgsql_page.authorize_user(instance_name, user_name, db_name, "读写")

        with allure_step_log("步骤二：验证授权结果"):
            pgsql_page.assert_popup_success("授权成功")

        with allure_step_log("步骤三：解除用户授权"):
            pgsql_page.deauthorize_user(instance_name, user_name, db_name)

        with allure_step_log("步骤四：验证解除授权结果"):
            pgsql_page.assert_popup_success("解除授权成功")

    @allure.title("PostgreSQL-批量删除用户")
    def test_batch_delete_users(self, pgsql_page, pgsql):
        """测试批量删除用户"""
        instance_name = pgsql["name"]
        db_name = pgsql["db_name"]
        user_names = [f"testuser_{random_string(k=5)}", f"testuser_{random_string(k=5)}"]
        user_password = f"sugon1234@{random_string(k=5)}"

        with allure_step_log("步骤一：创建多个用户"):
            for user_name in user_names:
                pgsql_page.create_user(instance_name, user_name, user_password, db_name, "只读")
                pgsql_page.assert_popup_success("创建用户成功", 10)

        with allure_step_log("步骤二：批量删除用户"):
            pgsql_page.batch_delete_users(instance_name, user_names)

        with allure_step_log("步骤三：验证批量删除结果"):
            pgsql_page.assert_popup_success("删除用户成功")

    @allure.title("PostgreSQL-白名单管理")
    def test_whitelist_management(self, pgsql_page, pgsql):
        """测试白名单管理（添加、删除、重置）"""
        instance_name = pgsql["name"]
        ip_address = "192.168.1.100"
        ip_addresses = ["192.168.1.101", "192.168.1.102"]

        with allure_step_log("步骤一：添加单个白名单"):
            pgsql_page.add_whitelist(instance_name, ip_address)
            pgsql_page.assert_popup_success("添加白名单成功")

        with allure_step_log("步骤二：删除单个白名单"):
            pgsql_page.delete_whitelist(instance_name, ip_address)
            pgsql_page.assert_popup_success("移除白名单成功")

        with allure_step_log("步骤三：添加多个白名单"):
            for ip in ip_addresses:
                pgsql_page.add_whitelist(instance_name, ip)
                pgsql_page.assert_popup_success("添加白名单成功")

        with allure_step_log("步骤四：批量删除白名单"):
            pgsql_page.batch_delete_whitelist(instance_name, ip_addresses)
            pgsql_page.assert_popup_success("删除白名单成功")

        with allure_step_log("步骤五：重置白名单"):
            pgsql_page.reset_whitelist(instance_name)
            pgsql_page.assert_popup_success("重置白名单成功")

    @allure.title("PostgreSQL-修改实例参数")
    def test_edit_instance_parameter(self, pgsql_page, pgsql):
        """测试修改实例参数"""
        instance_name = pgsql["name"]
        param_name = "max_connections"
        param_value = "150"

        with allure_step_log(f"步骤一：修改参数 {param_name} 为 {param_value}"):
            pgsql_page.edit_instance_parameter(instance_name, param_name, param_value)

        with allure_step_log("步骤二：验证修改结果"):
            pgsql_page.assert_popup_success("应用参数成功")
