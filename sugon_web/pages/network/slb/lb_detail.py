import re

from sugon_web.common.playwright import expect
from .slb_detail import SlbDetailMixin


class LbDetailMixin(SlbDetailMixin):
    """LB监听器详情页。"""

    def goto_lb_pool_detail(self, lb_name, pool_name, force=False):
        """进入指定监听器下资源池详情页"""
        # 若当前已在目标资源池详情页，避免重复导航导致 select_lb_in_left_list 在错误页面上执行
        current_url = self.page.url
        if not force and "resource-pool-detail" in current_url and pool_name in current_url:
            self.logger.info(f"当前已在资源池详情页，跳过重复导航: {pool_name}")
            return

        self.goto_lb_pool_tab(lb_name)
        active_pane = self._get_lb_nested_tabs().locator(".el-tab-pane:not([aria-hidden='true'])").last
        pool_row = active_pane.locator(".el-table__body-wrapper tr").filter(has_text=pool_name).first
        expect(pool_row).to_be_visible(timeout=5000)

        clickable = pool_row.locator("a", has_text=pool_name).first
        if clickable.count() == 0:
            clickable = pool_row.get_by_text(pool_name).first
        clickable.click()
        self.logger.info(f"进入监听器 {lb_name} 下资源池详情成功: {pool_name}")

    def _get_lb_detail_active_pane(self):
        """获取监听器详情页当前激活的右侧内容区域"""
        nested_tabs = self._get_lb_nested_tabs()
        nested_tabs.get_by_role("tab", name="详情").click()
        active_pane = nested_tabs.locator(".el-tab-pane:not([aria-hidden='true'])").last
        active_pane.get_by_text("基本信息", exact=True).wait_for(state="visible", timeout=5000)
        return active_pane

    def _open_lb_basic_info_edit(self, lb_name, edit_icon_index):
        """打开监听器详情页"基本信息"区域对应位置的编辑入口。"""
        self.goto_lb_detail(lb_name)
        active_pane = self._get_lb_detail_active_pane()
        edit_icons = active_pane.locator(".el-icon-edit:visible")
        expect(edit_icons.nth(edit_icon_index)).to_be_visible(timeout=5000)
        edit_icons.nth(edit_icon_index).click()
        self.page.wait_for_timeout(300)
        return active_pane

    def _confirm_lb_inline_edit(self, active_pane):
        """提交监听器详情页的内联编辑。"""
        confirm_icons = active_pane.locator(".el-icon-check:visible")
        if confirm_icons.count() > 0:
            confirm_icons.first.click()
        else:
            input_box = active_pane.locator("input:visible, textarea:visible").first
            input_box.press("Enter")
        self.page.wait_for_timeout(500)

    def lb_edit_basic_info(self, lb_name, field, **kwargs):
        """修改监听器基本信息

        Args:
            lb_name: 监听器名称
            field: 要修改的字段，支持 "name"、"description"、"port"、"access_control"
            **kwargs: 对应字段的修改参数
        """
        if field == "name":
            new_name = kwargs.get("new_name")
            active_pane = self._open_lb_basic_info_edit(lb_name, 0)
            name_input = active_pane.locator("input:visible").first
            expect(name_input).to_be_visible(timeout=3000)
            name_input.fill(new_name)
            self._confirm_lb_inline_edit(active_pane)
            self.logger.info(f"监听器名称修改完成: {lb_name} -> {new_name}")

        elif field == "description":
            new_desc = kwargs.get("new_desc")
            active_pane = self._open_lb_basic_info_edit(lb_name, 3)
            desc_input = active_pane.locator("textarea:visible, input:visible").first
            expect(desc_input).to_be_visible(timeout=3000)
            desc_input.fill(new_desc)
            self._confirm_lb_inline_edit(active_pane)
            self.logger.info(f"监听器描述修改完成: {lb_name} -> {new_desc}")

        elif field == "port":
            protocol = kwargs.get("protocol")
            port = kwargs.get("port")
            if protocol is None and port is None:
                raise ValueError("protocol 和 port 不能同时为空")

            self._open_lb_basic_info_edit(lb_name, 1)
            dialog = self._find_element([
                self.get_by_role("dialog", name="修改端口"),
                self.get_by_role("dialog").filter(has_text="修改端口"),
            ], "修改端口对话框", timeout=5000)

            expect(dialog).to_be_visible(timeout=5000)
            if protocol:
                expect(dialog).to_contain_text(protocol)
            if port is not None:
                port_input = dialog.get_by_role("spinbutton").first
                expect(port_input).to_be_visible(timeout=3000)
                port_input.fill(str(port))

            dialog.get_by_text("确定", exact=True).click()
            self.page.wait_for_timeout(800)

            # 检查对话框是否仍然可见（前端校验阻止提交时对话框保持打开）
            if dialog.count() > 0 and dialog.is_visible():
                dialog.get_by_text("取消", exact=True).click()
                self.page.wait_for_timeout(300)
                self.logger.warning(
                    f"修改端口被拒绝（对话框未关闭）: {lb_name} -> {protocol}/{port}"
                )
            else:
                self.logger.info(f"监听器前端协议/端口修改完成: {lb_name} -> {protocol}/{port}")

        elif field == "access_control":
            enable = kwargs.get("enable", False)
            access_policy = kwargs.get("access_policy")
            ip_group = kwargs.get("ip_group")

            self._open_lb_basic_info_edit(lb_name, 2)
            dialog = self._find_element([
                self.get_by_role("dialog", name="设置访问控制"),
                self.get_by_role("dialog").filter(has_text="设置访问控制"),
            ], "设置访问控制对话框", timeout=5000)

            expect(dialog).to_be_visible(timeout=5000)
            acl_switch = dialog.get_by_role("switch")
            is_enabled = acl_switch.get_attribute("aria-checked") == "true"
            if is_enabled != enable:
                acl_switch.locator("span").click()
                self.page.wait_for_timeout(300)

            if enable:
                selects = dialog.get_by_placeholder("请选择")
                if access_policy:
                    selects.first.click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text=re.compile(rf"^{re.escape(access_policy)}$")
                    ).first.click()
                if ip_group:
                    selects = dialog.get_by_placeholder("请选择")
                    expect(selects.nth(1)).to_be_visible(timeout=3000)
                    selects.nth(1).click()
                    self.locator("div.el-select-dropdown:visible li").filter(
                        has_text=re.compile(rf"^{re.escape(ip_group)}$")
                    ).first.click()

            dialog.get_by_text("确定", exact=True).click()
            self.logger.info(
                f"监听器访问控制修改完成: {lb_name} -> enable={enable}, "
                f"access_policy={access_policy}, ip_group={ip_group}"
            )
        else:
            raise ValueError(f"不受支持的 field: {field}")

    def lb_edit_redirect_port(self, lb_name, redirect_port=None, enable=True):
        """修改监听器HTTP重定向端口。

        Args:
            lb_name: 监听器名称。
            redirect_port: 重定向端口，为None时只切换开关状态。
            enable: 是否启用HTTP重定向。
        """
        self.goto_lb_detail(lb_name)
        active_pane = self._get_lb_detail_active_pane()

        # 监听器详情页中，HTTP重定向端口的编辑图标位于 <p> 标签内，
        # 按 DOM 顺序第二个 p 内的 .el-icon-edit 即为目标（第一个是前端协议/端口）。
        edit_icon = active_pane.locator("p .el-icon-edit").nth(1)
        expect(edit_icon).to_be_visible(timeout=5000)
        edit_icon.click()

        dialog = self.get_by_role("dialog", name="修改HTTP重定向端口")
        expect(dialog).to_be_visible(timeout=5000)

        switch = dialog.locator(".el-switch").first
        is_checked = switch.get_attribute("aria-checked") == "true"
        if is_checked != enable:
            switch.click()
            self.page.wait_for_timeout(300)

        if enable and redirect_port is not None:
            port_input = dialog.get_by_role("spinbutton").first
            port_input.fill(str(redirect_port))

        dialog.get_by_text("确定", exact=True).click()
        self.logger.info(
            f"监听器 {lb_name} HTTP重定向端口修改完成: enable={enable}, port={redirect_port}"
        )

    def lb_forward_rule_create(self, slb_name, lb_name, rule_name, condition_type,
                               judge_condition, condition_value, forward_pool_name):
        """在监听器下创建转发规则（L7策略）。

        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            rule_name: 规则名称
            condition_type: 条件类型，如"域名"、"URL路径"
            judge_condition: 判断条件，如"精确匹配相等"
            condition_value: 条件值，如域名或URL
            forward_pool_name: 转发目标资源池名称
        """
        # 先导航到SLB详情页的监听器tab，确保页面状态正确
        self.goto_slb_detail(slb_name, tab_name="监听器")
        self.page.wait_for_timeout(3000)
        # 进入转发规则tab
        self.goto_lb_detail(lb_name, tab_name="转发规则")
        self.page.wait_for_timeout(3000)

        # 点击"插入新规则"按钮
        insert_btn = self.get_by_text("插入新规则").first
        expect(insert_btn).to_be_visible(timeout=5000)
        insert_btn.click()

        # 等待插入表单出现（注意：前端实际类名为 list-group-item-opeartion）
        form_container = self.locator(".list-group-item-opeartion").first
        expect(form_container).to_be_visible(timeout=5000)

        # 1. 填写规则名称
        form_container.get_by_placeholder("请输入规则名称").fill(rule_name)

        # 2. 选择条件类型（"如果"区域）
        left_section = form_container.locator(".form-left").first
        condition_input = left_section.locator("input[placeholder='请选择条件类型']").first
        expect(condition_input).to_be_visible(timeout=10000)
        condition_input.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"{re.escape(condition_type)}")
        ).first.click()
        # 等待Vue条件渲染更新，显示判断条件和输入框
        self.page.wait_for_timeout(1500)

        # 3. 选择判断条件（judge_condition，如"精确匹配相等"）
        # 条件类型选择后，form-left区域出现 placeholder="请选择动作类型" 的下拉框
        judge_input = left_section.locator("input[placeholder='请选择动作类型']").first
        if judge_input.count() > 0 and judge_input.is_visible():
            judge_input.click()
            self.locator("div.el-select-dropdown:visible li").filter(
                has_text=re.compile(rf"{re.escape(judge_condition)}")
            ).first.click()
            self.page.wait_for_timeout(500)

        # 4. 填写条件值
        if condition_type == "域名":
            form_container.get_by_placeholder("请输入域名").fill(condition_value)
        elif condition_type == "URL路径":
            form_container.get_by_placeholder("请输入URL路径").fill(condition_value)

        # 5. 选择动作类型（"那么"区域，先选"转发至"）
        right_section = form_container.locator(".form-right").first
        action_input = right_section.locator("input[placeholder='请选择动作类型']").first
        expect(action_input).to_be_visible(timeout=10000)
        action_input.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text="转发至"
        ).first.click()
        # 等待Vue渲染出"转发至"选择框
        self.page.wait_for_timeout(1500)

        # 6. 选择转发目标资源池
        forward_input = right_section.locator("input[placeholder='请选择转发至']").first
        expect(forward_input).to_be_visible(timeout=10000)
        forward_input.click()
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"{re.escape(forward_pool_name)}")
        ).first.click()

        # 7. 点击保存
        form_container.locator(".btn-box").get_by_text("保存", exact=True).click()
        self.logger.info(
            f"转发规则创建完成: {rule_name}, 条件={condition_type} {judge_condition} {condition_value}, "
            f"转发至={forward_pool_name}"
        )

    def lb_forward_rule_delete(self, slb_name, lb_name, rule_name):
        """删除监听器下的转发规则。

        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            rule_name: 转发规则名称
        """
        self.goto_slb_detail(slb_name, tab_name="监听器")
        self.page.wait_for_timeout(3000)
        self.goto_lb_detail(lb_name, tab_name="转发规则")
        self.page.wait_for_timeout(3000)

        # 转发规则列表使用 draggable list，每个规则卡片有删除图标
        rule_item = self.locator(".list-group-item-box").filter(
            has_text=re.compile(rf"{re.escape(rule_name)}")
        ).first
        expect(rule_item).to_be_visible(timeout=5000)
        rule_item.locator(".el-icon-delete").first.click()
        self.dialog_confirm.click()
        self.logger.info(f"转发规则删除完成: {rule_name}")

    def lb_pool_delete(self, slb_name, lb_name, pool_name):
        """删除监听器下的非默认资源池。

        默认资源池无法直接删除，需通过删除监听器级联删除。
        本方法仅用于删除额外创建的非默认资源池。

        Args:
            slb_name: 负载均衡名称
            lb_name: 监听器名称
            pool_name: 资源池名称
        """
        self.goto_slb_detail(slb_name, tab_name="监听器")
        self.page.wait_for_timeout(3000)
        self.goto_lb_pool_tab(lb_name)
        self.page.wait_for_timeout(3000)

        # 资源池列表为表格形式，使用 click_action 删除
        self.click_action(pool_name, "删除")
        self.dialog_confirm.click()
        self.logger.info(f"资源池删除完成: {pool_name}")
