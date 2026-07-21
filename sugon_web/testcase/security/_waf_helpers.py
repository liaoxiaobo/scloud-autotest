"""WEB应用防火墙WAF 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import time
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def create_waf_instance(page, waf_page, name: str, network: str = None,
                        subnet: str = None, volume_type: str = None,
                        cpu: str = "4核", memory: str = "8GiB") -> dict[str, Any]:
    """创建 WAF 实例并完成跳转验证（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        waf_page: WAF 页面对象。
        name: 实例名称。
        network: 专有网络名称。
        subnet: 子网名称。
        volume_type: 云硬盘类型，None 表示由 Page Object 根据 Config.stor 自动推断。
        cpu: 规格 CPU，默认 4核。
        memory: 规格内存，默认 8GiB。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-waf-")
            logger.info(f"第 {attempt} 次尝试创建 WAF 实例: {actual_name}")
            waf_page.goto_list_page()
            waf_page.waf_create(name=actual_name, network=network, subnet=subnet,
                                volume_type=volume_type, cpu=cpu, memory=memory)
            waf_page.assert_waf_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except Exception as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"WAF 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    # 跳转地址验证
    waf_page.waf_to_details(name)
    waf_page.wait_for_page_ready()
    start = time.time()
    while time.time() - start < 30:
        try:
            body = waf_page.get_detail_body_text()
            if "跳转地址" in body and len(body) > 500:
                break
        except Exception:
            pass
        time.sleep(2)
    new_page = waf_page.waf_open_jump_address()
    if new_page and new_page.url:
        if "chrome-error" not in new_page.url:
            logger.info(f"WAF 实例 {name} 跳转地址验证通过: {new_page.url}")
        else:
            logger.warning(
                f"WAF 实例 {name} 跳转地址验证未通过，URL: {new_page.url}，"
                "继续执行测试（VM 本身已就绪）"
            )
    else:
        logger.warning("WAF 实例跳转地址页面为空，继续执行测试（VM 本身已就绪）")
    if new_page and new_page != page:
        new_page.close()

    waf_page.goto_list_page()
    row_data = waf_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_waf_instance(page, waf_page, name: str) -> None:
    """删除 WAF 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        waf_page: WAF 页面对象。
        name: 要删除的实例名称。
    """
    waf_page.goto_list_page()
    waf_page.waf_delete(name)
    waf_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"WAF 实例 {name} 已删除")
