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
        expect(dialog).not_to_be_visible(timeout=10000)

        if selected_ips:
            return selected_ips

        current_ips = self._get_eip_list()
        created_ips = [current_ip for current_ip in current_ips if current_ip not in set(previous_ips)]
        return created_ips[:count]

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

        self.dialog_confirm.click()
