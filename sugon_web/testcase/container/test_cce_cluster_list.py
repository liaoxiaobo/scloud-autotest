import allure
import pytest
import time
from sugon_web.utils.logger import allure_step_log


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-列表页')
class TestCCEClusterList:

    @allure.title("集群管理-列表页-搜索")
    def test_search_cluster(self, cce_page, cce_cluster):
        """验证集群列表页搜索功能正常"""
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 按集群名称搜索，验证结果正确"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.goto_submenu("集群管理")
            cce_page.search(cluster_name)
            cce_page.assert_list_contain(cluster_name, column_name="集群名称")

        with allure_step_log("步骤2: 搜索不存在的名称，验证无结果"):
            non_existent = "cce-non-existent-99999"
            cce_page.search(non_existent)
            cce_page.assert_list_not_contain(non_existent, column_name="集群名称")

    @allure.title("集群管理-列表页-修改集群名称")
    def test_edit_cluster_name(self, cce_page, cce_cluster):
        """修改集群名称并验证列表中更新成功"""
        cluster_name = cce_cluster["name"]
        new_name = f"{cluster_name}-edited"

        with allure_step_log("步骤1: 修改集群名称"):
            cce_page.cce_edit_name(cluster_name, new_name)
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表中显示新名称"):
            cce_page.assert_list_contain(new_name, column_name="集群名称")

        with allure_step_log("步骤3: 改回原名称"):
            cce_page.cce_edit_name(new_name, cluster_name)
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(cluster_name, column_name="集群名称")

    @allure.title("集群管理-列表页-修改时间同步服务器")
    def test_edit_time_sync_server(self, cce_page, cce_cluster, ssh_vm):
        """修改集群时间同步服务器并验证后端配置生效"""
        cluster_name = cce_cluster["name"]
        sync_server = "100.126.255.254"

        with allure_step_log("步骤1: 修改时间同步服务器"):
            cce_page.cce_edit_time_sync(cluster_name, sync_server)

        with allure_step_log("步骤2: UI验证提交成功"):
            cce_page.assert_popup_success("设置CCE集群时间同步器成功")

        with allure_step_log("步骤3: SSH验证新配置生效"):
            ssh_vm.connect(cce_cluster["mfip"], port=22022, pwd="admin1234@sugon")
            for _ in range(5):
                result = ssh_vm.run("chronyc sources", return_rc=True)
                if result["rc"] == 0 and sync_server in result["stdout"]:
                    break
                time.sleep(10)
            else:
                assert False, f"时间同步服务器配置未生效: {result.get('stdout', '')}"
