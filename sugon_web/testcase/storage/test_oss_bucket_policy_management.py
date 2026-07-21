import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶策略-编辑与删除')
class TestOSSBucketPolicyManagement:
    """验证OSS对象存储桶策略的编辑和删除完整流程。

    覆盖场景：
    1. 编辑桶策略（405412）：创建桶策略后编辑其名称，验证编辑成功
    2. 删除桶策略（405415）：删除已存在的桶策略，验证删除成功

    数据复用策略：
    - 场景1和场景2共享同一套测试数据（桶和桶策略）
    - 由 class-scoped fixture 统一创建和清理
    - 场景1执行后保留桶和策略，供场景2复用
    """

    @allure.title("对象存储OSS-编辑桶策略")
    def test_oss_edit_bucket_policy(self, oss_bucket_with_policy, oss_page):
        """编辑已存在的桶策略，验证编辑后名称正确更新。"""
        bucket_name = oss_bucket_with_policy["bucket_name"]
        original_policy_name = oss_bucket_with_policy["policy_name"]
        edited_policy_name = f"{original_policy_name}-edit"

        with allure_step_log(f"步骤1: 导航到桶 {bucket_name} 的桶策略页面"):
            oss_page.oss_bucket_goto_policy_page(bucket_name)

        with allure_step_log(f"步骤2: 编辑桶策略 {original_policy_name}"):
            oss_page.oss_bucket_policy_edit(
                bucket_name=bucket_name,
                policy_name=original_policy_name,
                new_policy_name=edited_policy_name,
            )

        with allure_step_log("步骤3: 验证编辑成功（P0: 策略存在性）"):
            policies = oss_page.oss_bucket_get_policies(bucket_name)
            assert edited_policy_name in policies, \
                f"[ListAssertion] 桶策略列表中未找到编辑后的策略 '{edited_policy_name}' | 实际策略列表: {policies}"

        with allure_step_log("步骤4: 验证编辑后的策略字段（P1: 末态字段回读）"):
            policies = oss_page.oss_bucket_get_policies(bucket_name)
            assert original_policy_name not in policies, \
                f"[ListAssertion] 原策略名称 '{original_policy_name}' 仍存在于列表中，编辑未生效 | 实际策略列表: {policies}"
            assert edited_policy_name in policies, \
                f"[ListAssertion] 编辑后的策略 '{edited_policy_name}' 未在列表中 | 实际策略列表: {policies}"

    @allure.title("对象存储OSS-删除桶策略")
    def test_oss_delete_bucket_policy(self, oss_bucket_with_policy, oss_page):
        """删除已存在的桶策略，验证删除成功且策略不在列表中。"""
        bucket_name = oss_bucket_with_policy["bucket_name"]
        # 由于编辑测试可能已修改策略名称，使用编辑后的名称进行删除
        policy_name = f"{oss_bucket_with_policy['policy_name']}-edit"

        with allure_step_log(f"步骤1: 导航到桶 {bucket_name} 的桶策略页面"):
            oss_page.oss_bucket_goto_policy_page(bucket_name)

        with allure_step_log(f"步骤2: 确认桶策略 {policy_name} 存在于列表中"):
            policies = oss_page.oss_bucket_get_policies(bucket_name)
            assert policy_name in policies, \
                f"[ListAssertion] 待删除策略 '{policy_name}' 未在列表中 | 实际策略列表: {policies}"

        with allure_step_log(f"步骤3: 删除桶策略 {policy_name}"):
            oss_page.oss_bucket_policy_delete(
                bucket_name=bucket_name,
                policy_name=policy_name,
            )

        with allure_step_log("步骤4: 验证删除成功（P0: 策略不存在）"):
            policies = oss_page.oss_bucket_get_policies(bucket_name)
            assert policy_name not in policies, \
                f"[ListAssertion] 已删除策略 '{policy_name}' 仍存在于列表中 | 实际策略列表: {policies}"
