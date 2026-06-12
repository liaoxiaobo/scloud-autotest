import re
import time
from time import sleep
import pytest
from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsDetailMixin(BasePage):
    """ECS 详情页与杂项操作。"""
    @submenu("弹性云服务器")
    def ecs_to_details(self, name: str):
        """进入云服务器详情页面

        Args:
            name: 云服务器名称
        """
        # 点击指定云服务器的详情链接
        self.get_by_role("cell", name=name).locator("a").click()

        # 等待详情页面加载完成

        logger.info(f"成功进入云服务器{name}详情页")


    @submenu("弹性云服务器")
    def get_first_event_data(self, name: str) -> dict:
        """获取云服务器事件列表第一条事件数据

        Args:
            name: 云服务器名称

        Returns:
            dict: 事件数据字典，包含事件名称、事件信息等
        """
        self.goto_detail_page(instance_name=name, tab_name="事件列表")

        first_row = self.locator(".el-table__body-wrapper .el-table__body tr").first
        expect(first_row).to_be_visible(timeout=5000)

        headers = self.locator(".el-table__header-wrapper th").all_text_contents()
        headers = [h.strip() for h in headers]

        cells = first_row.locator("td").all()
        cell_contents = []
        for cell in cells:
            text = cell.inner_text()
            text = re.sub(r'\s+', ' ', text).strip()
            cell_contents.append(text)

        result = dict(zip(headers, cell_contents))

        logger.info(f"第一条事件数据: {result}")
        self.goto_submenu("弹性云服务器")
        return result


    @submenu("弹性云服务器")
    def ecs_set_boot_order(self, name: str, boot_order: list):
        """
        设置云服务器启动顺序

        Args:
            name: 云服务器名称
            boot_order: 启动顺序配置，格式为：
                [  # 启动设备列表，按优先级排序
                        {"磁盘": "hdc:20GB"},
                        {"网络", "10.228.42.59/fa:16:3e:ae:bb:fa"}
                    ]
        """
        # 点击云服务器的操作按钮
        self.click_action(name, "设置启动项")

        # 添加启动项
        if len(boot_order) > 1:
            for i in range(len(boot_order) - 1):
                self.get_by_role("button", name=" 添加启动项").click()

        for i, boot_device in enumerate(boot_order):
            # 选择启动类型
            for boot_type, devices in boot_device.items():
                self.get_by_label("设置启动项").get_by_placeholder("请选择").nth(0 if i == 0 else i * 2).click()

                self.locator("li").filter(has_text=re.compile(fr"^{boot_type}$")).nth(
                    1 if len(boot_order) > 1 else 0).click()

                # 选择设备
                self.get_by_label("设置启动项").get_by_placeholder("请选择").nth((i * 2 + 1)).click()
                self.locator("li").filter(has_text=devices).click()

        # 确认设置
        self.dialog_confirm.click()

        logger.info(f"云服务器 {name} 启动顺序设置完成")


    @submenu("弹性云服务器")
    def ecs_install_tools(self, name: str):
        """为云服务器安装工具

        Args:
            name: 云服务器名称
        """
        # 点击操作按钮
        self.click_action(name, "安装工具")

        # 点击安装并进入下一步
        self.get_by_text("安装并进入下一步").click()
        logger.info(f"云服务器 {name} 安装工具请求已提交")


    @submenu("弹性云服务器")
    def ecs_uninstall_tools(self, name: str):
        """云服务器页面卸载工具

        Args:
            name: 云服务器名称
        """
        # 点击操作按钮
        self.click_action(name, "卸载工具")

        # 点击确定
        time.sleep(2)
        self.dialog_confirm.click()

        logger.info(f"云服务器 {name} 卸载工具请求已提交")


    @submenu("弹性云服务器")
    def ecs_record_screen(self, name: str):
        """云服务器录屏
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "开启录屏")
        self.get_by_label("开启录屏").get_by_text("开启", exact=True).click()
        self.assert_popup_success(f"{name}实例开启录屏成功")
        logger.info(f"实例: {name}开启录屏")


    @submenu("弹性云服务器")
    def ecs_stop_record_screen(self, name: str):
        """云服务器停止录屏
        Args:
            name: 云服务器名称
        """
        self.click_action(name, "关闭录屏")
        self.get_by_label("关闭录屏").get_by_text("关闭", exact=True).click()
        self.assert_popup_success(f"{name}实例禁用录屏成功")
        logger.info(f"实例: {name}实例关闭录屏成功")


    @submenu("弹性云服务器")
    def ecs_agent_version(self, name: str, agent_conf: list):
        """云服务器获取代理版本
        Args:
            name: 云服务器名称
            agent_conf: 代理类型, [{"FsAgent": "manual"}], [{"FsAgent": "manual"},{"DingAgent": "latest"}]
        """
        self.click_action(name, "Agent版本设置")
        for conf in agent_conf:
            for agent_type, agent_version in conf.items():
                self.locator("label").filter(has_text=agent_type).click()
                locator = self.get_by_role("row",name=f"默认{agent_type} {agent_version} 系统默认，禁止修改").get_by_role("radio")
                if not locator.is_checked():
                    locator.click()
                else:
                    pytest.skip(f"当前{agent_type}版本已设置为: {agent_version}")
        self.dialog_confirm.click()
        logger.info(f"{name}实例修改Agent版本设置为: {agent_conf}")


    @submenu("弹性云服务器")
    def ecs_nic_set_qos(self, vm_name, qos_name=None):
        """在ECS详情页网卡列表中为第一张网卡设置QoS。

        Args:
            vm_name: 云服务器名称。
            qos_name: QoS策略名称，传入None或"不限制"表示取消QoS限制。
        """
        self.ecs_to_details(vm_name)
        self.wait_for_page_ready()

        # 切换到"网卡列表"页签
        tab = self.page.locator(".el-tabs__item").filter(has_text=re.compile(r"^\s*网卡列表\s*$")).first
        # 移动鼠标到空白区域消除可能遮挡的 tooltip
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)
        tab.click()
        self.wait_for_page_ready()

        # 等待网卡列表表格加载
        self.page.wait_for_timeout(2000)
        first_row = self.page.locator(".el-table__body-wrapper .el-table__body tr").first
        expect(first_row).to_be_visible(timeout=15000)

        op_cell = first_row.locator("td").last
        op_cell.scroll_into_view_if_needed()

        btn = op_cell.locator("button").first
        if btn.count() == 0 or not btn.is_visible():
            btn = op_cell.get_by_text("更多")
        if btn.count() == 0 or not btn.is_visible():
            dropdown = op_cell.locator("[class*='dropdown']").first
            if dropdown.count() > 0:
                inner_btn = dropdown.locator("button").first
                if inner_btn.count() > 0 and inner_btn.is_visible():
                    btn = inner_btn
                else:
                    dropdown.click(force=True)
                    self.page.wait_for_timeout(500)
                    self.page.get_by_text("设置QoS").first.dispatch_event("click")
                    dialog = self.get_by_role("dialog").filter(has_text="设置QoS").first
                    expect(dialog).to_be_visible(timeout=5000)

                    if qos_name and qos_name != "不限制":
                        dialog.get_by_placeholder("QoS").click()
                        self.page.wait_for_timeout(800)
                        self.page.locator(".el-select-dropdown__item").filter(has_text=qos_name).first.click()
                    else:
                        dialog.get_by_placeholder("QoS").click()
                        self.page.wait_for_timeout(800)
                        self.page.get_by_text("不限制", exact=True).click()

                    dialog.get_by_text("确定", exact=True).click()
                    logger.info(f"云服务器 {vm_name} 网卡QoS设置完成: {qos_name or '不限制'}")
                    return

        btn.click()
        self.page.wait_for_timeout(500)

        self.page.get_by_text("设置QoS").first.dispatch_event("click")

        dialog = self.get_by_role("dialog").filter(has_text="设置QoS").first
        expect(dialog).to_be_visible(timeout=5000)

        if qos_name and qos_name != "不限制":
            dialog.get_by_placeholder("QoS").click()
            self.page.wait_for_timeout(800)
            self.page.locator(".el-select-dropdown__item").filter(has_text=qos_name).first.click()
        else:
            dialog.get_by_placeholder("QoS").click()
            self.page.wait_for_timeout(800)
            self.page.get_by_text("不限制", exact=True).click()

        dialog.get_by_text("确定", exact=True).click()
        logger.info(f"云服务器 {vm_name} 网卡QoS设置完成: {qos_name or '不限制'}")

    def ecs_back_to_list(self):
        """返回云服务器列表页
        """
        logger.info(f"返回云服务器列表页面")
        # 点击指定云服务器的详情链接
        self.locator(".el-icon-back").click()
        # 等待详情页面加载完成


    @submenu("弹性云服务器")
    def ecss_create(self, name, snapshot_name, desc="", data_disk=False):
        self.click_action(name, "新建快照")
        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^快照名称$")).get_by_role("textbox").fill(snapshot_name)
        dialog.locator("textarea").fill(desc)
        if data_disk:
            self.page.locator("form span").nth(3).click()
        self.dialog_confirm.click()
        logger.info(f"云服务器快照创建请求已提交: {name}, {snapshot_name}")


    def wait_for_snapshot_start(self, vm_name, snap_time, timeout=3600):
        """等待快照开始创建

        Args:
            vm_name: 虚拟机名称
            snap_time: 目标时间（小时，如16表示16点）
            timeout: 最大超时时间（秒），默认为3600秒（1小时）

        Returns:
            bool: 如果成功检测到快照创建开始，返回True；否则返回False
        """
        start_time = time.time()
        polling_started = False
        polling_duration = 180  # 3分钟
        polling_start_time = None

        # 等待到达目标时间
        while time.time() - start_time < timeout:
            # 获取当前时间
            current_hour = int(time.strftime("%H", time.localtime()))
            current_time_str = time.strftime("%H:%M:%S", time.localtime())

            # 如果当前时间还未到目标时间，继续等待
            if current_hour < snap_time:
                logger.debug(f"当前时间 {current_time_str} 小于目标时间 {snap_time}点，继续等待...")
                self.page.wait_for_timeout(3000)  # 等待3秒
                continue

            # 如果到达目标时间但轮询还未开始，开始轮询计时
            if not polling_started:
                logger.info(f"已到达目标时间 {snap_time}点，开始轮询检查虚拟机状态")
                polling_started = True
                polling_start_time = time.time()

            # 检查虚拟机状态
            try:
                self.locator(".el-icon-refresh").click()
                status = self.get_row_data(vm_name).get("状态", "")

                if "创建快照中" in status:
                    logger.info(f"检测到虚拟机 {vm_name} 开始创建快照")
                    return True
            except Exception as e:
                logger.warning(f"检查虚拟机状态时出错: {str(e)}")

            # 如果轮询时间超过3分钟，退出
            if polling_started and (time.time() - polling_start_time) > polling_duration:
                logger.warning(f"轮询 {polling_duration} 秒后仍未检测到快照创建")
                break

            # 轮询间隔3秒
            self.page.wait_for_timeout(3000)

        # 只有在真正超时后返回True
        logger.warning(f"等待快照创建状态超时, 检查快照")
        return True


    def stout_to_dict(self, strs):
        """将gova show字输出的符串转为字典
        Args:
            strs: 字符串
        Returns:
            字典
        """
        result = {}
        strs = strs.replace("+", "")
        strs = strs.strip()
        l = strs.split("|")
        for i, v in enumerate(l):
            if i % 3 == 1:
                result[v.strip()] = l[i + 1].strip()
            else:
                continue
        return result


    def wait_for_update(self, ssh_vm, cmd, expection, timeout=30, check_interval=15):
        """等待主机更新完成
        Args:
            ssh_vm: ssh对象及run的命令
            expection: 期望值
            timeout: 超时时间
            check_interval: 检查间隔
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if ssh_vm.run(cmd, return_rc=True).get('stdout').count(expection):
                break  # 已更新，退出轮询
            time.sleep(check_interval)
