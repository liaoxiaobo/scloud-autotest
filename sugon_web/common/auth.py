"""
【职责】为 page 创建或恢复登录态，提供独立的浏览器登录能力。

【层级】Utils 层；被 conftest.py 的 `_create_logged_in_page` 与 `MfipHelper` 调用。

【接口】
- prepare_page_session(page, config, username=None, password=None)：导航到 base_url 并在未登录时完成登录。
- login(page, username, password, max_retries=3)：在登录页执行用户名密码登录并自动重试。

【示例】
from sugon_web.common.auth import prepare_page_session

page = browser_context.new_page()
prepare_page_session(page, config)

【前置依赖】page 需为未导航或处于登录页的 Playwright Page；config 需包含 base_url、username、password。
"""

import re
from typing import Any

from playwright.sync_api import Page

from sugon_web.utils.logger import logger, allure_step_log


def _is_logged_in(page: Page) -> bool:
    """检查 page 当前是否处于已登录状态。"""
    current_url = page.url or ""
    return (
        "/#/index" in current_url
        or "/#/console-page" in current_url
        or "/#" in current_url
    ) and "login" not in current_url


def login(
    page: Page,
    username: str,
    password: str,
    *,
    max_retries: int = 3,
) -> None:
    """在指定 page 上执行登录操作。

    Args:
        page: Playwright Page 实例，当前应处于登录页。
        username: 用户名。
        password: 密码。
        max_retries: 最大重试次数。

    Raises:
        ValueError: 用户名或密码为空。
        RuntimeError: 超过最大重试次数仍未能成功登录。
    """
    if not username or not password:
        raise ValueError("环境配置中缺少用户名或密码")

    with allure_step_log("尝试登录"):
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(f"【登录尝试】第 {attempt}/{max_retries} 次")

            try:
                # 先关闭登录页可能弹出的提示弹窗
                for _ in range(3):
                    try:
                        dialog_btn = page.locator(
                            ".el-message-box__wrapper button, .el-dialog__wrapper button"
                        ).filter(has_text=re.compile(r"确定|知道了|关闭|确认")).first
                        if (
                            dialog_btn.count() > 0
                            and dialog_btn.is_visible(timeout=1000)
                        ):
                            dialog_btn.click()
                            page.wait_for_timeout(500)
                            continue
                    except Exception:
                        pass
                    break

                page.get_by_placeholder("请输入登录账号").fill(username)
                page.get_by_placeholder("请输入登录密码").fill(password)
                page.get_by_text("登 录").click()

                page.wait_for_url(
                    re.compile(r".*#/(index|console-page)$"), timeout=30000
                )
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_load_state("load")
                return

            except Exception as e:
                logger.info(f"第{attempt}次登录未成功: {e}")
                if attempt == max_retries:
                    raise RuntimeError(
                        f"登录失败，已重试 {max_retries} 次，"
                        "请检查账号密码或网络状态"
                    ) from e


def _wait_for_spa_route(page: Page) -> None:
    """等待前端路由稳定到首页或登录页。"""
    try:
        page.wait_for_url(re.compile(r".*#/(index|login|console-page)$"), timeout=10000)
    except Exception:
        logger.debug(
            f"首次访问后未在预期时间内跳转到首页/登录页，"
            f"当前URL: {page.url}"
        )
        if "/#" not in page.url:
            try:
                page.wait_for_url(
                    re.compile(r".*#/(index|login|console-page)$"),
                    timeout=30000,
                )
            except Exception:
                pass


def prepare_page_session(
    page: Page,
    config: Any,
    *,
    username: str | None = None,
    password: str | None = None,
) -> None:
    """在已有 page 上完成导航并确保已登录。

    职责边界：仅负责「导航 → 等待路由稳定 → 条件登录」，
    不涉及弹窗清理、no-permission 恢复、SPA 初始化等待等页面环境准备。
    这些由调用方（如 ``_create_logged_in_page``）按需补充。

    Args:
        page: 已创建的 Playwright Page 实例（尚未导航）。
        config: 配置对象。
        username: 覆盖 config 中的用户名。
        password: 覆盖 config 中的密码。

    Raises:
        RuntimeError: 登录失败。
    """
    base_url = config.get("base_url")
    resolved_username = username or config.get("username")
    resolved_password = password or config.get("password")

    page.goto(base_url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    logger.info(f"页面导航完成，当前URL: {page.url}")

    _wait_for_spa_route(page)
    logger.info(f"页面导航完成，当前URL: {page.url}")

    if not _is_logged_in(page):
        login(page, resolved_username, resolved_password)
        logger.info("登录成功")
