import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('云硬盘-快照基本功能验证')
class TestEVSS:

    @allure.title("云硬盘快照-创建和删除")
    @pytest.mark.parametrize("params", load_data('test_volume_add_snapshot'))
    def test_volume_add_snapshot(self, evs_page, volume, params):
        snapshot_name = params["snapshot_name_prefix"] + random_data()

        with allure_step_log("步骤1: 创建云硬盘快照"):
            evs_page.evss_create(volume["name"], snapshot_name, params["desc"])
            evs_page.assert_popup_success("创建快照成功")
            evs_page.goto_submenu("快照")
            evs_page.assert_status(snapshot_name, status="可用")

        with allure_step_log("步骤2: 验证快照数据"):
            evs_page.set_table_header("描述")
            snapshot_data = evs_page.get_row_data(snapshot_name)
            assert snapshot_data["描述"] == params["desc"]

        with allure_step_log("步骤3: 删除云硬盘快照"):
            evs_page.evss_delete(snapshot_name)
            evs_page.assert_deleted(snapshot_name)

    @allure.title("云硬盘快照-批量删除")
    def test_snapshot_batch_delete(self, evs_page, volume):

        snapshot_names = []
        with allure_step_log("步骤1: 创建多个云硬盘快照"):
            for i in range(3):
                name = random_data()
                snapshot_names.append(name)
                evs_page.evss_create(
                    volume_name=volume["name"],
                    snapshot_name=name,
                    desc=f"批量删除测试快照{i}"
                )
                evs_page.assert_popup_success("创建快照成功")
                evs_page.goto_submenu("快照")
                evs_page.assert_status(name, status="可用")

        with allure_step_log("步骤2: 批量删除快照"):
            evs_page.evss_delete(snapshot_names)
            # evs_page.assert_popup_success()
            for name in snapshot_names:
                evs_page.assert_deleted(name)

    @allure.title("云硬盘快照-搜索和重置")
    def test_evss_search(self, evs_page, evss):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = evss['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("云硬盘快照-修改")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_volume_modify_snapshot(self, evs_page, evss, params):

        new_name = evss["name"] + params["name_suffix"]
        new_desc = params["new_desc"]

        with allure_step_log("步骤1: 修改云硬盘快照的名称和描述"):
            evs_page.evss_edit(evss["name"], new_name, new_desc)
            evs_page.assert_popup_success("更新快照成功")

            # 验证修改后的快照在列表中
            evs_page.assert_list_contain(new_name)

            # 获取修改后的快照数据并验证
            evs_page.set_table_header("描述")
            snapshot_data = evs_page.get_row_data(new_name)
            assert snapshot_data["描述"] == new_desc

    @allure.title("云硬盘快照-创建云硬盘")
    def test_create_volume_from_snapshot(self, evs_page, evss, ssh_host):

        with allure_step_log("步骤1: 从快照创建云硬盘"):
            name = "volume_from_snapshot_" + evss["volume_name"]
            evs_page.evs_create_from_snapshot(
                snapshot_name=evss["name"],
                volume_name=name,
                desc="从快照创建的云硬盘"
            )

            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_list_contain(name)
            evs_page.assert_status(name, status="可用")

        with allure_step_log("步骤2：清理测试数据"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            ssh_host.wait_volume_deleted(name)

    @allure.title("快照策略-创建和删除")
    @pytest.mark.parametrize("params", load_data('test_create_policies'))
    def test_evss_policy_create(self, evs_page, params):
        """测试云服务器快照策略创建功能"""
        # 提取参数
        name = params.get("name")
        enabled = params.get("enabled")
        hours = params.get("hours")
        cycle_days = params.get("cycle_days")
        retention_type = params.get("retention_type")
        retention_value = params.get("retention_value", 1)

        # 创建快照策略
        with allure_step_log("步骤1: 创建快照策略"):
            evs_page.evss_policy_create(
                name=name,
                enabled=enabled,
                hours=hours,
                cycle_days=cycle_days,
                retention_type=retention_type,
                retention_value=retention_value
            )

            # 验证创建结果
            evs_page.assert_popup_success("添加策略成功")

        with allure_step_log("步骤2: 删除快照策略"):
            evs_page.evss_policy_delete([name])
            evs_page.assert_deleted(name)

    @allure.title("快照策略-批量删除")
    def test_evss_policy_batch_delete(self, evs_page):

        policy_names = []
        with allure_step_log("步骤1: 创建多个快照策略"):
            for i in range(3):
                name = random_data()
                policy_names.append(name)
                evs_page.evss_policy_create(
                    name=name,
                    hours=[0, 1, 2],
                    enabled=True,
                    cycle_days=1,
                    retention_type="按数量",
                    retention_value=5
                )
                evs_page.assert_popup_success("添加策略成功")

        with allure_step_log("步骤2: 批量删除快照策略"):
            evs_page.evss_policy_delete(policy_names)
            # evs_page.assert_popup_success()

        with allure_step_log("步骤3: 验证快照策略已删除"):
            for name in policy_names:
                evs_page.assert_deleted(name)

    @allure.title("快照策略-搜索和重置")
    def test_evss_policy_search(self, evs_page, evss_policy):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = evss_policy[:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, column_name="名称/ID", exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("快照策略-修改")
    def test_evss_policy_edit(self, evs_page, evss_policy):

        with allure_step_log("步骤1: 修改快照策略"):
            evs_page.evss_policy_edit(name=evss_policy, hours=[7,8,9])
            evs_page.assert_popup_success("修改策略成功")

    @allure.title("快照策略-绑定和解绑云硬盘")
    def test_volume_bind_evss_policy(self, evs_page, volume, evss_policy):

        with allure_step_log("步骤1: 绑定快照策略"):
            evs_page.evs_bind_snapshot_policy(
                volume_name=volume["name"],
                policy_name=evss_policy,
            )
            evs_page.assert_popup_success()

            # 验证快照任务已创建
            evs_page.goto_submenu("快照任务")
            evs_page.assert_list_contain(volume["name"], column_name="云硬盘名称")

        with allure_step_log("步骤2: 删除快照任务（解绑）"):
            evs_page.evss_task_delete(volume["name"])
            evs_page.assert_deleted(volume["name"])

    @allure.title("快照任务-批量删除")
    def test_snapshot_task_batch_delete(self, evs_page, evss_policy):

        volume_names = []
        with allure_step_log("步骤1: 批量创建云硬盘"):
            base_name = random_data()
            evs_page.evs_create(
                name=base_name,
                count=3,
                size=10,
                desc="批量删除测试云硬盘"
            )
            evs_page.assert_popup_success("创建云硬盘成功")

            for i in range(3):
                volume_names.append(f"{base_name}-{i}")

            for name in volume_names:
                evs_page.assert_status(name, status="可用")

        with allure_step_log("步骤2: 为云硬盘绑定快照策略"):
            for name in volume_names:
                evs_page.evs_bind_snapshot_policy(
                    volume_name=name,
                    policy_name=evss_policy,
                    enable_auto_snapshot=True
                )
                evs_page.assert_popup_success()

            evs_page.goto_submenu("快照任务")
            for name in volume_names:
                evs_page.assert_list_contain(name, column_name="云硬盘名称")

        with allure_step_log("步骤3: 批量删除快照任务"):
            evs_page.evss_task_delete(volume_names)
            # evs_page.assert_popup_success()

        with allure_step_log("步骤4: 验证快照任务已删除"):
            for name in volume_names:
                evs_page.assert_deleted(name)

        with allure_step_log("步骤5: 清理测试数据"):
            evs_page.evs_remove(volume_names)
            evs_page.evs_delete(volume_names)
            for name in volume_names:
                evs_page.assert_deleted(name)

    @allure.title("快照任务-禁用和开启自动快照")
    def test_volume_auto_snapshot(self, evs_page, volume, evss_policy):

        with allure_step_log("步骤1: 绑定快照策略"):
            evs_page.evs_bind_snapshot_policy(
                volume_name=volume["name"],
                policy_name=evss_policy,
            )
            evs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 开启自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume["name"])
            evs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤3: 禁用自动快照"):
            evs_page.evss_task_set_auto_snapshot(volume["name"], enable=False)
            evs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤4: 删除快照任务（解绑）"):
            evs_page.evss_task_delete(volume["name"])
            evs_page.assert_deleted(volume["name"])
