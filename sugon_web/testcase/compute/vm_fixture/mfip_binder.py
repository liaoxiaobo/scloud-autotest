from typing import Any

from sugon_web.common.mfip_helper import MfipHelper
from sugon_web.utils.logger import allure_step_log


def _bind_vm_fixture_mfips(
    page: Any,
    config: Any,
    metadata_list: list[dict],
) -> None:
    """为虚机绑定 MFIP（API 方式），使用独立 admin 登录态，并回填到元数据。"""
    with allure_step_log(f"为虚机绑定 MFIP"):
        browser = page.context.browser
        admin_page, admin_context = MfipHelper._create_admin_page(browser, config)
        try:
            helper = MfipHelper(admin_page)
            for vm_data in metadata_list:
                helper.bind_mfip_for_vm(vm_data)
        finally:
            admin_context.close()
