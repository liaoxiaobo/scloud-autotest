import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.testcase.iam._iam_helpers import login_as_user, restore_admin_login


@allure.epic('身份认证IAM')
@allure.feature('组织管理-组织结构树')
@allure.story('创建组织')
class TestIamOrgCreate:

    @allure.title("IAM-组织管理-创建组织并验证用户登录")
    def test_iam_create_org_and_login(self, iam_page, iam_shared_org):
        """验证共享顶级组织存在，且组织管理员用户可登录并访问ECS页面。"""
        org_name = iam_shared_org["org_name"]
        username = iam_shared_org["username"]
        password = iam_shared_org["password"]

        with allure_step_log("步骤1: admin登录并进入IAM页面"):
            iam_page.wait_for_page_ready()
            iam_page.iam_assert_page_title()
            logger.info("admin已登录并进入IAM页面")

        with allure_step_log(f"步骤2: 验证组织 {org_name} 存在于组织树中"):
            iam_page.iam_assert_org_in_tree(org_name)

        with allure_step_log(f"步骤3: 使用组织管理员 {username} 登录云平台"):
            login_as_user(iam_page.page, username, password)
            iam_page.wait_for_page_ready()
            assert "login" not in iam_page.page.url.lower(), \
                f"用户 {username} 登录失败，仍在登录页"
            logger.info(f"用户 {username} 登录成功")

        with allure_step_log("步骤4: 访问弹性云服务器页面"):
            iam_page.goto_service("弹性云服务器")
            iam_page.assert_page_content_contains(
                ["弹性云服务器", "ECS", "未绑定项目", "无权访问"],
                timeout=180
            )
            logger.info("弹性云服务器页面访问成功")

        with allure_step_log("恢复admin登录状态"):
            restore_admin_login(iam_page.page)
            logger.info("已恢复admin登录状态")
