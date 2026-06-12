"""VPN 网关连接 ER 场景专用 fixture。"""

import time

import allure
import pytest

from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


@pytest.fixture
def er_for_vpn_gateway(er_page):
    """创建并返回一个开启 HA 的企业路由器，测试结束后自动清理。

    该 fixture 专为 VPN 网关连接 ER 场景设计。teardown 阶段会等待 40 秒，
    确保 VPN 网关后台资源释放完毕后再删除 ER，避免 ER 因仍有依赖而删除失败。

    Yields:
        dict: 包含企业路由器名称，如 {"name": "vpn_er_xxxx"}。
    """
    er_name = f"vpn_er_{random_data(length=4)}"

    with allure_step_log(f"前置: 创建开启HA的企业路由器 {er_name}"):
        er_page.er_create(name=er_name, cluster_name="Autotest", ha_enable=True)
        er_page.assert_popup_success(timeout=30)
        logger.info(f"企业路由器 {er_name} 创建提交成功")

    with allure_step_log("前置: 等待企业路由器状态变为运行中"):
        er_page._ensure_list_page()
        er_page.assert_status(
            er_name,
            status="运行中",
            timeout=600,
            refresh=True,
            refresh_interval=10,
        )

    yield {"name": er_name}

    with allure_step_log("清理: 等待VPN网关后台资源释放（40秒）"):
        time.sleep(40)

    with allure_step_log(f"清理: 删除企业路由器 {er_name}"):
        try:
            er_page._ensure_list_page()
            er_page.wait_for_page_ready()
            try:
                er_page.get_row_by_name(er_name)
            except Exception:
                logger.info(f"企业路由器 {er_name} 已不存在，跳过删除")
                return
            er_page.er_delete(er_name)
            er_page.assert_deleted(er_name, timeout=120)
        except Exception as e:
            logger.warning(f"清理企业路由器 {er_name} 失败: {e}")
