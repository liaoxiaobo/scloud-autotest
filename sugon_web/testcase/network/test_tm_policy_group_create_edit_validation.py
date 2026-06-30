import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('传输策略组')
@allure.story('策略组新建与编辑功能验证')
class TestTransferStrategyGroupCreateEdit:
    """传输策略组新建与编辑功能验证。

    场景1：策略组新建可用性验证（用例422118）
    场景2：策略组编辑可用性验证（用例422121）

    两个场景共享同一测试类，但各自独立执行和清理。
    """

    @allure.title("传输策略组-新建可用性验证")
    def test_transfer_strategy_group_create(self, transfer_strategy_page):
        """测试传输策略组新建功能。

        步骤：
        1. 进入传输策略组模块（机密互联子菜单）
        2. 点击新建按钮，弹出新建窗口
        3. 填写策略组信息（名称随机，描述为空）
        4. 点击确定提交创建
        5. 列表页校验新增记录信息

        清理：删除新建的策略组
        """
        policy_name = f"tsg-{random_data()}"

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤2: 点击新建按钮并填写策略组信息"):
            transfer_strategy_page.transfer_strategy_create(
                name=policy_name, description=""
            )

        with allure_step_log("步骤3: 断言创建成功"):
            # P0: 操作成功弹窗
            transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤4: 列表页校验新增记录"):
            # P0: 列表中存在新增记录
            transfer_strategy_page.assert_list_contain(policy_name, column_name="名称")
            # P1: 回读字段值
            row_data = transfer_strategy_page.get_transfer_strategy_row_data(policy_name)
            assert row_data.get("名称") == policy_name, \
                f"[FieldAssertion] 名称不匹配 | 期望: {policy_name} | 实际: {row_data.get('名称')}"
            # 描述为空时，列表页可能显示"--"
            actual_desc = row_data.get("描述", "")
            assert actual_desc == "--" or actual_desc == "", \
                f"[FieldAssertion] 描述不匹配 | 期望: '--' 或空 | 实际: {actual_desc}"

        # 清理：删除新建的策略组
        with allure_step_log("清理: 删除新建的策略组"):
            transfer_strategy_page.transfer_strategy_delete(policy_name)
            transfer_strategy_page.assert_deleted(policy_name, timeout=30000)

    @allure.title("传输策略组-编辑可用性验证")
    def test_transfer_strategy_group_edit(self, transfer_strategy_page):
        """测试传输策略组编辑功能。

        前置条件：已预置策略组 policy1（名称为policy1，描述为autotest测试预置）

        步骤：
        1. 进入传输策略组模块
        2. 点击policy1的编辑按钮
        3. 确认初始值（名称=policy1，描述=autotest测试预置）
        4. 修改名称和描述
        5. 点击确定提交编辑
        6. 列表页校验编辑结果
        7. 进入详情页校验

        清理：删除编辑后的策略组（恢复policy1）
        """
        pre_set_name = "policy1"
        pre_set_desc = "autotest测试预置"
        new_name = f"tsg-{random_data()}"
        new_desc = new_name

        with allure_step_log("步骤1: 进入传输策略组模块"):
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()

        with allure_step_log("步骤1.5: 确保预置策略组policy1存在"):
            # 第1条用例会删除自身数据，第2条需重新预置；
            # transfer_strategy_exists 内部会先进入列表页（与第1条用例同样的进入方式）再搜索判断
            if not transfer_strategy_page.transfer_strategy_exists(pre_set_name):
                # 创建预置策略组
                transfer_strategy_page.transfer_strategy_create(
                    name=pre_set_name, description=pre_set_desc
                )
                transfer_strategy_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤2: 点击编辑按钮并确认初始值"):
            original_data = transfer_strategy_page.transfer_strategy_edit(
                name=pre_set_name,
                new_name=new_name,
                new_description=new_desc,
            )

        with allure_step_log("步骤3: 断言编辑操作成功"):
            # P0: 操作成功弹窗
            transfer_strategy_page.assert_popup_success(timeout=10000)
            # P1: 断言初始值正确
            assert original_data["name"] == pre_set_name, \
                f"[FieldAssertion] 初始名称不匹配 | 期望: {pre_set_name} | 实际: {original_data['name']}"
            assert original_data["description"] == pre_set_desc, \
                f"[FieldAssertion] 初始描述不匹配 | 期望: {pre_set_desc} | 实际: {original_data['description']}"

        with allure_step_log("步骤4: 列表页校验编辑结果"):
            # 编辑后名称已变更，列表仍按旧名称(policy1)过滤，需重新按新名称搜索
            transfer_strategy_page.search(new_name)
            transfer_strategy_page.wait_for_page_ready()
            # P0: 列表中存在编辑后的记录
            transfer_strategy_page.assert_list_contain(new_name, column_name="名称")
            # P1: 回读字段值
            row_data = transfer_strategy_page.get_transfer_strategy_row_data(new_name)
            assert row_data.get("名称") == new_name, \
                f"[FieldAssertion] 名称不匹配 | 期望: {new_name} | 实际: {row_data.get('名称')}"
            actual_desc = row_data.get("描述", "")
            assert actual_desc == new_desc, \
                f"[FieldAssertion] 描述不匹配 | 期望: {new_desc} | 实际: {actual_desc}"

        with allure_step_log("步骤5: 进入详情页校验"):
            transfer_strategy_page.goto_transfer_strategy_detail(new_name)
            # 等待详情页加载，检查加密规则tab
            transfer_strategy_page.wait_for_page_ready()
            # 断言详情页显示加密规则tab
            transfer_strategy_page.assert_tab_visible("加密规则")

        # 清理：删除编辑后的策略组，恢复预置的policy1
        with allure_step_log("清理: 删除编辑后的策略组并恢复policy1"):
            # 先返回列表页
            transfer_strategy_page.goto_service("虚拟私有云")
            transfer_strategy_page.goto_submenu("机密互联")
            transfer_strategy_page.wait_for_page_ready()
            transfer_strategy_page.transfer_strategy_delete(new_name)
            transfer_strategy_page.assert_deleted(new_name, timeout=30000)
            # 恢复预置的policy1
            transfer_strategy_page.transfer_strategy_create(
                name=pre_set_name, description=pre_set_desc
            )
            transfer_strategy_page.assert_popup_success(timeout=10000)
