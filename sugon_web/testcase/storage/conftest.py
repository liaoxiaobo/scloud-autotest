import pytest
from sugon_web.common.playwright import expect
from sugon_web.pages.kms import KmsPage
from sugon_web.pages.storage.obs import ObsPage
from sugon_web.pages.storage.oss import OssPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@pytest.fixture()
def bucket(obs_page, request):
    """创建或复用对象存储桶并自动清理。

    优先复用已有的 autotest-* 空桶以避免配额耗尽；
    不足时创建新桶。支持通过 request.param 传入参数。

    参数:
        request.param: dict, 可选
            - count: int, 创建数量，默认 1
            - name: str, 自定义名称，默认使用 random_data()
            - capacity: str, 桶容量，默认 "10"

    Yields:
        dict 或 list[dict]:
            count=1 返回单字典，包含 name 及所有实际使用的参数。
            count>1 返回列表，每个元素均为完整参数字典。
    """
    from sugon_web.testcase.storage._obs_helpers import (
        prepare_bucket_list_page,
        create_bucket,
        delete_bucket,
        empty_bucket,
    )

    params = getattr(request, 'param', {}) or {}
    count = params.get('count', 1)
    base_name = params.get('name') or random_data()
    capacity = params.get('capacity', '10')

    # 过滤控制参数，只保留业务参数传给 helper
    create_params = {k: v for k, v in params.items() if k not in ('count', 'name', 'capacity')}

    bucket_items = []

    with allure_step_log(f"创建/复用对象存储桶 (count={count})"):
        existing_buckets = prepare_bucket_list_page(obs_page)

        # 优先复用已有的 autotest-* / bucket-autotest-* 桶（先清空对象）
        autotest_buckets = [n for n in existing_buckets
                           if n.startswith("autotest-") or n.startswith("bucket-autotest-")]
        for old_name in autotest_buckets:
            if len(bucket_items) >= count:
                break
            try:
                empty_bucket(obs_page, old_name)
                bucket_items.append({"name": old_name, "capacity": capacity, "reused": True})
            except Exception as e:
                logger.warning(f"复用桶 {old_name} 失败: {e}")

        # 复用不足时创建新桶
        for i in range(count - len(bucket_items)):
            name = f"{base_name}-{i}" if count > 1 else base_name
            item = create_bucket(obs_page, name=name, capacity=capacity, **create_params)
            item["reused"] = False
            bucket_items.append(item)

    result = bucket_items[0] if count == 1 else bucket_items
    yield result

    # 清理阶段
    with allure_step_log(f"清理: 删除 {len(bucket_items)} 个对象存储桶"):
        for item in bucket_items:
            try:
                delete_bucket(obs_page, item["name"])
            except Exception as e:
                # ACL变更可能导致桶无法通过UI访问，仅记录日志不抛异常
                logger.warning(f"删除桶 {item['name']} 失败(可能因ACL限制): {e}")


@pytest.fixture(scope="function")
def oss_page(page):
    """初始化对象存储OSS页对象并导航到服务页。"""
    oss = OssPage(page)
    oss.goto_service("对象存储")
    return oss


@pytest.fixture()
def oss_bucket(oss_page, request):
    """创建OSS对象存储桶并自动清理。

    参数:
        request.param: dict, 可选
            - name: str, 自定义名称，默认使用 random_data()
            - region: str, 区域，默认 "RegionOne"
            - az_strategy: str, 数据冗余存储策略，默认 "MULTI_AZ"
            - storage_class: str, 默认存储类别，默认 "标准存储"
            - bucket_strategy: str, 桶策略，默认 "私有"
            - is_encryption: bool, 是否开启默认加密，默认 True
            - data_read: bool, 归档数据直读，默认 False
            - tags: list[dict], 标签列表，默认 None

    Yields:
        dict: 包含 name 及所有实际使用的参数。
    """
    params = getattr(request, 'param', {}) or {}
    name = params.get('name') or random_data()
    region = params.get('region', 'RegionOne')
    az_strategy = params.get('az_strategy', 'MULTI_AZ')
    storage_class = params.get('storage_class', '标准存储')
    bucket_strategy = params.get('bucket_strategy', '私有')
    is_encryption = params.get('is_encryption', True)
    data_read = params.get('data_read', False)
    tags = params.get('tags')

    with allure_step_log(f"创建OSS桶: {name}"):
        oss_page.oss_bucket_create(
            name=name,
            region=region,
            az_strategy=az_strategy,
            storage_class=storage_class,
            bucket_strategy=bucket_strategy,
            is_encryption=is_encryption,
            data_read=data_read,
            tags=tags,
        )

    bucket_info = {
        "name": name,
        "region": region,
        "az_strategy": az_strategy,
        "storage_class": storage_class,
        "bucket_strategy": bucket_strategy,
        "is_encryption": is_encryption,
        "data_read": data_read,
        "tags": tags,
    }
    yield bucket_info

    # 清理阶段
    with allure_step_log(f"清理: 删除OSS桶 {name}"):
        try:
            oss_page.oss_bucket_delete(name)
            oss_page.assert_deleted(name)
        except Exception as e:
            logger.warning(f"删除OSS桶 {name} 失败: {e}")


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
