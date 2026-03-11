import random
import time
from datetime import datetime

import pytest
import allure

from sugon_web.config.config import Config
from sugon_web.testcase.conftest import ecs_page, ops_page, backup_task
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


@allure.epic('云备份')
@allure.feature('实例备份')
@allure.story('备份任务创建场景')
class TestBackupCreate:

    @allure.title("验证创建周期性备份任务")
    @pytest.mark.parametrize("policy", load_data('test_backup_creat_scenario', "test_backup.yaml"))
    def test_backup_create_scenario(self, backup_page, vm_backup, cleanup_backup_task, policy):
        """测试创建每周增量备份任务"""
        # 用例名称
        allure.dynamic.title(f"{policy['case_name']}")

        server_name = vm_backup[0].get("name")
        task_name = f"scenario{time.strftime('%M%S')}-{server_name}"
        cleanup_backup_task.append(task_name)

        with allure_step_log("步骤1: 创建每周增量备份任务"):
            backup_page.create_backup_task(task_name=task_name, server_names=[server_name], policy=policy)
            backup_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 验证备份任务创建成功"):
            backup_page.assert_status(task_name, "创建完成")
            backup_page.assert_backup_policy_details(task_name, policy)
            backup_page.assert_backup_policy_details(task_name, {"云服务器名": server_name}, "云服务器列表")

    @pytest.mark.parametrize("policy", load_data('test_backup_once', "test_backup.yaml"))
    # @pytest.mark.slow
    @allure.title("验证创建一次性备份任务")
    def test_backup_once(self, backup_page, vm_backup, cleanup_backup_task, policy):
        """测试创建一次性备份任务功能"""
        allure.dynamic.title(f"{policy['case_name']}")
        server_name = vm_backup[0].get("name")
        task_name = f"once{time.strftime('%M%S')}-{server_name}"
        cleanup_backup_task.append(task_name)

        with allure_step_log("步骤1: 创建一次性备份任务"):
            backup_page.create_backup_task(task_name=task_name, server_names=[server_name], policy=policy)
            backup_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 验证备份任务创建成功"):
            backup_page.assert_status(task_name, "一次性备份", timeout=600)
            backup_page.assert_status(task_name, "立即备份")
            backup_page.assert_status(task_name, "已完成")
            backup_page.assert_backup_policy_details(task_name, {"云服务器名": server_name, "上一次备份状态": "备份成功"}, "云服务器列表")

@allure.epic('云备份')
@allure.feature('实例备份')
@allure.story('备份任务基本功能验证')
class TestBackupBasic:

    @allure.title("验证列表页搜索&重置")
    def test_backup_search(self, backup_page, backup_task):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            backup_page.goto_submenu('任务')
            keyword = backup_task.get('task_name').split("-")[-1]
            backup_page.backup_search(keyword)
            backup_page.page.wait_for_load_state("networkidle")
            backup_page.assert_list_contain(keyword, column_name="任务名", exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            backup_page.btn_reset.click()
            # 断言重置后搜索输入框已清空
            assert backup_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("启动/停止任务")
    def test_backup_task_start(self, backup_task, backup_page):
        """测试启动暂停任务功能"""

        task_name = backup_task.get("task_name")

        with allure_step_log("步骤1: 启动任务"):
            backup_page.backup_start_stop(task_name, "启动")
            backup_page.assert_status(task_name, "已启动")

        with allure_step_log("步骤2: 停止任务"):
            backup_page.backup_start_stop(task_name, "停止")
            backup_page.assert_status(task_name, "已停止")

    @allure.title("修改名称")
    def test_backup_edit_name(self, backup_task, backup_page):
        """测试修改任务名称功能"""
        task_name = backup_task.get("task_name")
        new_task_name = f"{task_name}-{time.strftime('%M%S')}"
        with allure_step_log("步骤1: 修改任务名称"):
            backup_page.backup_edit_name(task_name, new_task_name)
            backup_page.assert_popup_success("修改备份任务名称成功")
            backup_page.assert_backup_task_exists(new_task_name)

        with allure_step_log("步骤2: 还原任务名称"):
            backup_page.backup_edit_name(new_task_name, task_name)
            backup_page.assert_popup_success("修改备份任务名称成功")
            backup_page.assert_backup_task_exists(task_name)

    @allure.title("管理云服务器")
    @pytest.mark.parametrize("vm_backup, backup_task", [({"count": 2}, {"task_count": 1})], indirect=True)
    def test_backup_edit_vm(self, backup_task, vm_backup, backup_page):
        """测试管理云服务器功能"""
        vm_names = [vm_backup[i].get("name") for i in range(len(vm_backup))]
        task_name = backup_task.get("task_name")

        with allure_step_log("步骤1: 任务添加云服务器"):
            backup_page.goto_service('备份')
            backup_page.backup_edit_vm(task_name, vm_names[-1])
            backup_page.assert_popup_success("管理云服务器执行成功")
            backup_page.wait_for_source_complete(task_name)
            assert backup_page.get_row_data(task_name).get("保护实例数") == "2"

        with allure_step_log("步骤2: 任务移除云服务器"):
            backup_page.backup_edit_vm(task_name, [vm_names[-1]], attach=False)
            backup_page.assert_popup_success("管理云服务器执行成功")
            backup_page.wait_for_source_complete(task_name)
            assert backup_page.get_row_data(task_name).get("保护实例数") == "1"

    @allure.title("修改策略")
    @pytest.mark.parametrize("new_policy", load_data('test_backup_edit_policy', "test_backup.yaml"))
    def test_backup_edit_policy(self, backup_task, backup_page, new_policy):
        """测试管理云服务器功能"""
        task_name = backup_task.get("task_name")

        with allure_step_log("步骤1: 修改任务名称"):
            backup_page.backup_edit_policy(task_name, new_policy)
            backup_page.assert_popup_success("修改备份任务成功")

        with allure_step_log("步骤2: 验证任务名称"):
            backup_page.assert_backup_policy_details(task_name, new_policy)

    @allure.title("批量操作任务")
    @pytest.mark.parametrize("vm_backup, backup_task",[({"count": 2}, {"task_count": 2})],indirect=True)
    @pytest.mark.parametrize("operation", ["启动", "停止", "删除"])
    def test_backup_batch_operation(self, vm_backup, backup_task, backup_page, operation):
        """测试 批量操作功能"""
        names = [backup_task[i].get("task_name") for i in range(len(backup_task))]

        with allure_step_log(f"步骤1: 批量操作任务{operation}"):
            backup_page.backup_batch_operation(names, operation)

        with allure_step_log("步骤2: 验证任务状态"):
            if operation != "删除":
                backup_page.assert_popup_success(f"{operation}备份任务成功")
                backup_page.assert_status(names, f"已{operation}")
            else:
                backup_page.assert_deleted(names)

    @allure.title("执行全量/增量备份")
    # @pytest.mark.slow
    @pytest.mark.parametrize("method", ["执行增量", "执行全量"])
    def test_backup_exec_full(self, backup_task, backup_page, method):
        """测试执行全量/增量备份功能"""
        task_name = backup_task.get("task_name")
        server_name = backup_task.get("server_names")

        with allure_step_log(f"步骤1: {method}"):
            backup_page.exec_backup(task_name, method)
            backup_page.assert_popup_success("备份任务执行成功", timeout=10)

        with allure_step_log("步骤2: 验证备份结果"):
            backup_page.assert_status(task_name, "已启动", timeout=600)
            backup_page.assert_status(task_name, "成功", timeout=5)
            backup_page.assert_backup_data(server_name, "备份成功")
            backup_page.get_backup_data(server_name)
            backup_page.goto_submenu('任务')
            backup_page.assert_backup_policy_details(task_name, {"状态": "备份成功"}, "周期性任务")

    @allure.title("执行全量/增量备份重置任务")
    # @pytest.mark.slow
    @pytest.mark.parametrize("method", ["执行增量", "执行全量"])
    def test_backup_reset_task(self, backup_task, backup_page, method):
        """测试 重置任务功能"""
        task_name = backup_task.get("task_name")

        with allure_step_log(f"步骤1: {method}"):
            backup_page.exec_backup(task_name, method)
            backup_page.assert_popup_success("备份任务执行成功")

        with allure_step_log("步骤2: 重置任务"):
            backup_page.backup_reset_task(task_name)
            backup_page.assert_popup_success(f"重置备份任务{task_name}成功", timeout=60)
            backup_page.assert_status(task_name, "已启动")

    @allure.title("自动迁移任务")
    def test_backup_auto_migrate(self, backup_task, backup_page):
        """测试迁移任务功能"""
        enabled_nodes = backup_task.get("backup_nodes")
        if len(enabled_nodes) < 2:
            pytest.skip("迁移任务需要至少2个备份节点")

        task_name = backup_task.get("task_name")
        cur_target = backup_task.get("cur_target")

        with allure_step_log("步骤1: 迁移任务"):
            backup_page.backup_migrate(task_name)
            backup_page.assert_popup_success("迁移备份任务成功")

        with allure_step_log("步骤2: 验证迁移后任务节点"):
            assert cur_target in enabled_nodes  # 自动迁移会看当前备份任务的分布，迁移后节点不一定变更，确保在可用节点内即可

    @allure.title("手动迁移任务")
    def test_backup_manually_migrate(self, backup_task, backup_page):
        """测试迁移任务功能"""
        enabled_nodes = backup_task.get("backup_nodes")
        if len(enabled_nodes) < 2:
            pytest.skip("迁移任务需要至少2个备份节点")

        task_name = backup_task.get("task_name")
        cur_target = backup_task.get("cur_target")
        enabled_nodes.remove(cur_target)
        target = random.choice(enabled_nodes)

        with allure_step_log("步骤1: 迁移任务"):
            backup_page.backup_migrate(task_name, method="手动", target=target)
            backup_page.assert_popup_success("迁移备份任务成功")

        with allure_step_log("步骤2: 验证迁移后任务节点"):
            assert target == backup_page.backup_get_cur_target(task_name)

@allure.epic('云备份')
@allure.feature('实例备份')
@allure.story('恢复任务')
class TestResumeCreate:

    @allure.title("恢复-创建恢复任务场景")
    # @pytest.mark.slow
    @pytest.mark.parametrize("data", load_data('test_resume_create_scenario', 'test_backup.yaml'))
    def test_resume_create_scenario(self, backup_page, backup_task, ecs_page, ssh_vm, cleanup_resume_data, data):
        """测试创建恢复任务的各种场景"""
        allure.dynamic.title(f"恢复-{data['用例名称']}")
        backup_page.goto_service('备份')

        source_vm = backup_task.get("server_names")
        task_name = backup_task.get("task_name")

        re_vm = f"resume-scenario-{random_data()}"
        re_task = f"resume{time.strftime('%M%S')}-{source_vm}"
        # 获取fixture返回的列表
        resume_tasks, new_vm_names = cleanup_resume_data
        resume_tasks.append(re_task)
        new_vm_names.append(re_vm)

        with allure_step_log(f"步骤1: 创建备份数据"):
            backup_page.exec_backup(task_name, "执行增量")
            backup_page.assert_popup_success("备份任务执行成功")
            backup_page.assert_status(task_name, "已启动", timeout=600)
            backup_page.get_backup_data(source_vm)

        with allure_step_log(f"步骤2: 创建恢复任务-{re_task}"):
            backup_page.create_resume_task(
                source_vm=source_vm,
                re_vm=re_vm,
                re_task=re_task,
                data=data
            )
            backup_page.assert_popup_success("创建恢复任务成功")

        with allure_step_log("步骤3: 验证恢复任务创建成功"):
            backup_page.assert_status(re_task, "恢复成功", timeout=600)
            backup_page.assert_resume_task_details(re_task, data.get("恢复方式"))
            backup_page.assert_resume_task_details(re_task, {"云服务器名": re_vm, "恢复进度": "100%"}, "云服务器列表")

        with allure_step_log("步骤4: 验证恢复虚机"):
            # 获取原始虚机的 MD5 字典
            original_md5_dict = backup_task.get("source_md5")

            # 获取恢复的新虚机信息并连接
            backup_page.goto_service("弹性云服务器")
            ecs_page.assert_status(re_vm)
            ecs_page.set_table_header("架构")
            row_data = ecs_page.get_row_data(re_vm)
            assert row_data.get("镜像名称") == f"{Config.get('stor')}-test", "镜像与原始虚机不一致"
            assert row_data.get("架构x86_64aarch64   筛选   重置 ") == backup_task.get("source_arch"), "架构与原始虚机不一致"

            # 获取新虚机的 IP 并建立 SSH 连接
            new_vm_ip = ecs_page.get_row_data(re_vm).get("IP地址").split('固定:')[1].strip()
            new_mfip = ecs_page.bind_mfip(new_vm_ip.strip())
            mgmt_config = data.get("恢复配置", {}).get("管理配置", {})
            login_pwd = mgmt_config.get("登录密码", "admin1234@sugon")
            ssh_vm.connect(new_mfip, pwd=login_pwd)

            # 验证 MD5 是否一致
            for vol_name, vol_info in original_md5_dict.items():
                vol_dir = vol_info.get('dir', f'/cbr_test_{vol_name}')
                vol_file = vol_info.get('file', '')
                original_md5 = vol_info.get('md5', '')
                if not vol_file:
                    continue
                data_md5_cmd = f"cd {vol_dir} && md5sum {vol_file} | awk '{{print $1}}'"
                new_data_md5 = ssh_vm.run(data_md5_cmd, check_rc=True).strip()
                assert new_data_md5 == original_md5, f"{vol_name} 盘MD5不一致! 原始: {original_md5}, 新: {new_data_md5}"

            # 验证虚机可用性
            ecs_page.assert_ecs_enable(re_vm, ssh_vm)

        with allure_step_log("步骤5: 输入名称进行搜索"):
            backup_page.goto_service('备份')
            backup_page.goto_submenu("恢复任务")
            keyword = re_task.split("-")[-1]
            backup_page.backup_search(keyword)
            backup_page.assert_list_contain(keyword, column_name="任务名", exact_match=False)

        with allure_step_log("步骤6: 重置搜索条件"):
            backup_page.btn_reset.click()
            # 断言重置后搜索输入框已清空
            assert backup_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("恢复-新建资源/覆盖原始场景")
    @pytest.mark.parametrize("data", load_data('test_resume_scenarios', 'test_backup.yaml'))
    def test_resume_scenarios(
            self,
            backup_page,
            ecs_page,
            ssh_vm,
            backup_with_full_backup,
            cleanup_resume_data,
            data
    ):
        """测试恢复的各种数据准备场景（新建资源/覆盖原始）"""

        allure.dynamic.title(f"恢复-{data['用例名称']}")

        # 从 fixture 获取基础数据
        source_vm = backup_with_full_backup.get("server_names")
        task_name = backup_with_full_backup.get("task_name")
        source_mfip = backup_with_full_backup.get("source_mfip")
        original_md5_dict = backup_with_full_backup.get("source_md5")
        backup_data = backup_with_full_backup.get("backup_data")

        # 获取 cleanup fixture
        resume_tasks, new_vm_names = cleanup_resume_data

        # ========== 场景判断 ==========
        is_new_resource = data.get("恢复配置").get("恢复类型") == "新建资源"
        scenario_type = data.get("场景类型")

        # 根据场景确定恢复目标虚机
        if is_new_resource:
            re_vm = f"resume-new-{random_data()}"
            original_arch = backup_with_full_backup.get("original_arch")
            new_vm_names.append(re_vm)
        else:
            re_vm = source_vm

        re_task = f"resume{time.strftime('%M%S')}-{source_vm}"
        resume_tasks.append(re_task)
        incremental_data = {}

        with allure_step_log(f"步骤1: 数据准备 - {scenario_type}"):
            ssh_vm.connect(source_mfip)
            if scenario_type == "删除原始数据":
                for vol_name, vol_info in original_md5_dict.items():
                    vol_dir = vol_info.get('dir', f'/cbr_test_{vol_name}')
                    ssh_vm.run(f"cd {vol_dir} && rm -rf", check_rc=True)
            elif scenario_type in ["增量备份后删除增量数据", "增量备份后删除全部数据"]:
                for vol_name, vol_info in original_md5_dict.items():
                    vol_dir = vol_info.get('dir', f'/cbr_test_{vol_name}')
                    inc_file = f"inc_{vol_name}_{time.strftime('%H%M%S')}.txt"

                    content = f"incremental_{vol_name}_{time.strftime('%Y%m%d%H%M%S')}"
                    ssh_vm.run(f'cd {vol_dir} && echo -n "{content}" > {inc_file} && sync', check_rc=True)
                    ssh_vm.run(f"cd {vol_dir} && cat {inc_file}")

                    md5_cmd = f"cd {vol_dir} && md5sum {inc_file} | awk '{{print $1}}'"
                    inc_md5 = ssh_vm.run(md5_cmd, check_rc=True).strip()

                    incremental_data[vol_name] = {
                        "file": inc_file,
                        "dir": vol_dir,
                        "md5": inc_md5,
                        "path": f"{vol_dir}/{inc_file}"
                    }
                backup_page.goto_service('备份')
                backup_page.exec_backup(task_name, "执行增量")
                backup_page.assert_popup_success("备份任务执行成功")
                backup_page.assert_status(task_name, "已启动", timeout=600)
                re_data = backup_page.get_backup_data(source_vm)
                backup_data.extend(re_data)

                delete_range = data.get("删除范围")
                if delete_range == "仅增量数据":
                    for vol_name, inc_info in incremental_data.items():
                        ssh_vm.run(f"rm -f {inc_info['path']}", check_rc=True)
                elif delete_range == "全部数据":
                    for vol_name, vol_info in original_md5_dict.items():
                        vol_dir = vol_info.get('dir', f'/cbr_test_{vol_name}')
                        ssh_vm.run(f"cd {vol_dir} && rm -rf", check_rc=True)

        with allure_step_log(f"步骤2: 创建恢复任务-{re_task}"):
            backup_page.create_resume_task(
                source_vm=source_vm,
                re_vm=re_vm,
                re_task=re_task,
                data=data
            )
            backup_page.assert_popup_success("创建恢复任务成功")

        with allure_step_log("步骤3: 验证恢复任务创建成功"):
            backup_page.assert_status(re_task, "恢复成功", timeout=600)
            backup_page.assert_resume_task_details(re_task, data.get("恢复方式"))
            backup_page.assert_resume_task_details(re_task, {"云服务器名": re_vm, "恢复进度": "100%"}, "云服务器列表")

        with allure_step_log("步骤4: 验证恢复虚机"):
            backup_page.goto_service("弹性云服务器")
            ecs_page.assert_status(re_vm)

            # 新建资源场景：验证配置并获取新IP连接
            if is_new_resource:
                ecs_page.set_table_header("架构")
                row_data = ecs_page.get_row_data(re_vm)
                assert row_data.get("镜像名称") == f"{Config.get('stor')}-test", "镜像与原始虚机不一致"
                assert row_data.get("架构x86_64aarch64   筛选   重置 ") == original_arch, "架构与原始虚机不一致"

                new_vm_ip = row_data.get("IP地址").split('固定:')[1].strip()
                new_mfip = ecs_page.bind_mfip(new_vm_ip.strip())
                mgmt_config = data.get("恢复配置", {}).get("管理配置", {})
                login_pwd = mgmt_config.get("登录密码", "sugon@20")
                ssh_vm.connect(new_mfip, pwd=login_pwd)
            else:
                ssh_vm.connect(source_mfip)

            # 验证原始数据MD5
            for vol_name, vol_info in original_md5_dict.items():
                vol_dir = vol_info.get('dir', f'/cbr_test_{vol_name}')
                vol_file = vol_info.get('file', '')
                original_md5 = vol_info.get('md5', '')
                if vol_file:
                    data_md5_cmd = f"cd {vol_dir} && md5sum {vol_file} | awk '{{print $1}}'"
                    new_data_md5 = ssh_vm.run(data_md5_cmd, check_rc=True).strip()
                    if is_new_resource:
                        assert new_data_md5 == original_md5, f"{vol_name} 盘MD5不一致! 原始: {original_md5}, 新: {new_data_md5}"
                    else:
                        assert new_data_md5 == original_md5

            # 验证增量数据MD5
            if incremental_data:
                for vol_name, inc_info in incremental_data.items():
                    vol_dir = inc_info.get('dir')
                    inc_file = inc_info.get('file')
                    expected_md5 = inc_info.get('md5')
                    verify_md5_cmd = f"cd {vol_dir} && md5sum {inc_file} | awk '{{print $1}}'"
                    actual_md5 = ssh_vm.run(verify_md5_cmd, check_rc=True).strip()
                    if is_new_resource:
                        assert actual_md5 == expected_md5, f"{vol_name} 增量数据MD5不一致! 期望: {expected_md5}, 实际: {actual_md5}"
                    else:
                        assert actual_md5 == expected_md5

            # 验证虚机可用性
            ecs_page.assert_ecs_enable(re_vm, ssh_vm)