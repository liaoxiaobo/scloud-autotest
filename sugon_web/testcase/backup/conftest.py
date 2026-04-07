import time
import pytest
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.backup import BackUpPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.ecs_create import EcsCreatePage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import load_data


@pytest.fixture(scope="function")
def backup_page(page):
    """初始化备份任务页对象。"""
    backup_page = BackUpPage(page)
    backup_page.goto_service("备份")
    return backup_page


@pytest.fixture(scope="class")
def vm_backup(browser_context, config, ssh_vm, request):
    """创建并返回虚机备份数据，支持批量创建。"""
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ecs_create_page = EcsCreatePage(page)
    ecs_page.goto_service("弹性云服务器")

    params = getattr(request, "param", {})
    vm_count = params.get("count", 1)

    with allure_step_log("检查环境备份节点"):
        ecs_page.goto_service("备份设施")
        ecs_page.goto_submenu("备份节点")

        state = ecs_page.get_column_data("服务状态")
        ips = ecs_page.get_column_data("IP地址")
        nodes_dic = {ip: st for ip, st in zip(ips, state) if ip and st}
        enabled_nodes = [ip for ip, status in nodes_dic.items() if status == "已启用"]
        if not enabled_nodes:
            pytest.skip("无已启用的备份节点")

    with allure_step_log("预置公网IP"):
        ecs_page.assign_ip(count=str(vm_count))

    with allure_step_log("预置虚机及数据"):
        ecs_page.goto_service("弹性云服务器")
        basic, network, manage, advanced = {"数量": vm_count}, {}, {}, {}
        storage = {
            "系统盘": 25,
            "数据盘": [{"vol_type": f"{ecs_page.stor}-type", "size": "25", "count": "2"}],
        }
        vm_info = ecs_create_page.ecs_create(basic, storage, network, manage, advanced)
        vm_name = vm_info.get("name")

        if vm_count == 1:
            vm_names = [vm_name]
        else:
            vm_names = [f"{vm_name}-{j}" for j in range(vm_count)]
        ecs_page.assert_status(vm_names, f"-{time.strftime('%Y%m%d')}", refresh=True)

        vm_list = []
        ecs_page.goto_service("云硬盘")
        ecs_page.goto_submenu("云硬盘")
        for vm_name in vm_names:
            ecs_page.btn_refresh.click()
            rows = ecs_page.get_rows_by_text(f"{vm_name}-")

            vols = {}
            for row in rows.all():
                row_data = ecs_page.get_row_data_by_locator(row)
                v_name = row_data.get("名称")
                ecs_page.assert_status(v_name, "正在使用", refresh=True)
                vol_name = row_data.get("挂载信息").split("上的")[-1]
                vol_size = row_data.get("容量")
                if vol_name not in vols and vol_name != "--":
                    vols.update({vol_name: vol_size})
            vm_list.append({"name": vm_name, "vols": vols})

        for vm_name in vm_list:
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_bind_pub_ip(vm_name.get("name"))
            ecs_page.assert_popup_success("执行成功")
            ecs_page.set_table_header("架构")
            row_data = ecs_page.get_row_data(vm_name.get("name"))
            arch = row_data.get("架构x86_64aarch64   筛选   重置 ")
            ip = row_data.get("IP地址").split("固定:")[1].strip()
            mfip = ecs_page.bind_mfip(ip.strip())
            ssh_vm.connect(mfip)
            md5_dict = ecs_create_page.vm_pre_data(ssh_vm, vm_name.get("vols"))
            vm_name.update({"backup_nodes": enabled_nodes, "md5_dict": md5_dict, "mfip": mfip, "arch": arch})
        logger.info(f"vm_list: {vm_list}")

    ecs_create_page.goto_service("备份")

    yield vm_list

    with allure_step_log("清理虚机"):
        vm_names = [vm_info.get("name") for vm_info in vm_list]
        ecs_page.goto_service("弹性云服务器")
        ecs_page.ecs_remove(vm_names)
        ecs_page.ecs_delete(vm_names, delete_volume=True, release_ip=True)
        ecs_page.assert_deleted(vm_names)
        page.close()


@pytest.fixture(scope="class")
def backup_task(browser_context, config, vm_backup, request):
    """创建并返回备份任务数据，支持批量创建。"""
    page = _create_logged_in_page(browser_context, config)
    backup_page = BackUpPage(page)
    backup_page.goto_service("备份")

    params = getattr(request, "param", {})
    task_count = params.get("task_count", 1)

    policy_data = load_data("common_backup", "test_backup.yaml")
    policy = params.get("policy", policy_data[0])

    vm_list = vm_backup
    vm_count = len(vm_list)
    if task_count > vm_count:
        raise ValueError(f"任务数({task_count})不能大于虚机数量({vm_count})，每个虚机只能创建一个任务")

    task_list = []
    for i in range(task_count):
        vm = vm_list[i]
        task_name = f"task{time.strftime('%M%S')}-{vm.get('name')}"
        backup_page.goto_service("备份")
        backup_page.create_backup_task(task_name=task_name, server_names=[vm.get("name")], policy=policy)
        backup_page.assert_popup_success("执行成功")
        backup_page.assert_status(task_name, "创建完成")

        task = {
            "server_names": vm.get("name"),
            "task_name": task_name,
            "cur_target": backup_page.backup_get_cur_target(task_name),
            "backup_nodes": vm.get("backup_nodes"),
            "source_md5": vm.get("md5_dict"),
            "source_mfip": vm.get("mfip"),
            "source_arch": vm.get("arch"),
        }
        task_list.append(task)
    logger.info(f"task_list: {task_list}")

    yield task_list[0] if task_count == 1 else task_list

    task_names = [task_list[i].get("task_name") for i in range(len(task_list))]
    try:
        backup_page.backup_batch_operation(task_names, "停止")
    except Exception:
        pass
    try:
        backup_page.backup_batch_operation(task_names, "删除")
    except Exception:
        pass
    try:
        backup_page.backup_delete(task_names)
        backup_page.assert_deleted(task_names)
    except Exception:
        pass

    for task in task_list:
        vm_name = task.get("server_names")
        try:
            with allure_step_log(f"清理 {vm_name} 的备份数据"):
                backup_page.backup_data_delete(vm_name)
        except Exception as e:
            logger.warning(f"清理 {vm_name} 备份数据失败, 错误: {e}")
    page.close()


@pytest.fixture
def cleanup_backup_task(backup_page):
    """自动清理备份任务。"""
    task_names = []

    yield task_names

    for task_name in task_names:
        try:
            with allure_step_log(f"清理测试数据: {task_name}"):
                backup_page.backup_remove(task_name)
                backup_page.backup_delete(task_name)
                backup_page.assert_deleted(task_name)
        except Exception as e:
            allure_step_log(f"清理失败: {task_name}, 错误: {e}")
        if "once" in task_name:
            vm_name = task_name.split("-")[-1]
            try:
                with allure_step_log(f"清理 {vm_name} 的备份数据"):
                    backup_page.backup_data_delete(vm_name)
            except Exception as e:
                logger.warning(f"清理 {vm_name} 备份数据失败, 错误: {e}")


@pytest.fixture(scope="function")
def cleanup_resume_data(ecs_page, backup_page):
    """自动清理恢复任务和恢复产生的新虚机。"""
    resume_tasks = []
    new_vm_names = []

    yield resume_tasks, new_vm_names

    if resume_tasks:
        try:
            with allure_step_log(f"清理恢复任务: {resume_tasks}"):
                backup_page.goto_service("备份")
                backup_page.delete_resume_task(resume_tasks)
        except Exception as e:
            logger.warning(f"清理恢复任务失败: {resume_tasks}, 错误: {e}")

    if new_vm_names:
        try:
            with allure_step_log(f"清理恢复产生的新虚拟机: {new_vm_names}"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.ecs_remove(new_vm_names)
                ecs_page.ecs_delete(new_vm_names, delete_volume=True, release_ip=True)
                ecs_page.assert_deleted(new_vm_names)
        except Exception as e:
            logger.warning(f"清理虚拟机失败: {new_vm_names}, 错误: {e}")

    backup_page.goto_service("备份")


@pytest.fixture(scope="class")
def backup_with_full_backup(browser_context, config, backup_task, ssh_vm):
    """执行全量备份并返回备份数据。"""
    page = _create_logged_in_page(browser_context, config)
    backup_page = BackUpPage(page)
    backup_page.goto_service("备份")

    task_name = backup_task.get("task_name")
    source_vm = backup_task.get("server_names")
    source_mfip = backup_task.get("source_mfip")
    original_md5_dict = backup_task.get("source_md5")
    original_arch = backup_task.get("source_arch")

    backup_data = []

    with allure_step_log("前置步骤: 执行全量备份"):
        backup_page.goto_service("备份")
        backup_page.exec_backup(task_name, "执行全量")
        backup_page.assert_popup_success("备份任务执行成功")
        backup_page.assert_status(task_name, "已启动", timeout=600)
        re_data = backup_page.get_backup_data(source_vm)
        backup_data.extend(re_data)

    yield {
        "task_name": task_name,
        "server_names": source_vm,
        "source_mfip": source_mfip,
        "source_md5": original_md5_dict,
        "backup_data": backup_data,
        "original_arch": original_arch,
    }
    page.close()
