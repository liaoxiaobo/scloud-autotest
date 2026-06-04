import re

import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-生命周期管理-创建规则功能验证')
class TestOBSBucketLifecycle:

    @allure.title("对象存储-创建桶内所有对象生命周期规则")
    def test_obs_bucket_lifecycle_create_all_objects(self, obs_page, bucket):
        """验证在桶内创建'所有对象'类型的生命周期规则功能。"""
        rule_name = random_data()

        with allure_step_log("步骤1: 进入桶详情页"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            expect(obs_page.page).to_have_url(
                re.compile(r"/detail|/bucket")
            )

        with allure_step_log("步骤2: 进入生命周期管理页面"):
            obs_page.obs_bucket_lifecycle_config_click()
            expect(
                obs_page.page.get_by_text("生命周期管理", exact=True).first
            ).to_be_visible()

        with allure_step_log("步骤3: 创建生命周期规则"):
            obs_page.obs_lifecycle_create_rule_all_objects(
                rule_name=rule_name,
                expiration_days=1,
                fragment_days=1,
                start_time="17:00",
                end_time="18:00",
            )

        with allure_step_log("步骤4: 验证生命周期规则列表"):
            # 生命周期管理页面使用 cl-table 组件，BasePage 表格方法不适用
            # 直接通过页面文本断言规则存在
            expect(
                obs_page.page.get_by_text(rule_name, exact=True).first
            ).to_be_visible(timeout=10000)
            # 验证对象属性列显示"桶内所有对象"
            table = obs_page.page.locator(".cl-table-body, .el-table__body-wrapper").first
            rule_row = table.locator("tr").filter(has_text=rule_name).first
            expect(rule_row).to_be_visible(timeout=5000)
            assert "桶内所有对象" in rule_row.inner_text(), (
                f"对象属性不匹配，期望包含'桶内所有对象'"
            )
