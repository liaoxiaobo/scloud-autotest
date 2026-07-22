import pytest
from sugon_web.common.playwright import expect
from sugon_web.pages.kms import KmsPage
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


@pytest.fixture()
def sfs_page(page):
    """初始化文件存储 SFS 页面对象并导航到服务页。"""
    from sugon_web.pages.storage.sfs import SfsPage
    sfs = SfsPage(page)
    sfs.goto_service("文件存储")
    return sfs


@pytest.fixture()
def clean_sfs_instances(sfs_page):
    """注册表模式：测试用例动态登记 SFS 实例名称，fixture 统一清理。

    Yields:
        list: 实例名称注册表，测试用例通过 append() 登记。
    """
    from sugon_web.testcase.storage._sfs_helpers import delete_sfs_instance

    registry = []
    yield registry

    with allure_step_log(f"清理: 删除 {len(registry)} 个文件存储实例"):
        for name in registry:
            try:
                delete_sfs_instance(sfs_page, name)
            except Exception as e:
                logger.warning(f"删除文件存储实例 {name} 失败: {e}")
                raise


@pytest.fixture()
def sfs_instance(sfs_page, request):
    """创建文件存储实例并自动清理。

    参数:
        request.param: dict, 可选
            - count: int, 创建数量，默认 1
            - name: str, 自定义名称前缀，默认使用 random_data()
            - protocol: str | list[str], 文件协议，默认 "nfs"；
              count>1 时可为列表，按索引依次使用
            - cluster: str, 集群名称，默认 "Autotest"
            - network: str, 专有网络名称，默认 "Autotest"
            - subnet: str, 子网名称，默认 None（自动选择第一个可用子网）
            - volume_type: str, 云硬盘类型，默认 None（自动选择第一个可用类型）
            - volume_size: int, 云硬盘大小（GiB），默认 10
            - cpu_cores: int, CPU 核数，默认 8
            - ram_gb: int, 内存 GiB，默认 8

    Yields:
        dict 或 list[dict]:
            count=1 返回单字典，包含 name 及所有实际使用的参数（传入的+默认的）。
            count>1 返回列表，每个元素均为完整参数字典。
    """
    from sugon_web.testcase.storage._sfs_helpers import (
        create_sfs_instance,
        delete_sfs_instance,
        delete_sfs_instances,
    )

    params = getattr(request, 'param', {}) or {}
    count = params.get('count', 1)
    base_name = params.get('name') or f"sfs-{random_data()}"
    protocol = params.get('protocol', 'nfs')

    # 过滤 fixture 控制参数，只保留业务参数传给 helper
    create_params = {k: v for k, v in params.items() if k not in ('count', 'name', 'protocol')}

    instances = []
    with allure_step_log(f"创建文件存储实例 (count={count})"):
        for i in range(count):
            name = f"{base_name}-{i}" if count > 1 else base_name
            proto = protocol[i] if isinstance(protocol, list) else protocol
            item = create_sfs_instance(
                sfs_page,
                name=name,
                protocol=proto,
                **create_params,
            )
            instances.append(item)

    result = instances[0] if count == 1 else instances
    yield result

    # 清理阶段
    names = [item["name"] for item in instances]
    with allure_step_log(f"清理: 删除 {len(names)} 个文件存储实例"):
        try:
            if len(names) == 1:
                delete_sfs_instance(sfs_page, names[0])
            else:
                delete_sfs_instances(sfs_page, names)
        except Exception as e:
            logger.warning(f"清理文件存储实例失败: {e}")
            raise


@pytest.fixture()
def evss_policy(evs_page):
    """创建并返回一个快照策略，测试结束后自动清理。"""
    policy_name = random_data()

    with allure_step_log("创建快照策略"):
        evs_page.evss_policy_create(
            name=policy_name,
            enabled=True,
            hours=[0, 1, 2],
            retention_type="按数量",
            retention_value=1,
            cycle_days=1,
        )
        evs_page.assert_popup_success("添加策略成功")

    yield policy_name

    with allure_step_log("清理测试数据"):
        evs_page.evss_policy_delete(policy_name)
        evs_page.assert_deleted(policy_name)


@pytest.fixture()
def evss(evs_page, volume):
    """创建并返回一个快照，测试结束后自动清理。"""
    snapshot_name = random_data()
    with allure_step_log("创建快照"):
        evs_page.evss_create(volume["name"], snapshot_name, "测试快照")
        evs_page.assert_popup_success("创建快照成功")
        evs_page.goto_submenu("快照")
        evs_page.assert_status(snapshot_name, status="可用")

    yield {"name": snapshot_name, "volume_name": volume["name"]}

    with allure_step_log("清理测试数据"):
        evs_page.goto_submenu("快照")
        evs_page.evss_delete(snapshot_name)
        evs_page.assert_deleted(snapshot_name)


@pytest.fixture
def kms_page(page):
    """创建密钥管理页面对象并导航到密钥管理页面。"""
    kms = KmsPage(page)
    kms.goto_service("可信密码模块")

    try:
        text_locator = kms.get_by_text("您已成功授权")
        expect(text_locator).to_be_visible()
    except Exception:
        pytest.skip("当前环境可信密码模块未授权，跳过测试")

    return kms


@pytest.fixture
def kms_key(kms_page, request):
    """创建测试密钥并在测试后清理。"""
    engine = getattr(request, "param", "HCT")
    key_name = random_data()

    kms_page.kms_create(
        name=key_name,
        engine=engine,
        key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
        desc="测试密钥",
    )
    kms_page.assert_popup_success("执行成功")
    key_data = kms_page.get_row_data(key_name)

    yield key_data

    kms_page.goto_service("可信密码模块")
    kms_page.kms_delete(key_name)
    kms_page.assert_deleted(key_name)
