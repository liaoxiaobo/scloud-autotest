from sugon_web.common.base import BasePage, submenu


class RecyclePage(BasePage):
    """云硬盘回收站页面对象。"""

    @submenu("回收站")
    def evs_delete(self, names, secure=False):
        """删除回收站中的云硬盘资源，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            if secure:
                self.click_action(names, "安全删除")
            else:
                self.click_action(names, "删除")

        self.dialog_confirm.click()

    @submenu("回收站")
    def evs_restore(self, volume_name):
        """从回收站恢复云硬盘。"""
        self.click_action(volume_name, "恢复")
        self.dialog_confirm.click()