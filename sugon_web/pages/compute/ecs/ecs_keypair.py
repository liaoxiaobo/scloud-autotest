import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class EcsKeypairMixin(BasePage):
    """密钥对页面操作。"""

    @submenu("密钥对")
    def goto_keypair_submenu(self):
        """导航到密钥对子菜单。"""
        self.goto_service("弹性云服务器")
        logger.info("已进入密钥对子菜单")

    def keypair_create(self, name: str) -> str:
        """创建密钥对并返回下载的 pem 文件路径。

        通过拦截创建密钥对的 API 响应提取 private_key 内容并保存为 pem 文件，
        避免依赖浏览器下载配置（context 可能未开启 accept_downloads）。

        Args:
            name: 密钥对名称。

        Returns:
            str: 保存的 pem 文件完整路径。
        """
        # 点击新建按钮
        self.btn_create.click()

        # 等待弹窗出现
        dialog = self.get_by_role("dialog", name="新建密钥对")
        expect(dialog).to_be_visible(timeout=5000)

        # 填写密钥对名称
        dialog.get_by_role("textbox").fill(name)

        # 点击确定（cl-button 自定义组件可能无 role="button"，优先用 .cloud-button-btn）
        submit_btn = dialog.locator(".cloud-button-btn, button").filter(has_text="确定").first
        if submit_btn.count() == 0 or not submit_btn.is_visible():
            submit_btn = dialog.get_by_role("button", name="确定")

        # 注入 JS Hook 捕获 exportRaw 的 private_key 内容
        self.page.evaluate("""
            () => {
                window.__capturedPemContent = null;
                const orig = window.URL || window.webkitURL || window;
                if (orig.createObjectURL) {
                    const _origCreateObjectURL = orig.createObjectURL;
                    orig.createObjectURL = function(blob) {
                        const reader = new FileReader();
                        reader.onloadend = function() {
                            window.__capturedPemContent = reader.result;
                        };
                        reader.readAsText(blob);
                        return _origCreateObjectURL.call(orig, blob);
                    };
                }
            }
        """)

        submit_btn.click()

        # 等待弹窗关闭
        expect(dialog).not_to_be_visible(timeout=10000)

        # 从 JS Hook 提取 private_key
        private_key = self.page.evaluate("() => window.__capturedPemContent")
        if not private_key:
            # 短暂等待 Blob 读取完成
            self.page.wait_for_timeout(500)
            private_key = self.page.evaluate("() => window.__capturedPemContent")

        # 保存 pem 文件到指定目录
        pem_path = self._save_keypair_pem(name, private_key)
        logger.info(f"密钥对创建成功: {name}, pem文件: {pem_path}")
        return pem_path

    def _save_keypair_pem(self, name: str, private_key: str | None) -> str:
        """将私钥内容保存为 pem 文件。

        Args:
            name: 密钥对名称（不含 .pem 后缀）。
            private_key: 私钥内容；若为 None 则抛出异常。

        Returns:
            str: 保存后的 pem 文件绝对路径。
        """
        if not private_key:
            raise ValueError(f"密钥对 {name} 创建响应中未包含 private_key，无法保存 pem 文件")

        # 确定下载目录：screenshots 同级目录下的 pkeytemp
        screenshots_dir = Path(os.environ.get("SCREENSHOTS_DIR", "screenshots"))
        if not screenshots_dir.is_absolute():
            project_root = Path(__file__).resolve().parents[4]
            screenshots_dir = project_root / "screenshots"
        download_dir = screenshots_dir.parent / "pkeytemp"
        download_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{name}.pem"
        pem_path = download_dir / filename

        pem_path.write_text(private_key, encoding="utf-8")
        logger.info(f"密钥对文件已保存: {pem_path}")
        return str(pem_path)

    def _dismiss_ui_overlays(self):
        """关闭可能干扰操作的悬浮层（下拉菜单、tooltip、drawer 等）。"""
        self.page.keyboard.press("Escape")
        self.page.mouse.move(1, 1)
        self.page.evaluate("""
            () => {
                document.querySelectorAll('.el-dropdown-menu, .el-popper, .el-tooltip__popper')
                    .forEach(el => { if(el.parentNode) el.parentNode.removeChild(el); });
            }
        """)
        self.page.wait_for_timeout(300)

    def _get_delete_dialog(self):
        """获取删除确认弹窗（兼容 sugon-delete-dialog 自定义组件）。"""
        self._dismiss_ui_overlays()
        # sugon-delete-dialog 是自定义组件，无 role="dialog"，用可见性 + 文本过滤
        # 先尝试 .el-dialog 类（若组件内部渲染为 el-dialog 结构）
        dialog = self.page.locator(".el-dialog:visible").filter(has_text=re.compile(r"删除密钥对"))
        if dialog.count() > 0 and dialog.first.is_visible():
            return dialog.first
        # 回退：任何可见的包含"删除密钥对"和"确定"按钮的容器
        fallback = self.page.locator("body").locator(".el-dialog__wrapper:visible, .el-message-box__wrapper:visible, .el-dialog:visible").filter(has_text="删除密钥对")
        if fallback.count() > 0:
            return fallback.first
        # 再回退：直接找包含"删除密钥对"文本的可见元素
        text_fallback = self.page.locator("*:visible").filter(has_text="删除密钥对").first
        return text_fallback

    def _click_dialog_button(self, button_text: str) -> bool:
        """通过 JS 在删除对话框中查找并点击指定按钮（兼容 sugon-delete-dialog 自定义组件）。"""
        return self.page.evaluate(f"""
            () => {{
                // 策略1: 在 .el-dialog 中查找
                const dialogs = document.querySelectorAll('.el-dialog');
                for (const d of dialogs) {{
                    if (d.textContent.includes('删除')) {{
                        const btns = d.querySelectorAll('button, .cloud-button-btn, .el-button');
                        for (const btn of btns) {{
                            const txt = btn.textContent.trim();
                            if ((txt === '{button_text}' || txt.includes('{button_text}')) && !btn.disabled) {{
                                btn.click();
                                return true;
                            }}
                        }}
                    }}
                }}
                // 策略2: 在 sugon-delete-dialog 或任何可见对话框中查找
                const allDialogs = document.querySelectorAll('.el-dialog__wrapper, .el-message-box__wrapper, [class*="dialog"]');
                for (const d of allDialogs) {{
                    if (d.textContent.includes('删除')) {{
                        const btns = d.querySelectorAll('button, .cloud-button-btn, .el-button');
                        for (const btn of btns) {{
                            const txt = btn.textContent.trim();
                            if ((txt === '{button_text}' || txt.includes('{button_text}')) && !btn.disabled) {{
                                btn.click();
                                return true;
                            }}
                        }}
                    }}
                }}
                // 策略3: 全局查找包含"删除"的可见容器
                const wrappers = document.querySelectorAll('.el-dialog, .el-message-box, .cv-dialog, [class*="delete"]');
                for (const w of wrappers) {{
                    const style = window.getComputedStyle(w);
                    if (style.display !== 'none' && style.visibility !== 'hidden') {{
                        if (w.textContent.includes('删除')) {{
                            const btns = w.querySelectorAll('button, .cloud-button-btn, .el-button');
                            for (const btn of btns) {{
                                const txt = btn.textContent.trim();
                                if ((txt === '{button_text}' || txt.includes('{button_text}')) && !btn.disabled) {{
                                    btn.click();
                                    return true;
                                }}
                            }}
                        }}
                    }}
                }}
                // 策略4: 最宽松——找页面上任何包含"删除"文本的可见元素
                const allElements = document.body.querySelectorAll('*');
                for (const el of allElements) {{
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    if (el.children.length === 0) continue;
                    if (el.textContent.includes('删除')) {{
                        const btns = el.querySelectorAll('button, .cloud-button-btn, .el-button, [class*="btn"]');
                        for (const btn of btns) {{
                            const txt = btn.textContent.trim();
                            if ((txt === '{button_text}' || txt.includes('{button_text}')) && !btn.disabled) {{
                                btn.click();
                                return true;
                            }}
                        }}
                    }}
                }}
                return false;
            }}
        """)

    def _click_row_delete_button(self, name: str):
        """点击密钥对列表行中的删除图标按钮。

        密钥对页面的删除按钮是 icon-only 的 cl-button（无可见文本），
        click_action 的 get_by_text 无法匹配，需直接定位行内的删除图标。

        Args:
            name: 密钥对名称。
        """
        row = self.get_row_by_name(name)
        # 在行内查找删除按钮：优先找 title="删除" 或包含 el-icon-delete 类的元素
        delete_btn = row.locator("[title='删除'], .el-icon-delete, .el-icon-delete-solid").first
        if delete_btn.count() > 0 and delete_btn.is_visible():
            delete_btn.click()
            logger.info(f"点击密钥对行删除按钮: {name}")
            return
        # 回退2：通过 JS 在行内查找包含删除图标的按钮并点击
        clicked = self.page.evaluate(f"""
            () => {{
                const rows = document.querySelectorAll('table tr');
                for (const row of rows) {{
                    if (row.textContent.includes('{name}')) {{
                        const btns = row.querySelectorAll('button, .cloud-button-btn, .el-button, [class*="button"]');
                        for (const btn of btns) {{
                            if (btn.title === '删除' || btn.innerHTML.includes('el-icon-delete') || btn.textContent.includes('删除')) {{
                                btn.click();
                                return true;
                            }}
                        }}
                        // 如果没找到特定删除按钮，点击操作列最后一个按钮
                        if (btns.length > 0) {{
                            btns[btns.length - 1].click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }}
        """)
        if clicked:
            logger.info(f"点击密钥对行删除按钮(JS): {name}")
            return
        raise Exception(f"未找到密钥对 {name} 的删除按钮")

    def keypair_delete(self, name: str, confirm: bool = True):
        """删除单个密钥对。

        Args:
            name: 要删除的密钥对名称。
            confirm: 是否确认删除，False 则点击取消。
        """
        # 点击操作列的删除按钮（密钥对页面是 icon-only 按钮，需特殊处理）
        self._click_row_delete_button(name)

        # 等待删除确认弹窗出现（给 sugon-delete-dialog 渲染时间，异步组件需较长等待）
        self.page.wait_for_timeout(2000)

        if confirm:
            clicked = self._click_dialog_button("确定")
            if clicked:
                logger.info(f"密钥对删除已确认: {name}")
            else:
                logger.warning(f"密钥对删除确认对话框未找到或按钮点击失败: {name}")
                raise Exception(f"无法确认删除密钥对 {name}：删除对话框未出现或确定按钮不可点击")
        else:
            clicked = self._click_dialog_button("取消")
            if clicked:
                logger.info(f"密钥对删除已取消: {name}")
            else:
                logger.warning(f"密钥对删除取消对话框未找到或按钮点击失败: {name}")
                # 取消失败不一定是错误，尝试按 Escape 关闭对话框
                self.page.keyboard.press("Escape")

    def keypair_batch_delete(self, names: list[str], confirm: bool = True):
        """批量删除密钥对。

        Args:
            names: 要删除的密钥对名称列表。
            confirm: 是否确认删除，False 则点击取消。
        """
        # 勾选指定行
        self.select_rows_by_names(names)

        # 点击批量删除按钮
        self.btn_batch_delete.click()

        # 等待删除确认弹窗出现（给 sugon-delete-dialog 渲染时间）
        self.page.wait_for_timeout(800)

        if confirm:
            clicked = self._click_dialog_button("确定")
            if clicked:
                logger.info(f"批量删除密钥对已确认: {names}")
            else:
                # 回退：尝试通过 Playwright locator 点击
                delete_dialog = self._get_delete_dialog()
                confirm_btn = delete_dialog.locator(".cloud-button-btn, button").filter(has_text="确定").first
                if confirm_btn.count() == 0 or not confirm_btn.is_visible():
                    confirm_btn = delete_dialog.get_by_role("button", name="确定")
                confirm_btn.click()
                logger.info(f"批量删除密钥对已确认(回退): {names}")
        else:
            clicked = self._click_dialog_button("取消")
            if clicked:
                logger.info(f"批量删除密钥对已取消: {names}")
            else:
                # 回退：尝试通过 Playwright locator 点击
                delete_dialog = self._get_delete_dialog()
                cancel_btn = delete_dialog.locator(".cloud-button-btn, button").filter(has_text="取消").first
                if cancel_btn.count() == 0 or not cancel_btn.is_visible():
                    cancel_btn = delete_dialog.get_by_role("button", name="取消")
                cancel_btn.click()
                logger.info(f"批量删除密钥对已取消(回退): {names}")

    def keypair_get_detail(self, name: str) -> dict:
        """进入密钥对详情页获取信息。

        Args:
            name: 密钥对名称。

        Returns:
            dict: 包含名称、ID、指纹、创建时间、公钥等字段的字典。
        """
        self._dismiss_ui_overlays()

        # 点击名称链接进入详情
        self.get_by_role("cell", name=name).locator("a").click()

        # 等待 drawer 出现（el-drawer 用 .el-drawer__wrapper，按标题"详细信息"过滤）
        drawer = self.page.locator(".el-drawer__wrapper:visible").filter(has_text="详细信息")
        expect(drawer).to_be_visible(timeout=5000)

        # 等待详情数据加载完成（抽屉打开后异步请求数据，需等待非占位符内容）
        self.page.wait_for_timeout(1500)

        # 读取详情字段——通过 JS 提取 drawer 内所有文本内容
        # 由于 sugon-option 是 Vue 自定义组件，实际渲染结构可能变化，采用多策略提取
        detail = self.page.evaluate("""
            () => {
                const result = {};
                // 策略1: 找所有可见的 el-drawer，提取 sugon-option 或 .sugon-option 内容
                const drawers = document.querySelectorAll('.el-drawer__wrapper, .el-drawer');
                for (const drawer of drawers) {
                    const style = window.getComputedStyle(drawer);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    // 尝试 sugon-option 标签
                    const options = drawer.querySelectorAll('sugon-option, .sugon-option');
                    for (const opt of options) {
                        const label = opt.getAttribute('label') || '';
                        const value = opt.getAttribute('value') || '';
                        if (label.includes('名称')) result.name = value;
                        if (label.includes('ID')) result.id = value;
                        if (label.includes('指纹')) result.fingerprint = value;
                        if (label.includes('创建时间')) {
                            const span = opt.querySelector('span');
                            result.created_at = span ? span.textContent.trim() : value;
                        }
                        if (label.includes('公钥')) {
                            const p = opt.querySelector('p');
                            result.public_key = p ? p.textContent.trim() : value;
                        }
                    }
                    // 如果上面没找到，尝试从 label/value DOM 结构提取
                    if (!result.name || result.name === '--') {
                        const allOptions = drawer.querySelectorAll('.sugon-option, [class*="option"]');
                        for (const opt of allOptions) {
                            const labelEl = opt.querySelector('.label, [class*="label"]');
                            const valueEl = opt.querySelector('.value, [class*="value"]');
                            const label = labelEl ? labelEl.textContent.trim() : '';
                            const value = valueEl ? valueEl.textContent.trim() : '';
                            if (label.includes('名称')) result.name = value;
                            if (label.includes('ID')) result.id = value;
                            if (label.includes('指纹')) result.fingerprint = value;
                            if (label.includes('创建时间')) result.created_at = value;
                            if (label.includes('公钥')) result.public_key = value;
                        }
                    }
                    // 如果还是没找到，暴力提取所有文本节点按行解析
                    if (!result.name || result.name === '--') {
                        const text = drawer.innerText || drawer.textContent;
                        const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                        for (let i = 0; i < lines.length - 1; i++) {
                            if (lines[i].includes('名称')) result.name = lines[i+1];
                            if (lines[i].includes('ID')) result.id = lines[i+1];
                            if (lines[i].includes('指纹')) result.fingerprint = lines[i+1];
                            if (lines[i].includes('创建时间')) result.created_at = lines[i+1];
                            if (lines[i].includes('公钥')) result.public_key = lines[i+1];
                        }
                    }
                }
                // 转换为中文键名以匹配测试层断言
                return {
                    '名称': result.name,
                    'ID': result.id,
                    '指纹': result.fingerprint,
                    '创建时间': result.created_at,
                    '公钥': result.public_key
                };
            }
        """)

        # 关闭 drawer
        close_btn = drawer.locator(".el-drawer__close-btn, .el-drawer__headerbtn").first
        if close_btn.count() > 0 and close_btn.is_visible():
            close_btn.click()
        else:
            self.page.keyboard.press("Escape")
        expect(drawer).not_to_be_visible(timeout=5000)

        logger.info(f"获取密钥对详情: {detail}")
        return detail

    def keypair_search(self, name: str):
        """在密钥对列表页定位指定名称。

        密钥对页面无搜索框，直接通过 get_row_by_name 定位行并滚动到视图。

        Args:
            name: 要搜索的密钥对名称。
        """
        row = self.get_row_by_name(name)
        row.scroll_into_view_if_needed()
        logger.info(f"密钥对页面无搜索框，已定位到行: {name}")
