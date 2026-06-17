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

@pytest.fixture(scope="class")
def affinity(browser_context, config, request):
    """创建并返回亲和组名称，测试结束后自动清理。

    支持与 vm fixture 联动：当测试同时声明 affinity 和 vm fixture，
    vm 会自动将 affinity 注入到 advanced.affinity 中。

    注意：本 fixture 自行创建页面实例，不依赖 function-scoped 的 ecs_page
    fixture，因此可设为 class scope 与 vm fixture 配合。

    Args:
        browser_context: Playwright 浏览器上下文。
        config: 测试配置对象。
        request: pytest 请求对象，用于获取参数化配置。

    request.param:
        dict: 配置字典，可选字段：
            - policy: 亲和组策略，"亲和" 或 "反亲和"，默认 "亲和"
            - name: 亲和组名称，默认使用 random_data() 生成

    Yields:
        str: 创建的亲和组名称。
    """
    from sugon_web.utils.data import random_data

    page = _create_logged_in_page(browser_context, config)
    ecs_page = EcsPage(page)

    params = getattr(request, "param", {})
    policy = params.get("policy", "亲和")
    name = params.get("name", f"{random_data()}-{policy}")

    with allure_step_log(f"创建亲和组: {name}, 策略: {policy}"):
        ecs_page.goto_service("弹性云服务器")
        ecs_page.ecs_create_affinity_group(name, policy=policy)
        ecs_page.assert_popup_success("执行成功")

    yield name

    with allure_step_log(f"清理亲和组: {name}"):
        try:
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("亲和组")
            ecs_page.ecs_delete_affinity_group(name)
            ecs_page.assert_deleted(name)
        except Exception as e:
            logger.warning(f"清理亲和组 {name} 时出错: {e}")
        finally:
            page.close()
