import json
import os
import ipaddress
import shlex
import time
import pytest
from sugon_web.pages.network import VpcPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page
from sugon_web.config.config import Config


BMS_IMAGE_DEFAULTS = {
    "image_name": "centos76-bms-0511-base",
    "image_file": "/home/scloudadmin/centos76-bms-0511.raw",
    "image_url": "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos76-bms-0511.raw",
    "image_backend": "bms",
    "image_min_disk": 50,
}


def _bms_config_value(bms_env, key):
    value = bms_env.get(key)
    if value not in (None, ""):
        return value
    return BMS_IMAGE_DEFAULTS[key]


def ensure_bms_image(ssh_host, bms_env=None, image_name=None):
    """Ensure the BMS bare-metal image exists before instance operations."""
    bms_env = bms_env or {}
    image_name = image_name or _bms_config_value(bms_env, "image_name")
    image_file = _bms_config_value(bms_env, "image_file")
    image_url = _bms_config_value(bms_env, "image_url")
    image_backend = _bms_config_value(bms_env, "image_backend")
    image_min_disk = _bms_config_value(bms_env, "image_min_disk")
    image_name_arg = shlex.quote(image_name)
    image_check_cmd = (
        "source /root/admin-openrc.sh && scli image list | "
        f"awk -F'|' -v name={image_name_arg} "
        """'{gsub(/^[ \t]+|[ \t]+$/, "", $3); gsub(/^[ \t]+|[ \t]+$/, "", $5); """
        """if ($3 == name && $5 == "active") found=1} END {exit found ? 0 : 1}'"""
    )

    with allure_step_log(f"前置: 检查BMS镜像 {image_name} 状态为active"):
        result = ssh_host.run(image_check_cmd, return_rc=True)
        if result["rc"] == 0:
            logger.info(f"BMS镜像 '{image_name}' 已存在且状态为active，跳过创建")
            return image_name

    with allure_step_log("前置: 准备BMS镜像文件"):
        result = ssh_host.run(f"test -f {image_file} && echo 'exists' || echo 'missing'", return_rc=True)
        assert result["rc"] == 0, f"检查BMS镜像文件失败: {result.get('stderr', '')}"
        if "missing" in result["stdout"]:
            result = ssh_host.run(f"curl -L {image_url} -o {image_file}", return_rc=True, timeout=300)
            assert result["rc"] == 0, f"BMS镜像下载失败: {result.get('stderr', '')}"
            logger.info(f"BMS镜像文件已下载: {image_file}")
        else:
            logger.info(f"BMS镜像文件已存在: {image_file}")

    with allure_step_log(f"前置: 创建BMS镜像 {image_name}"):
        cmd = (
            f"source /root/admin-openrc.sh && "
            f"scli image create --visibility public --disk-format raw --container-format bare "
            f"--min-disk {image_min_disk} --property hypervisor_type=baremetal --property purpose=ironic "
            f"--property os_type=linux --property hw_qemu_guest_agent=yes --backend {image_backend} "
            f"--file {image_file} --name {image_name}"
        )
        result = ssh_host.run(cmd, return_rc=True, timeout=1800)
        assert result["rc"] == 0, f"BMS镜像创建失败: {result.get('stderr', '')}"
        logger.info(f"BMS镜像 '{image_name}' 创建成功")

    with allure_step_log(f"前置: 验证BMS镜像 {image_name} 状态为active"):
        result = ssh_host.run(image_check_cmd, return_rc=True)
        assert result["rc"] == 0, f"BMS镜像创建后未达到active状态: {result.get('stderr', '')}"

    return image_name


@pytest.fixture(scope="function")
def bms_eip_pool(page, request):
    """Allocate a small BMS-only EIP pool and return the largest IP.

    Teardown releases each EIP independently. If one IP is already bound or
    cannot be released, log a warning and continue with the remaining EIPs.
    """
    params = getattr(request, "param", {}) or {}
    count = params.get("count", 5)
    pool = params.get("pool", Config.get("network") or "public_net(基础版)")
    method = params.get("method", "快速选择")

    vpc_page = VpcPage(page)
    created_ips = []

    with allure_step_log(f"Setup: allocate {count} BMS EIPs"):
        vpc_page.goto_service("虚拟私有云")
        created_ips = vpc_page.eip_allocate(pool=pool, count=count, method=method)
        vpc_page.assert_popup_success("执行成功")
        assert created_ips, "BMS EIP pool allocation returned no IPs"
        target_ip = max(created_ips, key=ipaddress.ip_address)
        logger.info(f"BMS allocated EIPs: {created_ips}, selected max IP: {target_ip}")

    try:
        yield {
            "ips": created_ips,
            "target_ip": target_ip,
            "pool": pool,
        }
    finally:
        with allure_step_log(f"Teardown: release BMS EIPs {created_ips}"):
            for current_ip in created_ips:
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.switch_eip_pool(pool)
                    vpc_page.search(current_ip)
                    if current_ip not in vpc_page.get_eip_list():
                        logger.info(f"BMS preallocated EIP {current_ip} no longer exists; skip release")
                        continue

                    try:
                        row_data = vpc_page.get_row_data(current_ip) or {}
                        logger.info(f"BMS preallocated EIP {current_ip} row before cleanup: {row_data}")
                    except Exception as row_err:
                        logger.warning(f"Failed to read BMS preallocated EIP {current_ip} row; still trying release: {row_err}")

                    vpc_page.eip_release(current_ip)
                    vpc_page.assert_deleted(current_ip)
                    logger.info(f"BMS preallocated EIP {current_ip} released")
                except Exception as e:
                    logger.warning(f"Failed to release BMS preallocated EIP {current_ip}; it may be bound elsewhere, continuing: {e}")
                finally:
                    try:
                        vpc_page.close_dialog_if_exists()
                    except Exception:
                        pass
                    try:
                        vpc_page.btn_reset.click()
                    except Exception:
                        pass


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
        ops_page.goto_service("基础设施")
        ops_page.goto_submenu("存储池")
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

@pytest.fixture(scope="session")
def bms_env(pytestconfig, config):
    """返回 BMS 回归测试的基线环境配置，CLI 参数可覆盖配置文件，ENV_DISPATCH 中的 bms 配置次之。"""
    bms_config = config.get("bms", {}) or {}

    # 读取 Jenkins 通过 SUGON_BMS_OVERRIDE 传入的 BMS 覆盖配置
    bms_override_json = os.environ.get("SUGON_BMS_OVERRIDE", "{}")
    try:
        bms_override = json.loads(bms_override_json)
    except json.JSONDecodeError as e:
        logger.error(f"SUGON_BMS_OVERRIDE 解析失败: {e}, 原始内容: {bms_override_json}")
        bms_override = {}

    if bms_override:
        bms_config = bms_config.copy()
        bms_config.update(bms_override)

    def _value(option_name, config_key):
        option_value = pytestconfig.getoption(option_name)
        if option_value:
            return option_value
        return bms_config.get(config_key)

    return {
        "instance_name": _value("--bms-instance-name", "instance_name"),
        "bmc_ip": _value("--bms-bmc-ip", "bmc_ip"),
        "preferred_node": _value("--bms-preferred-node", "preferred_node"),
        "network_name": _value("--bms-network-name", "network_name"),
        "password": _value("--bms-password", "password"),
        "image_name": bms_config.get("image_name") or BMS_IMAGE_DEFAULTS["image_name"],
        "image_file": bms_config.get("image_file") or BMS_IMAGE_DEFAULTS["image_file"],
        "image_url": bms_config.get("image_url") or BMS_IMAGE_DEFAULTS["image_url"],
        "image_backend": bms_config.get("image_backend") or BMS_IMAGE_DEFAULTS["image_backend"],
        "image_min_disk": bms_config.get("image_min_disk") or BMS_IMAGE_DEFAULTS["image_min_disk"],
    }


@pytest.fixture(scope="session")
def bms_instance_name(bms_env):
    """返回 BMS 操作用例复用的实例名称。"""
    return bms_env["instance_name"]


@pytest.fixture(autouse=True)
def bms_regression_requires_instance(request):
    """BMS回归用例执行前确认实例已存在，避免创建失败后的级联失败。"""
    if not request.node.get_closest_marker("bms_regression"):
        return

    bms_page = request.getfixturevalue("bms_page")
    bms_env = request.getfixturevalue("bms_env")
    instance_name = bms_env["instance_name"]
    with allure_step_log("setup: 检查BMS回归实例前置"):
        bms_page._goto_submenu_safe("裸金属实例")
        bms_page.bms_search(instance_name)
        row_data = bms_page.get_row_data(instance_name)
        if not row_data:
            pytest.skip(f"BMS实例 '{instance_name}' 不存在，跳过依赖该实例的回归用例")
        status = str(row_data.get("状态", ""))
        if any(bad in status for bad in ["删除", "错误"]):
            pytest.skip(f"BMS实例 '{instance_name}' 状态异常，跳过回归用例: {status}")


@pytest.fixture()
def bms_image(ssh_host, bms_env):
    """确保BMS镜像存在，并返回镜像名称。"""
    return ensure_bms_image(ssh_host, bms_env)


@pytest.fixture()
def bms_instance(bms_page, bms_env, ssh_host):
    """返回裸金属实例创建器（工厂函数），封装步骤13-14。

    使用方式：
        instance_name = bms_instance(name=bms_env["instance_name"])

    前置条件：调用前需确保交换机组、网络、代理、PXE、发现、注册已完成。
    """
    def _create(
        name=None,
        image_name=None,
        system_disk="MR9361-16iGiB",
        password=None,
        security_group="default",
        server_name="N/A 2U Rack Server",
        network_name="guanyy-vpc",
        subnet_name="",
    ):
        name = name or bms_env["instance_name"]
        image_name = image_name or bms_env["image_name"]
        password = password or bms_env["password"]
        ensure_bms_image(ssh_host, bms_env, image_name=image_name)
        with allure_step_log("步骤13: 创建裸金属实例"):
            try:
                bms_page.bms_instance_create(
                    name=name,
                    image_name=image_name,
                    system_disk=system_disk,
                    password=password,
                    security_group=security_group,
                    server_name=server_name,
                    network_name=network_name,
                    subnet_name=subnet_name,
                    bmc_ip=bms_env["bmc_ip"],
                )
            except RuntimeError as e:
                pytest.skip(str(e))
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
