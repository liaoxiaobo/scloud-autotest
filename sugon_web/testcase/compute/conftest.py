import time
import pytest
from sugon_web.pages.network import VpcPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data
from sugon_web.conftest import _create_logged_in_page


@pytest.fixture()
def ecss(ecs_page, vm):
    """创建并返回一个ECS快照名称，测试结束后自动清理。"""
    vm_name = vm.get("name")
    snapshot_name = f"{vm_name}{time.strftime('%H%M%S')}"
    with allure_step_log("setup: 创建系统盘快照"):
        ecs_page.ecss_create(name=vm_name, snapshot_name=snapshot_name)
        ecs_page.assert_popup_success("创建实例快照成功")
        ecs_page.assert_status(vm_name)

        ecs_page.goto_submenu("快照")
        ecs_page.assert_status(snapshot_name, status="可用", refresh=True)

    yield {"name": snapshot_name, "vm_name": vm_name}

    with allure_step_log("清理测试数据"):
        ecs_page.ecss_delete(snapshot_name)
        ecs_page.assert_deleted(snapshot_name, refresh=True)


@pytest.fixture()
def ecss_policy(ecs_page):
    """创建并返回一个云服务器快照策略，测试结束后自动清理。"""
    policy_name = random_data()

    with allure_step_log("setup: 创建快照策略"):
        ecs_page.ecss_policy_create(
            name=policy_name,
            hours=[0, 1, 2],
            enabled=True,
            cycle_days=1,
            retention_type="按数量",
            retention_value=1,
        )

    ecs_page.assert_popup_success("执行成功")

    yield {"name": policy_name}

    with allure_step_log("清理测试数据"):
        ecs_page.ecss_policy_delete(policy_name)
        ecs_page.assert_deleted(policy_name)
        ecs_page.assert_popup_success("删除策略成功")


@pytest.fixture()
def image(ssh_host, ecs_page, request):
    """动态创建镜像，支持从测试用例层传参。"""
    params = getattr(request, "param", {})
    name = params.get("name", random_data())
    backend = params.get("backend", ecs_page.storage_pool)
    if backend.startswith("local"):
        backend = "local-test"
    image_name = params.get("image", "AnolisOS-8.9-x86_64-minimal.iso")
    with allure_step_log(f"创建镜像 {name}"):
        ssh_host.glance_image_create(name, image=image_name, backend=backend)
    yield {"name": name}
    ssh_host.glance_image_delete(name)


@pytest.fixture
def pool(ops_page, vm, request):
    """动态创建存储池，测试结束后自动清理。"""
    params = getattr(request, "param", {})
    node = params.get("node", vm.get("host"))

    pool_name = f"disk_{random_data()}"
    with allure_step_log("创建指定数量的虚机"):
        ops_page.goto_service("基础设施")
        _disk_name, _disk_size = ops_page.enable_disk("所在物理机", node)

        storage_type = params.get("storage_type", "本地磁盘")
        ops_page.create_storage_pool(pool_name, device_type=_disk_size, storage_type=storage_type)
        ops_page.sync_storage_pool_config()
        ops_page.sync_pool_size(pool_name)

        pool_data = {"pool_name": pool_name, "disk_size": _disk_size, "disk_name": _disk_name}
        pool_data.update(vm)
        logger.info(f"pool_data: {pool_data}")

    yield pool_data

    try:
        ops_page.goto_service("存储设施")
        ops_page.search(pool_name)
        ops_page.delete_storage_pool(pool_name)
    except Exception as e:
        logger.warning(f"清理存储池 {pool_name}时出错: {e}")

    try:
        ops_page.search_disk("所在物理机", node)
        ops_page.disable_disk(_disk_name)
    except Exception as e:
        logger.warning(f"禁用裸磁盘{_disk_name}时出错: {e}")


# ---- BMS 裸金属 fixture（只读，无清理） ----

@pytest.fixture()
def bms_instance(bms_page):
    """返回裸金属实例创建器（工厂函数），封装步骤13-14。

    使用方式：
        instance_name = bms_instance(name="bms-0430")

    前置条件：调用前需确保交换机组、网络、代理、PXE、发现、注册已完成。
    """
    def _create(
        name="bms-0430",
        image_name="bms",
        system_disk="sdi",
        password="admin1234@sugon",
        security_group="default",
        server_name="N/A 2U Rack Server",
        network_name="guanyy-vpc",
    ):
        with allure_step_log("步骤13: 创建裸金属实例"):
            bms_page.bms_instance_create(
                name=name,
                image_name=image_name,
                system_disk=system_disk,
                password=password,
                security_group=security_group,
                server_name=server_name,
                network_name=network_name,
            )
            bms_page.page.wait_for_timeout(3000)
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(name)
            assert bms_page.get_row_data(name) is not None

        with allure_step_log("步骤14: 验证实例列表并等待运行中"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(name)
            rd = bms_page.get_row_data(name)
            assert rd is not None
            for waited in range(0, 1800, 30):
                status = rd.get("状态", "")
                if "运行中" in status:
                    logger.info(f"实例状态已为'运行中'，等待了{waited}s")
                    break
                logger.info(f"实例当前状态'{status}'，继续等待... ({waited}s/1800s)")
                time.sleep(30)
                bms_page._goto_submenu_safe("裸金属实例")
                bms_page.search(name)
                rd = bms_page.get_row_data(name)
            else:
                pytest.skip("实例未在30分钟内变为运行中")

        return name

    return _create


# ---- 安全组 fixture（复用 network conftest 的底层能力） ----

from sugon_web.testcase.network.conftest import (
    _create_security_groups,
    _cleanup_security_groups,
)


@pytest.fixture(scope="function")
def sg(browser_context, config, request):
    """创建并返回安全组名称，测试结束后自动清理。

    本 fixture 复用 network 模块的底层安全组创建/清理逻辑，
    使 compute 模块的测试用例也能直接使用安全组资源。

    Args:
        browser_context: Playwright 浏览器上下文。
        config: 测试配置对象。
        request: pytest 请求对象，用于获取参数化配置。

    request.param:
        int: 需要创建的安全组数量，默认为 1。

    Yields:
        str | list[str]: 创建单个安全组时返回名称字符串，批量创建时返回名称列表。
    """
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)

    count = getattr(request, "param", 1)
    if count <= 0:
        yield []
        page.close()
        return

    names = _create_security_groups(vpc_page, count)

    yield names[0] if count == 1 else names

    try:
        _cleanup_security_groups(vpc_page, names)
    finally:
        page.close()
