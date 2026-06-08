import pytest
from sugon_web.config.config import Config
from sugon_web.pages.iam.iam import IamPage
from sugon_web.conftest import _create_logged_in_page
from sugon_web.testcase.iam._iam_helpers import (
    create_iam_user, delete_iam_user,
    create_iam_org, create_iam_child_org,
)
from sugon_web.utils.logger import logger


@pytest.fixture(scope="session")
def verify_ctx(browser):
    """session级验证上下文，创建时预热避免首次调用超时。"""
    ctx = browser.new_context(ignore_https_errors=True)
    base_url = Config.get("base_url")
    warmup = ctx.new_page()
    warmup.goto(f"{base_url}/#/login", wait_until="domcontentloaded")
    warmup.close()
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def iam_page(page):
    """初始化统一身份认证IAM页对象，确保页面状态干净"""
    page_object = IamPage(page)
    page_object.goto_service("统一身份认证IAM")
    page_object.close_dialog_if_exists()
    try:
        page_object.page.locator(".el-input__clear, .search-clear").first.click(timeout=2000)
    except Exception:
        pass
    return page_object


@pytest.fixture(scope="function")
def iam_tenant_page(page, iam_shared_tenant_user):
    """初始化IAM页对象（运营-租户-用户管理列表页入口），扁平用户列表无组织树。"""
    page_object = IamPage(page)
    page_object.goto_iam_tenant_user_list()
    page_object.close_dialog_if_exists()
    # 清理搜索框
    try:
        page_object.page.locator(".el-input__clear, .search-clear").first.click(timeout=2000)
    except Exception:
        pass
    # 主动搜索租户测试用户确保其在租户列表中可见
    search_name = iam_shared_tenant_user.get("display_name") or iam_shared_tenant_user["name"]
    try:
        search_input = page_object.page.locator("input[placeholder*='搜索']").first
        if search_input.count() > 0:
            search_input.fill(search_name)
            page_object.page.wait_for_timeout(2000)
            rows = page_object.page.locator(".el-table__row")
            if rows.count() > 0:
                logger.info(f"租户列表中已找到用户 {search_name}")
            else:
                # 改用账户名重试
                search_input.fill(iam_shared_tenant_user["name"])
                page_object.page.wait_for_timeout(2000)
            search_input.clear()
            page_object.page.wait_for_timeout(1000)
    except Exception as e:
        logger.warning(f"租户列表搜索失败: {e}")
    return page_object


@pytest.fixture(scope="package")
def _iam_shared_ctx(browser):
    """package 级共享 browser context，供 IAM fixture 复用。"""
    ctx = browser.new_context(ignore_https_errors=True)
    yield ctx
    ctx.close()


@pytest.fixture(scope="package")
def iam_shared_org(_iam_shared_ctx, config):
    """package级IAM顶级组织，整个iam测试包共享，最后清理。"""
    page = _create_logged_in_page(_iam_shared_ctx, config)
    org_info = create_iam_org(page)
    page.close()
    yield org_info

    # 清理：删除顶级组织（使用最新名称，改名测试可能已更新）
    page = _create_logged_in_page(_iam_shared_ctx, config)
    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    try:
        iam.iam_delete_organization(org_info["org_name"])
    except Exception as e:
        logger.warning(f"清理顶级组织 {org_info['org_name']} 失败: {e}")
    page.close()


@pytest.fixture(scope="package")
def iam_shared_child_org(_iam_shared_ctx, config, iam_shared_org):
    """package级IAM子组织，依赖iam_shared_org，先于父组织清理。"""
    page = _create_logged_in_page(_iam_shared_ctx, config)
    child_info = create_iam_child_org(page, iam_shared_org["org_name"])
    page.close()
    yield child_info

    # 清理：删除子组织（使用最新名称，改名测试可能已更新）
    page = _create_logged_in_page(_iam_shared_ctx, config)
    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    try:
        iam.iam_delete_organization(child_info["child_name"])
    except Exception as e:
        logger.warning(f"清理子组织 {child_info['child_name']} 失败: {e}")
    page.close()


@pytest.fixture(scope="package")
def iam_shared_user(_iam_shared_ctx, browser, config, iam_shared_child_org):
    """package级IAM测试用户，在共享子组织下创建，所有用户测试共享。"""
    page = _create_logged_in_page(_iam_shared_ctx, config)
    user_info = create_iam_user(page, target_org=iam_shared_child_org["child_name"])
    page.close()
    yield user_info

    # 清理：删除用户（忽略已删除或定位失败的情况）
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    try:
        delete_iam_user(page, user_info["display_name"], target_org=user_info.get("target_org"))
    except Exception as e:
        logger.warning(f"清理共享用户 {user_info['display_name']} 失败: {e}")
    page.close()


@pytest.fixture(scope="class")
def iam_shared_tenant_user(_iam_shared_ctx, config, iam_shared_child_org):
    """class级IAM租户测试专用用户，在共享子组织下创建，租户测试类结束后自动删除。

    与 iam_shared_user 隔离：避免 test_iam_06/07 的密码/访问控制修改污染租户测试。
    """
    page = _create_logged_in_page(_iam_shared_ctx, config)
    user_info = create_iam_user(page, target_org=iam_shared_child_org["child_name"])
    page.close()
    yield user_info

    # 清理：删除用户
    page = _create_logged_in_page(_iam_shared_ctx, config)
    try:
        delete_iam_user(page, user_info["display_name"], target_org=user_info.get("target_org"))
    except Exception as e:
        logger.warning(f"清理租户测试用户 {user_info['display_name']} 失败: {e}")
    page.close()


@pytest.fixture(scope="function")
def iam_batch_users(_iam_shared_ctx, config, iam_shared_child_org):
    """function级 fixture：在共享子组织下创建5个普通用户，测试结束后自动删除。"""
    from sugon_web.utils.data import random_data
    import random

    page = _create_logged_in_page(_iam_shared_ctx, config)

    users = []
    for i in range(5):
        name = random_data().replace("autotest-", "autotest-iam-")
        password = "Keystone@1234"
        email = f"{name}@sugon.com"
        phone = "138" + "".join(str(random.randint(0, 9)) for _ in range(8))
        user_info = create_iam_user(
            page, name=name, password=password, email=email, phone=phone,
            target_org=iam_shared_child_org["child_name"]
        )
        users.append(user_info)

    page.close()

    yield users

    # 清理：删除所有用户
    page = _create_logged_in_page(_iam_shared_ctx, config)
    for user in users:
        try:
            delete_iam_user(page, user["display_name"])
        except Exception as e:
            logger.warning(f"删除用户 {user['display_name']} 失败: {e}")
    page.close()
