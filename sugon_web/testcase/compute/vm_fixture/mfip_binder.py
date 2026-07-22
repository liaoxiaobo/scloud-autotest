from typing import Any

from sugon_web.common.mfip_helper import MfipHelper
from sugon_web.conftest import _create_admin_logged_in_page
from sugon_web.utils.logger import allure_step_log


def _bind_vm_fixture_mfips(
    admin_browser_context: Any,
    config: Any,
    metadata_list: list[dict],
) -> None:
    """为虚机绑定 MFIP（API 方式），复用 admin browser context 登录态。

    Args:
        admin_browser_context: 已登录 admin 的 Playwright BrowserContext。
        config: 配置对象。
        metadata_list: 虚机元数据列表，绑定成功后回填 ``mfip`` 字段。
    """
    with allure_step_log(f"为虚机绑定 MFIP"):
        admin_page = _create_admin_logged_in_page(admin_browser_context, config)
        try:
            helper = MfipHelper(admin_page)
            for vm_data in metadata_list:
                helper.bind_mfip_for_vm(vm_data)
        finally:
            admin_page.close()
