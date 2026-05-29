import os
import re

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-上传对象设置元数据功能验证')
class TestOBSObjectUploadMetadata:

    @allure.title("对象存储-上传对象时设置元数据")
    def test_obs_object_upload_with_metadata(self, obs_page, bucket):
        """验证上传对象时设置元数据，上传成功后可在对象详情页查看元数据。"""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)
        metadata_key = f"meta-{random_data(length=6)}"
        metadata_value = f"value-{random_data(length=6)}"

        with allure_step_log("步骤1: 进入桶详情页"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            expect(obs_page.page).to_have_url(
                re.compile(r"/detail|/bucket")
            )

        with allure_step_log("步骤2: 切换到对象tab"):
            obs_page.obs_object_tab_click()

        with allure_step_log("步骤3: 上传文件并设置元数据"):
            obs_page.obs_object_upload_with_metadata(
                test_file_path,
                [{"key": metadata_key, "value": metadata_value}]
            )

        with allure_step_log("步骤4: 验证对象上传成功"):
            obs_page.assert_list_contain(test_file_name)

        with allure_step_log("步骤5: 进入对象详情页并查看元数据"):
            obs_page.obs_object_enter_detail(test_file_name)
            obs_page.obs_object_detail_click_metadata_tab()

        with allure_step_log("步骤6: 验证元数据名称和值"):
            actual_value = obs_page.obs_object_metadata_get_value(metadata_key)
            assert actual_value == metadata_value, (
                f"元数据值不匹配: 期望 '{metadata_value}', 实际 '{actual_value}'"
            )

        with allure_step_log("步骤7: 清理上传的对象"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_delete(test_file_name)
