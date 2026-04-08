import time
import pytest
from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.ecs import EcsPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data


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
        ops_page.goto_service("计算设施")
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


@pytest.fixture(scope="class")
def labels(browser_context, config, request):
    """创建并返回指定数量的标签，测试结束后自动清理。"""
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ecs_page.goto_service("弹性云服务器")
    params = getattr(request, "param", {})
    count = params.get("count", 1)

    label_names = []
    prefix = params.get("prefix", "label")
    with allure_step_log("创建指定数量的标签"):
        for _ in range(count):
            name = f"{prefix}-{random_data()}"
            label_name = ecs_page.create_label(name)
            ecs_page.assert_popup_success("新建标签成功")
            label_names.append(label_name)
            logger.info(f"已创建标签: {label_name}")

    yield label_names

    with allure_step_log("清理测试标签"):
        logger.info(f"开始清理标签: {label_names}")
        try:
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("标签")
            ecs_page.batch_delete_label(label_names)
            logger.info(f"标签清理完成: {label_names}")
        except Exception as e:
            logger.warning(f"清理标签时出错: {e}")
        finally:
            page.close()


@pytest.fixture()
def affinity(ecs_page, request):
    """创建并返回指定数量的亲和组标签名。"""
    params = getattr(request, "param", {})
    count = params.get("count", 1)

    label_names = []
    prefix = params.get("prefix", "label")

    for _ in range(count):
        name = f"{prefix}_{random_data()}"
        label_name = ecs_page.create_label(name)
        ecs_page.assert_popup_success("新建标签成功")
        label_names.append(label_name)
        logger.info(f"已创建标签: {label_name}")

    yield label_names
