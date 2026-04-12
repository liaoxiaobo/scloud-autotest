import re

from sugon_web.common.base import BasePage, submenu


class AclPage(BasePage):
    """
    网络ACL页面
    """

    @submenu("网络ACL")
    def acl_create(self, name, desc=None):
        """创建网络ACL

        Args:
            name: ACL名称
            desc: ACL描述
        """
        self.btn_create.click()
        dialog = self.get_by_label("新建网络ACL")
        dialog.locator("input[type=\"text\"]").fill(name)
        if desc:
            dialog.locator("textarea").fill(desc)
        dialog.get_by_text("确定").click()
        self.assert_popup_success("新建网络ACL成功")

    @submenu("网络ACL")
    def acl_delete(self, acl_name):
        """删除网络ACL，支持单个操作

        Args:
            acl_name: 网络ACL名称（字符串）
        """

        self.click_action(acl_name, "删除")

        # 确认删除
        self.dialog_confirm.click()

    @submenu("网络ACL")
    def acl_search(self, acl_name):
        """搜索网络ACL"""
        self.search(acl_name)

    def acl_search_reset(self):
        """重置搜索条件"""
        self.btn_reset.click()
        self.page.wait_for_timeout(1000)  # 确保列表刷新完毕
        self.logger.info("重置网络ACL搜索条件完成")

    @submenu("网络ACL")
    def goto_acl_detail(self, acl_name, tab_name=None):
        """进入网络ACL详情页面

        Args:
            acl_name: 网络ACL名称
            tab_name: 详情页内的页签名称，例如 "入方向规则"、"出方向规则"、"关联子网"
        """
        self.get_by_text(acl_name, exact=True).nth(1).click()
        
        if tab_name:
            self.get_by_role("tab", name=tab_name).click()
            
        self.logger.info(f"进入网络ACL {acl_name} 详情页" + (f"，并切换至 {tab_name} 页签" if tab_name else ""))

    @submenu("网络ACL")
    def acl_edit(self, acl_name, new_name=None, new_desc=None):
        """修改网络ACL

        Args:
            acl_name: 原网络ACL名称
            new_name: 新名称
            new_desc: 新描述
        """
        try:
            self.click_action(acl_name, "修改")
        except:
            self.click_action(acl_name, "修改")

        dialog = self.get_by_role("dialog", name="修改网络ACL")
        if new_name:
            name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
            name_input.click()
            name_input.fill(new_name)
        if new_desc:
            dialog.locator("textarea").click()
            dialog.locator("textarea").fill(new_desc)
        dialog.get_by_text("确定").click()
        self.logger.info(f"修改网络ACL完成: {acl_name}")

    @submenu("网络ACL")
    def acl_enable(self, acl_name):
        """开启网络ACL"""
        # 先检查acl列表状态，如果是已开启，则不操作
        if self.get_row_data(acl_name).get("状态") == "开启":
            self.logger.info(f"网络ACL {acl_name} 已开启")
            return
        self.click_action(acl_name, "开启")
        self.dialog_confirm.click()

        self.logger.info(f"开启网络ACL完成: {acl_name}")

    @submenu("网络ACL")
    def acl_disable(self, acl_name):
        """关闭网络ACL"""
        if self.get_row_data(acl_name).get("状态") == "关闭":
            self.logger.info(f"网络ACL {acl_name} 已关闭")
            return
        self.click_action(acl_name, "关闭")

        self.dialog_confirm.click()
        self.logger.info(f"关闭网络ACL完成: {acl_name}")

    @submenu("网络ACL")
    def acl_associate_subnet(self, acl_name, subnets):
        """关联子网

        Args:
            acl_name: 网络ACL名称
            subnets: 子网名称或子网名称列表
        """
        if isinstance(subnets, str):
            subnets = [subnets]

        self.click_action(acl_name, "关联子网")

        self.get_by_text("新建", exact=True).click()

        dialog = self.get_by_role("dialog")
        for subnet in subnets:
            row = dialog.get_by_role("row").filter(has_text=subnet)
            row.locator(".el-checkbox").first.click()

        dialog.get_by_text("确定").click()

        # 返回列表
        self.locator("#detail_container i").first.click()
        self.logger.info(f"网络ACL {acl_name} 关联子网成功: {subnets}")

    @submenu("网络ACL")
    def acl_disassociate_subnet(self, acl_name, subnets):
        """解关联子网

        Args:
            acl_name: 网络ACL名称
            subnets: 子网名称或子网名称列表
        """
        if isinstance(subnets, str):
            subnets = [subnets]

        # 进入到网络ACL详情页面，并切换至关联子网页签
        self.goto_acl_detail(acl_name, tab_name="关联子网")

        for subnet in subnets:
            self.click_action(subnet, "解关联子网")
            self.dialog_confirm.click()

        self.logger.info(f"网络ACL {acl_name} 解关联子网成功: {subnets}")

    @submenu("网络ACL")
    def acl_batch_enable(self, acl_names):
        """批量开启网络ACL"""
        self.select_rows_by_names(acl_names)
        self.get_by_role("button", name="批量操作").click()
        self.get_by_text("批量开启").click()
        
        dialog = self.get_by_label("开启")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")
            
        dialog.get_by_text("确定", exact=True).click()
        
        # 处理如果有ACL已经是开启状态导致弹窗无法关闭（按钮置灰或报错）
        self.page.wait_for_timeout(1000)
        if dialog.is_visible():
            self.logger.warning(f"发现不能重复开启或状态冲突的 ACL，弹窗仍显示，执行取消以关闭弹窗: {acl_names}")
            try:
                dialog.get_by_text("取消", exact=True).click()
            except:
                dialog.locator(".cloud-button-btn").last.click()

        self.logger.info(f"批量开启网络ACL完成: {acl_names}")

    @submenu("网络ACL")
    def acl_batch_disable(self, acl_names):
        """批量关闭网络ACL"""
        self.select_rows_by_names(acl_names)
        self.get_by_role("button", name="批量操作").click()
        self.get_by_text("批量关闭").click()
        
        dialog = self.get_by_label("关闭")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")
            
        btn_ok = dialog.get_by_text("确定", exact=True)
        if btn_ok.is_visible():
            btn_ok.click()
        else:
            dialog.locator(".cloud-button-btn").first.click()
            
        # 处理重复关闭的场景
        self.page.wait_for_timeout(1000)
        if dialog.is_visible():
            self.logger.warning(f"发现不能重复关闭或状态冲突的 ACL，尝试点击取消关闭弹窗: {acl_names}")
            try:
                btn_cancel = dialog.get_by_text("取消", exact=True)
                if btn_cancel.is_visible():
                    btn_cancel.click()
                else:
                    dialog.locator(".cloud-button-btn").last.click()
            except:
                pass

        self.logger.info(f"批量关闭网络ACL完成: {acl_names}")

    @submenu("网络ACL")
    def acl_batch_delete(self, acl_names):
        """批量删除网络ACL"""
        self.select_rows_by_names(acl_names)
        self.get_by_role("button", name="批量操作").click()
        self.get_by_text("批量删除").click()
        
        dialog = self.locator("#cloud-container-content")
        btn_ok = dialog.get_by_text("确定", exact=True)
        if btn_ok.is_visible():
            btn_ok.click()
        else:
            self.dialog_confirm.click()
            
        self.logger.info(f"批量删除网络ACL完成: {acl_names}")

    def _fill_rule_form(self, dialog, ip_version=None, policy=None, protocol=None, 
                        source_ip=None, source_port=None, 
                        dest_ip=None, dest_port=None, description=None):
        """通用方法：填充 ACL 规则表单"""
        # 选择IP类型
        if ip_version:
            dialog.get_by_placeholder("请选择类型").click()
            self.locator("li:visible").filter(has_text=ip_version).click()
            
        # 选择策略
        if policy:
            dialog.get_by_placeholder("请选择策略").click()
            self.locator("li:visible").filter(has_text=policy).click()
            
        # 选择协议
        if protocol:
            dialog.locator("label").filter(has_text=re.compile(f"^{protocol}$", re.IGNORECASE)).click()

        # 填写源IP
        if source_ip is not None:
            src_ip_input = dialog.locator("form div").filter(has_text="源IP地址").locator("textarea, input[type='text']").first
            src_ip_input.click()
            src_ip_input.fill(source_ip)

        # 填写目的IP
        if dest_ip is not None:
            dest_ip_input = dialog.locator("form div").filter(has_text="目的IP地址").locator("textarea, input[type='text']").first
            dest_ip_input.click()
            dest_ip_input.fill(dest_ip)

        if protocol in ["TCP", "UDP"]:
            # 填写源端口
            if source_port is not None:
                src_port_input = dialog.locator("form div").filter(has_text="源端口").locator("textarea, input[type='text']").first
                src_port_input.click()
                src_port_input.fill(source_port)
                
            # 填写目的端口
            if dest_port is not None:
                dest_port_input = dialog.locator("form div").filter(has_text="目的端口").locator("textarea, input[type='text']").first
                dest_port_input.click()
                dest_port_input.fill(dest_port)
            
        # 描述
        if description is not None:
            desc_input = dialog.locator("div").filter(has_text=re.compile(r"^描述")).get_by_role("textbox")
            desc_input.click()
            desc_input.fill(description)

    def acl_rule_create(self, acl_name, direction="入方向", ip_version="IPv4", policy="允许", 
                        protocol="全部", source_ip=None, source_port=None,
                        dest_ip=None, dest_port=None, description=None, detail_mode=False):
        """创建网络ACL规则

        Args:
            acl_name: 网络ACL名称
            direction: 规则方向，"入方向" 或 "出方向"，默认"入方向"
            ip_version: IP版本，"IPv4" 或 "IPv6"
            policy: 策略，"允许" 或 "拒绝"
            protocol: 协议，"TCP", "UDP", "ICMP", "ALL", "ICMPV6" 等
            source_ip: 源IP地址
            source_port: 源端口
            dest_ip: 目的IP地址
            dest_port: 目的端口
            description: 描述
            detail_mode: 是否处于网络ACL详情页中
        """
        tab_name = f"{direction}规则"

        if not detail_mode:
            self.goto_acl_detail(acl_name, tab_name=tab_name)
        else:
            self.get_by_role("tab", name=tab_name).click()
        
        self.get_by_text("新建", exact=True).click()
        
        dialog_name = f"新建{tab_name}"
        dialog = self.get_by_label(dialog_name)
        
        self._fill_rule_form(dialog, ip_version, policy, protocol, source_ip, source_port, dest_ip, dest_port, description)
            
        # 确定
        dialog.get_by_text("确定", exact=True).click()
        
        
        self.logger.info(f"网络ACL创建规则完成: {acl_name} -> {tab_name} ({policy} {protocol} {ip_version})")

    def click_rule_action(self, option_text: str,
                          ip_version=None, policy=None, protocol=None, 
                          source_ip=None, source_port=None, 
                          dest_ip=None, dest_port=None):
        """
        点击规则的操作选项（兼容平铺按钮和“更多”下拉菜单隐藏的按钮）
        """
        target_row = self._get_rule_target_row(
            ip_version=ip_version, policy=policy, protocol=protocol, 
            source_ip=source_ip, source_port=source_port, 
            dest_ip=dest_ip, dest_port=dest_port
        )
        
        try:
            # 1. 尝试直接点击行内平铺可见的按钮
            option_btn = target_row.get_by_text(option_text, exact=True)
            for i in range(option_btn.count()):
                btn = option_btn.nth(i)
                if btn.is_visible() and btn.is_enabled():
                    btn.click()
                    self.logger.info(f"点击ACL规则平铺操作选项: {option_text}")
                    return
        except Exception as e:
            self.logger.debug(f"平铺操作按钮定位异常: {e}")

        # 2. 如果没找到，尝试在“更多”下拉菜单里寻找
        try:
            # 兼容"更多"可能是span/button的情况，只要包含该文本即可
            more_btn = target_row.get_by_text("更多", exact=True)
            if more_btn.count() > 0 and more_btn.is_visible():
                more_btn.hover()
                # 悬停后需要等待下拉菜单动画出现
                self.page.wait_for_timeout(1000)
                
                dropdown_selectors = [
                    ('[id^="dropdown-menu-"]', 'id'),
                    ('[class^="cloud-table-dropdown"]', 'class'),
                    ('.el-dropdown-menu', 'class')
                ]
                
                for selector, selector_type in dropdown_selectors:
                    try:
                        dropdown_menus = self.page.locator(selector)
                        menu_count = dropdown_menus.count()
                        if menu_count == 0:
                            continue
                        
                        # 从后往前遍历找最新弹出的可见菜单
                        for i in range(menu_count - 1, -1, -1):
                            menu = dropdown_menus.nth(i)
                            if menu.is_visible():
                                option = menu.get_by_text(option_text, exact=True)
                                if option.count() > 0:
                                    # 循环遍历选项防抖
                                    for j in range(option.count()):
                                        opt_btn = option.nth(j)
                                        if opt_btn.is_visible() and opt_btn.is_enabled():
                                            opt_btn.click()
                                            self.logger.info(f"点击ACL规则下拉操作选项: {option_text} (使用 {selector_type})")
                                            return
                    except Exception as e:
                        self.logger.debug(f"{selector_type} 下拉选择器失败: {e}")
                        continue
        except Exception as e:
            self.logger.debug(f"下拉菜单定位异常: {e}")

        raise Exception(f"未找到ACL规则的可用操作选项: {option_text}")

    def acl_rule_delete(self, acl_name, direction="入方向",
                        ip_version=None, policy=None, protocol=None, 
                        source_ip=None, source_port=None, 
                        dest_ip=None, dest_port=None):
        """删除网络ACL规则"""

        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)
        
        self.click_rule_action(
            option_text="删除", ip_version=ip_version, policy=policy,
            protocol=protocol, source_ip=source_ip, source_port=source_port,
            dest_ip=dest_ip, dest_port=dest_port
        )
        self.dialog_confirm.click()
        
        self.logger.info(f"网络ACL删除规则完成: {acl_name} -> {tab_name}")

    def _get_rule_target_row(self, ip_version=None, policy=None, 
                             protocol=None, source_ip=None, source_port=None, 
                             dest_ip=None, dest_port=None):
        """根据给定的匹配条件或行号获取包含规则操作的整行"""
        # 基础过滤：必须包含“删除”或“修改”文本的行，避免拿到表头或无关行
        rows = self.get_by_role("row").filter(has=self.locator("td").filter(has_text=re.compile(r"修改|删除")))
        
        if protocol == "全部":
            protocol = "all"
            
        # 逐层加过滤条件 (定位 td 中包含指定文本)
        filters = [
            ip_version,
            policy,
            re.compile(f"^{protocol}$", re.IGNORECASE) if protocol else None,
            source_ip,
            str(source_port) if source_port else None,
            dest_ip,
            str(dest_port) if dest_port else None
        ]
        
        for condition in filters:
            if condition:
                rows = rows.filter(has=self.locator("td").filter(has_text=condition))
        
        # 默认返回筛选后的第一条匹配
        return rows.first

    def acl_rule_edit(self, acl_name, direction="入方向",
                      match_ip_version=None, match_policy=None, match_protocol=None, 
                      match_source_ip=None, match_source_port=None, 
                      match_dest_ip=None, match_dest_port=None,
                      new_ip_version=None, new_policy=None, new_protocol=None, 
                      new_source_ip=None, new_source_port=None, 
                      new_dest_ip=None, new_dest_port=None, new_description=None):
        """修改网络ACL规则"""
        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)
            
        self.click_rule_action(
            option_text="修改", ip_version=match_ip_version, policy=match_policy,
            protocol=match_protocol, source_ip=match_source_ip, source_port=match_source_port,
            dest_ip=match_dest_ip, dest_port=match_dest_port
        )
        
        dialog_name = f"修改{tab_name}"
        dialog = self.get_by_label(dialog_name)
        
        self._fill_rule_form(dialog, new_ip_version, new_policy, new_protocol, new_source_ip, new_source_port, new_dest_ip, new_dest_port, new_description)
            
        # 确定
        dialog.get_by_text("确定", exact=True).click()
        
        self.logger.info(f"网络ACL修改规则完成: {acl_name} -> {tab_name}")

    def acl_rule_insert_before(self, acl_name, direction="入方向",
                               ip_version=None, policy=None, protocol=None, 
                               source_ip=None, source_port=None, 
                               dest_ip=None, dest_port=None, description=None):
        """向前插入网络ACL规则"""
        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)
            
        self.click_rule_action(
            option_text="向前插入规则", ip_version=ip_version, policy=policy,
            protocol=protocol, source_ip=source_ip, source_port=source_port,
            dest_ip=dest_ip, dest_port=dest_port
        )
        
        dialog = self.get_by_label("向前插入规则")
        
        self._fill_rule_form(dialog, ip_version, policy, protocol, source_ip, source_port, dest_ip, dest_port, description)
            
        # 确定
        dialog.get_by_text("确定", exact=True).click()
        
        self.logger.info(f"网络ACL向前插入规则完成: {acl_name} -> {tab_name}")

    def acl_rule_disable(self, acl_name, direction="入方向",
                         ip_version=None, policy=None, protocol=None, 
                         source_ip=None, source_port=None, 
                         dest_ip=None, dest_port=None):
        """关闭单个网络ACL规则"""
        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)
            
        self.click_rule_action(
            option_text="关闭", ip_version=ip_version, policy=policy,
            protocol=protocol, source_ip=source_ip, source_port=source_port,
            dest_ip=dest_ip, dest_port=dest_port
        )
        
        confirm_btn = self.page.locator(".el-message-box__btns .el-button--primary, .dialog-box-footer .cloud-button-btn:has-text('确定')").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        else:
            self.dialog_confirm.click()
            
        self.logger.info(f"网络ACL关闭规则完成: {acl_name} -> {tab_name}")

    def acl_rule_enable(self, acl_name, direction="入方向",
                        ip_version=None, policy=None, protocol=None, 
                        source_ip=None, source_port=None, 
                        dest_ip=None, dest_port=None):
        """开启单个网络ACL规则"""
        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)
            
        self.click_rule_action(
            option_text="开启", ip_version=ip_version, policy=policy,
            protocol=protocol, source_ip=source_ip, source_port=source_port,
            dest_ip=dest_ip, dest_port=dest_port
        )
        
        dialog = self.get_by_label("启用规则")
        dialog.get_by_text("确定", exact=True).click()
        
        self.logger.info(f"网络ACL开启规则完成: {acl_name} -> {tab_name}")

    def acl_rule_batch_operation(self, acl_name, direction="入方向", rule_matches=None, rules=None, operation="开启"):
        """批量操作网络ACL规则

        Args:
            acl_name: 网络ACL名称
            direction: 规则方向，"入方向" 或 "出方向"
            rule_matches: 规则匹配条件列表 (List of dict)
            rules: 同 rule_matches，为了兼容性
            operation: 操作名称，例如 "开启"、"关闭"、"删除"
        """
        tab_name = f"{direction}规则"
        self.goto_acl_detail(acl_name, tab_name=tab_name)

        target_rules = rule_matches or rules
        if not target_rules:
            self.logger.warning("未提供需要操作的规则列表")
            return

        # 遍历匹配规则并勾选
        for rule in target_rules:
            row = self._get_rule_target_row(**rule)
            # 点击复选框
            checkbox = row.locator(".el-checkbox")
            if checkbox.count() > 0:
                checkbox.first.click()
            else:
                # 兼容性：如果没找到 el-checkbox，尝试通过 cell 查找
                row.locator("td").first.click()

        # 点击批量操作
        self.get_by_role("button", name="批量操作").click()
        
        # 处理操作文本，如果没带“批量”，则补全
        op_text = operation if operation.startswith("批量") else f"批量{operation}"
        
        # 点击具体的批量操作项
        self.get_by_text(op_text, exact=True).click()

        # 处理确认弹窗
        # 批量删除和某些批量关闭会有确认框
        self.page.wait_for_timeout(1000)
        confirm_btn = self.page.locator(".el-message-box__btns .el-button--primary, .dialog-box-footer .cloud-button-btn:has-text('确定')").first
        if confirm_btn.is_visible():
            confirm_btn.click()
        
        self.logger.info(f"网络ACL规则{op_text}完成: {acl_name} -> {len(target_rules)} 条规则")