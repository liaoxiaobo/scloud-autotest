import re

class CceStorageMixin:
    """存储管理：存储类型 + 存储卷。"""

    def storage_class_create(self, name, volume_type="xbd-type", fstype="ext4", encrypt=False, access_mode="ReadWriteOnce"):
        """创建云硬盘存储类型。

        Args:
            name: 存储类型名称
            volume_type: 云硬盘类型，默认"xbd-type"
            fstype: 分区格式，默认"ext4"
            encrypt: 是否加密，默认False
            access_mode: 访问模式，默认"ReadWriteOnce"
        """
        self.page.locator("#storage-class").get_by_text("新建").click()
        dialog = self.page.locator(".el-dialog__wrapper:visible .el-dialog").filter(has_text="新建").first
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="存储类型名称").locator("input").fill(name)
        dialog.get_by_role("radio", name=re.compile(r"云硬盘|EVS")).click()
        dialog.locator(".el-form-item").filter(has_text="云硬盘类型").locator(".el-select").click()
        self._select_option(volume_type, exact=False)
        dialog.get_by_role("radio", name=fstype).click()
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def storage_class_delete(self, name):
        """删除指定名称的存储类型。

        Args:
            name: 存储类型名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def storage_class_batch_delete(self, names):
        """批量删除存储类型。

        Args:
            names: 存储类型名称列表
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def storage_volume_create(self, name, capacity, storage_class, access_mode="ReadWriteOnce"):
        """创建存储卷。

        Args:
            name: 存储卷名称
            capacity: 存储容量（Gi）
            storage_class: 存储类型名称
            access_mode: 访问模式，默认"ReadWriteOnce"
        """
        self.btn_create.click()
        dialog = self.page.locator(".el-dialog__wrapper:visible .el-dialog").filter(has_text="添加存储卷").first
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="名称").locator("input").first.fill(name)
        dialog.locator(".el-form-item").filter(has_text="存储类型").locator(".el-select").click()
        self._select_option(storage_class, exact=False)
        # 等待存储类型下拉关闭，避免与后续访问模式下拉混淆
        self.page.wait_for_timeout(1000)
        dialog.locator(".el-form-item").filter(has_text="存储容量").locator("input").first.fill(str(capacity))
        dialog.locator(".el-form-item").filter(has_text="访问模式").locator(".el-select").click()
        access_mode_text = {
            "ReadWriteOnce": "只允许单节点读写访问",
            "ReadOnlyMany": "允许多个节点只读访问",
            "ReadWriteMany": "允许多个节点读写访问"
        }.get(access_mode, "只允许单节点读写访问")
        # 使用 page.get_by_text 直接定位选项，限定在下拉菜单范围内避免strict mode
        dropdown_item = self.page.locator(".el-select-dropdown:visible").get_by_text(access_mode_text, exact=True).first
        dropdown_item.scroll_into_view_if_needed()
        dropdown_item.click()
        self.page.wait_for_timeout(800)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(200)
        dialog.get_by_text("立即创建").click()
        self.wait_for_page_ready()

    def storage_volume_expand(self, name, new_capacity):
        """扩容存储卷。

        Args:
            name: 存储卷名称
            new_capacity: 扩容后的容量（Gi）
        """
        self.click_action(name, "扩容")
        dialog = self.page.locator(".el-dialog").filter(has_text="扩容")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="存储容量").locator("input").fill(str(new_capacity))
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def storage_volume_delete(self, name):
        """删除指定名称的存储卷。

        Args:
            name: 存储卷名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def storage_volume_batch_delete(self, names):
        """批量删除存储卷。

        Args:
            names: 存储卷名称列表
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()
