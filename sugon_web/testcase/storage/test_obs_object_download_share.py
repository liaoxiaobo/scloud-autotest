import hashlib
import os
import tempfile

import allure

from sugon_web.testcase.storage._obs_download_helpers import (
    _capture_opened_urls,
    _download_file_via_request,
    _wait_for_generated_url,
)
from sugon_web.utils.logger import allure_step_log


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-下载及分享功能验证')
class TestOBSObjectDownloadShare:

    @allure.title("对象存储-下载对象并验证")
    def test_obs_object_download(self, obs_page, bucket):
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)

        # 计算原始文件 MD5
        with open(test_file_path, "rb") as f:
            original_md5 = hashlib.md5(f.read()).hexdigest()

        # 先上传对象
        with allure_step_log("前置: 上传测试对象"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.wait_for_page_ready()
            obs_page.assert_object_list_contain(test_file_name)

        with allure_step_log("步骤1: 点击下载对象"):
            tmp_dir = tempfile.gettempdir()
            download_url = _wait_for_generated_url(
                obs_page.page,
                ["objects/url", "objects/share-url"],
                trigger=lambda: obs_page.obs_object_download(test_file_name),
                timeout=30,
            )

            downloaded_path = None
            if download_url:
                downloaded_path = os.path.join(tmp_dir, test_file_name)
                if not _download_file_via_request(
                    obs_page.page.request, download_url, downloaded_path
                ):
                    downloaded_path = None

        with allure_step_log("步骤2: 验证下载文件MD5"):
            assert downloaded_path and os.path.exists(downloaded_path), \
                f"下载文件不存在"
            with open(downloaded_path, "rb") as f:
                download_md5 = hashlib.md5(f.read()).hexdigest()
            assert download_md5 == original_md5, \
                f"MD5不匹配，原始: {original_md5}, 下载: {download_md5}"

        with allure_step_log("清理: 删除上传的对象"):
            obs_page.obs_object_delete(test_file_name)
            obs_page.assert_deleted(test_file_name)

    @allure.title("对象存储-分享对象-复制链接下载验证")
    def test_obs_object_share_copy_link(self, obs_page, bucket):
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)

        # 计算原始文件 MD5
        with open(test_file_path, "rb") as f:
            original_md5 = hashlib.md5(f.read()).hexdigest()

        # 先上传对象
        with allure_step_log("前置: 上传测试对象"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.wait_for_page_ready()
            obs_page.assert_object_list_contain(test_file_name)

        with allure_step_log("步骤1: 打开分享弹窗并设置有效期"):
            obs_page.obs_object_share_open(test_file_name)
            obs_page.obs_object_share_set_expiration(500)

        with allure_step_log("步骤2: 创建分享链接"):
            share_link = obs_page.obs_object_share_create_link()
            assert share_link, "分享链接为空"
            assert share_link.startswith("http"), f"分享链接格式不正确: {share_link}"

        with allure_step_log("步骤3: 新tab打开分享链接并验证下载"):
            downloaded_path = os.path.join(tempfile.gettempdir(), test_file_name)
            assert _download_file_via_request(
                obs_page.page.request, share_link, downloaded_path
            ), "下载文件不存在"
            with open(downloaded_path, "rb") as f:
                download_md5 = hashlib.md5(f.read()).hexdigest()
            assert download_md5 == original_md5, \
                f"MD5不匹配，原始: {original_md5}, 下载: {download_md5}"

        with allure_step_log("步骤4: 关闭分享弹窗"):
            obs_page.obs_object_share_close()

        with allure_step_log("清理: 删除上传的对象"):
            obs_page.obs_object_delete(test_file_name)
            obs_page.assert_deleted(test_file_name)

    @allure.title("对象存储-分享对象-打开URL下载验证")
    def test_obs_object_share_open_url(self, obs_page, bucket):
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)

        # 计算原始文件 MD5
        with open(test_file_path, "rb") as f:
            original_md5 = hashlib.md5(f.read()).hexdigest()

        # 先上传对象
        with allure_step_log("前置: 上传测试对象"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.wait_for_page_ready()
            obs_page.assert_object_list_contain(test_file_name)

        with allure_step_log("步骤1: 打开分享弹窗并创建链接"):
            obs_page.obs_object_share_open(test_file_name)
            obs_page.obs_object_share_set_expiration(500)
            share_link = obs_page.obs_object_share_create_link()
            assert share_link, "分享链接为空"

        with allure_step_log("步骤2: 点击打开URL并验证下载"):
            tmp_dir = tempfile.gettempdir()
            captured_urls = _capture_opened_urls(
                obs_page.page,
                obs_page.obs_object_share_open_url,
                timeout=30,
            )

            downloaded_path = None
            if captured_urls:
                downloaded_path = os.path.join(tmp_dir, test_file_name)
                if not _download_file_via_request(
                    obs_page.page.request, captured_urls[0], downloaded_path
                ):
                    downloaded_path = None

            assert downloaded_path and os.path.exists(downloaded_path), \
                "下载文件不存在"
            with open(downloaded_path, "rb") as f:
                download_md5 = hashlib.md5(f.read()).hexdigest()
            assert download_md5 == original_md5, \
                f"MD5不匹配，原始: {original_md5}, 下载: {download_md5}"

        with allure_step_log("步骤3: 关闭分享弹窗"):
            obs_page.obs_object_share_close()

        with allure_step_log("清理: 删除上传的对象"):
            obs_page.obs_object_delete(test_file_name)
            obs_page.assert_deleted(test_file_name)
