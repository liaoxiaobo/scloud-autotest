import allure
import pytest
import time

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


# CSV 定义的测试数据
CONFIGMAP_DATA_NAME = "ccetest123.2312-2.3-2w"
CONFIGMAP_DATA_CONTENT = "cce_test123.2312-2.-w" * 40
CONFIGMAP_EDIT_CONTENT = "cce_test-CCE123!@##"

SECRET_DATA_NAME = "cce-test123-2312-2-w"
SECRET_DATA_CONTENT = "cce_test123.2312-2.-w" * 40
SECRET_EDIT_CONTENT = "cce_test-CCE123!@##"

# 密钥创建用例（5968）固定测试数据
SECRET_CREATE_NAME = "test-est123"
SECRET_LABELS = {
    "test": "1024",
    "cce_test-12312345FF678901234567890a.bcdefghijklnmopqrs890":
        "cce_test-12312345678901234567890abcdefghijklnmopqrst1234567890",
}
SECRET_DATAS = {
    "cce-test2": "cce_test-122333322",
    "cce-.-test1": (
        "cce_./test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
        "cce_test-123/12345678901234567890abcdefghijklnmopqrst1234567890"
    ),
}


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-配置项')
class TestCCEResourceConfigmap:

    @allure.title("配置项-创建和删除")
    def test_configmap_create_and_delete(self, cce_page, cce_cluster):
        """测试创建配置项、验证详情、单个删除并验证清理。"""
        config_name = f"cfg-{random_data(length=4)}"
        labels = {"test": "1024"}
        datas = {"cce-test2": "cce_test-122333322"}

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(
                name=config_name,
                labels=labels,
                datas=datas
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表页包含新创建的配置项"):
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤3: 进入详情页验证数据一致性"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(
                name=config_name,
                labels=labels,
                datas=datas
            )

        with allure_step_log("步骤4: 单个删除配置项"):
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

        with allure_step_log("步骤5: 验证列表页不存在被删除的配置项"):
            cce_page.assert_list_not_contain(config_name, column_name="名称")

    @allure.title("配置项-批量删除")
    def test_configmap_delete_batch(self, cce_page, cce_cluster):
        """测试批量删除配置项并验证删除后数据一致性。"""
        config_name_1 = f"cfg-del-{random_data(length=4)}"
        config_name_2 = f"cfg-del-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建多个配置项"):
            for name in [config_name_1, config_name_2]:
                cce_page.configmap_create(name=name, datas={"key": "value"})
                cce_page.assert_popup_success()
                cce_page.assert_list_contain(name, column_name="名称")

        with allure_step_log("步骤2: 批量删除配置项"):
            cce_page.configmap_batch_delete([config_name_1, config_name_2])
            cce_page.assert_deleted(config_name_1)
            cce_page.assert_deleted(config_name_2)

        with allure_step_log("步骤3: 验证列表页不存在被删除的配置项"):
            cce_page.assert_list_not_contain(config_name_1, column_name="名称")
            cce_page.assert_list_not_contain(config_name_2, column_name="名称")

    @allure.title("配置项-详情添加和删除数据")
    def test_configmap_data_add_and_delete(self, cce_page, cce_cluster):
        """测试配置项详情页添加数据后删除，并验证列表一致性。"""
        config_name = f"cfg-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(name=config_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(name=config_name)

        with allure_step_log("步骤3: 添加数据"):
            cce_page.configmap_data_add(CONFIGMAP_DATA_NAME, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_assert_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤4: 删除数据"):
            cce_page.configmap_data_delete(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.configmap_data_assert_not_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤6: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

    @allure.title("配置项-详情编辑数据")
    def test_configmap_data_edit(self, cce_page, cce_cluster):
        """测试配置项详情页编辑数据，并验证内容一致性。"""
        config_name = f"cfg-edit-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建带数据的配置项"):
            cce_page.configmap_create(
                name=config_name,
                datas={CONFIGMAP_DATA_NAME: CONFIGMAP_DATA_CONTENT}
            )
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)
            cce_page.configmap_assert_detail(name=config_name, datas={CONFIGMAP_DATA_NAME: CONFIGMAP_DATA_CONTENT})

        with allure_step_log("步骤3: 编辑数据"):
            cce_page.configmap_data_edit(CONFIGMAP_DATA_NAME, CONFIGMAP_EDIT_CONTENT)

        with allure_step_log("步骤4: 验证编辑后内容一致性"):
            cce_page.configmap_data_assert_list(CONFIGMAP_DATA_NAME)

        with allure_step_log("步骤5: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)

    @allure.title("配置项-详情批量删除数据")
    def test_configmap_data_batch_delete(self, cce_page, cce_cluster):
        """测试配置项详情页批量删除数据，并验证列表一致性。"""
        config_name = f"cfg-batch-{random_data(length=4)}"
        data_name_1 = f"{CONFIGMAP_DATA_NAME}-1"
        data_name_2 = f"{CONFIGMAP_DATA_NAME}-2"

        with allure_step_log("步骤1: 创建配置项"):
            cce_page.configmap_create(name=config_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()
            cce_page.assert_list_contain(config_name, column_name="名称")

        with allure_step_log("步骤2: 进入配置项详情页"):
            cce_page.configmap_goto_detail(config_name)

        with allure_step_log("步骤3: 添加多条数据"):
            cce_page.configmap_data_add(data_name_1, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_add(data_name_2, CONFIGMAP_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.configmap_data_assert_list([data_name_1, data_name_2])

        with allure_step_log("步骤4: 批量删除数据"):
            cce_page.configmap_data_batch_delete([data_name_1, data_name_2])

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.configmap_data_assert_not_list([data_name_1, data_name_2])

        with allure_step_log("步骤6: 清理配置项"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.configmap_delete(config_name)
            cce_page.assert_deleted(config_name)


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('配置管理-密钥')
class TestCCEResourceSecret:

    @allure.title("密钥-创建和删除")
    def test_secret_create_and_delete(self, cce_page, cce_cluster):
        """测试创建密钥并验证列表数据，然后删除并验证清理。"""
        with allure_step_log("步骤1: 创建密钥"):
            cce_page.secret_create(
                name=SECRET_CREATE_NAME,
                secret_type="Opaque",
                labels=SECRET_LABELS,
                datas=SECRET_DATAS,
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表页数据一致性"):
            cce_page.secret_assert_list(SECRET_CREATE_NAME, secret_type="Opaque")

        with allure_step_log("步骤3: 删除密钥"):
            cce_page.secret_delete(SECRET_CREATE_NAME)

        with allure_step_log("步骤4: 验证被删除的密钥不存在"):
            cce_page.assert_list_not_contain(SECRET_CREATE_NAME, column_name="名称")

    @allure.title("密钥-详情添加和删除数据")
    def test_secret_data_add_and_delete(self, cce_page, cce_cluster):
        """测试密钥详情页添加数据后删除，并验证列表一致性。"""
        secret_name = f"sec-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建密钥"):
            cce_page.secret_create(name=secret_name, datas={"placeholder": "init"})
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 进入密钥详情页"):
            cce_page.secret_goto_detail(secret_name)

        with allure_step_log("步骤3: 添加数据"):
            cce_page.secret_data_add(SECRET_DATA_NAME, SECRET_DATA_CONTENT)
            cce_page.assert_popup_success()
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤4: 删除数据"):
            cce_page.secret_data_delete(SECRET_DATA_NAME)

        with allure_step_log("步骤5: 验证被删除数据不存在"):
            cce_page.secret_data_assert_not_list(SECRET_DATA_NAME)

        with allure_step_log("步骤6: 清理密钥"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.secret_delete(secret_name)
            cce_page.assert_deleted(secret_name)

    @allure.title("密钥-详情编辑数据")
    def test_secret_data_edit(self, cce_page, cce_cluster):
        """测试密钥详情页编辑数据，并验证内容一致性。"""
        secret_name = f"sec-edit-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建带数据的密钥"):
            cce_page.secret_create(
                name=secret_name,
                datas={SECRET_DATA_NAME: SECRET_DATA_CONTENT}
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤2: 进入密钥详情页"):
            cce_page.secret_goto_detail(secret_name)
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤3: 编辑数据"):
            cce_page.secret_data_edit(SECRET_DATA_NAME, SECRET_EDIT_CONTENT)
            cce_page.assert_popup_success()

        with allure_step_log("步骤4: 验证编辑后内容一致性"):
            cce_page.secret_data_assert_list(SECRET_DATA_NAME)

        with allure_step_log("步骤5: 清理密钥"):
            cce_page.goto_service(cce_page.service_name)
            cce_page.secret_delete(secret_name)
            cce_page.assert_deleted(secret_name)


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理-存储类型')
class TestCCEResourceStorageClass:

    @pytest.mark.parametrize("fstype", ["ext4", "xfs"])
    @allure.title("存储类型-创建和删除(fstype={fstype})")
    def test_storage_class_create(self, cce_page, cce_cluster, ssh_host, ssh_vm, fstype):
        cluster_name = cce_cluster["name"]
        mfip = cce_cluster.get("master_mfip", "")
        sc_name = f"evs-sc-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入集群详情-存储类型页面"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="存储类型")

        with allure_step_log(f"步骤2: 创建云硬盘存储类型(fstype={fstype})"):
            cce_page.storage_class_create(
                name=sc_name,
                volume_type=cce_page.volume_type,
                fstype=fstype,
                encrypt=False,
                access_mode="ReadWriteOnce"
            )
            cce_page.assert_popup_success()

        with allure_step_log("步骤3: 验证存储类型列表数据"):
            row_data = cce_page.get_row_data(sc_name)
            assert row_data, f"列表中未找到 {sc_name}"
            assert "云硬盘" in row_data.get("类型", "") or "EVS" in row_data.get("类型", ""), f"类型不匹配: {row_data.get('类型', '')}"
            assert "是" in row_data.get("创建完成", ""), f"创建完成状态不匹配: {row_data.get('创建完成', '')}"

        with allure_step_log(f"步骤4: 后台验证StorageClass yaml(fstype={fstype})"):
            assert mfip, "未获取到集群 MFIP"
            ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")
            result = ssh_vm.run(f"kubectl get storageclass {sc_name} -oyaml", return_rc=True)
            assert result["rc"] == 0, f"kubectl 执行失败: {result.get('stderr', '')}"
            yaml_content = result["stdout"]
            assert "storageType" in yaml_content, "yaml 中缺少 storageType"
            assert f"fstype: {fstype}" in yaml_content, f"yaml 中 fstype 值不匹配，期望 {fstype}"

        with allure_step_log("步骤5: 删除存储类型"):
            cce_page.storage_class_delete(sc_name)
            cce_page.assert_deleted(sc_name, timeout=60)

        with allure_step_log("步骤6: 后台验证StorageClass已删除"):
            result = ssh_vm.run(f"kubectl get storageclass {sc_name}", return_rc=True)
            assert result["rc"] != 0 or "NotFound" in result.get("stderr", ""), f"StorageClass {sc_name} 未删除"

    @allure.title("存储类型-批量删除")
    def test_storage_class_batch_delete(self, cce_page, cce_cluster):
        cluster_name = cce_cluster["name"]
        sc_names = []

        with allure_step_log("步骤1: 进入集群详情-存储类型页面"):
            cce_page.goto_submenu("集群管理")
            cce_page.goto_detail_page(cluster_name, tab_name="存储类型")

        with allure_step_log("步骤2: 预置两个存储类型"):
            for i in range(2):
                sc_name = f"evs-sc-{random_data(length=4)}"
                sc_names.append(sc_name)
                cce_page.storage_class_create(
                    name=sc_name,
                    volume_type=cce_page.volume_type,
                    fstype="ext4",
                    encrypt=False,
                    access_mode="ReadWriteOnce"
                )
                cce_page.assert_popup_success()

        with allure_step_log("步骤3: 批量删除存储类型"):
            cce_page.storage_class_batch_delete(sc_names)

        with allure_step_log("步骤4: 验证存储类型已删除"):
            cce_page.assert_deleted(sc_names, timeout=60)


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('存储管理')
class TestCCEResourceStorage:
    """CCE 存储卷管理测试类"""

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
                    access_mode="ReadWriteOnce",
                    cluster=cluster_name
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
