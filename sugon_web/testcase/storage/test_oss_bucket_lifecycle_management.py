import allure
import pytest
import re

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-基础配置-生命周期规则')
class TestOSSBucketLifecycleDisable:
    """验证OSS对象存储桶生命周期规则禁用功能。

    覆盖场景：
    1. 单一禁用生命周期规则
    2. 批量禁用生命周期规则
    3. 验证禁用后所有规则状态为未启用
    """

    @allure.title("对象存储OSS-禁用生命周期规则")
    def test_oss_bucket_lifecycle_disable(self, oss_bucket, oss_page):
        """禁用生命周期规则，验证单一禁用和批量禁用均成功。"""
        bucket_name = oss_bucket["name"]
        prefix_list = ["test01", "test02", "test03"]
        days = 7

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页并开启多版本控制"):
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 创建3条生命周期规则（状态：已启用）"):
            rule_names = []
            for prefix in prefix_list:
                rule_name = random_data()
                rule_info = oss_page.oss_bucket_lifecycle_create_rule(
                    bucket_name=bucket_name,
                    rule_name=rule_name,
                    prefix=prefix,
                    days=days,
                    enabled=True,
                )
                rule_names.append(rule_info["name"])
            logger.info(f"创建的3条规则名称: {rule_names}")

        with allure_step_log("步骤3: 验证3条规则均创建成功且状态为已启用（P0-存在性断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                assert name in [r["name"] for r in rules], \
                    f"[ListAssertion] 规则列表中未找到 '{name}'"
                created_rule = next((r for r in rules if r["name"] == name), None)
                assert created_rule is not None, f"未找到规则 '{name}'"
                assert created_rule["enabled"] is True, \
                    f"[StatusAssertion] 规则 '{name}' 状态期望'已启用'，实际: '未启用'"

        with allure_step_log(f"步骤4: 单一禁用生命周期规则（规则: {rule_names[0]}）"):
            oss_page.click_action(rule_names[0], "禁用")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤5: 验证单一禁用成功（P0-状态断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            disabled_rule = next((r for r in rules if r["name"] == rule_names[0]), None)
            assert disabled_rule is not None, f"[ListAssertion] 禁用后规则 '{rule_names[0]}' 仍应存在"
            assert disabled_rule["enabled"] is False, \
                f"[StatusAssertion] 规则 '{rule_names[0]}' 禁用后期望状态'未启用'，实际: '已启用'"

        with allure_step_log("步骤6: 批量禁用剩余2条生命周期规则"):
            oss_page.select_rows_by_names(rule_names[1:])
            oss_page.oss_bucket_lifecycle_click_more_dropdown("禁用")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤7: 验证批量禁用成功，所有规则状态为未启用（P1-末态字段断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                rule = next((r for r in rules if r["name"] == name), None)
                assert rule is not None, f"[ListAssertion] 规则 '{name}' 应仍存在"
                assert rule["enabled"] is False, \
                    f"[FieldAssertion] 规则 '{name}' 状态期望'未启用'，实际: '已启用'"


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-基础配置-生命周期规则')
class TestOSSBucketLifecycleEnable:
    """验证OSS对象存储桶生命周期规则启用功能。

    覆盖场景：
    1. 单一启用生命周期规则
    2. 批量启用生命周期规则
    3. 验证启用后所有规则状态为已启用
    """

    @allure.title("对象存储OSS-启用生命周期规则")
    def test_oss_bucket_lifecycle_enable(self, oss_bucket, oss_page):
        """启用生命周期规则，验证单一启用和批量启用均成功。"""
        bucket_name = oss_bucket["name"]
        prefix_list = ["test01", "test02", "test03"]
        days = 7

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页并开启多版本控制"):
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 创建3条已禁用的生命周期规则作为前置数据"):
            rule_names = []
            for prefix in prefix_list:
                rule_name = random_data()
                rule_info = oss_page.oss_bucket_lifecycle_create_rule(
                    bucket_name=bucket_name,
                    rule_name=rule_name,
                    prefix=prefix,
                    days=days,
                    enabled=False,
                )
                rule_names.append(rule_info["name"])
            logger.info(f"创建的3条已禁用规则名称: {rule_names}")

        with allure_step_log("步骤3: 验证3条规则均创建成功且状态为未启用（P0-存在性断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                assert name in [r["name"] for r in rules], \
                    f"[ListAssertion] 规则列表中未找到 '{name}'"
                created_rule = next((r for r in rules if r["name"] == name), None)
                assert created_rule is not None, f"未找到规则 '{name}'"
                assert created_rule["enabled"] is False, \
                    f"[StatusAssertion] 规则 '{name}' 状态期望'未启用'，实际: '已启用'"

        with allure_step_log(f"步骤4: 单一启用生命周期规则（规则: {rule_names[0]}）"):
            oss_page.click_action(rule_names[0], "启用")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤5: 验证单一启用成功（P0-状态断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            enabled_rule = next((r for r in rules if r["name"] == rule_names[0]), None)
            assert enabled_rule is not None, f"[ListAssertion] 启用后规则 '{rule_names[0]}' 仍应存在"
            assert enabled_rule["enabled"] is True, \
                f"[StatusAssertion] 规则 '{rule_names[0]}' 启用后期望状态'已启用'，实际: '未启用'"

        with allure_step_log("步骤6: 批量启用剩余2条生命周期规则"):
            oss_page.select_rows_by_names(rule_names[1:])
            oss_page.oss_bucket_lifecycle_click_more_dropdown("启用")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤7: 验证批量启用成功，所有规则状态为已启用（P1-末态字段断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                rule = next((r for r in rules if r["name"] == name), None)
                assert rule is not None, f"[ListAssertion] 规则 '{name}' 应仍存在"
                assert rule["enabled"] is True, \
                    f"[FieldAssertion] 规则 '{name}' 状态期望'已启用'，实际: '未启用'"


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-基础配置-生命周期规则')
class TestOSSBucketLifecycleDelete:
    """验证OSS对象存储桶生命周期规则删除功能。

    覆盖场景：
    1. 单一删除生命周期规则
    2. 批量删除生命周期规则
    3. 验证删除后规则不存在于列表中
    """

    @allure.title("对象存储OSS-删除生命周期规则")
    def test_oss_bucket_lifecycle_delete(self, oss_bucket, oss_page):
        """删除生命周期规则，验证单一删除和批量删除均成功。"""
        bucket_name = oss_bucket["name"]
        prefix_list = ["test01", "test02", "test03"]
        days = 7

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页并开启多版本控制"):
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤2: 创建3条生命周期规则（状态：已启用）"):
            rule_names = []
            for prefix in prefix_list:
                rule_name = random_data()
                rule_info = oss_page.oss_bucket_lifecycle_create_rule(
                    bucket_name=bucket_name,
                    rule_name=rule_name,
                    prefix=prefix,
                    days=days,
                    enabled=True,
                )
                rule_names.append(rule_info["name"])
            logger.info(f"创建的3条规则名称: {rule_names}")

        with allure_step_log("步骤3: 验证3条规则均创建成功（P0-存在性断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                assert name in [r["name"] for r in rules], \
                    f"[ListAssertion] 规则列表中未找到 '{name}'"

        with allure_step_log(f"步骤4: 单一删除生命周期规则（规则: {rule_names[0]}）"):
            oss_page.click_action(rule_names[0], "删除")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤5: 验证单一删除成功（P0-删除断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            assert rule_names[0] not in [r["name"] for r in rules], \
                f"[ListAssertion] 规则 '{rule_names[0]}' 删除后仍存在于列表中"

        with allure_step_log("步骤6: 批量删除剩余2条生命周期规则"):
            oss_page.select_rows_by_names(rule_names[1:])
            oss_page.oss_bucket_lifecycle_click_more_dropdown("删除")
            oss_page.dialog_confirm.click()

        with allure_step_log("步骤7: 验证批量删除成功，所有规则已不存在（P1-末态存在性断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            for name in rule_names:
                assert name not in [r["name"] for r in rules], \
                    f"[ListAssertion] 规则 '{name}' 删除后仍存在于列表中"


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-基础配置-生命周期规则')
class TestOSSBucketLifecycleEdit:
    """验证OSS对象存储桶生命周期规则编辑功能。

    覆盖场景：
    1. 创建生命周期规则
    2. 编辑生命周期规则（修改状态、名称、前缀、天数）
    3. 验证编辑后字段值正确
    """

    @allure.title("对象存储OSS-编辑生命周期规则")
    def test_oss_bucket_lifecycle_edit(self, oss_bucket, oss_page):
        """编辑生命周期规则，验证编辑后字段值正确。"""
        bucket_name = oss_bucket["name"]
        original_rule_name = random_data()
        prefix = "test01"
        days = 7
        new_rule_name = "rule1-change"

        with allure_step_log(f"步骤1: 进入桶 {bucket_name} 详情页并开启多版本控制"):
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log(f"步骤2: 创建1条生命周期规则（名称: {original_rule_name}）"):
            rule_info = oss_page.oss_bucket_lifecycle_create_rule(
                bucket_name=bucket_name,
                rule_name=original_rule_name,
                prefix=prefix,
                days=days,
                enabled=True,
            )
            logger.info(f"创建规则: {rule_info}")

        with allure_step_log("步骤3: 验证规则创建成功（P0-存在性断言）"):
            oss_page.wait_for_operation_complete()
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            assert original_rule_name in [r["name"] for r in rules], \
                f"[ListAssertion] 规则列表中未找到 '{original_rule_name}'"
            created_rule = next((r for r in rules if r["name"] == original_rule_name), None)
            assert created_rule is not None, f"未找到规则 '{original_rule_name}'"
            assert created_rule["enabled"] is True, \
                f"[StatusAssertion] 规则状态期望'已启用'，实际: '未启用'"

        with allure_step_log(f"步骤4: 编辑生命周期规则（名称改为: {new_rule_name}, 状态改为禁用）"):
            oss_page.oss_bucket_lifecycle_edit_rule(
                bucket_name=bucket_name,
                original_rule_name=original_rule_name,
                new_rule_name=new_rule_name,
                prefix=prefix,
                days=days,
                enabled=False,
            )

        with allure_step_log("步骤5: 验证编辑后的规则字段值正确（P1-末态字段断言）"):
            rules = oss_page.oss_bucket_lifecycle_get_rules(bucket_name)
            # 原规则名不应再存在
            assert original_rule_name not in [r["name"] for r in rules], \
                f"[ListAssertion] 原规则名 '{original_rule_name}' 编辑后仍存在于列表中"
            # 新规则名应存在
            assert new_rule_name in [r["name"] for r in rules], \
                f"[ListAssertion] 新规则名 '{new_rule_name}' 未在列表中找到"
            edited_rule = next((r for r in rules if r["name"] == new_rule_name), None)
            assert edited_rule is not None, f"未找到编辑后的规则 '{new_rule_name}'"
            assert edited_rule["enabled"] is False, \
                f"[FieldAssertion] 规则状态期望'未启用'，实际: '已启用'"
            assert edited_rule["prefix"] == prefix, \
                f"[FieldAssertion] 规则前缀期望'{prefix}'，实际: '{edited_rule['prefix']}'"
            assert edited_rule["days"] == days, \
                f"[FieldAssertion] 自动删除天数期望{days}，实际: {edited_rule['days']}"
