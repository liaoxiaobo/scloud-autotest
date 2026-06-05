"""pytest 钩子辅助函数。

与 pytest 生命周期（setup/call/teardown）交互的纯工具函数，
用于失败现场保留、报告附加等。
"""

from datetime import datetime
from pathlib import Path

import allure

from sugon_web.utils.logger import logger


def capture_failure_screenshot(page, item, failure_stage):
    """捕获失败截图并添加到 Allure 报告。

    Args:
        page: Playwright 页面对象
        item: pytest 测试项对象
        failure_stage: 失败阶段 (setup/call/teardown)
    """
    try:
        logger.info(f"开始生成失败截图")
        project_root = Path(__file__).resolve().parents[2]
        screenshot_dir = project_root / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"{item.name}_{timestamp}.png"

        page.screenshot(path=str(screenshot_path))
        logger.info(f"截图保存成功: {screenshot_path}")

        failure_info = (
            f"测试失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"测试用例名称: {item.name}\n"
            f"失败阶段: {failure_stage}\n"
            f"当前页面URL: {page.url}\n"
        )
        logger.error(f"测试失败详情:\n{failure_info}")

        with allure.step(f"用例信息收集 -> {failure_stage}阶段"):
            with open(screenshot_path, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"失败截图",
                    attachment_type=allure.attachment_type.PNG
                )
            allure.attach(
                body=failure_info,
                name="失败信息",
                attachment_type=allure.attachment_type.TEXT
            )

        logger.info(f"失败截图已保存并添加到 Allure 报告: {screenshot_path}")

    except Exception as e:
        logger.error(f"截图保存失败: {e}")


def get_page_from_item(item):
    """从测试用例的 fixture 中获取 page 对象。

    Args:
        item: pytest 测试项对象

    Returns:
        Page 对象或 None
    """
    page = item.funcargs.get("page", None)
    if page:
        return page

    for fixture_name, fixture_obj in item.funcargs.items():
        if hasattr(fixture_obj, 'page'):
            page = getattr(fixture_obj, 'page')
            logger.info(f"从 {fixture_name} 中获取到page对象")
            return page

    logger.warning("无法获取page对象")
    return None
