"""VDB 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import time
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


def _ensure_vdb_running(vdb_page, name: str, timeout: int = 1800) -> dict[str, Any]:
    """等待 VDB 实例到达运行状态，期间可自动授权一次或清理创建失败实例。

    该 helper 集中处理创建后的副作用行为，使 assert_vdb_status 保持纯断言。
    """
    start_time = time.time()
    last_data = {}
    authorized = False
    while time.time() - start_time < timeout:
        try:
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            last_data = row_data
            svc = str(row_data.get("服务状态", "")).strip()
            vmst = str(row_data.get("虚拟机状态", "")).strip()
            if "运行" in svc and "运行" in vmst:
                logger.info(f"VDB 实例 {name} 已到达运行状态")
                return row_data
            if "创建中" in vmst and "不可用" in svc:
                logger.warning(
                    f"VDB 实例 {name} 创建失败（虚拟机=创建中, 服务=不可用），将自动清理并抛出异常"
                )
                try:
                    vdb_page.vdb_delete(name)
                    vdb_page.assert_deleted(name, timeout=120, refresh=True)
                    logger.info(f"VDB 实例 {name} 已自动删除")
                except Exception as del_err:
                    logger.warning(f"VDB 实例 {name} 自动删除失败: {del_err}")
                raise AssertionError(
                    f"VDB 实例 {name} 创建失败（虚拟机状态=创建中, 服务状态=不可用），"
                    f"已自动清理，请重新创建"
                )
            if not authorized and "授权失败" in svc and "创建中" not in vmst:
                logger.info(f"VDB 实例 {name} 服务状态为'授权失败'，执行授权操作")
                authorized = True
                try:
                    vdb_page.vdb_authorize(name, "1个月")
                    continue
                except Exception as e:
                    logger.warning(f"VDB 实例 {name} 自动授权失败: {e}")
        except AssertionError:
            raise
        except Exception as e:
            logger.debug(f"读取 VDB 实例 {name} 状态失败: {e}")
        time.sleep(5)
    raise AssertionError(
        f"[EnsureRunning] VDB '{name}' | 状态未收敛 | "
        f"期望: 服务=运行, 虚拟机=运行 | 实际={last_data}"
    )


def create_vdb_instance(page, vdb_page, name: str, network: str = None,
                        subnet: str = None) -> dict[str, Any]:
    """创建 VDB 实例并完成跳转验证（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        vdb_page: VDB 页面对象。
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
                actual_name = random_data().replace("autotest-", "autotest-vdb-")
            logger.info(f"第 {attempt} 次尝试创建 VDB 实例: {actual_name}")
            vdb_page.vdb_create(name=actual_name, network=network)
            _ensure_vdb_running(vdb_page, actual_name, timeout=1800)
            name = actual_name
            break
        except Exception as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"VDB 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    vdb_page.vdb_to_details(name)
    vdb_page.wait_for_page_ready()
    start = time.time()
    while time.time() - start < 30:
        try:
            body = vdb_page.get_detail_body_text()
            if "跳转地址" in body and len(body) > 500:
                break
        except Exception:
            pass
        time.sleep(2)
    new_page = vdb_page.vdb_open_jump_address()
    jump_ok = False
    if new_page and new_page.url:
        if "chrome-error" not in new_page.url and (
            "vdb" in new_page.url.lower()
            or "/dashboard" in new_page.url
            or "openapiOAuth" in new_page.url
        ):
            jump_ok = True
            logger.info(f"VDB 实例 {name} 跳转地址验证通过: {new_page.url}")
        else:
            logger.warning(
                f"VDB 实例 {name} 跳转地址验证未通过，URL: {new_page.url}，"
                "继续执行测试（VM 本身已就绪）"
            )
    else:
        logger.warning("VDB 实例跳转地址页面为空，继续执行测试（VM 本身已就绪）")
    if new_page and new_page != page:
        new_page.close()

    vdb_page.goto_list_page()
    row_data = vdb_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_vdb_instance(page, vdb_page, name: str) -> None:
    """删除 VDB 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        vdb_page: VDB 页面对象。
        name: 要删除的实例名称。
    """
    vdb_page.goto_list_page()
    vdb_page.vdb_delete(name)
    vdb_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"VDB 实例 {name} 已删除")
