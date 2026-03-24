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
        self.wait_for_page_ready()
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
        self.wait_for_page_ready()
        
        if tab_name:
            self.get_by_role("tab", name=tab_name).click()
            self.wait_for_page_ready()
            
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

        self.wait_for_page_ready()

        self.get_by_text("新建", exact=True).click()

        dialog = self.get_by_role("dialog")
        for subnet in subnets:
            row = dialog.get_by_role("row").filter(has_text=subnet)
            row.locator(".el-checkbox").first.click()

        dialog.get_by_text("确定").click()

        # 返回列表
        self.locator("#detail_container i").first.click()
        self.wait_for_page_ready()
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
            self.click_action(subnet, "解关联子网", t_type="body")
            self.dialog_confirm.click()

        self.wait_for_page_ready()
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

    def acl_rule_create(self, acl_name, direction="入方向", ip_version="IPv4", policy="允许", 
                        protocol="TCP", source_ip=None, source_port=None, 
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
            self.wait_for_page_ready()
        
        self.get_by_text("新建", exact=True).click()
        
        dialog_name = f"新建{tab_name}"
        dialog = self.get_by_label(dialog_name)
        
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
            
        # 确定
        dialog.get_by_text("确定").click()
        
        # 根据录制脚本，点击确定之后通过点击Close关闭弹窗（连续创建模式弹出不自动关闭现象）
        self.page.wait_for_timeout(1000)
        self.close_dialog_if_exists()
        
        self.logger.info(f"网络ACL创建规则完成: {acl_name} -> {tab_name} ({policy} {protocol} {ip_version})")

    def acl_rule_delete(self, acl_name, direction="入方向", detail_mode=False):
        """删除网络ACL规则"""
        
        tab_name = f"{direction}规则"
        
        if not detail_mode:
            self.goto_acl_detail(acl_name, tab_name=tab_name)
        else:
            self.get_by_role("tab", name=tab_name).click()
            self.wait_for_page_ready()
        
        target_row = self.get_by_role("row").filter(has=self.get_by_text("删除")).first
        target_row.get_by_text("删除").click()
        self.dialog_confirm.click()
        
        self.logger.info(f"网络ACL删除规则完成: {acl_name} -> {tab_name}")