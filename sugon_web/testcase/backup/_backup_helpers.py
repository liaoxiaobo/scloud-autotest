from __future__ import annotations

from typing import Any, Dict, List

from sugon_web.pages.backup import BackUpPage
from sugon_web.utils.logger import allure_step_log


TaskInfo = Dict[str, Any]


def _execute_full_backup_and_collect_data(backup_page: BackUpPage, backup_task: TaskInfo) -> TaskInfo:
    """执行一次全量备份，并返回恢复场景所需的数据。

    这是备份域的场景 helper，不属于 fixture 生命周期管理逻辑，因此放在
    ``_backup_helpers.py`` 中，而不是 ``conftest.py``。
    """
    task_name = backup_task.get("task_name")
    source_vm = backup_task.get("server_names")
    source_mfip = backup_task.get("source_mfip")
    original_md5_dict = backup_task.get("source_md5")
    original_arch = backup_task.get("source_arch")
    backup_data: List[Any] = []

    with allure_step_log("前置步骤: 执行全量备份"):
        backup_page.goto_service("备份")
        backup_page.exec_backup(task_name, "执行全量")
        backup_page.assert_popup_success("备份任务执行成功")
        backup_page.assert_status(task_name, "已启动", timeout=600)
        backup_data.extend(backup_page.get_backup_data(source_vm))

    return {
        "task_name": task_name,
        "server_names": source_vm,
        "source_mfip": source_mfip,
        "source_md5": original_md5_dict,
        "backup_data": backup_data,
        "original_arch": original_arch,
    }
