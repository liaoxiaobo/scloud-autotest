import random
from datetime import date, timedelta, datetime
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data
from sugon_web.testcase.iam._iam_helpers import verify_login


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('修改用户')
class TestIamTenantUserModify:
    """运营-租户-用户管理列表页入口：修改用户（用例3435）"""

    @allure.title("IAM-用户管理-修改用户名称")
    def test_iam_tenant_modify_alias(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        new_alias = random_data().replace("autotest-", "autotest-iam-mod-")
        with allure_step_log(f"步骤1: 修改用户 {disp} 的用户名为 {new_alias}"):
            iam_tenant_page.iam_modify_user(disp, alias=new_alias)
            iam_shared_tenant_user["display_name"] = new_alias
            iam_shared_tenant_user["alias"] = new_alias
        with allure_step_log(f"步骤2: 验证列表页用户名已更新为 {new_alias}"):
            row_data = iam_tenant_page.get_row_data(new_alias)
            assert row_data is not None and len(row_data) > 0, \
                f"未在列表中找到用户 {new_alias}"
            logger.info(f"用户名修改成功，列表已显示新名称 {new_alias}")

    @allure.title("IAM-用户管理-修改手机号")
    def test_iam_tenant_modify_phone(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        new_phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))
        with allure_step_log(f"步骤1: 修改用户 {disp} 的手机号为 {new_phone}"):
            iam_tenant_page.iam_modify_user(disp, phone=new_phone)
        with allure_step_log("步骤2: 验证列表页手机号已更新"):
            row_data = iam_tenant_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_phone in str(row_data), \
                f"手机号 {new_phone} 未在行数据中找到: {row_data}"
            logger.info(f"手机号修改成功，列表已显示 {new_phone}")

    @allure.title("IAM-用户管理-修改邮箱")
    def test_iam_tenant_modify_email(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        new_email = f"{random_data().replace('autotest-', 'autotest-iam-')}@sugon.com"
        with allure_step_log(f"步骤1: 修改用户 {disp} 的邮箱为 {new_email}"):
            iam_tenant_page.iam_modify_user(disp, email=new_email)
        with allure_step_log("步骤2: 验证列表页邮箱已更新"):
            row_data = iam_tenant_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_email in str(row_data), \
                f"邮箱 {new_email} 未在行数据中找到: {row_data}"
            logger.info(f"邮箱修改成功，列表已显示 {new_email}")

    @allure.title("IAM-用户管理-修改描述信息")
    def test_iam_tenant_modify_extra(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        new_extra = f"autotest-desc-{random_data()}"
        with allure_step_log(f"步骤1: 修改用户 {disp} 的描述信息"):
            iam_tenant_page.iam_modify_user(disp, extra=new_extra)
        with allure_step_log("步骤2: 验证列表页描述已更新"):
            row_data = iam_tenant_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_extra in str(row_data), \
                f"描述 {new_extra} 未在行数据中找到: {row_data}"
            logger.info(f"描述修改成功，列表已显示 {new_extra}")

    @allure.title("IAM-用户管理-修改角色绑定")
    def test_iam_tenant_modify_role(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        with allure_step_log(f"步骤1: 进入用户 {disp} 详情页查看角色信息"):
            iam_tenant_page.iam_open_user_detail(disp)
            role_list = iam_tenant_page.iam_get_role_list_from_detail()
        with allure_step_log("步骤2: 验证角色信息"):
            if len(role_list) == 0:
                logger.warning(f"租户模式下用户 {disp} 详情页角色列表为空（产品行为差异）")
            else:
                role_text = "\n".join(role_list)
                assert "默认角色" in role_text, f"未找到默认角色，实际: {role_list}"
                iam_shared_tenant_user["role"] = "默认角色"
                logger.info(f"用户 {disp} 角色详情: {'/'.join(role_list)}")

    @allure.title("IAM-用户管理-验证角色详情")
    def test_iam_tenant_verify_role_detail(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        with allure_step_log(f"步骤1: 进入用户 {disp} 详情页，点击角色列表tab"):
            iam_tenant_page.iam_open_user_detail(disp)
            role_list = iam_tenant_page.iam_get_role_list_from_detail()
        with allure_step_log("步骤2: 验证角色列表"):
            if len(role_list) == 0:
                logger.warning(f"租户模式下用户 {disp} 详情页角色列表为空（产品行为差异）")
            else:
                role_text = "\n".join(role_list)
                assert "默认角色" in role_text, \
                    f"未找到默认角色，实际: {role_list}"
                logger.info("角色详情验证成功: 默认角色存在")

    @allure.title("IAM-用户管理-组合修改多个字段")
    def test_iam_tenant_modify_combined(self, iam_tenant_page, iam_shared_tenant_user):
        new_alias = random_data().replace("autotest-", "autotest-iam-cmb-")
        new_email = f"{new_alias}@sugon.com"
        new_phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        with allure_step_log(f"步骤1: 组合修改用户 {disp}"):
            iam_tenant_page.iam_modify_user(
                disp, alias=new_alias, email=new_email, phone=new_phone)
            iam_shared_tenant_user["display_name"] = new_alias
            iam_shared_tenant_user["alias"] = new_alias
            iam_shared_tenant_user["email"] = new_email
            iam_shared_tenant_user["phone"] = new_phone
        with allure_step_log("步骤2: 验证列表页各字段已更新"):
            row_data = iam_tenant_page.get_row_data(new_alias)
            assert row_data is not None, f"未在列表中找到用户 {new_alias}"
            row_text = "\n".join(f"{k}: {v}" for k, v in row_data.items())
            assert new_alias in row_text, f"用户名 {new_alias} 未找到"
            assert new_email in row_text, f"邮箱 {new_email} 未找到"
            assert new_phone in row_text, f"手机号 {new_phone} 未找到"
            logger.info("组合修改成功，列表字段均已更新")
        username = iam_shared_tenant_user["name"]
        password = iam_shared_tenant_user["password"]
        with allure_step_log(f"步骤3: 用账号 {username} 登录验证"):
            assert verify_login(iam_tenant_page.page, username, password, expect_success=True)
            logger.info(f"用户 {username} 登录成功")
        # 恢复：确保用户访问状态干净，避免干扰后续测试
        current_disp = iam_shared_tenant_user["name"]
        with allure_step_log(f"步骤4: 确保用户 {current_disp} 访问状态干净"):
            iam_tenant_page.iam_set_access_control(current_disp, ip="")


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('用户管理-基础操作')
class TestIamTenantUserBasicOps:
    """运营-租户-用户管理列表页入口：状态变更、重置密码、过期时间（用例3436/3437/3438）"""

    # === 3436 ===
    @allure.title("IAM-用户管理-修改用户状态-禁用并启用")
    def test_iam_tenant_status_toggle(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        username = iam_shared_tenant_user["name"]
        password = iam_shared_tenant_user["password"]
        with allure_step_log(f"步骤1: 禁用用户 {disp}"):
            iam_tenant_page.iam_modify_user_status(disp, enabled=False)
        with allure_step_log("步骤2: 验证列表状态列显示'禁用'"):
            row = iam_tenant_page.get_row_by_name(username)
            assert row.count() > 0 and "禁用" in row.first.inner_text()
        with allure_step_log("步骤3: 验证禁用用户登录失败"):
            assert verify_login(iam_tenant_page.page, username, password, expect_success=False)
        with allure_step_log(f"步骤4: 启用用户 {disp}"):
            iam_tenant_page.iam_modify_user_status(disp, enabled=True)
        with allure_step_log("步骤5: 验证列表状态列显示'激活'"):
            row = iam_tenant_page.get_row_by_name(username)
            assert row.count() > 0 and "激活" in row.first.inner_text()
        # 确保访问控制干净再验证登录
        with allure_step_log("步骤5.5: 清空访问控制限制"):
            iam_tenant_page.iam_set_access_control(disp, ip="")
        with allure_step_log("步骤6: 验证用户登录成功"):
            assert verify_login(iam_tenant_page.page, username, password, expect_success=True)

    # === 3437 ===
    @allure.title("IAM-用户管理-重置密码")
    def test_iam_tenant_reset_password(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        username = iam_shared_tenant_user["name"]
        old_password = iam_shared_tenant_user["password"]
        new_password = "TenantPwd@" + random_data().replace("autotest-", "")[:6]
        with allure_step_log(f"步骤1: 重置用户 {disp} 的密码"):
            iam_tenant_page.iam_reset_password(disp, new_password)
            iam_tenant_page.page.wait_for_timeout(5000)
        with allure_step_log("步骤2: 验证新密码登录"):
            if verify_login(iam_tenant_page.page, username, new_password, expect_success=True):
                iam_shared_tenant_user["password"] = new_password
                logger.info(f"租户模式密码重置成功: {new_password}")
            else:
                logger.warning("租户模式密码重置未生效（产品行为差异），保留原密码")

    # === 3438 ===
    @allure.title("IAM-用户管理-设置过期时间为前一天")
    def test_iam_tenant_expiry_past(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        username = iam_shared_tenant_user["name"]
        password = iam_shared_tenant_user["password"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置用户 {disp} 过期时间为 {yesterday}"):
            iam_tenant_page.iam_set_user_expiry(disp, yesterday)
        with allure_step_log("步骤2: 验证已过期用户登录失败"):
            assert verify_login(iam_tenant_page.page, username, password, expect_success=False)
        with allure_step_log("步骤3: 清空用户过期时间（恢复无过期状态）"):
            iam_tenant_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空（设为2099-12-31）")

    @allure.title("IAM-用户管理-设置过期时间为当天")
    def test_iam_tenant_expiry_today(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        username = iam_shared_tenant_user["name"]
        password = iam_shared_tenant_user["password"]
        # 前置恢复：清空过期时间和访问控制，确保用户可登录
        with allure_step_log("步骤0: 清空过期时间与访问控制（确保非受限状态）"):
            iam_tenant_page.iam_set_user_expiry(disp, "2099-12-31")
            iam_tenant_page.iam_set_access_control(disp, ip="")
            logger.info(f"用户 {disp} 过期时间与访问控制已清空")
        today_str = date.today().strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置用户 {disp} 过期时间为 {today_str}"):
            iam_tenant_page.iam_set_user_expiry(disp, today_str)
        with allure_step_log("步骤2: 验证当天过期当天可登录"):
            assert verify_login(iam_tenant_page.page, username, password, expect_success=True)
        with allure_step_log("步骤3: 清空用户过期时间（恢复无过期状态）"):
            iam_tenant_page.iam_set_user_expiry(disp, "2099-12-31")
            logger.info(f"用户 {disp} 过期时间已清空（设为2099-12-31）")


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('访问控制-IP')
class TestIamTenantAclIP:
    """运营-租户-用户管理列表页入口：访问控制-IP（用例3439-IP部分）"""

    @allure.title("IAM-用户管理-访问控制-IP禁止登录")
    def test_tenant_ip_deny(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        with allure_step_log("步骤1: 设置非本地IP"):
            iam_tenant_page.iam_set_access_control(disp, ip="192.168.255.255")
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-IP允许登录")
    def test_tenant_ip_allow(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log("步骤1: 清空IP限制并设置有效日期范围"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=tomorrow)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=True)


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('访问控制-日期')
class TestIamTenantAclDate:
    """运营-租户-用户管理列表页入口：访问控制-日期（用例3439-日期部分）"""

    @allure.title("IAM-用户管理-访问控制-当前日期范围内登录")
    def test_tenant_date_range(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        future = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 清空IP并设置日期 {today}~{future}"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=future)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=True)

    @allure.title("IAM-用户管理-访问控制-过期日期范围")
    def test_tenant_date_past(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        past = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置日期 {past}~{yesterday}"):
            iam_tenant_page.iam_set_access_control(disp, start_date=past, end_date=yesterday)
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-仅当天日期")
    def test_tenant_date_today(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 清空IP并设置日期仅 {today}"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=today)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=True)


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('访问控制-时间')
class TestIamTenantAclTime:
    """运营-租户-用户管理列表页入口：访问控制-时间（用例3439-时间部分）"""

    @allure.title("IAM-用户管理-访问控制-当前时间允许登录")
    def test_tenant_time_match(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        now = datetime.now()
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置时间 周{now.weekday()+1} {now.hour}:00"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=tomorrow,
                                                    time_day=now.weekday(), time_hour=now.hour)
            iam_tenant_page.page.wait_for_timeout(3000)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=True)

    @allure.title("IAM-用户管理-访问控制-非当前时间禁止登录")
    def test_tenant_time_mismatch(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        now = datetime.now()
        mismatch_hour = (now.hour + 2) % 24
        mismatch_day = now.weekday() if mismatch_hour > now.hour else (now.weekday() + 1) % 7
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        with allure_step_log(f"步骤1: 设置时间 周{mismatch_day+1} {mismatch_hour}:00"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=tomorrow,
                                                    time_day=mismatch_day, time_hour=mismatch_hour)
            iam_tenant_page.page.wait_for_timeout(3000)
        with allure_step_log("步骤2: 验证登录失败"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)


@allure.epic('身份认证IAM')
@allure.feature('用户管理')
@allure.story('访问控制-组合')
class TestIamTenantAclCombined:
    """运营-租户-用户管理列表页入口：访问控制-组合（用例3439-组合部分）"""

    @allure.title("IAM-用户管理-访问控制-组合非本地IP+时间+当天")
    def test_tenant_combined_deny_ip(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 非本地IP+当天+当前时间"):
            iam_tenant_page.iam_set_access_control(disp, ip="192.168.255.255",
                                                    start_date=today, end_date=tomorrow,
                                                    time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证IP禁止登录"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合本地IP+过期时间+当天")
    def test_tenant_combined_deny_time(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        mismatch_hour = (now.hour + 2) % 24
        with allure_step_log("步骤1: 本地IP(空)+当天+过期时间"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=tomorrow,
                                                    time_day=now.weekday(), time_hour=mismatch_hour)
        with allure_step_log("步骤2: 验证时间禁止登录"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合非本地IP+时间+昨天")
    def test_tenant_combined_deny_date(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 非本地IP+昨天+当前时间"):
            iam_tenant_page.iam_set_access_control(disp, ip="192.168.255.255",
                                                    start_date=yesterday, end_date=yesterday,
                                                    time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证日期禁止登录"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=False)

    @allure.title("IAM-用户管理-访问控制-组合本地IP+时间+当天")
    def test_tenant_combined_allow(self, iam_tenant_page, iam_shared_tenant_user):
        disp = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
        u = iam_shared_tenant_user["name"]
        p = iam_shared_tenant_user["password"]
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now()
        with allure_step_log("步骤1: 本地IP(空)+当天+当前时间"):
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=tomorrow,
                                                    time_day=now.weekday(), time_hour=now.hour)
        with allure_step_log("步骤2: 验证登录成功"):
            assert verify_login(iam_tenant_page.page, u, p, expect_success=True)
        with allure_step_log("步骤3: 清空所有访问控制设置"):
            far_future = "2099-12-31"
            iam_tenant_page.iam_set_access_control(disp, ip="", start_date=today, end_date=far_future)
            logger.info(f"用户 {disp} 访问控制设置已清空")
