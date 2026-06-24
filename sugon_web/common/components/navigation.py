import re
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

        # 兼容 8.0.6.0: URL 结构从 /#{service} 变为 /{service}/#/...
        # 如 service_path=/#/vpc 对应实际 URL /vpc/#/vpc-overview
        if target_path == "/" and target_hash:
            service_from_hash = target_hash.lstrip("#")
            if current_path.lstrip("/") == service_from_hash:
                return True

        if current_path != target_path:
            return False
        # 若服务路径包含 hash，则要求当前 hash 也以该前缀开头
        if target_hash and not current_hash.startswith(target_hash):
            return False
        return True

    def _goto_service_by_path(self, service: str, service_path: str, force: bool = False) -> bool:
        """通过服务入口路径直达指定服务。"""
        try:
            if not force and self._is_current_service_path(service_path):
                self.wait_for_page_ready()
                self.logger.info(f"当前已在目标服务下，复用现有页面: {service} -> {self.page.url}")
                return True

            base_url = Config.get("base_url").rstrip("/")
            target_url = f"{base_url}{service_path}"
            self.page.goto(target_url)
            self.wait_for_page_ready()

            # 等待前端路由完成跳转（URL 稳定），慢环境兼容
            prev_url = ""
            for _ in range(60):
                current_url = self.page.url
                if current_url == prev_url:
                    break
                prev_url = current_url
                self.page.wait_for_timeout(1000)

            if not self._is_current_service_path(service_path):
                raise AssertionError(
                    f"URL 直达服务失败: current={self.page.url}, expected_service_path={service_path}"
                )

            self.logger.info(f"通过 URL 直达服务成功: {service} -> {target_url}")
            return True
        except Exception as e:
            self.logger.error(f"通过 URL 直达服务 {service} 失败: {e}")
            raise AssertionError(f"通过 URL 直达服务 {service} 失败: {e}") from e

    def goto_service(self, service: str, force: bool = False):
        """导航到指定服务，通过服务入口路径直达。

        导航完成后会根据当前角色配置的 project 自动切换顶部项目上下文，
        确保普通用户/部门管理员进入服务页面后处于正确项目下。

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
            result = self._goto_service_by_path(service, service_path, force=force)
            self._ensure_project_context()
            return result
        except Exception as e:
            self.logger.error(f"导航到服务 {service} 失败: {e}")
            raise AssertionError(f"导航到服务 {service} 失败: {e}") from e

    def _ensure_project_context(self) -> None:
        """进入服务页面后，根据当前角色配置自动切换顶部项目。

        仅当角色配置中包含 project 且页面存在项目选择器时执行；
        失败时记录 warning 但不阻塞后续测试。
        """
        user_role = Config.get("user_role", "admin")
        users = Config.get("users", {})
        role_cfg = users.get(user_role, {})
        project_name = role_cfg.get("project", "")

        if not project_name:
            self.logger.debug(f"角色 '{user_role}' 未配置 project，跳过项目上下文检查")
            return

        # 等待项目选择器出现，超时则视为页面无该元素
        top_project_btn = self.page.locator(".project_btn")
        try:
            expect(top_project_btn.first).to_be_visible(timeout=3000)
        except (TimeoutError, AssertionError):
            self.logger.debug("当前页面无顶部项目选择器，跳过项目上下文切换")
            return

        try:
            self.logger.info(f"服务页面自动切换项目: role={user_role}, project={project_name}")
            self.select_top_project(project_name)
        except Exception as e:
            self.logger.warning(f"服务页面自动切换项目 '{project_name}' 失败（非关键步骤）: {e}")

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

        # 兼容 8.0.6.0：等待左侧菜单出现，慢环境轮询检测
        menu_found = False
        for _ in range(30):
            if self.locator("#cloud-menu-left").count() > 0:
                menu_found = True
                break
            self.page.wait_for_timeout(500)

        if not menu_found:
            # 如果当前在服务路径下但没有左侧菜单，说明在服务子页面（如 region-management-list）
            # 重新导航到服务根页面以加载左侧菜单
            if service_name and service_path and self._is_current_service_path(service_path):
                base_url = Config.get("base_url").rstrip("/")
                self.page.goto(f"{base_url}{service_path}")
                self.wait_for_page_ready()
                # 重新检查左侧菜单
                for _ in range(30):
                    if self.locator("#cloud-menu-left").count() > 0:
                        menu_found = True
                        break
                    self.page.wait_for_timeout(500)

            if not menu_found:
                self.logger.info(f"左侧菜单不存在，跳过子菜单导航: {submenu}")
                self.wait_for_page_ready()
                # 等待前端路由完成跳转（URL 稳定），慢环境兼容
                prev_url = ""
                for _ in range(60):
                    current_url = self.page.url
                    if current_url == prev_url:
                        break
                    prev_url = current_url
                    self.page.wait_for_timeout(1000)
                return

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

    def select_top_project(self, project_name: str, timeout: int = 10000) -> None:
        """通过顶部导航栏搜索并切换项目。

        适用于普通用户/部门管理员登录后，页面顶部存在项目选择器的场景。
        打开项目选择弹窗 -> 按项目名称搜索 -> 选择目标项目 -> 点击确定。

        Args:
            project_name: 目标项目名称，如 "公共测试"。
            timeout: 等待元素可见的超时时间（毫秒），默认 10 秒。

        Raises:
            AssertionError: 项目选择器未出现、搜索失败或目标项目不可选时抛出。
        """
        if not project_name:
            raise AssertionError("project_name 不能为空")

        project_btn = self.page.locator(".project_btn").first
        expect(project_btn).to_be_visible(timeout=timeout)

        # 若当前已选中目标项目，直接跳过，避免重复弹窗操作
        current_text = project_btn.inner_text().strip()
        if project_name in current_text and "请选择" not in current_text:
            self.logger.info(f"顶部导航栏已处于项目 '{project_name}'，无需切换")
            return

        self.logger.info(f"顶部导航栏切换项目: {project_name}")

        # 重试点击项目按钮，确保弹窗打开（兼容首页异步渲染/事件绑定延迟）
        dialog = self.page.locator(".project_dialog").first
        for attempt in range(3):
            try:
                project_btn.click(timeout=5000)
                expect(dialog).to_be_visible(timeout=timeout)
                break
            except Exception as e:
                self.logger.warning(f"打开项目选择弹窗失败（尝试 {attempt + 1}/3）: {e}")
                if attempt == 2:
                    raise AssertionError(f"无法打开顶部项目选择弹窗: {e}")
                self.page.wait_for_timeout(1000)
                # 重新定位按钮，避免 stale element
                project_btn = self.page.locator(".project_btn").first

        # 等待项目列表渲染完成
        self.page.wait_for_timeout(1000)

        # 选择目标项目（优先点击所在行的 radio，兼容行点击）
        project_item = dialog.get_by_text(project_name, exact=False)
        expect(project_item).to_be_visible(timeout=timeout)
        try:
            project_item.locator("xpath=..").locator(".el-radio").first.click(timeout=3000)
        except Exception:
            project_item.click()

        # 点击确定
        confirm_btn = dialog.locator(".cloud-button-btn.cl-btn-primary").first
        expect(confirm_btn).to_be_visible(timeout=timeout)
        confirm_btn.click()

        self.wait_for_page_ready()

        # 验证切换成功：顶部项目按钮应显示目标项目名称
        expect(project_btn).to_contain_text(project_name, timeout=timeout)
        self.logger.info(f"顶部导航栏项目切换成功: {project_name}")
