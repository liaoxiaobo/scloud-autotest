import os

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-文件夹内批量上传功能验证')
class TestOBSBatchUploadInFolder:

    @allure.title("对象存储-文件夹内批量上传多个对象")
    def test_obs_batch_upload_in_folder(self, obs_page, bucket):
        # 准备5个测试文件路径（每个约15M，满足10M~100M要求）
        test_data_dir = os.path.join(
            os.path.dirname(__file__), "..", "test_data"
        )
        file_names = [
            "batch_file_01.bin",
            "batch_file_02.bin",
            "batch_file_03.bin",
            "batch_file_04.bin",
            "batch_file_05.bin",
        ]
        file_paths = [os.path.join(test_data_dir, name) for name in file_names]
        # 验证测试文件存在
        for fp in file_paths:
            assert os.path.exists(fp), f"测试文件不存在: {fp}"

        folder_name = random_data()

        with allure_step_log("步骤1: 进入桶详情页并切换到对象tab"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.wait_for_page_ready()
            obs_page.page.wait_for_timeout(3000)

        with allure_step_log("步骤2: 新建文件夹"):
            obs_page.obs_folder_create(folder_name)
            # 验证文件夹出现在对象列表中
            obs_page.assert_object_list_contain(folder_name)

        with allure_step_log("步骤3: 进入文件夹"):
            obs_page.obs_object_enter_folder(folder_name)
            # 验证进入文件夹成功：页面URL应包含文件夹相关信息或路径指示
            # 新创建的文件夹内对象列表为空，因此不验证列表内容
            obs_page.page.wait_for_timeout(2000)

        with allure_step_log("步骤4: 批量上传5个文件"):
            obs_page.obs_object_batch_upload(file_paths)

        with allure_step_log("步骤5: 验证上传结果"):
            # 大文件批量上传需要较长时间等待后台处理
            obs_page.page.wait_for_timeout(15000)
            # 验证每个文件都出现在对象列表中（带重试，处理异步刷新）
            for file_name in file_names:
                try:
                    obs_page.assert_object_list_contain(file_name)
                except AssertionError:
                    # 异步刷新可能未完全完成，等待后重试一次
                    obs_page.page.wait_for_timeout(5000)
                    obs_page.assert_object_list_contain(file_name)

        with allure_step_log("清理: 删除文件夹"):
            # 通过导航重新进入桶对象列表（避免 obs_object_back_to_list 面包屑导航异常）
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.wait_for_page_ready()

            # 删除文件夹
            obs_page.obs_folder_delete(folder_name)
            # 验证文件夹已删除
            obs_page.assert_deleted(folder_name)
