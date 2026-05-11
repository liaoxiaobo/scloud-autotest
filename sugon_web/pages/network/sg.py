import re

from sugon_web.common.base import BasePage, submenu


class SgMixin(BasePage):
    """安全组页面类"""

    @staticmethod
    def _normalize_rule_text(value):
        """统一规则字段文本，便于跨读取/删除逻辑做一致比较。"""
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _get_sg_rule_table(self):
        """定位安全组详情页中的规则表。"""
        active_tabs = self.locator(".el-tab-pane:not([aria-hidden='true']) .el-table:visible").all()
        candidate_tables = active_tabs or self.locator("#cloud-container-content .el-table:visible").all()

        for table in candidate_tables:
            try:
                headers = table.locator(".el-table__header-wrapper th").all_text_contents()
                if any("方向" in header for header in headers) and any("协议" in header for header in headers):
                    self.logger.info(f"已定位安全组规则表，表头: {headers}")
                    return table, headers
            except Exception as exc:
                self.logger.debug(f"检查安全组规则表候选项失败: {exc}")
                continue

        raise AssertionError("未找到安全组详情规则表")

    def _build_rule_data(self, headers, cell_contents):
        """将页面行数据按规则字段做标准化映射。"""
        row_data = dict(zip(headers, cell_contents))
        rule_data = {}

        for key, val in row_data.items():
            normalized_value = self._normalize_rule_text(val)
            if "方向" in key:
                rule_data["方向"] = normalized_value
            elif "以太网类型" in key:
                rule_data["以太网类型"] = normalized_value
            elif "IP协议" in key:
                rule_data["IP协议"] = normalized_value
            elif "端口范围" in key:
                rule_data["端口范围"] = normalized_value
            elif "远端IP前缀" in key:
                rule_data["远端IP前缀"] = normalized_value
            elif "远端安全组" in key:
                rule_data["远端安全组"] = normalized_value
            elif "描述" in key:
                rule_data["描述"] = normalized_value

        return rule_data

    def _get_rule_rows_with_data(self):
        """获取当前规则表中的页面行及其结构化规则数据。"""
        rules_table, headers = self._get_sg_rule_table()
        row_locators = rules_table.locator(".el-table__body-wrapper tr")
        rows = []

        for i in range(row_locators.count()):
            row_locator = row_locators.nth(i)
            cell_contents = self._get_cell_contents(row_locator)
            rows.append((row_locator, self._build_rule_data(headers, cell_contents)))

        return rows

    def _rule_matches(self, actual_rule, expected_rule):
        """判断页面规则是否与期望规则匹配。"""
        for key, expected_value in expected_rule.items():
            expected_text = self._normalize_rule_text(expected_value)
            if not expected_text:
                continue
            if self._normalize_rule_text(actual_rule.get(key)) != expected_text:
                return False
        return True

    @submenu("安全组")
    def sg_create(self, name, desc=None):
        """创建安全组

        Args:
            name: 安全组名称
            desc: 安全组描述
        """
        self.btn_create.click()
        dialog = self.get_by_label("新建安全组")
        dialog.locator("input[type=\"text\"]").fill(name)
        if desc:
            dialog.locator("textarea").fill(desc)
        dialog.get_by_text("确定").click()
        self.assert_popup_success("新建安全组成功")

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
            self.click_action(sg_names, "删除")

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
        self.click_action(sg_name, "编辑")
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
        self.click_action(sg_name, "克隆")
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
        self.page.wait_for_timeout(1000)  # 确保列表刷新完毕
        self.logger.info("重置安全组搜索条件完成")

    @submenu("安全组")
    def goto_sg_detail(self, sg_name):
        """进入安全组详情页面

        Args:
            sg_name: 安全组名称
        """
        self.get_by_text(sg_name, exact=True).click()
        self.page.wait_for_url("**/security-group-detail/**")
        self.wait_for_page_ready()
        self.logger.info(f"进入安全组{sg_name}详情页")

    def select_all_rows(self):
        """公共方法: 勾选表格表头中的全选复选框"""
        # 定位表头中的复选框
        header_checkbox = self.locator("#cloud-container-content .el-table__header-wrapper:visible .el-checkbox").first
        if header_checkbox.count() > 0:
            # 如果没选中则点击
            if not header_checkbox.is_checked():
                header_checkbox.click()
                self.logger.info("已勾选表头全选复选框")
        else:
            self.logger.warning("未找到表头全选复选框")

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

    def sg_rule_create(self, sg_name, protocol="所有", direction="出口",
                       remote_type="CIDR", ip_version="IPv4",
                       remote_sg=None, description=None,
                       protocol_type=None, protocol_code=None,
                       port_type=None, port=None, cidr=None, from_list=True, detail_mode=False):
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
            self.goto_submenu("安全组")
            self.click_action(sg_name, "创建规则")
        elif detail_mode:
            # 在详情页/页签中直接创建
            self.btn_create.click()
        else:
            # 进入安全组详情
            self.goto_sg_detail(sg_name)

            # 点击创建规则按钮
            self.btn_create.click()

        # 获取创建规则弹窗
        dialog = self.get_by_role("dialog", name="创建规则")

        # 选择协议
        protocol_input = dialog.locator("form div").filter(has_text="协议").get_by_placeholder("请选择", exact=True)
        self.select_if_not_match(protocol_input, protocol, exact=True)

        # 如果选择常用协议，需要进一步选择协议类型
        if protocol == "选择常用协议" and protocol_type:
            protocol_type_input = dialog.get_by_placeholder("请选择协议")
            protocol_type_input.click()  # 确保下拉框展开
            protocol_type_input.fill(protocol_type)
            self.locator("li:visible").filter(has_text=re.compile(f"^{protocol_type}$", re.IGNORECASE)).first.click()

            # 处理端口配置（定制TCP/UDP协议时需要）
            if "TCP" in protocol_type or "UDP" in protocol_type:
                port_type_input = dialog.locator("div").filter(has_text=re.compile(r"^打开端口")).get_by_placeholder("请选择")
                self.select_if_not_match(port_type_input, port_type, exact=True)

                # 填写端口
                if port_type == "端口范围" and port and "-" in port:
                    start_port, end_port = port.split("-")
                    start_loc = dialog.locator("div").filter(has_text=re.compile(r"^起始端口号$")).get_by_role("textbox")
                    start_loc.clear()
                    start_loc.fill(start_port.strip())
                    end_loc = dialog.locator("div").filter(has_text=re.compile(r"^终止端口号$")).get_by_role("textbox")
                    end_loc.clear()
                    end_loc.fill(end_port.strip())
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
            # 限制在 .el-form-item 层级查找，避免匹配到包含整个表单的外层 div
            dialog.locator(".el-form-item").filter(has_text=re.compile(r"^安全组")).get_by_placeholder("请选择").click()
            self.locator("li:visible").filter(has_text=remote_sg).first.click()
        elif remote_type == "CIDR" and cidr:
            # 兼容 IPv4 (非必填 如：0.0.0.0) 和 IPv6 (非必填 如：2000:c000::/64)
            dialog.get_by_placeholder(re.compile(r"^非必填.*如：")).fill(cidr)

        # 填写描述
        if description:
            dialog.locator("textarea").fill(description)

        # 点击确定
        dialog.get_by_text("确定").click()

        self.assert_popup_success("新建安全组规则成功")

        self.logger.info(
            f"安全组规则创建完成: sg={sg_name}, 方向={direction}, 协议={protocol_type or protocol}, "
            f"远程={remote_type}{f', CIDR={cidr}' if remote_type == 'CIDR' and cidr else ''}"
            f"{f', 端口={port}' if port else ''}{f', 描述={description}' if description else ''}"
        )

    def sg_rule_delete(self, sg_name, direction="入口", detail_mode=False, rule_filter=None):
        """删除安全组规则

        Args:
            sg_name: 安全组名称
            direction: "入口" 或者是 "出口"
            detail_mode: 是否已在详情页中
            rule_filter: 可选，按结构化规则字段精确过滤目标规则
        """
        # 进入安全组详情
        if not detail_mode:
            self.goto_sg_detail(sg_name)

        target_row = None
        target_rule = None
        expected_direction = self._normalize_rule_text(direction)

        for attempt in range(3):
            for row_locator, row_rule in self._get_rule_rows_with_data():
                if self._normalize_rule_text(row_rule.get("方向")) != expected_direction:
                    continue
                if rule_filter and not self._rule_matches(row_rule, rule_filter):
                    continue
                target_row = row_locator
                target_rule = row_rule
                break

            if target_row:
                break

            self.logger.warning(f"第{attempt + 1}次未定位到方向为 {direction} 的规则行，等待页面稳定后重试")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(500)

        if target_row is None:
            current_rules = self.sg_get_all_rules()
            self.logger.warning(
                f"未找到方向为 {direction} 的规则行, 过滤条件={rule_filter}, 当前规则={current_rules}"
            )
            return False

        # 获取该行的所有文本信息
        row_text = " | ".join(target_row.inner_text().split())
        self.logger.info(f"准备删除[{sg_name}]的一条[{direction}]规则: {target_rule or row_text}")

        # 点击该行的删除按钮
        target_row.get_by_text("删除").click()

        # 确认删除
        self.dialog_confirm.click()

        self.logger.info(f"已删除 {sg_name} 的一条规则: {row_text}")
        return True

    def sg_rule_delete_all_by_direction(self, sg_name, direction="入口", detail_mode=False):
        """删除指定方向的所有安全组规则。"""
        if not detail_mode:
            self.goto_sg_detail(sg_name)

        while True:
            rules = self.sg_get_all_rules()
            target_rules = [rule for rule in rules if rule["方向"] == direction]
            if not target_rules:
                break

            deleted = self.sg_rule_delete(
                sg_name,
                direction=direction,
                detail_mode=True,
                rule_filter=target_rules[0],
            )
            if not deleted:
                raise AssertionError(f"存在方向为 {direction} 的规则，但未能在页面表格中定位到可删除的行")

            self.wait_for_page_ready()

        self.logger.info(f"已清空 {sg_name} 的所有[{direction}]规则")

    def sg_rule_restore_defaults(self, sg_name):
        """恢复安全组规则到默认状态 (出口 IPv4 所有, 出口 IPv6 所有)"""
        self.goto_sg_detail(sg_name)

        # 批量删除所有现有规则(当前实现只删除第一页的规则)
        if len(self.table_rows) > 0:
            self.select_all_rows()
            self.btn_batch_delete.click()
            self.dialog_confirm.click()
            self.logger.info(f"已批量清理 {sg_name} 的所有现有规则")
            rules = self.sg_get_all_rules()
            assert len(rules) == 0, "安全组规则列表未全部删除"
        else:
            self.logger.info(f"安全组 {sg_name} 当前无规则，无需清理")

        # 重新创建默认两条规则
        # 出口, IPv6, 所有协议
        self.sg_rule_create(
            sg_name=sg_name,
            protocol="所有",
            direction="出口",
            remote_type="CIDR",
            ip_version="IPv6",
        )
        # 出口, IPv4, 所有协议
        self.sg_rule_create(
            sg_name=sg_name,
            protocol="所有",
            direction="出口",
            remote_type="CIDR",
            ip_version="IPv4"
        )

        self.logger.info(f"安全组 {sg_name} 规则已重置为默认")

    def _get_rules_data(self, sg_name):
        """获取指定安全组的所有规则"""
        return self.sg_get_all_rules(sg_name)

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
            self.goto_sg_detail(sg_name)

        rules = []
        for _, rule_data in self._get_rule_rows_with_data():
            rules.append(rule_data)

        # 为了比较，需要对列表里的字典按固定某种排序组合
        rules.sort(key=lambda x: f"{x.get('方向', '')}-{x.get('以太网类型', '')}-{x.get('IP协议', '')}")
        self.logger.info(f"成功获取到的{sg_name}安全组规则列表: {rules}")
        return rules

    def _resolve_expected_ports(self, params, selected_vms):

        ports = params["ports"]
        if isinstance(ports, list):
            return ports[:len(selected_vms)]
        return [ports] * len(selected_vms)
