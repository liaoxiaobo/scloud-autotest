"""安全合规模块通用 helper 函数。

供多个安全服务测试共用的后端验证、FIP 连通性检查、等待等函数。
"""
import platform
import re
import socket
import subprocess
import time

from sugon_web.utils.logger import logger


def _ping_fip(fip: str, timeout: int = 5) -> bool:
    """检查 FIP 连通性（支持 Windows/Linux）。

    先尝试 ICMP ping；如果环境禁 ping，则 fallback 到 TCP 443/80 端口探测。

    Args:
        fip: 公网IP地址
        timeout: 超时秒数

    Returns:
        bool: True 表示可达
    """
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), fip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), fip]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # ICMP 不通时，尝试 TCP 连接常见端口
    for port in (443, 80):
        try:
            with socket.create_connection((fip, port), timeout=timeout):
                logger.info(f"FIP {fip}:{port} TCP 连通")
                return True
        except Exception:
            continue
    return False


def wait_backend_volume_size(
    ssh_host,
    server_id: str,
    expected_size: int,
    timeout: int = 300,
    interval: int = 10,
    target_host: str = None,
) -> int:
    """通过 SSH 轮询 ``scli guest show``，等待后端云硬盘大小达到期望值。

    该函数用于解决 UI 已显示扩容后大小但后端尚未同步完成的问题。

    Args:
        ssh_host: SSH 连接对象（pytest fixture）。
        server_id: 虚拟机 server_id（UUID）。
        expected_size: 期望磁盘大小（GiB）。
        timeout: 最大等待时间（秒），默认 300。
        interval: 每次轮询间隔（秒），默认 10。
        target_host: 若需在目标物理机上执行命令（如 WAF/VER），传入物理机短名；
            为 None 时直接在 ssh_host 上执行。

    Returns:
        int: 后端实际磁盘大小（GiB）。

    Raises:
        AssertionError: 超时后后端大小仍未达到期望值。
    """
    start = time.time()
    inner_cmd = f"scli guest show {server_id}"
    if target_host:
        cmd = f"ssh -o StrictHostKeyChecking=no {target_host} '{inner_cmd}'"
    else:
        cmd = inner_cmd
    last_size = -1
    while time.time() - start < timeout:
        output = ssh_host.run(cmd, check_rc=True)
        size_match = re.search(r'"size"\s*:\s*(\d+)', output)
        if size_match is None:
            logger.warning(f"scli guest show 输出中未解析到 size，等待 {interval}s 后重试")
            time.sleep(interval)
            continue
        last_size = int(size_match.group(1))
        logger.info(
            f"后端磁盘大小检查: server_id={server_id}, 当前={last_size}GiB, "
            f"期望>={expected_size}GiB, 已耗时={int(time.time() - start)}s"
        )
        if last_size >= expected_size:
            logger.info(f"后端磁盘大小已达预期: {last_size}GiB")
            return last_size
        time.sleep(interval)

    raise AssertionError(
        f"后端磁盘大小未在 {timeout}s 内达到预期: 当前={last_size}GiB, 期望>={expected_size}GiB"
    )


def cleanup_security_instance(
    context,
    config,
    page,
    page_obj,
    name: str,
    delete_fn,
    unbind_method_name: str | None = None,
    lock=None,
    current_name: str | None = None,
) -> None:
    """安全合规模块实例 fixture 的通用 teardown。

    执行顺序：
    1. 若指定了解绑方法，先尝试解绑 EIP（忽略异常）。
    2. 调用 delete_fn 删除实例。
    3. 当原 name 找不到时，若测试过程中修改过实例名称（current_name），
       会尝试用当前名称再清理一次。
    4. 当原 page session 过期导致"未找到名称"时，新建 page 重试一次。
    5. 最后释放可选锁并关闭 page/context。

    Args:
        context: Playwright BrowserContext。
        config: Config 对象。
        page: 当前 Playwright Page。
        page_obj: 当前页面对象实例。
        name: 待清理实例名称（fixture 创建时的原始名称）。
        delete_fn: 删除函数，签名为 delete_fn(page, page_obj, name)。
        unbind_method_name: 解绑 EIP 的方法名，如 "usm_unbind_eip"；无需解绑则留空。
        lock: 可选的锁对象，拥有 release() 方法（如 AptProjectLock）。
        current_name: 可选，实例当前名称（如被重命名过）。清理时优先尝试原始名称，
                      失败后回退到当前名称。
    """
    from sugon_web.conftest import _create_logged_in_page

    names_to_try = [name]
    if current_name and current_name != name:
        names_to_try.append(current_name)

    def _do_cleanup(cleanup_page, cleanup_page_obj):
        last_error = None
        for try_name in names_to_try:
            try:
                if unbind_method_name:
                    try:
                        getattr(cleanup_page_obj, unbind_method_name)(try_name)
                    except Exception:
                        pass
                delete_fn(cleanup_page, cleanup_page_obj, try_name)
                return
            except Exception as e:
                last_error = e
                logger.warning(f"使用名称 {try_name} 清理实例失败: {e}")
        raise last_error or AssertionError("清理实例失败，所有候选名称均无法定位到实例")

    try:
        _do_cleanup(page, page_obj)
    except Exception as e:
        error_msg = str(e)
        if "未找到名称为" in error_msg or "未找到名称" in error_msg:
            logger.warning(
                f"使用原 page 清理实例 {name} 失败（可能 session 过期）: {e}，尝试创建新 page 重新清理"
            )
            new_page = _create_logged_in_page(context, config)
            try:
                new_page_obj = page_obj.__class__(new_page)
                _do_cleanup(new_page, new_page_obj)
            finally:
                new_page.close()
        else:
            logger.error(f"清理实例 {name} 失败: {e}")
            raise
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception as e:
                logger.warning(f"释放实例锁时忽略异常: {e}")
        page.close()
        context.close()
