import os
import tempfile

import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('对象管理-对象和文件夹复制路径')
class TestOSSObjectFolderCopyPath:
    """验证OSS对象存储对象和文件夹复制路径功能。

    两个场景各自独立创建和清理资源，测试数据不可复用。
    """

    # ── 场景1：桶根目录下对象复制路径（用例405347） ──

    @allure.title("对象存储OSS-桶根目录下对象复制路径")
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
    def test_oss_object_copy_path_root(self, oss_page, oss_bucket):
        """在桶根目录上传对象，复制路径，验证路径仅包含对象名。"""
        bucket_name = oss_bucket["name"]
        test_file_name = "test01.txt"
        # 准备测试文件路径
        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        test_file_path = os.path.join(test_data_dir, "test_upload.txt")
        assert os.path.exists(test_file_path), \
            f"[BackendAssertion] 测试文件不存在: {test_file_path}"

        with allure_step_log("步骤1: 进入桶详情页对象tab"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()
            # 确保在对象列表页
            if "/object" not in oss_page.page.url:
                oss_page.oss_bucket_object_tab_click()

        with allure_step_log("步骤2: 上传对象"):
            # 使用临时文件重命名为 test01.txt
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, test_file_name)
            with open(test_file_path, "rb") as src:
                with open(temp_file_path, "wb") as dst:
                    dst.write(src.read())
            oss_page.oss_bucket_upload_object(bucket_name, temp_file_path)
            # 清理临时文件
            os.remove(temp_file_path)

        with allure_step_log("步骤3: 验证对象存在"):
            # 上传方法内部已轮询等待对象出现，此处直接验证
            # 先等待页面加载完成，避免读取到桶列表数据
            oss_page.wait_for_page_ready()
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 对象列表未包含 {test_file_name} | 实际列表: {objects}"

        with allure_step_log("步骤4: 复制对象路径并验证"):
            copied_path = oss_page.oss_bucket_copy_object_path(bucket_name, test_file_name)
            assert copied_path is not None, \
                "[PathAssertion] 复制路径失败，未获取到路径值"
            assert copied_path == test_file_name, \
                f"[PathAssertion] 复制路径不匹配 | 期望: {test_file_name} | 实际: {copied_path}"

        # 清理：对象由桶 fixture teardown 统一处理（删除桶时自动删除对象）

    # ── 场景2：文件夹内对象复制路径（用例405347） ──

    @allure.title("对象存储OSS-文件夹内对象复制路径")
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
    def test_oss_object_copy_path_in_folder(self, oss_page, oss_bucket):
        """新建文件夹，进入文件夹上传对象，复制路径，验证路径包含完整路径。"""
        bucket_name = oss_bucket["name"]
        folder_name = f"folder-{random_data()}"
        test_file_name = "test02.txt"

        # 准备测试文件
        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        test_file_path = os.path.join(test_data_dir, "test_upload.txt")
        assert os.path.exists(test_file_path), \
            f"[BackendAssertion] 测试文件不存在: {test_file_path}"

        with allure_step_log("步骤1: 进入桶详情页对象tab"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()

        with allure_step_log("步骤2: 新建文件夹"):
            oss_page.oss_bucket_create_folder(bucket_name, folder_name)
            # 验证文件夹出现在对象列表中
            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert folder_name in objects, \
                f"[ListAssertion] 对象列表未包含文件夹 {folder_name} | 实际列表: {objects}"

        with allure_step_log("步骤3: 进入文件夹并上传对象"):
            oss_page.oss_bucket_enter_folder(bucket_name, folder_name)
            # 使用临时文件重命名为 test02.txt
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, test_file_name)
            with open(test_file_path, "rb") as src:
                with open(temp_file_path, "wb") as dst:
                    dst.write(src.read())
            oss_page.oss_bucket_upload_object(bucket_name, temp_file_path, folder_path=folder_name)
            # 清理临时文件
            os.remove(temp_file_path)

        with allure_step_log("步骤4: 验证对象存在于文件夹中"):
            # 此时页面应在文件夹内，直接获取当前页对象列表
            objects = oss_page.oss_bucket_get_objects(bucket_name, folder_path=folder_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 文件夹内对象列表未包含 {test_file_name} | 实际列表: {objects}"

        with allure_step_log("步骤5: 复制对象路径并验证"):
            copied_path = oss_page.oss_bucket_copy_object_path(bucket_name, test_file_name, folder_path=folder_name)
            assert copied_path is not None, \
                "[PathAssertion] 复制路径失败，未获取到路径值"
            # 根据前端代码分析，objectKey 对于文件夹内对象格式为 folderName/objectName
            # 不包含桶名前缀
            expected_path = f"{folder_name}/{test_file_name}"
            assert copied_path == expected_path, \
                f"[PathAssertion] 复制路径不匹配 | 期望: {expected_path} | 实际: {copied_path}"

        # 清理：先删除文件夹内对象，再删除文件夹，最后桶由 fixture teardown 删除
        with allure_step_log("清理: 删除文件夹及内部对象"):
            # 关闭可能打开的任务中心抽屉或其他弹窗
            oss_page.page.evaluate("""
                () => {
                    // 关闭 el-drawer
                    const drawers = document.querySelectorAll('.el-drawer__wrapper, .el-drawer__container');
                    for (const drawer of drawers) {
                        const closeBtn = drawer.querySelector('.el-drawer__close-btn, .el-icon-close');
                        if (closeBtn) closeBtn.click();
                    }
                    // 关闭 el-dialog
                    const dialogs = document.querySelectorAll('.el-dialog__wrapper, .cv-dialog');
                    for (const dialog of dialogs) {
                        const closeBtn = dialog.querySelector('.el-dialog__close, .el-icon-close');
                        if (closeBtn) closeBtn.click();
                    }
                    // 点击遮罩层关闭
                    const masks = document.querySelectorAll('.el-overlay, .v-modal');
                    for (const mask of masks) {
                        mask.click();
                    }
                }
            """)
            oss_page.wait_for_page_ready()

            # 检查是否已在文件夹内，避免重复进入
            path_diag = oss_page.page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        if (el.__vue__ && el.__vue__.$store && el.__vue__.$store.state.current_objectPath) {
                            const paths = el.__vue__.$store.state.current_objectPath;
                            return { hasPath: true, pathCount: paths.length, lastPath: paths.length > 0 ? paths[paths.length - 1].data.objectKey : '' };
                        }
                    }
                    return { hasPath: false };
                }
            """)
            already_in_folder = path_diag.get('hasPath') and path_diag.get('lastPath') == folder_name
            if not already_in_folder:
                oss_page.oss_bucket_enter_folder(bucket_name, folder_name)
            oss_page.oss_bucket_delete_object(bucket_name, test_file_name, folder_path=folder_name)

            # 删除文件夹（oss_bucket_delete_folder 会自行导航到桶根目录）
            oss_page.oss_bucket_delete_folder(bucket_name, folder_name)
