"""APT 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_apt_instance(page, apt_page, name: str) -> dict[str, Any]:
    """创建 APT 实例并完成状态验证（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        apt_page: APT 页面对象。
        name: 实例名称。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-apt-")
            logger.info(f"第 {attempt} 次尝试创建 APT 实例: {actual_name}")
            apt_page.apt_create(name=actual_name)
            apt_page.assert_apt_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except (AssertionError, Exception) as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"APT 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    apt_page.goto_list_page()
    row_data = apt_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_apt_instance(page, apt_page, name: str) -> None:
    """删除 APT 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        apt_page: APT 页面对象。
        name: 要删除的实例名称。
    """
    apt_page.goto_list_page()
    apt_page.apt_delete(name)
    apt_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"APT 实例 {name} 已删除")
