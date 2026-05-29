import random
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data
from sugon_web.testcase.iam._iam_helpers import verify_login


@allure.epic('身份认证IAM')
@allure.feature('组织管理-用户管理')
@allure.story('修改用户')
class TestIamUserModify:

    @allure.title("IAM-用户管理-修改用户名称")
    def test_iam_modify_user_alias(self, iam_page, iam_shared_user):
        """场景3.1：修改用户名称为新值，验证列表页字段更新。"""
        new_alias = random_data().replace("autotest-", "autotest-iam-mod-")
        current_display = iam_shared_user["display_name"]

        with allure_step_log(f"步骤1: 修改用户 {current_display} 的用户名为 {new_alias}"):
            iam_page.iam_modify_user(current_display, alias=new_alias)
            iam_shared_user["display_name"] = new_alias
            iam_shared_user["alias"] = new_alias

        with allure_step_log(f"步骤2: 验证列表页用户名已更新为 {new_alias}"):
            row_data = iam_page.get_row_data(new_alias)
            assert row_data is not None and len(row_data) > 0, \
                f"未在列表中找到用户 {new_alias}"
            logger.info(f"用户名修改成功，列表已显示新名称 {new_alias}")

    @allure.title("IAM-用户管理-修改手机号")
    def test_iam_modify_user_phone(self, iam_page, iam_shared_user):
        """场景3.2：修改手机号，验证列表页手机号字段更新。"""
        disp = iam_shared_user["display_name"]
        new_phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))

        with allure_step_log(f"步骤1: 修改用户 {disp} 的手机号为 {new_phone}"):
            iam_page.iam_modify_user(disp, phone=new_phone)

        with allure_step_log(f"步骤2: 验证列表页手机号已更新"):
            row_data = iam_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_phone in str(row_data), \
                f"手机号 {new_phone} 未在行数据中找到: {row_data}"
            logger.info(f"手机号修改成功，列表已显示 {new_phone}")

    @allure.title("IAM-用户管理-修改邮箱")
    def test_iam_modify_user_email(self, iam_page, iam_shared_user):
        """场景3.3：修改邮箱，验证列表页邮箱字段更新。"""
        disp = iam_shared_user["display_name"]
        new_email = f"{random_data().replace('autotest-', 'autotest-iam-')}@sugon.com"

        with allure_step_log(f"步骤1: 修改用户 {disp} 的邮箱为 {new_email}"):
            iam_page.iam_modify_user(disp, email=new_email)

        with allure_step_log(f"步骤2: 验证列表页邮箱已更新"):
            row_data = iam_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_email in str(row_data), \
                f"邮箱 {new_email} 未在行数据中找到: {row_data}"
            logger.info(f"邮箱修改成功，列表已显示 {new_email}")

    @allure.title("IAM-用户管理-修改描述信息")
    def test_iam_modify_user_extra(self, iam_page, iam_shared_user):
        """场景3.4：修改描述信息为随机内容，验证列表页描述字段更新。"""
        disp = iam_shared_user["display_name"]
        new_extra = f"autotest-desc-{random_data()}"

        with allure_step_log(f"步骤1: 修改用户 {disp} 的描述信息"):
            iam_page.iam_modify_user(disp, extra=new_extra)

        with allure_step_log(f"步骤2: 验证列表页描述已更新"):
            row_data = iam_page.get_row_data(disp)
            assert row_data is not None, f"未在列表中找到用户 {disp}"
            assert new_extra in str(row_data), \
                f"描述 {new_extra} 未在行数据中找到: {row_data}"
            logger.info(f"描述修改成功，列表已显示 {new_extra}")

    @allure.title("IAM-用户管理-修改角色绑定")
    def test_iam_modify_user_role(self, iam_page, iam_shared_user):
        """场景3.5：修改角色绑定为非默认角色，验证弹窗关闭提示成功。"""
        disp = iam_shared_user["display_name"]
        with allure_step_log(f"步骤1: 修改用户 {disp} 的角色绑定"):
            result = iam_page.iam_modify_user(disp, role="__non_default__")
            if result.get("role"):
                iam_shared_user["role"] = result["role"]

        with allure_step_log("步骤2: 验证角色绑定修改成功"):
            assert iam_shared_user["role"] != "默认角色", \
                "角色绑定未修改为非默认角色"
            logger.info(f"角色绑定修改成功，新角色: {iam_shared_user['role']}")

    @allure.title("IAM-用户管理-验证角色详情")
    def test_iam_verify_role_detail(self, iam_page, iam_shared_user):
        """场景3.6：进入用户详情页角色列表tab，验证角色名称与场景5一致。"""
        disp = iam_shared_user["display_name"]
        with allure_step_log(f"步骤1: 进入用户 {disp} 详情页，点击角色列表tab"):
            iam_page.iam_open_user_detail(disp)
            role_list = iam_page.iam_get_role_list_from_detail()

        with allure_step_log("步骤2: 验证角色名称"):
            assert len(role_list) > 0, "角色列表为空"
            assert iam_shared_user["role"] in "\n".join(role_list), \
                f"角色列表中未找到 {iam_shared_user['role']}，实际: {role_list}"
            logger.info(f"角色详情验证成功: {iam_shared_user['role']}")

    @allure.title("IAM-用户管理-组合修改多个字段")
    def test_iam_modify_user_combined(self, iam_page, iam_shared_user):
        """场景3.7+场景8：同时修改用户名、邮箱、手机号，并用账号登录验证。"""
        new_alias = random_data().replace("autotest-", "autotest-iam-cmb-")
        new_email = f"{new_alias}@sugon.com"
        new_phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))

        disp = iam_shared_user["display_name"]
        with allure_step_log(f"步骤1: 组合修改用户 {disp}"):
            iam_page.iam_modify_user(
                disp,
                alias=new_alias,
                email=new_email,
                phone=new_phone,
            )
            iam_shared_user["display_name"] = new_alias
            iam_shared_user["alias"] = new_alias
            iam_shared_user["email"] = new_email
            iam_shared_user["phone"] = new_phone

        with allure_step_log("步骤2: 验证列表页各字段已更新"):
            row_data = iam_page.get_row_data(new_alias)
            assert row_data is not None, \
                f"未在列表中找到用户 {new_alias}"
            row_text = "\n".join(f"{k}: {v}" for k, v in row_data.items())
            assert new_alias in row_text, f"用户名 {new_alias} 未找到"
            assert new_email in row_text, f"邮箱 {new_email} 未找到"
            assert new_phone in row_text, f"手机号 {new_phone} 未找到"
            logger.info(f"组合修改成功，列表字段均已更新")

        # 场景8：修改后登录验证（合并在组合修改内，避免跨测试 state 问题）
        username = iam_shared_user["name"]  # 账号，不可修改
        password = iam_shared_user["password"]

        with allure_step_log(f"步骤3: 用账号 {username} 登录验证"):
            assert verify_login(iam_page.page, username, password, expect_success=True)
            logger.info(f"用户 {username} 登录成功")
