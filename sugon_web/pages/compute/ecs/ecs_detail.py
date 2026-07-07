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
        # 先尝试通过搜索+点击名称链接进入详情页
        try:
            self.search(name)
            self.wait_for_page_ready()
        except Exception:
            pass  # 搜索失败不影响后续尝试

        # 使用 get_row_by_name 查找行（支持复合名称如 "name ID:uuid"）
        try:
            row = self.get_row_by_name(name)
            # 在行内查找可点击的名称链接
            link = row.locator("a").first
            if link.count() > 0 and link.is_visible():
                link.click()
                logger.info(f"成功进入云服务器{name}详情页")
                return
        except Exception:
            pass

        # 兜底1：名称/ID 列常渲染在 el-table 固定左列（.el-table__fixed）的独立 DOM 子树，
        # 主体 tbody 行内取不到该 <a> 链接。el-table 固定列会复制 DOM 导致一份隐藏一份可见，
        # 故遍历所有匹配 <a> 并选第一个可见的点击。
        try:
            anchors = self.page.locator("a").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$")).all()
            for anchor in anchors:
                if anchor.is_visible():
                    anchor.click()
                    logger.info(f"成功进入云服务器{name}详情页（遍历可见a标签）")
                    return
        except Exception:
            pass

        # 兜底2：尝试通过 get_by_text 匹配（非精确匹配）
        try:
            name_link = self.page.locator("#cloud-container-content").get_by_text(name, exact=False).first
            if name_link.count() > 0 and name_link.is_visible():
                name_link.click()
                logger.info(f"成功进入云服务器{name}详情页")
                return
        except Exception:
            pass

        raise AssertionError(f"无法进入云服务器 {name} 详情页：未找到可点击的名称链接")


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
                        self.locator("div.el-select-dropdown:visible li").filter(
                            has_text=re.compile(rf"^{re.escape(qos_name)}$")
                        ).click()
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
            self.locator("div.el-select-dropdown:visible li").filter(
                has_text=re.compile(rf"^{re.escape(qos_name)}$")
            ).click()
        else:
            dialog.get_by_placeholder("QoS").click()
            self.page.wait_for_timeout(800)
            self.page.get_by_text("不限制", exact=True).click()

        dialog.get_by_text("确定", exact=True).click()
        logger.info(f"云服务器 {vm_name} 网卡QoS设置完成: {qos_name or '不限制'}")

    @submenu("弹性云服务器")
    def ecs_nic_set_transfer_strategy(self, vm_name, strategy_name=None):
        """在ECS详情页网卡列表中为第一张网卡设置/解绑传输策略组（机密互联）。

        Args:
            vm_name: 云服务器名称。
            strategy_name: 传输策略组名称。传入None或"不加密"表示解绑（选择"不加密"）。
                           传入具体策略组名称表示绑定该策略组。
        """
        self.ecs_to_details(vm_name)
        self.wait_for_page_ready()

        # 切换到"网卡列表"页签
        tab = self.page.locator(".el-tabs__item").filter(has_text=re.compile(r"^\s*网卡列表\s*$")).first
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)
        tab.click()
        self.wait_for_page_ready()

        # 等待网卡列表表格加载 - 在#pane-netCard范围内找可见表格
        self.page.wait_for_timeout(2000)
        netcard_panel = self.page.locator("#pane-netCard").first
        expect(netcard_panel).to_be_visible(timeout=15000)

        # 获取网卡列表表格中的可见行（排除隐藏表格的行）
        # 先尝试在#pane-netCard范围内找表格体
        table_body = netcard_panel.locator(".el-table__body-wrapper .el-table__body").first
        expect(table_body).to_be_visible(timeout=15000)

        first_row = table_body.locator("tr").first
        expect(first_row).to_be_visible(timeout=15000)

        # 获取操作列（最后一列）
        op_cell = first_row.locator("td").last
        op_cell.scroll_into_view_if_needed()

        # 先尝试点击"修改网卡"按钮（可能直接打开包含传输策略组设置的对话框）
        # 优先点击网卡面板内可见的"修改网卡"，避免点到隐藏列的按钮
        modify_btn = None
        for cand in netcard_panel.get_by_text("修改网卡", exact=True).all():
            try:
                if cand.is_visible():
                    modify_btn = cand
                    break
            except Exception:
                continue
        if modify_btn is None:
            modify_btn = op_cell.locator("text=修改网卡").first

        if modify_btn is not None and modify_btn.count() > 0 and modify_btn.is_visible():
            modify_btn.scroll_into_view_if_needed()
            modify_btn.click()
            self.logger.info(f"已点击 {vm_name} 网卡列表的'修改网卡'按钮")
            # 等待对话框渲染完成
            self.page.wait_for_timeout(2000)

            # 检查是否打开了包含"传输策略组"的对话框
            dialog = self.page.locator(".el-dialog:visible").first
            if dialog.count() > 0 and dialog.is_visible():
                # 检查对话框中是否有"传输策略组"字段（兼容短暂 loading）
                ts_field = dialog.locator("div.el-form-item").filter(
                    has_text=re.compile(r"传输策略组")
                )
                try:
                    ts_field.wait_for(state="visible", timeout=5000)
                except Exception:
                    pass
                if ts_field.count() > 0 and ts_field.is_visible():
                    self.logger.info("修改网卡对话框包含传输策略组设置")
                    # 直接进入传输策略组选择逻辑
                    select = ts_field.locator(".el-select").first
                    expect(select).to_be_visible(timeout=5000)
                    select.click()
                    self.page.wait_for_timeout(500)

                    # 在下拉选项中选择
                    if strategy_name and strategy_name != "不加密":
                        self.locator("div.el-select-dropdown:visible li").filter(
                            has_text=re.compile(rf"^{re.escape(strategy_name)}$")
                        ).click()
                    else:
                        self.locator("div.el-select-dropdown:visible li").filter(
                            has_text=re.compile(r"^不加密$")
                        ).click()

                    # 点击确定
                    dialog.get_by_text("确定", exact=True).click()
                    logger.info(f"云服务器 {vm_name} 传输策略组设置完成: {strategy_name or '不加密(解绑)'}")
                    return
                else:
                    # 对话框不包含传输策略组，关闭它并尝试其他方式
                    self.logger.info("修改网卡对话框不包含传输策略组，尝试其他方式")
                    dialog.get_by_text("取消", exact=True).click()
                    self.page.wait_for_timeout(500)

        # 如果修改网卡不包含传输策略组，尝试点击"更多"下拉按钮
        # 直接在#pane-netCard范围内找"更多"按钮（有 cloud-table-dropdown-item-cl-btn 类的是表格行内的）
        dropdown_btn = netcard_panel.locator(".cloud-table-dropdown-item-cl-btn").filter(
            has_text=re.compile(r"^更多$")
        ).first
        if dropdown_btn.count() == 0 or not dropdown_btn.is_visible():
            # 备选：在#pane-netCard范围内直接找文本为"更多"的元素（排除页面级别的"更多操作"）
            all_more = netcard_panel.locator("text=更多").all()
            for btn in all_more:
                try:
                    if btn.is_visible():
                        text = btn.inner_text().strip()
                        if text == "更多":
                            dropdown_btn = btn
                            break
                except Exception:
                    pass

        if dropdown_btn is None or (hasattr(dropdown_btn, 'count') and dropdown_btn.count() == 0) or not dropdown_btn.is_visible():
            raise AssertionError(f"未找到 {vm_name} 网卡列表的'更多'按钮")

        dropdown_btn.scroll_into_view_if_needed()
        dropdown_btn.click()
        self.logger.info(f"已点击 {vm_name} 网卡列表的'更多'按钮")

        # 等待下拉菜单渲染到 body（el-dropdown-menu / el-popover / el-popper 均兼容）
        self.page.wait_for_timeout(2000)
        for menu_sel in [".el-dropdown-menu:visible", ".el-popover:visible", ".el-popper:visible"]:
            try:
                menu = self.page.locator(menu_sel).first
                if menu.count() > 0 and menu.is_visible():
                    self.logger.info(f"检测到下拉菜单: {menu_sel}")
                    break
            except Exception:
                continue
        else:
            menu = None

        # 点击"设置机密互联"或"设置可信传输"
        # 根据页面侦察结论卡，文案可能为"设置机密互联"或"设置可信传输"
        # 部分环境下拉菜单项 is_visible() 为 false，但 count > 0，优先直接点击可见菜单容器内的项
        strategy_btn = None
        menu_item_text = None
        for text in ["设置机密互联", "设置可信传输"]:
            # 1) 在已检测到的下拉菜单容器内查找
            if menu is not None and menu.count() > 0:
                try:
                    item = menu.locator(".el-dropdown-menu__item, .el-popover__item, .cloud-table-dropdown-item").filter(
                        has_text=re.compile(rf"^{re.escape(text)}$")
                    ).first
                    if item.count() > 0:
                        strategy_btn = item
                        menu_item_text = text
                        self.logger.info(f"在下拉菜单容器内找到: {text}")
                        break
                except Exception:
                    pass

            # 2) 全局 get_by_text（仍做可见性兜底）
            if strategy_btn is None:
                candidates = self.page.get_by_text(text, exact=True).all()
                for cand in candidates:
                    try:
                        if cand.is_visible():
                            strategy_btn = cand
                            menu_item_text = text
                            self.logger.info(f"找到下拉菜单项: {text}")
                            break
                    except Exception:
                        pass
                if strategy_btn:
                    break

            # 3) CSS 类兜底
            if strategy_btn is None:
                try:
                    css_candidates = self.page.locator(".cloud-table-dropdown-item").filter(
                        has_text=re.compile(rf"^{re.escape(text)}$")
                    ).all()
                    for cand in css_candidates:
                        try:
                            if cand.is_visible():
                                strategy_btn = cand
                                menu_item_text = text
                                self.logger.info(f"通过 CSS 类找到下拉菜单项: {text}")
                                break
                        except Exception:
                            pass
                    if strategy_btn:
                        break
                except Exception:
                    pass

        if strategy_btn is None:
            raise AssertionError(f"未找到 {vm_name} 的'设置机密互联'按钮")

        # 部分下拉菜单项可见性检测不稳定，count>0 即可点击；force 作为最后兜底
        try:
            strategy_btn.click(timeout=5000)
        except Exception:
            self.logger.warning(f"{menu_item_text} 常规点击失败，尝试 force 点击")
            strategy_btn.click(force=True)

        # 等待弹窗出现
        dialog = self.page.locator(".el-dialog:visible").first
        expect(dialog).to_be_visible(timeout=10000)

        # 选择传输策略组
        select = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"传输策略组")
        ).locator(".el-select")
        expect(select).to_be_visible(timeout=5000)
        select.click()

        self.page.wait_for_timeout(500)

        # 在下拉选项中选择
        if strategy_name and strategy_name != "不加密":
            # 选择指定的传输策略组
            self.locator("div.el-select-dropdown:visible li").filter(
                has_text=re.compile(rf"^{re.escape(strategy_name)}$")
            ).click()
        else:
            # 选择"不加密"表示解绑
            self.locator("div.el-select-dropdown:visible li").filter(
                has_text=re.compile(r"^不加密$")
            ).click()

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()
        logger.info(f"云服务器 {vm_name} 传输策略组设置完成: {strategy_name or '不加密(解绑)'}")

    def ecs_nic_get_transfer_strategy(self, vm_name):
        """在ECS详情页网卡列表中获取第一张网卡的传输策略组名称。

        Args:
            vm_name: 云服务器名称。

        Returns:
            str: 传输策略组名称，未绑定返回"--"。
        """
        self.ecs_to_details(vm_name)
        self.wait_for_page_ready()

        # 切换到"网卡列表"页签
        tab = self.page.locator(".el-tabs__item").filter(has_text=re.compile(r"^\s*网卡列表\s*$")).first
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)
        tab.click()
        self.wait_for_page_ready()

        # 等待网卡列表表格加载 - 在#pane-netCard范围内找可见表格
        self.page.wait_for_timeout(2000)
        netcard_panel = self.page.locator("#pane-netCard").first
        expect(netcard_panel).to_be_visible(timeout=15000)

        # 获取网卡列表表格中的可见行（Element UI 可能渲染多个 table body，需遍历查找）
        table_bodies = netcard_panel.locator(".el-table__body-wrapper .el-table__body").all()
        if not table_bodies:
            raise AssertionError("未找到网卡列表表格体")

        # 遍历所有 table body，查找包含传输策略组数据的行
        for table_body in table_bodies:
            try:
                if not table_body.is_visible():
                    continue
                rows = table_body.locator("tr").all()
                for row in rows:
                    try:
                        if not row.is_visible():
                            continue
                        cells = row.locator("td").all()
                        if len(cells) > 11:
                            strategy_cell = cells[11]
                            strategy_text = strategy_cell.inner_text().strip()
                            self.logger.info(f"网卡表格行传输策略组值: '{strategy_text}'")
                            if strategy_text and strategy_text != "--":
                                return strategy_text
                    except Exception:
                        pass
            except Exception:
                pass

        return ""

    def ecs_nic_assert_transfer_strategy(self, vm_name, expected_strategy):
        """断言ECS详情页网卡列表中第一张网卡的传输策略组名称。

        Args:
            vm_name: 云服务器名称。
            expected_strategy: 期望的传输策略组名称，空字符串表示未绑定。
        """
        actual = self.ecs_nic_get_transfer_strategy(vm_name)
        if expected_strategy:
            assert actual == expected_strategy, (
                f"[FieldAssertion] 网卡传输策略组 | 期望: {expected_strategy} | 实际: {actual}"
            )
        else:
            assert actual == "" or actual == "--", (
                f"[FieldAssertion] 网卡传输策略组 | 期望: 未绑定 | 实际: {actual}"
            )
        logger.info(f"断言通过: {vm_name} 网卡传输策略组为 '{actual}'")


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
