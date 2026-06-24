"""
跨测试模块共享 Fixture 定义（vm、eip、volume、ops_page 等）。

职责范围:
- 页面与资源 fixture（login_page、ecs_page、vm、eip、volume 等）
- vm fixture 的参数解析、依赖注入、创建与清理
- 弹性公网 IP 的分配与释放
- 飞书测试报告通知 (pytest_sessionfinish)

============================================================
⚠️ 重要提示：该文件禁止修改已有方法 ⚠️
如需新增功能，请仅通过新增函数/fixture 实现。
严禁直接改动现有代码。
============================================================
"""

import re
import time
from pathlib import Path

import allure
import pytest
from sugon_web.pages.login import LoginPage
from sugon_web.pages.network import VpcPage
from sugon_web.pages.ops import OpsPage
from sugon_web.pages.storage import EvsPage
from sugon_web.pages.storage.obs import ObsPage
from sugon_web.pages.compute import EcsPage, BmsPage
from sugon_web.pages.compute.ecs import (
    EcsCreateRequest,
    EcsBasicConfig,
    EcsStorageConfig,
    EcsNetworkConfig,
    EcsManageConfig,
    EcsAdvancedConfig,
    _normalize_ecs_create_request,
)
from typing import Any, Callable, Iterator, NotRequired, TypedDict
from sugon_web.testcase.compute.vm_fixture.types import VmMetadata
from sugon_web.config.config import Config
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page


@pytest.fixture(scope="function")
def login_page(page):
    """初始化登录页对象"""
    login_page = LoginPage(page)
    login_page.logout()   # 登录测试用例需要先退出登录状态
    return login_page


@pytest.fixture(scope="function")
def evs_page(page):
    """初始化云硬盘页对象"""
    return EvsPage(page)


@pytest.fixture()
def volume(evs_page, request):
    """初始化云硬盘数据

    Args:
        evs_page: 云硬盘页面对象
        request: pytest fixture，用于获取参数和动态获取其他 fixture
        request.param: 包含云硬盘配置的字典，例如：
            {
                "empty": True,  # 是否创建空白云硬盘，默认为True
                "image_name": "",  # 镜像名称，当empty=False时使用
                "size": 30,  # 云硬盘大小，默认为30GB
                "desc": "",  # 云硬盘描述，默认为空
                "shared": False,  # 是否创建共享云硬盘，默认为False
            }
    """
    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    empty = params.get('empty', True)
    image_name = params.get('image_name', '')
    size = params.get('size', 30)
    desc = params.get('desc', '')
    shared = params.get('shared', False)

    # 当存储类型为 local 时，且测试用例引用了 vm fixture 时，才动态获取 host 信息
    host = None
    if evs_page.stor == 'local' and 'vm' in request.fixturenames:
        resource = request.getfixturevalue('vm')
        if isinstance(resource, list):
            resource = resource[0]
        host = resource.get('host')
        logger.info(f"检测到存储类型为{evs_page.stor}，从虚机 {resource['name']} 获取 host: {host}")

    name = random_data()

    # 构建云硬盘创建参数
    create_kwargs = {
        "name": name,
        "empty": empty,
        "image_name": image_name,
        "size": size,
        "desc": desc,
        "shared": shared,
        "host": host
    }
    with allure_step_log("创建云硬盘"):
        evs_page.evs_create(**create_kwargs)
        evs_page.assert_popup_success()
        evs_page.assert_status(name, status="可用")
        row_data = evs_page.get_row_data(name)
        volume = {"name": name}

    yield volume

    evs_page.evs_remove(volume["name"])
    evs_page.assert_deleted(volume["name"])
    evs_page.evs_delete(volume["name"])
    evs_page.assert_deleted(volume["name"])


@pytest.fixture(scope="function")
def ecs_page(page):
    """初始化弹性云服务器页对象"""
    return EcsPage(page)


@pytest.fixture(scope="function")
def obs_page(page):
    """初始化对象存储专业版页对象并导航到服务页"""
    obs = ObsPage(page)
    obs.goto_service("对象存储专业版")
    return obs


@pytest.fixture(scope="function")
def ops_page(request):
    """初始化运维管理页对象。

    admin 角色直接使用当前 page；非 admin 角色自动切换为 admin_page，
    以支持普通用户执行测试时用 admin 权限操作基础设施服务。
    """
    user_role = Config.get("user_role", "admin")
    if user_role == "admin":
        page = request.getfixturevalue("page")
    else:
        page = request.getfixturevalue("admin_page")
    return OpsPage(page)


@pytest.fixture(scope="function")
def bms_page(page):
    """初始化裸金属BMS页对象"""
    return BmsPage(page)


@pytest.fixture(scope="class")
def vm(
    browser_context: Any,
    admin_browser_context: Any,
    config: Any,
    request: pytest.FixtureRequest,
    ssh_host: Any,
) -> Iterator[VmMetadata | list[VmMetadata]]:
    """创建弹性云服务器（ECS）资源，测试结束后自动清理。

    通用 ECS 资源 fixture，支持单实例/多实例创建、MFIP 自动绑定、
    依赖注入（安全组/标签/亲和组）。scope 为 class 级别，同一测试类内
    复用已创建的 VM。

    Args:
        browser_context: Playwright BrowserContext，用于创建独立页面。
        config: 测试配置对象，包含 base_url、admin 凭据等。
        request: pytest 请求对象，通过 request.param 接收参数字典。
        ssh_host: SSH 客户端，用于后端查询 VM 元数据（port_id/project_id）。

    Yields:
        VmMetadata: 单实例时返回单个字典；多实例时返回字典列表。
        元数据字段包含：
            - name (str): 虚机名称
            - id (str): 虚机 UUID
            - ip (str): 内网 IPv4
            - ipv6 (str): 内网 IPv6（如有）
            - host (str): 所在物理机
            - flavor (str): 规格
            - image (str): 镜像名称
            - project (str): 项目名称
            - network (str): 网络名称
            - subnet (str): 子网名称
            - mfip (str | None): MFIP 地址（bind_mfip=True 时填充）
            - port_id (str | None): 端口 ID（ssh_host 可用时填充）
            - project_id (str | None): 项目 ID（ssh_host 可用时填充）

    request.param 支持的参数：
        basic (dict): 基础配置，支持 name、count（默认 1）、cluster、
            flavor 等。count > 1 时名称自动添加 ``-index`` 后缀。
        storage (dict): 存储配置，支持 storage_pool、image.source、
            image.name、system_disk 等。
        network (dict): 网络配置，支持 networks 列表、enable_ipv6 等。
        manage (dict): 管理配置，支持 login_type、login_pwd、vnc_pwd 等。
        bind_mfip (bool): 是否自动绑定 MFIP，默认 True。
        name_prefix (str): 名称前缀，用于多实例批次区分。
        instances (list[dict]): 多批次创建配置列表。提供时忽略外层
            basic/count，按列表逐项创建不同配置的 VM。
        inject_dependencies (bool): 是否自动注入依赖（SG/标签/亲和组），
            默认 True。
        inject_sg / inject_labels / inject_affinity (bool): 单项依赖开关。

    使用示例::

        # 单实例，默认绑定 MFIP
        def test_ecs_basic(self, vm):
            ssh_vm.connect(vm["mfip"])
            ...

        # 多实例，不绑定 MFIP（内网场景）
        @pytest.mark.parametrize(
            "vm", [{"basic": {"count": 3}, "bind_mfip": False}], indirect=True
        )
        def test_ecs_batch(self, vm):
            names = [v["name"] for v in vm]
            ...

        # 多批次不同配置
        @pytest.mark.parametrize(
            "vm",
            [{
                "instances": [
                    {"basic": {"count": 1, "flavor": "ecs.c6.large"}},
                    {"basic": {"count": 2, "flavor": "ecs.c6.small"}},
                ]
            }],
            indirect=True,
        )

    二、依赖 fixture 自动注入

    若测试同时声明了某些已注册依赖 fixture，`vm` 会自动把它们映射到
    ECS 创建参数中。例如：
    - `sg` -> `network.security_groups`
    - `labels` -> `basic.labels`
    - `affinity` -> `advanced.affinity`

    示例：
        @pytest.mark.parametrize("sg", [2], indirect=True)
        @pytest.mark.parametrize("labels", [{"count": 3}], indirect=True)
        @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
        def test_xxx(vm, sg, labels):
            ...

    Note:
        - scope 为 class，同一测试类内所有方法共享同一批 VM。
        - 支持通过 ``@fixture.path`` 语法引用其他 fixture 值作为参数。
        - 创建成功后立即将 VM 名称注册到 ``vm_names``，确保后续步骤
          失败时仍能在 teardown 中正确清理。
        - MFIP 绑定使用独立 admin 页面上下文，避免污染测试用户登录态。
    """
    from sugon_web.testcase.compute.vm_fixture.param_parser import _get_vm_fixture_params
    from sugon_web.testcase.compute.vm_fixture.request_builder import (
        _build_vm_create_request,
        _build_vm_instance_params,
    )
    from sugon_web.testcase.compute.vm_fixture.resource_creator import (
        _build_vm_fixture_names,
        _create_vm_resources,
    )
    from sugon_web.testcase.compute.vm_fixture.metadata_collector import _collect_vm_fixture_metadata
    from sugon_web.testcase.compute.vm_fixture.mfip_binder import _bind_vm_fixture_mfips
    from sugon_web.testcase.compute.vm_fixture.cleanup_manager import _cleanup_vm_resources

    # 解析参数，支持 @fixture.path 引用解析
    params = _get_vm_fixture_params(request)
    instance_params_list = params.get("instances") or []
    if instance_params_list and not isinstance(instance_params_list, list):
        raise TypeError("'vm.instances' expects a list of dict items")

    # 创建独立页面，生命周期由本 fixture 管理
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    # vm_names 用于跟踪已创建 VM，确保 teardown 时无泄漏
    vm_names: list[str] = []

    try:
        metadata_list: list[VmMetadata] = []
        name_prefix = params.get('name_prefix', '')

        if instance_params_list:
            # 多批次创建模式：每项实例可独立配置
            shared_params = {key: value for key, value in params.items() if key != "instances"}
            for instance_params in instance_params_list:
                instance_config = _build_vm_instance_params(shared_params, instance_params)
                base_name = f"{name_prefix}{random_data()}"
                create_request, count, network, subnet = _build_vm_create_request(
                    request, instance_config, base_name
                )

                current_vm_names = _build_vm_fixture_names(base_name, count)
                _create_vm_resources(
                    ecs_page=ecs_page,
                    create_request=create_request,
                    vm_names=current_vm_names,
                )
                # 关键：创建成功后立即注册，防止后续步骤失败导致泄漏
                vm_names.extend(current_vm_names)

                current_metadata = _collect_vm_fixture_metadata(
                    ecs_page, current_vm_names, network, subnet, ssh_host
                )

                if instance_config.get("bind_mfip", True):
                    _bind_vm_fixture_mfips(admin_browser_context, config, current_metadata)

                metadata_list.extend(current_metadata)
        else:
            # 单批次创建模式：使用外层统一参数
            bind_mfip = params.get("bind_mfip", True)
            base_name = f"{name_prefix}{random_data()}"
            create_request, count, network, subnet = _build_vm_create_request(
                request, params, base_name
            )
            vm_names = _build_vm_fixture_names(create_request["basic"]["name"], count)

            _create_vm_resources(
                ecs_page=ecs_page,
                create_request=create_request,
                vm_names=vm_names,
            )
            metadata_list = _collect_vm_fixture_metadata(
                ecs_page, vm_names, network, subnet, ssh_host
            )

            if bind_mfip:
                _bind_vm_fixture_mfips(admin_browser_context, config, metadata_list)

        # 单实例返回字典，多实例返回列表
        yield metadata_list[0] if len(metadata_list) == 1 else metadata_list
    finally:
        # 先清理 VM 资源，再关闭页面，确保无泄漏
        try:
            _cleanup_vm_resources(ecs_page, vm_names)
        finally:
            page.close()

@pytest.fixture(scope="function")
def test_context(request):
    """用于在测试用例各步骤间传递数据的上下文"""
    if not hasattr(request.node, "test_context"):
        request.node.test_context = {}
    return request.node.test_context


def _allocate_eips(
    vpc_page: VpcPage,
    count: int = 1,
    pool: str = 'public_net(基础版)',
    method: str = '快速选择',
    ip: str | None = None,
) -> list[str]:
    """分配并返回弹性公网IP列表。"""
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count!r}")

    with allure_step_log(f"Setup: 分配 {count} 个弹性公网IP"):
        created_ips = vpc_page.eip_allocate(pool=pool, count=count, method=method, ip=ip)
        vpc_page.assert_popup_success("执行成功")

    if created_ips is None:
        return []
    if isinstance(created_ips, list):
        return created_ips
    if isinstance(created_ips, tuple):
        return list(created_ips)
    return [created_ips]


def _release_eips(
    vpc_page: VpcPage,
    created_ips: str | list[str] | tuple[str, ...] | None,
) -> None:
    """释放已创建的弹性公网IP。"""
    if created_ips is None:
        current_ips = []
    elif isinstance(created_ips, list):
        current_ips = created_ips
    elif isinstance(created_ips, tuple):
        current_ips = list(created_ips)
    else:
        current_ips = [created_ips]

    with allure_step_log(f"Teardown: 释放弹性公网IP {current_ips}"):
        if not current_ips:
            return

        try:
            for current_ip in current_ips:
                vpc_page.goto_service('虚拟私有云')
                vpc_page.search(current_ip)
                if current_ip in vpc_page.get_eip_list():
                    vpc_page.eip_release(current_ip)
                    vpc_page.assert_deleted(current_ip)
                vpc_page.btn_reset.click()
        except Exception as e:
            logger.warning(f"清理弹性公网IP时出错: {e}")


@pytest.fixture(scope="function")
def eip(page: Any, request: pytest.FixtureRequest) -> Iterator[str | list[str]]:
    """创建并返回弹性公网IP，测试结束后自动清理。"""
    params = getattr(request, 'param', {})
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        raise TypeError(
            f"'eip' fixture expects request.param to be a dict, got {type(params).__name__}"
        )

    count = params.get('count', 1)
    pool = params.get('pool', Config.get('network'))
    method = params.get('method', '快速选择')
    ip = params.get('ip')

    vpc_page = VpcPage(page)
    vpc_page.goto_service('虚拟私有云')

    created_ips = _allocate_eips(vpc_page, count=count, pool=pool, method=method, ip=ip)
    result = created_ips[0] if count == 1 else created_ips

    try:
        yield result
    finally:
        _release_eips(vpc_page, created_ips)


# ── 飞书测试报告通知 ──────────────────────────────────────────

def pytest_sessionstart(session: pytest.Session) -> None:
    """记录测试会话开始时间，用于后续计算总耗时。"""
    session._feishu_start_time = time.time()  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """测试会话结束后，自动发送统计报告到飞书。"""
    import json
    import glob
    import os
    from sugon_web.utils.feishu_notifier import send_feishu_report

    passed = 0
    failed = 0
    skipped = 0
    error = 0
    case_results = []

    # 通过 terminal reporter 获取准确的测试结果统计
    terminalreporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter and hasattr(terminalreporter, "stats"):
        passed = len(terminalreporter.stats.get("passed", []))
        failed = len(terminalreporter.stats.get("failed", []))
        skipped = len(terminalreporter.stats.get("skipped", []))
        error = len(terminalreporter.stats.get("error", []))

    # 从 allure-result 读取测试详情（标题、耗时、步骤）
    allure_details: dict[str, dict] = {}
    rootdir = str(
        session.config.rootpath if hasattr(session.config, "rootpath") else session.config.rootdir
    )
    allure_dir = getattr(session.config.option, "allure_report_dir", None) or os.path.join(
        rootdir, "allure-result"
    )
    for result_file in glob.glob(os.path.join(allure_dir, "*-result.json")):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            full_name = data.get("fullName", "")
            start = data.get("start", 0)
            stop = data.get("stop", 0)
            duration_sec = (stop - start) / 1000.0 if stop > start else 0
            if duration_sec < 60:
                duration_str = f"{duration_sec:.1f}秒"
            else:
                duration_str = f"{int(duration_sec // 60)}分{int(duration_sec % 60)}秒"
            allure_details[full_name] = {
                "title": data.get("name", ""),
                "outcome": data.get("status", "unknown"),
                "duration": duration_str,
                "steps": [s.get("name", "") for s in data.get("steps", [])],
            }
        except Exception:
            pass

    # 收集每个用例的结果明细，匹配 allure 详情
    if terminalreporter and hasattr(terminalreporter, "stats"):
        for outcome in ["passed", "failed", "skipped", "error"]:
            for rep in terminalreporter.stats.get(outcome, []):
                nodeid = getattr(rep, "nodeid", "unknown")
                case_name = nodeid.split("::")[-1]
                if "::" not in nodeid:
                    continue
                # 转换 nodeid 为 allure fullName 格式
                parts = nodeid.split("::")
                file_part = parts[0].replace("/", ".").replace("\\", ".")
                if file_part.endswith(".py"):
                    file_part = file_part[:-3]
                if len(parts) == 3:
                    full_name = f"{file_part}.{parts[1]}#{parts[2]}"
                elif len(parts) == 2:
                    full_name = f"{file_part}#{parts[1]}"
                else:
                    full_name = file_part

                detail = allure_details.get(full_name, {})
                case_results.append(
                    {
                        "name": case_name,
                        "title": detail.get("title", case_name),
                        "outcome": outcome,
                        "duration": detail.get("duration", "未知"),
                        "steps": detail.get("steps", []),
                    }
                )
    else:
        # fallback：通过 _pytest 内部状态统计
        for item in session.items:
            for key in item.stash:
                rep = item.stash[key]
                if hasattr(rep, "when") and hasattr(rep, "outcome"):
                    if rep.when == "call":
                        if rep.outcome == "passed":
                            passed += 1
                        elif rep.outcome == "failed":
                            failed += 1
                        elif rep.outcome == "skipped":
                            skipped += 1
                    elif rep.when in ("setup", "teardown") and rep.outcome == "failed":
                        error += 1

    start_time = getattr(session, "_feishu_start_time", None)
    if start_time:
        duration = time.time() - start_time
    else:
        duration = 0

    if duration < 60:
        duration_str = f"{duration:.1f}秒"
    else:
        duration_str = f"{int(duration // 60)}分{int(duration % 60)}秒"

    stats = {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "error": error,
        "duration": duration_str,
        "case_results": case_results,
    }

    logger.info(f"测试会话结束，统计: {stats}")
    send_feishu_report(stats)


# ── 自动 mark 体系 ──────────────────────────────────────────────
# 新增模块目录或服务前缀时，只要遵循 testcase/<module>/test_<service>_*.py
# 的命名约定，就无需修改本文件。
# 多词服务名（如 internal_dns）需要在 sugon_web/config/service_marks.yaml
# 中注册描述，确保 _resolve_service_mark 能做最长前缀匹配。

import yaml

_SERVICE_NAME_RE = re.compile(r"^test_([a-zA-Z0-9]+)_.*\.py$")
_FILE_MARK_RE = re.compile(r"^test_([a-zA-Z0-9_]+)\.py$")


_SERVICE_MARKS_CONFIG_PATH = Path(__file__).parent.parent / "config" / "service_marks.yaml"


def _load_service_descriptions() -> dict:
    """加载 service_marks.yaml 中的 mark 描述映射。

    配置文件不存在或解析失败时返回空字典，保证 pytest 仍能启动。
    """
    if not _SERVICE_MARKS_CONFIG_PATH.exists():
        return {}
    try:
        with open(_SERVICE_MARKS_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"加载 service_marks.yaml 失败: {e}")
        return {}


_SERVICE_DESCRIPTIONS = _load_service_descriptions()


def _resolve_service_mark(filename):
    """从测试文件名提取服务级 mark。

    优先按 _SERVICE_DESCRIPTIONS 中的已知服务做最长前缀匹配，兼容
    test_bms_bind.py、test_bms_remove_label.py 等非规范命名；
    未知服务则 fallback 到 test_<service>_* 的首个下划线段。
    """
    for service in sorted(_SERVICE_DESCRIPTIONS, key=len, reverse=True):
        if filename.startswith(f"test_{service}_"):
            return service
    match = _SERVICE_NAME_RE.match(filename)
    return match.group(1) if match else None


def _resolve_file_mark(filename):
    """从测试文件名提取文件级 mark，如 test_mysql_basic.py -> mysql_basic。"""
    match = _FILE_MARK_RE.match(filename)
    return match.group(1) if match else None


def pytest_configure(config):
    """在 pytest 启动时动态注册所有模块级和服务级 mark。

    扫描 testpaths 下的测试文件，自动提取模块目录名和服务前缀，
    追加到 markers 配置中。配合 --strict-markers 时，新增服务也
    不会触发未知 mark 错误。
    """
    testpaths = config.getini("testpaths") or ["sugon_web/testcase"]
    if isinstance(testpaths, str):
        testpaths = [testpaths]

    module_marks = set()
    service_marks = set()
    file_marks = set()

    for tp in testpaths:
        base = Path(tp)
        if not base.is_absolute():
            base = Path(config.rootpath) / base
        if not base.is_dir():
            # PyCharm 从子目录启动单用例时，相对 testpaths 可能解析不到项目根。
            base = Path(__file__).parent
        if not base.is_dir():
            continue
        for path in base.rglob("test_*.py"):
            parts = path.parts
            if "testcase" in parts:
                idx = parts.index("testcase")
                if len(parts) > idx + 1:
                    module_marks.add(parts[idx + 1])

            service = _resolve_service_mark(path.name)
            if service:
                service_marks.add(service)
            file_mark = _resolve_file_mark(path.name)
            if file_mark:
                file_marks.add(file_mark)

    for mark in sorted(module_marks):
        desc = _SERVICE_DESCRIPTIONS.get(mark, f"{mark}测试")
        config.addinivalue_line("markers", f"{mark}: 模块级-{desc}")

    for mark in sorted(service_marks):
        desc = _SERVICE_DESCRIPTIONS.get(mark, mark)
        config.addinivalue_line("markers", f"{mark}: 服务级-{desc}")

    for mark in sorted(file_marks):
        config.addinivalue_line("markers", f"{mark}: 文件级-{mark}")


def pytest_collection_modifyitems(config, items):
    """根据测试文件路径自动添加模块级和服务级 pytest mark。

    模块级 mark：testcase/<module>/ 下的直接子目录名。
    服务级 mark：文件名 test_<service>_*.py 中的 service 部分。
    新增模块目录或服务前缀时，只要遵循命名约定，无需修改本函数。
    """
    for item in items:
        path = item.path
        parts = path.parts

        # ── 模块级 mark（按目录） ──
        if "testcase" in parts:
            idx = parts.index("testcase")
            if len(parts) > idx + 1:
                module_mark = parts[idx + 1]
                item.add_marker(module_mark)

        # ── 服务级 mark（按文件名） ──
        service_mark = _resolve_service_mark(path.name)
        if service_mark:
            item.add_marker(service_mark)

        # ── 文件级 mark（按完整文件名） ──
        file_mark = _resolve_file_mark(path.name)
        if file_mark:
            item.add_marker(file_mark)


def _resolve_ecs_feature(module_name):
    """根据 ECS 文件名解析 feature 名称。"""
    if module_name.startswith("test_ecs_affinity"):
        return "亲和组"
    if module_name == "test_ecs_labels":
        return "标签"
    if module_name == "test_ecs_recycle":
        return "回收站"
    if module_name == "test_ecs_snapshot":
        return "云服务器快照"
    return "弹性云服务器 ECS"


def pytest_runtest_setup(item):
    """多环境调度时，仅对 ECS/EVS 用例动态注入 host/stor 到 epic/feature。

    其他用例保持现有静态 @allure.epic/@allure.feature 不变。
    """
    host = item.config.getoption("--host")
    stor = item.config.getoption("--stor")

    module_name = item.path.stem
    parent = item.path.parent.name

    if parent == "compute" and module_name.startswith("test_ecs_"):
        epic = "计算服务"
        feature = _resolve_ecs_feature(module_name)
    elif parent == "storage" and module_name.startswith("test_evs_"):
        epic = "存储服务"
        feature = "云硬盘"
    else:
        return

    if host:
        epic = f"{epic} / {host}"
    if stor:
        feature = f"{feature} / {stor}"

    allure.dynamic.epic(epic)
    allure.dynamic.feature(feature)
