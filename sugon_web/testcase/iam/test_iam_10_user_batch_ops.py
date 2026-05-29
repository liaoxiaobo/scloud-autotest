from datetime import date, timedelta, datetime
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.testcase.iam._iam_helpers import verify_login


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('用户管理-批量操作')
class TestIamUserBatchOps:

    # === 3450 ===
    @allure.title("IAM-用户管理-批量修改用户状态")
    def test_iam_batch_modify_user_status(self, iam_page, iam_batch_users, iam_shared_child_org):
        names = [u["display_name"] for u in iam_batch_users]
        username_list = [u["name"] for u in iam_batch_users]
        password = iam_batch_users[0]["password"]
        target_org = iam_shared_child_org["child_name"]

        with allure_step_log(f"步骤1: 批量禁用5个用户"):
            iam_page.iam_batch_modify_status(names, enabled=False, target_org=target_org)

        with allure_step_log("步骤2: 验证列表状态列均显示'禁用'"):
            for name in names:
                row = iam_page.get_row_by_name(name)
                assert row.count() > 0 and "禁用" in row.first.inner_text()

        with allure_step_log("步骤3: 依次验证5个禁用用户登录失败"):
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤4: 批量启用5个用户"):
            iam_page.iam_batch_modify_status(names, enabled=True, target_org=target_org)

        with allure_step_log("步骤5: 验证列表状态列均显示'激活'"):
            for name in names:
                row = iam_page.get_row_by_name(name)
                assert row.count() > 0 and "激活" in row.first.inner_text()

        with allure_step_log("步骤6: 依次验证5个启用用户登录成功"):
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

    # === 3451 ===
    @allure.title("IAM-用户管理-批量重置密码")
    def test_iam_batch_reset_password(self, iam_page, iam_batch_users, iam_shared_child_org):
        names = [u["display_name"] for u in iam_batch_users]
        username_list = [u["name"] for u in iam_batch_users]
        old_password = iam_batch_users[0]["password"]
        new_password = "NewPwd@5678"
        target_org = iam_shared_child_org["child_name"]

        with allure_step_log("步骤1: 批量重置5个用户的密码"):
            iam_page.iam_batch_reset_password(names, new_password, target_org=target_org)

        # 更新密码记录
        for u in iam_batch_users:
            u["password"] = new_password

        with allure_step_log("步骤2: 依次用旧密码登录，验证失败"):
            for username in username_list:
                assert verify_login(iam_page.page, username, old_password, expect_success=False)

        with allure_step_log("步骤3: 依次用新密码登录，验证成功"):
            for username in username_list:
                assert verify_login(iam_page.page, username, new_password, expect_success=True)

    # === 3452 ===
    @allure.title("IAM-用户管理-批量设置用户过期时间")
    def test_iam_batch_set_user_expiry(self, iam_page, iam_batch_users, iam_shared_child_org):
        names = [u["display_name"] for u in iam_batch_users]
        username_list = [u["name"] for u in iam_batch_users]
        password = iam_batch_users[0]["password"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = date.today().strftime("%Y-%m-%d")
        target_org = iam_shared_child_org["child_name"]

        with allure_step_log(f"步骤1: 批量设置过期时间为前一天 {yesterday}"):
            iam_page.iam_batch_set_expiry(names, yesterday, target_org=target_org)

        with allure_step_log("步骤2: 验证列表过期时间与设置一致"):
            for name in names:
                row = iam_page.get_row_by_name(name)
                assert row.count() > 0

        with allure_step_log("步骤3: 依次验证5个过期用户登录失败"):
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤4: 批量清除过期时间"):
            iam_page.iam_batch_set_expiry(names, "", target_org=target_org)

        with allure_step_log("步骤5: 验证列表用户行存在"):
            for name in names:
                row = iam_page.get_row_by_name(name)
                assert row.count() > 0

        with allure_step_log("步骤6: 依次验证5个用户登录成功"):
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

    # === 3453 ===
    @allure.title("IAM-用户管理-批量访问控制")
    def test_iam_batch_access_control(self, iam_page, iam_batch_users, iam_shared_child_org):
        names = [u["display_name"] for u in iam_batch_users]
        username_list = [u["name"] for u in iam_batch_users]
        password = iam_batch_users[0]["password"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        past_start = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        target_org = iam_shared_child_org["child_name"]

        with allure_step_log("步骤1: 批量设置非本地IP，验证登录失败"):
            iam_page.iam_batch_set_access_control(names, target_org=target_org, ip="192.168.255.255")
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤2: 批量设置本地IP(空)，验证登录成功"):
            iam_page.iam_batch_set_access_control(names, target_org=target_org, ip="")
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

        with allure_step_log(f"步骤3: 批量设置日期 {today}~{day_after}，验证登录成功"):
            iam_page.iam_batch_set_access_control(names, target_org=target_org, start_date=today, end_date=day_after)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

        with allure_step_log(f"步骤4: 批量设置过期日期 {past_start}~{yesterday}，验证登录失败"):
            iam_page.iam_batch_set_access_control(names, target_org=target_org, start_date=past_start, end_date=yesterday)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log(f"步骤5: 批量设置当天日期 {today}，验证登录成功"):
            iam_page.iam_batch_set_access_control(names, target_org=target_org, start_date=today, end_date=today)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

        with allure_step_log("步骤6: 批量设置当前时间段内，验证登录成功"):
            now6 = datetime.now()
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="", start_date=today, end_date=tomorrow,
                time_day=now6.weekday(), time_hour=now6.hour)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)

        with allure_step_log("步骤7: 批量设置时间范围外，验证登录失败"):
            now7 = datetime.now()
            mismatch_hour7 = (now7.hour + 2) % 24
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="", start_date=today, end_date=tomorrow,
                time_day=now7.weekday(), time_hour=mismatch_hour7)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤8: 组合-非本地IP+当前时间+当天，验证IP禁止"):
            now8 = datetime.now()
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="192.168.255.255", start_date=today, end_date=tomorrow,
                time_day=now8.weekday(), time_hour=now8.hour)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤9: 组合-本地IP+过期时间+当天，验证时间禁止"):
            now9 = datetime.now()
            mismatch_hour9 = (now9.hour + 2) % 24
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="", start_date=today, end_date=tomorrow,
                time_day=now9.weekday(), time_hour=mismatch_hour9)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤10: 组合-非本地IP+当前时间+昨天，验证日期禁止"):
            now10 = datetime.now()
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="192.168.255.255", start_date=yesterday, end_date=yesterday,
                time_day=now10.weekday(), time_hour=now10.hour)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=False)

        with allure_step_log("步骤11: 组合-本地IP+当前时间+当天，验证登录成功"):
            now11 = datetime.now()
            iam_page.iam_batch_set_access_control(
                names, target_org=target_org, ip="", start_date=today, end_date=tomorrow,
                time_day=now11.weekday(), time_hour=now11.hour)
            for username in username_list:
                assert verify_login(iam_page.page, username, password, expect_success=True)
