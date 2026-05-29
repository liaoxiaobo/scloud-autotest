import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-桶存储策略配置功能验证')
class TestOBSBucketStoragePolicy:

    @allure.title("对象存储-配置桶存储策略并验证生效")
    def test_obs_bucket_storage_policy_configure(self, obs_page, bucket):
        """验证在桶详情页配置存储策略后，策略在列表中正确展示。"""
        rule_name = f"rule-{random_data(length=6)}"

        # ------------------ 步骤1：进入桶详情页 ------------------
        with allure_step_log("步骤1: 进入桶详情页"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])

        # ------------------ 步骤2：进入桶存储策略管理页面 ------------------
        with allure_step_log("步骤2: 进入桶存储策略管理页面"):
            obs_page.obs_bucket_storage_policy_config_click()

        # ------------------ 步骤3~4：新建存储策略 ------------------
        with allure_step_log("步骤3~4: 新建存储策略并填写表单"):
            # 点击新建按钮（兼容新旧版本）
            add_btn = obs_page.page.get_by_text("新建", exact=True)
            if add_btn.count() == 0:
                add_btn = obs_page.page.get_by_text("添加存储策略")
            add_btn.first.click()
            obs_page.page.wait_for_timeout(1500)

            dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
                has_text="新建存储策略"
            ).first
            # 验证弹窗可见
            assert dialog.is_visible(), "新建存储策略弹窗未显示"

            # 输入策略名称
            dialog.locator('input[placeholder*="请输入策略名称"]').fill(rule_name)
            obs_page.page.wait_for_timeout(300)

            # 选择对象属性：桶内所有对象
            dialog.get_by_text("桶内所有对象", exact=True).first.click()
            obs_page.page.wait_for_timeout(500)

            # 存储类别保持默认（标准存储）
            # 验证标准存储单选按钮存在
            standard_radio = dialog.get_by_text("标准存储", exact=True)
            assert standard_radio.count() > 0, "未找到标准存储选项"

            # 策略优先级：随机选择可用项
            priority_select = dialog.locator('input[placeholder="请选择策略优先级"]')
            priority_select.click()
            obs_page.page.wait_for_timeout(500)
            selected_priority = obs_page.page.evaluate(
                """
                () => {
                    const items = document.querySelectorAll('.el-select-dropdown__item');
                    const available = [];
                    for (let item of items) {
                        if (!item.classList.contains('is-disabled')) {
                            available.push(item);
                        }
                    }
                    if (available.length > 0) {
                        const idx = Math.floor(Math.random() * available.length);
                        available[idx].click();
                        return available[idx].innerText.trim();
                    }
                    return null;
                }
                """
            )
            assert selected_priority, "没有可用的策略优先级"
            obs_page.page.wait_for_timeout(500)

            # 点击确定
            dialog.get_by_text("确定", exact=True).first.click()
            obs_page.page.wait_for_timeout(3000)
            obs_page.wait_for_page_ready()

        # ------------------ 步骤5：验证存储策略在列表中展示 ------------------
        with allure_step_log("步骤5: 验证存储策略在列表中正确展示"):
            obs_page.obs_storage_policy_assert_contain(rule_name)

            # 额外验证：读取列表行数据确认策略内容
            row_data = obs_page.obs_storage_policy_get_row_data(rule_name)
            assert row_data, f"未找到策略'{rule_name}'的行数据"
            assert "桶内所有对象" in str(row_data.values()), (
                f"策略对象属性不匹配: {row_data}"
            )
            assert "标准存储" in str(row_data.values()), (
                f"策略存储类别不匹配: {row_data}"
            )

        # ------------------ 清理前置：导航回桶列表页 ------------------
        with allure_step_log("清理前置: 导航回桶列表，确保teardown可正常执行"):
            from sugon_web.config.config import Config
            base_url = Config.get("base_url")
            obs_page.page.goto(f"{base_url}/obs/#/store/list")
            obs_page.page.wait_for_load_state("networkidle")
            obs_page.page.wait_for_timeout(2000)
            obs_page.wait_for_page_ready()
