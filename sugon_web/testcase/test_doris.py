import allure
import pytest

from sugon_web.testcase.conftest import doris_page
from sugon_web.utils.util import random_data, load_data, random_string
from sugon_web.utils import db_util


@allure.epic('数据库服务')
@allure.feature('数据仓库 Doris')
class TestDoris:

    @allure.title("Doris-创建并删除实例-{params[ha_type]}")
    @pytest.mark.parametrize("params", load_data("test_create_and_delete_doris", data_file='test_cdb.yaml'))
    def test_create_and_delete_instance(self, doris_page, params, ssh_host):
        """测试创建并删除Doris实例（参数化）"""
        instance_name = f"doris-{random_data()}"

        with allure.step(f"步骤一：创建实例: {instance_name} ({params['ha_type']})"):
            doris_page.create_instance(
                name=instance_name,
                ha_type=params['ha_type'],
                fe_disk_size=params['fe_disk_size'],
                be_disk_size=params['be_disk_size'],
                case_sensitivity=params['case_sensitivity']
            )

        with allure.step("步骤二：验证创建结果"):
            doris_page.assert_popup_success("Doris创建任务提交成功")
            doris_page.assert_list_contain(instance_name)
            doris_page.assert_status(instance_name, status="就绪", timeout=1800)

        with allure.step("步骤三：删除实例"):
            doris_page.delete_instance(instance_name)

        with allure.step("步骤四：验证删除结果"):
            doris_page.assert_deleted(instance_name, timeout=1200)
            db_util.assert_backend_deleted(doris_page, ssh_host, instance_name)

    @allure.title("Doris-批量删除实例")
    def test_batch_delete_instances(self, doris_page, ssh_host):
        """测试批量删除Doris实例"""
        instance_names = [f"doris-batch-{random_data()}", f"doris-batch-{random_data()}"]

        for instance_name in instance_names:
            with allure.step(f"步骤一：创建实例: {instance_name}"):
                doris_page.create_instance(name=instance_name)
                doris_page.assert_popup_success("Doris创建任务提交成功")
                doris_page.assert_list_contain(instance_name)
                doris_page.assert_status(instance_name, status="就绪", timeout=1800)

        with allure.step("步骤二：批量删除实例"):
            doris_page.batch_delete_instances(instance_names)

        with allure.step("步骤三：验证批量删除结果"):
            for instance_name in instance_names:
                doris_page.assert_deleted(instance_name, timeout=1200)
                db_util.assert_backend_deleted(doris_page, ssh_host, instance_name)

    @allure.title("Doris-重命名实例")
    def test_rename_instance(self, doris_page, doris):
        """测试重命名Doris实例"""
        instance_name = doris["name"]
        renamed_name = f"doris-renamed-{random_data()}"

        with allure.step("步骤一：重命名实例"):
            doris_page.rename_instance(instance_name, renamed_name)

        with allure.step("步骤二：验证重命名结果"):
            doris_page.assert_popup_success("修改实例名称成功")
            doris_page.assert_list_contain(renamed_name)
            doris_page.assert_status(renamed_name, status="就绪")

        with allure.step("步骤三：重命名实例回退"):
            doris_page.rename_instance(renamed_name, instance_name)

        with allure.step("步骤四：验证重命名回退结果"):
            doris_page.assert_popup_success("修改实例名称成功")
            doris_page.assert_list_contain(instance_name)
            doris_page.assert_status(instance_name, status="就绪")

    @allure.title("Doris-重置管理员密码")
    def test_reset_admin_password(self, doris_page, doris, ssh_host, ssh_vm):
        """测试重置Doris实例的管理员密码"""
        instance_name = doris["name"]
        new_password = f"NewPass1@{random_string(k=5)}"

        with allure.step("步骤一：重置管理员密码"):
            doris_page.reset_admin_password(instance_name, new_password)

        with allure.step("步骤二：验证密码重置结果"):
            doris_page.assert_popup_success("执行成功")
            doris_page.assert_status(instance_name, status="就绪", timeout=300)

        with allure.step("步骤三：验证新密码生效"):
            node_name = f"{instance_name}_fe_node01"
            ip_from_db = db_util.get_node_mfip_from_db(doris_page, ssh_host, "sugoncloud_doris", node_name)
            ssh_vm.connect(ip_from_db, port=22022, pwd="admin1234@sugon")
            # 验证新密码可以成功登录Doris
            cmd_new = f"mysql -uadmin -p'{new_password}' -P9030 -h127.0.0.1 -e 'SELECT 1;'"
            result_new = ssh_vm.run(cmd_new)
            assert result_new.splitlines()[-1] == "1"
            # doris["admin_password"] = new_password

    @allure.title("Doris-停止和启动实例")
    def test_stop_and_start_instance(self, doris_page, doris):
        """测试停止和启动Doris实例"""
        instance_name = doris["name"]

        with allure.step("步骤一：停止实例"):
            doris_page.stop_instance(instance_name)

        with allure.step("步骤二：验证停止结果"):
            doris_page.assert_popup_success("实例停止任务创建完成")
            doris_page.assert_status(instance_name, status="停止中", timeout=1200)

        with allure.step("步骤三：状态重置"):
            doris_page.reset_instance(instance_name)

        with allure.step("步骤四：验证状态重置结果"):
            doris_page.assert_popup_success("实例数据库状态重置成功")
            doris_page.assert_status(instance_name, status="就绪", timeout=1200)

        with allure.step("步骤三：启动实例"):
            doris_page.start_instance(instance_name)

        with allure.step("步骤四：验证启动结果"):
            doris_page.assert_popup_success("实例重启任务创建完成")
            doris_page.assert_status(instance_name, status="重启中", timeout=600)
            doris_page.assert_status(instance_name, status="就绪", timeout=1200)

    @allure.title("DORIS-实例管理列表页搜索")
    def test_instance_search(self, doris_page, doris):
        """测试实例管理列表页的搜索功能"""
        instance_name = doris["name"]

        with allure.step("步骤一：输入实例名称进行搜索"):
            doris_page.goto_submenu("实例管理")
            keyword = instance_name[:-2]
            doris_page.search(keyword)
            doris_page.assert_list_contain(keyword, exact_match=False)

        with allure.step("步骤二：重置搜索条件"):
            doris_page.locator("div.cloud-button-btn").get_by_text("重置").click()
            doris_page.wait_for_page_ready()
            # 断言搜索输入框已清空
            assert doris_page._input_search.input_value() == "", "重置后搜索输入框未被清空"