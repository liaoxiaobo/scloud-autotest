import pytest
import allure
from sugon_web.testcase.conftest import ecs_page
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


@allure.epic('计算服务')
@allure.feature('云服务器快照')
@allure.story('快照基本功能验证')
class TestECSS:

    @allure.title("验证创建&删除快照")
    def test_ecs_system_snapshot(self, ecs_page, vm, ssh_host):
        """测试创建云服务器快照"""
        snapshot_name = f"snapshot_{vm['name']}"

        with allure_step_log("步骤1: 创建系统盘快照"):
            ecs_page.ecss_create(
                name=vm['name'],
                snapshot_name=snapshot_name,
                desc="系统盘快照测试"
            )
            ecs_page.assert_popup_success("创建实例快照成功")
            ecs_page.assert_status(vm['name'], status="当前无任务")

        with allure_step_log("步骤2: 验证快照创建成功"):
            # 切换到快照页面
            ecs_page.goto_submenu("快照")
            ecs_page.assert_status(snapshot_name, status="可用", refresh=True)

            # 验证快照属性
            snapshot_data = ecs_page.get_row_data(snapshot_name)
            assert snapshot_data["是否快照数据卷"] == "否"
            assert snapshot_data["是否启动源"] == "是"

        with allure_step_log("步骤3: 删除系统盘快照"):
            # 删除快照
            ecs_page.ecss_delete(snapshot_name)

        with allure_step_log("步骤4: 验证快照已删除"):
            ecs_page.assert_deleted(snapshot_name, refresh=True)    # 刷新页面，确保删除成功
            assert ssh_host.run(f"glance image-list| grep {snapshot_name}") == "", "底层未删除成功"

    @allure.title("验证批量删除快照")
    def test_ecs_batch_snapshot(self, ecs_page, vm, ssh_host):
        """测试批量删除云服务器快照"""
        snapshot_names = []

        with allure_step_log("步骤1: 批量创建快照"):
            # 创建多个快照
            for i in range(3):
                snapshot_name = f"snapshot_{random_data()}"
                snapshot_names.append(snapshot_name)

                ecs_page.ecss_create(
                    name=vm["name"],
                    snapshot_name=snapshot_name,
                )
                ecs_page.assert_popup_success("创建实例快照成功")
                ecs_page.assert_status(vm["name"], status="当前无任务")

        with allure_step_log("步骤2: 验证所有快照创建成功"):
            # 切换到快照页面
            ecs_page.goto_submenu("快照")
            ecs_page.assert_status(snapshot_names, status="可用", refresh=True)

        with allure_step_log("步骤3: 批量删除快照"):
            # 批量删除快照
            ecs_page.ecss_delete(snapshot_names)

        with allure_step_log("步骤4: 验证所有快照已删除"):
            ecs_page.assert_deleted(snapshot_names, refresh=True)
            assert ssh_host.run(f"glance image-list| grep {snapshot_name}") == "", "底层未删除成功"

    @allure.title("验证修改快照")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_ecss_modify(self, ecs_page, ecss: dict, params):
        """测试云服务器快照修改功能"""

        new_name = ecss["name"] + params["name_suffix"]
        new_desc = params["new_desc"]

        with allure_step_log("步骤1: 修改云服务器快照的名称和描述"):
            ecs_page.ecss_edit(ecss["name"], new_name, new_desc)
            ecs_page.assert_popup_success("修改快照成功")

        with allure_step_log("步骤2: 验证修改结果"):
            ecs_page.assert_list_contain(new_name)
            # 获取修改后的快照数据并验证
            snapshot_data = ecs_page.get_row_data(new_name)
            assert snapshot_data["描述"] == new_desc

    @allure.title("验证还原快照")
    def test_ecss_restore(self, ecs_page, vm, ecss: dict, ssh_vm):
        """测试云服务器快照还原功能"""

        with allure_step_log("步骤1: 虚机打快照后，在root目录下写测试文件"):
            # 连接虚拟机
            ssh_vm.connect(vm['mfip'])

            # 在root目录下创建测试文件
            test_file = "/root/test_restore_file.txt"
            ssh_vm.create_file(test_file)
            ssh_vm.file_exist(test_file)

        with allure_step_log("步骤2: 虚机还原快照"):

            # 还原快照
            ecs_page.ecss_restore(ecss["name"])
            ecs_page.assert_popup_success(f"{vm['name']}实例还原快照成功")

        with allure_step_log("步骤3: 页面验证快照还原结果"):
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.assert_status(vm['name'], status="快照还原中")
            ecs_page.assert_status(vm['name'], status="当前无任务")
            data = ecs_page.get_row_data(vm['name'])
            assert data["镜像名称"] == ecss["name"]

        with allure_step_log("步骤4: 验证虚机内测试文件已不存在"):
            # 重新连接虚拟机
            ssh_vm.connect(vm['mfip'])
            ssh_vm.file_not_exist(test_file)

        with allure_step_log("步骤5: 重建虚机并删除快照"):
            image = ecs_page.storage_pool  # 获取存储池同名镜像
            if ecs_page.env["stor"] not in ["usan", "local", "nfs"]:     # 虚机有快照时，不支持重建
                ecs_page.ecs_rebuild(vm['name'], 'centos7.9', '64位', image)
                ecs_page.assert_status(vm['name'], status="当前无任务")
                ecs_page.page.wait_for_timeout(5000)    # 延迟5秒，再去清理快照数据

    @allure.title("验证列表页搜索&重置")
    def test_ecss_search(self, ecs_page, ecss: dict):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = ecss['name'][:-2]
            ecs_page.search(keyword)

        with allure_step_log("步骤2: 验证搜索结果"):
            ecs_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            ecs_page.search(random_data())
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()

        with allure_step_log("步骤4: 验证重置结果"):
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
            assert len(ecs_page.table_rows) > 0, "重置后列表数据为空"

    @allure.title("快照策略-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_create_policies'))
    def test_ecss_policy_create(self, ecs_page, params):
        """测试云服务器快照策略创建功能"""
        # 提取参数
        name = params.get("name")
        enabled = params.get("enabled")
        hours = params.get("hours")
        cycle_days = params.get("cycle_days")
        retention_type = params.get("retention_type")
        retention_value = params.get("retention_value", 1)
        snapshot_data_disk = params.get("snapshot_data_disk")

        # 创建快照策略
        with allure_step_log("步骤1: 创建快照策略"):
            ecs_page.ecss_policy_create(
                name=name,
                enabled=enabled,
                hours=hours,
                cycle_days=cycle_days,
                retention_type=retention_type,
                retention_value=retention_value,
                snapshot_data_disk=snapshot_data_disk
            )

            # 验证创建结果
            ecs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 删除快照策略"):
            ecs_page.ecss_policy_delete([name])
            ecs_page.assert_popup_success("删除策略成功")
            ecs_page.assert_deleted(name)

    @allure.title("快照策略-批量删除")
    def test_ecss_policy_batch_delete(self, ecs_page):

        policy_names = []
        with allure_step_log("步骤1: 创建多个快照策略"):
            for i in range(3):
                name = random_data()
                policy_names.append(name)
                ecs_page.ecss_policy_create(
                    name=name,
                    hours=[0, 1, 2],
                    enabled=True,
                    cycle_days=1,
                    retention_type="按数量",
                    retention_value=5
                )
                ecs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 批量删除快照策略"):
            ecs_page.ecss_policy_delete(policy_names)
            # evs_page.assert_popup_success()

        with allure_step_log("步骤3: 验证快照策略已删除"):
            ecs_page.assert_deleted(policy_names)

    @allure.title("快照策略-列表页搜索&重置")
    def test_ecss_policy_search(self, ecs_page, ecss_policy):
        """测试云服务器快照策略搜索功能"""

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = ecss_policy["name"][:-2]  # 取策略名称的前几个字符作为关键词
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, exact_match=False, column_name="名称/ID")

        with allure_step_log("步骤2: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"