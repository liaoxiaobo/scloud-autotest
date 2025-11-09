import pytest
from sugon_web.pages.login import LoginPage
from sugon_web.pages.evs import EvsPage
from sugon_web.pages.ecs import EcsPage
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
