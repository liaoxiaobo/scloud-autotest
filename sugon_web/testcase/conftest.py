import allure
import pytest

from sugon_web.pages.login import LoginPage
from sugon_web.pages.evs import EvsPage
from sugon_web.pages.ecs import EcsPage
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger
from sugon_web.utils.util import random_data


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

@pytest.fixture(scope="class")
def volume(evs_page):
    """初始化云硬盘数据"""
    name = random_data()
    evs_page.evs_create(name)
    evs_page.assert_popup_success()
    evs_page.assert_status(name, status="可用")
    volume = {"name": name}
    
    yield volume

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
def _ecs(ecs_page):
    """初始化弹性云服务器数据"""
    name = random_data()
    ecs_page.ecs_create(name)
    ecs_page.assert_popup_success("创建实例命令下发成功")
    ecs_page.assert_status(name, status="当前无任务", timeout=300)
    row_data = ecs_page.get_row_details(name)
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
    # metadata["mfip"] = ecs_page.get_row_details(metadata["ip"]).get("Mfip 地址")

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