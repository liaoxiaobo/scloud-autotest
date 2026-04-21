import pytest
from sugon_web.common.playwright import expect
from sugon_web.pages.kms import KmsPage
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@pytest.fixture()
def evss_policy(evs_page):
    """创建并返回一个快照策略，测试结束后自动清理。"""
    policy_name = random_data()

    with allure_step_log("创建快照策略"):
        evs_page.evss_policy_create(
            name=policy_name,
            enabled=True,
            hours=[0, 1, 2],
            retention_type="按数量",
            retention_value=1,
            cycle_days=1,
        )
        evs_page.assert_popup_success("添加策略成功")

    yield policy_name

    with allure_step_log("清理测试数据"):
        evs_page.evss_policy_delete(policy_name)
        evs_page.assert_deleted(policy_name)


@pytest.fixture()
def evss(evs_page, volume):
    """创建并返回一个快照，测试结束后自动清理。"""
    snapshot_name = random_data()
    with allure_step_log("创建快照"):
        evs_page.evss_create(volume["name"], snapshot_name, "测试快照")
        evs_page.assert_popup_success("创建快照成功")
        evs_page.goto_submenu("快照")
        evs_page.assert_status(snapshot_name, status="可用")

    yield {"name": snapshot_name, "volume_name": volume["name"]}

    with allure_step_log("清理测试数据"):
        evs_page.goto_submenu("快照")
        evs_page.evss_delete(snapshot_name)
        evs_page.assert_deleted(snapshot_name)


@pytest.fixture
def kms_page(page):
    """创建密钥管理页面对象并导航到密钥管理页面。"""
    kms = KmsPage(page)
    kms.goto_service("可信密码模块")

    try:
        text_locator = kms.get_by_text("您已成功授权")
        expect(text_locator).to_be_visible()
    except Exception:
        pytest.skip("当前环境可信密码模块未授权，跳过测试")

    return kms


@pytest.fixture
def kms_key(kms_page, request):
    """创建测试密钥并在测试后清理。"""
    engine = getattr(request, "param", "HCT")
    key_name = random_data()

    kms_page.kms_create(
        name=key_name,
        engine=engine,
        key_type="SM4 (用途：加解密，包括系统盘、数据盘、网卡等)",
        desc="测试密钥",
    )
    kms_page.assert_popup_success("执行成功")
    key_data = kms_page.get_row_data(key_name)

    yield key_data

    kms_page.goto_service("可信密码模块")
    kms_page.kms_delete(key_name)
    kms_page.assert_deleted(key_name)
