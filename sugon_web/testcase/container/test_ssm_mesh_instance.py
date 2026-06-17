import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@pytest.mark.parametrize(
    "cce_cluster",
    [{"name": "liaoxb-dontdelete", "reuse_existing": True}],
    indirect=True
)
@allure.epic('容器服务')
@allure.feature('服务治理SSM')
@allure.story('网格实例生命周期验证')
class TestSsmMeshInstanceLifecycle:
    """网格实例生命周期测试类：创建、批量删除。

    每个用例独立创建/删除网格实例，确保一个 CCE 集群上同一时刻最多只有一个 mesh。
    """

    @allure.title("网格实例-创建-默认规格")
    def test_mesh_create_default(self, ssm_page, cce_cluster):
        """创建默认规格网格实例，状态收敛到安装完成后删除。"""
        name = f"mesh-{random_data(length=4)}"
        cluster_name = cce_cluster["name"]

        with allure_step_log(f"步骤1: 创建网格实例 {name}"):
            ssm_page.mesh_create(name=name, cluster=cluster_name)
            ssm_page.assert_popup_success()

        with allure_step_log("步骤2: 验证状态收敛到安装完成"):
            ssm_page.mesh_assert_status(name, status="安装完成", timeout=1800, refresh=True)

        with allure_step_log("步骤3: 清理测试数据"):
            ssm_page.mesh_delete(name)
            ssm_page.assert_deleted(name, timeout=600)

    @allure.title("网格实例-批量删除")
    def test_mesh_batch_delete(self, ssm_page, cce_cluster):
        """创建一个临时网格实例，勾选后通过批量删除按钮删除。"""
        name = f"mesh-batch-{random_data(length=4)}"
        cluster_name = cce_cluster["name"]

        with allure_step_log(f"步骤1: 创建临时网格实例 {name}"):
            ssm_page.mesh_create(name=name, cluster=cluster_name)
            ssm_page.assert_popup_success()
            ssm_page.mesh_assert_status(name, status="安装完成", timeout=1800, refresh=True)

        with allure_step_log("步骤2: 批量删除该实例"):
            ssm_page.mesh_batch_delete([name])

        with allure_step_log("步骤3: 验证实例已删除"):
            ssm_page.assert_deleted(name, timeout=600)


@pytest.mark.parametrize(
    "cce_cluster",
    [{"name": "liaoxb-dontdelete", "reuse_existing": True}],
    indirect=True
)
@allure.epic('容器服务')
@allure.feature('服务治理SSM')
@allure.story('网格实例基础功能验证')
class TestSsmMeshInstanceManagement:
    """网格实例管理功能测试类：搜索、修改、检测。

    复用 class 级 mesh_instance fixture 创建的单个网格实例，
    避免在同一 CCE 集群上创建多个 mesh。
    """

    @allure.title("网格实例-列表页搜索")
    def test_mesh_search(self, ssm_page, mesh_instance):
        """验证按网格实例名称搜索功能。"""
        name = mesh_instance["name"]

        with allure_step_log("步骤1: 按名称搜索"):
            ssm_page.goto_service(ssm_page.service_name)
            ssm_page.goto_submenu("网格实例")
            ssm_page.search(name)
            ssm_page.assert_list_contain(name, column_name="名称")

        with allure_step_log("步骤2: 搜索不存在的关键字"):
            ssm_page.search("mesh-non-existent-99999")
            ssm_page.assert_list_not_contain(name, column_name="名称")

    @allure.title("网格实例-修改名称和规格")
    def test_mesh_edit(self, ssm_page, mesh_instance):
        """修改网格实例名称和规格，验证后恢复。"""
        name = mesh_instance["name"]
        new_name = f"{name}-edited"

        with allure_step_log("步骤1: 修改名称和规格为 64x"):
            ssm_page.mesh_edit(name, new_name=new_name, flavor="64x")
            ssm_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表显示新名称"):
            ssm_page.assert_list_contain(new_name, column_name="名称")

        with allure_step_log("步骤3: 等待状态恢复安装完成后恢复原始名称和规格 32x"):
            # 修改后网格会进入"资源准备中"状态，需等待恢复"安装完成"后再编辑
            ssm_page.mesh_assert_status(new_name, status="安装完成", timeout=1800, refresh=True)
            ssm_page.mesh_edit(new_name, new_name=name, flavor="32x")
            ssm_page.assert_popup_success()
            ssm_page.assert_list_contain(name, column_name="名称")

    @allure.title("网格实例-检测状态")
    def test_mesh_check(self, ssm_page, mesh_instance):
        """点击检测，验证弹窗展示 4 项检测内容。"""
        name = mesh_instance["name"]

        with allure_step_log("步骤1: 点击检测"):
            result = ssm_page.mesh_check(name)

        with allure_step_log("步骤2: 验证弹窗包含 4 项检测内容"):
            expected_items = ["集群状态", "控制面板", "出口网关", "入口网关"]
            for item in expected_items:
                assert item in result, f"检测结果缺少: {item}"
