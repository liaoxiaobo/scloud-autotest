"""APT 实例创建与清理的 helper 函数。

按照 fixture_spec.md 规范：helper 负责组装创建/删除的完整流程，
封装多步 Page Object 调用，不包含 yield 和 fixture 依赖注入。
"""
import time
from pathlib import Path
from typing import Any

from sugon_web.utils.logger import logger
from sugon_web.utils.data import random_data


# APT 为单项目单实例资源，跨 xdist worker 需要互斥创建
_APT_LOCK_DIR = Path(__file__).resolve().parents[3] / ".apt_project_lock"
_APT_LOCK_MAX_AGE = 3600  # 锁最长持有时间，超过视为死锁


class AptProjectLock:
    """基于原子目录创建的跨进程项目级互斥锁。

    用于保证同一时刻只有一个 worker/测试在默认项目下创建/持有 APT 实例，
    避免"一个项目只能创建一台 APT"导致的并行冲突。
    """

    def __init__(self, lock_dir: Path | str = None, max_age: int = _APT_LOCK_MAX_AGE):
        self.lock_dir = Path(lock_dir or _APT_LOCK_DIR).resolve()
        self.max_age = max_age

    def _owner_file(self) -> Path:
        return self.lock_dir / "owner.txt"

    def acquire(self, owner: str = "", timeout: int = 3600, poll: float = 5.0) -> None:
        """获取 APT 项目锁，阻塞直到成功或超时。

        Args:
            owner: 锁持有者标识，用于排查。
            timeout: 最大等待时间（秒），默认 3600。
            poll: 轮询间隔（秒）。
        """
        self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()
        while True:
            try:
                self.lock_dir.mkdir(exist_ok=False)
                self._owner_file().write_text(
                    f"{owner}\n{time.time()}", encoding="utf-8"
                )
                logger.info(f"APT 项目锁已获取: {owner}")
                return
            except FileExistsError:
                # 检查是否为死锁
                try:
                    content = self._owner_file().read_text(encoding="utf-8").splitlines()
                    ts = float(content[1]) if len(content) > 1 else start
                    stale_owner = content[0] if content else "unknown"
                except Exception:
                    ts = start
                    stale_owner = "unknown"
                if time.time() - ts > self.max_age:
                    logger.warning(
                        f"APT 项目锁疑似死锁（持有者={stale_owner}），强制清理后重试"
                    )
                    self.release()
                    continue
                logger.debug(
                    f"APT 项目锁已被占用（持有者={stale_owner}），{poll}s 后重试..."
                )
                time.sleep(poll)
            if time.time() - start > timeout:
                raise TimeoutError(f"获取 APT 项目锁超时: {owner}")

    def release(self) -> None:
        """释放 APT 项目锁。"""
        try:
            self._owner_file().unlink(missing_ok=True)
            self.lock_dir.rmdir()
            logger.info("APT 项目锁已释放")
        except Exception as e:
            logger.debug(f"APT 项目锁释放时忽略异常: {e}")


def create_apt_instance(page, apt_page, name: str) -> dict[str, Any]:
    """创建 APT 实例并完成状态验证（最多3次重试）。

    Args:
        page: Playwright 页面对象。
        apt_page: APT 页面对象。
        name: 实例名称。

    Returns:
        dict: 包含 name 及行数据的完整信息。
    """
    for attempt in range(1, 4):
        try:
            actual_name = name
            if attempt > 1:
                actual_name = random_data().replace("autotest-", "autotest-apt-")
            logger.info(f"第 {attempt} 次尝试创建 APT 实例: {actual_name}")
            apt_page.apt_create(name=actual_name)
            apt_page.assert_apt_status(actual_name, service_status="运行", vm_status="运行", timeout=1200)
            name = actual_name
            break
        except Exception as e:
            if "创建失败" in str(e) and attempt < 3:
                logger.warning(f"APT 实例创建失败，将重新创建 (第{attempt}次): {e}")
                continue
            raise

    apt_page.goto_list_page()
    row_data = apt_page.get_row_data(name)
    return {"name": name, "row_data": row_data}


def delete_apt_instance(page, apt_page, name: str) -> None:
    """删除 APT 实例并确认已从列表消失。

    Args:
        page: Playwright 页面对象。
        apt_page: APT 页面对象。
        name: 要删除的实例名称。
    """
    apt_page.goto_list_page()
    apt_page.apt_delete(name)
    apt_page.assert_deleted(name, timeout=300, refresh=True)
    logger.info(f"APT 实例 {name} 已删除")
