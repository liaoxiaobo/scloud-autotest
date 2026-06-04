from datetime import date, timedelta, datetime
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.testcase.iam._iam_helpers import verify_login


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('访问控制-IP')
class TestAclIP:
    @allure.title("IAM-用户管理-访问控制-IP禁止登录")
    def test_ip_deny(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        with allure_step_log("步骤1: 设置非本地IP"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="192.168.255.255")
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-IP允许登录")
    def test_ip_allow(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        with allure_step_log("步骤1: 清空IP限制"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="")
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, u, p, expect_success=True)


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('访问控制-日期')
class TestAclDate:
    @allure.title("IAM-用户管理-访问控制-当前日期范围内登录")
    def test_date_range(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today = date.today().strftime("%Y-%m-%d")
        future = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置日期 {today}~{future}"):
            iam_page.iam_set_access_control(disp, target_org=child_org, start_date=today, end_date=future)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, u, p, expect_success=True)

    @allure.title("IAM-用户管理-访问控制-过期日期范围")
    def test_date_past(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        past = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置日期 {past}~{yesterday}"):
            iam_page.iam_set_access_control(disp, target_org=child_org, start_date=past, end_date=yesterday)
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-未来日期范围")
    def test_date_future(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置日期 {tomorrow}~{day_after}"):
            iam_page.iam_set_access_control(disp, target_org=child_org, start_date=tomorrow, end_date=day_after)
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-仅当天日期")
    def test_date_today(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today = date.today().strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置日期仅 {today}"):
            iam_page.iam_set_access_control(disp, target_org=child_org, start_date=today, end_date=today)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, u, p, expect_success=True)


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('访问控制-时间')
class TestAclTime:
    @allure.title("IAM-用户管理-访问控制-当前时间允许登录")
    def test_time_match(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        now = datetime.now()
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置时间 周{now.weekday()+1} {now.hour}:00"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="",
                                            start_date=today, end_date=tomorrow,
                                            time_day=now.weekday(), time_hour=now.hour)
            iam_page.page.wait_for_timeout(3000)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, u, p, expect_success=True)

    @allure.title("IAM-用户管理-访问控制-非当前时间禁止登录")
    def test_time_mismatch(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        now = datetime.now()
        mismatch_hour = (now.hour + 2) % 24
        mismatch_day = now.weekday() if mismatch_hour > now.hour else (now.weekday() + 1) % 7
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置时间 周{mismatch_day+1} {mismatch_hour}:00"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="",
                                            start_date=today, end_date=tomorrow,
                                            time_day=mismatch_day, time_hour=mismatch_hour)
            iam_page.page.wait_for_timeout(3000)
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_page.page, u, p, expect_success=False)


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('访问控制-组合')
class TestAclCombined:
    @allure.title("IAM-用户管理-访问控制-组合非本地IP+时间+当天")
    def test_combined_deny_ip(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 非本地IP+当天+当前时间"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="192.168.255.255",
                                            start_date=today, end_date=tomorrow,
                                            time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证IP禁止登录"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合本地IP+过期时间+当天")
    def test_combined_deny_time(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        mismatch_hour = (now.hour + 2) % 24
        with allure_step_log("步骤1: 本地IP(空)+当天+过期时间"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="",
                                            start_date=today, end_date=tomorrow,
                                            time_day=now.weekday(), time_hour=mismatch_hour)
        with allure_step_log("步骤2: 验证时间禁止登录"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合非本地IP+时间+昨天")
    def test_combined_deny_date(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 非本地IP+昨天+当前时间"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="192.168.255.255",
                                            start_date=yesterday, end_date=yesterday,
                                            time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证日期禁止登录"):
            assert verify_login(iam_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合本地IP+时间+当天")
    def test_combined_allow(self, iam_page, iam_shared_user, iam_shared_child_org):
        iam_page._navigate_to_user_management(target_org=iam_shared_user.get("target_org"))
        disp = iam_shared_user["name"]
        u = iam_shared_user["name"]
        p = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 本地IP(空)+当天+当前时间"):
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="",
                                            start_date=today, end_date=tomorrow,
                                            time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_page.page, u, p, expect_success=True)

        # 恢复：清空所有访问控制设置，确保用户可被正常删除
        with allure_step_log("步骤3: 清空所有访问控制设置"):
            far_future = "2099-12-31"
            iam_page.iam_set_access_control(disp, target_org=child_org, ip="",
                                            start_date=today, end_date=far_future)
            logger.info(f"用户 {disp} 访问控制设置已清空")
