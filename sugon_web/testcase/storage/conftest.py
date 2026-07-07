import pytest
from sugon_web.common.playwright import expect
from sugon_web.pages.kms import KmsPage
from sugon_web.pages.storage.obs import ObsPage
from sugon_web.pages.storage.oss import OssPage
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.conftest import _create_logged_in_page


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
    object_limit = params.get('object_limit', None)

    # 过滤控制参数，只保留业务参数传给 helper
    create_params = {k: v for k, v in params.items() if k not in ('count', 'name', 'capacity', 'object_limit')}

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
                # 复用旧桶时强制对齐配额，避免旧桶容量/对象数限制与本次测试要求不符
                if capacity is not None or object_limit is not None:
                    obs_page.obs_bucket_modify_quota(
                        old_name, capacity=capacity, object_limit=object_limit
                    )
                bucket_items.append({"name": old_name, "capacity": capacity, "object_limit": object_limit, "reused": True})
            except Exception as e:
                logger.warning(f"复用桶 {old_name} 失败: {e}")

        # 复用不足时创建新桶
        for i in range(count - len(bucket_items)):
            name = f"{base_name}-{i}" if count > 1 else base_name
            item = create_bucket(obs_page, name=name, capacity=capacity, object_limit=object_limit, **create_params)
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
            - count: int, 创建数量，默认 1
            - name: str, 自定义名称，默认使用 random_data()
            - region: str, 区域，默认 "RegionOne"
            - az_strategy: str, 数据冗余存储策略，默认 "MULTI_AZ"
            - storage_class: str, 默认存储类别，默认 "标准存储"
            - bucket_strategy: str, 桶策略，默认 "私有"
            - is_encryption: bool, 是否开启默认加密，默认 True
            - data_read: bool, 归档数据直读，默认 False
            - tags: list[dict], 标签列表，默认 None

    Yields:
        dict 或 list[dict]:
            count=1 返回单字典，包含 name 及所有实际使用的参数。
            count>1 返回列表，每个元素均为完整参数字典。
    """
    from sugon_web.testcase.storage._oss_helpers import (
        create_oss_bucket,
        delete_oss_bucket,
    )

    params = getattr(request, 'param', {}) or {}
    count = params.get('count', 1)
    base_name = params.get('name') or f"oss-{random_data()}"

    # 过滤 fixture 控制参数，只保留业务参数传给 helper
    create_params = {k: v for k, v in params.items() if k not in ('count', 'name')}

    bucket_items = []
    with allure_step_log(f"创建OSS桶 (count={count})"):
        for i in range(count):
            name = f"{base_name}-{i}" if count > 1 else base_name
            item = create_oss_bucket(
                oss_page,
                name=name,
                **create_params,
            )
            bucket_items.append(item)

    result = bucket_items[0] if count == 1 else bucket_items
    yield result

    # 清理阶段
    with allure_step_log(f"清理: 删除 {len(bucket_items)} 个OSS桶"):
        for item in bucket_items:
            try:
                delete_oss_bucket(oss_page, item["name"])
            except Exception as e:
                logger.warning(f"删除OSS桶 {item['name']} 失败: {e}")
                raise


@pytest.fixture(scope="class")
def oss_bucket_with_policy(browser_context, config, request):
    """在 class 范围内创建一个OSS桶并预置一条公共读写桶策略。

    同一测试类内复用该桶和策略，场景1编辑后场景2可继续复用。
    """
    from sugon_web.testcase.storage._oss_helpers import (
        create_oss_bucket,
        delete_oss_bucket,
    )

    page = _create_logged_in_page(browser_context, config)
    oss_page = OssPage(page)
    bucket_name = f"oss-{random_data()}"
    policy_name = random_data()

    try:
        with allure_step_log(f"预置: 创建OSS桶 {bucket_name} 并添加策略 {policy_name}"):
            oss_page.goto_service("对象存储")
            create_oss_bucket(oss_page, name=bucket_name)
            oss_page.oss_bucket_policy_create(
                bucket_name=bucket_name,
                policy_name=policy_name,
                template_name="公共读写",
            )
        yield {"bucket_name": bucket_name, "policy_name": policy_name}
    finally:
        with allure_step_log(f"清理: 删除预置OSS桶 {bucket_name}"):
            try:
                delete_oss_bucket(oss_page, bucket_name)
            except Exception as e:
                logger.warning(f"删除预置OSS桶 {bucket_name} 失败: {e}")
            try:
                page.close()
            except Exception as e:
                logger.warning(f"关闭预置页面失败: {e}")


@pytest.fixture()
def copy_source_cleanup(oss_page):
    """复制桶源场景的复制桶及源桶对象清理 fixture。

    仅负责登记并按 OSS-复制桶源用例要求的顺序清理"复制桶"与"源桶内对象"，
    源桶本身由 `oss_bucket` fixture 的 teardown 删除。用法：测试内调用
    `register_copy_bucket(copy_name)` 登记复制桶、`register_source_object(bucket, obj)`
    登记源桶内待清理对象。

    清理顺序（teardown，先于 oss_bucket 的源桶删除执行）：
        1. 删除复制桶内对象（复制桶通常为空，无对象则跳过）
        2. 删除复制桶
        3. 删除源桶内已上传对象（如 test01），使源桶为空以便 oss_bucket 删除

    Yields:
        dict: 含 register_copy_bucket / register_source_object 两个登记函数。
    """
    from sugon_web.testcase.storage._oss_helpers import delete_oss_bucket

    copy_buckets = []
    source_objects = []

    def register_copy_bucket(name):
        copy_buckets.append(name)

    def register_source_object(bucket_name, object_name):
        source_objects.append((bucket_name, object_name))

    yield {
        "register_copy_bucket": register_copy_bucket,
        "register_source_object": register_source_object,
    }

    # 清理阶段：先复制桶（内对象→桶），再源桶内对象
    with allure_step_log("清理: 删除复制桶与源桶内对象"):
        for copy_name in copy_buckets:
            try:
                objects = oss_page.oss_bucket_get_objects(copy_name)
                for obj in objects:
                    try:
                        oss_page.oss_bucket_delete_object(copy_name, obj)
                    except Exception as e:
                        logger.warning(f"删除复制桶 {copy_name} 内对象 {obj} 失败: {e}")
            except Exception as e:
                logger.warning(f"读取复制桶 {copy_name} 对象列表失败: {e}")
            try:
                delete_oss_bucket(oss_page, copy_name)
            except Exception as e:
                logger.warning(f"删除复制桶 {copy_name} 失败: {e}")

        for bucket_name, object_name in source_objects:
            try:
                oss_page.oss_bucket_delete_object(bucket_name, object_name)
            except Exception as e:
                logger.warning(f"删除源桶 {bucket_name} 内对象 {object_name} 失败: {e}")


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


@pytest.fixture()
def oss_object_acl_page(page):
    """初始化对象 ACL 页面对象并导航到对象存储服务页。"""
    from sugon_web.pages.storage.oss_object_acl import OssObjectAclPage

    acl_page = OssObjectAclPage(page)
    acl_page.goto_service("对象存储")
    return acl_page


@pytest.fixture(scope="class")
def oss_object_acl_env(browser_context, config, request):
    """在 class 范围内创建共享的 OSS 桶、对象及初始环境。

    三个场景（新增/编辑/删除对象 ACL）共享同一源桶 bucket01 和同一对象 test01，
    并在 teardown 中按 ACL -> 对象 -> 桶的顺序统一清理。

    Yields:
        dict: 包含 bucket_name、object_name、account_id、temp_file 等共享数据。
    """
    import os
    import tempfile

    from sugon_web.pages.storage.oss import OssPage
    from sugon_web.pages.storage.oss_object_acl import OssObjectAclPage
    from sugon_web.testcase.storage._oss_helpers import (
        create_oss_bucket,
        delete_oss_bucket,
        delete_oss_object,
        upload_oss_object,
    )

    import shutil

    page = _create_logged_in_page(browser_context, config)
    oss_page = OssPage(page)
    acl_page = OssObjectAclPage(page)

    bucket_name = f"oss-{random_data()}"
    object_name = "test01"
    account_id = "9e385563c24245439562482429342d2a"

    temp_dir = tempfile.mkdtemp(prefix="oss_acl_")
    temp_file = os.path.join(temp_dir, object_name)
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("object acl test content")

        with allure_step_log(f"预置: 创建OSS桶 {bucket_name} 并上传对象 {object_name}"):
            create_oss_bucket(oss_page, name=bucket_name)
            upload_oss_object(oss_page, bucket_name, temp_file)

        yield {
            "bucket_name": bucket_name,
            "object_name": object_name,
            "account_id": account_id,
            "temp_file": temp_file,
            "page": page,
        }
    finally:
        with allure_step_log("清理: 删除对象ACL、对象、桶"):
            try:
                acl_page.oss_object_acl_delete_all(bucket_name, object_name)
            except Exception as e:
                logger.warning(f"清理对象 ACL 失败（可能已不存在）: {e}")
            try:
                delete_oss_object(oss_page, bucket_name, object_name)
            except Exception as e:
                logger.warning(f"删除对象 {bucket_name}/{object_name} 失败: {e}")
            try:
                delete_oss_bucket(oss_page, bucket_name)
            except Exception as e:
                logger.warning(f"删除OSS桶 {bucket_name} 失败: {e}")
            try:
                page.close()
            except Exception as e:
                logger.warning(f"关闭预置页面失败: {e}")
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"删除临时目录 {temp_dir} 失败: {e}")
