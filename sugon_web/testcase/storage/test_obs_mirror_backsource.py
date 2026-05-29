import os

import allure
import pytest

from sugon_web.utils.logger import allure_step_log


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('数据回源-镜像回源规则生效性验证')
class TestOBSMirrorBacksource:

    @pytest.mark.parametrize("bucket", [{"count": 2}], indirect=True)
    @allure.title("对象存储-镜像回源规则生效性验证")
    def test_obs_mirror_backsource_rule_effective(self, obs_page, bucket, page):
        """验证为桶配置镜像回源规则后，访问不存在的对象可自动从源站回源并保存。"""
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
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 步骤2：获取 bucket01 EndPoint ------------------
        with allure_step_log("步骤2: 获取 bucket01 的 EndPoint HTTPS URL"):
            # 返回桶详情页获取 EndPoint
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket01["name"])
            obs_page.page.wait_for_timeout(3000)
            endpoint_text = obs_page.obs_bucket_endpoint_get()
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
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_public_edit(
                read_permission=True, object_read_permission=True
            )
            obs_page.obs_bucket_acl_assert_contain("所有用户")

        # ------------------ 步骤5：为 bucket02 配置镜像回源规则 ------------------
        with allure_step_log("步骤5: 为 bucket02 配置镜像回源规则"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_datasource_config_click()
            obs_page.obs_datasource_mirror_rule_create(
                source_domain=source_domain,
                source_bucket=bucket01["name"],
                source_port=source_port,
            )
            obs_page.obs_datasource_rule_assert_contain(
                rule_type="镜像回源", source_type="公有类型"
            )

        # ------------------ 步骤6：测试镜像回源规则生效 ------------------
        with allure_step_log("步骤6: 通过 URL 访问触发镜像回源"):
            # 构造访问 URL: https://步骤1记录的URL/bucket02桶名称/bucket01桶内对象test1名称
            # endpoint_text 格式如 https://obs.xxx.com:20480
            mirror_url = (
                f"{endpoint_text}/{bucket02['name']}/{test_file_name}"
            )
            # 使用 API 请求访问（避免浏览器下载触发导航中止）
            response = obs_page.page.request.get(mirror_url)
            # 验证响应状态为 200 或触发下载
            assert response.status in [200, 204, 206], (
                f"镜像回源访问失败，状态码: {response.status}"
            )

        # ------------------ 步骤7：验证 bucket02 对象列表存在回源对象 ------------------
        with allure_step_log("步骤7: 验证 bucket02 对象列表中存在回源对象"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_object_tab_click()
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 清理：删除 bucket02 的数据回源规则 ------------------
        with allure_step_log("清理: 删除 bucket02 的镜像回源规则"):
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket02["name"])
            obs_page.obs_bucket_datasource_config_click()
            obs_page.obs_datasource_rule_delete(rule_type="镜像回源")
