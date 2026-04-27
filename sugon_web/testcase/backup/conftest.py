from __future__ import annotations
import time
import pytest
from typing import Any, Dict, Iterator, List, Tuple, Union
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.backup import BackUpPage
from sugon_web.pages.compute import EcsPage
from sugon_web.pages.ops import OpsPage
from sugon_web.pages.network import VpcPage
from sugon_web.testcase.conftest import (
    VmFixtureParams,
    _allocate_eips,
    _build_vm_create_request,
    _build_vm_fixture_names,
    _collect_vm_fixture_metadata,
    _create_vm_resources,
)
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import load_data, random_data


RequestParams = Dict[str, Any]
VmInfo = Dict[str, Any]
VmList = List[VmInfo]
TaskInfo = Dict[str, Any]
TaskList = List[TaskInfo]
BackupTaskData = Union[TaskInfo, TaskList]


def _get_request_params(request: pytest.FixtureRequest) -> RequestParams:
    """返回当前 fixture 调用的参数化载荷。

    本模块中的备份类 fixture 统一约定 ``request.param`` 为字典。若该 fixture
    未被参数化，则返回空字典，便于下游 helper 将其作为可变配置对象继续处理。

    Args:
        request: 当前 pytest fixture request 对象。

    Returns:
        fixture 对应的参数字典；未参数化时返回 ``{}``。

    Example:
        @pytest.mark.parametrize(
            "backup_task",
            [{"task_count": 2}],
            indirect=True,
        )
        def test_xxx(backup_task):
            ...
    """
    return getattr(request, "param", {})


def _create_backup_page_with_session(browser_context: Any, config: Any) -> tuple[Any, BackUpPage]:
    """为类级资源创建已登录的备份页面对象。

    该 helper 统一封装了“打开页面 -> 登录 -> 进入备份服务”的流程，供多个
    class scope 的 fixture 复用，避免重复写会话初始化逻辑。

    Args:
        browser_context: 全局测试环境提供的 Playwright browser context。
        config: ``_create_logged_in_page`` 所需的运行配置。

    Returns:
        ``(page, backup_page)`` 二元组。调用方负责在使用结束后关闭 ``page``。
    """
    page = _create_logged_in_page(browser_context, config)
    backup_page = BackUpPage(page)
    backup_page.goto_service("备份")
    return page, backup_page


def _create_ecs_page_with_session(browser_context: Any, config: Any) -> tuple[Any, EcsPage]:
    """为备份资源准备流程创建已登录的 ECS 页面对象。

    返回的页面已切换到“弹性云服务器”服务，适合 ``vm_backup`` 这类 class scope
    资源 fixture 直接复用。

    Args:
        browser_context: 全局测试环境提供的 Playwright browser context。
        config: ``_create_logged_in_page`` 所需的运行配置。

    Returns:
        ``(page, ecs_page)`` 二元组。调用方负责页面生命周期。
    """
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ecs_page.goto_service("弹性云服务器")
    return page, ecs_page


def _create_vpc_page_with_session(browser_context: Any, config: Any) -> tuple[Any, VpcPage]:
    """为备份资源准备流程创建已登录的 VPC 页面对象。"""
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    vpc_page.goto_service("虚拟私有云")
    return page, vpc_page


def _get_enabled_backup_nodes(ecs_page: EcsPage) -> List[str]:
    """返回当前环境中已启用的备份节点列表。

    这是一个环境前置校验 helper。备份任务创建和迁移场景至少依赖一个可用备份
    节点；如果环境未满足条件，应尽早跳过，而不是在后续断言中报出不易定位的错。

    Args:
        ecs_page: 已登录的 ECS 页面对象，用于跨服务导航和查询。

    Returns:
        已启用备份节点的 IP 列表。

    Raises:
        pytest.skip: 当环境中不存在已启用备份节点时主动跳过。
    """
    with allure_step_log("检查环境备份节点"):
        ecs_page.goto_service("备份设施")
        ecs_page.goto_submenu("备份节点")

        all_states = ecs_page.get_column_data("服务状态")
        all_nodes = ecs_page.get_column_data("节点名称")
        nodes_by_ip = {ip: st for ip, st in zip(all_nodes, all_states) if ip and st}
        enabled_nodes = [ip for ip, status in nodes_by_ip.items() if status == "已启用"]
        if not enabled_nodes:
            pytest.skip("无已启用的备份节点")
        return enabled_nodes


def _build_backup_storage(ecs_page: EcsPage) -> Dict[str, Any]:
    """构造备份源虚机的默认存储配置。

    备份用例默认要求源虚机包含 1 块系统盘和 2 块数据盘，以便后续稳定地执行
    文件写入、备份和恢复校验。

    Args:
        ecs_page: ECS 页面对象，仅用于读取当前环境的存储类型。

    Returns:
        与 ``_build_vm_create_request`` 兼容的 ``storage`` 分组字典。
    """
    return {
        "system_disk": 25,
        "data_disks": [{"vol_type": f"{ecs_page.stor}-type", "size": "25", "count": "2"}],
    }


def _build_vm_backup_params(ecs_page: EcsPage, params: RequestParams) -> VmFixtureParams:
    """将备份场景参数转换为公共 VM fixture 协议。

    备份模块复用了 ``sugon_web.testcase.conftest`` 中定义的通用虚机创建协议。
    该 helper 只补充备份场景所需的最小额外字段，不引入新的创建协议。

    Args:
        ecs_page: ECS 页面对象，用于推导默认存储配置。
        params: 备份场景参数，通常来自 ``request.param``。

    Returns:
        可直接传给 ``_build_vm_create_request`` 的 ``VmFixtureParams``。

    Example:
        params = {"count": 2}
        vm_params = _build_vm_backup_params(ecs_page, params)
    """
    vm_count = params.get("count", 1)
    return {
        "basic": {"count": vm_count},
        "storage": _build_backup_storage(ecs_page),
        "bind_mfip": False,
    }


def _prepare_single_vm_backup_metadata(
    ecs_page: EcsPage,
    ssh_vm: Any,
    vm_data: VmInfo,
    backup_nodes: List[str],
) -> VmInfo:
    """为单台虚机补齐备份场景专用校验元数据。

    通用 VM helper 只返回 ECS 基础元数据；备份场景还需要：
    - 备份节点列表
    - 管理浮动 IP
    - 源数据 MD5 清单
    - 架构信息

    Args:
        ecs_page: ECS 页面对象，用于绑定 IP 和查询虚机详情。
        ssh_vm: SSH fixture，用于连接源虚机并生成校验数据。
        vm_data: 通用 VM helper 返回的一台虚机元数据。
        backup_nodes: 当前环境可用的备份节点列表。

    Returns:
        一个新的虚机元数据字典，除原始字段外，还包含 ``backup_nodes``、
        ``md5_dict``、``mfip`` 和 ``arch``。
    """
    with allure_step_log(f"准备备份源虚机: {vm_data['name']}"):
        ecs_page.set_table_header("架构")
        ecs_page.ecs_bind_pub_ip(vm_data["name"])
        ecs_page.assert_popup_success("执行成功")
        row_data = ecs_page.get_row_data(vm_data["name"])
        arch = row_data.get("架构x86_64aarch64   筛选   重置 ")
        ip = row_data.get("IP地址").split("固定:")[1].strip()
        mfip = OpsPage(ecs_page.page).bind_mfip(ip)
        ssh_vm.connect(mfip)
        md5_dict = ecs_page.vm_pre_data(ssh_vm)

    enriched_vm = dict(vm_data)
    enriched_vm.update({"backup_nodes": backup_nodes, "md5_dict": md5_dict, "mfip": mfip, "arch": arch})
    return enriched_vm


def _prepare_vm_backup_metadata(
    ecs_page: EcsPage,
    ssh_vm: Any,
    vm_list: VmList,
    backup_nodes: List[str],
) -> VmList:
    """批量补齐备份场景所需的虚机元数据。

    Args:
        ecs_page: ECS 页面对象，用于执行虚机相关操作。
        ssh_vm: SSH fixture，用于准备源数据。
        vm_list: 通用 VM helper 返回的虚机元数据列表。
        backup_nodes: 当前环境可用的备份节点列表。

    Returns:
        补齐备份校验字段后的虚机元数据列表。
    """
    return [
        _prepare_single_vm_backup_metadata(
            ecs_page=ecs_page,
            ssh_vm=ssh_vm,
            vm_data=vm_data,
            backup_nodes=backup_nodes,
        )
        for vm_data in vm_list
    ]


def _cleanup_vm_backup_resources(ecs_page: EcsPage, vm_names: List[str]) -> None:
    """清理备份源虚机及其附属资源。

    备份源虚机与普通 VM fixture 不同：它会额外绑定公网/管理 IP，并创建数据盘
    用于校验。因此清理时必须连同卷和 IP 一并释放。

    Args:
        ecs_page: ECS 页面对象，用于移除并删除虚机。
        vm_names: ``vm_backup`` 创建的虚机名称列表。
    """
    if not vm_names:
        return
    with allure_step_log(f"清理备份源虚机: {vm_names}"):
        ecs_page.goto_service("弹性云服务器")
        ecs_page.ecs_remove(vm_names)
        ecs_page.ecs_delete(vm_names, delete_volume=True, release_ip=True)
        ecs_page.assert_deleted(vm_names)


def _load_backup_policy(params: RequestParams) -> Dict[str, Any]:
    """返回 ``backup_task`` 使用的备份策略。

    Args:
        params: fixture 参数字典。若包含 ``policy`` 字段，则优先使用；否则从
            测试数据中加载模块默认策略。

    Returns:
        单个备份策略字典。
    """
    policy_data = load_data("common_backup", "test_backup.yaml")
    return params.get("policy", policy_data[0])


def _validate_backup_task_count(task_count: int, vm_count: int) -> None:
    """校验任务创建数量是否超过可用源虚机数量。

    Args:
        task_count: fixture 参数请求创建的任务数。
        vm_count: 已准备好的源虚机数量。

    Raises:
        ValueError: 当请求任务数大于源虚机数时抛出。
    """
    if task_count > vm_count:
        raise ValueError(f"任务数({task_count})不能大于虚机数量({vm_count})，每个虚机只能创建一个任务")


def _build_backup_task_record(backup_page: BackUpPage, vm: VmInfo, task_name: str) -> TaskInfo:
    """组装备份/恢复用例消费的任务元数据。

    Args:
        backup_page: 备份页面对象，用于查询任务详情字段。
        vm: ``vm_backup`` 返回的、已补齐元数据的源虚机信息。
        task_name: 刚刚创建成功的备份任务名称。

    Returns:
        一个任务元数据字典，包含源虚机、当前目标节点及恢复校验所需字段。
    """
    return {
        "server_names": vm.get("name"),
        "task_name": task_name,
        "cur_target": backup_page.backup_get_cur_target(task_name),
        "backup_nodes": vm.get("backup_nodes"),
        "source_md5": vm.get("md5_dict"),
        "source_mfip": vm.get("mfip"),
        "source_arch": vm.get("arch"),
    }


def _create_backup_tasks(
    backup_page: BackUpPage,
    vm_list: VmList,
    policy: Dict[str, Any],
    task_count: int,
) -> TaskList:
    """按需为源虚机创建一个或多个备份任务。

    该 helper 只负责“创建任务 + 组装任务元数据”，资源生命周期由
    ``backup_task`` fixture 自行管理。

    Args:
        backup_page: 备份页面对象，用于执行任务创建。
        vm_list: ``vm_backup`` 返回的源虚机列表。
        policy: 创建任务时使用的备份策略字典。
        task_count: 要创建的任务数量，按顺序消耗前 ``task_count`` 台虚机。

    Returns:
        任务元数据字典列表。
    """
    task_list: TaskList = []
    for vm in vm_list[:task_count]:
        task_name = f"task{time.strftime('%M%S')}-{vm.get('name')}"
        backup_page.goto_service("备份")
        backup_page.create_backup_task(task_name=task_name, server_names=[vm.get("name")], policy=policy)
        backup_page.assert_popup_success("执行成功")
        backup_page.assert_status(task_name, "创建完成")
        task_list.append(_build_backup_task_record(backup_page, vm, task_name))
    return task_list


def _cleanup_backup_tasks(backup_page: BackUpPage, task_names: List[str]) -> None:
    """以尽力而为模式清理备份任务。

    某些测试在业务流程中可能已经删除、回收或停止了被测任务，因此 teardown
    阶段不能假设任务一定处于固定状态。该 helper 会尝试多种清理路径，并吞掉
    中间异常，确保清理尽量完成。

    Args:
        backup_page: 备份页面对象，用于执行任务操作。
        task_names: 待停止、移除和删除的备份任务名称列表。
    """
    if not task_names:
        return
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


def _cleanup_backup_data(backup_page: BackUpPage, vm_names: List[str]) -> None:
    """清理指定源虚机产生的备份数据。

    Args:
        backup_page: 备份页面对象，用于执行清理操作。
        vm_names: 需要删除备份数据的源虚机名称列表。
    """
    for vm_name in vm_names:
        try:
            with allure_step_log(f"清理 {vm_name} 的备份数据"):
                backup_page.backup_data_delete(vm_name)
        except Exception as e:
            logger.warning(f"清理 {vm_name} 备份数据失败, 错误: {e}")


def _normalize_backup_task_data(task_list: TaskList, task_count: int) -> BackupTaskData:
    """规范化 ``backup_task`` 的返回值，兼容历史用例约定。

    Args:
        task_list: 已创建完成的任务元数据列表。
        task_count: fixture 请求的任务数。

    Returns:
        当 ``task_count == 1`` 时返回 ``task_list[0]``，否则返回完整列表。
    """
    return task_list[0] if task_count == 1 else task_list


@pytest.fixture(scope="function")
def backup_page(page: Any) -> BackUpPage:
    """返回 function 级别的备份页面对象。

    当测试只需要页面交互，而不需要单独管理登录页生命周期时，应使用该 fixture。

    Args:
        page: 共享的 Playwright ``page`` fixture。

    Returns:
        已导航到“备份”服务的 ``BackUpPage`` 对象。

    Example:
        def test_search(backup_page, backup_task):
            backup_page.backup_search(backup_task["task_name"])
    """
    page_object = BackUpPage(page)
    page_object.goto_service("备份")
    return page_object


@pytest.fixture(scope="class")
def vm_backup(
    browser_context: Any,
    config: Any,
    ssh_vm: Any,
    request: pytest.FixtureRequest,
) -> Iterator[VmList]:
    """为当前测试类提供可用于备份的源虚机。

    这是备份模块的核心资源 fixture。它复用通用 VM 创建 helper，随后补齐备份
    场景所需元数据，例如源数据 MD5、MFIP 和可用备份节点列表。

    Parametrization:
        ``request.param`` 支持以下字段：
        - ``count``: 需要创建的源虚机数量。

    Yields:
        虚机元数据字典列表。当前备份用例统一按列表消费该 fixture，即使只创建
        1 台虚机也是如此。

    Example:
        @pytest.mark.parametrize("vm_backup", [{"count": 2}], indirect=True)
        def test_xxx(vm_backup):
            assert len(vm_backup) == 2
    """
    page, ecs_page = _create_ecs_page_with_session(browser_context, config)
    vpc_page_raw, vpc_page = _create_vpc_page_with_session(browser_context, config)
    params = _get_request_params(request)
    vm_params = _build_vm_backup_params(ecs_page, params)
    enabled_nodes = _get_enabled_backup_nodes(ecs_page)
    base_name = random_data()
    create_request, count, network, subnet = _build_vm_create_request(request, vm_params, base_name)
    vm_names = _build_vm_fixture_names(create_request["basic"]["name"], count)

    try:
        _allocate_eips(vpc_page, count=count)
        _create_vm_resources(
            ecs_page=ecs_page,
            create_request=create_request,
            vm_names=vm_names,
        )
        vm_list = _collect_vm_fixture_metadata(ecs_page, vm_names, network, subnet)
        vm_list = _prepare_vm_backup_metadata(ecs_page, ssh_vm, vm_list, enabled_nodes)
        logger.info(f"vm_list: {vm_list}")

        ecs_page.goto_service("备份")
        yield vm_list
    finally:
        try:
            _cleanup_vm_backup_resources(ecs_page, vm_names)
        finally:
            vpc_page_raw.close()
            page.close()


@pytest.fixture(scope="class")
def backup_task(
    browser_context: Any,
    config: Any,
    vm_backup: VmList,
    request: pytest.FixtureRequest,
) -> Iterator[BackupTaskData]:
    """为当前测试类提供已创建完成的备份任务。

    该 fixture 明确保持为“资源型 fixture”：它只负责准备任务并返回任务元数据，
    不负责执行备份、恢复或迁移动作。这些业务动作应保留在测试代码或专用 helper 中。

    Parametrization:
        ``request.param`` 支持以下字段：
        - ``task_count``: 需要创建的任务数量。
        - ``policy``: 备份策略字典；若提供，则覆盖默认测试数据。

    Yields:
        当 ``task_count == 1`` 时返回单个任务元数据字典；否则返回任务元数据列表。

    Example:
        @pytest.mark.parametrize(
            "backup_task",
            [{"task_count": 2}],
            indirect=True,
        )
        def test_batch(backup_task):
            assert len(backup_task) == 2
    """
    page, backup_page = _create_backup_page_with_session(browser_context, config)

    params = _get_request_params(request)
    task_count = params.get("task_count", 1)
    policy = _load_backup_policy(params)

    vm_list = vm_backup
    _validate_backup_task_count(task_count, len(vm_list))
    task_list = _create_backup_tasks(backup_page, vm_list, policy, task_count)
    logger.info(f"task_list: {task_list}")

    backup_task_data = _normalize_backup_task_data(task_list, task_count)
    yield backup_task_data

    try:
        _cleanup_backup_tasks(backup_page, [task.get("task_name") for task in task_list])
        _cleanup_backup_data(backup_page, [task.get("server_names") for task in task_list])
    finally:
        page.close()


@pytest.fixture
def cleanup_backup_task(backup_page: BackUpPage) -> Iterator[List[str]]:
    """收集测试中临时创建的备份任务，并在测试后清理。

    该 fixture 适用于那些在测试函数内部显式创建任务、而不是通过 ``backup_task``
    预置任务的场景。测试将任务名追加到返回列表中，teardown 阶段再统一尽力清理。

    Yields:
        一个可变列表，作为 teardown 清理登记簿。

    Example:
        def test_create(backup_page, cleanup_backup_task):
            cleanup_backup_task.append("task-001")
    """
    task_names: List[str] = []

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
def cleanup_resume_data(ecs_page: EcsPage, backup_page: BackUpPage) -> Iterator[Tuple[List[str], List[str]]]:
    """收集恢复场景产物，并在每条用例结束后清理。

    恢复用例通常会在测试执行过程中动态生成资源名。该 fixture 提供两个可变登记簿：
    - 恢复任务名列表
    - 新创建虚机名列表

    测试在资源创建成功后应立即把名称追加进登记簿，teardown 阶段再以尽力而为方式
    清理这些资源。

    Yields:
        一个 ``(resume_tasks, new_vm_names)`` 元组，两个元素均为可变列表。

    Example:
        def test_resume(cleanup_resume_data):
            resume_tasks, new_vm_names = cleanup_resume_data
            resume_tasks.append("resume-001")
            new_vm_names.append("vm-restore-001")
    """
    resume_tasks: List[str] = []
    new_vm_names: List[str] = []

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
