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
    """初始化统一身份认证IAM页对象"""
    page_object = IamPage(page)
    page_object.goto_service("统一身份认证IAM")
    return page_object


@pytest.fixture(scope="package")
def iam_shared_org(browser, config):
    """package级IAM顶级组织，整个iam测试包共享，最后清理。"""
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    org_info = create_iam_org(page)
    page.close()
    ctx.close()
    yield org_info

    # 清理：删除顶级组织
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_delete_organization(org_info["org_name"])
    page.close()
    ctx.close()


@pytest.fixture(scope="package")
def iam_shared_child_org(browser, config, iam_shared_org):
    """package级IAM子组织，依赖iam_shared_org，先于父组织清理。"""
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    child_info = create_iam_child_org(page, iam_shared_org["org_name"])
    page.close()
    ctx.close()
    yield child_info

    # 清理：删除子组织（使用最新名称，改名测试可能已更新）
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    iam = IamPage(page)
    iam.goto_service("统一身份认证IAM")
    iam.iam_delete_organization(child_info["child_name"])
    page.close()
    ctx.close()


@pytest.fixture(scope="package")
def iam_shared_user(browser, config, iam_shared_child_org):
    """package级IAM测试用户，在共享子组织下创建，所有用户测试共享。"""
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    user_info = create_iam_user(page, target_org=iam_shared_child_org["child_name"])
    page.close()
    ctx.close()
    yield user_info

    # 清理：删除用户
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    delete_iam_user(page, user_info["display_name"])
    page.close()
    ctx.close()


@pytest.fixture(scope="function")
def iam_batch_users(browser, config, iam_shared_child_org):
    """function级 fixture：在共享子组织下创建5个普通用户，测试结束后自动删除。"""
    from sugon_web.utils.util import random_data
    import random

    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)

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
    ctx.close()

    yield users

    # 清理：删除所有用户
    ctx = browser.new_context(ignore_https_errors=True)
    page = _create_logged_in_page(ctx, config)
    for user in users:
        try:
            delete_iam_user(page, user["display_name"])
        except Exception as e:
            logger.warning(f"删除用户 {user['display_name']} 失败: {e}")
    page.close()
    ctx.close()
