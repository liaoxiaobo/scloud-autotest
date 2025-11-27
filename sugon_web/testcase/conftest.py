import allure
import pytest
from sugon_web.pages.login import LoginPage
from sugon_web.pages.evs import EvsPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.ops import OpsPage
from sugon_web.pages.mysql import MySQLPage
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
                "desc": ""  # 云硬盘描述，默认为空
            }
    """
    # 获取参数，如果没有提供则使用默认值
    params = getattr(request, 'param', {})
    empty = params.get('empty', True)
    image_name = params.get('image_name', '')
    size = params.get('size', 30)
    desc = params.get('desc', '')

    name = random_data()
    evs_page.goto_service('云硬盘')  # 保证在同一服务页面,满足云盘挂载测试
    evs_page.evs_create(
        name=name,
        empty=empty,
        image_name=image_name,
        size=size,
        desc=desc
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
def _ecs(ecs_page):
    """初始化弹性云服务器数据"""
    name = random_data()
    ecs_page.ecs_create(name)
    ecs_page.assert_popup_success("创建实例命令下发成功")
    ecs_page.assert_status(name)
    row_data = ecs_page.get_row_data(name)
    metadata = {
        "name": name,
        "id": row_data["名称/ID"],
        "ip": row_data["IP地址"].split(":")[1].strip(),
        'host': row_data["物理机"],
        "flavor": row_data["规格"],
        "image": row_data["镜像名称"],
        "project": row_data["项目名称"]
    }

    # 临时方案：跨服务页面直接跳转，给虚机绑定mfip
    # ecs_page.goto_service("网络设施")
    # ecs_page.mfip_create(row_data["项目名称"], "Autotest",metadata["ip"])
    # ecs_page.assert_popup_success()
    # ecs_page.mfip_search(metadata["ip"])
    # metadata["mfip"] = ecs_page.get_row_data(metadata["ip"]).get("Mfip 地址")

    yield metadata

    ecs_page.goto_service("弹性云服务器") # 保证在同一服务页面
    ecs_page.ecs_remove(metadata["name"])
    ecs_page.ecs_delete(metadata["name"])
    ecs_page.assert_deleted(metadata["name"])

@pytest.fixture(scope="class")
def vm(_ecs, ops_page):
    """虚机绑定mfip"""
    ops_page.mfip_create(_ecs["project"], "Autotest", _ecs["ip"])
    ops_page.assert_popup_success()
    ops_page.mfip_search(_ecs["ip"])
    _ecs["mfip"] = ops_page.get_column_data("Mfip 地址")[0]   # 更新metadata

    yield _ecs


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
