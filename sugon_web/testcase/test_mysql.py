import allure
import pytest

from sugon_web.utils.util import random_data, load_data, random_string


@allure.epic('数据库服务')
@allure.feature('AnhanDB(for MySQL)')
class TestMySQL:

    @allure.title("MySQL-创建并删除实例-{params[instance_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_instance", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, mysql_page, params):
        """测试创建并删除MySQL实例（参数化）"""
        instance_name = f"mysql-{random_data()}"

        with allure.step(f"创建实例: {instance_name} ({params['instance_type']})"):
            mysql_page.create_instance(
                name=instance_name,
                instance_type=params['instance_type'],
                version=params['version'],
                disk_size=params['disk_size']
            )

        with allure.step("验证创建结果"):
            mysql_page.assert_popup_success("创建MySQL资源成功")
            mysql_page.assert_list_contain(instance_name)
            mysql_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure.step("删除实例"):
            mysql_page.delete_instance(instance_name)

        with allure.step("验证删除结果"):
            mysql_page.assert_deleted(instance_name)

    @allure.title("MySQL-重命名实例")
    def test_rename_instance(self, mysql_page, mysql):
        """测试重命名MySQL实例，这是一个独立的流程"""
        instance_name = mysql["name"]
        renamed_name = f"mysql-renamed-{random_data()}"

        with allure.step("重命名实例"):
            mysql_page.rename_instance(instance_name, renamed_name)
        with allure.step("验证重命名结果"):
            mysql_page.assert_popup_success("修改实例名称成功")
            mysql_page.assert_list_contain(renamed_name)
            mysql_page.assert_status(renamed_name, status="运行中")

        with allure.step("重命名实例回退"):
            mysql_page.rename_instance(renamed_name, instance_name)
        with allure.step("验证重命名回退结果"):
            mysql_page.assert_popup_success("修改实例名称成功")
            mysql_page.assert_list_contain(instance_name)
            mysql_page.assert_status(instance_name, status="运行中")

    @allure.title("MySQL-重启实例")
    def test_restart_instance(self, mysql_page, mysql):
        """测试重启MySQL实例"""
        instance_name = mysql["name"]
        with allure.step("重启实例"):
            mysql_page.restart_instance(instance_name)
        with allure.step("验证重启结果"):
            mysql_page.assert_popup_success("实例重启任务创建完成")
            mysql_page.assert_status(instance_name, status="重启中", timeout=10)
            mysql_page.assert_status(instance_name, status="运行中", timeout=300)

    @allure.title("MySQL-修改实例管理员密码")
    def test_change_root_password(self, mysql_page, mysql):
        """测试修改MySQL实例的管理员密码"""
        instance_name = mysql["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure.step("修改管理员密码"):
            mysql_page.change_root_password(instance_name, new_password)
        with allure.step("验证修改密码结果"):
            mysql_page.assert_popup_success("更新管理员用户信息成功")
            mysql_page.assert_status(instance_name, status="运行中", timeout=300)

    @allure.title("MySQL-修改云盘大小")
    def test_change_disk_size(self, mysql_page, mysql):
        """测试调整MySQL实例的云盘大小"""
        instance_name = mysql["name"]
        new_disk_size = 33  # 假设从20扩容到40

        with allure.step(f"调整实例 {instance_name} 的磁盘大小为 {new_disk_size}GB"):
            mysql_page.change_disk_size(instance_name, new_disk_size)

        with allure.step("验证调整结果"):
            mysql_page.assert_popup_success("扩容硬盘中，请耐心等待")
            mysql_page.assert_status(instance_name + "-0", status="调整云硬盘中", timeout=1200)
            mysql_page.assert_status(instance_name + "-0", status="运行中", timeout=500)

    @allure.title("MySQL-修改实例规格")
    def test_change_specification(self, mysql_page, mysql):
        """测试修改MySQL实例的规格"""
        instance_name = mysql["name"]
        specification_name = "mysql.d6 mysql.d6.2xlarge 8核"  # 请根据实际情况修改目标规格

        with allure.step("执行修改规格操作"):
            mysql_page.change_specification(instance_name, specification_name)

        with allure.step("验证规格是否修改成功"):
            # 刷新页面，然后检查实例列表中的规格信息
            mysql_page.assert_popup_success("修改规格中，请耐心等待")
            mysql_page.assert_status(instance_name + "-0", status="调整规格中", timeout=1200)
            mysql_page.assert_status(instance_name + "-0", status="运行中", timeout=5000)

    @allure.title("MySQL-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, mysql_page, mysql):
        """测试实例绑定和解绑MySQL实例的公网IP"""
        instance_name = mysql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure.step("绑定公网IP"):
            mysql_page.instance_ip_binding(instance_name, network=network)

        with allure.step("验证绑定结果"):
            mysql_page.assert_popup_success("执行成功")

        with allure.step("解绑公网IP"):
            mysql_page.instance_ip_unbinding(instance_name)

        with allure.step("验证解绑结果"):
            # 解绑后，IP地址信息应该不再显示
            mysql_page.assert_popup_success("执行成功")

    @allure.title("MySQL-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, mysql_page, mysql):
        """测试节点绑定和解绑MySQL实例的公网IP"""
        instance_name = mysql["name"]
        network = "public_net(基础版)"  # 请根据实际环境修改

        with allure.step("绑定公网IP"):
            mysql_page.node_ip_binding(instance_name, network=network)

        with allure.step("验证绑定结果"):
            mysql_page.assert_popup_success("执行成功")

        with allure.step("解绑公网IP"):
            mysql_page.node_ip_unbinding(instance_name)

        with allure.step("验证解绑结果"):
            # 解绑后，IP地址信息应该不再显示
            mysql_page.assert_popup_success("执行成功")

    @allure.title("MySQL-创建数据库")
    def test_create_database(self, mysql_page, mysql):
        """测试在实例下创建数据库"""
        instance_name = mysql["name"]
        db_name = f"autodb-{random_string(k=5)}"

        with allure.step(f"在实例 {instance_name} 下创建数据库 {db_name}"):
            mysql_page.create_database(instance_name, db_name)

        with allure.step("验证数据库是否创建成功"):
            # The popup is already asserted, now check the list
            mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            mysql_page.assert_list_contain(db_name)

    @allure.title("MySQL-创建和修改用户")
    def test_create_and_change_user(self, mysql_page, mysql):
        """测试创建用户并修改其权限"""
        instance_name = mysql["name"]
        db_name = mysql["db_name"]
        user_name = f"user_{random_string(k=5)}"
        password = f"sugon1234@{random_string(k=5)}"
        new_password = "sugon@4321"

        with allure.step(f"在实例 {instance_name} 中为数据库 {db_name} 创建用户 {user_name}"):
            mysql_page.create_user(instance_name, user_name, password, db_name, "读写")

        with allure.step("验证用户是否创建成功"):
            mysql_page.assert_popup_success("创建用户成功")
            mysql_page.assert_list_contain(user_name)

        with allure.step(f"修改用户 {user_name} 的密码"):
            mysql_page.change_user_privileges(instance_name, user_name, new_password)

        with allure.step("验证密码是否修改成功"):
            # 重新登录或执行需要新密码的操作来验证
            mysql_page.assert_popup_success("更新用户成功,若数据未更新请刷新页面")

    @allure.title("MySQL-用户授权和解除授权")
    def test_authorize_and_deauthorize_user(self, mysql_page, mysql):
        """测试用户授权和解除授权"""
        instance_name = mysql["name"]
        user_name = mysql["user_name"]
        # Create a new database for this test
        db_name = f"autodb-{random_string(k=5)}"

        with allure.step(f"前置操作：创建数据库 {db_name}"):
            mysql_page.create_database(instance_name, db_name)
            mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")

        with allure.step(f"为用户 {user_name} 授权访问数据库 {db_name}"):
            mysql_page.authorize_user(instance_name, user_name, db_name, "读写")

        with allure.step("验证授权结果"):
            mysql_page.assert_popup_success("授权用户数据库成功,若数据未更新请刷新页面")

        with allure.step(f"为用户 {user_name} 解除数据库 {db_name} 的授权"):
            mysql_page.deauthorize_user(instance_name, user_name, db_name)

        with allure.step("验证解除授权结果"):
            mysql_page.assert_popup_success("解除用户数据库权限成功")

    @allure.title("MySQL-开通和关闭读写分离")
    def test_read_write_splitting(self, mysql_page, mysql):
        """测试为MySQL实例开通和关闭读写分离功能"""
        instance_name = mysql["name"]
        with allure.step(f"为实例 {instance_name} 开通读写分离"):
            mysql_page.enable_splitting(instance_name)

        with allure.step("验证开通结果"):
            mysql_page.assert_popup_success("执行成功，若数据未响应请刷新页面", 10)
            obj_name = instance_name + "-middleware-0"
            mysql_page.assert_status(obj_name, "运行中", 120, True)

        with allure.step(f"为实例 {instance_name} 关闭读写分离"):
            mysql_page.disable_splitting(instance_name)

        with allure.step("验证关闭结果"):
            mysql_page.assert_popup_success("执行成功，若数据未响应请刷新页面")

    @allure.title("MySQL-手动备份")
    def test_create_backup(self, mysql_page, mysql):
        """测试为MySQL实例创建备份"""
        instance_name = mysql["name"]
        backup_name = f"backup-{random_data()}"

        with allure.step(f"为实例 {instance_name} 创建备份 {backup_name}"):
            mysql_page.create_backup(instance_name, backup_name)

        with allure.step("验证备份创建结果"):
            mysql_page.assert_popup_success("创建备份任务成功")
            # 这里可以增加导航到备份列表页并断言备份存在的逻辑

    @allure.title("MySQL-开启和关闭慢日志")
    def test_toggle_slow_log(self, mysql_page, mysql):
        """测试为MySQL实例开启和关闭慢日志功能"""
        instance_name = mysql["name"]
        with allure.step(f"为实例 {instance_name} 开启慢日志"):
            mysql_page.enable_slow_log(instance_name)

        with allure.step("验证开启结果"):
            mysql_page.assert_popup_success("开启慢日志成功")

        with allure.step(f"为实例 {instance_name} 关闭慢日志"):
            mysql_page.disable_slow_log(instance_name)

        with allure.step("验证关闭结果"):
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

        with allure.step(f"前置清理：重置白名单，确保环境干净"):
            mysql_page.reset_whitelist(instance_name)
            mysql_page.assert_popup_success("重置白名单成功")

        with allure.step("测试单个白名单的添加与删除"):
            mysql_page.add_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("创建白名单成功")
            mysql_page.assert_list_contain(ip_single, 1)

            mysql_page.delete_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("删除白名单成功")

        with allure.step(f"测试批量添加与批量删除白名单"):
            for ip in ip_batch:
                mysql_page.add_whitelist(instance_name, ip)
                mysql_page.assert_popup_success("创建白名单成功")
            for ip in ip_batch:
                mysql_page.assert_list_contain(ip, 1)

            mysql_page.batch_delete_whitelist(instance_name, ip_batch)
            mysql_page.assert_popup_success("删除白名单成功")

        with allure.step("测试重置白名单功能"):
            # 先添加一个，确保有内容可重置
            mysql_page.add_whitelist(instance_name, ip_single)
            mysql_page.assert_popup_success("创建白名单成功")
            mysql_page.assert_list_contain(ip_single, 1)

            # 执行重置
            mysql_page.reset_whitelist(instance_name)
            mysql_page.assert_popup_success("重置白名单成功")
