"""网页防篡改WPT 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_wpt_instance(page, wpt_page, name: str, network: str = None,
                        subnet: str = None, cpu: str = "8核",
                        memory: str = "16GiB") -> dict[str, Any]:
    """创建 WPT 实例并验证状态（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        wpt_page: WPT 页面对象。
        name: 实例名称。
        network: 专有网络名称。
        subnet: 子网名称。
        cpu: 规格 CPU，默认 8核。
        memory: 规格内存，默认 16GiB。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-wpt-")
            logger.info(f"第 {attempt} 次尝试创建 WPT 实例: {actual_name}")
            wpt_page.goto_list_page()
            wpt_page.wpt_create(name=actual_name, network=network, subnet=subnet,
                                cpu=cpu, memory=memory)
            wpt_page.assert_wpt_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except Exception as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"WPT 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    wpt_page.goto_list_page()
    row_data = wpt_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_wpt_instance(page, wpt_page, name: str) -> None:
    """删除 WPT 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        wpt_page: WPT 页面对象。
        name: 要删除的实例名称。
    """
    wpt_page.goto_list_page()
    wpt_page.wpt_delete(name)
    wpt_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"WPT 实例 {name} 已删除")
