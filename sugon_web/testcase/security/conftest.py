import pytest
from sugon_web.pages.security.apt import AptPage
from sugon_web.pages.security.usm import UsmPage
from sugon_web.pages.security.ver import VerPage
from sugon_web.pages.security.vdb import VdbPage
from sugon_web.utils.logger import logger


@pytest.fixture(scope="session")
def usm_instance(browser, config):
    """创建 USM 实例并自动清理（scope=session）。

    所有 USM 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 usm_instance 参数即可接入，通过 usm_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._usm_helpers import create_usm_instance, delete_usm_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    usm_page_obj = UsmPage(page)
    usm_page_obj.goto_service("云堡垒机高级版")

    name = random_data().replace("autotest-", "autotest-usm-")
    result = None

    try:
        result = create_usm_instance(page, usm_page_obj, name)
        yield result
    finally:
        if result is not None:
            try:
                delete_usm_instance(page, usm_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 USM 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_usm_page = UsmPage(new_page)
                        delete_usm_instance(new_page, new_usm_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 USM 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 USM 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="function")
def apt_page(page):
    """初始化攻击预警APT页对象"""
    page_object = AptPage(page)
    page_object.goto_service("攻击预警")
    return page_object


@pytest.fixture(scope="function")
def usm_page(page):
    """初始化云堡垒机高级版USM页对象"""
    page_object = UsmPage(page)
    page_object.goto_service("云堡垒机高级版")
    # 等待列表数据加载完成，避免刚进入页面时表格为空导致查找失败
    for _ in range(10):
        if page.locator(".el-table__row").count() > 0:
            break
        page.wait_for_timeout(2000)
    else:
        page.wait_for_selector(".el-table__row", timeout=30000)
    page.wait_for_timeout(2000)
    return page_object


@pytest.fixture(scope="session")
def ver_instance(browser, config):
    """创建 VER 实例并自动清理（scope=session）。

    所有 VER 测试共享同一个实例，session 结束时自动删除。
    测试方法声明 ver_instance 参数即可接入，通过 ver_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._ver_helpers import create_ver_instance, delete_ver_instance
    from sugon_web.utils.data import random_data

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    ver_page_obj = VerPage(page)
    ver_page_obj.goto_service("日志审计")

    name = random_data().replace("autotest-", "autotest-ver-")
    result = None

    try:
        result = create_ver_instance(page, ver_page_obj, name)
        yield result
    finally:
        if result is not None:
            try:
                delete_ver_instance(page, ver_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 VER 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_ver_page = VerPage(new_page)
                        delete_ver_instance(new_page, new_ver_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 VER 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 VER 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="session")
def vdb_instance(browser, config):
    """创建 VDB 实例并自动清理（scope=session）。

    所有 VDB 操作类测试共享同一个实例，session 结束时自动删除。
    测试方法声明 vdb_instance 参数即可接入，通过 vdb_instance["name"] 获取实例名。

    Yields:
        dict: 包含 name 字段的实例信息。
    """
    from sugon_web.conftest import _create_logged_in_page
    from sugon_web.testcase.security._vdb_helpers import create_vdb_instance, delete_vdb_instance
    from sugon_web.utils.util import random_data

    context = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(context, config)
    vdb_page_obj = VdbPage(page)
    vdb_page_obj.goto_service("数据库审计")

    name = random_data().replace("autotest-", "autotest-vdb-")
    result = None

    try:
        result = create_vdb_instance(page, vdb_page_obj, name)
        yield result
    finally:
        if result is not None:
            try:
                delete_vdb_instance(page, vdb_page_obj, result["name"])
            except Exception as e:
                error_msg = str(e)
                if "未找到名称为" in error_msg or "未找到名称" in error_msg:
                    logger.warning(f"使用原 page 清理 VDB 实例失败（可能 session 过期）: {e}，尝试创建新 page 重新清理")
                    try:
                        new_page = _create_logged_in_page(context, config)
                        new_vdb_page = VdbPage(new_page)
                        delete_vdb_instance(new_page, new_vdb_page, result["name"])
                        new_page.close()
                    except Exception as e2:
                        logger.error(f"使用新 page 清理 VDB 实例也失败: {e2}")
                        raise e2 from e
                else:
                    logger.error(f"清理 VDB 实例失败: {e}")
                    raise
        page.close()
        context.close()


@pytest.fixture(scope="function")
def ver_page(page):
    """初始化日志审计VER页对象"""
    page_object = VerPage(page)
    page_object.goto_service("日志审计")
    return page_object


@pytest.fixture(scope="function")
def vdb_page(page):
    """初始化数据库审计VDB页对象"""
    page_object = VdbPage(page)
    page_object.goto_service("数据库审计")
    return page_object

