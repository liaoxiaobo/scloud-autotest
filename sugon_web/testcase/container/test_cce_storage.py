import re
import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('存储管理')
class TestCCEStorageClassAndVolume:
    """CCE 存储类型和存储卷管理测试类"""

    @allure.title("集群管理-新建xbd存储池的云硬盘存储类型")
    def test_storage_class_create(self, cce_page, cce_cluster, ssh_host):
        cluster_name = cce_cluster["name"]

        with allure_step_log("步骤1: 进入集群详情页-存储类型页面"):
            cce_page.navigate_to_cluster_storage_class(cluster_name)

        with allure_step_log("步骤2: 创建云硬盘存储类型"):
            cce_page.storage_class_create(
                name="evs-sc",
                volume_type="xbd-test",
                fstype="ext4",
                encrypt=False,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证存储类型列表数据"):
            row_data = cce_page.get_row_data("evs-sc")
            assert row_data, "列表中未找到 evs-sc"
            assert "云硬盘" in row_data.get("类型", "") or "EVS" in row_data.get("类型", ""), f"类型不匹配: {row_data.get('类型', '')}"
            assert "是" in row_data.get("创建完成", ""), f"创建完成状态不匹配: {row_data.get('创建完成', '')}"

        with allure_step_log("步骤4: 后台验证StorageClass yaml"):
            result = ssh_host.run("kubectl get sc evs-sc -oyaml", return_rc=True)
            assert result["rc"] == 0, f"kubectl 执行失败: {result.get('stderr', '')}"
            yaml_content = result["stdout"]
            assert "storageType" in yaml_content, "yaml 中缺少 storageType"
            assert "fstype" in yaml_content, "yaml 中缺少 fstype"

    @allure.title("云硬盘类型存储卷-创建功能验证")
    def test_storage_volume_create(self, cce_page, cce_cluster, ssh_host):
        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.navigate_to_storage_volume()

        with allure_step_log("步骤2: 创建存储卷"):
            cce_page.storage_volume_create(
                name="test-pvc",
                capacity=5,
                storage_class="evs-sc",
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证列表数据"):
            cce_page.assert_status("test-pvc", "绑定", timeout=60)

        with allure_step_log("步骤4: 后台验证PVC详情"):
            result = ssh_host.run(
                r"kubectl get pvc --all-namespaces -o jsonpath='{range .items[?(@.metadata.name==\"test-pvc\")]}{.metadata.namespace}{end}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl 执行失败: {result.get('stderr', '')}"
            namespace = result["stdout"].strip()
            assert namespace, "未找到 test-pvc 的 namespace"

            result = ssh_host.run(f"kubectl describe pvc test-pvc -n {namespace}", return_rc=True)
            assert result["rc"] == 0, f"kubectl describe 执行失败: {result.get('stderr', '')}"

        with allure_step_log("步骤5: 后台验证对应云盘"):
            result = ssh_host.run(
                f"kubectl get pvc test-pvc -n {namespace} -o jsonpath='{{.spec.volumeName}}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl get pvc 执行失败: {result.get('stderr', '')}"
            pvc_name = result["stdout"].strip()
            assert pvc_name, "未获取到 PVC 的 volumeName"

            result = ssh_host.run(f"scli volume list | grep {pvc_name}", return_rc=True)
            assert result["rc"] == 0, f"未找到对应云盘: {pvc_name}"

    @allure.title("云硬盘类型存储卷-扩容功能验证")
    def test_storage_volume_expand(self, cce_page, cce_cluster):
        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.navigate_to_storage_volume()

        with allure_step_log("步骤2: 扩容存储卷"):
            cce_page.storage_volume_expand("test-pvc", 10)
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证容量已更新"):
            row_data = cce_page.get_row_data("test-pvc")
            assert row_data, "未找到 test-pvc"
            capacity = row_data.get("存储容量", "")
            assert "10Gi" in capacity, f"容量未更新，实际: {capacity}"

    @allure.title("云硬盘类型存储卷-删除功能验证")
    def test_storage_volume_delete(self, cce_page, cce_cluster, ssh_host):
        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.navigate_to_storage_volume()

        with allure_step_log("步骤2: 创建存储卷"):
            cce_page.storage_volume_create(
                name="test-pvc-del",
                capacity=5,
                storage_class="evs-sc",
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()
            cce_page.assert_status("test-pvc-del", "绑定", timeout=60)

        with allure_step_log("步骤3: 后台验证PVC详情"):
            result = ssh_host.run(
                r"kubectl get pvc --all-namespaces -o jsonpath='{range .items[?(@.metadata.name==\"test-pvc-del\")]}{.metadata.namespace}{end}'",
                return_rc=True
            )
            namespace = result["stdout"].strip() if result["rc"] == 0 else "default"

            result = ssh_host.run(f"kubectl describe pvc test-pvc-del -n {namespace}", return_rc=True)
            assert result["rc"] == 0, f"kubectl describe 执行失败: {result.get('stderr', '')}"

        with allure_step_log("步骤4: 后台验证对应云盘"):
            result = ssh_host.run(
                f"kubectl get pvc test-pvc-del -n {namespace} -o jsonpath='{{.spec.volumeName}}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl get pvc 执行失败: {result.get('stderr', '')}"
            pvc_name = result["stdout"].strip()
            assert pvc_name, "未获取到 PVC 的 volumeName"

            result = ssh_host.run(f"scli volume list | grep {pvc_name}", return_rc=True)
            assert result["rc"] == 0, f"未找到对应云盘: {pvc_name}"

        with allure_step_log("步骤5: 删除存储卷"):
            cce_page.storage_volume_delete("test-pvc-del")
            cce_page.assert_popup_success()
            cce_page.assert_deleted("test-pvc-del", timeout=60)

        with allure_step_log("步骤6: 后台验证PVC已删除"):
            result = ssh_host.run(f"kubectl describe pvc test-pvc-del -n {namespace}", return_rc=True)
            assert result["rc"] != 0 or "NotFound" in result.get("stderr", ""), "PVC 未删除"

        with allure_step_log("步骤7: 后台验证云盘已删除"):
            result = ssh_host.run(f"scli volume list | grep {pvc_name}", return_rc=True)
            assert result["rc"] != 0, f"云盘未删除: {pvc_name}"

        with allure_step_log("步骤8: 清理存储卷 test-pvc"):
            cce_page.storage_volume_delete("test-pvc")
            cce_page.assert_popup_success()

        with allure_step_log("步骤9: 清理存储类型 evs-sc"):
            cluster_name = cce_cluster["name"]
            cce_page.navigate_to_cluster_storage_class(cluster_name)
            cce_page.storage_class_delete("evs-sc")
            cce_page.assert_popup_success()
