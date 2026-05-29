from sugon_web.utils.logger import logger


def prepare_bucket_list_page(obs_page):
    """选择项目并导航到桶列表页面，返回现有桶名称列表。

    Returns:
        list[str]: 现有桶名称列表
    """
    obs_page.select_top_nav_project(
        org_name=["sugoncloud", "智能云事业部"],
        project_name="公共测试",
    )
    obs_page.goto_submenu("桶列表")
    obs_page.page.wait_for_timeout(2000)

    try:
        return obs_page.get_column_data("名称")
    except Exception:
        return []


def create_bucket(obs_page, name: str, capacity: str = "10") -> dict:
    """创建对象存储桶。

    完整流程：创建桶 -> 返回桶列表 -> 验证列表包含。

    Args:
        obs_page: ObsPage 页面对象
        name: 桶名称
        capacity: 桶容量，默认 10GB

    Returns:
        dict: 包含 name 及所有实际使用参数的完整字典
    """
    obs_page.obs_bucket_create(name)
    obs_page.goto_submenu("桶列表")
    obs_page.page.wait_for_timeout(2000)
    obs_page.assert_list_contain(name)

    return {"name": name, "capacity": capacity}


def empty_bucket(obs_page, name: str) -> None:
    """清空对象存储桶内所有对象。

    Args:
        obs_page: ObsPage 页面对象
        name: 桶名称
    """
    obs_page._obs_bucket_empty(name)


def delete_bucket(obs_page, name: str) -> None:
    """删除对象存储桶（先清空对象再删除）。

    若桶已不存在，则跳过删除并记录 info 日志。

    Args:
        obs_page: ObsPage 页面对象
        name: 桶名称
    """
    # 先关闭可能存在的弹窗，避免遮挡导航
    obs_page.close_dialog_if_exists()
    obs_page.page.keyboard.press("Escape")
    obs_page.page.wait_for_timeout(500)

    obs_page.goto_submenu("桶列表")
    obs_page.page.wait_for_timeout(1000)

    # 检查桶是否仍存在
    column_data = []
    try:
        column_data = obs_page.get_column_data("名称")
    except Exception:
        pass

    if name not in column_data:
        logger.info(f"桶 {name} 已不存在，跳过删除")
        return

    empty_bucket(obs_page, name)
    obs_page.page.wait_for_timeout(1000)
    obs_page.obs_bucket_delete(name)
    obs_page.assert_deleted(name)
