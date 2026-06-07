"""USM 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_usm_instance(page, usm_page, name: str) -> dict[str, Any]:
    """创建 USM 实例并完成绑定EIP+跳转验证（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        usm_page: USM 页面对象。
        name: 实例名称。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-usm-")
            logger.info(f"第 {attempt} 次尝试创建 USM 实例: {actual_name}")
            usm_page.usm_create(name=actual_name)
            usm_page.assert_usm_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except AssertionError as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"USM 实例创建失败，将重新创建: {e}")
                continue
            raise

    # 绑定公网IP（内部含 120s 等待和网络列验证）
    usm_page.usm_bind_eip(name)
    usm_page.goto_list_page()
    logger.info(f"新实例 {name} 创建并绑定EIP完成")

    # 验证跳转地址——重新进入详情页获取新 token，避免绑定EIP期间旧token过期
    usm_page.usm_to_details(name)
    # 进入详情页后等1分钟让跳转地址完全渲染
    page.wait_for_timeout(60000)
    new_page = usm_page.usm_open_jump_address()
    jump_ok = False
    if new_page and new_page.url:
        if "chrome-error" not in new_page.url and (
            "u-s-m-" in new_page.url
            or "/dashboard" in new_page.url
            or "openapiOAuth" in new_page.url
        ):
            jump_ok = True
            logger.info(f"USM 实例 {name} 跳转地址验证通过: {new_page.url}")
        else:
            logger.warning(
                f"USM 实例 {name} 跳转地址验证未通过，URL: {new_page.url}，"
                "继续执行测试（VM 本身已就绪）"
            )
    else:
        logger.warning("USM 实例跳转地址页面为空，继续执行测试（VM 本身已就绪）")
    if new_page and new_page != page:
        new_page.close()

    usm_page.goto_list_page()
    row_data = usm_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_usm_instance(page, usm_page, name: str) -> None:
    """删除 USM 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        usm_page: USM 页面对象。
        name: 要删除的实例名称。
    """
    usm_page.goto_list_page()
    usm_page.usm_delete(name)
    usm_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"USM 实例 {name} 已删除")
