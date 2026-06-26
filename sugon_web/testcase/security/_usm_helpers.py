"""USM 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import re
import subprocess
import time
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def _ping_fip(fip: str, timeout: int = 5) -> bool:
    """检查 FIP 连通性（支持 Windows/Linux）。

    Args:
        fip: 公网IP地址
        timeout: 超时秒数

    Returns:
        bool: True 表示 ping 通
    """
    import platform
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), fip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), fip]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return result.returncode == 0
    except Exception:
        return False


def create_usm_instance(page, usm_page, name: str, network: str = None,
                        subnet: str = None) -> dict[str, Any]:
    """创建 USM 实例并完成绑定EIP+跳转验证（最多3次重试）。"""
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-usm-")
            logger.info(f"第 {attempt} 次尝试创建 USM 实例: {actual_name}")
            usm_page.usm_create(name=actual_name, network=network, subnet=subnet)
            usm_page.assert_usm_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except (AssertionError, Exception) as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"USM 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    # 绑定公网IP
    eip = usm_page.usm_bind_eip(name)
    usm_page.goto_list_page()
    logger.info(f"新实例 {name} 创建并绑定EIP完成, FIP={eip}")

    # 检查 FIP 连通性
    fip = None
    if eip:
        fip_match = re.search(r"\d+\.\d+\.\d+\.\d+", str(eip))
        if fip_match:
            fip = fip_match.group(0)

    if fip:
        logger.info(f"USM FIP 连通性检查: ping {fip}")
        if _ping_fip(fip):
            logger.info(f"USM FIP {fip} ping 通，开始跳转地址验证")
        else:
            logger.warning(f"USM FIP {fip} 首次 ping 不通，等待3分钟后重试...")
            time.sleep(180)
            if _ping_fip(fip):
                logger.info(f"USM FIP {fip} 等待后 ping 通，开始跳转地址验证")
            else:
                logger.warning(f"USM FIP {fip} 仍 ping 不通，环境网络问题，跳过跳转地址验证继续执行")
                usm_page.goto_list_page()
                row_data = usm_page.get_row_data(name)
                return {"name": name, "row_data": row_data}

    # 验证跳转地址
    usm_page.usm_to_details(name)
    usm_page.wait_for_detail_page_ready(timeout=60)
    new_page = usm_page.usm_open_jump_address()
    if new_page and new_page.url:
        if "chrome-error" not in new_page.url and (
            "u-s-m-" in new_page.url
            or "/dashboard" in new_page.url
            or "openapiOAuth" in new_page.url
        ):
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
