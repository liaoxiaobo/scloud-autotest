import allure
import pytest
from playwright.sync_api import expect
from sugon_web.pages.login import LoginPage
from sugon_web.pages.evs import EvsPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.ops import OpsPage
from sugon_web.pages.mysql import MySQLPage
from sugon_web.pages.doris import DorisPage
from sugon_web.pages.kms import KmsPage
from sugon_web.utils.logger import logger
from sugon_web.utils.util import random_data, random_string


@pytest.fixture(scope="function", autouse=True)
def close_dialog_before_test(page):
    """用例执行前关闭可能存在的对话框，避免页面元素定位被遮挡或干扰"""

    try:
        # 直接检查并关闭对话框
        close_button = page.get_by_role("button", name="Close")
        if close_button.is_visible():
            logger.info("发现未关闭的对话框，正在关闭...")
            close_button.click()
    except:
        pass  # 忽略对话框不存在的情况

    yield

@pytest.fixture(scope="module")
def login_page(page, env):
    """初始化登录页对象"""
    page = LoginPage(page, env)
    page.logout()   # 登录测试用例需要先退出登录状态
    return page


@pytest.fixture(scope="module")
def evs_page(page, env):
    """初始化云硬盘页对象"""
    page = EvsPage(page, env)
    page.goto_service('云硬盘')
    return page


@pytest.fixture()
def volume(evs_page, request):
    """初始化云硬盘数据

    Args:
        request: pytest fixture，用于获取参数
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

    name = random_data()
    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试
    evs_page.evs_create(
        name=name,
        empty=empty,
        image_name=image_name,
        size=size,
        desc=desc,
        shared=shared
    )
    evs_page.assert_popup_success()
    evs_page.assert_status(name, status="可用")
    volume = {"name": name}

    yield volume

    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试
    evs_page.evs_remove(volume["name"])
    evs_page.evs_delete(volume["name"])
    evs_page.assert_deleted(volume["name"])


@pytest.fixture(scope="module")
def ecs_page(page, env):
    """初始化弹性云服务器页对象"""
    page = EcsPage(page, env)
    page.goto_service('弹性云服务器')
    return page

@pytest.fixture(scope="class")
def ops_page(page, env):
    """初始化运维管理页对象"""
    page = OpsPage(page, env)
    page.goto_service('网络设施')
    return page


@pytest.fixture(scope="class")
def mysql_page(page, env):
    """初始化MySQL实例管理页面"""
    mysql_page = MySQLPage(page, env)
    mysql_page.goto_service('AnhanDB(for MySQL)')
    return mysql_page


@pytest.fixture(scope="class")
def doris_page(page, env):
    """初始化Doris实例管理页面"""
    doris_page = DorisPage(page, env)
    doris_page.goto_service('数据仓库 Doris')
    return doris_page


@pytest.fixture(scope="class")
def doris(doris_page):
    """创建一个供整个测试类使用的Doris实例对象"""
    name = f"doris-{random_data()}"
    admin_password = "admin1234@sugon"  # Doris默认密码
    data = {"name": name, "admin_password": admin_password}
    logger.info(f"为测试类创建共享Doris实例: {name}")

    with allure.step(f"前置操作：创建共享实例 {name}"):
        doris_page.create_instance(name, password=admin_password)
        doris_page.assert_popup_success("Doris创建任务提交成功")
        doris_page.assert_status(name, status="就绪", timeout=1800)

    yield data

    with allure.step(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享Doris实例: {name}")
        doris_page.delete_instance(data["name"])


@pytest.fixture(scope="class")
def mysql(mysql_page):
    """创建一个供整个测试类使用的MySQL实例对象"""
    name = random_data()
    type = "集群"
    db_name = f"autodb-{random_string(k=5)}"
    user_name = f"user_{random_string(k=5)}"
    user_password = f"sugon1234@{random_string(k=5)}"
    privileges = "读写"
    data = {"name": name, "db_name": db_name, "user_name": user_name, "user_password": user_password}
    logger.info(f"为测试类创建共享MySQL实例: {name}")

    with allure.step(f"前置操作：创建共享实例 {name}"):
        mysql_page.create_instance(name, type)
        mysql_page.assert_popup_success("创建MySQL资源成功")
        mysql_page.assert_status(name, status="运行中", timeout=1200)

    with allure.step(f"前置操作：创建新数据库 {db_name}"):
        mysql_page.create_database(name, db_name)
        mysql_page.assert_popup_success("创建数据库成功,如果数据未更新,请刷新页面")
        mysql_page.assert_list_contain(db_name)

    with allure.step(f"前置操作：创建新用户 {db_name}"):
        mysql_page.create_user(name, user_name, user_password, db_name, privileges)
        mysql_page.assert_popup_success("创建用户成功",10)

    yield data

    with allure.step(f"后置操作：删除共享实例 {name}"):
        logger.info(f"清理共享MySQL实例: {name}")
        # 在删除前，确保页面在实例列表页，防止在详情页删除失败
        mysql_page.delete_instance(data["name"])


@pytest.fixture(scope="class")
def vm(ecs_page, request):
    """初始化弹性云服务器数据

    支持参数化配置，可通过pytest.mark.parametrize传入参数：
    - count: 创建虚机数量，默认为1
    - root_gb: 系统盘大小，默认为100GB
    - bind_mfip: 是否绑定mfip，默认为False


    返回值:
    - 如果创建一台虚机：返回字典类型的虚机信息
    - 如果创建多台虚机：返回字典列表，每个字典包含一台虚机的信息
    """
    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    count = params.get('count', 1)
    root_gb = params.get('root_gb', 100)
    bind_mfip = params.get('bind_mfip', True)

    name = random_data()

    # 创建指定数量的虚机
    ecs_page.goto_service('弹性云服务器') # 临时方案：保证在同一服务页面,满足云盘挂载测试
    ecs_page.ecs_create(name, count=count, sys_size=root_gb)
    ecs_page.assert_popup_success("创建实例命令下发成功")

    # 等待虚机创建完成并收集信息
    metadata_list = []

    # 根据创建数量处理虚机名称
    if count == 1:
        vm_names = [name]
    else:
        # 多台虚机时，名称会自动添加序号后缀
        vm_names = [f"{name}-{i}" for i in range(0, count)]

    # 等待虚机创建完成
    ecs_page.assert_status(vm_names)

    # 收集每台虚机的信息
    for vm_name in vm_names:
        row_data = ecs_page.get_row_data(vm_name)
        vm_metadata = {
            "name": vm_name,
            "id": row_data["名称/ID"],
            "ip": row_data["IP地址"].split(":")[1].strip(),
            'host': row_data["物理机"],
            "flavor": row_data["规格"],
            "image": row_data["镜像名称"],
            "project": row_data["项目名称"]
        }
        metadata_list.append(vm_metadata)

    # 如果需要绑定mfip
    if bind_mfip:
        for vm_data in metadata_list:
            ecs_page.goto_service("网络设施")
            ecs_page.mfip_create(vm_data["project"], "Autotest", vm_data["ip"])
            ecs_page.assert_popup_success()
            ecs_page.mfip_search(vm_data["ip"])
            vm_data["mfip"] = ecs_page.get_column_data("Mfip 地址")[0]  # 更新metadata
        ecs_page.goto_service("弹性云服务器") # 跳转回弹性云服务器页面

    # 根据虚机数量返回不同类型的数据
    if count == 1:
        yield metadata_list[0]  # 单台虚机返回字典
    else:
        yield metadata_list  # 多台虚机返回列表

    # 清理虚机
    ecs_page.goto_service("弹性云服务器")  # 保证在同一服务页面
    ecs_page.ecs_remove(vm_names)
    ecs_page.ecs_delete(vm_names)
    ecs_page.assert_deleted(vm_names)

@pytest.fixture()
def evss_policy(evs_page):
    """创建并返回一个快照策略，测试结束后自动清理"""
    policy_name = random_data()

    # 创建快照策略
    evs_page.evss_policy_create(
        name=policy_name,
        enabled=True,
        hours=[0, 1, 2],
        retention_type="按数量",
        retention_value=1,
        cycle_days=1
    )

    # 验证创建成功
    evs_page.assert_popup_success("添加策略成功")

    # 返回策略名称供测试使用
    yield policy_name

    # 测试结束后清理
    with allure.step("清理测试数据"):
        evs_page.evss_policy_delete(policy_name)    # TODO: 删除失败，云盘未解绑
        evs_page.assert_deleted(policy_name)


@pytest.fixture()
def evss(evs_page, volume):
    """创建并返回一个快照，测试结束后自动清理"""
    snapshot_name = random_data()

    # 创建快照
    evs_page.evss_create(volume["name"], snapshot_name, "测试快照")
    evs_page.assert_popup_success("创建快照成功")
    evs_page.goto_submenu("快照")
    evs_page.assert_status(snapshot_name, status="可用")

    # 返回快照名称供测试使用
    yield {"name": snapshot_name, "volume_name": volume["name"]}

    # 测试结束后清理
    with allure.step("清理测试数据"):
        evs_page.goto_submenu("快照")
        evs_page.evss_delete(snapshot_name)
        evs_page.assert_deleted(snapshot_name)


@pytest.fixture
def kms_page(page, env):
    """创建密钥管理页面对象并导航到密钥管理页面"""
    kms = KmsPage(page, env)
    kms.goto_service("可信密码模块")

    # 检查是否已授权
    try:
        text_locator = kms.get_by_text("您已成功授权")
        expect(text_locator).to_be_visible()
        # kms.page.wait_for_selector('text="您已成功授权"', state='visible', timeout=5000)
    except:
        pytest.skip("当前环境可信密码模块未授权，跳过测试")

    return kms


@pytest.fixture
def kms_key(kms_page, request):
    """创建密钥管理页面对象并创建一个测试密钥

    Args:
        kms_page: 密钥管理页面对象
        request: pytest的request对象，用于获取参数

    Returns:
        str: 创建的密钥名称
    """
    # 获取加密引擎参数，默认为"HCT"
    engine = getattr(request, 'param', 'HCT')

    # 生成随机密钥名称
    key_name = random_data()

    # 创建密钥
    kms_page.kms_create(
        name=key_name,
        engine=engine,
        key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
        desc="测试密钥"
    )

    # 验证创建成功
    kms_page.assert_popup_success("执行成功")

    # 获取密钥数据行的字典对象
    key_data = kms_page.get_row_data(key_name)

    yield key_data

    # 清理测试数据
    kms_page.goto_service("可信密码模块")
    kms_page.kms_delete(key_name)
    kms_page.assert_deleted(key_name)


@pytest.fixture()
def ecss(ecs_page, vm):
    """创建并返回一个ECS快照名称，测试结束后自动清理

    Args:
        ecs_page: ECS页面对象
        vm: 虚拟机fixture

    Returns:
        str: 快照名称
    """
    vm_name = vm.get("name")
    snapshot_name = f"snapshot_{vm_name}"

    # 创建系统盘快照
    ecs_page.ecss_create(
        name=vm_name,
        snapshot_name=snapshot_name,
    )
    ecs_page.assert_popup_success("创建实例快照成功")
    ecs_page.assert_status(vm_name, status="当前无任务")

    # 切换到快照页面并验证
    ecs_page.goto_submenu("快照")
    ecs_page.assert_status(snapshot_name, status="可用", refresh=True)

    # 返回快照名称
    yield {"name": snapshot_name, "vm_name": vm_name}

    # 测试结束后清理快照
    ecs_page.ecss_delete(snapshot_name)
    ecs_page.assert_deleted(snapshot_name, refresh=True)

@pytest.fixture()
def ecss_policy(ecs_page):
    """创建并返回一个云服务器快照策略，测试结束后自动清理"""
    policy_name = random_data()

    # 创建快照策略
    ecs_page.ecss_policy_create(
        name=policy_name,
        hours=[0, 1, 2],
        enabled=True,
        cycle_days=1,
        retention_type="按数量",
        retention_value=1
    )

    # 验证创建成功
    ecs_page.assert_popup_success("执行成功")

    # 返回策略名称供测试使用
    yield {"name": policy_name}

    # 测试结束后清理
    with allure.step("清理测试数据"):
        ecs_page.ecss_policy_delete(policy_name)
        ecs_page.assert_deleted(policy_name)
