import re

from playwright.sync_api import expect

from sugon_web.common.base import submenu


class EipMixin:
    """弹性公网IP页面动作。"""

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
        candidate_ips = [ip for ip in visible_ips if ip not in current_ips]
        return candidate_ips or visible_ips

    @submenu("弹性公网IPv4")
    def get_eip_list(self):
        """获取当前列表中的弹性公网IP"""
        return self._get_eip_list()

    @submenu("弹性公网IPv4")
    def eip_allocate(self, pool: str = "public_net(基础版)", count: int = 1, method: str = "快速选择", ip: str = None):
        """分配弹性公网IP并返回本次新分配的IP列表"""
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
        self.wait_for_page_ready()
        expect(dialog).not_to_be_visible(timeout=10000)

        if selected_ips:
            return selected_ips

        raise AssertionError("当前仅支持数量为1的弹性公网IP精确分配场景")

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
        self.wait_for_page_ready()
