import os

import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('对象管理-上传对象与新建文件夹')
class TestOSSUploadObjectAndCreateFolder:
    """验证OSS对象存储上传对象与新建文件夹功能。

    两个场景共享同一桶资源，所有用例执行完成后统一清理。
    """

    # ── 场景1：桶内上传对象（用例6338） ──

    @allure.title("对象存储OSS-桶内上传对象")
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
    def test_oss_bucket_upload_object(self, oss_page, ssh_host, oss_bucket):
        """在桶内上传1个小于10M的对象并验证对象存在。"""
        bucket_name = oss_bucket["name"]
        test_file_name = "test_upload.txt"
        # 准备测试文件路径（使用 os.path.join 正确计算相对路径）
        test_data_dir = os.path.join(os.path.dirname(__file__), "..", "test_data")
        test_file_path = os.path.join(test_data_dir, test_file_name)
        assert os.path.exists(test_file_path), f"[BackendAssertion] 测试文件不存在: {test_file_path}"

        with allure_step_log("步骤1: 进入桶详情页对象tab"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            # 通过桶列表页点击进入详情页
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_object_tab_click()

        with allure_step_log("步骤2: 上传对象"):
            oss_page.oss_bucket_upload_object(bucket_name, test_file_path)

        with allure_step_log("步骤3: 验证对象存在"):
            # 等待对象列表异步刷新（oss_bucket_get_objects 内部已轮询）
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 对象列表未包含 {test_file_name} | 实际列表: {objects}"

        # 对象清理由桶 fixture teardown 统一处理（删除桶时自动删除对象）

    # ── 场景2：新建文件夹且批量上传对象（用例6341） ──

    @allure.title("对象存储OSS-新建文件夹且批量上传对象")
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
    def test_oss_bucket_create_folder_and_batch_upload(
        self, oss_page, ssh_host, oss_bucket
    ):
        """新建文件夹，进入文件夹后批量上传5个对象并验证。"""
        bucket_name = oss_bucket["name"]
        folder_name = f"folder-{random_data()}"

        # 准备5个测试文件路径（15MB，满足10M~100M要求）
        test_data_dir = os.path.join(os.path.dirname(__file__), "..", "test_data")
        file_names = [
            "batch_file_01.bin",
            "batch_file_02.bin",
            "batch_file_03.bin",
            "batch_file_04.bin",
            "batch_file_05.bin",
        ]
        file_paths = [os.path.join(test_data_dir, name) for name in file_names]
        for fp in file_paths:
            assert os.path.exists(fp), f"[BackendAssertion] 测试文件不存在: {fp}"

        with allure_step_log("步骤1: 进入桶详情页对象tab"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            # 通过桶列表页点击进入详情页
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_object_tab_click()

        with allure_step_log("步骤2: 新建文件夹"):
            oss_page.oss_bucket_create_folder(bucket_name, folder_name)
            # 验证文件夹出现在对象列表中
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert folder_name in objects, \
                f"[ListAssertion] 对象列表未包含文件夹 {folder_name} | 实际列表: {objects}"

        with allure_step_log("步骤3: 进入文件夹"):
            oss_page.oss_bucket_enter_folder(bucket_name, folder_name)

        with allure_step_log("步骤4: 批量上传5个文件"):
            oss_page.oss_bucket_batch_upload(bucket_name, file_paths)

        with allure_step_log("步骤5: 验证上传结果"):
            # 验证每个文件都出现在对象列表中
            objects = oss_page.oss_bucket_get_objects(bucket_name, folder_path=folder_name)
            for file_name in file_names:
                assert file_name in objects, \
                    f"[ListAssertion] 对象列表未包含 {file_name} | 实际列表: {objects}"

        # 清理：删除文件夹（先删除文件夹内对象，再删除文件夹）
        with allure_step_log("清理: 删除文件夹及内部对象"):
            # 导航回桶对象列表
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            # 通过桶列表页点击进入详情页
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_object_tab_click()

            # 删除文件夹内对象
            for file_name in file_names:
                oss_page.oss_bucket_delete_object(bucket_name, file_name, folder_path=folder_name)

            # 删除文件夹
            oss_page.oss_bucket_delete_folder(bucket_name, folder_name)
