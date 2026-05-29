import os
import re

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-文件夹分享提取码验证')
class TestOBSFolderShare:

    @allure.title("对象存储-文件夹分享-提取码生效验证")
    def test_obs_folder_share_extract_code(self, obs_page, bucket, page):
        """验证文件夹分享功能，包括创建分享链接、复制链接验证、打开URL验证。"""
        folder_name = f"folder-{random_data()}"
        test_data_dir = os.path.join(os.path.dirname(__file__), "..", "test_data")
        batch_files = [
            os.path.join(test_data_dir, f"batch_file_{i:02d}.bin")
            for i in range(1, 6)
        ]
        extract_code = "123456"

        with allure_step_log("步骤1: 进入桶详情页并新建文件夹"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            expect(obs_page.page).to_have_url(
                re.compile(r"/detail|/bucket")
            )
            obs_page.obs_object_tab_click()
            obs_page.obs_folder_create(folder_name)
            obs_page.assert_list_contain(folder_name)

        with allure_step_log("步骤2: 进入文件夹并批量上传对象"):
            obs_page.obs_object_enter_folder(folder_name)
            obs_page.obs_object_batch_upload(batch_files)
            for f in batch_files:
                fname = os.path.basename(f)
                obs_page.assert_object_list_contain(fname)

        with allure_step_log("步骤3: 返回对象列表并打开分享弹窗"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.assert_list_contain(folder_name)
            obs_page.obs_folder_share_open(folder_name)

        with allure_step_log("步骤4: 设置分享参数并创建分享链接"):
            obs_page.obs_folder_share_set_expiration(500)
            obs_page.obs_folder_share_set_code(extract_code)
            share_link, actual_code = obs_page.obs_folder_share_create_link()
            assert share_link, "分享链接为空"
            assert share_link.startswith("http"), (
                f"分享链接格式不正确: {share_link}"
            )
            assert actual_code == extract_code, (
                f"提取码不匹配: 期望 {extract_code}, 实际 {actual_code}"
            )

        with allure_step_log("步骤5: 验证分享弹窗按钮展示"):
            dialog = obs_page._get_share_dialog(is_folder=True)
            expect(
                dialog.first.get_by_text("复制链接", exact=True)
            ).to_be_visible()
            expect(
                dialog.first.get_by_text("打开URL", exact=True)
            ).to_be_visible()

        with allure_step_log("步骤6: 验证复制链接生效"):
            new_page = page.context.new_page()
            new_page.goto(share_link)
            new_page.wait_for_timeout(3000)
            code_input = new_page.get_by_placeholder("请输入6位数字提取码")
            expect(code_input).to_be_visible(timeout=10000)
            code_input.fill(extract_code)
            new_page.get_by_text("获取分享目录列表", exact=True).click()
            new_page.wait_for_timeout(3000)
            for f in batch_files:
                fname = os.path.basename(f)
                expect(
                    new_page.get_by_text(fname).first
                ).to_be_visible(timeout=10000)
            new_page.close()

        with allure_step_log("步骤7: 验证打开URL生效"):
            obs_page.page.evaluate("""
                () => {
                    window._capturedUrls = [];
                    const originalOpen = window.open;
                    window.open = function(url, target) {
                        if (url) window._capturedUrls.push(url);
                        return originalOpen.apply(this, arguments);
                    };
                    return 'ok';
                }
            """)
            obs_page.obs_folder_share_open_url()
            obs_page.page.wait_for_timeout(3000)
            captured_urls = obs_page.page.evaluate(
                "() => window._capturedUrls || []"
            )
            assert captured_urls and len(captured_urls) > 0, (
                "未捕获到打开URL的链接"
            )
            url = captured_urls[0]
            new_page2 = page.context.new_page()
            new_page2.goto(url)
            new_page2.wait_for_timeout(3000)
            code_input2 = new_page2.get_by_placeholder("请输入6位数字提取码")
            expect(code_input2).to_be_visible(timeout=10000)
            code_input2.fill(extract_code)
            new_page2.get_by_text("获取分享目录列表", exact=True).click()
            new_page2.wait_for_timeout(3000)
            for f in batch_files:
                fname = os.path.basename(f)
                expect(
                    new_page2.get_by_text(fname).first
                ).to_be_visible(timeout=10000)
            new_page2.close()

        with allure_step_log("步骤8: 关闭分享弹窗"):
            obs_page.obs_folder_share_close()

        with allure_step_log("清理: 删除文件夹及对象"):
            obs_page.obs_object_tab_click()
            obs_page.obs_object_enter_folder(folder_name)
            for f in batch_files:
                fname = os.path.basename(f)
                obs_page.obs_object_delete(fname)
                obs_page.assert_deleted(fname)
            obs_page.obs_object_back_to_list(bucket["name"])
            obs_page.obs_folder_delete(folder_name)
            obs_page.assert_deleted(folder_name)
