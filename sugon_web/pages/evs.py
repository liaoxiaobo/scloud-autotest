from sugon_web.common.base import BasePage, submenu
from playwright.sync_api import Page
import re

class EvsPage(BasePage):
    # 云硬盘页面
    def __init__(self, page: Page, env: dict) -> None:
        super().__init__(page, env)

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

    def _set_count(self, count):
        """设置云硬盘数量"""
        self.get_by_label("数量").fill(str(count))

    def _select_image_source(self):
        """选择云硬盘来源为镜像"""
        self.get_by_role("dialog", name="dialog").get_by_placeholder("请选择", exact=True).click()
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

    @submenu("云硬盘")
    def evs_create(
            self,
            name,
            count=1,
            size=30,
            empty=True,
            image_name="",
            volume_type="",
            desc=""
    ):
        """创建云硬盘

        Args:
            name: 云硬盘名称
            count: 创建数量，默认为1
            size: 云硬盘大小（GB），默认为30GB
            empty: 是否创建空白云硬盘，默认True
            image_name: 镜像名称
            volume_type: 云硬盘类型
            desc: 云硬盘描述信息，默认为空
        """
        image_name = image_name or self.storage_pool
        volume_type = volume_type or self.volume_type
        self.btn_create.click()
        self._input_name.fill(name)

        if count != 1:
            self._set_count(count)
        if not empty:
            self._select_image_source()
        self._select_volume_type(volume_type)
        if not empty:
            self._select_image(image_name)

        self._input_size.fill(str(size))
        self._input_desc.fill(desc)
        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_remove(self, name):
        """回收云硬盘资源
        
        Args:
            name: 云硬盘名称
        """
        self.click_dropdown_option(name, "删除")
        self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()

    @submenu("回收站")
    def evs_delete(self, name, secure=False):
        """删除指定名称的云硬盘资源

        Args:
            name: 云硬盘名称
            secure: 是否安全删除（彻底删除），默认为False（普通删除）
        """
        # 根据参数选择删除类型
        delete_option = "安全删除" if secure else "删除"

        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(name, delete_option)
        
        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("回收站")
    def evs_restore(self, volume_name):
        """从回收站恢复云硬盘

        Args:
            volume_name: 云硬盘名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(volume_name, "恢复")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_edit(self, name, new_name, new_desc):
        """修改指定云硬盘的名称和描述

        Args:
            name: 原云硬盘名称
            new_name: 新的云硬盘名称
            new_desc: 新的描述信息
        """
        self.click_dropdown_option(name, "修改")

        dialog = self.get_by_role("dialog")
        dialog.locator('input[type="text"]').fill(new_name)
        dialog.locator("textarea").fill(new_desc)

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_clone(self, source_name, clone_name):
        """克隆指定云硬盘

        Args:
            source_name: 源云硬盘名称
            clone_name: 克隆后的云硬盘名称
        """
        self.click_dropdown_option(source_name, "克隆")

        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(clone_name)

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_expand(self, name, new_size):
        """扩容指定云硬盘

        Args:
            name: 云硬盘名称
            new_size: 扩容后的大小（GB）
        """
        self.click_dropdown_option(name, "扩容")

        dialog = self.get_by_label("扩容")
        size_input = dialog.get_by_role("spinbutton")
        size_input.fill(str(new_size))

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_mount(self, volume_name, server_name):
        """挂载云硬盘到指定服务器

        Args:
            volume_name: 云硬盘名称
            server_name: 目标服务器名称
        """
        # 使用通用方法点击挂载选项
        self.click_dropdown_option(volume_name, "挂载")

        # 选择目标服务器
        self.get_by_role("row", name=server_name).get_by_role("radio").click()

        # 确认挂载
        self.locator("span").filter(has_text="挂载").click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_unmount(self, volume_name, server_name):
        """从指定服务器卸载云硬盘

        Args:
            volume_name: 云硬盘名称
            server_name: 目标服务器名称
        """
        # 使用通用方法点击卸载选项
        self.click_dropdown_option(volume_name, "卸载")

        # 在卸载对话框中选择服务器
        self.get_by_label("卸载").get_by_placeholder("请选择").click()
        self.locator("span").filter(has_text=re.compile(rf"^{server_name}$")).click()

        # 确认卸载
        self.get_by_label("卸载").get_by_text("确定").click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_enable_qos(self, volume_name, read_speed=None, write_speed=None, read_iops=None, write_iops=None):
        """为云硬盘启用QoS限制

        Args:
            volume_name: 云硬盘名称
            read_speed: 读取速度限制（MB/s），可选
            write_speed: 写入速度限制（MB/s），可选
            read_iops: 每秒读次数限制，可选
            write_iops: 每秒写次数限制，可选
        """
        # 点击设置QoS选项
        self.click_dropdown_option(volume_name, "设置QoS")

        # # 启用QoS开关
        # self.get_by_role("switch").locator("span").click()

        # 如果提供了速度限制参数，则设置
        if read_speed is not None:
            self.locator("form div").filter(has_text="读取速度 MBpsKBpsBps").get_by_placeholder("空表示未限制").fill(
                str(read_speed))

        if write_speed is not None:
            self.locator("form div").filter(has_text="写入速度 MBpsKBpsBps").get_by_placeholder("空表示未限制").fill(
                str(write_speed))

        # 如果提供了IOPS限制参数，则设置
        if read_iops is not None:
            self.locator("div").filter(has_text=re.compile(r"^每秒读次数 次/S$")).get_by_placeholder(
                "空表示未限制").fill(str(read_iops))

        if write_iops is not None:
            self.locator("div").filter(has_text=re.compile(r"^每秒写次数 次/S$")).get_by_placeholder(
                "空表示未限制").fill(str(write_iops))

        # 确认设置
        self.get_by_label("设置QoS").get_by_text("确定").click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_disable_qos(self, volume_name):
        """关闭云硬盘的QoS限制

        Args:
            volume_name: 云硬盘名称
        """
        # 点击设置QoS选项
        self.click_dropdown_option(volume_name, "设置QoS")

        # 关闭QoS开关
        self.get_by_role("switch").locator("span").click()

        # 确认设置
        self.get_by_label("设置QoS").get_by_text("确定").click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evs_convert_to_image(self, volume_name, image_name):
        """将云硬盘转换为镜像

        Args:
            volume_name: 云硬盘名称
            image_name: 转换后的镜像名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(volume_name, "转镜像")

        # 填写镜像名称
        self.locator("form").get_by_role("textbox").fill(image_name)

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("云硬盘")
    def evss_create(self, volume_name, snapshot_name, desc):
        """给指定云硬盘添加快照

        Args:
            volume_name: 云硬盘名称
            snapshot_name: 快照名称
            desc: 快照描述
        """
        self.click_dropdown_option(volume_name, "添加快照")

        dialog = self.get_by_role("dialog")
        # 填写快照名称
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(snapshot_name)
        # 填写描述
        desc_input = dialog.locator("textarea")
        desc_input.fill(desc)

        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_bind_snapshot_policy(self, volume_name, policy_name, enable_auto_snapshot=True):
        """云硬盘绑定快照策略

        Args:
            volume_name: 云硬盘名称
            policy_name: 快照策略名称
            enable_auto_snapshot: 是否启用自动快照，默认为True
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(volume_name, "绑定策略")

        # 选择快照策略
        self.get_by_role("dialog", name="dialog").get_by_placeholder("请选择").click()
        self.get_by_text(policy_name, exact=True).click()

        # 设置自动快照开关
        if enable_auto_snapshot:
            self.get_by_role("switch").locator("span").click()

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照")
    def evs_create_from_snapshot(self, snapshot_name, volume_name, desc=""):
        """从快照创建云硬盘

        Args:
            snapshot_name: 快照名称
            volume_name: 新创建的云硬盘名称
            desc: 云硬盘描述信息，默认为空
        """
        # 点击操作按钮
        self.click_dropdown_option(snapshot_name, "创建云硬盘")

        # 填写云硬盘名称
        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.fill(volume_name)

        # 填写描述
        self.locator("textarea").fill(desc)

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照")
    def evss_delete(self, name):
        """删除指定名称的云硬盘快照资源

        Args:
            name: 快照名称
        """
        self.click_dropdown_option(name, "删除")
        self.get_by_text("确定", exact=True).nth(1).click()

    @submenu("快照策略")
    def evss_policy_create(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1):
        """创建快照策略

        Args:
            name: 策略名称
            enabled: 是否启用策略，默认为True
            hours: 执行时间的小时列表，如[1, 2]表示01:00和02:00执行
            cycle_days: 快照周期（天），默认为1
            retention_type: 保留规则类型，"按数量"、"按时间"或"永久保存"，默认为"按数量"
            retention_value: 保留值，数量或天数，默认为1
        """
        # 使用BasePage中的通用创建按钮
        self.btn_create.click()

        # 填写策略名称
        dialog = self.get_by_label("dialog")
        dialog.get_by_role("textbox").fill(name)

        # 设置启用状态
        if enabled:
            self.get_by_role("switch").locator("span").click()

        # 设置执行时间 - 修改这里，使用exact=True参数
        if hours:
            for hour in hours:
                self.get_by_text(f"{hour:02d}:00", exact=True).click()

        # 设置快照周期（天）
        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))

        # 设置保留规则
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            # 设置保留值
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照策略")
    def evss_policy_delete(self, name):
        """删除快照策略

        Args:
            name: 策略名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(name, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照策略")
    def evss_policy_edit(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1):
        """修改快照策略

        Args:
            name: 策略名称
            enabled: 是否启用策略，默认为True
            hours: 执行时间的小时列表，如[1, 2]表示01:00和02:00执行
            cycle_days: 快照周期（天），默认为1
            retention_type: 保留规则类型，"按数量"、"按时间"或"永久保存"，默认为"按数量"
            retention_value: 保留值，数量或天数，默认为1
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(name, "修改")

        # 填写策略名称
        self.get_by_label("修改策略").get_by_role("textbox").nth(1).fill(name)

        # 设置启用状态
        if enabled:
            self.get_by_role("switch").locator("span").click()

        # 设置执行时间 - 修改这里，使用exact=True参数
        if hours:
            for hour in hours:
                self.get_by_text(f"{hour:02d}:00", exact=True).click()

        # 设置快照周期（天）
        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))

        # 设置保留规则
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            # 设置保留值
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照任务")
    def evs_disable_auto_snapshot(self, volume_name):
        """禁用云硬盘的自动快照

        Args:
            volume_name: 云硬盘名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(volume_name, "禁用自动快照")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()

    @submenu("快照任务")
    def evss_task_delete(self, volume_name):
        """删除云硬盘的快照任务

        Args:
            volume_name: 云硬盘名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_dropdown_option(volume_name, "删除")

        self.dialog_confirm.click()

        # 等待操作完成
        self.wait_for_page_ready()
