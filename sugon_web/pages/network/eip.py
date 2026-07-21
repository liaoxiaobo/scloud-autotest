import re

from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu


class EipMixin(BasePage):
    """弹性公网IP页面动作。"""

    @staticmethod
    def _get_ipv4_segment(ip: str):
        """返回 IPv4 的前三段，用于同网段匹配。"""
        match = re.fullmatch(r"((?:\d{1,3}\.){2}\d{1,3})\.\d{1,3}", ip or "")
        return match.group(1) if match else None

    def _get_eip_list(self):
        """获取当前列表中的弹性公网IP"""
        raw_values = self.get_column_data("IP地址")
        eips = []
        for value in raw_values:
            match = re.search(r"((?:\d{1,3}\.){3}\d{1,3})(?!\.)", value)
            if match:
                eips.append(match.group())
        return eips

    def _open_eip_allocate_dialog(self):
        """打开分配公网IP弹窗并返回弹窗定位器。"""
        self.get_by_text("分配公网IP").first.click()
        dialog = self.get_by_label("分配公网IP")
        expect(dialog).to_be_visible(timeout=8000)
        return dialog

    def _get_eip_allocate_ip_options(self, dialog):
        """获取分配公网IP弹窗中的可选IP列表。"""
        form_item = dialog.locator(".el-form-item").filter(has_text="IP").last
        ip_select = form_item.locator(".el-input").first
        expect(ip_select).to_be_visible(timeout=8000)
        ip_select.click()

        visible_ips = self.locator("body *").evaluate_all(
            """
            (elements) => {
                const isVisible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const result = [];
                for (const el of elements) {
                    if (!isVisible(el)) continue;
                    const text = (el.textContent || '').trim();
                    if (/^(?:\\d{1,3}\\.){3}\\d{1,3}$/.test(text) && !result.includes(text)) {
                        result.push(text);
                    }
                }
                return result;
            }
            """
        )
        current_ips = set(self._get_eip_list())
        current_segments = {
            self._get_ipv4_segment(ip) for ip in current_ips if self._get_ipv4_segment(ip)
        }
        candidate_ips = [
            ip
            for ip in visible_ips
            if ip not in current_ips
            and (
                not current_segments
                or self._get_ipv4_segment(ip) in current_segments
            )
        ]
        return candidate_ips or visible_ips

    @submenu("弹性公网IPv4")
    def get_eip_list(self):
        """获取当前列表中的弹性公网IP"""
        return self._get_eip_list()

    @submenu("弹性公网IPv4")
    def switch_eip_pool(self, pool_name: str = "public_net(基础版)"):
        """根据资源池名称切换左侧资源池。"""
        pool_panel = self.locator(".floating-ip-content-box")
        expect(pool_panel).to_be_visible(timeout=8000)

        active_item = pool_panel.locator(".left-box-list-item-active").first
        expect(active_item).to_be_visible(timeout=8000)
        current_pool = re.sub(r"\s+", " ", active_item.text_content() or "").strip()
        if current_pool == pool_name:
            self.logger.info(f"当前已在目标资源池，无需切换: {pool_name}")
            return current_pool

        search_input = pool_panel.get_by_placeholder("请输入资源池名称")
        expect(search_input).to_be_visible(timeout=8000)
        search_input.fill(pool_name)
        search_input.press("Enter")
        self.page.wait_for_timeout(300)

        pool_items = pool_panel.locator(".left-box-list .left-box-list-item")
        target_item = pool_items.filter(has_text=re.compile(rf"^{re.escape(pool_name)}$")).first
        if target_item.count() == 0:
            visible_pools = []
            for i in range(pool_items.count()):
                item_text = re.sub(r"\s+", " ", pool_items.nth(i).text_content() or "").strip()
                if item_text:
                    visible_pools.append(item_text)
            raise AssertionError(f"未找到资源池 '{pool_name}'，当前可见资源池: {visible_pools}")

        target_item.click()
        expect(target_item).to_have_class(re.compile(r"left-box-list-item-active"), timeout=10000)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(500)
        self.logger.info(f"切换资源池成功: {current_pool} -> {pool_name}")
        return pool_name

    @submenu("弹性公网IPv4")
    def eip_allocate(self, pool: str = "public_net(基础版)", count: int = 1, method: str = "快速选择", ip: str = None):
        """分配弹性公网IP并返回本次新分配的IP列表"""
        self.switch_eip_pool(pool)
        previous_ips = self._get_eip_list()
        dialog = self._open_eip_allocate_dialog()

        dialog.get_by_placeholder("请选择").first.click()
        self.locator("li").filter(has_text=pool).click()

        dialog.get_by_placeholder("请选择").nth(1).click()
        self.locator("li").filter(has_text=re.compile(rf"^{count}$")).last.click()

        selected_ips = []
        if count == 1:
            if method == "快速选择":
                available_ips = self._get_eip_allocate_ip_options(dialog)
                assert available_ips, "快速选择模式下未获取到可选公网IP"
                selected_ip = ip or available_ips[0]
                if ip is None:
                    self.page.keyboard.press("ArrowDown")
                    self.page.keyboard.press("Enter")
                else:
                    option_locator = self.get_by_text(selected_ip, exact=True)
                    for i in range(option_locator.count()):
                        option = option_locator.nth(i)
                        if option.is_visible():
                            option.click(force=True)
                            break
                    else:
                        raise AssertionError(f"快速选择模式下未找到可点击的公网IP选项: {selected_ip}")
                selected_ips = [selected_ip]
            elif method == "手动输入":
                if ip is None:
                    dialog.get_by_text("快速选择", exact=True).click()
                    available_ips = self._get_eip_allocate_ip_options(dialog)
                    assert available_ips, "手动输入模式下未获取到可输入的公网IP"
                    ip = available_ips[0]
                    dialog.get_by_text("手动输入", exact=True).click()

                dialog.get_by_text("手动输入", exact=True).click()
                ip_loc = dialog.locator(".el-form-item").filter(has_text=re.compile(r"^\*?\s*IP")).get_by_role("textbox")
                ip_loc.clear()
                ip_loc.fill(ip)
                selected_ips = [ip]
            else:
                raise AssertionError(f"不支持的分配模式: {method}")

        dialog.get_by_text("确定", exact=True).click()
        # 弹窗断言需在对话框关闭前完成（Element UI toast 默认只显示 3 秒）
        self.assert_popup_success("执行成功")
        expect(dialog).not_to_be_visible(timeout=10000)

        if selected_ips:
            return selected_ips

        # 分配后等待列表刷新，使用轮询获取新IP（慢环境兼容）
        created_ips = []
        for _ in range(30):
            self.page.wait_for_timeout(1000)
            current_ips = self._get_eip_list()
            created_ips = [current_ip for current_ip in current_ips if current_ip not in set(previous_ips)]
            if len(created_ips) >= count:
                break

        return created_ips[:count]

    def _eip_click_action(self, fip_ip: str, action_name: str):
        """在弹性公网IP列表中点击指定FIP的操作按钮，支持搜索定位。

        Args:
            fip_ip: FIP地址。
            action_name: 操作名称（如"绑定QoS"、"解绑QoS"）。
        """
        try:
            self.click_action(fip_ip, action_name)
            return
        except Exception:
            self.logger.info(f"直接定位 {action_name} 失败，尝试搜索后重试")

        try:
            self.search(fip_ip)
            self.click_action(fip_ip, action_name)
            return
        except Exception:
            self.logger.info(f"搜索后点击 {action_name} 仍失败，尝试下拉菜单模式")

        row = self.get_row_by_name(fip_ip)
        op_cell = row.locator("td").last
        op_cell.scroll_into_view_if_needed()
        more_btn = op_cell.get_by_text("更多").first
        if more_btn.count() > 0 and more_btn.is_visible():
            more_btn.dispatch_event("click")
        else:
            op_cell.locator("button").first.dispatch_event("click")
        self.page.wait_for_timeout(500)
        self.page.get_by_text(action_name).first.dispatch_event("click")

    @submenu("弹性公网IPv4")
    def eip_bind_qos(self, fip_ip: str, qos_name: str):
        """为指定FIP绑定QoS策略。

        Args:
            fip_ip: FIP地址。
            qos_name: QoS策略名称。
        """
        self.switch_eip_pool("public_net(基础版)")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        self._eip_click_action(fip_ip, "绑定QoS")

        dialog = self.get_by_role("dialog").filter(has_text="绑定QoS").first
        expect(dialog).to_be_visible(timeout=8000)

        rows = dialog.locator(".el-table__body-wrapper .el-table__body tr")
        expect(rows.first).to_be_visible(timeout=10000)

        for i in range(rows.count()):
            row = rows.nth(i)
            name_cell = row.locator("td").nth(1)
            if qos_name in (name_cell.text_content() or ""):
                checkbox = row.locator(".el-checkbox").first
                checkbox.click()
                break
        else:
            raise AssertionError(f"[FieldAssertion] 未在绑定QoS列表中找到QoS策略: {qos_name}")

        dialog.get_by_text("确定", exact=True).click()
        expect(dialog).not_to_be_visible(timeout=10000)
        try:
            self.assert_popup_success(timeout=10)
        except Exception:
            self.logger.warning("绑定QoS后弹窗未出现，跳过弹窗断言")
        self.logger.info(f"FIP {fip_ip} 绑定QoS {qos_name} 完成")

    @submenu("弹性公网IPv4")
    def eip_unbind_qos(self, fip_ip: str):
        """为指定FIP解绑QoS策略。

        Args:
            fip_ip: FIP地址。
        """
        self.switch_eip_pool("public_net(基础版)")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        self._eip_click_action(fip_ip, "解绑QoS")

        dialog = self.get_by_role("dialog").filter(has_text="解绑QoS").first
        expect(dialog).to_be_visible(timeout=8000)

        dialog.get_by_text("确定", exact=True).click()
        expect(dialog).not_to_be_visible(timeout=10000)
        try:
            self.assert_popup_success(timeout=10)
        except Exception:
            self.logger.warning("解绑QoS后弹窗未出现，跳过弹窗断言")
        self.logger.info(f"FIP {fip_ip} 解绑QoS 完成")

    @submenu("弹性公网IPv4")
    def eip_release(self, ips):
        """释放弹性公网IP，支持单个和批量操作"""
        if isinstance(ips, str):
            for action_name in ("释放公网IP", "释放"):
                try:
                    self.click_action(ips, action_name)
                    break
                except Exception:
                    continue
            else:
                raise AssertionError(f"未找到公网IP {ips} 的释放操作")
        else:
            self.select_rows_by_names(ips)
            batch_buttons = [
                self.get_by_text("批量释放公网IP", exact=True),
                self.get_by_text("批量释放公网IP").first,
            ]
            for btn in batch_buttons:
                try:
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        break
                except Exception:
                    continue
            else:
                raise AssertionError("未找到'批量释放公网IP'按钮")

        # 等待 EIP 释放确认弹窗出现，并在弹窗内点击可用确认按钮
        dialog_selectors = [
            ".sugon-dialog:visible",
            ".el-dialog__wrapper:visible",
            ".el-message-box:visible",
            "[role='dialog']:visible",
        ]
        release_dialog = None
        for sel in dialog_selectors:
            try:
                candidates = self.locator(sel)
                if candidates.count() > 0 and candidates.first.is_visible():
                    release_dialog = candidates.first
                    break
            except Exception:
                continue

        if release_dialog is None:
            raise AssertionError("EIP 释放确认弹窗未出现")

        # 等待弹窗稳定，并点击可用确认按钮
        clicked = False
        confirm_texts = ["确定", "释放", "确认"]
        for text in confirm_texts:
            try:
                btn = release_dialog.locator(
                    "button, .el-button, .cloud-button-btn"
                ).filter(has_text=text).first
                expect(btn).to_be_visible(timeout=5000)
                expect(btn).to_be_enabled(timeout=15000)
                btn.click()
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            # 兜底：尝试 dialog_confirm（可能定位到其他弹窗）
            try:
                self.dialog_confirm.click()
                clicked = True
            except Exception:
                pass

        if not clicked:
            raise AssertionError("EIP 释放确认弹窗中未找到可用确认按钮")
