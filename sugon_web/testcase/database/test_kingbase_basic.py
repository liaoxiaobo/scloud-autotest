import allure
import pytest
from time import sleep

from sugon_web.utils import db_util
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, random_string


@allure.epic("数据库服务")
@allure.feature("人大金仓 KingbaseES")
class TestKingbaseBasic:

    @allure.title("KingbaseES-重命名实例")
    def test_rename_instance(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        renamed_name = f"kingbase-renamed-{random_data()}"

        with allure_step_log("步骤一：修改实例名称"):
            kingbase_page.rename_instance(instance_name, renamed_name)

        with allure_step_log("步骤二：验证实例名称修改成功"):
            kingbase_page.assert_popup_success()
            kingbase_page.assert_list_contain(renamed_name)
            kingbase_page.assert_status(renamed_name, status="运行中", refresh=True)

        with allure_step_log("步骤三：回退实例名称"):
            kingbase_page.rename_instance(renamed_name, instance_name)

        with allure_step_log("步骤四：验证实例名称回退成功"):
            kingbase_page.assert_popup_success()
            kingbase_page.assert_list_contain(instance_name)
            kingbase_page.assert_status(instance_name, status="运行中", refresh=True)

    @allure.title("KingbaseES-重启数据库")
    def test_restart_instance(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]

        with allure_step_log("步骤一：重启数据库"):
            kingbase_page.restart_instance(instance_name)

        with allure_step_log("步骤二：验证重启任务执行成功"):
            kingbase_page.assert_popup_success("重启实例成功")
            kingbase_page.assert_status(instance_name, status="重启中", timeout=300, refresh=True)
            kingbase_page.assert_status(instance_name, status="运行中", timeout=1200, refresh=True)

    @allure.title("KingbaseES-重置密码")
    def test_change_root_password(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        new_password = f"NewPwd@1{random_string(k=6)}"

        with allure_step_log("步骤一：重置管理员密码"):
            kingbase_page.change_root_password(instance_name, new_password)

        with allure_step_log("步骤二：验证密码重置成功"):
            kingbase_page.assert_popup_success("执行成功")
            kingbase_page.assert_status(instance_name, status="运行中", timeout=600, refresh=True)
            kingbase["admin_password"] = new_password

    @allure.title("KingbaseES-实例绑定和解绑公网IP")
    def test_instance_bind_and_unbind_ip(self, kingbase_page, kingbase, ssh_host):
        instance_name = kingbase["name"]

        with allure_step_log("步骤一：为实例绑定公网IP"):
            ip = kingbase_page.instance_ip_binding(instance_name)

        with allure_step_log("步骤二：验证实例公网IP绑定成功"):
            kingbase_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：为实例解绑公网IP"):
            kingbase_page.instance_ip_unbinding(instance_name)

        with allure_step_log("步骤四：验证实例公网IP解绑成功"):
            kingbase_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("KingbaseES-节点绑定和解绑公网IP")
    def test_node_bind_and_unbind_ip(self, kingbase_page, kingbase, ssh_host):
        instance_name = kingbase["name"]
        node_name = f"{instance_name}-0"

        with allure_step_log("步骤一：为节点绑定公网IP"):
            ip = kingbase_page.node_ip_binding(instance_name, node_name=node_name)

        with allure_step_log("步骤二：验证节点公网IP绑定成功"):
            kingbase_page.assert_popup_success("执行成功")
            ssh_host.ping(ip)

        with allure_step_log("步骤三：为节点解绑公网IP"):
            kingbase_page.node_ip_unbinding(instance_name, node_name=node_name)

        with allure_step_log("步骤四：验证节点公网IP解绑成功"):
            kingbase_page.assert_popup_success("执行成功")
            ssh_host.ping(ip, connected=False)

    @allure.title("KingbaseES-节点热迁移")
    def test_node_hot_migration(self, kingbase_page, kingbase, ssh_host):
        instance_name = kingbase["name"]
        node_name = f"{instance_name}-0"
        old_host = db_util.get_backend_host(kingbase_page, ssh_host, node_name)

        with allure_step_log(f"步骤一：对节点 {node_name} 执行热迁移"):
            try:
                selected_host = kingbase_page.kingbase_hot_migration(instance_name, node_name)
            except pytest.skip.Exception:
                raise

        with allure_step_log("步骤二：验证热迁移任务执行成功"):
            kingbase_page.assert_popup_success("热迁移命令下发成功")
            kingbase_page.assert_status(node_name, status="迁移中", timeout=300, refresh=True)
            kingbase_page.assert_status(node_name, status="运行中", timeout=1800, refresh=True)

        with allure_step_log("步骤三：验证迁移后的后端宿主机发生变化"):
            new_host = db_util.get_backend_host(kingbase_page, ssh_host, node_name)
            assert new_host != old_host, f"热迁移后宿主机未发生变化: {old_host}"
            if selected_host:
                assert selected_host in new_host, f"目标宿主机不匹配，期望包含 {selected_host}，实际为 {new_host}"

    @allure.title("KingbaseES-新建备节点")
    def test_add_backup_node(self, kingbase_page, kingbase, ssh_host):
        instance_name = kingbase["name"]
        new_node_name = f"{instance_name}-3"

        with allure_step_log("步骤一：为实例新建备节点"):
            kingbase_page.add_backup_node(instance_name)

        with allure_step_log("步骤二：验证备节点创建成功"):
            kingbase_page.assert_popup_success("添加从节点")
            kingbase_page.assert_status(new_node_name, status="创建中", timeout=600, refresh=True)
            kingbase_page.assert_status(new_node_name, status="运行中", timeout=1800, refresh=True)
            db_util.assert_backend_created(kingbase_page, ssh_host, new_node_name, timeout=1800)

    @allure.title("KingbaseES-新建数据库")
    def test_create_database(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        db_name = f"autodb_{random_string(k=5)}"

        with allure_step_log(f"步骤一：新建数据库 {db_name}"):
            kingbase_page.create_database(instance_name, db_name)

        with allure_step_log("步骤二：验证数据库创建成功"):
            kingbase_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
            kingbase_page.assert_list_contain(db_name)

    @allure.title("KingbaseES-新建用户")
    def test_create_user(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        user_name = f"user_{random_string(k=5)}"
        password = f"Pwd@1{random_string(k=6)}"

        with allure_step_log(f"步骤一：新建用户 {user_name}"):
            kingbase_page.create_user(instance_name, user_name, password)

        with allure_step_log("步骤二：验证用户创建成功"):
            kingbase_page.assert_popup_success("创建用户成功")
            kingbase_page.assert_list_contain(user_name, "用户名")

    @allure.title("KingbaseES-修改用户")
    def test_change_user_password(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        user_name = kingbase["user_name"]
        new_password = f"NewPwd@1{random_string(k=6)}"

        with allure_step_log(f"步骤一：修改用户 {user_name} 密码"):
            kingbase_page.change_user_privileges(instance_name, user_name, new_password)

        with allure_step_log("步骤二：验证用户修改成功"):
            kingbase_page.assert_popup_success("更新用户成功")
            kingbase["user_password"] = new_password

    @allure.title("KingbaseES-授权和解除授权")
    def test_authorize_and_deauthorize_user(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        user_name = kingbase["user_name"]
        db_name = f"grantdb_{random_string(k=5)}"

        with allure_step_log(f"步骤一：创建待授权数据库 {db_name}"):
            kingbase_page.create_database(instance_name, db_name)
            kingbase_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")

        with allure_step_log("步骤二：为用户授权数据库"):
            kingbase_page.authorize_user(instance_name, user_name, db_name)

        with allure_step_log("步骤三：验证授权成功"):
            kingbase_page.assert_popup_success("执行成功,若数据未更新请刷新页面")
            kingbase_page.assert_list_contain(db_name, "数据库", exact_match=False)

        with allure_step_log("步骤四：解除用户数据库授权"):
            kingbase_page.deauthorize_user(instance_name, user_name, db_name)

        with allure_step_log("步骤五：验证解除授权成功"):
            kingbase_page.assert_popup_success("执行成功")

    @allure.title("KingbaseES-白名单管理")
    def test_whitelist_management(self, kingbase_page, kingbase):
        instance_name = kingbase["name"]
        whitelist_ips = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]

        with allure_step_log("步骤一：重置白名单，确保环境干净"):
            kingbase_page.reset_whitelist(instance_name)
            kingbase_page.assert_popup_success("重置白名单成功")

        with allure_step_log("步骤二：添加单个白名单并验证"):
            kingbase_page.add_whitelist(instance_name, whitelist_ips[0])
            kingbase_page.assert_popup_success("添加白名单成功")
            kingbase_page.assert_whitelist_contains(whitelist_ips[0])

        with allure_step_log("步骤三：删除单个白名单并验证"):
            kingbase_page.delete_whitelist(instance_name, whitelist_ips[0])
            kingbase_page.assert_popup_success("删除白名单成功")
            kingbase_page.assert_whitelist_not_contains(whitelist_ips[0])

        with allure_step_log("步骤四：批量添加白名单并验证"):
            for ip_address in whitelist_ips[1:]:
                kingbase_page.add_whitelist(instance_name, ip_address)
                kingbase_page.assert_popup_success("添加白名单成功")
                kingbase_page.assert_whitelist_contains(ip_address)

        with allure_step_log("步骤五：批量删除白名单并验证"):
            kingbase_page.batch_delete_whitelist(instance_name, whitelist_ips[1:])
            kingbase_page.assert_popup_success("删除白名单成功")
            for ip_address in whitelist_ips[1:]:
                kingbase_page.assert_whitelist_not_contains(ip_address)

    @allure.title("KingbaseES-实例搜索")
    def test_instance_search(self, kingbase_page, kingbase):
        keyword = kingbase["name"][:-2]

        with allure_step_log(f"步骤一：按关键字 {keyword} 搜索实例"):
            kingbase_page.goto_submenu("实例管理")
            kingbase_page.search(keyword)

        with allure_step_log("步骤二：验证实例搜索结果正确"):
            kingbase_page.assert_list_contain(keyword, exact_match=False)

    @allure.title("KingbaseES-数据库搜索")
    def test_database_search(self, kingbase_page, kingbase):
        """测试数据库列表页的搜索功能"""
        instance_name = kingbase["name"]
        keyword = kingbase["db_name"][:-2]

        with allure_step_log("步骤一：输入数据库名称进行搜索"):
            kingbase_page.goto_submenu("实例管理")
            kingbase_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            kingbase_page.get_by_role("tab", name="数据库", exact=True).click()
            kingbase_page.search(keyword)
            sleep(2)

        with allure_step_log("步骤二：验证数据库搜索结果正确"):
            kingbase_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            kingbase_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            assert kingbase_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("KingbaseES-用户搜索")
    def test_user_search(self, kingbase_page, kingbase):
        """测试用户列表页的搜索功能"""
        instance_name = kingbase["name"]
        keyword = kingbase["user_name"][:-2]

        with allure_step_log("步骤一：输入用户名称进行搜索"):
            kingbase_page.goto_submenu("实例管理")
            kingbase_page.locator("#cloud-container-content").get_by_text(instance_name).first.click()
            kingbase_page.get_by_role("tab", name="用户").click()
            kingbase_page.search(keyword)

        with allure_step_log("步骤二：验证用户搜索结果正确"):
            kingbase_page.assert_list_contain(keyword, "用户名", exact_match=False)

        with allure_step_log("步骤三：重置搜索条件"):
            kingbase_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            assert kingbase_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
