import os

import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-删除桶功能验证')
class TestOBSBucketDelete:

    @pytest.mark.parametrize("bucket", [{"count": 3}], indirect=True)
    @allure.title("对象存储-删除桶功能验证")
    def test_obs_bucket_delete_validation(self, obs_page, bucket, page):
        """验证桶不为空时删除桶失败，桶为空时批量删除桶成功。"""
        bucket01, bucket02, bucket03 = bucket[0]["name"], bucket[1]["name"], bucket[2]["name"]
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        folder_name = random_data()

        # ------------------ 前置：选择项目 ------------------
        with allure_step_log("前置: 选择公共测试项目"):
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")

        # ------------------ 场景1：桶内含有空文件夹无法删除桶 ------------------
        with allure_step_log("场景1: 桶内含有空文件夹无法删除桶"):
            # 1.1 进入 bucket01 创建文件夹
            obs_page.obs_bucket_enter_detail(bucket01)
            obs_page.obs_object_tab_click()
            obs_page.obs_folder_create(folder_name)
            obs_page.assert_object_list_contain(folder_name)

            # 1.2 返回桶列表，尝试删除 bucket01
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_delete(bucket01)
            # 关闭可能存在的错误弹窗
            obs_page.close_dialog_if_exists()
            obs_page.page.keyboard.press("Escape")
            obs_page.page.wait_for_timeout(2000)
            # 验证桶仍在列表中（删除失败的核心断言）
            obs_page.assert_list_contain(bucket01)

        # ------------------ 场景2：桶内包含对象无法删除桶 ------------------
        with allure_step_log("场景2: 桶内包含对象无法删除桶"):
            # 2.1 进入 bucket02 上传对象
            obs_page.obs_bucket_enter_detail(bucket02)
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_object_list_contain("test_upload.txt")

            # 2.2 返回桶列表，尝试删除 bucket02
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_delete(bucket02)
            # 关闭可能存在的错误弹窗
            obs_page.close_dialog_if_exists()
            obs_page.page.keyboard.press("Escape")
            obs_page.page.wait_for_timeout(2000)
            # 验证桶仍在列表中
            obs_page.assert_list_contain(bucket02)

        # ------------------ 场景3：桶内同时包含文件夹和对象无法删除桶 ------------------
        with allure_step_log("场景3: 桶内同时包含文件夹和对象无法删除桶"):
            # 3.1 进入 bucket03 上传对象并创建文件夹
            obs_page.obs_bucket_enter_detail(bucket03)
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.page.wait_for_timeout(3000)
            obs_page.obs_folder_create(folder_name + "_2")
            obs_page.assert_object_list_contain("test_upload.txt")
            obs_page.assert_object_list_contain(folder_name + "_2")

            # 3.2 返回桶列表，尝试删除 bucket03
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_delete(bucket03)
            # 关闭可能存在的错误弹窗
            obs_page.close_dialog_if_exists()
            obs_page.page.keyboard.press("Escape")
            obs_page.page.wait_for_timeout(2000)
            # 验证桶仍在列表中
            obs_page.assert_list_contain(bucket03)

        # ------------------ 场景4：桶内无文件夹和对象时删除桶 ------------------
        with allure_step_log("场景4: 桶内无文件夹和对象时删除桶"):
            # 4.1 依次清空 bucket01、bucket02、bucket03
            for b in [bucket01, bucket02, bucket03]:
                obs_page.goto_submenu("桶列表")
                obs_page._obs_bucket_empty(b)
                obs_page.page.wait_for_timeout(1000)

            # 4.2 返回桶列表，勾选三个桶，点击更多操作-批量删除
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_batch_delete([bucket01, bucket02, bucket03])

            # 4.3 验证桶已被删除
            obs_page.assert_deleted(bucket01)
            obs_page.assert_deleted(bucket02)
            obs_page.assert_deleted(bucket03)
