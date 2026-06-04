import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.pages.login import LoginPage
from sugon_web.config.config import Config


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('创建普通用户')
class TestIamUserCreate:

    @allure.title("IAM-用户管理-创建普通用户")
    def test_iam_create_user(self, iam_page, iam_shared_user, iam_shared_child_org):
        """验证共享IAM用户可登录。"""
        username = iam_shared_user["name"]
        user_password = iam_shared_user["password"]
        child_org = iam_shared_child_org["child_name"]
        login = LoginPage(iam_page.page)
        admin_password = "keystone_sugon"

        with allure_step_log("步骤1: 进入统一身份认证IAM页面"):
            iam_page.wait_for_page_ready()
            assert "/iam" in iam_page.page.url, \
                f"未导航到 IAM 页面，当前 URL: {iam_page.page.url}"
            logger.info(f"已进入 IAM 页面: {iam_page.page.url}")

        with allure_step_log(f"步骤2: 验证用户 {username} 存在于用户列表中"):
            user_list = iam_page.iam_get_user_list(target_org=child_org)
            assert any(username in user for user in user_list), \
                f"用户 {username} 未在列表中找到，列表内容: {user_list[:5]}..."
            logger.info(f"用户 {username} 已在列表中找到")

        with allure_step_log(f"步骤3: 退出登录并使用 {username} 重新登录验证"):
            base_url = Config.get("base_url")
            iam_page.page.goto(base_url)
            iam_page.wait_for_page_ready()
            login.logout()
            logger.info("已退出 admin 登录")
            iam_page.page.wait_for_timeout(1000)
            login.login(username, user_password)
            iam_page.wait_for_page_ready()
            assert "login" not in iam_page.page.url.lower(), \
                f"用户 {username} 登录失败，当前 URL: {iam_page.page.url}"
            logger.info(f"用户 {username} 登录成功")

        with allure_step_log("步骤4: 恢复admin登录状态"):
            base_url = Config.get("base_url")
            iam_page.page.goto(f"{base_url}/#/login")
            iam_page.wait_for_page_ready()
            login.login("admin", admin_password)
            iam_page.wait_for_page_ready()
            logger.info("已恢复admin登录状态")
