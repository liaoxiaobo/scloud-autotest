import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶策略-创建桶策略')
class TestOSSCreateBucketPolicy:
    """验证OSS对象存储创建桶策略的完整流程。

    覆盖场景：
    1. 使用"公共读写"模板创建桶策略，验证策略创建成功并显示在列表中
    """

    @allure.title("对象存储OSS-创建桶策略")
    def test_oss_create_bucket_policy(self, oss_bucket, oss_page):
        """使用公共读写模板创建桶策略，验证创建成功。"""
        bucket_name = oss_bucket["name"]
        policy_name = random_data()

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页"):
            oss_page.oss_bucket_enter_detail(bucket_name)

        with allure_step_log(f"步骤2: 进入桶策略页面"):
            oss_page.oss_bucket_goto_policy_page(bucket_name)

        with allure_step_log("步骤3: 点击新建按钮，进入创建桶策略页面"):
            # 创建桶策略方法内部会点击新建并导航到创建页
            pass

        with allure_step_log(f"步骤4: 配置并创建桶策略（模板: 公共读写，名称: {policy_name}）"):
            created_name = oss_page.oss_bucket_policy_create(
                bucket_name=bucket_name,
                policy_name=policy_name,
                template_name="公共读写",
            )

        with allure_step_log("步骤5: 验证桶策略创建成功"):
            # P0: 断言策略列表中包含新创建的策略
            policies = oss_page.oss_bucket_get_policies(bucket_name)
            assert policy_name in policies, \
                f"[ListAssertion] 桶策略列表中未找到策略 '{policy_name}' | 实际策略列表: {policies}"
