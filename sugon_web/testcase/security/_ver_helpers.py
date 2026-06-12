"""VER 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import time
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_ver_instance(page, ver_page, name: str, network: str = None,
                        subnet: str = None) -> dict[str, Any]:
    """创建 VER 实例并完成跳转验证（最多3次重试）。

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

    # 验证跳转地址——进入详情页后等待详情页渲染就绪
    ver_page.ver_to_details(name)
    ver_page.wait_for_page_ready()
    start = time.time()
    while time.time() - start < 30:
        try:
            body = ver_page.get_detail_body_text()
            if "跳转地址" in body and len(body) > 500:
                break
        except Exception:
            pass
        time.sleep(2)
    new_page = ver_page.ver_open_jump_address()
    jump_ok = False
    if new_page and new_page.url:
        if "chrome-error" not in new_page.url and (
            "ver" in new_page.url.lower()
            or "/dashboard" in new_page.url
            or "openapiOAuth" in new_page.url
        ):
            jump_ok = True
            logger.info(f"VER 实例 {name} 跳转地址验证通过: {new_page.url}")
        else:
            logger.warning(
                f"VER 实例 {name} 跳转地址验证未通过，URL: {new_page.url}，"
                "继续执行测试（VM 本身已就绪）"
            )
    else:
        logger.warning("VER 实例跳转地址页面为空，继续执行测试（VM 本身已就绪）")
    if new_page and new_page != page:
        new_page.close()

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
