"""USM 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import re
import time
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data
from sugon_web.testcase.security._security_helpers import _ping_fip


def _ensure_usm_running(usm_page, name: str, timeout: int = 1200) -> dict[str, Any]:
    """等待 USM 实例到达运行状态，期间可自动授权一次或清理创建失败实例。

    该 helper 集中处理创建后的副作用行为，使 assert_usm_status 保持纯断言。
    """
    start_time = time.time()
    last_data = {}
    authorized = False
    while time.time() - start_time < timeout:
        try:
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            last_data = row_data
            svc = row_data.get("服务状态", "")
            vmst = row_data.get("虚拟机状态", "")
            if "运行" in svc and "运行" in vmst:
                logger.info(f"USM 实例 {name} 已到达运行状态")
                return row_data
            if "创建中" in vmst and "不可用" in svc:
                logger.warning(
                    f"USM 实例 {name} 创建失败（虚拟机=创建中, 服务=不可用），将自动清理并抛出异常供重新创建"
                )
                try:
                    usm_page.usm_delete(name)
                    usm_page.assert_deleted(name, timeout=120, refresh=True)
                    logger.info(f"USM 实例 {name} 已自动删除")
                except Exception as del_err:
                    logger.warning(f"USM 实例 {name} 自动删除失败: {del_err}")
                raise AssertionError(
                    f"USM 实例 {name} 创建失败（虚拟机状态=创建中, 服务状态=不可用），"
                    f"已自动清理，请重新创建"
                )
            if not authorized and "授权失败" in svc and "创建中" not in vmst:
                logger.info(f"USM 实例 {name} 服务状态为'授权失败'，执行授权操作")
                authorized = True
                try:
                    usm_page.usm_authorize(name, "1个月")
                    continue
                except Exception as e:
                    logger.warning(f"USM 实例 {name} 自动授权失败: {e}")
        except AssertionError:
            raise
        except Exception as e:
            logger.debug(f"读取 USM 实例 {name} 状态失败: {e}")
        time.sleep(5)
    raise AssertionError(
        f"[EnsureRunning] USM '{name}' | 状态未收敛 | "
        f"期望: 服务=运行, 虚拟机=运行 | 实际={last_data}"
    )


def create_usm_instance(page, usm_page, name: str, network: str = None,
                        subnet: str = None, eip_ip: str | None = None) -> dict[str, Any]:
    """创建 USM 实例并完成绑定 EIP（最多3次重试）。

    跳转地址的打开与验证由测试用例自身负责，fixture/helper 阶段只做资源创建与绑定，
    避免从跳转页返回后列表页状态异常导致 fixture 初始化失败。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-usm-")
            logger.info(f"第 {attempt} 次尝试创建 USM 实例: {actual_name}")
            usm_page.usm_create(name=actual_name, network=network, subnet=subnet)
            _ensure_usm_running(usm_page, actual_name, timeout=1200)
            name = actual_name
            break
        except Exception as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"USM 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    # 绑定公网IP（指定 FIP 池中的 IP 或弹窗中第一个可用 IP）
    eip = usm_page.usm_bind_eip(name, eip_ip=eip_ip)
    usm_page.goto_list_page()
    logger.info(f"新实例 {name} 创建并绑定EIP完成, FIP={eip}")

    # 检查 FIP 连通性（仅记录日志，不在 fixture 中做跳转地址验证，
    # 跳转地址的打开与断言由 test_usm_01_create_and_fip_bind 负责）
    fip = None
    if eip:
        fip_match = re.search(r"\d+\.\d+\.\d+\.\d+", str(eip))
        if fip_match:
            fip = fip_match.group(0)

    if fip:
        logger.info(f"USM FIP 连通性检查: ping {fip}")
        if _ping_fip(fip):
            logger.info(f"USM FIP {fip} ping 通")
        else:
            logger.warning(f"USM FIP {fip} ping 不通，环境网络问题，继续执行测试")

    # 尽量刷新行数据，但从跳转地址页返回后列表页偶发为空，
    # 因此获取失败时不阻断 fixture，回退到 ensure running 阶段的行数据。
    try:
        usm_page.goto_list_page()
        row_data = usm_page.get_row_data(name)
    except Exception as e:
        logger.warning(f"USM 实例 {name} 创建完成后读取列表行数据失败: {e}，使用创建过程中的行数据")
        row_data = row_data if row_data is not None else {}

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
