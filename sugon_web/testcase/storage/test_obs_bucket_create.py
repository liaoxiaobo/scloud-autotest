import re

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-基本功能验证')
class TestOBSBucketCreate:

    @allure.title("对象存储-创建桶取消")
    def test_obs_bucket_create_cancel(self, obs_page):
        bucket_name = random_data()

        with allure_step_log("步骤1: 导航到OBS，顶部导航栏选择项目，进入新建桶页面"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试"
            )
            obs_page.goto_submenu("桶列表")
            obs_page.btn_create.click()
            obs_page.wait_for_page_ready()
            expect(obs_page.page).to_have_url(re.compile(r"/store/list/create"))

        with allure_step_log("步骤2: 在业务属性模块查看项目名称"):
            obs_page.assert_form_project_displayed("公共测试")

        with allure_step_log("步骤3: 在区域模块查看默认区域"):
            region_name = obs_page._get_selected_region_name()
            assert region_name == "RegionOne", f"区域应为'RegionOne'，实际为'{region_name}'"

        with allure_step_log("步骤4: 在桶配置模块填写桶名称和桶容量"):
            obs_page._input_bucket_name.fill(bucket_name)
            obs_page._input_bucket_capacity.fill("10")

        with allure_step_log("步骤5: 选择标准存储并核对选项状态"):
            # 主动点击标准存储选项
            obs_page.page.get_by_text("标准存储", exact=True).first.click()
            performance_enabled = obs_page._get_storage_class_state("性能存储")
            extreme_enabled = obs_page._get_storage_class_state("极致性能存储")
            assert not performance_enabled, "性能存储应置灰不可选"
            assert not extreme_enabled, "极致性能存储应置灰不可选"

        with allure_step_log("步骤6: 点击取消并验证桶未创建"):
            obs_page._btn_cancel_page.click()
            obs_page.wait_for_page_ready()
            expect(obs_page.page).to_have_url(re.compile(r"/store/list"))
            obs_page.assert_list_not_contain(bucket_name)

    @allure.title("对象存储-创建桶成功并验证")
    def test_obs_bucket_create_success(self, obs_page):
        bucket_name = random_data()

        with allure_step_log("步骤1: 导航到OBS，选择项目，验证默认区域"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试"
            )
            obs_page.goto_submenu("桶列表")
            # 临时打开创建页验证区域
            obs_page.btn_create.click()
            obs_page.wait_for_page_ready()
            region_name = obs_page._get_selected_region_name()
            assert region_name == "RegionOne", f"区域应为'RegionOne'，实际为'{region_name}'"
            # 使用子菜单导航返回列表页，避免取消按钮可能带来的页面状态不稳定
            obs_page.goto_submenu("桶列表")
            obs_page.wait_for_page_ready()

        with allure_step_log("步骤2: 创建桶"):
            # 使用 Page Object 方法（含30秒轮询+回退机制）
            obs_page.obs_bucket_create(bucket_name, capacity="10")

        with allure_step_log("步骤3: 校验桶列表显示信息"):
            obs_page.goto_submenu("桶列表")
            obs_page.assert_list_contain(bucket_name)
            row_data = obs_page.get_row_data(bucket_name)
            assert row_data.get("桶存储类别") == "标准存储", \
                f"桶存储类别不匹配，期望'标准存储'，实际'{row_data.get('桶存储类别')}'"
            assert "可用" in row_data.get("状态", ""), \
                f"桶状态不匹配，期望包含'可用'，实际'{row_data.get('状态')}'"
            assert row_data.get("项目") == "公共测试", \
                f"项目不匹配，期望'公共测试'，实际'{row_data.get('项目')}'"

        with allure_step_log("步骤4: 清理测试数据"):
            obs_page.obs_bucket_delete(bucket_name)
            obs_page.assert_deleted(bucket_name)
