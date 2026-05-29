import os
import re

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-上传对象功能验证')
class TestOBSObjectUpload:

    @allure.title("对象存储-上传小文件对象")
    def test_obs_object_upload_small_file(self, obs_page, bucket):
        # 准备测试文件路径
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)

        with allure_step_log("步骤1: 进入桶详情页"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            expect(obs_page.page).to_have_url(
                re.compile(r"/detail|/bucket")
            )

        with allure_step_log("步骤2: 切换到对象tab并点击上传对象"):
            obs_page.obs_object_tab_click()
            obs_page.page.get_by_text("上传对象", exact=True).first.click()
            obs_page.page.wait_for_timeout(1500)
            # 验证上传弹窗出现
            dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
                has_text="上传对象"
            )
            expect(dialog.first).to_be_visible(timeout=10000)

        with allure_step_log("步骤3: 添加文件到上传弹窗"):
            # 通过文件input设置文件
            file_input = obs_page.page.locator('input[type="file"]')
            file_input.set_input_files(test_file_path)
            obs_page.page.wait_for_timeout(1500)
            # 验证文件名出现在弹窗中
            expect(obs_page.page.get_by_text(test_file_name).first).to_be_visible(
                timeout=5000
            )

        with allure_step_log("步骤4: 执行上传并验证对象列表"):
            obs_page.page.get_by_text("立即上传", exact=True).first.click()
            obs_page.page.wait_for_timeout(5000)
            # 验证对象列表中存在上传的文件
            obs_page.assert_list_contain(test_file_name)

        # 对象清理由 bucket fixture teardown 统一处理（删除桶时自动删除对象）
