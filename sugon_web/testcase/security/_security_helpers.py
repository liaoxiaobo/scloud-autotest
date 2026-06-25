"""安全合规模块通用 helper 函数。

供多个安全服务测试共用的后端验证、等待等纯函数。
"""
import re
import time

from sugon_web.utils.logger import logger


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
