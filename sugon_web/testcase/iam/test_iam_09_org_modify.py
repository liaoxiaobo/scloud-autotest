import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('身份认证IAM')
@allure.feature('组织管理-组织结构树')
@allure.story('修改一级组织')
class TestIamOrgModify:

    @allure.title("IAM-组织管理-修改一级组织名称")
    def test_iam_modify_org_name(self, iam_page, iam_shared_org):
        """修改一级组织名称并验证组织结构树中名称已更新。"""
        old_name = iam_shared_org["org_name"]
        new_name = f"{old_name}_mod_{random_data()}"

        with allure_step_log("步骤1: 进入IAM组织管理页面"):
            iam_page.goto_service("统一身份认证IAM")
            iam_page.wait_for_page_ready()

        with allure_step_log("步骤2: 修改一级组织名称"):
            iam_page.iam_modify_organization(old_name, new_name)

        with allure_step_log("步骤3: 验证组织结构树显示新名称"):
            iam_page.iam_assert_org_in_tree(new_name)

        # 更新共享组织名称，确保后续操作和 teardown 使用最新名称
        iam_shared_org["org_name"] = new_name
        logger.info(f"共享组织名称已更新: {old_name} -> {new_name}")
