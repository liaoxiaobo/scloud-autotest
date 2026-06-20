from sugon_web.pages.compute import EcsPage
from sugon_web.utils.logger import allure_step_log, logger


def _cleanup_vm_resources(ecs_page: EcsPage, vm_names: list[str]) -> None:
    """清理 vm fixture 创建的虚机。"""
    if not vm_names:
        return
    with allure_step_log(f"清理虚机资源"):
        ecs_page.goto_service("弹性云服务器")
        ecs_page.goto_submenu("弹性云服务器")
        # 过滤掉已经被删除的虚机，避免重复删除报错
        existing_names = []
        for name in vm_names:
            try:
                ecs_page.search(name)
                ecs_page.get_row_by_name(name)
                existing_names.append(name)
            except Exception:
                logger.info(f"虚机 {name} 已不存在，跳过清理")
                continue
        if not existing_names:
            logger.info("所有虚机已清理，无需操作")
            return
        ecs_page.btn_reset.click()
        ecs_page.ecs_remove(existing_names)
        ecs_page.ecs_delete(existing_names)
        ecs_page.assert_deleted(existing_names, timeout=600)
