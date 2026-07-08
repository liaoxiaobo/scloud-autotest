import allure
import pytest

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-基础配置-生命周期规则')
class TestOSSSetBucketLifecycle:
    """验证OSS对象存储桶生命周期规则创建的完整流程。

    覆盖场景：
    1. 创建桶生命周期规则，验证规则创建成功并显示在列表中
    """

    @allure.title("对象存储OSS-设置桶生命周期规则")
    def test_oss_set_bucket_lifecycle(self, oss_bucket, oss_page):
        """创建桶生命周期规则，验证规则创建成功并字段值正确。"""
        bucket_name = oss_bucket["name"]
        rule_name = random_data()
        prefix = "test01"
        days = 7

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页并开启多版本控制"):
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 进入生命周期规则页面"):
            oss_page.oss_bucket_goto_lifecycle_page(bucket_name)

        with allure_step_log(f"步骤3: 创建生命周期规则（名称: {rule_name}, 前缀: {prefix}, 天数: {days}）"):
            rule_info = oss_page.oss_bucket_lifecycle_create_rule(
                bucket_name=bucket_name,
                rule_name=rule_name,
                prefix=prefix,
                days=days,
                enabled=True,
            )

        with allure_step_log("步骤4: 验证生命周期规则创建成功（P0-存在性断言）"):
            # 等待列表刷新 - 使用 wait_for_operation_complete 替代固定等待
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            rule_names = [r["name"] for r in rules]
            assert rule_name in rule_names, \
                f"[ListAssertion] 生命周期规则列表中未找到规则 '{rule_name}' | 实际规则列表: {rule_names}"

        with allure_step_log("步骤5: 验证生命周期规则字段值正确（P1-末态字段断言）"):
            created_rule = next((r for r in rules if r["name"] == rule_name), None)
            assert created_rule is not None, f"未找到规则 '{rule_name}' 的详细信息"
            assert created_rule["enabled"] is True, \
                f"[FieldAssertion] 规则状态期望'已启用'，实际: {'已启用' if created_rule['enabled'] else '未启用'}"
            assert created_rule["prefix"] == prefix, \
                f"[FieldAssertion] 规则前缀期望'{prefix}'，实际: '{created_rule['prefix']}'"
            assert created_rule["days"] == days, \
                f"[FieldAssertion] 自动删除天数期望{days}，实际: {created_rule['days']}"
