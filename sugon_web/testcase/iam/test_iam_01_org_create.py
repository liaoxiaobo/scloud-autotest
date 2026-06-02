import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.pages.login import LoginPage
from sugon_web.config.config import Config


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
        base_url = Config.get("base_url")

        with allure_step_log("步骤1: admin登录并进入IAM页面"):
            page_title = iam_page.page.locator(
                ".cloud-page-header-title, .page-title, h1"
            ).first
            if page_title.count() > 0:
                title_text = page_title.inner_text()
                assert "统一身份认证" in title_text or "IAM" in title_text, \
                    f"未进入IAM页面，当前标题: {title_text}"
            else:
                assert "iam" in iam_page.page.url.lower(), "未进入IAM页面"
            logger.info("admin已登录并进入IAM页面")

        with allure_step_log(f"步骤2: 验证组织 {org_name} 存在于组织树中"):
            iam_page.page.reload()
            iam_page.wait_for_page_ready()
            iam_page.iam_assert_org_in_tree(org_name)
            logger.info(f"组织 {org_name} 已在组织树中")

        with allure_step_log(f"步骤3: 使用组织管理员 {username} 登录云平台"):
            login = LoginPage(iam_page.page)
            login.logout()
            iam_page.page.wait_for_timeout(2000)
            login.login(username, password)
            iam_page.page.wait_for_timeout(5000)
            assert "login" not in iam_page.page.url.lower(), \
                f"用户 {username} 登录失败，仍在登录页"
            logger.info(f"用户 {username} 登录成功")

        with allure_step_log("步骤4: 访问弹性云服务器页面"):
            iam_page.goto_service("弹性云服务器")
            try:
                iam_page.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            iam_page.page.wait_for_timeout(3000)
            page_content = ""
            for _ in range(3):
                page_content = iam_page.page.content()
                if "弹性云服务器" in page_content or "ECS" in page_content or "未绑定项目" in page_content:
                    break
                iam_page.page.wait_for_timeout(2000)
            assert "未绑定项目" in page_content or "无权访问" in page_content or \
                   "弹性云服务器" in page_content or "ECS" in page_content, \
                "未进入弹性云服务器页面"
            if "未绑定项目" in page_content or "无权访问" in page_content:
                logger.info("弹性云服务器页面显示未绑定项目/无权访问，符合预期")
            else:
                logger.info("弹性云服务器页面访问成功")

        # 恢复 admin 登录状态（后续测试依赖 admin 登录态）
        with allure_step_log("恢复admin登录状态"):
            try:
                login.logout()
                iam_page.page.wait_for_timeout(2000)
            except Exception:
                pass
            iam_page.page.goto(f"{base_url}/#/login")
            iam_page.page.wait_for_timeout(3000)
            login.login("admin", "keystone_sugon")
            iam_page.page.wait_for_timeout(3000)
            logger.info("已恢复admin登录状态")
