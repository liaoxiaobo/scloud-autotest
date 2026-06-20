import time

import pytest


def assert_backend_created(logger, ssh_host, name: str, command: str = "scli guest list", timeout: int = 600,
                           interval: int = 10):
    """断言资源已在后端创建成功，支持轮询检查。

    Args:
        logger: 日志记录器（原通过 self.logger 传入）。
        ssh_host: SSH 连接对象。
        name: 要检查的资源名称。
        command: 用于检查的命令模板，默认为 "scli guest list"。
        timeout: 超时时间（秒），默认为 600 秒（10 分钟）。
        interval: 轮询间隔时间（秒），默认为 10 秒。

    Raises:
        pytest.skip: 当 SSH 连接未配置时。
        pytest.fail: 当资源在超时时间内未被创建时。
    """
    if not ssh_host:
        pytest.skip("SSH host is not configured, skipping backend assertion.")
        return

    end_time = time.time() + timeout
    if command.strip() == "scli guest list":
        check_command = f"scli guest list --name '{name}' | grep -F '{name}'"
    else:
        check_command = f"{command} | grep {name}"
    logger.info(f"开始轮询检查后端资源 '{name}' 是否已创建...")

    while time.time() < end_time:
        result = ssh_host.run(check_command)
        if result != "":
            logger.info(f"后端资源 '{name}' 已成功创建。")
            logger.debug(f"资源详情: {result}")
            return

        logger.debug(f"资源 '{name}' 尚未在后端创建，将在 {interval} 秒后重试...")
        time.sleep(interval)

    # 超时后，最后检查一次并失败
    final_result = ssh_host.run(check_command)
    if final_result != "":
        logger.info(f"后端资源 '{name}' 在最后一次检查时已创建。")
        logger.debug(f"资源详情: {final_result}")
    else:
        pytest.fail(f"超时错误：资源 '{name}' 在 {timeout} 秒内未能在后端创建。")


def assert_backend_deleted(logger, ssh_host, name: str, command: str = "scli guest list", timeout: int = 600,
                           interval: int = 10):
    """断言资源已从后端删除，支持轮询检查。

    Args:
        logger: 日志记录器（原通过 self.logger 传入）。
        ssh_host: SSH 连接对象。
        name: 要检查的资源名称。
        command: 用于检查的命令模板，默认为 "scli guest list"。
        timeout: 超时时间（秒），默认为 600 秒（10 分钟）。
        interval: 轮询间隔时间（秒），默认为 10 秒。

    Raises:
        pytest.skip: 当 SSH 连接未配置时。
        pytest.fail: 当资源在超时时间内未被删除时。
    """
    if not ssh_host:
        pytest.skip("SSH host is not configured, skipping backend assertion.")
        return

    end_time = time.time() + timeout
    if command.strip() == "scli guest list":
        check_command = f"scli guest list --name '{name}' | grep -F '{name}'"
    else:
        check_command = f"{command} | grep {name}"
    logger.info(f"开始轮询检查后端资源 '{name}' 是否已删除...")

    while time.time() < end_time:
        result = ssh_host.run(check_command)
        if result == "":
            logger.info(f"后端资源 '{name}' 已成功删除。")
            return

        logger.debug(f"资源 '{name}' 仍然存在于后端，将在 {interval} 秒后重试...")
        time.sleep(interval)

    # 超时后，最后检查一次并失败
    final_result = ssh_host.run(check_command)
    if final_result == "":
        logger.info(f"后端资源 '{name}' 在最后一次检查时已删除。")
    else:
        pytest.fail(f"超时错误：资源 '{name}' 在 {timeout} 秒内未能从后端删除。")
