"""
【职责】通过浏览器登录态调用 SDN MFIP 接口，完成浮动 IP 的绑定，供网络相关测试做后端准备或验证。

【层级】Utils 层；被 fixture、测试用例直接实例化调用。

【接口】
- bind_mfip(port_id, mfip_address, project_id="admin-inner-project", description="") -> dict：调用 SDN API 绑定 MFIP。
- bind_mfip_for_vm(vm_data, port_id=None) -> dict：为虚拟机数据绑定 MFIP 并回填 vm_data["mfip"]。
- bind_mfip_with_admin_context(browser, config, port_id, project_id="admin-inner-project", mfip_address="") -> str：创建 admin 上下文完成绑定并返回分配的 MFIP 地址。

【示例】
from sugon_web.common.mfip_helper import MfipHelper

helper = MfipHelper(page)
helper.bind_mfip_for_vm(vm_data={"name": "vm-01", "port_id": "port-xxx"})

【前置依赖】page 必须已完成登录，且 localStorage 中存在 api_header 登录态。
"""

import json

from playwright.sync_api import Page

from sugon_web.common.auth import prepare_page_session
from sugon_web.config.config import Config
from sugon_web.utils.logger import logger


class MfipHelper:
    """封装 MFIP 相关 API 调用。

    通过 Playwright 的 page.request 发起请求，自动复用当前浏览器的登录态。
    Token 从 localStorage.api_header 中提取。
    """

    def __init__(self, page: Page):
        self.page = page

    def _get_auth_token(self) -> str:
        """从 localStorage 获取 Authorization token。

        localStorage.api_header 存储格式:
            {"Authorization": "Bearer eyJhbG..."}
        """
        api_header = self.page.evaluate("() => localStorage.getItem('api_header')")
        if not api_header:
            raise RuntimeError("localStorage 中未找到 api_header，请确认已登录")

        try:
            header_data = json.loads(api_header)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"api_header 内容不是有效 JSON: {api_header}") from exc

        token = header_data.get("Authorization")
        if not token:
            raise RuntimeError("api_header 中未找到 Authorization 字段")

        return token

    def bind_mfip(
        self,
        port_id: str,
        mfip_address: str,
        project_id: str = "admin-inner-project",
        description: str = "",
    ) -> dict:
        """通过 API 绑定 MFIP。

        Args:
            port_id: 端口 ID。
            mfip_address: 要绑定的 MFIP 地址。传空字符串由系统自动分配。
            project_id: 项目 ID，默认 admin-inner-project。
            description: 描述信息。

        Returns:
            接口响应的 JSON 数据。

        Raises:
            RuntimeError: 请求失败或响应异常。
        """
        base_url = Config.get("base_url")
        url = f"{base_url}/api/sugoncloud-ops-api/api/ops/vpc/SDN/mfip/add"

        token = self._get_auth_token()

        payload = {
            "port_id": port_id,
            "mfip_address": mfip_address,
            "project_id": project_id,
            "description": description,
        }

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }

        resp = self.page.request.post(url, data=json.dumps(payload), headers=headers)

        if not resp.ok:
            raise RuntimeError(
                f"绑定 MFIP 失败: status={resp.status}, body={resp.text()}"
            )

        result = resp.json()
        if not result.get("success", True):
            raise RuntimeError(
                f"绑定 MFIP 失败: {result.get('status_mes', result)}"
            )

        logger.info(
            f"绑定 MFIP 成功: port_id={port_id}, mfip_address={mfip_address}, "
            f"response={result}"
        )
        return result

    def bind_mfip_for_vm(
        self,
        vm_data: dict,
        port_id: str | None = None,
    ) -> dict:
        """为虚机绑定 MFIP。

        Args:
            vm_data: 需包含 ``id`` / ``name`` / ``ip`` / ``port_id`` / ``project_id`` 。
            port_id: 网卡端口 ID，显式传入时优先使用。

        Returns:
            接口响应的 JSON 数据，包含系统分配的 ``mfip_address`` 。

        Raises:
            ValueError: ``port_id`` 无法获取。
            RuntimeError: API 调用失败。
        """
        resolved_port_id = port_id or vm_data.get("port_id")
        if not resolved_port_id:
            raise ValueError(
                f"VM {vm_data.get('name')} 缺少 port_id，"
                "请在调用前先通过 SSH 或其他方式获取。"
            )

        project_id = vm_data.get("project_id") or "admin-inner-project"
        mfip_address = vm_data.get("mfip", "")

        result = self.bind_mfip(
            port_id=resolved_port_id,
            mfip_address=mfip_address,
            project_id=project_id,
            description=f"Auto-bind for VM {vm_data.get('name', '')}",
        )

        assigned_mfip = (
            result.get("content", {}).get("mfip_address")
            or result.get("mfip_address")
        )
        if assigned_mfip:
            vm_data["mfip"] = assigned_mfip

        return result

    @staticmethod
    def bind_mfip_with_admin_context(
        admin_browser_context,
        config,
        port_id: str,
        project_id: str = "admin-inner-project",
        mfip_address: str = "",
    ) -> str:
        """使用 admin browser context 绑定 MFIP，返回分配的 MFIP 地址。

        调用方需先自行准备好 ``port_id`` 和 ``project_id``（例如通过 SSH
        ``guest_show`` 查询）。本方法只负责：从 admin_browser_context 创建
        admin page → 调绑定 API → 返回 ``mfip_address``。

        Args:
            admin_browser_context: 已登录 admin 的 Playwright BrowserContext 实例。
            config: 配置对象，需提供 ``base_url`` 及 admin 凭据。
            port_id: 网卡端口 ID。
            project_id: 项目 ID，默认 admin-inner-project。
            mfip_address: 要绑定的 MFIP 地址，空字符串由系统自动分配。

        Returns:
            系统分配的 MFIP 地址。

        Raises:
            RuntimeError: API 调用失败或响应中未返回 ``mfip_address``。
        """
        admin_cfg = config.get("users", {}).get("admin", {})
        admin_username = admin_cfg.get("username") or config.get("username", "admin")
        admin_password = admin_cfg.get("password") or config.get("password", "keystone_sugon")

        admin_page = admin_browser_context.new_page()
        try:
            prepare_page_session(
                admin_page,
                config,
                username=admin_username,
                password=admin_password,
            )
            result = MfipHelper(admin_page).bind_mfip(
                port_id=port_id,
                mfip_address=mfip_address,
                project_id=project_id,
            )
        finally:
            admin_page.close()

        assigned_mfip = (
            result.get("content", {}).get("mfip_address")
            or result.get("mfip_address")
        )
        if not assigned_mfip:
            raise RuntimeError(f"MFIP 绑定成功但响应中未返回 mfip_address: {result}")
        return assigned_mfip
