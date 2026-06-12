from datetime import date, timedelta
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.pages.login import LoginPage
from sugon_web.config.config import Config
from sugon_web.testcase.iam._iam_helpers import verify_login


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('用户管理-基础操作')
class TestIamUserBasicOps:

    # === 3436 ===
    @allure.title("IAM-用户管理-修改用户状态-禁用并启用")
    def test_iam_user_status_toggle(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        username = iam_shared_user["name"]
        password = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]

        with allure_step_log(f"步骤1: 禁用用户 {disp}"):
            iam_page.iam_modify_user_status(disp, enabled=False, target_org=child_org)
        with allure_step_log("步骤2: 验证列表状态列显示'禁用'"):
            row = iam_page.get_row_by_name(username)
            assert row.count() > 0 and "禁用" in row.first.inner_text()
        with allure_step_log("步骤3: 验证禁用用户登录失败"):
            assert verify_login(iam_page.page, username, password, expect_success=False)
        with allure_step_log(f"步骤4: 启用用户 {disp}"):
            iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
            iam_page.iam_modify_user_status(disp, enabled=True)
        with allure_step_log("步骤5: 验证列表状态列显示'激活'"):
            row = iam_page.get_row_by_name(username)
            assert row.count() > 0 and "激活" in row.first.inner_text()
        with allure_step_log("步骤6: 验证用户登录成功"):
            assert verify_login(iam_page.page, username, password, expect_success=True)

    # === 3437 ===
    @allure.title("IAM-用户管理-重置密码")
    def test_iam_reset_password(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        username = iam_shared_user["name"]
        old_password = iam_shared_user["password"]
        new_password = "NewPwd@5678"
        child_org = iam_shared_child_org["child_name"]

        with allure_step_log(f"步骤1: 重置用户 {disp} 的密码"):
            iam_page.iam_reset_password(disp, new_password)
            iam_page.wait_for_page_ready()
        # 先更新密码记录，确保即使后续验证失败，fixture 也知道新密码
        iam_shared_user["password"] = new_password

        with allure_step_log("步骤2: 旧密码登录应失败"):
            assert verify_login(iam_page.page, username, old_password, expect_success=False)
        with allure_step_log("步骤3: 新密码登录应成功"):
            assert verify_login(iam_page.page, username, new_password, expect_success=True)

    # === 3438 ===
    @allure.title("IAM-用户管理-设置过期时间为前一天")
    def test_iam_user_expiry_past(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        username = iam_shared_user["name"]
        password = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置用户 {disp} 过期时间为 {yesterday}"):
            iam_page.iam_set_user_expiry(disp, yesterday)
        with allure_step_log("步骤2: 验证已过期用户登录失败"):
            assert verify_login(iam_page.page, username, password, expect_success=False)

        # 恢复：清空过期时间，避免影响后续测试
        with allure_step_log("步骤3: 清空用户过期时间（恢复无过期状态）"):
            iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
            iam_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空（设为2099-12-31）")

    @allure.title("IAM-用户管理-设置过期时间为当天")
    def test_iam_user_expiry_today(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        username = iam_shared_user["name"]
        password = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today_str = date.today().strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置用户 {disp} 过期时间为 {today_str}"):
            iam_page.iam_set_user_expiry(disp, today_str)
        with allure_step_log("步骤2: 验证登录失败（当天过期）"):
            assert verify_login(iam_page.page, username, password, expect_success=False)

        # 恢复：清空过期时间，避免影响后续测试
        with allure_step_log("步骤3: 清空用户过期时间（恢复无过期状态）"):
            iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
            iam_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空（设为2099-12-31）")

    @allure.title("IAM-用户管理-设置过期时间为明天")
    def test_iam_user_expiry_future(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        username = iam_shared_user["name"]
        password = iam_shared_user["password"]

        # 前置恢复：先清空过期时间，确保用户非过期状态（前序测试可能已设置过期）
        with allure_step_log("步骤0: 清空用户过期时间（确保非过期状态）"):
            iam_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置用户 {disp} 过期时间为 {tomorrow}"):
            iam_page.iam_set_user_expiry(disp, tomorrow)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, username, password, expect_success=True)

        # 恢复：清空过期时间，避免影响后续访问控制测试
        with allure_step_log("步骤3: 清空用户过期时间（恢复无过期状态）"):
            iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
            iam_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空（设为2099-12-31）")
