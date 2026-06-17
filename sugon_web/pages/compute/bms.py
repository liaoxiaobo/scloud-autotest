import re
import time
import pytest
from playwright.sync_api import Locator, expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class BmsPage(BasePage):
    """裸金属BMS-软装版页面对象。"""

    service_name = "裸金属"

    _SOFT_SUBMENU_URL_MAP = {
        "网络": "/bms-network-list",
        "代理": "/bms-agent-list",
        "发现": "/bms-discover-list",
        "注册": "/bms-register-list",
        "裸金属实例": "/bms-physical-host-list",
        "标签": "/labels",
    }

    # ---- submenu ----

    def _goto_submenu_safe(self, name: str):
        expected = self._SOFT_SUBMENU_URL_MAP.get(name)
        self.goto_service("裸金属")
        if expected:
            if expected not in self.page.url:
                self.logger.info(f"[_goto_submenu_safe] 导航到 {name}")
                # SPA hash 路由下仅改变 hash 时 page.goto 可能不触发 Vue Router，
                # 先回到服务根页面（无 hash），再导航到目标子菜单，确保完整页面切换
                base = self.page.url.split('#')[0].rstrip('/')
                self.page.goto(base)
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(1500)
                self.page.goto(f"{base}#{expected}")
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(2500)
                # 若被重定向到 no-permission，尝试通过菜单点击导航
                if "no-permission" in self.page.url:
                    self.logger.warning(f"URL 导航到 {expected} 被重定向到 no-permission，尝试菜单点击")
                    self._click_bms_submenu(name)
            # 裸金属实例页面表格和搜索框加载较慢，增加等待时间
            wait_ms = 4000 if name == "裸金属实例" else 2500
            self.page.wait_for_timeout(wait_ms)
            self.logger.info(f"[_goto_submenu_safe] 当前 URL: {self.page.url}")
        else:
            self.goto_submenu(name)

    def _click_bms_submenu(self, name: str):
        """通过左侧菜单点击导航到 BMS 软装版下的子菜单，处理重名问题。"""
        self.logger.info(f"[_click_bms_submenu] 点击菜单: {name}")
        # 展开软装版父菜单（若未展开）
        menu_left = self.page.locator("#cloud-menu-left")
        parent_nodes = menu_left.locator(".one-tree-parent-node")
        for i in range(parent_nodes.count()):
            parent = parent_nodes.nth(i)
            text = parent.inner_text()
            if "软装版" in text:
                is_expanded = parent.evaluate("el => el.classList.contains('one-tree-expand')")
                if not is_expanded:
                    parent.click()
                    self.page.wait_for_timeout(500)
                # 在软装版同级或子级中查找目标菜单项
                break
        # 使用 JS 精确查找并点击可见的菜单文本
        self.page.evaluate(
            f"""(name) => {{
                const menu = document.querySelector('#cloud-menu-left');
                if (!menu) return 'menu-not-found';
                const items = menu.querySelectorAll('.one-tree-msg-text');
                // 优先找在已展开父节点下的匹配项（更可能是软装版下的）
                for (const item of items) {{
                    if (item.textContent.trim() === name) {{
                        const parent = item.closest('.one-tree-parent-node');
                        const isExpanded = parent && parent.classList.contains('one-tree-expand');
                        // 找已展开父节点下的项，或没有父节点的项
                        if (!parent || isExpanded) {{
                            item.click();
                            return 'clicked';
                        }}
                    }}
                }}
                // fallback: 点击第一个匹配
                for (const item of items) {{
                    if (item.textContent.trim() === name) {{
                        item.click();
                        return 'clicked-fallback';
                    }}
                }}
                return 'not-found';
            }}""",
            name,
        )
        self.page.wait_for_timeout(2500)
        self.logger.info(f"[_click_bms_submenu] 当前 URL: {self.page.url}")

    def bms_search(self, keyword: str):
        """BMS 页面专用搜索，使用回车触发，避免 _btn_search 定位不稳定问题。"""
        self.logger.info(f"[bms_search] 开始搜索: {keyword}")
        try:
            self.close_dialog_if_exists()
        except Exception as e:
            logger.debug(f"[bms_search] 关闭残留弹窗失败，继续搜索: {e}")
        self.page.wait_for_timeout(1000)
        # 优先查找 BMS 各子菜单页面搜索输入框
        inp = self.page.locator(
            "input[placeholder*='搜索(实例名称)'], "
            "input[placeholder*='搜索（实例名称）'], "
            "input[placeholder*='搜索（名称）'], "
            "input[placeholder*='搜索(名称)'], "
            "input[placeholder*='搜索（带外IP）'], "
            "input[placeholder*='搜索(带外IP)'], "
            "input[placeholder*='搜索（物理机）'], "
            "input[placeholder*='搜索(物理机)'], "
            "input[placeholder*='搜索（网络名称）'], "
            "input[placeholder*='搜索(网络名称)']"
        ).first
        if inp.count() == 0:
            inp = self.page.locator(".input-with-select input, .el-input__inner").first
        if inp.count() == 0 or not inp.is_editable():
            # 最终回退到通用搜索输入
            inp = self._input_search
        inp.fill(keyword)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)
        self.logger.info(f"[bms_search] 搜索完成: {keyword}")

    def search(self, keyword: str):
        """BMS 页面搜索入口，统一使用回车触发的专用搜索逻辑。"""
        self.bms_search(keyword)

    # ---- buttons & dialog ----

    def _click_cl_btn(self, text: str):
        # 先等待按钮可能出现
        self.page.wait_for_timeout(1500)
        # 尝试多种选择器组合，优先匹配可见的 cloud-button 组件
        selectors = [
            f".cloud-button--primary:has-text('{text}')",
            f".cloud-button-btn:has-text('{text}')",
            f"button:has-text('{text}')",
            f"a:has-text('{text}')",
        ]
        for sel in selectors:
            btn = self.page.locator(sel)
            for i in range(btn.count()):
                try:
                    if btn.nth(i).is_visible():
                        btn.nth(i).click()
                        return
                except Exception:
                    pass
        # 回退：使用 filter(has_text=) 匹配，只选可见元素，排除对话框标题
        for tag in ["button", "a", "span", "div"]:
            btn = self.page.locator(tag).filter(has_text=text)
            for i in range(btn.count()):
                try:
                    nth = btn.nth(i)
                    if nth.is_visible() and ".el-dialog__title" not in str(nth.evaluate("el => el.className")):
                        nth.click()
                        return
                except Exception:
                    pass
        # 最终回退：只在按钮类元素中搜索
        for sel in [".cloud-button", ".el-button", "button"]:
            btn = self.page.locator(sel).filter(has_text=text)
            for i in range(btn.count()):
                try:
                    if btn.nth(i).is_visible():
                        btn.nth(i).click()
                        return
                except Exception:
                    pass
        # 强制点击第一个匹配项（限制在按钮标签内）
        self.page.locator("button, .cloud-button, .el-button").filter(has_text=text).first.click()

    def _confirm_sugon_dialog(self, required=False):
        logger.info("[_confirm_sugon_dialog] 开始查找确认对话框")
        # 短暂等待对话框可能出现
        self.page.wait_for_timeout(500)
        # 统计可见对话框数量
        visible_dialogs = [d for d in self.page.locator(".sugon-dialog, .el-dialog, [role='dialog']").all() if d.is_visible()]
        logger.info(f"[_confirm_sugon_dialog] 可见对话框数量: {len(visible_dialogs)}")
        visible_dialogs_locator = self.page.locator(".sugon-dialog:visible, .el-dialog:visible, [role='dialog']:visible")

        def _wait_dialogs_closed():
            try:
                expect(visible_dialogs_locator).to_have_count(0, timeout=5000)
            except Exception as e:
                logger.warning(f"[_confirm_sugon_dialog] 对话框关闭等待超时: {e}")
                self.page.wait_for_timeout(1000)

        if len(visible_dialogs) == 0 and not required:
            logger.info("[_confirm_sugon_dialog] 无可见对话框且非必需，直接返回")
            return

        for dlg in self.page.locator(".sugon-dialog, .el-dialog, [role='dialog']").all():
            if dlg.is_visible():
                logger.info(f"[_confirm_sugon_dialog] 发现可见对话框")
                for sel in ["button", ".cloud-button-btn", ".el-button", "a"]:
                    btn = dlg.locator(sel).filter(has_text="确定")
                    if btn.count() > 0:
                        logger.info(f"[_confirm_sugon_dialog] 通过选择器 '{sel}' 找到确定按钮，执行点击")
                        clicked = False
                        try:
                            btn.first.click()
                            clicked = True
                        except Exception as e:
                            logger.warning(f"[_confirm_sugon_dialog] 标准点击失败: {e}")
                        if not clicked:
                            try:
                                btn.first.click(force=True)
                                clicked = True
                            except Exception as e:
                                logger.warning(f"[_confirm_sugon_dialog] force点击失败: {e}")
                        if not clicked:
                            # 最终回退：JavaScript 触发点击
                            try:
                                handle = btn.first.element_handle()
                                if handle:
                                    handle.evaluate("el => el.click()")
                                    clicked = True
                                    logger.info("[_confirm_sugon_dialog] JavaScript 点击成功")
                            except Exception as e:
                                logger.warning(f"[_confirm_sugon_dialog] JS点击失败: {e}")
                        self.page.wait_for_timeout(1000)
                        _wait_dialogs_closed()
                        return
        try:
            logger.info("[_confirm_sugon_dialog] 尝试使用 dialog_confirm 定位器")
            try:
                self.dialog_confirm.click()
            except Exception:
                self.dialog_confirm.click(force=True)
            self.page.wait_for_timeout(1000)
            _wait_dialogs_closed()
            return
        except Exception as e:
            logger.warning(f"[_confirm_sugon_dialog] dialog_confirm 点击失败: {e}")
        # 回退：查找全局可见的确定按钮（仅限对话框内的）
        try:
            for dlg in self.page.locator(".sugon-dialog, .el-dialog, [role='dialog']").all():
                for btn in dlg.locator("button, .cloud-button-btn, .el-button").filter(has_text="确定").all():
                    if btn.is_visible():
                        logger.info("[_confirm_sugon_dialog] 通过对话框内搜索找到可见确定按钮")
                        btn.click(force=True)
                        self.page.wait_for_timeout(1000)
                        _wait_dialogs_closed()
                        return
        except Exception as e:
            logger.warning(f"[_confirm_sugon_dialog] 对话框内搜索确定按钮失败: {e}")
        if required:
            logger.warning("[_confirm_sugon_dialog] 未找到任何可点击的确定按钮")

    def _js_click_action(self, row: Locator, action: str):
        if row is None:
            raise Exception(f"[_js_click_action] 无法执行 '{action}'：未找到目标行")
        logger.info(f"[_js_click_action] 开始执行操作 '{action}'")
        row_text = ""
        try:
            row_text = (row.text_content() or "").strip()
        except Exception:
            pass
        logger.info(f"[_js_click_action] 目标行文本: {row_text[:120]}")

        # 先展开下拉菜单
        more_btn = row.locator("button, .cloud-button-btn, a, span").filter(has_text=re.compile(r"更多|⋯|⋮"))
        if more_btn.count() == 0:
            more_btn = row.locator("button, .cloud-button-btn, a, span").filter(has_text="更多")
        if more_btn.count() > 0:
            logger.info(f"[_js_click_action] 找到'更多'按钮，尝试展开下拉菜单")
            try:
                more_btn.first.click(force=True)
                self.page.wait_for_timeout(800)
            except Exception as e:
                logger.warning(f"[_js_click_action] 点击'更多'按钮失败: {e}")
        else:
            logger.info(f"[_js_click_action] 未找到'更多'按钮，操作可能直接可见")

        # 下拉菜单通常挂载到 body，不一定在当前行 DOM 内。
        global_items = self.page.locator(
            ".cloud-table-dropdown-item, .el-dropdown-menu__item, [role='menuitem']"
        ).filter(has_text=action)
        for index in range(global_items.count()):
            try:
                item = global_items.nth(index)
                if item.is_visible(timeout=1000):
                    item.click(force=True)
                    logger.info(f"[_js_click_action] 成功点击全局可见菜单项 '{action}'")
                    return True
            except Exception as e:
                logger.debug(f"[_js_click_action] 全局菜单项第 {index + 1} 个不可点击: {e}")

        # 尝试标准点击下拉菜单项（要求元素可见可交互）
        items = row.locator(".cloud-table-dropdown-item").filter(has_text=action)
        item_count = items.count()
        logger.info(f"[_js_click_action] 下拉菜单项 '{action}' 匹配数量: {item_count}")
        if item_count > 0:
            try:
                items.first.wait_for(state="visible", timeout=3000)
                items.first.click()
                logger.info(f"[_js_click_action] 成功标准点击下拉菜单项 '{action}'")
                return True
            except Exception as e:
                logger.warning(f"[_js_click_action] 标准点击失败（元素不可见或不可交互）: {e}")

        # 回退到 JavaScript
        logger.info(f"[_js_click_action] 回退到 JavaScript 点击 '{action}'")
        result = self.page.evaluate(
            """([t, a]) => {
                const allRows = document.querySelectorAll('table tr');
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
                };
                for (const i of document.querySelectorAll('.cloud-table-dropdown-item, .el-dropdown-menu__item, [role="menuitem"]')) {
                    if (i.textContent.trim() === a && isVisible(i)) {
                        i.click();
                        return 'global-dropdown-clicked';
                    }
                }
                for (const r of allRows) {
                    if (r.textContent.includes(t)) {
                        for (const i of r.querySelectorAll('.cloud-table-dropdown-item')) {
                            i.classList.remove('cloud-table-dropdown-item-btn-hide');
                            i.style.display = 'block';
                            i.style.visibility = 'visible';
                        }
                        for (const i of r.querySelectorAll('.cloud-table-dropdown-item')) {
                            if (i.textContent.trim() === a) {
                                i.click();
                                return 'dropdown-clicked';
                            }
                        }
                        for (const i of r.querySelectorAll('a, button, .el-button, span')) {
                            if (i.textContent.trim() === a && i.offsetParent !== null) {
                                i.click();
                                return 'element-clicked';
                            }
                        }
                        return 'not-found';
                    }
                }
                return 'row-not-found';
            }""", [row_text, action])
        logger.info(f"[_js_click_action] JavaScript 点击结果: {result}")
        return result not in ("not-found", "row-not-found")

    def _get_switch_group_row(self, group_name: str, node_name: str = ""):
        """按交换机组名称定位行；有节点名时优先返回绑定该节点的行。"""
        candidates = []
        for row in self._get_rows():
            try:
                text = row.text_content(timeout=3000) or ""
                if group_name in text:
                    candidates.append((row, text))
                    if node_name and node_name in text:
                        logger.info(f"找到交换机组 '{group_name}' 且绑定节点 '{node_name}' 的目标行")
                        return row
            except Exception:
                continue
        if candidates:
            for row, text in candidates:
                if "--" in text or "—" in text:
                    logger.info(f"未找到绑定节点 '{node_name}' 的行，优先使用已解绑行: {text[:120]}")
                    return row
            logger.info(f"未找到绑定节点 '{node_name}' 的交换机组行，回退使用第一条匹配: {candidates[0][1][:120]}")
            return candidates[0][0]
        return None

    def _get_switch_group_name_from_row(self, row: Locator, fallback: str = ""):
        try:
            name = row.evaluate("""row => {
                const cells = Array.from(row.querySelectorAll('td'))
                    .map(td => (td.innerText || '').trim())
                    .filter(Boolean);
                return cells[0] || '';
            }""")
            if name:
                return name
        except Exception as e:
            logger.debug(f"[_get_switch_group_name_from_row] 解析交换机组名称失败: {e}")
        return fallback

    def _get_rows(self):
        return self.page.locator("tbody tr").all()

    def _get_row_by_name(self, name: str):
        try:
            loc = self.page.get_by_role("row", name=name)
            if loc.count() == 1:
                return loc.first
            if loc.count() > 1:
                logger.info(f"[_get_row_by_name] '{name}' 匹配到多行，改用逐行遍历避免 strict mode")
        except Exception:
            pass
        for r in self._get_rows():
            try:
                if name in r.text_content():
                    return r
            except Exception:
                continue
        return None

    def _get_row_by_cell_text(self, text: str, cell_index: int = 1, exact: bool = True):
        """按指定单元格文本定位表格行，避免只按整行包含导致误判。"""
        for row in self._get_rows():
            try:
                row_text = row.text_content(timeout=3000) or ""
                if "暂无数据" in row_text:
                    continue
                cells = row.locator("td")
                if cells.count() <= cell_index:
                    continue
                value = re.sub(r"\s+", " ", cells.nth(cell_index).text_content(timeout=3000) or "").strip()
                if (exact and value == text) or (not exact and text in value):
                    return row
            except Exception:
                continue
        return None

    # ---- network ----

    def bms_network_create(self, name, cidr, start_ip, end_ip, gateway, vlan):
        self._click_cl_btn("新建")
        d = self.page.locator('[role="dialog"]').filter(has_text="新建网络").last
        d.locator(".el-form-item").filter(has_text="名称").locator("input").fill(name)
        d.locator(".el-form-item").filter(has_text="起始IP").locator("input").fill(start_ip)
        d.locator(".el-form-item").filter(has_text="结束IP").locator("input").fill(end_ip)
        d.locator(".el-form-item").filter(has_text="Vlan").locator("input").fill(vlan)
        d.locator(".el-form-item").filter(has_text="网段").locator("input").fill(cidr)
        d.locator(".el-form-item").filter(has_text="网关IP").locator("input").fill(gateway)
        # 优先使用键盘 Enter 提交，避免按钮点击不触发事件
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)
        # 如果对话框仍然存在，再尝试点击确定按钮
        if d.is_visible():
            self._confirm_sugon_dialog()
            self.page.wait_for_timeout(2000)

    def bms_network_delete(self, name):
        self._goto_submenu_safe("网络")
        self.page.wait_for_timeout(500)
        self.bms_search(name)
        row = self._get_row_by_cell_text(name, cell_index=1)
        if not row:
            logger.info(f"网络 '{name}' 不存在，无需删除")
            return False
        if not self._js_click_action(row, "删除"):
            raise AssertionError(f"未找到网络 '{name}' 的删除操作")
        self._confirm_sugon_dialog(required=True)
        deadline = time.time() + 60
        while time.time() < deadline:
            self.page.wait_for_timeout(3000)
            self._goto_submenu_safe("网络")
            self.bms_search(name)
            if not self._get_row_by_cell_text(name, cell_index=1):
                logger.info(f"网络 '{name}' 已删除")
                return True
        raise AssertionError(f"网络 '{name}' 删除后仍存在")

    def bms_network_exists(self, name: str):
        """判断网络列表中是否存在指定网络名称。"""
        self._goto_submenu_safe("网络")
        self.bms_search(name)
        return self._get_row_by_cell_text(name, cell_index=1) is not None

    def bms_network_cleanup(self):
        self.page.wait_for_timeout(1000)
        names = []
        for r in self._get_rows():
            cells = r.locator("td")
            if cells.count() > 1:
                n = cells.nth(1).text_content().strip()
                if n and len(n) < 100 and "暂无数据" not in n and n not in names:
                    names.append(n)
        for n in names:
            try:
                self.bms_network_delete(n)
                self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning(f"删除网络失败: {e}")

    # ---- agent ----

    def _dialog_form_control(self, dialog: Locator, label_text: str, selector: str) -> Locator:
        """在对话框内按表单 label 精确定位控件。"""
        form_items = dialog.locator(".el-form-item")
        for index in range(form_items.count()):
            item = form_items.nth(index)
            try:
                label = item.locator(".el-form-item__label").first.text_content(timeout=1000) or ""
                label = re.sub(r"[\s:*：]+", "", label)
                if label == re.sub(r"[\s:*：]+", "", label_text):
                    control = item.locator(selector)
                    if control.count() > 0:
                        return control.first
            except Exception:
                continue
        return dialog.locator(".el-form-item").filter(has_text=label_text).locator(selector).first

    def _visible_select_options(self):
        """读取当前可见 ElementUI 下拉框选项。"""
        return self.page.evaluate(
            """() => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return el.getAttribute('aria-hidden') !== 'true'
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.opacity !== '0'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const dropdowns = Array.from(document.querySelectorAll('body > div.el-select-dropdown, .el-select-dropdown'))
                    .filter(isVisible);
                const dropdown = dropdowns[dropdowns.length - 1];
                if (!dropdown) return [];
                return Array.from(dropdown.querySelectorAll('li.el-select-dropdown__item, li'))
                    .filter((item) => isVisible(item) && !item.classList.contains('is-disabled'))
                    .map((item) => (item.textContent || '').trim())
                    .filter(Boolean);
            }"""
        )

    def _wait_visible_select_options(self, timeout=10000, interval=500):
        """等待当前可见下拉框选项出现。"""
        deadline = time.time() + timeout / 1000
        last_texts = []
        while time.time() < deadline:
            last_texts = self._visible_select_options()
            if last_texts:
                return last_texts
            self.page.wait_for_timeout(interval)
        return last_texts

    def _click_visible_select_option(self, option_text: str = "", exclude_texts=None):
        """点击当前可见 ElementUI 下拉框中的指定选项；未指定时选第一个有效项。"""
        exclude_texts = exclude_texts or []
        clicked = self.page.evaluate(
            """({optionText, excludeTexts}) => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return el.getAttribute('aria-hidden') !== 'true'
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.opacity !== '0'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const dropdowns = Array.from(document.querySelectorAll('body > div.el-select-dropdown, .el-select-dropdown'))
                    .filter(isVisible);
                const dropdown = dropdowns[dropdowns.length - 1];
                if (!dropdown) return '';
                const items = Array.from(dropdown.querySelectorAll('li.el-select-dropdown__item, li'))
                    .filter((item) => isVisible(item) && !item.classList.contains('is-disabled'));
                const target = items.find((item) => {
                    const text = (item.textContent || '').trim();
                    if (!text || excludeTexts.includes(text)) return false;
                    return optionText ? text === optionText : true;
                });
                if (!target) return '';
                const opts = {bubbles: true, cancelable: true, view: window};
                target.dispatchEvent(new MouseEvent('mousedown', opts));
                target.dispatchEvent(new MouseEvent('mouseup', opts));
                target.dispatchEvent(new MouseEvent('click', opts));
                return (target.textContent || '').trim();
            }""",
            {"optionText": option_text, "excludeTexts": exclude_texts},
        )
        if not clicked:
            raise Exception(f"未找到可点击的下拉选项: {option_text or '<first>'}")
        return clicked

    def bms_agent_register(self, node_name, ip_address="10.0.13.13"):
        """注册BMS代理。

        对话框中的"选择节点"下拉框实际展示的是Region（如RegionOne/RegionTwo），
        而非物理机节点名。选择Region后会触发网络列表的API加载。
        必须使用Playwright原生click触发Vue的change事件，JS click不会触发API调用。
        """
        self._goto_submenu_safe("代理")
        for ip_suffix in range(13, 20):
            current_ip = f"10.0.13.{ip_suffix}"
            self._click_cl_btn("注册代理")
            d = self.page.locator('[role="dialog"]').filter(has_text="注册代理").last
            d.wait_for(state="visible", timeout=10000)
            self.page.wait_for_timeout(1500)

            # 1. 选择节点/Region（不同版本展示不同文案）—— 使用原生事件触发 Vue change
            node_selected = False
            last_net_texts = []
            for attempt in range(5):
                try:
                    node_input = self._dialog_form_control(d, "选择节点", ".el-input")
                    node_input.click()
                    self.page.wait_for_timeout(1000)
                    all_texts = self._wait_visible_select_options(timeout=10000)
                    logger.info(f"[bms_agent_register] 节点/Region下拉选项(attempt {attempt + 1}): {all_texts}")
                    if not all_texts:
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)
                        continue
                    # 选择节点下拉在不同版本可能展示 Region 或物理机名；优先选择目标物理机。
                    candidate_names = [node_name] if node_name in all_texts else all_texts
                    if node_name not in all_texts:
                        logger.warning(f"[bms_agent_register] 目标节点 '{node_name}' 不在下拉选项中，回退尝试: {all_texts}")
                    for candidate_index, region_name in enumerate(candidate_names):
                        try:
                            if candidate_index > 0:
                                node_input.click()
                                self.page.wait_for_timeout(1000)
                            self._click_visible_select_option(region_name)
                            logger.info(f"[bms_agent_register] 已选择节点/Region: {region_name}")
                            self.page.wait_for_timeout(3000)
                            net_input = self._dialog_form_control(d, "网络", ".el-input")
                            net_input.click(timeout=5000)
                            self.page.wait_for_timeout(1000)
                            net_texts = self._wait_visible_select_options(timeout=10000)
                            last_net_texts = net_texts
                            logger.info(f"[bms_agent_register] 节点/Region '{region_name}' 的网络选项: {net_texts}")
                            valid_nets = [
                                n for n in net_texts
                                if n != region_name and "无数据" not in n and "暂无数据" not in n
                            ]
                            if valid_nets:
                                selected_network = self._click_visible_select_option(valid_nets[0])
                                logger.info(f"[bms_agent_register] 已选择网络: {selected_network}")
                                node_selected = True
                                break
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(500)
                        except Exception as e:
                            logger.warning(f"[bms_agent_register] 节点/Region '{region_name}' 未找到可用网络: {e}")
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(500)
                    if node_selected:
                        break
                    # 如果没有Region有网络，继续下一轮重试
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(500)
                    continue
                except Exception as e:
                    logger.warning(f"[bms_agent_register] 选择Region失败(attempt {attempt + 1}): {e}")
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)
            if not node_selected:
                raise Exception(f"无法选择节点/Region或网络，下拉框无可用网络选项: {last_net_texts}")

            # 3. 填写IP并提交
            self._dialog_form_control(d, "IP地址", "input").fill(current_ip)
            self._confirm_sugon_dialog()
            # 强制关闭所有残留对话框（含错误提示、关闭动画期间的对话框）
            self.page.wait_for_timeout(2000)
            for _ in range(5):
                any_visible = False
                for dlg in self.page.locator(".el-dialog__wrapper").all():
                    try:
                        if dlg.is_visible():
                            any_visible = True
                            break
                    except Exception:
                        pass
                if any_visible:
                    logger.warning("[bms_agent_register] 检测到可见对话框残留，按Escape关闭")
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(800)
                else:
                    break

            # 检查IP冲突
            try:
                if self.popup.is_visible() and "已经被使用" in self.popup.text_content():
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(500)
                    continue
            except: pass
            return
        raise Exception("所有IP地址均已被使用")

    def bms_agent_wait_healthy(self, node_name: str, max_wait: int = 600, poll_interval: int = 30):
        """等待BMS代理状态变为健康，返回代理行数据；超时返回 None。"""
        deadline = time.time() + max_wait
        last_status = "未找到"
        while time.time() < deadline:
            self._goto_submenu_safe("代理")
            self.bms_search(node_name)
            try:
                agent_data = self.get_row_data(node_name)
            except Exception as e:
                logger.warning(f"[bms_agent_wait_healthy] 未找到代理 '{node_name}'，继续等待: {e}")
                agent_data = None

            if agent_data:
                last_status = str(agent_data.get("状态", "")).strip()
                if "健康" in last_status:
                    logger.info(f"代理 '{node_name}' 状态已为健康")
                    return agent_data
                logger.info(f"代理 '{node_name}' 当前状态为 '{last_status}'，继续等待健康")

            self.page.wait_for_timeout(poll_interval * 1000)

        logger.warning(f"代理 '{node_name}' 未在 {max_wait}s 内变为健康，最后状态: {last_status}")
        return None

    def bms_agent_install_pxe(self, node_name):
        row = self._get_row_by_name(node_name)
        self._js_click_action(row, "安装PXE插件")
        self._confirm_sugon_dialog(required=False)

    def bms_agent_wait_pxe_installed(self, node_name, initial_wait=300, poll_interval=30, max_wait=600, max_retries=2):
        """等待 PXE 插件安装完成，若代理被系统删除则自动重新注册并重试。"""
        for attempt in range(max_retries + 1):
            # 先立即检查一次，避免PXE已完成仍傻等
            self.page.reload()
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
            row = self._get_row_by_name(node_name)
            if row:
                try:
                    txt = row.text_content()
                    if txt and "是" in txt:
                        logger.info(f"PXE已完成，无需等待")
                        return True
                except Exception:
                    pass
            logger.info(f"等待 {initial_wait}s 检查 PXE... (尝试 {attempt + 1}/{max_retries + 1})")
            time.sleep(initial_wait)
            elapsed = initial_wait
            agent_deleted = False
            while elapsed <= max_wait:
                self.page.reload()
                self.page.wait_for_load_state("networkidle")
                self.page.wait_for_timeout(2000)
                row = self._get_row_by_name(node_name)
                if row is None:
                    logger.warning(f"未找到代理行 '{node_name}'，可能已被系统自动删除 ({elapsed}s)")
                    agent_deleted = True
                    break
                else:
                    try:
                        txt = row.text_content()
                        if txt and "是" in txt:
                            logger.info(f"PXE完成 {elapsed}s")
                            return True
                    except Exception as e:
                        logger.warning(f"读取代理行文本失败: {e}")
                logger.info(f"PXE未完成 ({elapsed}s/{max_wait}s)")
                time.sleep(poll_interval)
                elapsed += poll_interval
            if agent_deleted and attempt < max_retries:
                logger.info("代理被删除，尝试重新注册并安装PXE...")
                self.bms_agent_register(node_name=node_name)
                self.page.wait_for_timeout(3000)
                self.bms_agent_install_pxe(node_name)
                self.page.wait_for_timeout(3000)
            else:
                break
        return False

    def bms_agent_delete(self, node_name):
        self._goto_submenu_safe("代理")
        self.search(node_name)
        row = self._get_row_by_name(node_name)
        if not row:
            logger.info(f"代理 '{node_name}' 不存在，无需删除")
            return

        clicked = self._js_click_action(row, "删除")
        if not clicked:
            raise RuntimeError(f"代理 '{node_name}' 的删除操作未点击成功")
        self._confirm_sugon_dialog(required=True)
        try:
            self.assert_popup_success()
        except AssertionError as e:
            logger.warning(f"未捕获到代理删除成功提示，继续轮询列表确认: {e}")

        self._wait_for_row_absence("代理", node_name, label="代理", timeout=300)

    def bms_agent_cleanup(self):
        self.page.wait_for_timeout(1500)
        for r in self._get_rows():
            try:
                txt = r.text_content(timeout=3000)
                if not txt or "暂无数据" in txt:
                    continue
            except Exception:
                continue
            try:
                self._js_click_action(r, "删除")
                self.page.wait_for_timeout(800)
                self._confirm_sugon_dialog()
                self.page.wait_for_timeout(1500)
            except Exception as e:
                logger.warning(f"删除代理失败: {e}")

    # ---- discovery ----

    def _goto_discovery(self):
        self._goto_submenu_safe("发现")
        self.page.wait_for_load_state("networkidle")

    def bms_discovery_create(self, name, start_ip, end_ip, subnet_mask="255.255.255.0", username="admin", password="admin"):
        self._goto_discovery()
        self._click_cl_btn("新建")
        d = self.page.locator('[role="dialog"]').filter(has_text="新建发现").last
        d.locator(".el-form-item").filter(has_text="名称").locator("input").fill(name)
        d.locator(".el-form-item").filter(has_text="起始IP").locator("input").fill(start_ip)
        d.locator(".el-form-item").filter(has_text="结束IP").locator("input").fill(end_ip)
        d.locator(".el-form-item").filter(has_text="子网掩码").locator("input").fill(subnet_mask)
        d.locator(".el-form-item").filter(has_text="用户名").locator("input").first.fill(username)
        d.locator(".el-form-item").filter(has_text="密码").locator("input[type='password']").fill(password)
        # 多阶段提交策略：先尝试Enter，再尝试JS表单提交，最后回退到按钮点击
        submitted = False
        for attempt in range(3):
            if submitted:
                break
            if attempt == 0:
                # 尝试1: 在密码框按Tab移到按钮再按Enter
                self.page.keyboard.press("Tab")
                self.page.wait_for_timeout(300)
                self.page.keyboard.press("Enter")
            elif attempt == 1:
                # 尝试2: JS触发表单提交
                try:
                    form = d.locator("form").first
                    if form.count() > 0:
                        form.first.evaluate("f => { f.dispatchEvent(new Event('submit')); }")
                    else:
                        d.evaluate("dlg => { const btn = dlg.querySelector('.cloud-button--primary, .el-button--primary, button[type=submit]'); if(btn) btn.click(); }")
                except Exception as e:
                    logger.warning(f"[bms_discovery_create] JS提交失败: {e}")
            else:
                # 尝试3: 直接点击确定按钮
                self._confirm_sugon_dialog()
            self.page.wait_for_timeout(3000)
            # 检查对话框是否消失
            try:
                if not d.is_visible():
                    submitted = True
                    logger.info(f"[bms_discovery_create] 第{attempt + 1}次尝试后对话框已关闭")
                    break
            except Exception:
                submitted = True
                break
        if not submitted:
            raise Exception("[bms_discovery_create] 所有提交尝试均失败，对话框仍未关闭")
        # 等待页面加载完成并验证任务已创建
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(5000)
        # 刷新并搜索验证（多次重试）
        for verify_attempt in range(5):
            self._goto_discovery()
            self.page.wait_for_timeout(2000)
            self.search(name)
            self.page.wait_for_timeout(3000)
            row = self._get_row_by_name(name)
            if row is not None:
                logger.info(f"[bms_discovery_create] 成功创建并验证发现任务 '{name}'（第{verify_attempt + 1}次验证）")
                return
            logger.warning(f"[bms_discovery_create] 第{verify_attempt + 1}/5次验证未找到 '{name}'，等待后重试...")
            self.page.wait_for_timeout(5000)
        logger.warning(f"[bms_discovery_create] 多次验证后仍未找到 '{name}'，可能提交未真正成功或后端处理延迟")

    def bms_discovery_sync(self, name, max_retries=3):
        for attempt in range(max_retries):
            self._goto_discovery()
            self.search(name)
            self.page.wait_for_timeout(3000)
            row = self._get_row_by_name(name)
            if row:
                self._js_click_action(row, "同步")
                self._confirm_sugon_dialog()
                return
            logger.warning(f"[bms_discovery_sync] 第 {attempt + 1}/{max_retries} 次未找到 '{name}'，重试...")
            self.page.wait_for_timeout(3000)
        raise Exception(f"[bms_discovery_sync] 无法找到发现任务 '{name}'")

    def bms_discovery_delete(self, name):
        self._goto_discovery()
        self.search(name)
        row = self._get_row_by_name(name)
        if row:
            self._js_click_action(row, "删除")
            self._confirm_sugon_dialog()
            self._wait_for_row_absence("发现", name, label="发现任务")

    def bms_discovery_cleanup(self):
        self._goto_discovery()
        self.page.wait_for_timeout(2000)
        for r in self._get_rows():
            try:
                txt = r.text_content(timeout=3000)
                if not txt or "暂无数据" in txt:
                    continue
            except Exception:
                continue
            try:
                self._js_click_action(r, "删除")
                self.page.wait_for_timeout(800)
                self._confirm_sugon_dialog()
                self.page.wait_for_timeout(1500)
            except Exception as e:
                logger.warning(f"删除发现任务失败: {e}")

    # ---- register ----

    def bms_register_out_of_band_info(self, bmc_ip, switch_vlan, switch_group_name):
        self._goto_submenu_safe("注册")
        row = self._get_row_by_name(bmc_ip)
        self._js_click_action(row, "带外信息")
        self.page.wait_for_timeout(800)
        d = self.page.locator('[role="dialog"]').filter(has_text="带外信息").last
        d.locator(".el-form-item").filter(has_text="交换机Vlan").locator("input").fill(str(switch_vlan))
        d.locator(".el-form-item").filter(has_text="交换机组").locator("input").click()
        self.page.wait_for_timeout(500)
        self.page.locator(".el-select-dropdown:visible li").filter(has_text=switch_group_name).first.click()
        self._confirm_sugon_dialog()

    def bms_register_action(self, bmc_ip):
        self._goto_submenu_safe("注册")
        row = self._get_row_by_name(bmc_ip)
        self._js_click_action(row, "注册")
        self._confirm_sugon_dialog()

    def bms_register_wait_status(self, bmc_ip, target_status, poll_interval=30, max_wait=600):
        """轮询等待注册状态达到目标值。

        点击注册后状态可能短暂变为中间态（如'注册中'），此方法持续轮询
        直到状态稳定为 target_status 或超时。
        """
        elapsed = 0
        while elapsed <= max_wait:
            self._goto_submenu_safe("注册")
            self.search(bmc_ip)
            row = self._get_row_by_name(bmc_ip)
            if row and target_status in row.text_content():
                logger.info(f"状态已达到 '{target_status}' ({elapsed}s)")
                return True
            current_status = row.text_content() if row else "未找到行"
            logger.info(f"未达到 '{target_status}'，当前: {current_status.strip()[:50]} ({elapsed}s/{max_wait}s)")
            time.sleep(poll_interval)
            elapsed += poll_interval
        logger.error(f"等待 '{target_status}' 超时 ({max_wait}s)")
        return False

    def bms_register_delete(self, bmc_ip):
        self._goto_submenu_safe("注册")
        self.search(bmc_ip)
        row = self._get_row_by_name(bmc_ip)
        if row:
            self._js_click_action(row, "删除")
            self._confirm_sugon_dialog()
            self._wait_for_row_absence("注册", bmc_ip, label="注册信息", cell_index=3)

    def bms_register_cleanup(self):
        self._goto_submenu_safe("注册")
        for r in self._get_rows():
            try:
                self._js_click_action(r, "删除")
                self._confirm_sugon_dialog()
                self.page.wait_for_timeout(1000)
            except Exception:
                pass

    def _wait_for_table_rows(self, section_locator, timeout=10000, interval=500):
        """轮询等待表格行出现。"""
        start = time.time()
        while (time.time() - start) * 1000 < timeout:
            rows = section_locator.locator("table tbody tr").all()
            if len(rows) > 0:
                return rows
            self.page.wait_for_timeout(interval)
        return []

    def _wait_for_row_absence(self, submenu_name: str, keyword: str, *, label: str, timeout: int = 120,
                              poll_interval: int = 5, cell_index: int | None = None,
                              navigate_as_service: bool = False):
        """轮询等待指定行从当前列表中消失。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if navigate_as_service:
                self.goto_service(submenu_name)
            else:
                self._goto_submenu_safe(submenu_name)
            self.search(keyword)
            self.page.wait_for_timeout(2000)
            row = (self._get_row_by_cell_text(keyword, cell_index=cell_index)
                   if cell_index is not None else self._get_row_by_name(keyword))
            if not row:
                logger.info(f"{label} '{keyword}' 已删除")
                return True
            self.page.wait_for_timeout(poll_interval * 1000)
        raise AssertionError(f"{label} '{keyword}' 删除后仍存在")

    def _click_el_radio(self, row_locator):
        """点击 Element UI 的 el-radio（优先点击包装器）。"""
        for sel in [".el-radio", ".el-radio__input", ".el-radio__original", "input[type='radio']"]:
            els = row_locator.locator(sel)
            try:
                if els.count() > 0 and els.first.is_visible():
                    els.first.scroll_into_view_if_needed()
                    els.first.click()
                    return True
            except Exception:
                continue
        # 最终回退：JS 点击
        try:
            row_locator.evaluate("row => { const r = row.querySelector('.el-radio input, input[type=radio]'); if(r) r.click(); }")
            return True
        except Exception:
            return False

    # ---- instance ----

    def bms_instance_create(self, name, image_name="", system_disk="sdi", password="",
                               security_group="", server_name="", network_name="", subnet_name="", bmc_ip=""):
        self._goto_submenu_safe("裸金属实例")
        self._click_cl_btn("新建")
        self.page.wait_for_load_state("networkidle")
        logger.info(f"创建实例: {name}")
        self.page.wait_for_timeout(2000)

        # 前置检查：镜像列表和服务器列表必须非空
        image_section = self.page.locator(".el-form-item").filter(has_text=re.compile(r"^镜像$"))
        try:
            image_section.locator("table tbody tr").first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        image_rows = image_section.locator("table tbody tr").all()
        if not image_rows:
            # 再次尝试 JS 检查
            has_images = self.page.evaluate("""() => {
                const items = document.querySelectorAll('.el-form-item');
                for (const item of items) {
                    const label = item.querySelector('label');
                    if (label && label.textContent.trim() === '镜像') {
                        return item.querySelectorAll('table tbody tr').length > 0;
                    }
                }
                return false;
            }""")
            if not has_images:
                raise RuntimeError("环境缺少裸金属镜像，无法创建实例")

        server_section = self.page.locator(".el-form-item").filter(has_text=re.compile(r"服务器"))
        if server_section.count() == 0:
            server_section = self.page.locator(".el-form-item").filter(has_text=re.compile(r"server", re.IGNORECASE))
        server_rows = server_section.locator("table tbody tr").all() if server_section.count() > 0 else []
        if not server_rows:
            has_servers = self.page.evaluate("""() => {
                const items = document.querySelectorAll('.el-form-item');
                for (const item of items) {
                    const label = item.querySelector('label');
                    if (label && label.textContent.includes('服务器')) {
                        const rows = item.querySelectorAll('table tbody tr');
                        for (const row of rows) {
                            if (!row.textContent.includes('暂无数据')) return true;
                        }
                        return false;
                    }
                }
                return false;
            }""")
            if not has_servers:
                raise RuntimeError("环境没有可用的裸金属服务器，无法创建实例")

        # 1. 填写名称
        try:
            name_inputs = self.page.locator(".el-form-item").filter(has_text=re.compile(r"^名称$")).locator("input")
            if name_inputs.count() > 0:
                name_inputs.first.fill(name)
                logger.info("[bms_instance_create] 名称填写成功")
            else:
                logger.warning("[bms_instance_create] 未找到名称输入框")
        except Exception as e:
            logger.warning(f"[bms_instance_create] 填写名称失败: {e}")
        self.page.wait_for_timeout(300)

        # 2. 选择安全组
        try:
            sg_item = self.page.locator(".el-form-item").filter(has_text="安全组")
            sg_select = sg_item.locator(".el-select").first
            if sg_select.count() > 0:
                try:
                    sg_select.click()
                except Exception:
                    self.page.evaluate("(el) => el.click()", sg_select.element_handle())
                self.page.wait_for_timeout(800)
                opts = self.page.locator(".el-select-dropdown:visible li")
                if opts.count() > 0:
                    if security_group:
                        # 优先选择指定安全组
                        sg_opt = opts.filter(has_text=security_group)
                        if sg_opt.count() > 0:
                            # 使用更完整的事件序列来确保 Element UI select 组件捕获选择
                            opt_el = sg_opt.first.element_handle()
                            if opt_el:
                                opt_el.click()
                                # 额外触发 mousedown/mouseup 确保事件被捕获
                                try:
                                    opt_el.evaluate("""el => {
                                        el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                                        el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                                        el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                                    }""")
                                except Exception:
                                    pass
                            else:
                                sg_opt.first.click()
                            logger.info(f"[bms_instance_create] 安全组选择成功({security_group})")
                        else:
                            opts.first.click()
                            logger.info("[bms_instance_create] 安全组选择成功(第一个)")
                    else:
                        opts.first.click()
                        logger.info("[bms_instance_create] 安全组选择成功(第一个)")
                else:
                    logger.warning("[bms_instance_create] 安全组下拉框无选项")
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
                # 强力触发 Element UI select 组件更新：模拟完整事件序列并强制 Vue 表单校验
                try:
                    self.page.evaluate(
                        """() => {
                            const items = document.querySelectorAll('.el-form-item');
                            let sgItem = null;
                            for (const item of items) {
                                const label = item.querySelector('.el-form-item__label');
                                if (label && label.textContent.includes('安全组')) {
                                    sgItem = item;
                                    break;
                                }
                            }
                            if (!sgItem) return;
                            const selectEl = sgItem.querySelector('.el-select');
                            if (!selectEl) return;
                            // 尝试通过 Vue 实例直接触发值更新
                            const vueEl = selectEl.__vue__ || selectEl._vue_ || selectEl.__VUE__;
                            if (vueEl && vueEl.$emit) {
                                vueEl.$emit('change', vueEl.value);
                                vueEl.$emit('input', vueEl.value);
                                vueEl.$emit('blur');
                            }
                            // 强制触发表单校验
                            const formItem = sgItem.__vue__ || sgItem._vue_ || sgItem.__VUE__;
                            if (formItem && formItem.validate) {
                                formItem.validate('change');
                            }
                            // 对 input 触发完整事件序列
                            const input = selectEl.querySelector('input');
                            if (input) {
                                ['mousedown', 'mouseup', 'click', 'input', 'change', 'blur'].forEach(et => {
                                    input.dispatchEvent(new Event(et, { bubbles: true }));
                                });
                            }
                        }"""
                    )
                except Exception:
                    pass
                self.page.wait_for_timeout(800)
                # 备用：blur 触发
                sg_input = sg_item.locator("input").first
                if sg_input.count() > 0:
                    try:
                        sg_input.focus()
                        self.page.wait_for_timeout(200)
                        sg_input.blur()
                    except Exception:
                        pass
            else:
                logger.warning("[bms_instance_create] 未找到安全组选择器")
            self.page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"[bms_instance_create] 选择安全组失败: {e}")

        # 3. 填写密码
        pwd = password if password else "Sugon@1234"
        try:
            pwd_item = self.page.locator(".el-form-item").filter(has_text=re.compile(r"^密码$"))
            if pwd_item.locator("input").count() > 0:
                pwd_item.locator("input").first.fill(pwd)
                logger.info("[bms_instance_create] 密码填写成功")
            else:
                logger.warning("[bms_instance_create] 未找到密码输入框")
        except Exception as e:
            logger.warning(f"[bms_instance_create] 填写密码失败: {e}")
        self.page.wait_for_timeout(300)
        try:
            confirm_item = self.page.locator(".el-form-item").filter(has_text="确认密码")
            if confirm_item.locator("input").count() > 0:
                confirm_item.locator("input").first.fill(pwd)
                logger.info("[bms_instance_create] 确认密码填写成功")
            else:
                logger.warning("[bms_instance_create] 未找到确认密码输入框")
        except Exception as e:
            logger.warning(f"[bms_instance_create] 填写确认密码失败: {e}")
        self.page.wait_for_timeout(300)

        # 4. 选择镜像
        try:
            image_section = self.page.locator(".el-form-item").filter(has_text=re.compile(r"^镜像$"))
            # 等待镜像列表加载完成（至少有一行数据）
            try:
                image_section.locator("table tbody tr").first.wait_for(state="visible", timeout=5000)
            except Exception:
                pass
            self.page.wait_for_timeout(800)
            image_rows = image_section.locator("table tbody tr").all()
            # 打印所有镜像行内容，便于排查
            for idx, row in enumerate(image_rows):
                logger.info(f"[bms_instance_create] 镜像行{idx}: {row.text_content() or ''!r}")

            selected = False
            # 优先匹配指定的 image_name
            if image_name and image_rows:
                for row in image_rows:
                    txt = row.text_content() or ""
                    if image_name in txt:
                        if self._click_el_radio(row):
                            selected = True
                            logger.info(f"[bms_instance_create] 镜像选择成功({image_name})")
                            break
                        else:
                            logger.warning(f"[bms_instance_create] 镜像行匹配'{image_name}'但radio点击失败")
            # 若未匹配到，尝试关键词 '裸金属'
            if not selected and image_rows:
                for row in image_rows:
                    txt = row.text_content() or ""
                    if "裸金属" in txt:
                        if self._click_el_radio(row):
                            selected = True
                            logger.info("[bms_instance_create] 镜像选择成功(裸金属)")
                            break
            # 最终 fallback 选第一个
            if not selected and image_rows:
                if self._click_el_radio(image_rows[0]):
                    logger.info("[bms_instance_create] 镜像选择成功(第一个)")
                else:
                    logger.warning("[bms_instance_create] 镜像行无radio")
            elif not image_rows:
                # fallback: JS click first radio in image table
                result = self.page.evaluate("""() => {
                    const items = document.querySelectorAll('.el-form-item');
                    for (const item of items) {
                        const label = item.querySelector('label');
                        if (label && label.textContent.trim() === '镜像') {
                            const radio = item.querySelector('table tbody tr input[type=radio]');
                            if (radio) { radio.click(); return true; }
                        }
                    }
                    return false;
                }""")
                logger.info(f"[bms_instance_create] 镜像JS选择结果: {result}")
            self.page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"[bms_instance_create] 选择镜像失败: {e}")

        # 5. 选择服务器
        try:
            server_section = None
            for pattern in ["服务器", "server"]:
                sec = self.page.locator(".el-form-item").filter(has_text=re.compile(pattern, re.IGNORECASE))
                if sec.count() > 0:
                    server_section = sec
                    logger.info(f"[bms_instance_create] 找到服务器区域(模式: {pattern})")
                    break
            if not server_section:
                logger.warning("[bms_instance_create] 未通过locator找到服务器区域，尝试JS")
                server_section = self.page.locator(".el-form-item").nth(4)

            server_rows = self._wait_for_table_rows(server_section, timeout=10000)
            selected = False
            if server_name and server_rows:
                for row in server_rows:
                    txt = row.text_content() or ""
                    if server_name in txt:
                        if self._click_el_radio(row):
                            selected = True
                            logger.info(f"[bms_instance_create] 服务器选择成功({server_name})")
                            break
            if not selected and bmc_ip and server_rows:
                for row in server_rows:
                    txt = row.text_content() or ""
                    if bmc_ip in txt:
                        if self._click_el_radio(row):
                            selected = True
                            logger.info(f"[bms_instance_create] 服务器选择成功({bmc_ip})")
                            break
            if not selected and server_rows:
                if self._click_el_radio(server_rows[0]):
                    logger.info("[bms_instance_create] 服务器选择成功(第一个)")
                else:
                    logger.warning("[bms_instance_create] 服务器行无radio")
            elif not server_rows:
                logger.warning("[bms_instance_create] 未找到服务器行，尝试JS选择")
                result = self.page.evaluate("""(bmcIp) => {
                    const items = document.querySelectorAll('.el-form-item');
                    for (const item of items) {
                        const label = item.querySelector('label');
                        if (label && label.textContent.includes('服务器')) {
                            const table = item.querySelector('table');
                            if (!table) return 'no-table';
                            const rows = table.querySelectorAll('tbody tr');
                            for (const row of rows) {
                                if (bmcIp && row.textContent.includes(bmcIp)) {
                                    const radio = row.querySelector('.el-radio');
                                    if (radio && !radio.classList.contains('is-disabled')) {
                                        radio.click(); return 'found-bmc';
                                    }
                                }
                            }
                            const firstRadio = table.querySelector('.el-radio');
                            if (firstRadio && !firstRadio.classList.contains('is-disabled')) {
                                firstRadio.click(); return 'first-available';
                            }
                            return 'all-disabled';
                        }
                    }
                    return 'no-section';
                }""", bmc_ip)
                logger.info(f"[bms_instance_create] 服务器JS选择结果: {result}")
            self.page.wait_for_timeout(1500)
        except Exception as e:
            logger.warning(f"[bms_instance_create] 选择服务器失败: {e}")

        # 6. 选择系统盘
        try:
            disk_section = None
            for _ in range(20):
                for pattern in ["磁盘", "disk"]:
                    sec = self.page.locator(".el-form-item").filter(has_text=re.compile(pattern, re.IGNORECASE))
                    if sec.count() > 0:
                        disk_section = sec
                        logger.info(f"[bms_instance_create] 找到磁盘区域(模式: {pattern})")
                        break
                if disk_section:
                    break
                self.page.wait_for_timeout(500)
            if not disk_section:
                logger.warning("[bms_instance_create] 未通过locator找到磁盘区域，尝试JS")
                disk_section = self.page.locator(".el-form-item").nth(5)

            disk_rows = self._wait_for_table_rows(disk_section, timeout=8000)
            selected = False
            for row in disk_rows:
                txt = row.text_content() or ""
                if system_disk in txt:
                    if self._click_el_radio(row):
                        selected = True
                        logger.info(f"[bms_instance_create] 磁盘选择成功({system_disk})")
                        break
            if not selected and disk_rows:
                if self._click_el_radio(disk_rows[0]):
                    logger.info("[bms_instance_create] 磁盘选择成功(第一个)")
                else:
                    logger.warning("[bms_instance_create] 磁盘行无radio")
            elif not disk_rows:
                logger.warning("[bms_instance_create] 未找到磁盘行，尝试JS选择")
                result = self.page.evaluate("""() => {
                    const items = document.querySelectorAll('.el-form-item');
                    for (const item of items) {
                        const label = item.querySelector('label');
                        if (label && label.textContent.includes('磁盘')) {
                            const radios = item.querySelectorAll('table tbody tr .el-radio');
                            if (radios.length > 0) { radios[0].click(); return true; }
                        }
                    }
                    return false;
                }""")
                logger.info(f"[bms_instance_create] 磁盘JS选择结果: {result}")
            self.page.wait_for_timeout(800)
        except Exception as e:
            logger.warning(f"[bms_instance_create] 选择磁盘失败: {e}")

        # 7. 配置网络
        try:
            net_section = self.page.locator(".el-form-item").filter(has_text="专有网络")
            net_selects = net_section.locator(".row-layout .el-select").all()
            if len(net_selects) >= 2:
                # 选择网络
                net_selects[0].click()
                self.page.wait_for_timeout(500)
                net_opts = self.page.locator(".el-select-dropdown:visible li")
                if network_name:
                    net_opt = net_opts.filter(has_text=network_name)
                    if net_opt.count() > 0:
                        net_opt.first.click()
                        logger.info(f"[bms_instance_create] 网络选择成功({network_name})")
                    else:
                        net_opts.first.click()
                        logger.info("[bms_instance_create] 网络选择成功(第一个)")
                else:
                    bms_opt = net_opts.filter(has_text="bms")
                    if bms_opt.count() > 0:
                        bms_opt.first.click()
                    else:
                        net_opts.first.click()
                    logger.info("[bms_instance_create] 网络选择成功")
                self.page.wait_for_timeout(500)
                # 选择子网
                net_selects[1].click()
                self.page.wait_for_timeout(500)
                subnet_opts = self.page.locator(".el-select-dropdown:visible li")
                if subnet_name:
                    subnet_opt = subnet_opts.filter(has_text=subnet_name)
                    if subnet_opt.count() > 0:
                        subnet_opt.first.click()
                        logger.info(f"[bms_instance_create] 子网选择成功({subnet_name})")
                    else:
                        subnet_opts.first.click()
                        logger.info("[bms_instance_create] 子网选择成功(第一个)")
                else:
                    subnet_opts.first.click()
                    logger.info("[bms_instance_create] 子网选择成功(第一个)")
                self.page.wait_for_timeout(500)
                # 分配模式（自动分配）
                if len(net_selects) >= 3:
                    net_selects[2].click()
                    self.page.wait_for_timeout(500)
                    auto_opt = self.page.locator(".el-select-dropdown:visible li").filter(has_text="自动分配")
                    if auto_opt.count() > 0:
                        auto_opt.first.click()
                    else:
                        self.page.locator(".el-select-dropdown:visible li").first.click()
                logger.info("[bms_instance_create] 网络配置成功")
            else:
                # flat_network 模式：表格多选
                net_rows = net_section.locator("table tbody tr").all()
                selected = False
                for row in net_rows:
                    txt = row.text_content() or ""
                    if network_name and network_name in txt:
                        chk = row.locator(".el-checkbox, input[type='checkbox']").first
                        if chk.count() > 0:
                            chk.click()
                            selected = True
                            logger.info(f"[bms_instance_create] 网络(flat)配置成功({network_name})")
                        break
                    elif not network_name and "bms" in txt:
                        chk = row.locator(".el-checkbox, input[type='checkbox']").first
                        if chk.count() > 0:
                            chk.click()
                            selected = True
                            logger.info("[bms_instance_create] 网络(flat)配置成功")
                        break
                if not selected and net_rows:
                    chk = net_rows[0].locator(".el-checkbox, input[type='checkbox']").first
                    if chk.count() > 0:
                        chk.click()
                        logger.info("[bms_instance_create] 网络(flat)配置成功(第一个)")
                elif not net_rows:
                    logger.warning("[bms_instance_create] 未找到网络行")
        except Exception as e:
            logger.warning(f"[bms_instance_create] 配置网络失败: {e}")

        self.page.wait_for_timeout(1000)

        # 8. 点击立即创建
        logger.info("[bms_instance_create] 准备点击立即创建")
        # 先截图记录表单状态
        try:
            ss_path = "screenshots/bms_before_create.png"
            self.page.screenshot(path=ss_path)
            logger.info(f"[bms_instance_create] 创建前截图: {ss_path}")
        except Exception:
            pass

        try:
            create_btn = self.page.locator("button, .cloud-button-btn, .cloud-button--primary").filter(has_text="立即创建")
            if create_btn.count() > 0:
                create_btn.first.click()
                logger.info("[bms_instance_create] 立即创建按钮已点击")
            else:
                self.page.get_by_text("立即创建", exact=False).first.click()
                logger.info("[bms_instance_create] 立即创建按钮已点击(get_by_text)")
        except Exception as e:
            logger.warning(f"[bms_instance_create] 点击立即创建失败: {e}")

        # 等待页面导航或弹窗（最长5秒）
        navigated = False
        for i in range(10):
            self.page.wait_for_timeout(500)
            if "/bms-physical-host-create" not in self.page.url:
                navigated = True
                logger.info(f"[bms_instance_create] 页面已导航离开创建页: {self.page.url}")
                break
        if not navigated:
            logger.warning("[bms_instance_create] 点击创建后页面未导航，可能存在校验错误")
            # 检查 inline 校验错误
            try:
                err_fields = self.page.locator(".el-form-item__error").all()
                for ef in err_fields:
                    if ef.is_visible():
                        logger.warning(f"[bms_instance_create] 表单校验错误: {ef.text_content()}")
            except Exception:
                pass
            # 检查弹窗
            try:
                error_popup = self.page.locator(".el-message--error, .sugon-message-error").filter(has_text=re.compile(r"错误|失败|不能为空"))
                if error_popup.count() > 0 and error_popup.first.is_visible():
                    logger.warning(f"[bms_instance_create] 创建错误弹窗: {error_popup.first.text_content()}")
            except Exception:
                pass
            # 截图记录
            try:
                ss_path = "screenshots/bms_after_create_fail.png"
                self.page.screenshot(path=ss_path)
                logger.info(f"[bms_instance_create] 创建失败后截图: {ss_path}")
            except Exception:
                pass

    def bms_instance_delete(self, name):
        self._goto_submenu_safe("裸金属实例")
        self.search(name)
        row = self._get_row_by_name(name)
        if row:
            try:
                self._js_click_action(row, "删除")
            except Exception:
                self.click_action(name, "删除")
            self._confirm_sugon_dialog()
            self._wait_for_row_absence("裸金属实例", name, label="裸金属实例")

    def bms_instance_cleanup(self):
        self._goto_submenu_safe("裸金属实例")
        for r in self._get_rows():
            try:
                self._js_click_action(r, "删除")
                self._confirm_sugon_dialog()
                self.page.wait_for_timeout(2000)
            except Exception:
                pass

    # ---- bind / unbind EIP ----

    def bms_instance_bind_eip(self, instance_name: str, pool_name: str = None, eip_ip: str = "") -> str:
        """为裸金属实例绑定公网IP。

        Args:
            instance_name: 裸金属实例名称
            pool_name: 资源池名称，默认从 Config 读取
            eip_ip: 指定要绑定的弹性公网IP，为空则自动选择第一个可用IP

        Returns:
            str: 绑定的公网IP地址
        """
        if pool_name is None:
            from sugon_web.config.config import Config
            pool_name = Config.get("network") or "public_net(基础版)"
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "绑定公网IP")
        self.page.wait_for_timeout(3000)

        dlg = self.page.locator('[role="dialog"]').filter(has_text="绑定公网IP").last

        # 步骤1：选择端口（radio）—— 轮询等待端口列表加载
        port_rows = []
        for _ in range(10):
            port_rows = dlg.locator("table tbody tr").all()
            if port_rows and len(port_rows) > 0 and port_rows[0].locator("td").count() > 1:
                break
            logger.info("端口列表为空或加载中，等待...")
            self.page.wait_for_timeout(1500)
        if not port_rows:
            raise Exception("绑定公网IP对话框中未找到端口列表")
        self._click_el_radio(port_rows[0])
        self.page.wait_for_timeout(800)

        # 点击下一步
        next_btn = dlg.locator("button, .cloud-button-btn, .cloud-button--primary").filter(has_text="下一步")
        if next_btn.count() > 0:
            next_btn.first.click()
        else:
            dlg.get_by_text("下一步", exact=False).first.click()
        self.page.wait_for_timeout(1500)

        # 步骤2：选择资源池
        pool_select = dlg.locator(".el-form-item").filter(has_text="资源池").locator(".el-select").first
        if pool_select.count() > 0:
            pool_select.click()
            self.page.wait_for_timeout(500)
            pool_opt = self.page.locator(".el-select-dropdown:visible li").filter(has_text=pool_name)
            if pool_opt.count() > 0:
                pool_opt.first.click()
                logger.info(f"选择资源池: {pool_name}")
            else:
                self.page.locator(".el-select-dropdown:visible li").first.click()
                logger.info("选择资源池(第一个)")
            # 等待资源池切换后公网IP列表加载完成（API请求+渲染）
            self.page.wait_for_timeout(3000)

        # 选择公网IP（radio）—— 若列表为空则等待重试
        ip_rows = []
        for _ in range(10):
            # 步骤2的公网IP表格是可见的，端口表格是隐藏的；只取可见行
            all_rows = dlg.locator("table tbody tr, .el-table__row").all()
            ip_rows = [r for r in all_rows if r.is_visible()]
            if ip_rows:
                logger.info(f"公网IP列表找到 {len(ip_rows)} 行可见行")
                break
            logger.info("公网IP列表为空，等待加载...")
            self.page.wait_for_timeout(2000)
        if not ip_rows:
            raise Exception("绑定公网IP对话框中未找到公网IP列表")

        # 若指定了 eip_ip，查找包含该 IP 的行；支持翻页查找
        target_row = ip_rows[0]
        if eip_ip:
            page_num = 1
            while True:
                for r in ip_rows:
                    row_text = r.text_content() or ""
                    if eip_ip in row_text:
                        target_row = r
                        logger.info(f"找到指定的弹性公网IP行: {eip_ip} (第{page_num}页)")
                        break
                else:
                    # 当前页未找到，尝试翻页（分页器可能在对话框外）
                    # 限制最大翻页次数，避免无限循环
                    if page_num >= 10:
                        logger.warning(f"已翻页{page_num}次仍未找到 {eip_ip}，回退到第一行")
                        break

                    # 策略1：滚动表格加载更多行（虚拟滚动场景）
                    scrolled = False
                    try:
                        table_body = dlg.locator(".el-table__body-wrapper").first
                        if table_body.count() > 0:
                            table_body.evaluate("el => { el.scrollTop = el.scrollHeight; }")
                            self.page.wait_for_timeout(1500)
                            scrolled = True
                            all_rows = dlg.locator("table tbody tr, .el-table__row").all()
                            new_ip_rows = [r for r in all_rows if r.is_visible()]
                            if len(new_ip_rows) > len(ip_rows):
                                logger.info(f"滚动后公网IP列表从 {len(ip_rows)} 行变为 {len(new_ip_rows)} 行")
                                ip_rows = new_ip_rows
                                continue  # 用新行数据重新循环查找
                    except Exception as scroll_err:
                        logger.debug(f"表格滚动失败: {scroll_err}")

                    # 策略2：JS 查找对话框内所有可翻页的分页器
                    page_result = self.page.evaluate("""() => {
                        // 找到包含表格的可见对话框
                        let dialog = null;
                        const candidates = document.querySelectorAll('.el-dialog__wrapper:not([style*="display: none"]) .el-dialog, [role="dialog"]');
                        for (const c of candidates) {
                            if (c.offsetParent !== null && c.querySelector('table, .el-table')) { dialog = c; break; }
                        }
                        if (!dialog) return {status: 'no-dialog'};

                        // 查找对话框内所有分页器，优先点击有未禁用下一页按钮的
                        const pags = dialog.querySelectorAll('.el-pagination');
                        for (const pag of pags) {
                            const nextBtn = pag.querySelector('button.btn-next');
                            if (nextBtn && !nextBtn.disabled && !nextBtn.classList.contains('disabled')) {
                                nextBtn.click();
                                return {status: 'clicked'};
                            }
                            // 备选：通过页码按钮判断（有 page-count > 1 时找第2页）
                            const pagerItems = pag.querySelectorAll('.el-pager li');
                            if (pagerItems.length > 1) {
                                pagerItems[1].click(); // 点第2页
                                return {status: 'clicked-page2'};
                            }
                        }
                        return {status: 'disabled'};
                    }""")
                    if page_result.get("status") in ("clicked", "clicked-page2"):
                        logger.info(f"第{page_num}页未找到 {eip_ip}，尝试下一页")
                        self.page.wait_for_timeout(2500)
                        page_num += 1
                        all_rows = dlg.locator("table tbody tr, .el-table__row").all()
                        ip_rows = [r for r in all_rows if r.is_visible()]
                        continue
                    else:
                        logger.info(f"无法翻页: {page_result.get('status')}，未找到指定的弹性公网IP {eip_ip}")
                    logger.warning(f"未找到指定的弹性公网IP {eip_ip}，回退到第一行")
                    break
                break

        # 点击目标行的 radio
        radio_clicked = False
        for sel in [".el-radio", ".el-radio__input", "input[type='radio']"]:
            radios = target_row.locator(sel)
            if radios.count() > 0:
                try:
                    radios.first.scroll_into_view_if_needed()
                    radios.first.click()
                    radio_clicked = True
                    logger.info(f"通过选择器 '{sel}' 点击 radio 成功")
                    break
                except Exception as e:
                    logger.warning(f"选择器 '{sel}' 点击失败: {e}")
        if not radio_clicked:
            # 备用：JS 直接触发 radio 点击
            try:
                target_row.evaluate("""row => {
                    const radio = row.querySelector('.el-radio input[type=radio], input[type=radio]');
                    if (radio) { radio.click(); return 'clicked'; }
                    const label = row.querySelector('.el-radio');
                    if (label) { label.click(); return 'label-clicked'; }
                    return 'not-found';
                }""")
                radio_clicked = True
                logger.info("JS 触发 radio 点击成功")
            except Exception as e:
                logger.warning(f"JS 点击 radio 失败: {e}")
        if not radio_clicked:
            raise Exception("未能选中公网IP")
        self.page.wait_for_timeout(1000)

        # 获取选中的IP地址
        ip_address = ""
        try:
            ip_address = target_row.locator("td").nth(1).text_content().strip()
        except Exception:
            pass

        # 点击确定
        confirm_btn = dlg.locator("button, .cloud-button-btn, .cloud-button--primary").filter(has_text="确定")
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
        else:
            dlg.get_by_text("确定", exact=False).first.click()

        self.page.wait_for_timeout(2000)
        self.assert_popup_success()
        logger.info(f"实例 '{instance_name}' 绑定公网IP成功: {ip_address}")
        return ip_address

    def bms_instance_unbind_eip(self, instance_name: str):
        """为裸金属实例解绑公网IP。

        Args:
            instance_name: 裸金属实例名称
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "解除绑定公网IP")
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(2000)
        self.assert_popup_success()
        logger.info(f"实例 '{instance_name}' 解绑公网IP成功")

    def bms_instance_view_monitor(self, instance_name: str) -> dict:
        """查看裸金属实例监控信息。通过悬浮图表读取 tooltip 数值。

        Args:
            instance_name: 裸金属实例名称

        Returns:
            dict: 包含 cpu_text、memory_text 的字典
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        # 预安装 echarts.init 拦截器，记录弹窗中创建的实例
        self.page.evaluate("""() => {
            if (!window._echartsHookInstalled && window.echarts && window.echarts.init) {
                window._echarts_instances = [];
                const origInit = window.echarts.init;
                window.echarts.init = function(dom, theme, opts) {
                    const inst = origInit.apply(this, arguments);
                    if (inst && dom) {
                        window._echarts_instances.push({id: inst.id, domTag: dom.tagName, domClass: dom.className});
                    }
                    return inst;
                };
                window._echartsHookInstalled = true;
            }
        }""")

        self._js_click_action(row, "查看监控")
        # 监控图表加载需要时间，Jenkins 环境给予更充足等待
        self.page.wait_for_timeout(15000)

        # 监控可能是弹窗或新页面，优先查找弹窗
        monitor_dlg = self.page.locator('[role="dialog"]').filter(
            has_text=re.compile(r"监控|性能")
        ).last

        if monitor_dlg.count() == 0:
            monitor_container = self.page.locator("body")
        else:
            monitor_container = monitor_dlg

        # 截图用于诊断
        screenshot_path = f"monitor_dialog_{instance_name}.png"
        self.page.screenshot(path=screenshot_path)
        logger.info(f"监控对话框截图已保存: {screenshot_path}")

        cpu_value = ""
        mem_value = ""

        # 策略1：通过 echarts API 直接读取图表数据
        # 1a. 先尝试从拦截器记录的实例 ID 读取（优先读取当前可见区域的）
        # 1b. 再尝试标准 getInstanceByDom
        chart_data = self.page.evaluate("""() => {
            const results = [];
            if (!window.echarts) return {results, diagnostics: {reason: 'no_echarts'}};
            const diagnostics = {hookCount: 0, byDomCount: 0, byIdCount: 0, byHookCount: 0, visibleHookCount: 0, canvasCount: 0, attrCount: 0};

            // 辅助函数：判断元素是否在视口内且可见
            function isVisible(el) {
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.left >= 0 && rect.bottom <= window.innerHeight && rect.right <= window.innerWidth;
            }

            // 1a. 从拦截器记录的实例 ID 读取，优先读取当前可见的 canvas 对应的实例
            if (window._echarts_instances && window._echarts_instances.length > 0) {
                diagnostics.hookCount = window._echarts_instances.length;
                for (const rec of window._echarts_instances) {
                    try {
                        const ec = window.echarts.getInstanceById(rec.id);
                        if (ec) {
                            diagnostics.byHookCount++;
                            // 尝试通过 dom 找到对应元素并检查可见性
                            let domEl = null;
                            if (rec.domTag && rec.domClass) {
                                const candidates = document.querySelectorAll(rec.domTag + '.' + rec.domClass.split(' ').join('.'));
                                for (const c of candidates) {
                                    const cEc = window.echarts.getInstanceByDom(c);
                                    if (cEc && cEc.id === rec.id) { domEl = c; break; }
                                }
                            }
                            const visible = domEl ? isVisible(domEl) : true;
                            if (visible) diagnostics.visibleHookCount++;
                            const opt = ec.getOption();
                            const title = opt.title?.[0]?.text || '';
                            // 同时检查 series 和 dataset 两种数据源
                            let seriesData = (opt.series || []).map(s => {
                                const data = s.data || [];
                                const last = data[data.length - 1];
                                return {name: s.name || '', lastValue: Array.isArray(last) ? last[1] : last, dataCount: data.length};
                            });
                            // 如果 series 为空但 dataset 有数据，构造 seriesData
                            if (seriesData.length === 0 && opt.dataset && opt.dataset.source) {
                                const src = opt.dataset.source;
                                if (src.length > 1) {
                                    // dataset.source[0] 是表头，后面是数据行
                                    const header = src[0];
                                    const lastRow = src[src.length - 1];
                                    for (let i = 1; i < header.length; i++) {
                                        seriesData.push({name: header[i], lastValue: lastRow[i], dataCount: src.length - 1});
                                    }
                                }
                            }
                            results.push({title, seriesData, source: 'hook', visible});
                        }
                    } catch(e) {}
                }
            }

            // 1b. 标准 getInstanceByDom（仅处理可见 canvas）
            document.querySelectorAll('canvas').forEach(c => {
                diagnostics.canvasCount++;
                try {
                    const ec = window.echarts.getInstanceByDom(c);
                    if (ec && isVisible(c)) {
                        diagnostics.byDomCount++;
                        const opt = ec.getOption();
                        const title = opt.title?.[0]?.text || '';
                        let seriesData = (opt.series || []).map(s => {
                            const data = s.data || [];
                            const last = data[data.length - 1];
                            return {name: s.name || '', lastValue: Array.isArray(last) ? last[1] : last, dataCount: data.length};
                        });
                        if (seriesData.length === 0 && opt.dataset && opt.dataset.source) {
                            const src = opt.dataset.source;
                            if (src.length > 1) {
                                const header = src[0];
                                const lastRow = src[src.length - 1];
                                for (let i = 1; i < header.length; i++) {
                                    seriesData.push({name: header[i], lastValue: lastRow[i], dataCount: src.length - 1});
                                }
                            }
                        }
                        results.push({title, seriesData, source: 'dom', visible: true});
                    }
                } catch(e) {}
            });

            // 1c. _echarts_instance 属性（仅处理可见元素）
            document.querySelectorAll('[_echarts_instance]').forEach(el => {
                diagnostics.attrCount++;
                try {
                    const id = el.getAttribute('_echarts_instance');
                    if (id && window.echarts.getInstanceById && isVisible(el)) {
                        const ec = window.echarts.getInstanceById(id);
                        if (ec) {
                            diagnostics.byIdCount++;
                            const opt = ec.getOption();
                            const title = opt.title?.[0]?.text || '';
                            let seriesData = (opt.series || []).map(s => {
                                const data = s.data || [];
                                const last = data[data.length - 1];
                                return {name: s.name || '', lastValue: Array.isArray(last) ? last[1] : last, dataCount: data.length};
                            });
                            if (seriesData.length === 0 && opt.dataset && opt.dataset.source) {
                                const src = opt.dataset.source;
                                if (src.length > 1) {
                                    const header = src[0];
                                    const lastRow = src[src.length - 1];
                                    for (let i = 1; i < header.length; i++) {
                                        seriesData.push({name: header[i], lastValue: lastRow[i], dataCount: src.length - 1});
                                    }
                                }
                            }
                            results.push({title, seriesData, source: 'attr', visible: true});
                        }
                    }
                } catch(e) {}
            });

            return {results, diagnostics};
        }""")
        logger.info(f"echarts 诊断信息: {chart_data.get('diagnostics')}")
        logger.info(f"echarts API 读取图表数据: {chart_data.get('results')}")
        chart_data = chart_data.get('results', [])

        # 优先处理当前可见区域的图表数据，再处理隐藏的（其他 tab）
        visible_charts = [c for c in chart_data if c.get("visible", True)]
        charts_to_process = visible_charts if visible_charts else chart_data
        logger.info(f"echarts 处理: 可见图表 {len(visible_charts)} 个, 总计 {len(chart_data)} 个")

        for chart in charts_to_process:
            title = chart.get("title", "")
            for s in chart.get("seriesData", []):
                val = s.get("lastValue")
                series_name = s.get("name", "")
                data_count = s.get("dataCount", 0)
                if val is not None and str(val) != "":
                    val_str = str(val)
                    # 通过 title 或 series name 匹配 CPU 使用率
                    is_cpu = (
                        "CPU使用率" in title
                        or ("CPU" in title and "使用率" in title)
                        or "cpu使用率" in series_name.lower()
                        or series_name.lower() == "cpu"
                        or "cpu" in series_name.lower()
                    )
                    # 通过 title 或 series name 匹配内存使用率
                    is_mem = (
                        "内存使用率" in title
                        or ("内存" in title and "使用率" in title)
                        or "内存使用率" in series_name
                        or series_name.lower() == "memory"
                        or "mem" in series_name.lower()
                    )
                    # 额外判断：如果 title 为空但 dataCount > 0，且 seriesName 包含 cpu/mem，也视为有效
                    if not title and data_count > 0:
                        if "cpu" in series_name.lower():
                            is_cpu = True
                        if "mem" in series_name.lower():
                            is_mem = True
                    if is_cpu and not cpu_value:
                        cpu_value = val_str + "%" if "%" not in val_str else val_str
                        logger.info(f"从echarts获取CPU [title={title}, series={series_name}]: {cpu_value}")
                    elif is_mem and not mem_value:
                        mem_value = val_str + "%" if "%" not in val_str else val_str
                        logger.info(f"从echarts获取内存 [title={title}, series={series_name}]: {mem_value}")

        # 策略2：悬浮到各个**可见** canvas 图表的多个位置，读取 tooltip
        if not cpu_value or not mem_value:
            canvases = monitor_container.locator("canvas").all()
            logger.info(f"找到 {len(canvases)} 个 canvas 元素，尝试悬浮读取 tooltip")

            visible_canvases = [c for c in canvases if c.is_visible()]
            logger.info(f"其中可见 canvas: {len(visible_canvases)} 个")

            for idx, canvas in enumerate(visible_canvases[:8]):
                if cpu_value and mem_value:
                    break
                try:
                    box = canvas.bounding_box()
                    if not box or box["width"] <= 0 or box["height"] <= 0:
                        continue

                    # 在图表上多个位置悬浮（x轴方向从左到右，y轴方向偏上偏下都试）
                    for pos_x in [0.25, 0.4, 0.55, 0.7]:
                        for pos_y in [0.3, 0.5, 0.7]:
                            x = box["x"] + box["width"] * pos_x
                            y = box["y"] + box["height"] * pos_y
                            self.page.mouse.move(x, y)
                            self.page.wait_for_timeout(1200)

                            # 读取页面上所有可能包含 tooltip 文本的元素
                            tooltip_text = self.page.evaluate("""() => {
                                const selectors = [
                                    '.echarts-tooltip',
                                    '.el-tooltip__popper',
                                    '[class*="tooltip"]',
                                    '[class*="Tooltip"]',
                                ];
                                for (const sel of selectors) {
                                    const els = document.querySelectorAll(sel);
                                    for (const el of els) {
                                        const text = (el.innerText || el.textContent || '').trim();
                                        if (text && text.includes('%')) return text;
                                    }
                                }
                                // fallback：查找 body 下所有包含 % 的文本节点
                                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                                const texts = [];
                                let node;
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    if (text.includes('%') && text.length < 200) {
                                        texts.push(text);
                                    }
                                }
                                return texts.join(' | ');
                            }""")

                            if tooltip_text and '%' in tooltip_text:
                                logger.info(f"canvas[{idx}] x={pos_x:.0%} y={pos_y:.0%} 文本: {tooltip_text[:300]}")
                                all_pct = re.findall(r"(\d+\.?\d*)\s*%", tooltip_text)
                                if all_pct:
                                    if not cpu_value:
                                        cpu_value = all_pct[0] + "%"
                                    if len(all_pct) > 1 and not mem_value:
                                        mem_value = all_pct[1] + "%"
                            if cpu_value and mem_value:
                                break
                        if cpu_value and mem_value:
                            break
                except Exception as e:
                    logger.warning(f"canvas[{idx}] 悬浮读取失败: {e}")

        # 策略2b：通过 DOM 文本直接读取可见的图表数值（不依赖 echarts API / tooltip）
        if not cpu_value or not mem_value:
            dom_values = self.page.evaluate("""() => {
                const result = {cpu: '', memory: ''};
                // 查找所有可能包含指标名称和数值的元素
                const cells = document.querySelectorAll('[role="dialog"] .chart-title, [role="dialog"] .monitor-title, [role="dialog"] .chart-header, [role="dialog"] h3, [role="dialog"] h4, [role="dialog"] .title');
                for (const cell of cells) {
                    const text = (cell.innerText || cell.textContent || '').trim();
                    const parent = cell.closest('.chart-wrapper, .monitor-item, [class*="chart"], [class*="monitor"]') || cell.parentElement;
                    if (!parent) continue;
                    const parentText = (parent.innerText || parent.textContent || '').trim();
                    // 在父容器内查找包含 % 的数值
                    const pctMatches = parentText.match(/(\d+\.?\d*)\s*%/g);
                    const firstPct = pctMatches ? pctMatches[0].replace(/\s*%/, '') + '%' : '';
                    if (!result.cpu && (text.includes('CPU使用率') || text.includes('CPU使用率'))) {
                        result.cpu = firstPct;
                    }
                    if (!result.memory && (text.includes('内存使用率') || text.includes('内存使用率'))) {
                        result.memory = firstPct;
                    }
                }
                return result;
            }""")
            if dom_values.get('cpu') and not cpu_value:
                cpu_value = dom_values['cpu']
                logger.info(f"从 DOM 文本获取CPU: {cpu_value}")
            if dom_values.get('memory') and not mem_value:
                mem_value = dom_values['memory']
                logger.info(f"从 DOM 文本获取内存: {mem_value}")

        # 策略3：如果悬浮未获取到数值，检查图表区域是否显示"暂无数据"
        if not cpu_value and not mem_value:
            chart_area_text = monitor_container.evaluate("""el => {
                const wrappers = el.querySelectorAll('.chart-wrapper, .monitor-chart, [class*="chart"], [class*="Chart"]');
                for (const w of wrappers) {
                    const text = w.innerText || w.textContent;
                    if (text && text.includes('暂无数据')) return 'no_data';
                }
                const canvases = el.querySelectorAll('canvas');
                for (const c of canvases) {
                    let parent = c.parentElement;
                    for (let i = 0; i < 3 && parent; i++) {
                        const text = parent.innerText || parent.textContent;
                        if (text && text.includes('暂无数据')) return 'no_data';
                        parent = parent.parentElement;
                    }
                }
                return 'has_canvas';
            }""")
            logger.info(f"图表区域状态: {chart_area_text}")
            if chart_area_text == 'no_data':
                return {"cpu_text": "", "memory_text": "", "no_data": True}

        logger.info(f"实例 '{instance_name}' 监控信息: CPU={cpu_value}, 内存={mem_value}")
        return {"cpu_text": cpu_value, "memory_text": mem_value, "no_data": False}

    def bms_instance_rename(self, instance_name: str, new_name: str, description: str = ""):
        """修改裸金属实例名称和描述。

        Args:
            instance_name: 当前实例名称
            new_name: 新名称
            description: 描述信息
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        # 截图诊断操作栏
        self.page.screenshot(path="before_rename_action.png")

        # 先展开"更多"下拉菜单
        more_btn = row.locator("button, .cloud-button-btn, a, span").filter(has_text=re.compile(r"更多|⋯|⋮"))
        if more_btn.count() > 0:
            try:
                more_btn.first.click(force=True)
                self.page.wait_for_timeout(1200)
                logger.info("已点击'更多'按钮展开下拉菜单")
            except Exception as e:
                logger.warning(f"点击'更多'按钮失败: {e}")

        # 截图诊断下拉菜单内容
        self.page.screenshot(path="rename_dropdown.png")

        # 诊断：获取下拉菜单中所有按钮的文本
        all_actions = self.page.evaluate("""() => {
            const items = document.querySelectorAll('.cloud-table-dropdown-item, .el-dropdown-menu__item, [class*="dropdown-item"]');
            return Array.from(items).map(i => i.innerText.trim()).filter(t => t);
        }""")
        logger.info(f"下拉菜单所有操作项: {all_actions}")

        # 尝试标准点击"修改名称"
        clicked = False
        for action_text in ["修改名称", "编辑名称", "修改"]:
            items = row.locator(".cloud-table-dropdown-item").filter(has_text=action_text)
            if items.count() > 0:
                try:
                    items.first.click()
                    clicked = True
                    logger.info(f"成功点击下拉菜单项 '{action_text}'")
                    break
                except Exception:
                    pass
            # 也尝试在整个页面中查找
            page_items = self.page.locator(".cloud-table-dropdown-item").filter(has_text=action_text)
            if page_items.count() > 0:
                try:
                    page_items.first.click()
                    clicked = True
                    logger.info(f"通过页面定位器成功点击 '{action_text}'")
                    break
                except Exception:
                    pass

        # 回退到 JavaScript 强制点击
        if not clicked:
            result = self.page.evaluate("""([name, action]) => {
                const allRows = document.querySelectorAll('table tr');
                for (const r of allRows) {
                    if (r.textContent.includes(name)) {
                        // 先显示所有隐藏的操作项
                        for (const i of r.querySelectorAll('.cloud-table-dropdown-item, .el-dropdown-menu__item, a, button, span')) {
                            i.classList.remove('cloud-table-dropdown-item-btn-hide');
                            i.style.display = 'block';
                            i.style.visibility = 'visible';
                        }
                        // 优先精确匹配 dropdown-item 中的操作
                        const allItems = r.querySelectorAll('.cloud-table-dropdown-item, .el-dropdown-menu__item, a, button, span');
                        for (const i of allItems) {
                            const text = i.textContent.trim();
                            // 精确匹配 action，排除"更多"按钮
                            if (text === action && !text.includes('更多')) {
                                i.click();
                                return 'clicked: ' + text;
                            }
                        }
                        // fallback：部分匹配（用于查看监控等复杂文本）
                        for (const i of allItems) {
                            const text = i.textContent.trim();
                            if (text.includes(action) && text !== '更多' && !text.includes('删除开机')) {
                                i.click();
                                return 'clicked: ' + text;
                            }
                        }
                        return 'not-found-after-show';
                    }
                }
                return 'row-not-found';
            }""", [instance_name, "修改"])
            logger.info(f"JavaScript 点击结果: {result}")

        self.page.wait_for_timeout(1500)

        # 查找修改名称对话框
        dlg = self.page.locator(".sugon-dialog, .el-dialog, [role='dialog']").filter(
            has_text=re.compile(r"修改名称|编辑名称|修改")
        ).last

        if dlg.count() == 0:
            # 尝试查找任何可见对话框
            for d in self.page.locator(".sugon-dialog, .el-dialog, [role='dialog']").all():
                if d.is_visible():
                    dlg_text = d.inner_text()
                    logger.info(f"发现可见对话框文本: {dlg_text[:100]}")
                    dlg = d
                    break

        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到修改名称对话框")

        dlg_text = dlg.inner_text()
        logger.info(f"对话框内容: {dlg_text[:200]}")

        # 填写名称
        name_input = dlg.locator(".el-form-item").filter(has_text=re.compile(r"名称")).locator("input").first
        if name_input.count() > 0:
            name_input.fill("")
            name_input.fill(new_name)
            logger.info(f"填写新名称: {new_name}")

        # 填写描述（如果存在描述输入框）
        desc_input = dlg.locator(".el-form-item").filter(has_text=re.compile(r"描述")).locator("input, textarea").first
        if desc_input.count() > 0:
            desc_input.fill("")
            desc_input.fill(description)
            logger.info(f"填写描述: {description}")

        # 点击保存/确定按钮
        for btn_text in ["保存", "确定", "提交"]:
            btn = dlg.locator("button, .cloud-button-btn, .el-button").filter(has_text=btn_text)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                logger.info(f"点击'{btn_text}'按钮提交修改")
                break

        self.page.wait_for_timeout(2000)
        self.assert_popup_success()
        logger.info(f"实例 '{instance_name}' 修改名称为 '{new_name}' 成功")

    def bms_instance_detail_assert_name(self, instance_name: str, expected_name: str, expected_desc: str = ""):
        """进入实例详情页，验证名称和描述。

        Args:
            instance_name: 实例名称（用于定位行）
            expected_name: 期望的名称
            expected_desc: 期望的描述
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        # 先关闭可能打开的下拉菜单
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 尝试点击名称列的链接进入详情页
        clicked = False
        try:
            name_link = row.locator("a, span").filter(has_text=re.compile(rf"^{re.escape(instance_name)}$"))
            if name_link.count() > 0:
                name_link.first.click()
                clicked = True
                logger.info("通过点击名称链接进入详情页")
        except Exception:
            pass

        if not clicked:
            # 回退：使用 JavaScript 点击行内的名称元素
            result = self.page.evaluate(
                """(name) => {
                    const rows = document.querySelectorAll('table tbody tr');
                    for (const r of rows) {
                        if (r.textContent.includes(name)) {
                            const nameEl = r.querySelector('td:nth-child(2) a, td:nth-child(2) span');
                            if (nameEl) {
                                nameEl.click();
                                return 'clicked';
                            }
                            r.click();
                            return 'row-clicked';
                        }
                    }
                    return 'not-found';
                }""", instance_name)
            logger.info(f"JS 进入详情页结果: {result}")

        self.page.wait_for_timeout(2500)

        # 验证详情页 URL
        if "/cloud-server-BMS-Soft-decoration-details" not in self.page.url:
            logger.warning(f"当前URL不是详情页: {self.page.url}")

        # 获取页面文本验证名称和描述
        page_text = self.page.evaluate("() => document.body.innerText || ''")

        assert expected_name in page_text, f"详情页未找到名称 '{expected_name}'"
        logger.info(f"详情页验证名称通过: {expected_name}")

        if expected_desc:
            assert expected_desc in page_text, f"详情页未找到描述 '{expected_desc}'"
            logger.info(f"详情页验证描述通过: {expected_desc}")

    def bms_instance_set_security_group(self, instance_name: str, security_group_name: str):
        """设置裸金属实例安全组。

        在"安全组设置"对话框中，取消所有已勾选的安全组，
        仅勾选指定的安全组，然后提交。

        Args:
            instance_name: 实例名称
            security_group_name: 目标安全组名称
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        # 点击"更多→设置安全组"
        self._js_click_action(row, "设置安全组")

        # 等待对话框出现
        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"安全组设置")
        ).last
        if dlg.count() == 0:
            # 回退：查找任何可见对话框
            for d in self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").all():
                if d.is_visible():
                    dlg = d
                    break
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到安全组设置对话框")

        # 等待表格加载完成（轮询等待数据出现）
        try:
            dlg.locator(".el-loading-mask").wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
        # 轮询等待表格有数据，最多10秒
        all_rows_text = []
        for _ in range(10):
            self.page.wait_for_timeout(1000)
            all_rows_text = self.page.evaluate("""() => {
                // 精确定位可见的"安全组设置"对话框
                const dialogs = document.querySelectorAll('.el-dialog, .sugon-dialog');
                let target = null;
                for (const d of dialogs) {
                    if (d.textContent.includes('安全组设置') && d.offsetParent !== null) {
                        target = d;
                        break;
                    }
                }
                if (!target) return [];
                return Array.from(target.querySelectorAll('table tbody tr')).map(r => r.textContent.trim());
            }""")
            if all_rows_text:
                break
        logger.info(f"安全组列表内容: {all_rows_text}")
        if not all_rows_text:
            ss_path = f"sg_dialog_empty_{int(time.time())}.png"
            self.page.screenshot(path=ss_path)
            logger.warning(f"安全组设置对话框表格为空，截图: {ss_path}")

        # 使用 JS 操作 checkbox：取消所有已勾选的，仅勾选目标
        result = self.page.evaluate(
            """(sgName) => {
                const dialogs = document.querySelectorAll('.el-dialog, .sugon-dialog');
                let dialog = null;
                for (const d of dialogs) {
                    if (d.textContent.includes('安全组设置') && d.offsetParent !== null) {
                        dialog = d;
                        break;
                    }
                }
                if (!dialog) return 'dialog-not-found';
                const rows = dialog.querySelectorAll('table tbody tr');
                let logs = [];
                for (const r of rows) {
                    const text = r.textContent || '';
                    const cbWrap = r.querySelector('.el-checkbox');
                    if (!cbWrap) continue;
                    const isChecked = cbWrap.classList.contains('is-checked');
                    if (text.includes(sgName)) {
                        if (!isChecked) {
                            cbWrap.click();
                            logs.push('checked:' + sgName);
                        } else {
                            logs.push('already-checked:' + sgName);
                        }
                    } else {
                        if (isChecked) {
                            cbWrap.click();
                            logs.push('unchecked:' + text.trim().substring(0, 30));
                        }
                    }
                }
                return logs.length ? logs.join(';') : 'no-rows';
            }""",
            security_group_name,
        )
        logger.info(f"安全组勾选操作结果: {result}")
        self.page.wait_for_timeout(500)

        # 点击确定（使用 JS 在目标对话框内精确查找并点击）
        click_result = self.page.evaluate(
            """() => {
                const dialogs = document.querySelectorAll('.el-dialog, .sugon-dialog');
                let dialog = null;
                for (const d of dialogs) {
                    if (d.textContent.includes('安全组设置') && d.offsetParent !== null) {
                        dialog = d;
                        break;
                    }
                }
                if (!dialog) return 'dialog-not-found';
                // 优先查找 button / .el-button / .cl-button
                const selectors = ['button', '.el-button', '.cl-button', '.cloud-button-btn', '[class*="primary"]'];
                for (const sel of selectors) {
                    const btns = dialog.querySelectorAll(sel);
                    for (const b of btns) {
                        if (b.textContent.trim() === '确定') {
                            b.click();
                            return 'clicked:' + sel;
                        }
                    }
                }
                // 最终回退：遍历所有子元素找文本为"确定"的叶子节点
                const walker = document.createTreeWalker(dialog, NodeFilter.SHOW_ELEMENT);
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    if (node.children.length === 0 && node.textContent.trim() === '确定') {
                        node.click();
                        return 'clicked:leaf';
                    }
                }
                return 'confirm-not-found';
            }"""
        )
        logger.info(f"点击确定按钮结果: {click_result}")
        self.page.wait_for_timeout(500)

        # 等待对话框关闭（最多5秒）
        try:
            dlg.wait_for(state="hidden", timeout=5000)
            logger.info("安全组设置对话框已关闭")
        except Exception:
            logger.warning("安全组设置对话框未在5秒内关闭，尝试继续断言弹窗")

        self.page.wait_for_timeout(1500)
        self.assert_popup_success()
        logger.info(f"实例 '{instance_name}' 安全组设置为 '{security_group_name}' 成功")

    def bms_instance_detail_assert_security_group(self, instance_name: str, expected_sg: str):
        """进入实例详情页，验证安全组信息。

        Args:
            instance_name: 实例名称（用于定位行）
            expected_sg: 期望的安全组名称
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        # 先关闭可能打开的下拉菜单
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击名称链接进入详情页
        clicked = False
        try:
            name_link = row.locator("a, span").filter(has_text=re.compile(rf"^{re.escape(instance_name)}$"))
            if name_link.count() > 0:
                name_link.first.click()
                clicked = True
                logger.info("通过点击名称链接进入详情页")
        except Exception:
            pass

        if not clicked:
            result = self.page.evaluate(
                """(name) => {
                    const rows = document.querySelectorAll('table tbody tr');
                    for (const r of rows) {
                        if (r.textContent.includes(name)) {
                            const nameEl = r.querySelector('td:nth-child(2) a, td:nth-child(2) span');
                            if (nameEl) { nameEl.click(); return 'clicked'; }
                            r.click();
                            return 'row-clicked';
                        }
                    }
                    return 'not-found';
                }""",
                instance_name,
            )
            logger.info(f"JS 进入详情页结果: {result}")

        self.page.wait_for_timeout(2500)

        # 在详情页查找安全组信息区域
        page_text = self.page.evaluate("() => document.body.innerText || ''")

        # 验证安全组信息标题存在
        assert "安全组信息" in page_text, "详情页未找到'安全组信息'区域"

        # 验证期望的安全组名称存在
        assert expected_sg in page_text, f"详情页未找到安全组 '{expected_sg}'"
        logger.info(f"详情页验证安全组通过: {expected_sg}")

    # ---- label ----

    def bms_label_create(self, name: str):
        """在裸金属BMS标签页面创建标签。

        Args:
            name: 标签名称（同时作为描述）
        """
        self._goto_submenu_safe("标签")
        self._click_cl_btn("新建")
        self.page.wait_for_timeout(1000)

        # 查找新建标签对话框
        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"新建标签")
        ).last
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到新建标签对话框")

        # 填写名称
        name_input = dlg.locator("input[type='text']").first
        if name_input.count() > 0:
            name_input.fill(name)
        else:
            # fallback: 通过label查找
            dlg.get_by_label("新建标签").locator("input[type='text']").fill(name)

        # 填写描述（若对话框存在描述字段）
        desc_input = dlg.get_by_role("textbox", name="请输入描述内容")
        if desc_input.count() > 0:
            desc_input.fill(name)
        else:
            # 部分环境新建标签对话框无描述字段，跳过
            other_inputs = dlg.locator("textarea, input")
            if other_inputs.count() > 1:
                other_inputs.nth(1).fill(name)
            else:
                logger.info("新建标签对话框无描述字段，跳过描述填写")

        # 点击确定
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(1500)
        self.assert_popup_success("新建标签成功")
        logger.info(f"标签 '{name}' 创建成功")
        return name

    def bms_label_delete(self, name: str):
        """在裸金属BMS标签页面删除标签。

        Args:
            name: 标签名称
        """
        self._goto_submenu_safe("标签")
        self.bms_search(name)
        self.page.wait_for_timeout(1500)
        row = self._get_row_by_name(name)
        if not row:
            logger.warning(f"标签 '{name}' 不存在，跳过删除")
            return
        self._js_click_action(row, "删除")
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(1500)
        logger.info(f"标签 '{name}' 删除成功")

    def _bms_transfer_label(self, dlg, label_name: str, direction: str):
        """在标签设置对话框中执行标签转移操作。

        Args:
            dlg: 对话框 locator
            label_name: 标签名称
            direction: "bind" 表示左→右（绑定），"unbind" 表示右→左（解绑）
        """
        # 等待对话框稳定
        self.page.wait_for_timeout(800)

        # 获取左右面板
        panels = dlg.locator(".el-transfer-panel").all()
        if len(panels) < 2:
            raise Exception("未找到 Transfer 面板")
        src_panel = panels[0] if direction == "bind" else panels[1]
        dst_panel = panels[1] if direction == "bind" else panels[0]

        # 在源面板中查找目标标签
        src_items = src_panel.locator(".el-transfer-panel__item, .el-checkbox").all()
        target_item = None
        for item in src_items:
            text = item.inner_text().strip()
            if label_name in text:
                target_item = item
                break
        if not target_item:
            # 标签可能已经在目标面板中
            dst_items = dst_panel.locator(".el-transfer-panel__item, .el-checkbox").all()
            for item in dst_items:
                if label_name in item.inner_text().strip():
                    logger.info(f"标签 '{label_name}' 已在目标面板中，无需转移")
                    return
            raise Exception(f"在源面板中未找到标签 '{label_name}'")

        # 点击标签项选中它
        target_item.click()
        self.page.wait_for_timeout(500)

        # 点击转移按钮（使用 JS 避免选择器不稳定）
        btn_icon = "arrow-right" if direction == "bind" else "arrow-left"
        result = self.page.evaluate(
            f"""(iconClass) => {{
                const dialog = document.querySelector('.el-dialog__body');
                if (!dialog) return 'dialog-not-found';
                const btns = dialog.querySelectorAll('button');
                for (const b of btns) {{
                    if (b.disabled) continue;
                    const icon = b.querySelector('i');
                    if (icon && (icon.classList.contains(iconClass) || icon.className.includes(iconClass))) {{
                        b.click();
                        return 'clicked';
                    }}
                }}
                // fallback: 通过位置判断（第一个按钮是右移，第二个是左移）
                const transferBtns = dialog.querySelectorAll('.el-transfer__button');
                if (transferBtns.length >= 2) {{
                    const idx = iconClass.includes('right') ? 0 : 1;
                    if (!transferBtns[idx].disabled) {{
                        transferBtns[idx].click();
                        return 'clicked-fallback';
                    }}
                }}
                return 'btn-not-found';
            }}""",
            btn_icon,
        )
        logger.info(f"标签转移操作结果 ({direction}): {result}")
        self.page.wait_for_timeout(1000)

        # 验证标签已出现在目标面板
        dst_items = dst_panel.locator(".el-transfer-panel__item, .el-checkbox").all()
        found = any(label_name in item.inner_text().strip() for item in dst_items)
        if not found:
            raise Exception(f"标签转移后未在目标面板中找到 '{label_name}'")

    def bms_instance_bind_label(self, instance_name: str, label_name: str):
        """为裸金属实例绑定标签。

        Args:
            instance_name: 实例名称
            label_name: 标签名称
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "标签设置")
        self.page.wait_for_timeout(2000)

        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"标签设置")
        ).last
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到标签设置对话框")

        self._bms_transfer_label(dlg, label_name, "bind")

        # 关闭对话框
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1500)
        logger.info(f"实例 '{instance_name}' 绑定标签 '{label_name}' 成功")

    def bms_instance_unbind_label(self, instance_name: str, label_name: str):
        """为裸金属实例解绑标签。

        Args:
            instance_name: 实例名称
            label_name: 标签名称
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "标签设置")
        self.page.wait_for_timeout(2000)

        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"标签设置")
        ).last
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到标签设置对话框")

        self._bms_transfer_label(dlg, label_name, "unbind")

        # 关闭对话框
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1500)
        logger.info(f"实例 '{instance_name}' 解绑标签 '{label_name}' 成功")

    def bms_instance_detail_assert_label(self, instance_name: str, expected_label: str):
        """进入实例详情页，验证标签信息。

        Args:
            instance_name: 实例名称
            expected_label: 期望的标签名称
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        clicked = False
        try:
            name_link = row.locator("a, span").filter(has_text=re.compile(rf"^{re.escape(instance_name)}$"))
            if name_link.count() > 0:
                name_link.first.click()
                clicked = True
                logger.info("通过点击名称链接进入详情页")
        except Exception:
            pass

        if not clicked:
            result = self.page.evaluate(
                """(name) => {
                    const rows = document.querySelectorAll('table tbody tr');
                    for (const r of rows) {
                        if (r.textContent.includes(name)) {
                            const nameEl = r.querySelector('td:nth-child(2) a, td:nth-child(2) span');
                            if (nameEl) { nameEl.click(); return 'clicked'; }
                            r.click();
                            return 'row-clicked';
                        }
                    }
                    return 'not-found';
                }""",
                instance_name,
            )
            logger.info(f"JS 进入详情页结果: {result}")

        self.page.wait_for_timeout(2500)

        page_text = self.page.evaluate("() => document.body.innerText || ''")

        # 验证标签信息存在
        assert "标签" in page_text, "详情页未找到'标签'信息"
        assert expected_label in page_text, f"详情页未找到标签 '{expected_label}'"
        logger.info(f"详情页验证标签通过: {expected_label}")

    def bms_instance_detail_assert_label_absent(self, instance_name: str, absent_label: str):
        """进入实例详情页，验证指定标签已不存在。

        Args:
            instance_name: 实例名称
            absent_label: 期望已移除的标签名称
        """
        self._goto_submenu_safe("裸金属实例")
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        clicked = False
        try:
            name_link = row.locator("a, span").filter(has_text=re.compile(rf"^{re.escape(instance_name)}$"))
            if name_link.count() > 0:
                name_link.first.click()
                clicked = True
                logger.info("通过点击名称链接进入详情页")
        except Exception:
            pass

        if not clicked:
            result = self.page.evaluate(
                """(name) => {
                    const rows = document.querySelectorAll('table tbody tr');
                    for (const r of rows) {
                        if (r.textContent.includes(name)) {
                            const nameEl = r.querySelector('td:nth-child(2) a, td:nth-child(2) span');
                            if (nameEl) { nameEl.click(); return 'clicked'; }
                            r.click();
                            return 'row-clicked';
                        }
                    }
                    return 'not-found';
                }""",
                instance_name,
            )
            logger.info(f"JS 进入详情页结果: {result}")

        self.page.wait_for_timeout(2500)

        page_text = self.page.evaluate("() => document.body.innerText || ''")

        # 验证标签信息区域中不包含指定标签
        assert absent_label not in page_text, f"详情页不应存在标签 '{absent_label}'，但页面文本中包含"
        logger.info(f"详情页验证标签已移除: '{absent_label}' 不存在")

    def bms_label_assert_bind_status(self, label_name: str, bound: bool = True):
        """在标签页面验证标签的绑定状态。

        Args:
            label_name: 标签名称
            bound: 期望的绑定状态，True表示已绑定，False表示未绑定
        """
        self._goto_submenu_safe("标签")
        self.bms_search(label_name)
        self.page.wait_for_timeout(2000)
        row_data = self.get_row_data(label_name)
        bind_field = row_data.get("是否绑定实例", "")
        expected = "是" if bound else "否"
        assert expected in bind_field, f"标签 '{label_name}' 绑定状态期望为 '{expected}'，实际为 '{bind_field}'"
        logger.info(f"标签绑定状态验证通过: '{label_name}' = {expected}")

    def bms_instance_get_labels(self, instance_name: str) -> list:
        """通过"标签设置"对话框获取实例当前绑定的标签名称列表。

        Args:
            instance_name: 实例名称

        Returns:
            list: 当前绑定的标签名称列表
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "标签设置")
        self.page.wait_for_timeout(2000)

        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"标签设置")
        ).last
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到标签设置对话框")

        # 获取右侧已绑定标签
        bound_labels = self.page.evaluate("""() => {
            const dialogs = document.querySelectorAll('.el-dialog, .sugon-dialog');
            let dialog = null;
            for (const d of dialogs) {
                if (d.textContent.includes('标签设置') && d.offsetParent !== null) {
                    dialog = d;
                    break;
                }
            }
            if (!dialog) return [];

            const panels = dialog.querySelectorAll('.el-transfer-panel');
            let rightPanel = null;
            for (const p of panels) {
                const header = p.querySelector('.el-transfer-panel__header');
                if (header && (header.textContent.includes('已选择') || header.textContent.includes('已绑定') || header.textContent.includes('目标'))) {
                    rightPanel = p;
                    break;
                }
            }
            // 如果找不到右侧面板，取第二个面板
            if (!rightPanel && panels.length >= 2) {
                rightPanel = panels[1];
            }
            if (!rightPanel) return [];

            const items = rightPanel.querySelectorAll('.el-transfer-panel__item, .el-checkbox__label');
            return Array.from(items).map(i => i.textContent.trim()).filter(t => t && t.length > 0 && !t.includes('已绑定') && !t.includes('已选择') && !t.includes('目标'));
        }""")

        # 去重并过滤空值
        bound_labels = list(dict.fromkeys(bound_labels))
        logger.info(f"实例 '{instance_name}' 当前绑定标签: {bound_labels}")

        # 关闭对话框
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1000)

        return bound_labels

    def bms_instance_get_security_group(self, instance_name: str) -> str:
        """通过"设置安全组"对话框获取实例当前安全组名称。

        打开实例的"设置安全组"对话框，读取当前已勾选的安全组名称。
        此方法比详情页解析更可靠，因为对话框直接展示绑定关系。

        Args:
            instance_name: 实例名称

        Returns:
            str: 当前安全组名称（若未找到则返回空字符串）
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "设置安全组")

        # 等待对话框出现
        dlg = self.page.locator(".el-dialog, .sugon-dialog, [role='dialog']").filter(
            has_text=re.compile(r"安全组设置")
        ).last
        if dlg.count() == 0 or not dlg.is_visible():
            raise Exception("未找到安全组设置对话框")

        # 等待表格加载
        for _ in range(10):
            self.page.wait_for_timeout(1000)
            all_rows = self.page.evaluate("""() => {
                const dialogs = document.querySelectorAll('.el-dialog, .sugon-dialog');
                let target = null;
                for (const d of dialogs) {
                    if (d.textContent.includes('安全组设置') && d.offsetParent !== null) {
                        target = d;
                        break;
                    }
                }
                if (!target) return [];
                return Array.from(target.querySelectorAll('table tbody tr')).map(r => {
                    const cells = r.querySelectorAll('td');
                    // 第一列通常是 checkbox（无文本），名称一般在第二列
                    let nameText = '';
                    for (let i = 0; i < cells.length; i++) {
                        const txt = cells[i].textContent.trim();
                        if (txt && txt.length > 0) {
                            nameText = txt;
                            break;
                        }
                    }
                    return {
                        name: nameText,
                        fullText: r.textContent.trim(),
                        checked: r.querySelector('.el-checkbox.is-checked') !== null
                    };
                });
            }""")
            if all_rows:
                break

        logger.info(f"安全组对话框内容: {all_rows}")

        # 查找已勾选的安全组名称（使用第一列的纯名称）
        current_sg = ""
        for item in all_rows:
            if item.get("checked"):
                current_sg = item.get("name", "").strip()
                break

        # 关闭对话框（按 Escape）
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1000)

        logger.info(f"实例 '{instance_name}' 当前安全组: '{current_sg}'")
        return current_sg

    # ---- power operations ----

    def bms_instance_shutdown(self, instance_name: str):
        """关闭裸金属实例。

        Args:
            instance_name: 实例名称
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "关机")
        self.page.wait_for_timeout(1500)
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(2000)
        logger.info(f"实例 '{instance_name}' 关机操作已执行")

    def bms_instance_start(self, instance_name: str):
        """启动裸金属实例。

        Args:
            instance_name: 实例名称
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "开机")
        self.page.wait_for_timeout(1500)
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(2000)
        logger.info(f"实例 '{instance_name}' 开机操作已执行")

    def bms_instance_wait_for_status(self, instance_name: str, expected_status: str, timeout: int = 300):
        """轮询等待实例状态变为期望值。

        Args:
            instance_name: 实例名称
            expected_status: 期望状态，如"运行中"、"已关机"
            timeout: 最大等待时间（秒），默认300秒

        Returns:
            bool: 是否成功达到期望状态
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)

        start = time.time()
        while time.time() - start < timeout:
            row_data = self.get_row_data(instance_name)
            if row_data:
                current_status = row_data.get("状态", "")
                if expected_status in current_status:
                    logger.info(f"实例 '{instance_name}' 状态已变为 '{expected_status}'，等待了 {int(time.time() - start)}s")
                    return True
                logger.info(f"实例当前状态 '{current_status}'，继续等待... ({int(time.time() - start)}s/{timeout}s)")
            else:
                logger.warning(f"未找到实例 '{instance_name}' 的行数据")
            time.sleep(10)
            self._goto_submenu_safe("裸金属实例")
            self.bms_search(instance_name)

        logger.warning(f"实例 '{instance_name}' 在 {timeout}s 内未变为 '{expected_status}' 状态")
        return False

    def bms_instance_rebuild(self, instance_name: str, image_name: str = "bms"):
        """重建裸金属实例。

        Args:
            instance_name: 实例名称
            image_name: 镜像名称关键词，用于在镜像列表中匹配选择，默认"bms"
        """
        self._goto_submenu_safe("裸金属实例")
        self.bms_search(instance_name)
        row = self._get_row_by_name(instance_name)
        if not row:
            raise Exception(f"未找到实例 '{instance_name}'")

        self._js_click_action(row, "重建实例")
        self.page.wait_for_timeout(2000)

        # 等待重建对话框出现
        dlg = self.page.locator('[role="dialog"]').filter(has_text="重建实例").last
        dlg.wait_for(state="visible", timeout=10000)
        logger.info("[bms_instance_rebuild] 重建对话框已打开")

        # 等待镜像列表加载
        self.page.wait_for_timeout(1500)
        image_rows = []
        for _ in range(10):
            image_rows = dlg.locator("table tbody tr").all()
            if image_rows and len(image_rows) > 0:
                first_cells = image_rows[0].locator("td").all()
                if len(first_cells) > 1:
                    break
            logger.info("[bms_instance_rebuild] 镜像列表加载中，等待...")
            self.page.wait_for_timeout(1000)

        # 打印所有镜像名称供排查
        for idx, r in enumerate(image_rows):
            txt = r.text_content() or ""
            logger.info(f"[bms_instance_rebuild] 镜像行{idx}: {txt!r}")

        selected = False
        if image_rows:
            # 优先匹配 image_name
            for r in image_rows:
                txt = r.text_content() or ""
                if image_name in txt:
                    if self._click_el_radio(r):
                        selected = True
                        logger.info(f"[bms_instance_rebuild] 镜像选择成功({image_name})")
                        break
            # 若未匹配到，尝试关键词 '裸金属'
            if not selected:
                for r in image_rows:
                    txt = r.text_content() or ""
                    if "裸金属" in txt:
                        if self._click_el_radio(r):
                            selected = True
                            logger.info("[bms_instance_rebuild] 镜像选择成功(裸金属)")
                            break
            # 最终 fallback 选第一个
            if not selected:
                if self._click_el_radio(image_rows[0]):
                    logger.info("[bms_instance_rebuild] 镜像选择成功(第一个)")
                else:
                    logger.warning("[bms_instance_rebuild] 镜像行无radio，尝试JS click")
                    self.page.evaluate("""() => {
                        const dlg = document.querySelector('[role="dialog"]');
                        if (!dlg) return;
                        const radio = dlg.querySelector('table tbody tr input[type=radio]');
                        if (radio) radio.click();
                    }""")
        else:
            # 完全找不到镜像行时尝试JS兜底
            logger.warning("[bms_instance_rebuild] 未找到镜像列表行，尝试JS兜底")
            self.page.evaluate("""() => {
                const dlg = document.querySelector('[role="dialog"]');
                if (!dlg) return;
                const radio = dlg.querySelector('table tbody tr input[type=radio]');
                if (radio) radio.click();
            }""")

        self.page.wait_for_timeout(800)

        # 点击确定按钮
        confirm_btn = dlg.locator("button, .cloud-button-btn, .cloud-button--primary").filter(has_text="确定")
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
        else:
            dlg.get_by_text("确定", exact=True).click()

        logger.info(f"[bms_instance_rebuild] 实例 '{instance_name}' 重建操作已提交")
        self.page.wait_for_timeout(2000)

    # ---- switch group (exchange unit) ----

    def bms_switch_group_unbind(self, group_name: str, node_name: str = ""):
        """解绑交换机组中的物理机。

        Args:
            group_name: 交换机组名称
            node_name: 要解绑的节点名，为空则选择第一个可用节点
        """
        self.goto_service("交换机组")
        self.page.wait_for_timeout(3000)
        row = self._get_switch_group_row(group_name, node_name)
        if not row:
            logger.warning(f"未找到交换机组 '{group_name}'，跳过解绑")
            return
        actual_group_name = self._get_switch_group_name_from_row(row, group_name)
        row_text = row.text_content(timeout=3000) or ""
        if "--" in row_text or "—" in row_text:
            logger.info(f"交换机组 '{actual_group_name}' 已处于未绑定状态，跳过解绑")
            return actual_group_name

        if not self._js_click_action(row, "解绑物理机"):
            raise RuntimeError(f"交换机组 '{actual_group_name}' 的 '解绑物理机' 操作未点击成功")

        # 处理解绑对话框：需要选择要解绑的节点
        d = self.page.locator('[role="dialog"]').filter(has_text="解绑物理机").last
        d.wait_for(state="visible", timeout=10000)
        input_box = d.locator("input:visible").first
        input_box.click(force=True)
        self.page.wait_for_timeout(500)
        opts = self.page.locator(".el-select-dropdown:visible li")
        if opts.count() > 0:
            if node_name:
                matched = opts.filter(has_text=node_name)
                if matched.count() > 0:
                    matched.first.click()
                else:
                    first_text = opts.first.text_content(timeout=3000).strip()
                    logger.info(f"未找到匹配 '{node_name}' 的选项，回退选择第一个: {first_text}")
                    opts.first.click()
            else:
                opts.first.click()
        else:
            logger.warning("解绑对话框无可用节点选项")
        # 多选下拉框点击选项后不会自动关闭，需要按 Escape 关闭后再点确定
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        confirm = d.locator("button:visible, .cloud-button-btn:visible").filter(has_text="确定").first
        confirm.click(force=True)
        self.page.wait_for_timeout(10000)  # 解绑是异步的，等待10秒
        logger.info(f"交换机组 '{actual_group_name}' 解绑物理机操作已提交")
        return actual_group_name

    def bms_switch_group_delete(self, group_name: str):
        """删除交换机组。

        Args:
            group_name: 交换机组名称
        """
        self.goto_service("交换机组")
        self.search(group_name)
        self.page.wait_for_timeout(3000)
        row = self._get_row_by_name(group_name)
        if not row:
            logger.warning(f"未找到交换机组 '{group_name}'，跳过删除")
            return
        self._js_click_action(row, "删除")
        self._confirm_sugon_dialog()
        self._wait_for_row_absence("交换机组", group_name, label="交换机组", navigate_as_service=True)
        logger.info(f"交换机组 '{group_name}' 删除成功")

    # ---- full cleanup ----

    def clean_all_bms_resources(self):
        logger.info("=== 清理BMS资源 ===")
        for fn in [self.bms_instance_cleanup, self.bms_register_cleanup,
                    self.bms_discovery_cleanup, self.bms_agent_cleanup,
                    self.bms_network_cleanup]:
            try:
                fn()
            except Exception as e:
                logger.warning(f"清理出错: {e}")
