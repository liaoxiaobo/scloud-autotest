import allure
import pytest

from sugon_web.utils.logger import allure_step_log


@allure.epic("存储")
@allure.feature("对象存储OSS")
@allure.story("对象ACL管理")
class TestOssObjectAclManagement:
    """对象存储 OSS 对象 ACL 管理测试类。

    三个场景共享同一源桶 bucket01 和同一对象 test01，对象 ACL 记录
    按场景顺序创建、编辑、删除。
    """

    @allure.title("OSS-新增对象ACL")
    def test_oss_object_acl_create(self, oss_object_acl_page, oss_object_acl_env):
        """场景 405441：新增对象 ACL。"""
        bucket_name = oss_object_acl_env["bucket_name"]
        object_name = oss_object_acl_env["object_name"]
        account_id = oss_object_acl_env["account_id"]

        with allure_step_log("步骤1: 进入对象ACL页面并点击'新建'"):
            oss_object_acl_page.oss_object_acl_goto_page(bucket_name, object_name)
            oss_object_acl_page.oss_object_acl_click_new()
            assert oss_object_acl_page.oss_object_acl_dialog_is_visible("新增账号权限"), \
                "未弹出'新增账号权限'弹窗"

        with allure_step_log("步骤2: 填写账号权限配置并提交"):
            oss_object_acl_page.oss_object_acl_dialog_fill_account(account_id)
            oss_object_acl_page.oss_object_acl_dialog_check_permission("对象访问权限", "读取权限")
            oss_object_acl_page.oss_object_acl_dialog_check_permission("ACL访问权限", "读取权限")
            oss_object_acl_page.oss_object_acl_dialog_click_confirm()

        with allure_step_log("步骤3: 验证对象ACL配置已创建成功"):
            oss_object_acl_page.wait_for_operation_complete(timeout=30)
            oss_object_acl_page.oss_object_acl_assert_account_permissions(
                account_id,
                object_permission=["读取权限"],
                acl_permission=["读取权限"],
            )

    @allure.title("OSS-编辑对象ACL")
    def test_oss_object_acl_edit(self, oss_object_acl_page, oss_object_acl_env):
        """场景 405442：编辑对象 ACL。"""
        bucket_name = oss_object_acl_env["bucket_name"]
        object_name = oss_object_acl_env["object_name"]
        account_id = oss_object_acl_env["account_id"]

        with allure_step_log("步骤1: 导航到对象ACL页面"):
            oss_object_acl_page.oss_object_acl_goto_page(bucket_name, object_name)
            oss_object_acl_page.oss_object_acl_assert_account_permissions(
                account_id,
                object_permission=["读取权限"],
                acl_permission=["读取权限"],
            )

        with allure_step_log("步骤2: 找到目标ACL配置并点击'编辑'"):
            oss_object_acl_page.oss_object_acl_click_row_edit(account_id)
            assert oss_object_acl_page.oss_object_acl_dialog_is_visible("编辑账号权限"), \
                "未弹出'编辑账号权限'弹窗"

        with allure_step_log("步骤3: 修改权限配置（取消读取，勾选写入）"):
            oss_object_acl_page.oss_object_acl_dialog_uncheck_permission("ACL访问权限", "读取权限")
            oss_object_acl_page.oss_object_acl_dialog_check_permission("ACL访问权限", "写入权限")
            oss_object_acl_page.oss_object_acl_dialog_click_confirm()

        with allure_step_log("步骤4: 验证编辑后的ACL权限正确"):
            oss_object_acl_page.wait_for_operation_complete(timeout=30)
            oss_object_acl_page.oss_object_acl_assert_account_permissions(
                account_id,
                object_permission=["读取权限"],
                acl_permission=["写入权限"],
            )

    @allure.title("OSS-删除对象ACL")
    def test_oss_object_acl_delete(self, oss_object_acl_page, oss_object_acl_env):
        """场景 405455：删除对象 ACL。"""
        bucket_name = oss_object_acl_env["bucket_name"]
        object_name = oss_object_acl_env["object_name"]
        account_id = oss_object_acl_env["account_id"]

        with allure_step_log("步骤1: 导航到对象ACL页面"):
            oss_object_acl_page.oss_object_acl_goto_page(bucket_name, object_name)
            oss_object_acl_page.oss_object_acl_assert_account_permissions(
                account_id,
                object_permission=["读取权限"],
                acl_permission=["写入权限"],
            )

        with allure_step_log("步骤2: 找到目标ACL配置并点击'删除'"):
            oss_object_acl_page.oss_object_acl_click_row_delete(account_id)

        with allure_step_log("步骤3: 在删除确认弹窗中点击'确定'"):
            oss_object_acl_page.oss_object_acl_click_delete_confirm()

        with allure_step_log("步骤4: 验证对象ACL配置已删除"):
            oss_object_acl_page.wait_for_operation_complete(timeout=30)
            oss_object_acl_page.oss_object_acl_assert_account_not_exists(account_id)
