import pytest
import allure
import time

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('存储管理')
class TestCCEVolume:
    """CCE 存储类型和存储卷管理测试类"""

    @allure.title("存储卷-创建")
    def test_storage_volume_create(self, cce_page, cce_cluster, storage_class, ssh_host, ssh_vm):
        cluster_name = cce_cluster["name"]
        mfip = cce_cluster.get("master_mfip", "")
        sc_name = storage_class["name"]
        pvc_name = f"pvc-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.goto_submenu("存储卷")

        with allure_step_log("步骤2: 创建存储卷"):
            cce_page.storage_volume_create(
                name=pvc_name,
                capacity=5,
                storage_class=sc_name,
                cluster=cluster_name,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证列表数据"):
            cce_page.assert_status(pvc_name, "绑定", refresh=True)

        with allure_step_log("步骤4: 后台验证PVC详情"):
            assert mfip, "未获取到集群 MFIP"
            ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(
                f"kubectl get pvc --all-namespaces -o custom-columns=NAME:.metadata.name,NAMESPACE:.metadata.namespace --no-headers | grep {pvc_name} | awk '{{print $2}}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl 执行失败: {result.get('stderr', '')}"
            namespace = result["stdout"].strip()
            assert namespace, f"未找到 {pvc_name} 的 namespace"

            result = ssh_vm.run(f"kubectl describe pvc {pvc_name} -n {namespace}", return_rc=True)
            assert result["rc"] == 0, f"kubectl describe 执行失败: {result.get('stderr', '')}"

        with allure_step_log("步骤5: 后台验证对应云盘"):
            result = ssh_vm.run(
                f"kubectl get pvc {pvc_name} -n {namespace} -o jsonpath='{{.spec.volumeName}}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl get pvc 执行失败: {result.get('stderr', '')}"
            pv_name = result["stdout"].strip()
            assert pv_name, "未获取到 PVC 的 volumeName"

            result = ssh_host.run(f"scli volume list | grep {pv_name}", return_rc=True)
            assert result["rc"] == 0, f"未找到对应云盘: {pv_name}"

        with allure_step_log("步骤6: 清理存储卷"):
            cce_page.storage_volume_delete(pvc_name)
            cce_page.assert_deleted(pvc_name, timeout=60)

    @allure.title("存储卷-扩容")
    def test_storage_volume_expand(self, cce_page, cce_cluster, storage_class):
        cluster_name = cce_cluster["name"]
        sc_name = storage_class["name"]
        pvc_name = f"pvc-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.goto_submenu("存储卷")

        with allure_step_log("步骤2: 创建存储卷"):
            cce_page.storage_volume_create(
                name=pvc_name,
                capacity=5,
                storage_class=sc_name,
                cluster=cluster_name,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()
            cce_page.assert_status(pvc_name, "绑定", refresh=True)

        with allure_step_log("步骤3: 扩容存储卷"):
            cce_page.storage_volume_expand(pvc_name, 10)

        with allure_step_log("步骤4: 验证容量已更新"):
            time.sleep(5)
            cce_page.wait_for_page_ready()
            row_data = cce_page.get_row_data(pvc_name)
            assert row_data, f"未找到 {pvc_name}"
            capacity = row_data.get("存储容量", "")
            assert "10Gi" in capacity, f"容量未更新，实际: {capacity}"

        with allure_step_log("步骤5: 清理存储卷"):
            cce_page.storage_volume_delete(pvc_name)
            cce_page.assert_deleted(pvc_name, timeout=60)

    @allure.title("存储卷-删除")
    def test_storage_volume_delete(self, cce_page, cce_cluster, storage_class, ssh_host, ssh_vm):
        cluster_name = cce_cluster["name"]
        mfip = cce_cluster.get("master_mfip", "")
        sc_name = storage_class["name"]
        pvc_name = f"pvc-del-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.goto_submenu("存储卷")

        with allure_step_log("步骤2: 创建存储卷"):
            cce_page.storage_volume_create(
                name=pvc_name,
                capacity=5,
                storage_class=sc_name,
                cluster=cluster_name,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()
            cce_page.assert_status(pvc_name, "绑定", refresh=True)

        with allure_step_log("步骤3: 后台验证PVC详情"):
            assert mfip, "未获取到集群 MFIP"
            ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(
                f"kubectl get pvc --all-namespaces -o custom-columns=NAME:.metadata.name,NAMESPACE:.metadata.namespace --no-headers | grep {pvc_name} | awk '{{print $2}}'",
                return_rc=True
            )
            namespace = result["stdout"].strip() if result["rc"] == 0 else "default"

            result = ssh_vm.run(f"kubectl describe pvc {pvc_name} -n {namespace}", return_rc=True)
            assert result["rc"] == 0, f"kubectl describe 执行失败: {result.get('stderr', '')}"

        with allure_step_log("步骤4: 后台验证对应云盘"):
            result = ssh_vm.run(
                f"kubectl get pvc {pvc_name} -n {namespace} -o jsonpath='{{.spec.volumeName}}'",
                return_rc=True
            )
            assert result["rc"] == 0, f"kubectl get pvc 执行失败: {result.get('stderr', '')}"
            pv_name = result["stdout"].strip()
            assert pv_name, "未获取到 PVC 的 volumeName"

            result = ssh_host.run(f"scli volume list | grep {pv_name}", return_rc=True)
            assert result["rc"] == 0, f"未找到对应云盘: {pv_name}"

        with allure_step_log("步骤5: 删除存储卷"):
            cce_page.storage_volume_delete(pvc_name)
            cce_page.assert_deleted(pvc_name, timeout=60)

        with allure_step_log("步骤6: 后台验证PVC已删除"):
            result = ssh_vm.run(f"kubectl describe pvc {pvc_name} -n {namespace}", return_rc=True)
            assert result["rc"] != 0 or "NotFound" in result.get("stderr", ""), "PVC 未删除"

        with allure_step_log("步骤7: 后台验证云盘已删除"):
            deleted = False
            for _ in range(24):
                result = ssh_host.run(f"scli volume list | grep {pv_name}", return_rc=True)
                if result["rc"] != 0:
                    deleted = True
                    break
                if "deleting" in result.get("stdout", ""):
                    time.sleep(5)
                    continue
                time.sleep(5)
            assert deleted, f"云盘未删除: {pv_name}"

    @allure.title("存储卷-批量删除")
    def test_storage_volume_batch_delete(self, cce_page, cce_cluster, storage_class):
        cluster_name = cce_cluster["name"]
        sc_name = storage_class["name"]
        pvc_names = []

        with allure_step_log("步骤1: 进入存储卷页面"):
            cce_page.goto_submenu("存储卷")

        with allure_step_log("步骤2: 预置两个存储卷"):
            for i in range(2):
                pvc_name = f"pvc-{random_data(length=4)}"
                pvc_names.append(pvc_name)
                cce_page.storage_volume_create(
                    name=pvc_name,
                    capacity=5,
                    storage_class=sc_name,
                    access_mode="ReadWriteOnce"
                )
                cce_page.assert_popup_success()
                cce_page.assert_status(pvc_name, "绑定", refresh=True)

        with allure_step_log("步骤3: 批量删除存储卷"):
            cce_page.storage_volume_batch_delete(pvc_names)

        with allure_step_log("步骤4: 验证存储卷已删除"):
            cce_page.assert_deleted(pvc_names, timeout=60)

    @allure.title("存储卷-搜索和重置")
    def test_storage_volume_search(self, cce_page, cce_cluster, storage_class):
        cluster_name = cce_cluster["name"]
        sc_name = storage_class["name"]
        pvc_name = f"pvc-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建存储卷"):
            cce_page.goto_submenu("存储卷")
            cce_page.storage_volume_create(
                name=pvc_name,
                capacity=5,
                storage_class=sc_name,
                cluster=cluster_name,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()
            cce_page.assert_status(pvc_name, "绑定", refresh=True)

        with allure_step_log("步骤2: 输入名称进行搜索"):
            keyword = pvc_name[:-2]
            cce_page.search(keyword)
            cce_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            cce_page.btn_reset.click()
            assert cce_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 清理存储卷"):
            cce_page.storage_volume_delete(pvc_name)
            cce_page.assert_deleted(pvc_name, timeout=60)
