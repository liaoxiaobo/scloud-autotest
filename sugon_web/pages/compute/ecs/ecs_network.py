import random
import re
import time
from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsNetworkMixin(BasePage):
    """ECS 网络与安全组操作。"""
    @submenu("弹性云服务器")
    def ecs_load_network(
        self,
        name: str,
        net: str,
        subnet: str,
        mode="标准",
        ipv4: dict = None
    ):
        """加载网卡
        Args:
            name: 云服务器名称
            net: 网络
            subnet: 子网
            mode: 网络加速模式
            ipv4: IPV4分配方式，{"method": "自动分配"}，{"method": "选择端口", "端口":"xxxx"},{"method": "选择端口",“加密网卡”:True}
        """
        checked_subnet = ""
        try:
            self.click_action(name, "加载网卡")
            # 选择网络
            logger.info(f"云服务器{name}：选择网络{net}")
            self.get_by_role("textbox", name="请选择网络").click()
            self.get_by_text(net, exact=True).click()
            # 选择子网
            self.get_by_role("textbox", name="请选择子网").click()
            self.get_by_role("listitem").filter(has_text=f"{subnet}(").click()
            checked_subnet = self.get_by_role("textbox", name="请选择子网").input_value().split("(")[1].split(".0/")[0]
            logger.info(f"云服务器{name}：选择子网{subnet}, 实际子网{checked_subnet}")
            # 选择网络加速模式
            if mode:
                logger.info(f"云服务器{name}：选择网络加速模式{mode}")
                self.get_by_role("radio").filter(has_text=mode).click()
            if ipv4:
                for key, value in ipv4.items():
                    logger.info(f"云服务器{name}：IPV4分配方式{key}：{value}")
                    self.get_by_role("radio").filter(has_text=key).click()
                    self.get_by_text(value).click()
            self.get_by_label("加载网卡").get_by_text("确定").click()
            logger.info(f"操作完成: 云服务器{name}: 加载网卡")
            return checked_subnet
        except Exception as e:
            logger.error(f"云服务器{name}：加载网卡失败:{e}")
            raise e


    @submenu("弹性云服务器")
    def ecs_uninstall_network(self, name: str, net: str):
        """卸载网卡
        Args:
            name: 云服务器名称
            net: 需卸载的网卡
        """
        self.click_action(name, "卸载网卡")
        # 选择网络
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_role("listitem").filter(has_text=net).click()
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}卸载网: {net}")


    @submenu("弹性云服务器")
    def ecs_bind_pub_ip(self, name: str, subnet: str = "Autotest", pub_net: str = "public_net", eip_ip: str = None):
        """绑定公网IP
        Args:
            name: 云服务器名称
            subnet: 子网
            pub_net: 公网资源池
            eip_ip: 指定要绑定的公网IP地址，为None时随机选择可用IP
        """
        # 新版 ECS 列表操作项藏在“更多”展开的大型下拉面板内，
        # 文案位于 .cloud-button 内部 div，Playwright 判定该内部 div 不可见，
        # 导致通用 click_action 无法命中。这里直接点对应行的“更多”并定位外层 .cloud-button。
        row = self.get_row_by_name(name)
        interactive_row = self._get_interactive_row(row)
        more_btn = interactive_row.get_by_text("更多", exact=True)
        more_btn.click()
        self.page.wait_for_timeout(1000)

        visible_menu = None
        dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')
        for i in range(dropdown_menus.count()):
            menu = dropdown_menus.nth(i)
            if menu.is_visible():
                visible_menu = menu
                break
        if not visible_menu:
            raise AssertionError(f"未找到 {name} 的可见操作下拉菜单")

        bind_btn = visible_menu.locator(".cloud-button").filter(has_text="绑定公网IP").first
        if bind_btn.count() == 0 or not bind_btn.is_visible():
            raise AssertionError(f"未在下拉菜单中找到 {name} 的绑定公网IP 按钮")
        bind_btn.click()

        # 选择端口
        self.get_by_role("row").filter(has_text=subnet).get_by_role("radio").click()
        self.get_by_text("下一步", exact=True).click()
        # 选择资源池
        bind_dialog = self.get_by_role("dialog", name="绑定公网IP")
        bind_dialog.get_by_placeholder("请选择").click()
        self.get_by_text(pub_net).click()
        self.page.wait_for_timeout(2000)
        # 选择公网ip
        if eip_ip:
            # 在表格中查找指定IP地址的行，支持分页（含对话框外分页条）
            for page_attempt in range(20):
                # 等待表格加载完成（如有 loading 蒙层）
                try:
                    self.page.locator(".el-loading-mask").first.wait_for(state="hidden", timeout=3000)
                except Exception:
                    pass
                rows = bind_dialog.get_by_role("row").all()
                for row in rows:
                    cells = row.get_by_role("cell").all_text_contents()
                    if any(eip_ip in cell for cell in cells):
                        row.get_by_role("radio").click()
                        self.dialog_confirm.click()
                        logger.info(f"操作完成: 云服务器{name}: 绑定公网IP: {eip_ip}")
                        return eip_ip
                # 尝试翻页：优先在对话框内查找，再回退到页面级分页
                clicked = False
                pagination_scopes = [bind_dialog, self.page]
                for scope in pagination_scopes:
                    for selector in [
                        ".el-pagination .btn-next:not([disabled])",
                        ".el-pagination__next:not([disabled])",
                        ".pagination .next:not([disabled])",
                        ".btn-next:not(.is-disabled)",
                        "button[class*='next']:not([disabled])",
                    ]:
                        try:
                            btns = scope.locator(selector).all()
                            for btn in btns:
                                if btn.is_visible() and btn.is_enabled():
                                    btn.click()
                                    self.page.wait_for_timeout(1500)
                                    clicked = True
                                    break
                            if clicked:
                                break
                        except Exception:
                            continue
                    if clicked:
                        break
                # 策略2: 尝试点击页码数字（当前页+1）
                if not clicked:
                    try:
                        current_page = bind_dialog.locator(".el-pagination .active, .el-pager .active, .pagination .active").first
                        if current_page.count() == 0:
                            current_page = self.page.locator(".el-pagination .active, .el-pager .active, .pagination .active").first
                        if current_page.count() > 0:
                            current_text = current_page.text_content() or "1"
                            next_page_num = str(int(current_text) + 1)
                            next_page = bind_dialog.locator(".el-pager li, .pagination .page-item").filter(has_text=re.compile(rf"^{re.escape(next_page_num)}$")).first
                            if next_page.count() == 0:
                                next_page = self.page.locator(".el-pager li, .pagination .page-item").filter(has_text=re.compile(rf"^{re.escape(next_page_num)}$")).first
                            if next_page.count() > 0 and next_page.is_visible():
                                next_page.click()
                                self.page.wait_for_timeout(1500)
                                clicked = True
                    except Exception:
                        pass
                # 策略3: 尝试滚动表格主体加载更多
                if not clicked:
                    try:
                        body = bind_dialog.locator(".el-table__body-wrapper, .table-body").first
                        if body.count() > 0:
                            body.evaluate("el => el.scrollTop = el.scrollHeight")
                            self.page.wait_for_timeout(1500)
                            clicked = True
                    except Exception:
                        pass
                if not clicked:
                    break
            raise AssertionError(f"未在可用公网IP列表中找到指定IP: {eip_ip}")
        else:
            # 获取所有可用IP行，随机选择一个
            available_rows = bind_dialog.get_by_role("row").filter(has_text="关闭").all()
            if not available_rows:
                raise Exception("没有可用的公网IP")
            # 随机选择一个IP，降低多线程冲突概率
            selected_row = random.choice(available_rows)
            selected_row.get_by_role("radio").click()
            ip_info = selected_row.get_by_role("cell")
            ip = ip_info.nth(1).text_content()
            self.dialog_confirm.click()
            logger.info(f"操作完成: 云服务器{name}: 绑定公网IP: {subnet}, 公网ip: {ip}")
            return str(ip)


    @submenu("弹性云服务器")
    def ecs_unbind_pub_ip(self, name: str, IP_addr: str):
        """解绑公网IP
        Args:
            name: 云服务器名称
            IP_addr: 公网ip地址
        """
        self.click_action(name, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=IP_addr).click()
        self.get_by_label("解除绑定公网IP", exact=True).get_by_text("确定").click()
        logger.info(f"操作完成: 云服务器{name}: 解绑公网IP: {IP_addr}")


    @submenu("弹性云服务器")
    def ecs_to_sg_tab(self, name, sub_tab="自定义安全组"):
        """进入虚机详情的安全组页签

        Args:
            name: 云服务器名称
            sub_tab: 子页签名称，默认 "自定义安全组"
        """
        self.goto_detail_page(name, tab_name="安全组")
        self.wait_for_page_ready()

        # 详情页安全组区域存在异步渲染，先等待操作区或已绑定项出现，避免后续立刻读取为空。
        self._find_element(
            [
                self.get_by_text("设置安全组", exact=True),
                self.locator(".security-group-item").first,
            ],
            "安全组页签内容",
            timeout=10000,
        )
        if sub_tab:
            # 使用正则匹配精确文本，处理首尾空格和换行
            sub_tab_loc = self.locator(".security-group-item").filter(
                has_text=re.compile(rf"^\s*{re.escape(sub_tab)}\s*$")
            ).first
            expect(sub_tab_loc).to_be_visible(timeout=10000)
            sub_tab_loc.scroll_into_view_if_needed()
            for attempt in range(3):
                try:
                    sub_tab_loc.click(timeout=3000)
                    break
                except Exception as exc:
                    logger.warning(f"安全组子页签 {sub_tab} 第{attempt + 1}次普通点击失败: {exc}")
            else:
                logger.warning(f"安全组子页签 {sub_tab} 普通点击仍失败，尝试强制点击")
                sub_tab_loc.click(force=True)
            self.wait_for_page_ready()
        logger.info(f"进入云服务器 {name} 的安全组页签")


    def ecs_set_security_groups(self, sg_names: list, bind: bool = True):
        """虚机详情页设置安全组

        Args:
            sg_names: 安全组名称列表
            bind: 绑定/解绑
        """
        # 使用更精准的匹配
        self.get_by_text("设置安全组", exact=True).click()

        dialog = self.get_by_role("dialog").filter(has_text="安全组设置").last
        if not dialog.is_visible():
            dialog = self.get_by_role("dialog").filter(has_text="设置安全组").last

        self._expand_page_size("50")

        for sg in sg_names:
            # 找到对应行并勾选
            # row = dialog.get_by_role("row", name=re.compile(rf"^{re.escape(sg)}$")).first
            name_cell = dialog.locator(".el-table__cell").filter(has_text=re.compile(rf"^{re.escape(sg)}$")).first
            row = name_cell.locator("xpath=ancestor::tr[1]")
            checkbox = row.locator(".el-checkbox")

            # 检查是否已勾选
            is_checked = "is-checked" in (checkbox.get_attribute("class") or "")
            if bind and not is_checked:
                checkbox.click()
            elif not bind and is_checked:
                checkbox.click()

        self.dialog_confirm.click()

        # 等待成功提示
        self.assert_popup_success(re.compile(r"设置安全组成功|操作成功"))
        logger.info(f"设置安全组完成: {sg_names}, bind={bind}")


    def ecs_get_bound_security_groups(self):
        """获取已绑定的安全组列表
        """
        bound_items = self.locator(".security-group-item")
        # 切页签后绑定列表有异步渲染延迟，短轮询避免误把“未渲染”当成空列表。
        end_time = time.time() + 10
        items = []
        while time.time() < end_time:
            items = [item.strip() for item in bound_items.all_text_contents() if item.strip()]
            if items:
                break
            self.page.wait_for_timeout(500)

        # 清洗数据，提取安全组名称（通常在括号前或者开头）
        bound_sgs = []
        for item in items:
            # 过滤掉空的或者包含 "自定义安全组" 的通用项
            name = item.split('(')[0].strip()
            if name and name not in ["自定义安全组", "安全组"]:
                bound_sgs.append(name)

        logger.info(f"当前绑定的安全组: {bound_sgs}")
        return bound_sgs


    def ecs_create_custom_sg_rule(self, **kwargs):
        """在详情页创建自定义安全组规则

        支持从 kwargs 中提取所有安全组规则参数。
        """
        # 录制中可能出现多种按钮点击方式
        btn_locs = [
            self.get_by_text("创建规则 批量删除").get_by_text("创建规则"),
            self.get_by_text("创建规则").first,
        ]
        self._find_element(btn_locs, "添加/创建规则按钮").first.click()

        # 指定弹窗
        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"创建规则")).last

        # 提取参数
        protocol = kwargs.get("protocol", "所有")
        direction = kwargs.get("direction", "入口")
        remote_type = kwargs.get("remote_type", "CIDR")
        ip_version = kwargs.get("ip_version", "IPv4")
        remote_sg = kwargs.get("remote_sg")
        description = kwargs.get("description", "")
        protocol_type = kwargs.get("protocol_type")
        protocol_code = kwargs.get("protocol_code")
        port_type = kwargs.get("port_type")
        port = kwargs.get("port")
        cidr = kwargs.get("cidr")

        # 选择协议
        protocol_input = dialog.locator("form div").filter(has_text="协议").get_by_placeholder("请选择", exact=True)
        self.select_if_not_match(protocol_input, protocol, exact=True)

        # 如果选择常用协议，需要进一步选择协议类型
        if protocol == "选择常用协议" and protocol_type:
            protocol_type_input = dialog.get_by_placeholder("请选择协议")
            self.select_if_not_match(protocol_type_input, protocol_type, exact=False)

            # 处理端口配置（定制TCP/UDP协议时需要）
            if "TCP" in protocol_type or "UDP" in protocol_type:
                port_type_input = dialog.locator("div").filter(has_text=re.compile(r"^打开端口")).get_by_placeholder(
                    "请选择")
                self.select_if_not_match(port_type_input, port_type, exact=True)

                # 填写端口
                if port_type == "端口范围" and port and "-" in port:
                    start_port, end_port = port.split("-")
                    start_loc = dialog.locator("div").filter(has_text=re.compile(r"^起始端口号$")).get_by_role(
                        "textbox")
                    start_loc.clear()
                    start_loc.fill(start_port)
                    end_loc = dialog.locator("div").filter(has_text=re.compile(r"^终止端口号$")).get_by_role("textbox")
                    end_loc.clear()
                    end_loc.fill(end_port)
                elif port:
                    dialog.get_by_placeholder("请输入端口").fill(port)

        # 如果选择手填协议CODE，填写CODE值
        elif protocol == "手填协议CODE" and protocol_code:
            dialog.get_by_placeholder("请输入协议CODE").fill(protocol_code)

        # 选择方向
        direction_input = dialog.locator("div").filter(has_text=re.compile(r"^方向")).get_by_placeholder("请选择")
        self.select_if_not_match(direction_input, direction, exact=False)

        # 选择远程类型
        remote_type_input = dialog.locator("div").filter(has_text=re.compile(r"^远程")).get_by_placeholder("请选择")
        self.select_if_not_match(remote_type_input, remote_type, exact=True)

        # 选择IP版本
        ip_version_input = dialog.get_by_placeholder("请选择IP版本")
        self.select_if_not_match(ip_version_input, ip_version, exact=False)

        # 根据远程类型填写对应值
        if remote_type == "安全组" and remote_sg:
            # 使用更精确的正则匹配，避免匹配到已选择“安全组”的“远程”下拉框
            dialog.locator("div").filter(has_text=re.compile(r"^安全组$")).get_by_placeholder("请选择").click()
            self.locator("li:visible").filter(has_text=remote_sg).first.click()
        elif remote_type == "CIDR" and cidr:
            dialog.get_by_placeholder(re.compile(r"非必填.*如.*0\.0\.0\.0")).fill(cidr)

        # 填写描述
        if description:
            dialog.locator("textarea").fill(description)

        # 确定并断言
        dialog.get_by_text("确定", exact=True).click()
        self.assert_popup_success(re.compile(r"规则操作成功|新建.*成功|操作成功"))
        logger.info(f"自定义安全组规则创建完成: {kwargs}")


    def ecs_delete_custom_sg_rule(self, description=None):
        """在详情页删除指定的自定义安全组规则
        Args:
            description: 规则描述，用于精确定位某条规则
        """
        if description:
            # 使用描述查找对应行并点击删除
            self.click_action(description, "删除")
        else:
            # 如果没提供描述，默认删除第一条规则（兼容原有逻辑）
            active_pane = self.locator(".el-tab-pane:not([aria-hidden='true'])").first
            target_row = active_pane.locator(".el-table__row").first
            target_row.get_by_text("删除").click()

        self.dialog_confirm.click()
        logger.info(f"自定义安全组规则删除完成: description={description}")


    def ecs_get_custom_sg_rules(self, direction="入口"):
        """获取自定义安全组规则列表

        Args:
            direction: 规则方向，"入口" 或 "出口"
        """
        if direction:
            target_direction = self.get_by_text(direction, exact=True).filter(has_not_text="入口出口")
            if target_direction.count() > 0:
                target_direction.first.click()

        # 查找当前激活的tab页中的表格 headers 和 rows
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])", ".active-tab").first
        headers = [h.strip() for h in active_tab.locator(".el-table__header-wrapper th").all_text_contents() if
                   h.strip()]

        # 过滤掉可能存在的方向选择器文字
        headers = [h for h in headers if h not in ["入口", "出口"]]

        row_locators = active_tab.locator(".el-table__body-wrapper tr").all()

        rules = []
        for row_locator in row_locators:
            cell_contents = self._get_cell_contents(row_locator)
            row_data = dict(zip(headers, cell_contents))

            rule_data = {}
            for key, val in row_data.items():
                if "方向" in key:
                    rule_data["方向"] = val
                elif "以太网类型" in key:
                    rule_data["以太网类型"] = val
                elif "协议" in key:
                    rule_data["协议"] = val
                elif "端口范围" in key:
                    rule_data["端口范围"] = val
                elif "远端IP前缀" in key:
                    rule_data["远端IP前缀"] = val
                elif "远端安全组" in key:
                    rule_data["远端安全组"] = val
                elif "描述" in key:
                    rule_data["描述"] = val
            rules.append(rule_data)

        self.logger.info(f"获取到的云服务器自定义规则列表: {rules}")
        return rules


    def select_if_not_match(self, locator, value, exact=False):
        """
        如果当前选项不匹配，则选择指定值

        Args:
            locator: 定位器
            value: 期望值
            exact: 是否精确匹配，默认 False
        """
        if locator.input_value() != value:
            locator.click()
            # 增加 visible=True 过滤
            target = self.locator("li:visible")
            if exact:
                target.filter(has_text=re.compile(rf"^{value}$")).first.click()
            else:
                target.filter(has_text=value).first.click()
