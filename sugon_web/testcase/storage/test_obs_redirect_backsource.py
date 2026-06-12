import os

import allure
import pytest

from sugon_web.testcase.storage._obs_backsource_helpers import (
    _access_with_retry,
    _close_page_silent,
    _verify_source_public_read,
)
from sugon_web.utils.logger import allure_step_log, logger


def _goto_bucket_list(obs_page):
    """从任意 OBS 页面强制回到桶列表。

    obs_page.goto_service 会复用当前已在对象存储服务下的页面，
    但在 ACL/数据回源配置页等子页面中左侧菜单可能缺失，
    goto_submenu 无法完成导航。此处使用直达桶列表 URL 的兜底方式。
    """
    from sugon_web.config.config import Config

    base_url = Config.get("base_url").rstrip("/")
    obs_page.page.goto(f"{base_url}/obs/#/store/list")
    obs_page.wait_for_page_ready()


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('数据回源-重定向回源规则生效性验证')
class TestOBSRedirectBacksource:

    @pytest.mark.parametrize("bucket", [{"count": 2}], indirect=True)
    @allure.title("对象存储-重定向回源规则生效性验证")
    def test_obs_redirect_backsource_rule_effective(self, obs_page, bucket, page):
        """验证为桶配置重定向回源规则后，访问不存在的对象可自动从源站回源但不会保存到本地桶。"""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test1"
        )
        test_file_name = "test1"
        bucket01, bucket02 = bucket[0], bucket[1]

        # ------------------ 前置：选择项目 ------------------
        with allure_step_log("前置: 选择公共测试项目"):
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")

        # ------------------ 步骤1：上传对象到 bucket01 ------------------
        with allure_step_log("步骤1: 进入 bucket01 并上传对象 test1"):
            obs_page.obs_bucket_enter_detail(bucket01["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.wait_for_page_ready()
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 步骤2：获取 bucket01 EndPoint HTTP URL ------------------
        with allure_step_log("步骤2: 获取 bucket01 的 EndPoint HTTP URL"):
            _goto_bucket_list(obs_page)
            obs_page.obs_bucket_enter_detail(bucket01["name"])
            obs_page.wait_for_page_ready()
            endpoint_text = obs_page.obs_bucket_endpoint_get(protocol="http")
            source_domain, source_port, _ = obs_page.obs_bucket_endpoint_url_extract(
                endpoint_text
            )
            assert source_domain, "未能提取源站域名"

        # ------------------ 步骤3：开启 bucket01 公共读权限 ------------------
        with allure_step_log("步骤3: 开启 bucket01 桶ACLs公共访问权限"):
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_public_edit(
                read_permission=True, object_read_permission=True
            )
            obs_page.obs_bucket_acl_assert_contain("所有用户")

        # ------------------ 步骤4：开启 bucket02 公共读权限 ------------------
        with allure_step_log("步骤4: 开启 bucket02 桶ACLs公共访问权限"):
            _goto_bucket_list(obs_page)
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_public_edit(
                read_permission=True, object_read_permission=True
            )
            obs_page.obs_bucket_acl_assert_contain("所有用户")

        # ------------------ 步骤5：为 bucket02 配置重定向回源规则 ------------------
        with allure_step_log("步骤5: 为 bucket02 配置重定向回源规则"):
            _goto_bucket_list(obs_page)
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_datasource_config_click()
            obs_page.obs_datasource_redirect_rule_create(
                source_domain=source_domain,
                source_bucket=bucket01["name"],
                source_port=source_port,
            )
            obs_page.obs_datasource_rule_assert_contain(
                rule_type="重定向回源", source_type="公有类型"
            )

        # ------------------ 步骤6：诊断源站公共读权限 ------------------
        with allure_step_log("步骤6-诊断: 验证源站 bucket01 公共读权限是否生效"):
            source_direct_url = f"{endpoint_text}/{bucket01['name']}/{test_file_name}"
            anonymous_status, auth_status = _verify_source_public_read(
                page.context.browser, page.context, source_direct_url
            )
            logger.info(
                f"匿名访问源站 {bucket01['name']}/{test_file_name} 状态码: {anonymous_status}"
            )
            logger.info(
                f"登录态访问源站 {bucket01['name']}/{test_file_name} 状态码: {auth_status}"
            )

        # ------------------ 步骤7：测试重定向回源规则生效 ------------------
        with allure_step_log("步骤7: 通过浏览器新页面访问触发重定向回源"):
            redirect_url = f"{endpoint_text}/{bucket02['name']}/{test_file_name}"
            redirect_status, redirect_pages = _access_with_retry(
                page.context.browser,
                redirect_url,
                max_attempts=5,
                initial_delay=45,
                retry_delay=15,
            )
            assert redirect_status in [200, 204, 206], (
                f"重定向回源访问失败，状态码: {redirect_status}"
                f"(匿名访问源站状态码: {anonymous_status}, "
                f"登录态访问源站状态码: {auth_status})"
            )

        # ------------------ 步骤8：验证 bucket02 对象列表不存在回源对象 ------------------
        with allure_step_log("步骤8: 验证 bucket02 对象列表中不存在回源对象"):
            _goto_bucket_list(obs_page)
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_object_tab_click()
            obs_page.assert_list_not_contain(test_file_name)

        # ------------------ 清理：关闭所有新创建的页面实例 ------------------
        for p in redirect_pages:
            _close_page_silent(p)

        # ------------------ 清理：删除 bucket02 的数据回源规则 ------------------
        with allure_step_log("清理: 删除 bucket02 的重定向回源规则"):
            _goto_bucket_list(obs_page)
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_datasource_config_click()
            obs_page.obs_datasource_rule_delete(rule_type="重定向回源")
            # 删除规则后页面停留在数据回源配置页，左侧菜单可能缺失；
            # 回到桶列表，确保 fixture teardown 能正常定位并清理桶。
            _goto_bucket_list(obs_page)
