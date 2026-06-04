import allure
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic('身份认证IAM')
@allure.feature('组织管理-组织结构树')
@allure.story('创建子组织/修改子组织')
class TestIamOrgChild:

    @allure.title("IAM-组织管理-创建子组织")
    def test_iam_create_child_org(self, iam_page, iam_shared_org, iam_shared_child_org):
        """验证共享子组织存在于父组织下的组织树中。"""
        parent_name = iam_shared_org["org_name"]
        child_name = iam_shared_child_org["child_name"]

        with allure_step_log("步骤1-2: admin登录并进入IAM页面"):
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

        with allure_step_log(f"步骤3: 验证子组织 {child_name} 存在于父组织 {parent_name} 下"):
            iam_page.page.reload()
            iam_page.wait_for_page_ready()

            iam_page.iam_assert_org_in_tree(parent_name)
            tree_container = iam_page.page.locator("#iam-department")
            parent_node = tree_container.locator(".depart_name").filter(
                has_text=parent_name
            )
            parent_node.first.click()
            iam_page.page.wait_for_timeout(1500)

            iam_page.iam_assert_org_in_tree(child_name)
            logger.info(f"验证成功：子组织 {child_name} 存在于组织树中")

    @allure.title("IAM-组织管理-修改子组织")
    def test_iam_modify_child_org(self, iam_page, iam_shared_org, iam_shared_child_org,
                                   iam_shared_user):
        """修改共享子组织名称，更新fixture dict以便后续测试和清理使用新名称。"""
        parent_name = iam_shared_org["org_name"]
        old_name = iam_shared_child_org["child_name"]
        new_name = f"{old_name}-mod"

        with allure_step_log("步骤1-2: admin登录并进入IAM页面"):
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

        with allure_step_log(f"步骤3: 修改子组织名称 {old_name} -> {new_name}"):
            iam_page.iam_modify_organization(old_name, new_name)
            # 更新fixture dict，后续测试和清理均使用新名称
            iam_shared_child_org["child_name"] = new_name
            iam_shared_user["target_org"] = new_name
            logger.info(f"子组织名称已修改，fixture dict已更新为 {new_name}")

        with allure_step_log("步骤4: 验证子组织名称已修改"):
            iam_page.page.reload()
            iam_page.wait_for_page_ready()
            iam_page.page.wait_for_timeout(5000)

            tree_container = iam_page.page.locator("#iam-department")
            parent_node = tree_container.locator(".depart_name").filter(
                has_text=parent_name
            )
            for _ in range(5):
                if parent_node.count() > 0:
                    break
                iam_page.page.wait_for_timeout(1500)
            assert parent_node.count() > 0, f"组织树中未找到父组织 {parent_name}"
            parent_node.first.click()
            iam_page.page.wait_for_timeout(1500)

            new_child = tree_container.locator(".depart_name").filter(
                has_text=new_name
            )
            for _ in range(5):
                if new_child.count() > 0:
                    break
                iam_page.page.wait_for_timeout(1500)
            assert new_child.count() > 0, \
                f"父组织 {parent_name} 下未找到修改后的子组织 {new_name}"
            logger.info(f"验证成功：子组织名称已修改为 {new_name}")
