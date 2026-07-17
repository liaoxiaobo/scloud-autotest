from sugon_web.pages.compute import EcsPage
from sugon_web.pages.compute.ecs import EcsCreateRequest
from sugon_web.utils.logger import allure_step_log


def _build_vm_fixture_names(base_name: str, count: int) -> list[str]:
    """根据创建数量返回虚机名称列表。"""
    if count < 1:
        raise ValueError(f"'count' must be >= 1, got {count!r}")
    if count == 1:
        return [base_name]
    return [f"{base_name}-{index}" for index in range(1, count+1)]


def _create_vm_resources(
    ecs_page: EcsPage,
    create_request: EcsCreateRequest,
    vm_names: list[str],
) -> None:
    """创建指定数量的虚机并等待状态可用。

    入参 `create_request` 必须已经是标准 EcsCreateRequest。
    这里不再关心参数来自默认值、参数化传参还是依赖 fixture 注入。
    """
    with allure_step_log("创建指定数量的虚机"):
        ecs_page.goto_service("弹性云服务器")
        ecs_page.ecs_create(**create_request)
        ecs_page.assert_popup_success("创建实例命令下发成功")
        ecs_page.assert_status(vm_names)
