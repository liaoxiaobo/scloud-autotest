import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.network import VpcPage
from sugon_web.utils.logger import allure_step_log, logger


def _do_clean_acl_rules(vpc_page, acl_name, direction):
    """按方向清理指定 ACL 下的全部规则。

    Args:
        vpc_page: 网络页面对象。
        acl_name: 目标 ACL 名称。
        direction: 规则方向，取值如“入方向”或“出方向”。

    Returns:
        None: 清理动作完成后不返回数据。
    """
    tab_name = f"{direction}规则"
    with allure_step_log(f"Fixture清理: acl规则{direction} {acl_name}"):
        try:
            vpc_page.goto_service("网络ACL")
            vpc_page.goto_acl_detail(acl_name, tab_name=tab_name)
            while vpc_page.get_by_role("row").filter(has=vpc_page.get_by_text("删除", exact=True)).count() > 0:
                vpc_page.acl_rule_delete(acl_name, direction=direction)
        except Exception as exc:
            logger.warning(f"清理ACL{direction}规则失败: {exc}")


@pytest.fixture(scope="function")
def clean_acl_inbound_rules(vpc_page, acl):
    """在单用例结束后清理入方向规则。"""
    yield
    _do_clean_acl_rules(vpc_page, acl, "入方向")


@pytest.fixture(scope="class")
def clean_acl_inbound_rules_4vms(browser_context, config, acl):
    """在 4VM 规则复用类结束后统一清理入方向规则。"""
    yield
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    try:
        _do_clean_acl_rules(vpc_page, acl, "入方向")
    finally:
        page.close()


@pytest.fixture(scope="class")
def clean_acl_outbound_rules(browser_context, config, acl):
    """在 4VM 规则复用类结束后统一清理出方向规则。"""
    yield
    page = _create_logged_in_page(browser_context, config)
    vpc_page = VpcPage(page)
    try:
        _do_clean_acl_rules(vpc_page, acl, "出方向")
    finally:
        page.close()
