from functools import wraps
from typing import Callable
from urllib.parse import urlparse

from playwright.sync_api import expect

from sugon_web.config.config import Config
from sugon_web.config.constants import SERVICE_PATH_MAP


def submenu(name: str) -> Callable:
    """装饰器：确保进入当前服务下的指定子菜单页面。"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            service_name = getattr(self, "service_name", None)
            if service_name:
                self.goto_service(service_name)
            self.goto_submenu(name)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class NavigationMixin:
    """页面导航 Mixin。

    提供服务页面导航、子菜单切换能力。
    设计为与 Playwright 组合使用，依赖 self.page 和 self.logger。
    """

    @staticmethod
    def _normalize_route_parts(route: str) -> tuple[str, str]:
        """将 route 统一为 path 和 hash，便于做精确比较。"""
        parsed = urlparse(route)
        path = parsed.path.rstrip("/") or "/"
        hash_value = f"#{parsed.fragment}" if parsed.fragment else ""
        return path, hash_value

    def _is_current_service_path(self, service_path: str) -> bool:
        """判断当前页面是否已位于目标服务下的任意页面。"""
        current_path, current_hash = self._normalize_route_parts(self.page.url)
        target_path, target_hash = self._normalize_route_parts(service_path)
        if current_path != target_path:
            return False
        # 若服务路径包含 hash，则要求当前 hash 也以该前缀开头
        if target_hash and not current_hash.startswith(target_hash):
            return False
        return True

    def _goto_service_by_path(self, service: str, service_path: str) -> bool:
        """通过服务入口路径直达指定服务。"""
        try:
            if self._is_current_service_path(service_path):
                self.wait_for_page_ready()
                self.logger.info(f"当前已在目标服务下，复用现有页面: {service} -> {self.page.url}")
                return True

            base_url = Config.get("base_url").rstrip("/")
            target_url = f"{base_url}{service_path}"
            self.page.goto(target_url)
            self.wait_for_page_ready()

            if not self._is_current_service_path(service_path):
                raise AssertionError(
                    f"URL 直达服务失败: current={self.page.url}, expected_service_path={service_path}"
                )

            self.logger.info(f"通过 URL 直达服务成功: {service} -> {target_url}")
            return True
        except Exception as e:
            self.logger.error(f"通过 URL 直达服务 {service} 失败: {e}")
            raise AssertionError(f"通过 URL 直达服务 {service} 失败: {e}") from e

    def goto_service(self, service: str):
        """导航到指定服务，通过服务入口路径直达。

        Args:
            service: 服务名称，如 '云容器引擎'、'云硬盘'、'物理服务器' 等

        Raises:
            AssertionError: 未知服务或导航失败
        """
        if service not in SERVICE_PATH_MAP:
            self.logger.error(f"未知的服务: {service}，请检查服务名称或更新导航映射表")
            raise AssertionError(f"未知的服务: {service}")

        service_path = SERVICE_PATH_MAP.get(service)
        try:
            return self._goto_service_by_path(service, service_path)
        except Exception as e:
            self.logger.error(f"导航到服务 {service} 失败: {e}")
            raise AssertionError(f"导航到服务 {service} 失败: {e}") from e

    def goto_submenu(self, submenu: str) -> None:
        """切换当前服务页面的子菜单。

        若当前不在对应服务下（通过 service_name 和 SERVICE_PATH_MAP 判断），
        会自动调用 goto_service() 先回到服务根页面，再切换子菜单。

        注意：子菜单未找到时，Playwright 底层会抛出 TimeoutError。

        Args:
            submenu: 子菜单名称，如 "概览"、"云硬盘"、"回收站"、
                     "快照"、"弹性云服务器"、"虚拟私有云"
        """
        service_name = getattr(self, "service_name", None)
        service_path = SERVICE_PATH_MAP.get(service_name) if service_name else None
        if service_name and service_path and not self._is_current_service_path(service_path):
            self.goto_service(service_name)

        expect(self.locator("#cloud-menu-left")).to_be_visible(timeout=15000)
        menu_left = self.locator("#cloud-menu-left")
        parent_nodes = menu_left.locator(".one-tree-parent-node")
        count = parent_nodes.count()

        for i in range(count):
            parent = parent_nodes.nth(i)
            is_expanded = parent.evaluate("el => el.classList.contains('one-tree-expand')")
            if not is_expanded:
                parent.click()

        self.locator("#cloud-menu-left").get_by_text(submenu, exact=True).click()
        self.page.wait_for_timeout(1000)
        self.wait_for_page_ready()
        self.logger.info(f"成功导航到子菜单: {submenu}")
