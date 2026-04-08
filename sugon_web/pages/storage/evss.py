import re
from sugon_web.common.base import BasePage, submenu


class EvssPage(BasePage):
    """云硬盘快照、快照策略、快照任务页面对象。"""

    @submenu("云硬盘")
    def evss_create(self, volume_name, snapshot_name, desc):
        """给指定云硬盘添加快照。"""
        self.click_action(volume_name, "添加快照")

        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(snapshot_name)
        desc_input = dialog.locator("textarea")
        desc_input.fill(desc)

        self.dialog_confirm.click()

    @submenu("快照")
    def evs_create_from_snapshot(self, snapshot_name, volume_name, desc=""):
        """从快照创建云硬盘。"""
        self.click_action(snapshot_name, "创建云硬盘")

        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(volume_name)

        self.locator("textarea").fill(desc)
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照")
    def evss_delete(self, names):
        """删除云硬盘快照资源，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照")
    def evss_edit(self, name, new_name, new_desc):
        """修改指定云硬盘快照的名称和描述。"""
        self.click_action(name, "修改")

        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        desc_input = dialog.locator("textarea")

        name_input.fill(new_name)
        desc_input.fill(new_desc)

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照策略")
    def evss_policy_create(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1):
        """创建快照策略。"""
        self.btn_create.click()

        dialog = self.get_by_label("新建策略")
        dialog.get_by_role("textbox").fill(name)

        if enabled:
            self.get_by_role("switch").locator("span").click()

        if hours:
            for hour in hours:
                dialog.get_by_text(f"{hour:02d}:00", exact=True).click()

        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照策略")
    def evss_policy_delete(self, names):
        """删除快照策略，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照策略")
    def evss_policy_edit(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1):
        """修改快照策略。"""
        self.click_action(name, "修改")

        self.get_by_label("修改策略").get_by_role("textbox").nth(1).fill(name)

        if enabled:
            self.get_by_role("switch").locator("span").click()

        if hours:
            for hour in hours:
                self.get_by_text(f"{hour:02d}:00", exact=True).last.click()

        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照任务")
    def evss_task_set_auto_snapshot(self, volume_name, enable=True):
        """设置自动快照。"""
        if enable:
            self.click_action(volume_name, "开启自动快照")
        else:
            self.click_action(volume_name, "禁用自动快照")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("快照任务")
    def evss_task_delete(self, names):
        """删除云硬盘的快照任务，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()
