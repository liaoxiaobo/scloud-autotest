import re
import pytest
from sugon_web.common.base import BasePage, submenu


class EvsPage(BasePage):
    """云硬盘页面对象。"""

    @property
    def _input_name(self):
        """云硬盘名称输入框"""
        return self.locator("div").filter(has_text=re.compile(r"^云硬盘名称$")).get_by_role("textbox")

    @property
    def _input_desc(self):
        """描述输入框"""
        return self.locator("textarea")

    @property
    def _input_size(self):
        """输入云硬盘大小"""
        return self.get_by_label("slider between 1 and").get_by_role("spinbutton")

    def _select_image_source(self):
        """选择云硬盘来源为镜像"""
        self.get_by_text("云硬盘来源").locator("xpath=./following-sibling::div//input").click()
        self.locator("li").filter(has_text=re.compile(r"^镜像$")).click()

    def _select_volume_type(self, name):
        """选择云硬盘类型"""
        self.get_by_placeholder("请选择类型").click()
        self.locator("li").filter(has_text=re.compile(fr"^{name}$")).click()

    def _select_image(self, name):
        """选择镜像"""
        self.locator("div:nth-child(6) > .el-form-item__content > .el-select > .el-input").click()
        self.get_by_text(name, exact=True).click()

    def _select_mode(self, mode):
        """选择云硬盘模式"""
        self.get_by_placeholder("请选择模式").click()
        self.locator("li").filter(has_text=re.compile(fr"^{mode}$")).click()

    def _enable_encryption(self, encryption_key):
        """启用加密并选择密钥。"""
        self.locator("label").filter(has_text="机密存储").locator("span").nth(1).click()
        self.get_by_text("选择密钥").first.click()
        self.get_by_role("radio", name=encryption_key).click()
        self.page.locator("section").get_by_text("确定").first.click()
        self.page.wait_for_timeout(1000)

    def _enable_virtio_scsi(self):
        """启用VirtioSCSI。"""
        scsi_label = self.page.locator("form label").filter(has_text="VirtioSCSI")
        if not scsi_label.get_by_role("checkbox").is_checked():
            scsi_label.click()
            self.logger.info("已启用 VirtioSCSI")
        else:
            self.logger.info("VirtioSCSI 已处于启用状态")

    def _select_host(self, name=None):
        """选择物理机。"""
        self.page.locator("form div").filter(has_text="物理机").get_by_placeholder("请选择").click()
        self.page.wait_for_timeout(3000)

        if name is not None:
            self.get_by_text(name + ",").click()
        else:
            self.page.keyboard.press("ArrowDown")
            self.page.keyboard.press("Enter")

    @submenu("云硬盘")
    def evs_create(
            self,
            name,
            count=1,
            size=30,
            empty=True,
            image_name="",
            volume_type="",
            desc="",
            shared=False,
            encrypted=False,
            encryption_key="",
            host=None,
            scsi=True
    ):
        """创建云硬盘。"""
        unsupported_storages = ["local", "nfs", "usan"]
        if shared and self.stor in unsupported_storages:
            pytest.skip(f"当前存储类型 {self.stor} 不支持创建共享云硬盘")

        if encrypted and shared:
            pytest.skip("加密云硬盘不支持共享模式")

        self.btn_create.click()
        self.wait_for_page_ready()

        self._input_name.fill(name)
        self._input_desc.fill(desc)

        if count != 1:
            self.get_by_label("数量").fill(str(count))

        if not empty:
            self._select_image_source()

        volume_type = volume_type or self.volume_type
        self._select_volume_type(volume_type)

        if self.stor == "local":
            self._select_host(host)

        if not empty:
            image_name = image_name or self.storage_pool
            self._select_image(image_name)

        if encrypted:
            self._enable_encryption(encryption_key)

        if scsi:
            self._enable_virtio_scsi()

        if shared:
            self.locator("label").filter(has_text="共享盘").locator("span").nth(1).click()

        self._input_size.fill(str(size))
        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_remove(self, names):
        """回收云硬盘资源，支持单个和批量操作。"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.get_by_role("button", name="更多操作 ").click()
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_edit(self, name, new_name, new_desc):
        """修改指定云硬盘的名称和描述。"""
        self.click_action(name, "修改")

        dialog = self.get_by_role("dialog")
        dialog.locator('input[type="text"]').fill(new_name)
        dialog.locator("textarea").fill(new_desc)

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_clone(self, source_name, clone_name):
        """克隆指定云硬盘。"""
        self.click_action(source_name, "克隆")

        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(clone_name)

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_expand(self, name, new_size):
        """扩容指定云硬盘。"""
        self.click_action(name, "扩容")

        dialog = self.get_by_label("扩容")
        size_input = dialog.get_by_role("spinbutton")
        size_input.fill(str(new_size))

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_mount(self, volume_name, server_name):
        """挂载云硬盘到指定服务器。"""
        self.click_action(volume_name, "挂载")
        self.get_by_role("row", name=server_name).get_by_role("radio").click()
        self.get_by_label("挂载").get_by_text("挂载").nth(1).click()

    @submenu("云硬盘")
    def evs_unmount(self, volume_name, server_name):
        """从指定服务器卸载云硬盘。"""
        self.click_action(volume_name, "卸载")
        self.get_by_label("卸载").get_by_placeholder("请选择").click()
        self.locator("span").filter(has_text=re.compile(rf"^{server_name}$")).click()
        self.get_by_label("卸载").get_by_text("确定").click()

    @submenu("云硬盘")
    def evs_enable_qos(self, volume_name, read_speed=None, write_speed=None, read_iops=None, write_iops=None):
        """为云硬盘启用QoS限制。"""
        self.click_action(volume_name, "设置QoS")

        if read_speed is not None:
            self.locator("form div").filter(has_text="读取速度 MBpsKBpsBps").get_by_placeholder("空表示未限制").fill(str(read_speed))

        if write_speed is not None:
            self.locator("form div").filter(has_text="写入速度 MBpsKBpsBps").get_by_placeholder("空表示未限制").fill(str(write_speed))

        if read_iops is not None:
            self.locator("div").filter(has_text=re.compile(r"^每秒读次数 次/S$")).get_by_placeholder("空表示未限制").fill(str(read_iops))

        if write_iops is not None:
            self.locator("div").filter(has_text=re.compile(r"^每秒写次数 次/S$")).get_by_placeholder("空表示未限制").fill(str(write_iops))

        self.get_by_label("设置QoS").get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_disable_qos(self, volume_name):
        """关闭云硬盘的QoS限制。"""
        self.click_action(volume_name, "设置QoS")
        self.get_by_role("switch").locator("span").click()
        self.get_by_label("设置QoS").get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_convert_to_image(self, volume_name, image_name):
        """将云硬盘转换为镜像。"""
        self.click_action(volume_name, "转镜像")
        self.locator("form").get_by_role("textbox").fill(image_name)
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_reset_status(self, volume_name):
        """重置云硬盘状态。"""
        self.click_action(volume_name, "重置状态")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_view_snapshots(self, volume_name):
        """查看指定云硬盘的快照列表。"""
        self.click_action(volume_name, "查看快照")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)

    @submenu("云硬盘")
    def evs_bind_snapshot_policy(self, volume_name, policy_name, enable_auto_snapshot=False):
        """云硬盘绑定快照策略。"""
        self.click_action(volume_name, "绑定策略")
        self.get_by_role("dialog", name="绑定策略").get_by_placeholder("请选择").click()
        self.get_by_text(policy_name, exact=True).click()

        if enable_auto_snapshot:
            self.get_by_role("switch").locator("span").click()

        self.dialog_confirm.click()
        self.wait_for_page_ready()
