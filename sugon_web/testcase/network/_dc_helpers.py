import time

from sugon_web.utils.logger import allure_step_log, logger


def create_virtual_interface_with_retry(dc_page, **kwargs):
    """创建虚拟接口，若最终状态为错误则删除后重试一次。

    所有 kwargs 原样透传给 dc_page.virtual_interface_create，因此调用方保持与直接创建
    完全一致的参数写法，仅需把 dc_page.virtual_interface_create(...) 替换为本函数。
    """
    name = kwargs["name"]

    with allure_step_log(f"步骤: 创建虚拟接口 {name}"):
        dc_page.virtual_interface_create(**kwargs)
        dc_page.assert_popup_success(timeout=10000)

    status = _wait_virtual_interface_status(dc_page, name, timeout=150)

    if status == "错误":
        with allure_step_log(f"步骤: 虚拟接口 {name} 状态为错误，删除后等待5秒重试"):
            logger.warning(f"虚拟接口 {name} 状态为错误，准备删除后重试")
            dc_page.virtual_interface_delete(name)
            dc_page.assert_deleted(name, timeout=60)
            dc_page.page.wait_for_timeout(5000)

        with allure_step_log(f"步骤: 第2次创建虚拟接口 {name}"):
            dc_page.virtual_interface_create(**kwargs)
            dc_page.assert_popup_success(timeout=10000)

        status = _wait_virtual_interface_status(dc_page, name, timeout=150)

    if status != "运行中":
        raise AssertionError(f"虚拟接口 {name} 最终状态异常: {status}")

    logger.info(f"虚拟接口 {name} 状态正常: {status}")


def _wait_virtual_interface_status(dc_page, name, timeout=150):
    """轮询等待虚拟接口状态变为运行中或错误，返回最终状态。"""
    for _ in range(timeout):
        try:
            row_data = dc_page.get_row_data(name)
            status = row_data.get("状态", "")
            if status in ("运行中", "错误"):
                return status
        except Exception as exc:
            logger.debug(f"轮询虚拟接口 {name} 状态失败: {exc}")
        time.sleep(1)

    # 超时后尝试获取一次当前状态
    try:
        row_data = dc_page.get_row_data(name)
        return row_data.get("状态", "未知")
    except Exception as exc:
        logger.warning(f"超时后获取虚拟接口 {name} 状态失败: {exc}")
        return "未知"
