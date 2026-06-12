"""对象存储回源测试辅助函数。

纯函数，无 yield，无 fixture 依赖。
用于封装回源测试中跨页面的访问与诊断流程。
"""
import time

from sugon_web.utils.logger import logger


def _goto_handle_download(page, url, wait_until="networkidle"):
    """执行 page.goto 并处理下载触发的 ERR_ABORTED 异常。

    Playwright 在触发文件下载时会抛出 ERR_ABORTED 异常，
    这在对象存储回源测试中是预期行为，视为访问成功。

    Args:
        page: Playwright 页面对象。
        url: 访问 URL。
        wait_until: 等待条件，默认 networkidle。

    Returns:
        int: HTTP 状态码；若触发下载则返回 200。
    """
    try:
        resp = page.goto(url, wait_until=wait_until)
        return resp.status if resp else 0
    except Exception as e:
        if "ERR_ABORTED" in str(e):
            return 200
        raise


def _close_page_silent(page):
    """静默关闭页面，忽略所有异常。"""
    try:
        page.close()
    except Exception:
        pass


def _close_context_silent(context):
    """静默关闭浏览器上下文，忽略所有异常。"""
    try:
        context.close()
    except Exception:
        pass


def _verify_source_public_read(browser, context, url):
    """诊断验证源站公共读权限是否生效。

    分别使用匿名浏览器上下文和当前登录态访问源站 URL，
    返回 (anonymous_status, auth_status)。

    Args:
        browser: Playwright Browser 实例（用于匿名上下文）。
        context: 当前登录态的 BrowserContext 实例。
        url: 源站对象访问 URL。

    Returns:
        tuple: (anonymous_status, auth_status)
    """
    anonymous_status = 0
    try:
        anon_context = browser.new_context()
        anon_page = anon_context.new_page()
        anonymous_status = _goto_handle_download(anon_page, url)
        _close_page_silent(anon_page)
        _close_context_silent(anon_context)
    except Exception as e:
        logger.warning(f"匿名访问验证异常: {e}")

    auth_page = context.new_page()
    auth_status = _goto_handle_download(auth_page, url)
    _close_page_silent(auth_page)

    return anonymous_status, auth_status


def _access_with_retry(browser, url, max_attempts=5, initial_delay=30, retry_delay=15):
    """带重试的访问指定 URL，处理下载触发异常。

    首次等待 initial_delay 秒后访问，失败则间隔 retry_delay 秒重试，
    最多重试 max_attempts 次。

    Args:
        browser: Playwright Browser 实例。
        url: 访问 URL。
        max_attempts: 最大尝试次数，默认 5。
        initial_delay: 首次访问前等待秒数（规则传播时间），默认 30。
        retry_delay: 重试间隔秒数，默认 15。

    Returns:
        tuple: (final_status, redirect_pages)
            - final_status: 最终状态码
            - redirect_pages: 创建的所有页面实例列表（需由调用方关闭）
    """
    time.sleep(initial_delay)
    redirect_pages = []
    final_status = 0

    for attempt in range(max_attempts):
        redirect_page = browser.new_page()
        redirect_pages.append(redirect_page)
        final_status = _goto_handle_download(redirect_page, url)

        if final_status in [200, 204, 206]:
            break

        logger.info(
            f"回源访问尝试 {attempt + 1}/{max_attempts} 状态码: {final_status}，"
            f"等待 {retry_delay} 秒后重试..."
        )
        time.sleep(retry_delay)

    return final_status, redirect_pages
