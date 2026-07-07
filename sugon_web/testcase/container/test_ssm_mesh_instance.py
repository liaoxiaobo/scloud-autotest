import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('容器服务')
@allure.feature('服务治理SSM')
@allure.story('网格实例-列表页')
class TestSsmMeshInstanceLifecycle:
    """网格实例生命周期测试类：创建、批量删除。

    每个用例独立创建/删除网格实例，确保一个 CCE 集群上同一时刻最多只有一个 mesh。
    """

    @allure.title("网格实例-创建（不启用可观测）")
    def test_mesh_create_without_observability(self, ssm_page, cce_cluster, ssh_host, ssh_vm):
        """创建不启用可观测功能的网格实例，验证列表字段及后端 istio 组件。"""
        name = f"mesh-{random_data(length=4)}"
        cluster_name = cce_cluster["name"]
        master_mfip = cce_cluster["master_mfip"]

        with allure_step_log("前置清理：删除集群上残留的网格实例"):
            ssm_page.goto_service(ssm_page.service_name)
            ssm_page.goto_submenu("网格实例")
            ssm_page.wait_for_page_ready()
            rows = ssm_page.table_rows
            if rows:
                for row in rows:
                    try:
                        row_data = ssm_page.get_row_data_by_locator(row)
                        existing_name = row_data.get("名称", "")
                        if existing_name:
                            ssm_page.mesh_delete(existing_name)
                            ssm_page.assert_deleted(existing_name, timeout=600)
                            break
                    except Exception:
                        pass

        with allure_step_log(f"步骤1: 创建网格实例 {name}（规格32x，不启用可观测功能）"):
            ssm_page.mesh_create(name=name, cluster=cluster_name, flavor="32x")
            ssm_page.assert_popup_success()

        with allure_step_log("步骤2: 验证状态收敛到安装完成"):
            ssm_page.mesh_assert_status(name, status="安装完成", timeout=1800, refresh=True)

        with allure_step_log("步骤3: 验证列表字段与测试数据一致"):
            row = ssm_page.get_mesh_row_data(name)
            assert row.get("名称") == name, f"[FieldAssertion] 名称 | 期望: {name} | 实际: {row.get('名称')}"
            assert row.get("版本") == "1.16.2", f"[FieldAssertion] 版本 | 期望: 1.16.2 | 实际: {row.get('版本')}"
            assert cluster_name in row.get("集群", ""), (
                f"[FieldAssertion] 集群 | 期望包含: {cluster_name} | 实际: {row.get('集群')}"
            )

        with allure_step_log("步骤4: SSH验证istio组件及版本"):
            ssh_vm.connect(master_mfip, port=22022, pwd="admin1234@sugon")

            pods = ssh_vm.run("kubectl get po -n istio-system", return_rc=True)
            assert pods["rc"] == 0, f"[BackendAssertion] 查询 istio-system pod 失败: {pods.get('stderr', '')}"
            pod_text = pods["stdout"]
            assert "istiod" in pod_text, "[BackendAssertion] 未找到 istiod pod"
            assert "ingressgateway" in pod_text, "[BackendAssertion] 未找到 ingressgateway pod"
            assert "egressgateway" in pod_text, "[BackendAssertion] 未找到 egressgateway pod"
            assert "jaeger" not in pod_text, "[BackendAssertion] 不应存在 jaeger pod"
            assert "kiali" not in pod_text, "[BackendAssertion] 不应存在 kiali pod"

            # istioctl 可能未安装在节点固定路径，优先用 kubectl 从 pod image 标签验证版本
            version_check = ssh_vm.run(
                "kubectl get pods -n istio-system -o jsonpath='{..image}' | tr ' ' '\\n' | grep istio | head -1",
                return_rc=True,
            )
            assert version_check["rc"] == 0, (
                f"[BackendAssertion] 查询 istio pod image 失败: {version_check.get('stderr', '')}"
            )
            assert "1.16.2" in version_check["stdout"], (
                f"[BackendAssertion] istio 版本不匹配 | 期望包含: 1.16.2 | 实际: {version_check['stdout']}"
            )

        with allure_step_log("步骤5: 清理测试数据"):
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


@allure.epic('容器服务')
@allure.feature('服务治理SSM')
@allure.story('网格实例-列表页')
class TestSsmMeshInstanceManagement:
    """网格实例管理功能测试类：搜索、修改、检测。

    复用 class 级 mesh_instance fixture 创建的单个网格实例。
    """

    @allure.title("网格实例-搜索")
    def test_mesh_search(self, ssm_page, mesh_instance):
        """验证按网格实例名称搜索功能。"""
        name = mesh_instance["name"]

        with allure_step_log("步骤1: 按名称搜索"):
            ssm_page.mesh_search(name)
            ssm_page.assert_list_contain(name, column_name="名称")

        with allure_step_log("步骤2: 搜索不存在的关键字"):
            ssm_page.mesh_search("mesh-non-existent-99999")
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
