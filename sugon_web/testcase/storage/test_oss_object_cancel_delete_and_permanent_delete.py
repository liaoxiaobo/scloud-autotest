import os

import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('对象管理-取消删除与彻底删除')
class TestOSSObjectCancelDeleteAndPermanentDelete:
    """验证OSS对象存储已删除对象的取消删除与彻底删除功能。

    两个场景共享同一桶资源（class-scoped fixture），所有用例执行完成后统一清理。
    """

    # ── 场景1：已删除对象-取消删除（用例405365） ──

    @allure.title("对象存储OSS-已删除对象-取消删除")
    @pytest.mark.parametrize(
        "oss_bucket",
        [{
            "region": "RegionOne",
            "az_strategy": "MULTI_AZ",
            "storage_class": "标准存储",
            "bucket_strategy": "私有",
            "is_encryption": True,
            "data_read": False,
        }],
        indirect=True,
    )
    def test_oss_object_cancel_delete(self, oss_page, ssh_host, oss_bucket):
        """创建桶→开启多版本控制→上传对象→删除对象→取消删除→验证恢复→SSH后端验证。"""
        bucket_name = oss_bucket["name"]
        test_file_name = "test_upload.txt"

        # 准备测试文件路径
        test_data_dir = os.path.join(os.path.dirname(__file__), "..", "test_data")
        test_file_path = os.path.join(test_data_dir, test_file_name)
        assert os.path.exists(test_file_path), \
            f"[BackendAssertion] 测试文件不存在: {test_file_path}"

        with allure_step_log("步骤1: 进入桶详情页并开启多版本控制"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 上传对象"):
            oss_page.oss_bucket_object_tab_click()
            oss_page.oss_bucket_upload_object(bucket_name, test_file_path)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 对象列表未包含 {test_file_name} | 实际列表: {objects}"

        with allure_step_log("步骤3: 删除对象"):
            oss_page.oss_bucket_delete_object(bucket_name, test_file_name)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name not in objects, \
                f"[ListAssertion] 对象 {test_file_name} 删除后仍存在于列表 | 实际列表: {objects}"

        with allure_step_log("步骤4: 查看已删除对象"):
            del_objects = oss_page.oss_bucket_get_deleted_objects(bucket_name)
            assert test_file_name in del_objects, \
                f"[ListAssertion] 已删除对象列表未包含 {test_file_name} | 实际列表: {del_objects}"

        with allure_step_log("步骤5: 取消删除"):
            oss_page.oss_bucket_cancel_delete_object(bucket_name, test_file_name)

        with allure_step_log("步骤6: 验证对象恢复"):
            oss_page.oss_bucket_click_object_tab(bucket_name)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 取消删除后对象未恢复 | 实际列表: {objects}"

        with allure_step_log("步骤7: SSH后端验证文件恢复"):
            result = ssh_host.run("ls /opt/seaweedfs/master/weed", return_rc=True)
            if result["rc"] != 0:
                logger.warning(f"[BackendCheck] weed二进制不存在于/opt/seaweedfs/master/weed，跳过SSH后端验证")
            else:
                result2 = ssh_host.run(
                    f'echo "fs.ls /buckets/{bucket_name}" | /opt/seaweedfs/master/weed shell',
                    return_rc=True,
                )
                assert result2["rc"] == 0, \
                    f"[BackendAssertion] weed shell命令执行失败 | stderr: {result2.get('stderr', '')}"
                assert test_file_name in result2["stdout"] or bucket_name in result2["stdout"], \
                    f"[BackendAssertion] 后端未找到对象 {test_file_name} | stdout: {result2['stdout']}"

    # ── 场景2：已删除对象-彻底删除（用例405366） ──

    @allure.title("对象存储OSS-已删除对象-彻底删除")
    @pytest.mark.parametrize(
        "oss_bucket",
        [{
            "region": "RegionOne",
            "az_strategy": "MULTI_AZ",
            "storage_class": "标准存储",
            "bucket_strategy": "私有",
            "is_encryption": True,
            "data_read": False,
        }],
        indirect=True,
    )
    def test_oss_object_permanent_delete(self, oss_page, ssh_host, oss_bucket):
        """创建桶→开启多版本控制→批量上传3个对象→批量删除→单一彻底删除→批量彻底删除→验证→SSH后端验证。"""
        bucket_name = oss_bucket["name"]
        test_data_dir = os.path.join(os.path.dirname(__file__), "..", "test_data")
        file_names = [
            "batch_file_01.bin",
            "batch_file_02.bin",
            "batch_file_03.bin",
        ]
        file_paths = [os.path.join(test_data_dir, name) for name in file_names]
        for fp in file_paths:
            assert os.path.exists(fp), f"[BackendAssertion] 测试文件不存在: {fp}"

        with allure_step_log("步骤1: 进入桶详情页并开启多版本控制"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 批量上传3个对象"):
            oss_page.oss_bucket_object_tab_click()
            oss_page.oss_bucket_batch_upload(bucket_name, file_paths)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            for fn in file_names:
                assert fn in objects, \
                    f"[ListAssertion] 对象列表未包含 {fn} | 实际列表: {objects}"

        with allure_step_log("步骤3: 批量删除对象"):
            for fn in file_names:
                oss_page.oss_bucket_delete_object(bucket_name, fn)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            for fn in file_names:
                assert fn not in objects, \
                    f"[ListAssertion] 对象 {fn} 删除后仍存在于列表 | 实际列表: {objects}"

        with allure_step_log("步骤4: 查看已删除对象"):
            del_objects = oss_page.oss_bucket_get_deleted_objects(bucket_name)
            for fn in file_names:
                assert fn in del_objects, \
                    f"[ListAssertion] 已删除对象列表未包含 {fn} | 实际列表: {del_objects}"

        with allure_step_log("步骤5: 单一彻底删除"):
            first_obj = file_names[0]
            oss_page.oss_bucket_permanent_delete_object(bucket_name, first_obj, single=True)
            del_objects = oss_page.oss_bucket_get_deleted_objects(bucket_name)
            assert first_obj not in del_objects, \
                f"[ListAssertion] 彻底删除后 {first_obj} 仍存在于已删除列表 | 实际列表: {del_objects}"

        with allure_step_log("步骤6: 批量彻底删除"):
            remaining = file_names[1:]
            for fn in remaining:
                oss_page.oss_bucket_check_deleted_object_row(bucket_name, fn)
            oss_page.oss_bucket_click_batch_permanent_delete(bucket_name)
            del_objects = oss_page.oss_bucket_get_deleted_objects(bucket_name)
            for fn in remaining:
                assert fn not in del_objects, \
                    f"[ListAssertion] 批量彻底删除后 {fn} 仍存在于已删除列表 | 实际列表: {del_objects}"

        with allure_step_log("步骤7: 验证对象已彻底删除"):
            oss_page.oss_bucket_click_object_tab(bucket_name)
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            for fn in file_names:
                assert fn not in objects, \
                    f"[ListAssertion] 对象 {fn} 应已彻底删除，但仍存在于列表 | 实际列表: {objects}"

        with allure_step_log("步骤8: SSH后端验证文件已彻底删除"):
            result = ssh_host.run("ls /opt/seaweedfs/master/weed", return_rc=True)
            if result["rc"] != 0:
                logger.warning(f"[BackendCheck] weed二进制不存在于/opt/seaweedfs/master/weed，跳过SSH后端验证")
            else:
                result2 = ssh_host.run(
                    f'echo "fs.ls /buckets/{bucket_name}" | /opt/seaweedfs/master/weed shell',
                    return_rc=True,
                )
                assert result2["rc"] == 0, \
                    f"[BackendAssertion] weed shell命令执行失败 | stderr: {result2.get('stderr', '')}"
                for fn in file_names:
                    assert fn not in result2["stdout"], \
                        f"[BackendAssertion] 后端仍存在应已彻底删除的对象 {fn} | stdout: {result2['stdout']}"
