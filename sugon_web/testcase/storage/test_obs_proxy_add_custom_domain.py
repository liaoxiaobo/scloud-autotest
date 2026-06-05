import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('访问代理-添加自定义域名功能验证')
class TestOBSProxyAddCustomDomain:

    @allure.title("对象存储-访问代理-添加自定义域名并验证")
    def test_obs_proxy_add_custom_domain(self, obs_page):
        """验证在访问代理页面添加自定义域名后，列表和详情展示正确，
        且桶详情页Endpoint显示正确。
        """
        domain_name = f"obs-{random_data(length=6)}.sugoncloud.com"
        bucket_name = f"bucket-{random_data()}"

        # ------------------ 步骤1：进入访问代理页面 ------------------
        with allure_step_log("步骤1: 进入访问代理页面"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("访问代理")

        # ------------------ 步骤2~3：新建访问代理 ------------------
        with allure_step_log("步骤2~3: 新建自定义域名访问代理"):
            selected_vpc_name = obs_page.obs_proxy_create(domain_name)

        # ------------------ 步骤4：验证列表和展开详情 ------------------
        with allure_step_log("步骤4: 验证访问代理列表和展开详情"):
            obs_page.obs_proxy_assert_contain(domain_name)

            # 展开详情并验证4条Endpoint记录
            endpoint_urls = obs_page.obs_proxy_get_endpoint_urls(domain_name)
            assert len(endpoint_urls) == 4, (
                f"Expected 4 endpoint URLs, got {len(endpoint_urls)}: {endpoint_urls}"
            )

            expected_patterns = [
                ("S3", "HTTP", f"http://{domain_name}:20480"),
                ("S3", "HTTPS", f"https://{domain_name}:20481"),
                ("IAM", "HTTP", f"http://{domain_name}:20482"),
                ("IAM", "HTTPS", f"https://{domain_name}:20483"),
            ]
            for typ, method, url in expected_patterns:
                found = any(
                    u["type"] == typ and u["methods"] == method and url in u["endPoint"]
                    for u in endpoint_urls
                )
                assert found, f"未找到预期的Endpoint记录: {typ}/{method}/{url}"

        # ------------------ 步骤5：创建桶并验证Endpoint ------------------
        with allure_step_log("步骤5: 创建桶并验证桶详情页Endpoint显示"):
            # 确保任何残留弹窗已关闭
            obs_page.close_dialog_if_exists()
            obs_page.page.keyboard.press("Escape")
            obs_page.page.wait_for_timeout(500)
            obs_page.goto_submenu("桶列表")
            obs_page.wait_for_page_ready()

            obs_page.obs_bucket_create(bucket_name)
            obs_page.assert_popup_success("执行成功")
            obs_page.wait_for_page_ready()

            # 进入桶详情页
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.page.wait_for_timeout(2000)

            # 验证桶详情页包含自定义域名和VPC名称
            page_text = obs_page.page.content()
            assert domain_name in page_text, (
                f"桶详情页未显示自定义域名Endpoint: {domain_name}"
            )
            assert selected_vpc_name in page_text, (
                f"桶详情页未显示VPC名称: {selected_vpc_name}"
            )

        # ------------------ 清理 ------------------
        with allure_step_log("清理: 删除桶和访问代理"):
            # 先删除桶
            obs_page.goto_submenu("桶列表")
            obs_page.wait_for_page_ready()
            obs_page.obs_bucket_delete(bucket_name)
            obs_page.assert_deleted(bucket_name)

            # 再删除访问代理
            obs_page.goto_submenu("访问代理")
            obs_page.wait_for_page_ready()
            obs_page.obs_proxy_delete(domain_name)
            obs_page.assert_deleted(domain_name)
