import pytest
from sugon_web.pages.login import LoginPage
from sugon_web.pages.storage import EvsPage
from sugon_web.pages.compute import EcsCreatePage, EcsPage
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger, allure_step_log
from sugon_web.utils.util import random_data
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
        volume = {"name": name}

    yield volume

    evs_page.evs_remove([volume["name"]])
    evs_page.evs_delete([volume["name"]])
    evs_page.assert_deleted(volume["name"])


@pytest.fixture(scope="function")
def ecs_page(page):
    """初始化弹性云服务器页对象"""
    ecs_page = EcsPage(page)
    ecs_page.goto_service('弹性云服务器')
    return ecs_page

@pytest.fixture(scope="function")
def ops_page(page):
    """初始化运维管理页对象"""
    ops_page = OpsPage(page)
    ops_page.goto_service('网络设施')
    return ops_page

@pytest.fixture(scope="class")
def vm(browser_context, config, request):
    """初始化弹性云服务器数据

    支持参数化配置，可通过pytest.mark.parametrize传入参数：
    - count: 创建虚机数量，默认为1
    - root_gb: 系统盘大小，默认为100GB
    - bind_mfip: 是否绑定mfip，默认为True
    - network: 网络名称，默认为"Autotest"
    - subnet: 子网名称，默认为"Autotest(10"
    - cluster: 集群名称，默认为"Autotest"

    特性：如果测试用例引用了vpc fixture，自动使用vpc的网络和子网信息

    返回值:
    - 如果创建一台虚机：返回字典类型的虚机信息
    - 如果创建多台虚机：返回字典列表，每个字典包含一台虚机的信息
    """
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ecs_page.goto_service('弹性云服务器')

    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    count = params.get('count', 1)
    root_gb = params.get('root_gb', 25)
    bind_mfip = params.get('bind_mfip', True)

    # ✅ 如果引用了 vpc 或依赖 vpc 的 vip fixture，自动复用同一个网络和子网
    if 'vpc' in request.fixturenames or 'vip' in request.fixturenames:
        vpc_data = request.getfixturevalue('vpc')
        network = vpc_data['name']  # VPC名称就是网络名称
        subnet = vpc_data['subnet_name']
        logger.info(f"检测到与VPC相关的fixture，使用VPC网络: {network}, 子网: {subnet}")
    else:
        network = params.get('network', 'Autotest')
        subnet = params.get('subnet', 'Autotest(10')

    cluster = params.get('cluster', 'Autotest')
    name = random_data()

    with allure_step_log("创建指定数量的虚机"):
        # 创建指定数量的虚机
        ecs_page.goto_service('弹性云服务器')
        ecs_page.ecs_create(
            name=name,
            count=count,
            network=network,
            subnet=subnet,
            cluster=cluster,
            flavor="ecs.c6.Autotest",
            image_name="",
            os_version="centos7.9",
            login_password="admin1234@sugon",
            vnc_password="sugon@20",
            sys_size=root_gb
        )
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
        ip_list = row_data["IP地址"].split("固定: ")
        vm_metadata = {
            "name": vm_name,
            "id": row_data["名称/ID"].split(":")[1].strip(),
            "ip": ip_list[-1].strip(),
            "ipv6": ip_list[-2].strip(),
            'host': row_data["物理机"],
            "flavor": row_data["规格"],
            "image": row_data["镜像名称"],
            "project": row_data["项目名称"],
            "network": network,  # 添加网络信息
            "subnet": subnet  # 添加子网信息
        }
        metadata_list.append(vm_metadata)

    # 如果需要绑定mfip
    if bind_mfip:
        for vm_data in metadata_list:
            ecs_page.goto_service("网络设施")
            ecs_page.mfip_create(vm_data["project"], network, vm_data["ip"])
            ecs_page.assert_popup_success()
            ecs_page.mfip_search(vm_data["ip"])
            # vm_data["mfip"] = ecs_page.get_column_data("Mfip 地址")[0]  # 更新metadata
            vm_data["mfip"] = ecs_page.get_row_data(vm_data["ip"]).get("Mfip 地址")
        ecs_page.goto_service("弹性云服务器")

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
    page.close()

@pytest.fixture(scope="function")
def ecs_create_page(page):
    """初始化云硬盘页对象"""
    ecs_create_page = EcsCreatePage(page)
    ecs_create_page.goto_service('弹性云服务器')
    return ecs_create_page

@pytest.fixture(scope="function")
def test_context(request):
    """用于在测试用例各步骤间传递数据的上下文"""
    if not hasattr(request.node, "test_context"):
        request.node.test_context = {}
    return request.node.test_context
