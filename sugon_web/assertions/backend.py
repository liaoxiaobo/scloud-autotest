"""后端断言模块 - develop 分支版本（用于冲突验证）。"""
import time

import pytest


def assert_backend_created(ssh_host, name: str, timeout: int = 300):
    """简化版后端创建断言（develop 分支实现）。"""
    if not ssh_host:
        pytest.skip("SSH not configured")
        return

    end_time = time.time() + timeout
    cmd = f"scli guest list --name '{name}' | grep '{name}'"

    while time.time() < end_time:
        result = ssh_host.run(cmd)
        if result:
            return True
        time.sleep(5)

    pytest.fail(f"Resource '{name}' not created in {timeout}s")


def assert_backend_deleted(ssh_host, name: str, timeout: int = 300):
    """简化版后端删除断言（develop 分支实现）。"""
    if not ssh_host:
        pytest.skip("SSH not configured")
        return

    end_time = time.time() + timeout
    cmd = f"scli guest list --name '{name}' | grep '{name}'"

    while time.time() < end_time:
        result = ssh_host.run(cmd)
        if not result:
            return True
        time.sleep(5)

    pytest.fail(f"Resource '{name}' not deleted in {timeout}s")
