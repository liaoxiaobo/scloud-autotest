import pytest

from sugon_web.conftest import _create_logged_in_page
from sugon_web.pages.compute import EcsPage
from sugon_web.utils.logger import allure_step_log, logger

from ._ecs_helpers import create_labels, delete_labels


@pytest.fixture(scope="class")
def labels(browser_context, config, request):
    """创建并返回指定数量的标签，测试结束后自动清理。"""
    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)
    ecs_page.goto_service("弹性云服务器")

    params = getattr(request, "param", {})
    count = params.get("count", 1)

    with allure_step_log("创建指定数量的标签"):
        label_names = create_labels(ecs_page, count=count)

    yield label_names

    with allure_step_log("清理测试标签"):
        logger.info(f"开始清理标签: {label_names}")
        try:
            delete_labels(ecs_page, label_names)
        except Exception as e:
            logger.warning(f"清理标签时出错: {e}")
        finally:
            page.close()


@pytest.fixture()
def affinity(ecs_page, request):
    """创建并返回指定数量的亲和组场景标签，测试结束后自动清理。"""
    params = getattr(request, "param", {})
    count = params.get("count", 1)
    prefix = params.get("prefix", "label")

    with allure_step_log("创建指定数量的亲和组场景标签"):
        label_names = create_labels(ecs_page, count=count, prefix=prefix, separator="_")

    yield label_names

    with allure_step_log("清理亲和组场景标签"):
        logger.info(f"开始清理亲和组场景标签: {label_names}")
        try:
            delete_labels(ecs_page, label_names)
        except Exception as e:
            logger.warning(f"清理亲和组场景标签时出错: {e}")
