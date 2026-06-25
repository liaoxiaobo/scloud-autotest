"""VER 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_ver_instance(page, ver_page, name: str, network: str = None,
                        subnet: str = None) -> dict[str, Any]:
    """创建 VER 实例并验证状态（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        ver_page: VER 页面对象。
        name: 实例名称。
        network: 专有网络名称。
        subnet: 子网名称。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-ver-")
            logger.info(f"第 {attempt} 次尝试创建 VER 实例: {actual_name}")
            ver_page.ver_create(name=actual_name, network=network)
            ver_page.assert_ver_status(actual_name, service_status="运行", vm_status="运行", timeout=1800)
            name = actual_name
            break
        except (AssertionError, Exception) as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"VER 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    ver_page.goto_list_page()
    row_data = ver_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_ver_instance(page, ver_page, name: str) -> None:
    """删除 VER 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        ver_page: VER 页面对象。
        name: 要删除的实例名称。
    """
    ver_page.goto_list_page()
    ver_page.ver_delete(name)
    ver_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"VER 实例 {name} 已删除")
