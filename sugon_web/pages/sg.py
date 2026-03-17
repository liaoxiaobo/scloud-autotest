import re

from sugon_web.common.base import BasePage, submenu


class SgPage(BasePage):
    """安全组页面类"""

    @submenu("安全组")
    def sg_create(self, name, desc=None):
        """创建安全组

        Args:
            name: 安全组名称
            desc: 安全组描述
        """
        self.btn_create.click()
        self.get_by_label("新建安全组").locator("input[type=\"text\"]").fill(name)
        if desc:
            self.locator("textarea").fill(desc)
        self.get_by_label("新建安全组").get_by_text("确定").click()

    @submenu("安全组")
    def sg_delete(self, sg_names):
        """删除安全组，支持单个和批量操作

        Args:
            sg_names: 安全组名称（字符串）或安全组名称列表（列表）
        """
        if isinstance(sg_names, list):
            # 批量操作模式
            self.select_rows_by_names(sg_names)
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_dropdown_option(sg_names, "删除")

        # 确认删除
        self.dialog_confirm.click()

    @submenu("安全组")
    def sg_edit(self, sg_name, new_name=None, new_desc=None):
        """编辑安全组

        Args:
            sg_name: 原安全组名称
            new_name: 新名称
            new_desc: 新描述
        """
        self.click_option(sg_name, "编辑", t_type="body")
        dialog = self.get_by_role("dialog", name="编辑")
        if new_name:
            dialog.locator("input[type=\"text\"]").fill(new_name)
        if new_desc:
            dialog.locator("textarea").fill(new_desc)
        self.dialog_confirm.click()

    @submenu("安全组")
    def sg_clone(self, sg_name, clone_name, clone_desc=None):
        """克隆安全组

        Args:
            sg_name: 原安全组名称
            clone_name: 克隆后的新名称
            clone_desc: 克隆后的新描述
        """
        self.click_dropdown_option(sg_name, "克隆")
        dialog = self.get_by_role("dialog", name="克隆安全组")
        dialog.locator("input[type=\"text\"]").fill(clone_name)
        if clone_desc:
            dialog.locator("textarea").fill(clone_desc)
        dialog.get_by_text("确定").click()

    @submenu("安全组")
    def sg_search(self, sg_name):
        """搜索安全组"""
        self.search(sg_name)

    @submenu("安全组")
    def sg_search_reset(self):
        """重置搜索条件"""
        self.btn_reset.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)  # 确保列表刷新完毕
        self.logger.info("重置安全组搜索条件完成")

    @submenu("安全组")
    def goto_sg_detail(self, sg_name):
        """进入安全组详情页面

        Args:
            sg_name: 安全组名称
        """
        self.get_by_text(sg_name, exact=True).click()
        self.wait_for_page_ready()
        self.logger.info(f"进入安全组{sg_name}详情页")

    def sg_rule_create(self, sg_name, protocol="所有", direction="出口",
                       remote_type="安全组", ip_version="IPv4",
                       remote_sg=None, description=None,
                       protocol_type=None, protocol_code=None,
                       port_type=None, port=None, cidr=None, from_list=False):
        """创建安全组规则

        Args:
            sg_name: 安全组名称
            protocol: 协议类型，支持 "所有"/"常用协议"/"手填协议CODE"，默认"所有"
            direction: 规则方向，"入口" 或 "出口"，默认"出口"
            remote_type: 远程类型，"安全组" 或 "CIDR"，默认"安全组"
            ip_version: IP版本，"IPv4" 或 "IPv6"，默认"IPv4"
            remote_sg: 远程安全组名称，当 remote_type="安全组" 时必填
            description: 规则描述，可选
            protocol_type: 常用协议子类型，如"定制TCP协议"/"定制UDP协议"/"HTTP"等
            protocol_code: 协议CODE值，当 protocol="手填协议CODE" 时必填（0-133的整数）
            port_type: 端口类型，"端口" 或 "端口范围"
            port: 端口号，如"22"
            cidr: CIDR值，当 remote_type="CIDR" 时填写，如"0.0.0.0/0"
            from_list: 是否在列表页直接创建规则，默认 False
        """

        if from_list:
            # 在列表页直接点击“创建规则”
            self.click_option(sg_name, "创建规则", t_type="body")
        else:
            # 如果没有在详情页，则进入安全组详情
            if not hasattr(self, '_in_detail') or not self._in_detail:
                self.goto_sg_detail(sg_name)
                self._in_detail = True
            
            # 点击创建规则按钮
            self.btn_create.click()

        # 获取创建规则弹窗
        dialog = self.get_by_role("dialog", name="创建规则")

        # 定义一个辅助函数按需选择
        def select_if_not_match(locator, value, exact=False):
            if locator.input_value() != value:
                locator.click()
                if exact:
                    self.locator("li").filter(has_text=re.compile(rf"^{value}$")).click()
                else:
                    self.locator("li").filter(has_text=value).click()

        # 选择协议
        protocol_input = dialog.locator("form div").filter(has_text="协议").get_by_placeholder("请选择", exact=True)
        select_if_not_match(protocol_input, protocol, exact=True)

        # 如果选择常用协议，需要进一步选择协议类型
        if protocol == "选择常用协议" and protocol_type:
            protocol_type_input = dialog.get_by_placeholder("请选择协议")
            select_if_not_match(protocol_type_input, protocol_type, exact=False)

            # 处理端口配置（定制TCP/UDP协议时需要）
            if "TCP" in protocol_type or "UDP" in protocol_type:
                port_type_input = dialog.locator("div").filter(has_text=re.compile(r"^打开端口")).get_by_placeholder("请选择")
                select_if_not_match(port_type_input, port_type, exact=True)

                # 填写端口
                if port_type == "端口范围" and port and "-" in port:
                    start_port, end_port = port.split("-")
                    start_loc = dialog.locator("div").filter(has_text=re.compile(r"^起始端口号$")).get_by_role("textbox")
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
        select_if_not_match(direction_input, direction, exact=False)

        # 选择远程类型
        remote_type_input = dialog.locator("div").filter(has_text=re.compile(r"^远程")).get_by_placeholder("请选择")
        select_if_not_match(remote_type_input, remote_type, exact=True)

        # 选择IP版本
        ip_version_input = dialog.get_by_placeholder("请选择IP版本")
        select_if_not_match(ip_version_input, ip_version, exact=False)

        # 根据远程类型填写对应值
        if remote_type == "安全组" and remote_sg:
            dialog.locator("form div").filter(has_text="安全组").get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=remote_sg).click()
        elif remote_type == "CIDR" and cidr:
            dialog.get_by_placeholder(re.compile(r"非必填.*如.*0\.0\.0\.0")).fill(cidr)

        # 填写描述
        if description:
            dialog.locator("textarea").fill(description)

        # 点击确定
        dialog.get_by_text("确定").click()
        self.assert_popup_success("新建安全组规则成功")
        self.logger.info(f"安全组规则创建完成: {sg_name} -> {protocol} {direction}")

    def sg_rule_delete(self, sg_name, direction="入口"):
        """删除安全组规则（为了简化，默认删除指定方向的第一条可见规则）
        
        Args:
            sg_name: 安全组名称
            direction: "入口" 或者是 "出口"
        """
        # 如果没有在详情页，则进入安全组详情
        if not hasattr(self, '_in_detail') or not self._in_detail:
            self.goto_sg_detail(sg_name)
            self._in_detail = True
        
        # 点击第一条规则的删除按钮
        self.get_by_role("row").nth(1).get_by_text("删除").click()
        # 等待页面重载
        self.dialog_confirm.click()

        self.logger.info(f"已删除 {sg_name} 的第一条 {direction} 规则")

    def _get_rules_data(self, sg_name):
        """获取指定安全组的所有规则"""
        self.goto_service("安全组")
        self.goto_sg_detail(sg_name)
        return self.sg_get_all_rules()


    def sg_get_all_rules(self, sg_name=None):
        """获取安全组规则详情

        Args:
            sg_name: 可选，安全组名称。如果提供，会先导航到该安全组详情页；
                    如果不提供，则获取当前页面的规则

        Returns:
            list: 包含每条规则详细字典的列表，并按 方向、类型、协议 进行了统一排序
        """
        # 如果指定了安全组名称，先导航到详情页
        if sg_name:
            self.goto_service("安全组")
            self.goto_sg_detail(sg_name)

        rules = []
        headers = self.table_headers
        row_locators = self.table_rows

        for i in range(len(row_locators)):
            row_locator = row_locators[i]
            cell_contents = self._get_cell_contents(row_locator)
            row_data = dict(zip(headers, cell_contents))

            # 提取需要的字段。表头可能因为包含筛选/下拉带有额外字符，我们通过遍历keys进行子串匹配寻找真实值
            rule_data = {}
            for key, val in row_data.items():
                if "方向" in key:
                    rule_data["方向"] = val
                elif "以太网类型" in key:
                    rule_data["以太网类型"] = val
                elif "IP协议" in key:
                    rule_data["IP协议"] = val
                elif "端口范围" in key:
                    rule_data["端口范围"] = val
                elif "远端IP前缀" in key:
                    rule_data["远端IP前缀"] = val
                elif "远端安全组" in key:
                    rule_data["远端安全组"] = val
                elif "描述" in key:
                    rule_data["描述"] = val
            rules.append(rule_data)

        # 为了比较，需要对列表里的字典按固定某种排序组合
        rules.sort(key=lambda x: f"{x.get('方向', '')}-{x.get('以太网类型', '')}-{x.get('IP协议', '')}")
        self.logger.info(f"成功获取到的{sg_name}安全组规则列表: {rules}")
        return rules
