import time

import allure
import pytest
from playwright.sync_api import expect
from sugon_web.pages.login import LoginPage
from sugon_web.pages.evs import EvsPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.network import VpcPage
from sugon_web.pages.ops import OpsPage
from sugon_web.pages.kms import KmsPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data


@pytest.fixture(scope="function", autouse=True)
def close_dialog_before_test(page):
    """用例执行前关闭可能存在的对话框，避免页面元素定位被遮挡或干扰"""

    try:
        # 直接检查并关闭对话框
        close_buttons = [
            page.get_by_role("button", name="Close"),
            page.get_by_text("删除提示").locator("xpath=./i"),
            page.get_by_text("关闭取消").get_by_text("关闭")
        ]
        for close_button in close_buttons:
            if close_button.is_visible():
                logger.info("发现未关闭的对话框，正在关闭...")
                close_button.click()
    except:
        pass  # 忽略对话框不存在的情况

    yield

@pytest.fixture(scope="class")
def login_page(page):
    """初始化登录页对象"""
    login_page = LoginPage(page)
    login_page.logout()   # 登录测试用例需要先退出登录状态
    return login_page


@pytest.fixture(scope="class")
def evs_page(page):
    """初始化云硬盘页对象"""
    evs_page = EvsPage(page)
    evs_page.goto_service('云硬盘')
    return evs_page


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
        host = resource.get('host')
        logger.info(f"检测到存储类型为{evs_page.stor}，从虚机 {resource['name']} 获取 host: {host}")

    name = random_data()
    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试

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
        volume = {"name": name}

    yield volume

    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试
    evs_page.evs_remove(volume["name"])
    evs_page.evs_delete(volume["name"])
    evs_page.assert_deleted(volume["name"])


@pytest.fixture(scope="class")
def ecs_page(page):
    """初始化弹性云服务器页对象"""
    ecs_page = EcsPage(page)
    ecs_page.goto_service('弹性云服务器')
    return ecs_page

@pytest.fixture(scope="class")
def ops_page(page):
    """初始化运维管理页对象"""
    ops_page = OpsPage(page)
    ops_page.goto_service('网络设施')
    return ops_page

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
    root_gb = params.get('root_gb', 25)
    bind_mfip = params.get('bind_mfip', True)

    name = random_data()
    with allure_step_log("创建指定数量的虚机"):
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
                "id": row_data["名称/ID"].split(":")[1].strip(),
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
                # vm_data["mfip"] = ecs_page.get_column_data("Mfip 地址")[0]  # 更新metadata
                vm_data["mfip"] = ecs_page.get_row_data(vm_data["ip"]).get("Mfip 地址")
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
    with allure_step_log("创建快照策略"):
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
    with allure_step_log("清理测试数据"):
        evs_page.evss_policy_delete(policy_name)    # TODO: 删除失败，云盘未解绑
        evs_page.assert_deleted(policy_name)


@pytest.fixture()
def evss(evs_page, volume):
    """创建并返回一个快照，测试结束后自动清理"""
    snapshot_name = random_data()
    with allure_step_log("创建快照"):
        # 创建快照
        evs_page.evss_create(volume["name"], snapshot_name, "测试快照")
        evs_page.assert_popup_success("创建快照成功")
        evs_page.goto_submenu("快照")
        evs_page.assert_status(snapshot_name, status="可用")

    # 返回快照名称供测试使用
    yield {"name": snapshot_name, "volume_name": volume["name"]}

    # 测试结束后清理
    with allure_step_log("清理测试数据"):
        evs_page.goto_submenu("快照")
        evs_page.evss_delete(snapshot_name)
        evs_page.assert_deleted(snapshot_name)


@pytest.fixture
def kms_page(page):
    """创建密钥管理页面对象并导航到密钥管理页面"""
    kms = KmsPage(page)
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
    snapshot_name = f"{vm_name}{time.strftime('%H%M%S')}"
    with allure_step_log("setup: 创建系统盘快照"):
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

    with allure_step_log("清理测试数据"):
        # 测试结束后清理快照
        ecs_page.ecss_delete(snapshot_name)
        ecs_page.assert_deleted(snapshot_name, refresh=True)

@pytest.fixture()
def ecss_policy(ecs_page):
    """创建并返回一个云服务器快照策略，测试结束后自动清理"""
    policy_name = random_data()

    # 创建快照策略
    with allure_step_log("setup: 创建快照策略"):
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
    with allure_step_log("清理测试数据"):
        ecs_page.ecss_policy_delete(policy_name)
        ecs_page.assert_deleted(policy_name)
        ecs_page.assert_popup_success("删除策略成功")

@pytest.fixture()
def image(ssh_host, ecs_page, request):
    """
    动态创建镜像的fixture，支持从测试用例层传递参数

    测试用例可以通过以下方式使用：
    1. 直接使用：默认参数创建镜像
    2. 传递参数：使用pytest.mark.parametrize或indirect参数

    Args:
        ssh_host: SSH连接fixture
        ecs_page: ECS页面fixture
        request: pytest的request对象，用于获取测试用例传递的参数

    Returns:
        str: 创建的镜像名称

    Yields:
        str: 镜像名称，测试用例执行后自动清理
    """
    params = getattr(request, 'param', {})
    name = params.get('name', random_data())
    backend = params.get('backend', ecs_page.storage_pool)
    if backend.startswith("local"):
        backend = "local"
    image_name = params.get('image', "AnolisOS-8.9-x86_64-minimal.iso")
    ssh_host.glance_image_create(name, image=image_name, backend=backend)
    yield {"name": name}
    ssh_host.glance_image_delete(name)


@pytest.fixture
def pool(ops_page, vm, request):
    """
    动态创建存储池的fixture，支持从测试用例层传递参数
    测试用例可以通过以下方式使用：
    1. 直接使用：默认参数创建存储池
    2. 传递参数：使用pytest.mark.parametrize或indirect参数
    Args:
        ops_page: Ops页面对象
        request: pytest的request对象，用于获取测试用例传递的参数
    Returns:
        dict: 包含存储池名称的字典
    Yields:
        dict: 包含存储池名称的字典，测试用例执行后自动清理
    """
    params = getattr(request, 'param', {})

    # 从参数中获取节点名称
    node = params.get('node', vm.get("host"))

    # 生成随机名称
    pool_name = f"disk_{random_data()}"
    with allure_step_log("创建指定数量的虚机"):
        ops_page.goto_service("计算设施")
        # 启用磁盘并获取磁盘大小
        ops_page.search_disk("所在物理机", node)
        _disk_name, _disk_size = ops_page.enable_disk(node)
        # ops_page.assert_status(_disk_name, status="启用")

        # 创建存储池
        device_type = f"DISK-SSD-{_disk_size}"
        storage_type = params.get('storage_type', "本地磁盘")
        ops_page.create_storage_pool(pool_name, device_type=device_type, storage_type=storage_type)

        # 验证存储池创建成功
        # ops_page.assert_popup_success("执行成功")
        ops_page.sync_storage_pool_config()
        ops_page.assert_status(pool_name, status="已同步")

        pool_data = {"pool_name": pool_name, "disk_size": _disk_size, "disk_name": _disk_name}
        pool_data.update(vm)
        logger.info(f"pool_data: {pool_data}")

    yield pool_data

    try:
        # 检查存储池是否存在，如果存在则尝试删除
        ops_page.goto_service("存储设施")
        ops_page.search(pool_name)

        # 如果找到存储池，则删除
        ops_page.delete_storage_pool(pool_name)
    except Exception as e:
        logger.warning(f"清理存储池 {pool_name}时出错: {e}")

        # 禁用磁盘
    try:
        ops_page.search_disk("所在物理机", node)
        ops_page.disable_disk(node)

    except Exception as e:
        logger.warning(f"禁用裸磁盘{_disk_name}时出错: {e}")

@pytest.fixture(scope="class")
def labels(ecs_page, request):
    params = getattr(request, 'param', {})
    count = params.get('count', 1)  # 默认创建1个标签

    # 生成标签名称
    label_names = []
    prefix = params.get('prefix', 'label')  # 默认前缀为'label'
    with allure_step_log("创建指定数量的标签"):
        for i in range(count):
            # 使用随机数据生成唯一标签名称
            name = f"{prefix}_{random_data()}"
            label_name = ecs_page.create_label(name)
            ecs_page.assert_popup_success("新建标签成功")
            label_names.append(label_name)
            logger.info(f"已创建标签: {label_name}")

    yield label_names

    # 测试结束后清理标签
    with allure_step_log("清理测试标签"):
        logger.info(f"开始清理标签: {label_names}")
        try:
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("标签")
            ecs_page.batch_delete_label(label_names)
            logger.info(f"标签清理完成: {label_names}")
        except Exception as e:
            logger.warning(f"清理标签时出错: {e}")


@pytest.fixture()
def affinity(ecs_page, request):
    params = getattr(request, 'param', {})
    count = params.get('count', 1)  # 默认创建1个标签

    # 生成标签名称
    label_names = []
    prefix = params.get('prefix', 'label')  # 默认前缀为'label'

    for i in range(count):
        # 使用随机数据生成唯一标签名称
        name = f"{prefix}_{random_data()}"
        label_name = ecs_page.create_label(name)
        ecs_page.assert_popup_success("新建标签成功")
        label_names.append(label_name)
        logger.info(f"已创建标签: {label_name}")

    yield label_names


@pytest.fixture(scope="class")
def vpc_page(page):
    """初始化虚拟私有云页面对象"""
    vpc_page = VpcPage(page)
    vpc_page.goto_service('虚拟私有云')
    return vpc_page


@pytest.fixture(scope="class")
def vpc(vpc_page, request):
    """
    创建并返回一个VPC资源数据，测试结束后自动清理

    支持参数化配置，可通过pytest.mark.parametrize传入参数：
    - name: VPC名称，如果未指定则随机生成
    - subnet_name: 子网名称
    - cidr: 子网CIDR
    - desc: VPC描述
    - subnet_desc: 子网描述
    - network_type: 网络类型（Geneve/Vlan/Flat）
    - gateway_mode: 网关模式（分布式网关/集中式网关）
    - vlan_id: VLAN ID
    - gateway_ip: 网关IP

    Args:
        vpc_page: VPC页面对象
        request: pytest的request对象，用于获取测试用例传递的参数

    Returns:
        dict: 包含VPC信息的字典，例如：
            {
                "name": "autotest-abc123",
                "subnet_name": "subnet-xyz789",
                "cidr": "10.0.0.0/24",
                "network_type": "Geneve"
            }

    Yields:
        dict: VPC信息字典，测试用例执行后自动清理
    """


    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})

    name = params.get('name', random_data())
    print(params.get('vlan_id'))

    # 构建创建参数
    create_kwargs = {
        "name": name,
        "subnet_name": params.get('subnet_name', random_data()),
        "cidr": params.get('cidr', random_data("cidr")),
        "network_type": params.get('network_type', 'Geneve'),
        "gateway_mode": params.get('gateway_mode', "分布式网关"),
        "vlan_id": params.get('vlan_id')
    }

    # 创建VPC
    vpc_page.vpc_create(**create_kwargs)
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    vpc_page.assert_status(name)

    # 构建返回的VPC信息
    vpc_data = create_kwargs

    yield vpc_data

    # 清理VPC
    vpc_page.vpc_delete(name)
    vpc_page.assert_deleted(name)

