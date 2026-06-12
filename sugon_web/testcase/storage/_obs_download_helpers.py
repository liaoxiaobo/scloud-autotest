"""对象下载/分享测试辅助函数。

纯函数，无 yield，无 fixture 依赖。
用于封装对象下载/分享测试中 response 监听、URL 捕获、文件下载等跨步骤流程。
"""
import time

from sugon_web.utils.logger import logger


def _wait_for_generated_url(
    page, url_patterns, trigger=None, timeout=30, poll_interval=0.5
):
    """监听 response 事件，等待含 `genUrl` 的下载/分享 URL 响应。

    先注册监听器，再执行可选的 trigger 动作，最后轮询等待结果。

    Args:
        page: Playwright Page 对象。
        url_patterns: 匹配的 URL 子串列表（如 ["objects/url", "objects/share-url"]）。
        trigger: 触发响应的可选回调函数（如下载/分享按钮点击）。
        timeout: 最大等待秒数。
        poll_interval: 轮询间隔秒数。

    Returns:
        str or None: 提取到的 genUrl。
    """
    result = {"url": None}

    def handle_response(response):
        if result["url"]:
            return
        url = response.url
        if any(pattern in url for pattern in url_patterns):
            try:
                data = response.json()
                content = data.get("content") if isinstance(data, dict) else None
                if isinstance(content, dict) and content.get("genUrl"):
                    result["url"] = content["genUrl"]
            except Exception:
                pass

    page.on("response", handle_response)
    try:
        if trigger:
            trigger()
        deadline = time.time() + timeout
        while time.time() < deadline and result["url"] is None:
            time.sleep(poll_interval)
        return result["url"]
    finally:
        pass


def _download_file_via_request(request, url, save_path, timeout=30):
    """使用 Playwright request API 下载文件并保存。

    Args:
        request: Playwright APIRequestContext 对象。
        url: 下载 URL。
        save_path: 文件保存路径。
        timeout: 请求超时秒数。

    Returns:
        bool: 下载并保存成功返回 True，否则 False。
    """
    try:
        response = request.get(url, timeout=timeout * 1000)
        file_content = response.body()
        with open(save_path, "wb") as f:
            f.write(file_content)
        return True
    except Exception as e:
        logger.warning(f"通过 request 下载文件失败: {e}")
        return False


def _capture_opened_urls(page, trigger, timeout=30, poll_interval=0.5):
    """劫持 window.open，执行 trigger，返回捕获的 URL 列表。

    Args:
        page: Playwright Page 对象。
        trigger: 触发 window.open 的回调函数。
        timeout: 最大等待秒数。
        poll_interval: 轮询间隔秒数。

    Returns:
        list: 捕获到的 URL 列表。
    """
    page.evaluate(
        """
        () => {
            window._capturedUrls = [];
            const originalOpen = window.open;
            window.open = function(url, target) {
                if (url) window._capturedUrls.push(url);
                return originalOpen.apply(this, arguments);
            };
            return 'ok';
        }
        """
    )
    trigger()
    deadline = time.time() + timeout
    while time.time() < deadline:
        urls = page.evaluate("() => window._capturedUrls || []")
        if urls:
            return urls
        time.sleep(poll_interval)
    return []
