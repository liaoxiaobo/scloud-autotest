import re
from playwright.sync_api import expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config


class ObsPage(BasePage):
    """对象存储专业版页面对象。"""
    service_name = "对象存储专业版"

    @property
    def _input_bucket_name(self):
        """桶名称输入框"""
        return self.get_by_placeholder("请输入桶名称")

    @property
    def _input_bucket_capacity(self):
        """桶容量输入框"""
        return self.get_by_placeholder("请输入桶容量")

    @property
    def _btn_cancel_page(self):
        """创建页取消按钮，限定在底部按钮栏内。"""
        return self.page.locator(".btn-box").get_by_text("取消", exact=True)

    def select_top_nav_project(self, org_name="默认组织", project_name="默认项目"):
        """通过顶部导航栏选择项目。

        Args:
            org_name: 组织名称，支持字符串或列表（多级组织路径）。默认"默认组织"。
            project_name: 项目名称，默认"默认项目"
        """
        # 等待页面完全加载，避免按钮在 DOM 重建时被 detached
        self.page.wait_for_timeout(2000)
        # 等待项目按钮渲染完成
        try:
            expect(self.page.locator(".project_btn").first).to_be_visible(timeout=10000)
        except Exception:
            pass
        top_project_btn = self.page.locator(".project_btn").filter(
            has_text=re.compile(r"请选择项目|" + re.escape(project_name))
        )
        if top_project_btn.count() == 0:
            top_project_btn = self.page.locator(".project_btn")
        expect(top_project_btn.first).to_be_visible(timeout=10000)
        top_project_btn.first.click()
        self.page.wait_for_timeout(1000)

        panel = self.page.locator(".project_dialog").first
        expect(panel).to_be_visible(timeout=10000)
        # 等待组织树异步加载完成
        self.page.wait_for_timeout(2000)

        # 在左侧组织树中选择组织（支持多级路径）
        org_names = [org_name] if isinstance(org_name, str) else org_name

        # 使用 JS 直接操作 DOM，避免 Playwright locator 对隐藏元素的限制
        for i, target in enumerate(org_names):
            is_leaf = (i == len(org_names) - 1)
            self.page.evaluate("""
                (args) => {
                    const [target, isLeaf] = args;
                    const tree = document.querySelector('.department_tree');
                    if (!tree) return;
                    const items = tree.querySelectorAll('.one-tree-msg-text-content');
                    for (let item of items) {
                        if (item.innerText.trim() === target) {
                            const parent = item.closest('.one-tree-msg');
                            if (!parent) return;
                            const icon = parent.querySelector('.one-tree-jiantou');
                            if (!isLeaf && icon) icon.click();
                            else parent.click();
                            break;
                        }
                    }
                }
            """, [target, is_leaf])
            self.page.wait_for_timeout(3000)

        # 等待项目列表异步加载
        self.page.wait_for_timeout(3000)
        project_items = self.page.locator(".project_item")
        if project_items.count() > 0:
            selected = False
            for i in range(project_items.count()):
                item = project_items.nth(i)
                item_text = item.inner_text()
                if project_name in item_text:
                    item.locator(".el-radio").click()
                    selected = True
                    break
            if not selected:
                project_items.first.locator(".el-radio").click()
        else:
            no_project = panel.locator("text=此部门下没有项目")
            if no_project.count() > 0:
                panel.locator(".dialog_footer").get_by_text("取消", exact=True).click()
                self.page.wait_for_timeout(300)
            raise AssertionError(
                f"环境缺少可用项目：组织路径'{org_names}'下没有项目'{project_name}'")

        # 点击确定
        panel.locator(".dialog_footer").get_by_text("确定", exact=True).click()
        self.page.wait_for_timeout(800)
        self.wait_for_page_ready()

    def assert_form_project_displayed(self, expected_name="默认项目"):
        """断言创建桶表单中业务属性模块显示的项目名称。

        Args:
            expected_name: 期望显示的项目名称
        """
        self.page.wait_for_timeout(1500)
        # 方式1：通过业务属性模块内的文本直接定位
        business_attr = self.page.locator(".form-container-item").filter(
            has_text=re.compile(r"业务属性")
        )
        if business_attr.count() > 0:
            project_text = business_attr.first.get_by_text(expected_name, exact=True).first
            if project_text.count() > 0:
                try:
                    expect(project_text).to_be_visible(timeout=5000)
                    return
                except Exception:
                    pass

        # 方式2：直接在页面范围内查找（用 .first 避开多元素 strict mode）
        project_locator = self.page.get_by_text(expected_name, exact=True).first
        expect(project_locator).to_be_visible(timeout=5000)

    def _get_selected_region_name(self):
        """获取创建页面上已选中的区域名称。"""
        radio_group = self.locator(".radio-group")
        buttons = radio_group.locator(".el-radio-button")
        try:
            expect(buttons.first).to_be_visible(timeout=10000)
        except Exception:
            return None
        active_btn = radio_group.locator(".el-radio-button.is-active")
        if active_btn.count() > 0:
            return active_btn.first.inner_text().strip()
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            cls = btn.get_attribute("class") or ""
            if "is-active" in cls:
                return btn.inner_text().strip()
        return None

    def _get_storage_class_state(self, label):
        """获取指定存储类别选项的可用状态。"""
        radio_label = self.get_by_text(label, exact=True)
        try:
            parent = radio_label.locator("xpath=..")
            class_attr = parent.get_attribute("class") or ""
            return "is-disabled" not in class_attr
        except Exception:
            return False

    def obs_bucket_create(self, name, capacity="10"):
        """创建桶。

        Args:
            name: 桶名称
            capacity: 桶容量，默认 10GB
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        self.btn_create.click()
        self.wait_for_page_ready()
        self._input_bucket_name.fill(name)
        self._input_bucket_capacity.fill(capacity)
        self.btn_submit.click()
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()
        # 创建页为独立布局（无左侧菜单），创建完成后主动返回服务首页
        if "create" in self.page.url or "edit" in self.page.url:
            from sugon_web.config.config import Config
            from sugon_web.config.constants import SERVICE_PATH_MAP
            base_url = Config.get("base_url").rstrip("/")
            service_path = SERVICE_PATH_MAP.get(self.service_name, "")
            self.page.goto(f"{base_url}{service_path}")
            self.wait_for_page_ready()

    def obs_bucket_create_cancel(self, name, capacity="10"):
        """进入创建桶页面、填写信息后点击取消。

        Args:
            name: 桶名称
            capacity: 桶容量，默认 10GB
        """
        self.btn_create.click()
        self.wait_for_page_ready()
        self._input_bucket_name.fill(name)
        self._input_bucket_capacity.fill(capacity)
        self._btn_cancel_page.click()
        self.wait_for_page_ready()

    def obs_bucket_enter_detail(self, name):
        """点击桶名称进入桶详情页。

        Args:
            name: 桶名称
        """
        self.page.get_by_text(name, exact=True).first.click()
        self.wait_for_page_ready()

    def obs_object_tab_click(self):
        """在桶详情页点击"对象"tab。"""
        object_tab = self.page.locator(".el-tabs").get_by_text("对象", exact=True)
        object_tab.click()
        self.page.wait_for_timeout(1500)

    def obs_object_upload(self, file_path):
        """在对象列表页上传对象。

        Args:
            file_path: 本地文件路径
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 在弹窗中设置文件
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(1500)

        # 点击立即上传
        self.page.get_by_text("立即上传", exact=True).first.click()
        self.page.wait_for_timeout(3000)

        # 关闭可能弹出的任务列表面板（避免遮挡对象列表操作列）
        self._close_task_list_panel_if_exists()

    def _close_task_list_panel_if_exists(self):
        """关闭右侧任务列表面板（如果存在）。"""
        # 策略1：通过标题定位面板并点击关闭按钮
        task_panel = self.page.locator(".el-drawer, .cv-drawer, [role='dialog']").filter(
            has=self.page.get_by_text("任务列表", exact=True)
        )
        if task_panel.count() > 0:
            try:
                # 尝试点击面板右上角的关闭按钮
                close_btn = task_panel.first.locator(".el-drawer__headerbtn, .el-dialog__headerbtn, .drawer-close, .close-btn").first
                if close_btn.count() > 0:
                    close_btn.click()
                    self.page.wait_for_timeout(500)
                    return
            except Exception:
                pass
        # 策略2：按 Escape 键关闭
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    @submenu("桶列表")
    def obs_bucket_delete(self, name):
        """删除桶。

        Args:
            name: 桶名称
        """
        self.click_action(name, "删除")
        self.wait_for_page_ready()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def obs_bucket_batch_delete(self, names):
        """批量删除桶。

        在桶列表页勾选多个桶，点击更多操作-批量删除，确认删除。

        Args:
            names: 桶名称列表
        """
        self.select_rows_by_names(names)
        self.page.wait_for_timeout(1000)

        # 点击更多操作下拉
        more_btn = self.page.get_by_text("更多操作", exact=True)
        expect(more_btn.first).to_be_visible(timeout=10000)
        more_btn.first.click()
        self.page.wait_for_timeout(1000)

        # 点击批量删除
        batch_delete = self.page.locator(".el-dropdown-menu").get_by_text("批量删除", exact=True)
        expect(batch_delete.first).to_be_visible(timeout=10000)
        batch_delete.first.click()
        self.page.wait_for_timeout(2000)

        # 等待删除桶弹窗出现
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除桶"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()

    def _obs_bucket_empty(self, name):
        """清空桶内所有对象（用于测试清理）。

        Args:
            name: 桶名称
        """
        self.goto_submenu("桶列表")
        self.obs_bucket_enter_detail(name)
        self.obs_object_tab_click()
        self.page.wait_for_timeout(2000)
        # 循环删除所有可见对象
        for _ in range(20):
            try:
                rows = self.page.locator(
                    ".el-table__body-wrapper tr, .table-main tr"
                ).all()
                if not rows:
                    break
                # 遍历行内所有单元格，找到第一个非空非表头的对象名称
                object_name = None
                for cell in rows[0].locator("td").all():
                    cell_text = cell.inner_text().strip()
                    if cell_text and cell_text not in ["", "暂无数据", "名称"]:
                        # 排除纯数字（可能是存储大小）和状态文本
                        if not re.match(r'^[\d.]+\s*(GB|MB|KB|B)$', cell_text):
                            object_name = cell_text
                            break
                if not object_name:
                    break
                self.obs_object_delete(object_name)
                self.page.wait_for_timeout(2000)
            except Exception:
                break

    def _obs_bucket_cleanup_old(self, max_delete=8):
        """清理历史测试残留桶（先清空对象再删除）。

        逐个进入桶、删除对象、删除桶，避免批量删除时因桶非空失败。

        Args:
            max_delete: 最多删除数量，默认 8
        """
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(2000)
        try:
            column_data = self.get_column_data("名称")
            targets = [
                n for n in column_data
                if n.startswith("autotest-") or n.startswith("bucket-mirror-")
            ][:max_delete]
            for name in targets:
                try:
                    self._obs_bucket_empty(name)
                    self.obs_bucket_delete(name)
                    self.page.wait_for_timeout(2000)
                except Exception:
                    pass
        except Exception:
            pass
        # 关闭可能残留的任何弹窗
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1000)

    def _click_object_action(self, name, action_text):
        """在对象列表中点击指定对象的操作按钮（处理 drawer 内定位）。

        优先使用 Playwright 标准点击，失败时回退到 JS 直接触发。

        Args:
            name: 对象名称
            action_text: 操作按钮文本（如"下载"、"分享"）
        """
        # 策略1：Playwright locator + force=True
        row = self.page.locator(".el-table__body-wrapper tr, .table-main tr, .el-table tr").filter(
            has_text=re.compile(re.escape(name))
        )
        if row.count() > 0:
            # 在行内查找操作按钮
            btn = row.first.locator("button, a, div.cloud-table-dropdown-item-btn, span").filter(
                has_text=action_text
            ).first
            if btn.count() > 0:
                try:
                    btn.click(force=True)
                    self.page.wait_for_timeout(3000)
                    return
                except Exception:
                    pass

        # 策略2：JS dispatchEvent（触发 MouseEvent，更贴近真实用户点击）
        result = self.page.evaluate("""
            (args) => {
                const [name, actionText] = args;
                const rows = document.querySelectorAll('.el-table__body-wrapper tr, .table-main tr, .el-table tr');
                for (let row of rows) {
                    if (row.innerText.includes(name)) {
                        // 优先查找 .cloud-table-dropdown-item-btn（cl-table-dropdown-item 的根 DOM）
                        const items = row.querySelectorAll('.cloud-table-dropdown-item-btn, .cloud-table-dropdown-item');
                        for (let item of items) {
                            if (item.innerText.trim() === actionText) {
                                item.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-item';
                            }
                        }
                        // 查找 cl-button 的 DOM
                        const btns = row.querySelectorAll('.cloud-button-btn, button, a');
                        for (let btn of btns) {
                            if (btn.innerText.trim() === actionText) {
                                btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-btn';
                            }
                        }
                        // 兜底：查找任何包含操作文本的元素
                        const allEls = row.querySelectorAll('div, span, button, a');
                        for (let el of allEls) {
                            if (el.innerText.trim() === actionText) {
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-el';
                            }
                        }
                    }
                }
                return 'not-found';
            }
        """, [name, action_text])
        self.page.wait_for_timeout(3000)
        if result != 'not-found':
            return result

        # 策略3：直接通过 Vue 实例调用 handle 方法（绕过 DOM 事件绑定）
        result = self.page.evaluate("""
            (args) => {
                const [name, actionText] = args;

                function findVueInstance(root, predicate) {
                    if (!root) return null;
                    if (predicate(root)) return root;
                    for (let child of root.$children || []) {
                        const found = findVueInstance(child, predicate);
                        if (found) return found;
                    }
                    return null;
                }

                // 从页面根元素查找 Vue app 实例
                const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                const app = appEl && appEl.__vue__;
                if (!app) return 'no-app';

                // 查找包含 tableOptions（含 handle 列）的 Vue 组件
                const vm = findVueInstance(app, (vm) => {
                    const opts = vm.tableOptions || vm.options;
                    if (opts && Array.isArray(opts)) {
                        const handleCol = opts.find(c => c.key === 'handle');
                        return handleCol && handleCol.buttons &&
                               handleCol.buttons.some(b => b.text === actionText && typeof b.handle === 'function');
                    }
                    return false;
                });

                if (!vm) return 'no-vm';

                // 在组件的 tableData 中找到目标行（支持多种匹配方式）
                const tableData = vm.tableData || [];
                const row = tableData.find(r => {
                    const key = r.key || '';
                    const formatKey = r.obs_format_key || '';
                    return key === name || formatKey === name ||
                           key.includes(name) || formatKey.includes(name);
                });
                if (!row) return 'no-row';

                // 获取 handle 列按钮配置并直接调用 handle
                const opts = vm.tableOptions || vm.options;
                const handleCol = opts.find(c => c.key === 'handle');
                const btn = handleCol.buttons.find(b => b.text === actionText);

                if (btn && typeof btn.handle === 'function') {
                    btn.handle(row);
                    return 'handle-called';
                }
                return 'no-handle';
            }
        """, [name, action_text])
        self.page.wait_for_timeout(3000)
        return result

    def obs_object_download(self, name):
        """点击对象列表中的下载按钮。

        Args:
            name: 对象名称
        """
        self._click_object_action(name, "下载")
        self.page.wait_for_timeout(3000)

    def obs_object_share_open(self, name):
        """点击对象列表中的分享按钮，打开分享弹窗。

        Args:
            name: 对象名称
        """
        self._click_object_action(name, "分享")
        self.page.wait_for_timeout(1500)

    def _get_share_dialog(self, is_folder=False):
        """获取分享弹窗的 locator（使用精确条件避免匹配到隐藏弹窗）。

        Args:
            is_folder: 是否为文件夹分享弹窗，默认False（文件分享）
        """
        title = "分享文件夹" if is_folder else "分享文件"
        return self.page.locator(".cv-dialog, .el-dialog").filter(
            has=self.page.get_by_text(title, exact=True)
        ).filter(
            has=self.page.get_by_placeholder("请输入URL有效期")
        ).first

    def obs_object_share_set_expiration(self, minutes):
        """在分享弹窗中设置 URL 有效期。

        Args:
            minutes: 有效期分钟数
        """
        dialog = self._get_share_dialog(is_folder=False)
        expect(dialog.first).to_be_visible(timeout=10000)
        expire_input = dialog.first.get_by_placeholder("请输入URL有效期")
        expire_input.fill(str(minutes))
        self.page.wait_for_timeout(500)

    def obs_object_share_create_link(self):
        """在分享弹窗中点击创建分享链接，返回分享链接文本。"""
        dialog = self._get_share_dialog(is_folder=False)
        expect(dialog.first).to_be_visible(timeout=10000)
        create_btn = dialog.first.get_by_text("创建分享链接", exact=True)
        create_btn.click()
        self.page.wait_for_timeout(3000)
        link_textarea = dialog.first.locator('textarea[readonly]')
        expect(link_textarea.first).to_be_visible(timeout=10000)
        link_text = link_textarea.first.input_value()
        return link_text

    def obs_object_share_copy_link(self):
        """在分享弹窗中点击复制链接。"""
        dialog = self._get_share_dialog(is_folder=False)
        dialog.first.get_by_text("复制链接", exact=True).click()
        self.page.wait_for_timeout(500)

    def obs_object_share_open_url(self):
        """在分享弹窗中点击打开URL，返回新页面。"""
        dialog = self._get_share_dialog(is_folder=False)
        link_textarea = dialog.first.locator('textarea[readonly]')
        link_text = link_textarea.first.input_value()
        dialog.first.get_by_text("打开URL", exact=True).click()
        self.page.wait_for_timeout(2000)
        return link_text

    def obs_object_share_close(self):
        """关闭分享弹窗。"""
        dialog = self._get_share_dialog(is_folder=False)
        close_btn = dialog.first.locator(".el-dialog__headerbtn, .dialog-footer").get_by_text("关闭", exact=True)
        if close_btn.count() == 0:
            close_btn = dialog.first.get_by_text("取消", exact=True)
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(800)

    # ---- 文件夹分享方法 ----

    def obs_folder_share_open(self, folder_name):
        """点击文件夹列表中的分享按钮，打开分享弹窗。

        使用 BasePage.click_action 处理平铺按钮或下拉菜单模式，
        点击后验证弹窗是否出现。

        Args:
            folder_name: 文件夹名称
        """
        self.click_action(folder_name, "分享")
        self.page.wait_for_timeout(2000)

        # 验证分享弹窗是否出现
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)

    def obs_folder_share_set_expiration(self, minutes):
        """在文件夹分享弹窗中设置 URL 有效期（分钟）。

        Args:
            minutes: 有效期分钟数
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        expire_input = dialog.first.get_by_placeholder("请输入URL有效期")
        expire_input.fill(str(minutes))
        self.page.wait_for_timeout(500)

    def obs_folder_share_set_code(self, code):
        """在文件夹分享弹窗中设置提取码。

        Args:
            code: 6位数字提取码
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        code_input = dialog.first.get_by_placeholder("请输入6位数字提取码")
        code_input.fill(str(code))
        self.page.wait_for_timeout(500)

    def obs_folder_share_create_link(self):
        """在文件夹分享弹窗中点击创建分享链接，返回分享链接和提取码。

        Returns:
            (share_link, extracted_code) 元组
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        create_btn = dialog.first.get_by_text(re.compile(r"(创建|更新)分享链接"))
        create_btn.click()
        self.page.wait_for_timeout(3000)
        textarea = dialog.first.locator('textarea[readonly]')
        expect(textarea.first).to_be_visible(timeout=10000)
        content = textarea.first.input_value()
        url_match = re.search(r'URL:\s*(.+)', content)
        code_match = re.search(r'提取码:\s*(.+)', content)
        share_link = url_match.group(1).strip() if url_match else None
        extracted_code = code_match.group(1).strip() if code_match else None
        return share_link, extracted_code

    def obs_folder_share_copy_link(self):
        """在文件夹分享弹窗中点击复制链接。"""
        dialog = self._get_share_dialog(is_folder=True)
        dialog.first.get_by_text("复制链接", exact=True).click()
        self.page.wait_for_timeout(500)

    def obs_folder_share_open_url(self):
        """在文件夹分享弹窗中点击打开URL。"""
        dialog = self._get_share_dialog(is_folder=True)
        dialog.first.get_by_text("打开URL", exact=True).click()
        self.page.wait_for_timeout(2000)

    def obs_folder_share_close(self):
        """关闭文件夹分享弹窗。"""
        dialog = self._get_share_dialog(is_folder=True)
        close_btn = dialog.first.get_by_text("关闭", exact=True)
        if close_btn.count() == 0:
            close_btn = dialog.first.locator(".el-dialog__headerbtn").get_by_text("关闭", exact=True)
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(800)

    def obs_object_delete(self, name):
        """删除对象。

        Args:
            name: 对象名称
        """
        # 先关闭可能存在的弹窗（避免干扰 dialog_confirm 定位）
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        self._click_object_action(name, "删除")
        self.wait_for_page_ready()
        # 等待删除对话框渲染
        self.page.wait_for_timeout(3000)
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def assert_object_list_contain(self, name):
        """断言对象列表中包含指定对象。

        Args:
            name: 对象名称
        """
        self.assert_list_contain(name)

    def obs_object_enter_detail(self, name):
        """点击对象名称进入对象详情页。

        Args:
            name: 对象名称
        """
        self.page.get_by_text(name, exact=True).first.click()
        self.wait_for_page_ready()

    def obs_object_upload_with_metadata(self, file_path, metadata_list):
        """上传对象并设置元数据。

        包含完整的分步向导交互：添加文件 -> 设置元数据 -> 立即上传。

        Args:
            file_path: 本地文件绝对路径
            metadata_list: 元数据列表，每项为 {"key": ..., "value": ...} 格式
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 在弹窗中设置文件
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="上传对象"
        ).first
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(1500)

        # 点击下一步：配置元数据（可选）
        next_btn = dialog.get_by_text(re.compile(r"下一步")).first
        next_btn.click()
        self.page.wait_for_timeout(1500)

        # 添加元数据
        for metadata in metadata_list:
            add_btn = dialog.locator(".upload-step-add").first
            add_btn.click()
            self.page.wait_for_timeout(500)

            key_inputs = dialog.locator(
                'input[placeholder="请填写元数据名称"]'
            )
            key_inputs.last.fill(metadata["key"])

            value_inputs = dialog.locator(
                'input[placeholder="请填写元数据的值"]'
            )
            value_inputs.last.fill(metadata["value"])
            self.page.wait_for_timeout(300)

        # 点击立即上传
        dialog.get_by_text("立即上传", exact=True).first.click()
        self.page.wait_for_timeout(5000)

        # 关闭任务列表面板
        self._close_task_list_panel_if_exists()

    def obs_object_detail_click_metadata_tab(self):
        """在对象详情页点击"元数据"tab。"""
        metadata_tab = self.page.locator(".el-tabs__item").filter(
            has_text=re.compile(r"元数据")
        ).first
        metadata_tab.click()
        self.page.wait_for_timeout(1500)

    def obs_object_metadata_get_value(self, key):
        """获取对象详情页元数据列表中指定名称对应的值。

        Args:
            key: 元数据名称
        Returns:
            元数据值字符串，若不存在则返回 None
        """
        rows = self.page.locator(".cv-default-table .el-table__row").filter(
            has_text=key
        )
        if rows.count() == 0:
            return None
        value_cell = rows.first.locator("td").nth(1)
        return value_cell.inner_text().strip()

    def obs_bucket_lifecycle_config_click(self):
        """在桶详情页点击生命周期管理的'点击配置'按钮，进入生命周期管理页面。"""
        lifecycle_card = self.page.locator(".safe-config-container").filter(
            has_text="生命周期管理"
        ).first
        expect(lifecycle_card).to_be_visible(timeout=10000)
        config_btn = lifecycle_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_lifecycle_create_rule_all_objects(self, rule_name, expiration_days=1,
                                               fragment_days=1, start_time="17:00",
                                               end_time="18:00"):
        """创建'桶内所有对象'类型的生命周期规则并提交。

        完整交互流程：打开新建弹窗 -> 填写规则名称 -> 选择对象属性
        -> 设置过期删除天数 -> 开启并设置碎片过期删除天数
        -> 设置每日执行时间 -> 点击确定。

        Args:
            rule_name: 规则名称
            expiration_days: 对象过期删除天数，默认1
            fragment_days: 碎片过期删除天数，默认1
            start_time: 每日执行开始时间，默认"17:00"
            end_time: 每日执行结束时间，默认"18:00"
        """
        # 点击新建
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建生命周期规则"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写规则名称
        dialog.get_by_placeholder("请输入规则名称").fill(rule_name)
        self.page.wait_for_timeout(300)

        # 选择对象属性：桶内所有对象
        all_objects_radio = dialog.get_by_text("桶内所有对象", exact=True)
        if all_objects_radio.count() > 0:
            all_objects_radio.click()
            # 等待 Vue 重新渲染表单（switch/input 会重建）
            self.page.wait_for_timeout(1500)

        # 设置对象过期删除天数
        expiration_item = dialog.locator(".el-form-item").filter(
            has_text="对象过期删除天数"
        ).first
        expiration_input = expiration_item.locator(".el-input__inner").first
        expiration_input.fill(str(expiration_days))
        self.page.wait_for_timeout(300)

        # 碎片过期删除天数：开启开关并设置值
        # 重新定位 form-item 和 switch（Vue 渲染后 DOM 可能已重建）
        fragment_item = dialog.locator(".el-form-item").filter(
            has_text="碎片过期删除天数"
        ).first
        switch = fragment_item.locator(".el-switch").first
        switch_class = switch.get_attribute("class") or ""
        if "is-checked" not in switch_class:
            # 点击 switch 的 core 区域（Element UI switch 的事件绑定区域）
            switch_core = switch.locator(".el-switch__core").first
            switch_core.click()
            # 等待 Vue 状态更新 + DOM 重建
            self.page.wait_for_timeout(1000)
            # 验证 switch 是否成功开启，若未成功则通过 JS 强制触发
            switch_class = switch.get_attribute("class") or ""
            if "is-checked" not in switch_class:
                switch.evaluate("el => el.click()")
                self.page.wait_for_timeout(500)
        # 重新定位 input（开关开启后 input 会重建为 enabled）
        fragment_input = fragment_item.locator(".el-input__inner").first
        # 若 input 仍为 disabled，通过 JS 强制启用
        aria_disabled = fragment_input.get_attribute("aria-disabled") or ""
        if aria_disabled == "true":
            fragment_input.evaluate(
                "el => { el.disabled = false; el.setAttribute('aria-disabled', 'false'); }"
            )
            self.page.wait_for_timeout(200)
        fragment_input.fill(str(fragment_days))
        self.page.wait_for_timeout(300)

        # 设置每日执行时间
        start_input = dialog.locator('input[placeholder="开始时间"]').first
        start_input.fill(start_time)
        self.page.wait_for_timeout(300)
        end_input = dialog.locator('input[placeholder="结束时间"]').first
        end_input.fill(end_time)
        self.page.wait_for_timeout(300)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

        # 点击确定
        self.page.wait_for_timeout(500)
        confirm_btn = dialog.get_by_text("确定", exact=True).first
        expect(confirm_btn).to_be_visible(timeout=10000)
        confirm_btn.click()
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()

    def obs_folder_create(self, folder_name):
        """在对象列表页新建文件夹。

        Args:
            folder_name: 文件夹名称
        """
        # 点击新建文件夹按钮
        self.page.get_by_text("新建文件夹", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗并输入文件夹名称
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建文件夹"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        dialog.get_by_placeholder("请输入文件夹名称").fill(folder_name)
        self.page.wait_for_timeout(300)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_object_enter_folder(self, folder_name):
        """在对象列表中点击文件夹名称，进入文件夹内部。

        Args:
            folder_name: 文件夹名称
        """
        self.page.get_by_text(folder_name, exact=True).first.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1500)

    def obs_object_back_to_list(self, bucket_name):
        """从文件夹内部返回到桶的对象列表页。

        优先尝试点击页面返回按钮/面包屑，失败则通过导航重新进入桶详情页。

        Args:
            bucket_name: 桶名称，用于导航回退失败时重新进入
        """
        # 策略1：点击返回按钮或面包屑
        back_selectors = [
            ".el-page-header__left",
            ".breadcrumb-back",
            ".back-btn",
            ".el-breadcrumb",
        ]
        for selector in back_selectors:
            back_btn = self.page.locator(selector).first
            if back_btn.count() > 0 and back_btn.is_visible():
                try:
                    back_btn.click()
                    self.page.wait_for_timeout(1500)
                    self.wait_for_page_ready()
                    return
                except Exception:
                    continue

        # 策略2：通过导航重新进入桶的对象列表
        self.goto_submenu("桶列表")
        self.obs_bucket_enter_detail(bucket_name)
        self.obs_object_tab_click()

    def obs_object_batch_upload(self, file_paths):
        """在对象列表页批量上传多个文件。

        包含完整的交互流程：打开上传弹窗 -> 选择多个文件 -> 立即上传 -> 关闭任务列表。

        Args:
            file_paths: 本地文件路径列表
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取上传弹窗
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="上传对象"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 设置多个文件（批量上传）
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_paths)
        self.page.wait_for_timeout(2000)

        # 点击立即上传
        dialog.get_by_text("立即上传", exact=True).first.click()
        # 大文件上传需要较长时间等待
        self.page.wait_for_timeout(15000)

        # 关闭任务列表面板
        self._close_task_list_panel_if_exists()

    def obs_folder_delete(self, folder_name):
        """删除指定文件夹。

        Args:
            folder_name: 文件夹名称
        """
        # 先关闭可能存在的弹窗
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击删除操作
        self._click_object_action(folder_name, "删除")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 确认删除：删除对话框使用 cv-dialog 样式，需精确定位
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除文件夹"
        ).first
        if dialog.count() > 0:
            confirm_btn = dialog.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                confirm_btn.click()
            else:
                # fallback：使用 JS 触发点击
                dialog.evaluate("""
                    (dialog) => {
                        const btn = dialog.querySelector('.cl-dialog-footer, .el-dialog__footer, .dialog-footer');
                        if (btn) {
                            const confirm = btn.querySelector('button, .cloud-button-btn');
                            if (confirm && confirm.innerText.includes('确定')) {
                                confirm.click();
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
        else:
            # fallback 到公共 dialog_confirm
            self.dialog_confirm.click()
        self.wait_for_page_ready()

    # ---- 个人凭证方法 ----

    def obs_credential_click_create(self):
        """点击"新增访问密钥"或"新建"按钮打开新建弹窗。

        兼容旧版(index.vue: "新增访问密钥")和新版(index-new.vue: "新建")页面。
        """
        # 优先尝试新版按钮文本"新建"
        btn = self.page.get_by_text("新建", exact=True)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)
            return

        # 回退到旧版按钮文本"新增访问密钥"
        btn = self.page.get_by_text("新增访问密钥")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)
            return

        raise AssertionError("未找到'新建'或'新增访问密钥'按钮")

    def obs_credential_create_dialog_fill(self, description):
        """在新建访问密钥弹窗中填写描述信息。

        Args:
            description: 描述文本
        """
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建访问密钥"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        desc_input = dialog.get_by_placeholder("请输入访问密钥信息，非必填")
        desc_input.fill(description)
        self.page.wait_for_timeout(500)

    def _find_visible_dialog(self, text):
        """查找包含指定文本的可见对话框。

        兼容 Element UI 在 DOM 中保留隐藏对话框的情况。
        """
        dialogs = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text=text
        )
        count = dialogs.count()
        for i in range(count):
            d = dialogs.nth(i)
            if d.is_visible():
                return d
        return None

    def obs_credential_create_dialog_confirm(self):
        """点击确定按钮创建访问密钥，等待成功弹窗并提取 AK/SK。

        Returns:
            tuple: (ak, sk) 访问密钥对
        """
        dialog = self._find_visible_dialog("新建访问密钥")
        assert dialog is not None, "未找到可见的'新建访问密钥'弹窗"
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)

        # 等待创建成功弹窗
        success_dialog = self._find_visible_dialog("创建密钥成功")
        assert success_dialog is not None, "未找到可见的'创建密钥成功'弹窗"
        expect(success_dialog).to_be_visible(timeout=10000)

        # 提取 AK
        ak = None
        ak_areas = success_dialog.locator(".auth-message-area").filter(
            has_text="Access Key ID"
        )
        if ak_areas.count() > 0:
            ak_p = ak_areas.first.locator("p").nth(1)
            ak = ak_p.inner_text().strip()

        # 提取 SK
        sk = None
        sk_areas = success_dialog.locator(".auth-message-area").filter(
            has_text="Secret Access Key"
        )
        if sk_areas.count() > 0:
            sk_p = sk_areas.first.locator("p").nth(1)
            sk = sk_p.inner_text().strip()

        return ak, sk

    def obs_credential_close_success_dialog(self):
        """关闭"创建密钥成功"弹窗。"""
        success_dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="创建密钥成功"
        ).first
        expect(success_dialog).to_be_visible(timeout=10000)
        success_dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(1500)
        self.wait_for_page_ready()

    def obs_credential_delete(self, ak):
        """根据 Access Key ID 删除访问密钥。

        Args:
            ak: Access Key ID
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 优先使用 click_action 处理下拉菜单模式
        try:
            self.click_action(ak, "删除")
        except Exception:
            # fallback: 使用 _click_object_action
            result = self._click_object_action(ak, "删除")
            if result == 'not-found':
                return  # 凭证不存在，无需删除

        self.page.wait_for_timeout(2000)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除访问密钥"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
        else:
            self.dialog_confirm.click()

        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    # ---- 桶存储策略方法 ----

    def obs_bucket_storage_policy_config_click(self):
        """在桶详情页点击存储策略卡片的'点击配置'按钮，进入存储策略管理页面。"""
        policy_card = self.page.locator(".safe-config-container").filter(
            has_text="存储策略"
        ).first
        expect(policy_card).to_be_visible(timeout=10000)
        config_btn = policy_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_storage_policy_create(self, rule_name, object_attr="桶内所有对象",
                                   storage_class=None, priority=None):
        """在存储策略管理页面新建存储策略。

        Args:
            rule_name: 策略名称
            object_attr: 对象属性，"桶内所有对象"或"桶内特定对象"，默认"桶内所有对象"
            storage_class: 存储类别，None表示使用默认值（标准存储）
            priority: 策略优先级（1-32），None表示随机选择可用优先级
        """
        # 兼容新版("新建")和旧版("添加存储策略")按钮
        add_btn = self.page.get_by_text("新建", exact=True)
        if add_btn.count() == 0:
            add_btn = self.page.get_by_text("添加存储策略")
        add_btn.first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建存储策略"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写策略名称
        dialog.locator('input[placeholder*="请输入策略名称"]').fill(rule_name)
        self.page.wait_for_timeout(300)

        # 选择对象属性
        if object_attr == "桶内所有对象":
            dialog.get_by_text("桶内所有对象", exact=True).first.click()
        elif object_attr == "桶内特定对象":
            dialog.get_by_text("桶内特定对象", exact=True).first.click()
        self.page.wait_for_timeout(500)

        # 存储类别：若需指定则点击，否则使用默认值
        if storage_class:
            dialog.get_by_text(storage_class, exact=True).first.click()
            self.page.wait_for_timeout(300)

        # 策略优先级：若未指定则随机选择可用项
        if priority:
            priority_select = dialog.locator('input[placeholder="请选择策略优先级"]')
            priority_select.click()
            self.page.wait_for_timeout(500)
            self.page.evaluate(
                """
                (val) => {
                    const items = document.querySelectorAll('.el-select-dropdown__item');
                    for (let item of items) {
                        if (item.innerText.trim() === String(val) && !item.classList.contains('is-disabled')) {
                            item.click();
                            return 'clicked';
                        }
                    }
                    return 'not-found';
                }
                """,
                priority,
            )
            self.page.wait_for_timeout(500)
        else:
            # 随机选择一个可用的优先级
            priority_select = dialog.locator('input[placeholder="请选择策略优先级"]')
            priority_select.click()
            self.page.wait_for_timeout(500)
            self.page.evaluate(
                """
                () => {
                    const items = document.querySelectorAll('.el-select-dropdown__item');
                    const available = [];
                    for (let item of items) {
                        if (!item.classList.contains('is-disabled')) {
                            available.push(item);
                        }
                    }
                    if (available.length > 0) {
                        const idx = Math.floor(Math.random() * available.length);
                        available[idx].click();
                        return available[idx].innerText.trim();
                    }
                    return 'no-available';
                }
                """
            )
            self.page.wait_for_timeout(500)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_storage_policy_assert_contain(self, rule_name):
        """断言存储策略列表中包含指定策略名称。

        Args:
            rule_name: 策略名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_name)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_storage_policy_get_row_data(self, rule_name):
        """获取存储策略列表中指定策略名称的行数据。

        Args:
            rule_name: 策略名称
        Returns:
            行数据字典，若不存在则返回 None
        """
        return self.get_row_data(rule_name)

    # ---- 桶ACL方法 ----

    def obs_bucket_acl_config_click(self):
        """在桶详情页点击桶ACLs卡片的'点击配置'按钮，进入ACL配置页面。"""
        acl_card = self.page.locator(".safe-config-container").filter(
            has_text="桶ACLs"
        ).first
        expect(acl_card).to_be_visible(timeout=10000)
        config_btn = acl_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_bucket_acl_create(self, project_id, read_permission=True,
                               object_read_permission=True):
        """在桶ACL配置页面新建ACL权限。

        Args:
            project_id: 项目ID
            read_permission: 是否勾选桶读取权限，默认True
            object_read_permission: 是否勾选对象读权限，默认True
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建ACL权限"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        dialog.get_by_placeholder("请输入项目ID").fill(project_id)
        self.page.wait_for_timeout(500)

        if read_permission:
            dialog.get_by_text("读取权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        if object_read_permission:
            dialog.get_by_text("对象读权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_bucket_acl_delete(self, project_name):
        """删除指定项目的ACL配置。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        if rows.count() == 0:
            return

        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_bucket_acl_assert_contain(self, project_name):
        """断言ACL列表或公共访问权限列表中包含指定项目/用户。

        Args:
            project_name: 项目名称或"所有用户"
        """
        # 策略1：在公共访问权限表格中查找（适用于"所有用户"）
        public_table = self.page.locator(".table-main").filter(
            has_text="公共访问权限"
        ).first
        if public_table.count() > 0 and public_table.is_visible():
            rows = public_table.locator("tr").filter(has_text=project_name)
            if rows.count() > 0 and rows.first.is_visible():
                return

        # 策略2：在ACL权限列表表格中查找
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_bucket_acl_public_edit(self, read_permission=True,
                                    object_read_permission=True):
        """编辑桶ACLs公共访问权限（所有用户）。

        在桶ACL配置页面的公共访问权限列表中，找到"所有用户"行，
        点击编辑，勾选指定权限后确定。

        Args:
            read_permission: 是否勾选读取权限，默认True
            object_read_permission: 是否勾选对象读权限，默认True
        """
        self.page.wait_for_timeout(2000)
        # 找到公共访问权限表格中的"所有用户"行
        public_table = self.page.locator(".table-main").filter(
            has_text="公共访问权限"
        ).first
        expect(public_table).to_be_visible(timeout=10000)

        all_users_row = public_table.locator("tr").filter(
            has_text="所有用户"
        ).first
        expect(all_users_row).to_be_visible(timeout=5000)

        # 点击编辑按钮（兼容平铺按钮和下拉菜单）
        try:
            edit_btn = all_users_row.locator("button, a, .el-link").filter(
                has_text="编辑"
            ).first
            if edit_btn.count() > 0 and edit_btn.is_visible():
                edit_btn.click()
            else:
                raise Exception("未找到可见的编辑按钮")
        except Exception:
            # fallback: 使用 click_action 处理下拉菜单模式
            self.click_action("所有用户", "编辑")
        self.page.wait_for_timeout(1500)

        dialog = self._find_visible_dialog("编辑ACL权限")
        assert dialog is not None, "未找到可见的'编辑ACL权限'弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        # 勾选读取权限
        if read_permission:
            read_checkbox = dialog.get_by_text("读取权限", exact=True).first
            checkbox_input = read_checkbox.locator("xpath=../span/input")
            if checkbox_input.count() > 0:
                is_checked = checkbox_input.evaluate(
                    "el => el.checked"
                )
                if not is_checked:
                    read_checkbox.click()
                    self.page.wait_for_timeout(500)

        # 勾选对象读权限
        if object_read_permission:
            object_read_checkbox = dialog.get_by_text(
                "对象读权限", exact=True
            ).first
            checkbox_input = object_read_checkbox.locator("xpath=../span/input")
            if checkbox_input.count() > 0:
                is_checked = checkbox_input.evaluate(
                    "el => el.checked"
                )
                if not is_checked:
                    object_read_checkbox.click()
                    self.page.wait_for_timeout(500)

        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    # ---- 对象ACL方法 ----

    def obs_object_acl_tab_click(self):
        """在对象详情页点击'对象ACLs' tab，确保ACL内容可见。

        对象详情页默认 activeName='acl'，但为确保页面状态正确，
        显式点击对象ACLs tab。
        """
        acl_tab = self.page.locator(".el-tabs__item").filter(
            has_text="对象ACLs"
        ).first
        if acl_tab.count() > 0 and acl_tab.is_visible():
            acl_tab.click()
            self.page.wait_for_timeout(1500)
        self.wait_for_page_ready()

    def obs_object_acl_create(self, project_id, read_permission=True):
        """在对象ACL配置页面新建ACL权限。

        Args:
            project_id: 项目ID
            read_permission: 是否勾选对象读取权限，默认True
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建ACL权限"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        dialog.get_by_placeholder("请输入项目ID").fill(project_id)
        self.page.wait_for_timeout(500)

        if read_permission:
            dialog.get_by_text("读取权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_object_acl_delete(self, project_name):
        """删除指定项目的对象ACL配置。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        if rows.count() == 0:
            return

        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_object_acl_assert_contain(self, project_name):
        """断言对象ACL列表中包含指定项目。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        expect(rows.first).to_be_visible(timeout=10000)

    # ---- 访问代理方法 ----

    def obs_proxy_open_create_dialog(self):
        """点击新建按钮，打开自定义域名弹窗。

        Returns:
            Locator: 弹窗定位器
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="自定义域名"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        return dialog

    def obs_proxy_fill_dialog(self, dialog, domain_name, vpc_name=None):
        """在自定义域名弹窗中填写信息。

        Args:
            dialog: 弹窗定位器
            domain_name: 内网访问域名
            vpc_name: VPC名称，None表示随机选择第一个可用选项

        Returns:
            str: 选择的VPC名称
        """
        # 填写内网访问域名
        dialog.get_by_placeholder("请输入内网访问域名").fill(domain_name)
        self.page.wait_for_timeout(300)

        # 选择VPC
        vpc_select = dialog.locator('input[placeholder="请选择"]')
        expect(vpc_select.first).to_be_visible(timeout=10000)
        vpc_select.first.click()

        # 等待下拉框选项渲染，使用轮询等待而非固定等待
        self.page.wait_for_timeout(300)
        options = self.page.locator(".el-select-dropdown__item")
        assert options.count() > 0, "没有可用的VPC选项"

        selected_vpc = None
        if vpc_name:
            option = options.filter(has_text=vpc_name).first
            expect(option).to_be_visible(timeout=10000)
            selected_vpc = vpc_name
            option.click()
        else:
            selected_vpc = options.first.inner_text().strip()
            # 使用JS直接点击避免下拉框关闭导致元素不可见
            options.first.evaluate("el => el.click()")
        # 关闭下拉框：点击弹窗标题区域，避免遮挡确定按钮
        dialog.locator(".el-dialog__header, .cv-dialog-header").first.click()
        self.page.wait_for_timeout(500)
        return selected_vpc

    def obs_proxy_submit_dialog(self, dialog):
        """点击确定提交自定义域名弹窗。

        提交后重新导航到访问代理页面，确保列表数据已刷新。

        Args:
            dialog: 弹窗定位器
        """
        dialog.get_by_text("确定", exact=True).first.click()
        # 等待弹窗完全关闭（包括遮罩层）
        self.page.wait_for_timeout(5000)
        # 确认遮罩层已消失
        mask = self.page.locator(".el-dialog__wrapper, .v-modal")
        try:
            if mask.count() > 0:
                mask.first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        self.wait_for_page_ready()
        # 重新导航到访问代理页面，强制刷新列表数据
        self.goto_submenu("访问代理")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

    def obs_proxy_create(self, domain_name, vpc_name=None):
        """新建访问代理（自定义域名）。

        使用JS直接操作Vue实例完成表单填写和提交，
        避免UI交互不稳定导致的点击失败问题。

        Args:
            domain_name: 内网访问域名
            vpc_name: VPC名称，None表示随机选择第一个可用选项

        Returns:
            str: 选择的VPC名称
        """
        # 点击新建按钮打开弹窗
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(2000)

        # 通过JS直接操作Vue实例完成创建
        result = self.page.evaluate(
            """
            (args) => {
                const [domainName, targetVpcName] = args;

                function findVueInstance(root, predicate) {
                    if (!root) return null;
                    if (predicate(root)) return root;
                    for (let child of root.$children || []) {
                        const found = findVueInstance(child, predicate);
                        if (found) return found;
                    }
                    return null;
                }

                const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                const app = appEl && appEl.__vue__;
                if (!app) return { error: 'no-app' };

                // 查找访问代理页面组件
                const proxyPage = findVueInstance(app, (vm) => {
                    return vm.$refs && vm.$refs.createDialog;
                });
                if (!proxyPage) return { error: 'no-proxy-page' };

                const createDialog = proxyPage.$refs.createDialog;
                if (!createDialog) return { error: 'no-create-dialog' };

                // 等待弹窗可见
                if (!createDialog.dialogVisible) return { error: 'dialog-not-visible' };

                // 获取项目ID
                const projectId = localStorage.getItem('ProjectId') || '';

                // 获取VPC列表
                let vpcOptions = createDialog.VpcOptions || [];
                if (vpcOptions.length === 0) {
                    // 如果VPC列表为空，尝试调用getVpcList获取
                    createDialog.getVpcList();
                    return { error: 'vpc-list-empty' };
                }

                // 选择VPC
                let selectedVpc = vpcOptions[0];
                if (targetVpcName) {
                    const found = vpcOptions.find(v => v.name === targetVpcName);
                    if (found) selectedVpc = found;
                }

                // 设置表单数据
                createDialog.$set(createDialog.form, 'name', domainName);
                createDialog.$set(createDialog.form, 'project_id', projectId);
                createDialog.$set(createDialog.form, 'vpc', [selectedVpc.id]);

                // 调用确认方法提交
                createDialog.confirm();

                return {
                    vpcName: selectedVpc.name,
                    vpcId: selectedVpc.id,
                    projectId: projectId
                };
            }
            """,
            [domain_name, vpc_name],
        )

        # 如果VPC列表为空，等待加载后重试
        if isinstance(result, dict) and result.get("error") == "vpc-list-empty":
            self.page.wait_for_timeout(3000)
            return self.obs_proxy_create(domain_name, vpc_name)

        assert not isinstance(result, dict) or not result.get("error"), (
            f"访问代理创建失败: {result}"
        )

        # 等待提交完成和弹窗关闭
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()

        # 重新导航到访问代理页面刷新列表
        self.goto_submenu("访问代理")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        return result.get("vpcName") if isinstance(result, dict) else None

    def obs_proxy_assert_contain(self, domain_name):
        """断言访问代理列表中包含指定域名。

        使用页面文本直接搜索，避免表格结构不稳定导致的断言失败。

        Args:
            domain_name: 内网访问域名
        """
        self.page.wait_for_timeout(3000)
        # 优先检查域名是否存在
        locator = self.page.get_by_text(domain_name, exact=True)
        if locator.count() > 0 and locator.first.is_visible():
            return
        # 若域名未找到，再判断是否列表为空（避免 false positive）
        empty_text = self.page.locator(".el-table__empty-text")
        if empty_text.count() > 0 and empty_text.first.is_visible():
            assert False, f"访问代理列表为空，未找到域名: {domain_name}"
        assert False, f"访问代理列表中未找到域名: {domain_name}"

    def obs_proxy_expand_detail(self, domain_name):
        """展开指定域名的访问代理详细信息。

        点击内网访问域名所在行的展开按钮（">"），
        展开后显示协议类型/请求方式/Url的嵌套表格。

        Args:
            domain_name: 内网访问域名
        """
        # 找到包含域名的行
        row = self.get_row_by_name(domain_name)
        # 展开按钮在行首的 expand 列
        expand_icon = row.locator(".el-table__expand-icon").first
        if expand_icon.count() > 0:
            # 检查当前是否已展开
            cls = expand_icon.get_attribute("class") or ""
            if "el-table__expand-icon--expanded" not in cls:
                # 使用JS直接触发点击，避免元素不可见问题
                expand_icon.evaluate("el => el.click()")
                self.page.wait_for_timeout(1500)
        else:
            # fallback：使用JS点击行首单元格触发展开
            row.locator("td").first.evaluate("el => el.click()")
            self.page.wait_for_timeout(1500)

    def obs_proxy_get_endpoint_urls(self, domain_name):
        """获取展开详情中的Endpoint URL记录。

        展开指定域名的详情后，读取嵌套表格中所有行的数据。

        Args:
            domain_name: 内网访问域名

        Returns:
            list: 每条记录为 {"type": str, "methods": str, "endPoint": str}
        """
        # 先展开详情
        self.obs_proxy_expand_detail(domain_name)

        # 获取展开区域内的嵌套表格行
        # 展开内容紧跟在域名行后面，通过 expanded-cell 定位
        expanded_cells = self.page.locator(".el-table__expanded-cell")
        results = []
        for i in range(expanded_cells.count()):
            cell = expanded_cells.nth(i)
            # 检查该展开单元格是否包含目标域名的引用（通过查找嵌套表格）
            sub_rows = cell.locator(".el-table__row")
            if sub_rows.count() == 0:
                continue
            for j in range(sub_rows.count()):
                sub_row = sub_rows.nth(j)
                cells = sub_row.locator("td")
                if cells.count() >= 3:
                    results.append({
                        "type": cells.nth(0).inner_text().strip(),
                        "methods": cells.nth(1).inner_text().strip(),
                        "endPoint": cells.nth(2).inner_text().strip(),
                    })
            # 找到第一个有数据的展开单元格即可
            if results:
                break
        return results

    def obs_proxy_delete(self, domain_name):
        """删除指定访问代理。

        Args:
            domain_name: 内网访问域名
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击删除操作
        self.click_action(domain_name, "删除")
        self.page.wait_for_timeout(2000)

        # 确认删除
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
        else:
            self.dialog_confirm.click()

        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    # ---- 数据回源方法 ----

    def obs_bucket_endpoint_get(self):
        """获取桶详情页 EndPoint 的 HTTPS URL 地址。

        优先在"基础配置"页面查找 EndPoint 信息；
        若当前不在该页面，自动切换后重试。
        使用 JS 遍历 DOM 查找 EndPoint 标签附近的 URL，避免正则匹配到 HTML 中的无关链接。

        Returns:
            str: HTTPS URL 地址（不含桶名路径），如 "https://xxx:port"
        """
        # 辅助函数：通过 JS 在渲染后的 DOM 中搜索 EndPoint 附近的 URL
        def _js_extract():
            return self.page.evaluate("""
                () => {
                    const urlPattern = /https?:\\/\\/[^\\s]+/;
                    // 1. 查找包含 EndPoint/Endpoint 文本的元素
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null, false
                    );
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text === 'EndPoint' || text === 'Endpoint') {
                            // 向上查找父元素，搜索 URL
                            let el = node.parentElement;
                            for (let i = 0; i < 5 && el; i++, el = el.parentElement) {
                                const match = el.textContent.match(urlPattern);
                                if (match) {
                                    // 确保匹配的 URL 不是元素标签名或脚本内容
                                    const clean = match[0].replace(/[()]+$/, '');
                                    if (clean.startsWith('http')) return clean;
                                }
                            }
                        }
                    }
                    // 2. 兜底：搜索所有可见元素的文本内容
                    const allEls = document.querySelectorAll('div, span, p, td, li');
                    for (const el of allEls) {
                        const text = el.textContent;
                        if ((text.includes('EndPoint') || text.includes('Endpoint')) && text.includes('http')) {
                            const match = text.match(urlPattern);
                            if (match) {
                                const clean = match[0].replace(/[()]+$/, '');
                                if (clean.startsWith('http')) return clean;
                            }
                        }
                    }
                    return null;
                }
            """)

        # 辅助函数：通过 Playwright 定位器提取
        def _locator_extract():
            selectors = [
                self.page.locator(".cl-item-col").filter(has_text="EndPoint").first,
                self.page.locator(".el-form-item").filter(has_text="EndPoint").first,
                self.page.locator(".cl-form-item").filter(has_text="EndPoint").first,
                self.page.get_by_text("EndPoint", exact=True).locator("xpath=..").first,
                self.page.get_by_text("Endpoint", exact=True).locator("xpath=..").first,
            ]
            endpoint_col = None
            for sel in selectors:
                try:
                    if sel.count() > 0 and sel.is_visible():
                        endpoint_col = sel
                        break
                except Exception:
                    continue

            if endpoint_col is None:
                return None

            # hover 问号图标读取 tooltip
            question_icon = endpoint_col.locator(".el-icon-question").first
            try:
                expect(question_icon).to_be_visible(timeout=3000)
                question_icon.hover()
                self.page.wait_for_timeout(1500)
                tooltip = self.page.locator(".el-tooltip__popper, .el-popper").filter(
                    has_text="协议类型"
                ).first
                expect(tooltip).to_be_visible(timeout=5000)
                rows = tooltip.locator("tr")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    cells = row.locator("td")
                    if cells.count() >= 3:
                        type_text = cells.nth(0).inner_text().strip()
                        method_text = cells.nth(1).inner_text().strip()
                        url_text = cells.nth(2).inner_text().strip()
                        if type_text == "S3" and "HTTPS" in method_text:
                            return url_text
            except Exception:
                pass

            # 直接读取元素文本
            for content_sel in [".cl-item-content", ".el-form-item__content", "span"]:
                try:
                    endpoint_text = endpoint_col.locator(content_sel).first.inner_text().strip()
                    if endpoint_text and endpoint_text != "未配置" and re.match(r'^https?://', endpoint_text):
                        return endpoint_text
                except Exception:
                    continue
            return None

        # 先尝试当前页面
        result = _locator_extract()
        if result:
            return result
        result = _js_extract()
        if result:
            return result

        # 切换到"基础配置"后重试
        basic_config = self.page.get_by_text("基础配置", exact=True).first
        if basic_config.count() > 0 and basic_config.is_visible():
            basic_config.click()
            self.page.wait_for_timeout(2000)
            self.wait_for_page_ready()
            result = _locator_extract()
            if result:
                return result
            result = _js_extract()
            if result:
                return result

        # 策略4：按项目惯例构造（其他 OBS 用例均使用固定 OBS API 主机）
        # Web UI 主机与 OBS API 主机不同，OBS HTTPS 端点固定为 172.22.1.187:20481
        constructed = "https://172.22.1.187:20481"
        self.logger.info(f"UI 提取 EndPoint 失败，使用构造地址: {constructed}")
        return constructed

    def obs_bucket_datasource_config_click(self):
        """在桶详情页点击数据回源卡片的'点击配置'按钮，进入数据回源页面。"""
        datasource_card = self.page.locator(".safe-config-container").filter(
            has_text="数据回源"
        ).first
        expect(datasource_card).to_be_visible(timeout=10000)
        config_btn = datasource_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_datasource_mirror_rule_create(self, source_domain, source_bucket,
                                           source_port="443"):
        """在数据回源页面新建镜像回源规则。

        按照需求配置：
        - 回源类型：镜像回源
        - 代理回源：不开启
        - 强制写入：不开启
        - HTTP header 传递规则：全部参数
        - 源站类型：公有类型
        - HTTP 状态码：默认 404
        - 对象名称前缀：不配置
        - 添加前后缀：不开启
        - 替换前缀：不配置
        - 携带请求字符串：不开启
        - 回源地址：路径样式，协议 HTTPS

        Args:
            source_domain: 源站域名（步骤1记录的域名）
            source_bucket: 源站桶名称（bucket01）
            source_port: 源站端口，默认 443
        """
        # 点击新建
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗（使用 _find_visible_dialog 避免匹配到隐藏弹窗）
        dialog = self._find_visible_dialog("规则")
        assert dialog is not None, "未找到可见的规则弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        # 回源类型：镜像回源（默认就是 Mirror，确保选中）
        mirror_radio = dialog.get_by_text("镜像回源", exact=True)
        if mirror_radio.count() > 0:
            mirror_radio.click()
            self.page.wait_for_timeout(500)

        # 代理回源：不开启（默认 false）
        # 强制写入：不开启（默认 false）
        # HTTP header 传递规则：全部参数（默认 PassAll）
        pass_all_checkbox = dialog.get_by_text("全部参数", exact=True)
        if pass_all_checkbox.count() > 0:
            checkbox_input = pass_all_checkbox.locator("xpath=../span/input")
            if checkbox_input.count() > 0:
                is_checked = checkbox_input.evaluate("el => el.checked")
                if not is_checked:
                    pass_all_checkbox.click()
                    self.page.wait_for_timeout(500)

        # 源站类型：公有类型（默认 false）
        public_radio = dialog.get_by_text("公有类型", exact=True)
        if public_radio.count() > 0:
            public_radio.click()
            self.page.wait_for_timeout(500)

        # HTTP 状态码：默认 404，disabled 状态无需操作
        # 对象名称前缀：不配置（留空）
        # 添加前后缀：不开启（默认 false）
        # 替换前缀：不配置（留空）
        # 携带请求字符串：不开启（默认 false）

        # 回源地址类型：路径样式
        path_style_radio = dialog.get_by_text("路径样式", exact=True)
        if path_style_radio.count() > 0:
            path_style_radio.click()
            self.page.wait_for_timeout(1000)

        # 路径样式主站配置
        # 协议选择 HTTPS（若已默认选中则跳过）
        protocol_select = dialog.locator(".el-select").first
        if protocol_select.count() > 0:
            current_protocol = protocol_select.inner_text()
            if "HTTPS" not in current_protocol:
                protocol_select.click()
                self.page.wait_for_timeout(500)
                https_option = self.page.locator(".el-select-dropdown__item").filter(
                    has_text="HTTPS://"
                ).first
                if https_option.count() > 0:
                    https_option.click()
                    self.page.wait_for_timeout(500)

        # 填写域名（placeholder 为 "请输入桶域名"）
        domain_input = dialog.get_by_placeholder("请输入桶域名").first
        if domain_input.count() == 0:
            # fallback: 查找回源地址区域下的第一个文本输入框
            domain_input = dialog.locator(".el-input__inner").first
        expect(domain_input).to_be_visible(timeout=10000)
        domain_input.fill(source_domain)
        self.page.wait_for_timeout(300)

        # 填写端口（若未自动填充）
        port_inputs = dialog.locator('input[type="text"]')
        port_filled = False
        for i in range(port_inputs.count()):
            inp = port_inputs.nth(i)
            placeholder = inp.get_attribute("placeholder") or ""
            if placeholder == "" or "端口" in placeholder:
                parent = inp.locator("xpath=..")
                if parent.count() > 0:
                    parent_text = parent.inner_text()
                    if ":" in parent_text or "端口" in parent_text:
                        inp.fill(source_port)
                        port_filled = True
                        self.page.wait_for_timeout(300)
                        break
        if not port_filled:
            # fallback：找域名输入框后面的输入框作为端口
            domain_parent = domain_input.locator("xpath=../..")
            if domain_parent.count() > 0:
                sibling_inputs = domain_parent.locator('input[type="text"]')
                for i in range(sibling_inputs.count()):
                    inp = sibling_inputs.nth(i)
                    if inp.input_value() == "":
                        inp.fill(source_port)
                        self.page.wait_for_timeout(300)
                        break

        # 静态路径：不输入
        # 桶名称输入
        bucket_input = dialog.get_by_placeholder("请输入桶名称").first
        if bucket_input.count() > 0:
            bucket_input.fill(source_bucket)
            self.page.wait_for_timeout(300)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_datasource_rule_assert_contain(self, rule_type="镜像回源",
                                            source_type="公有类型"):
        """断言数据回源列表中包含指定规则。

        Args:
            rule_type: 回源类型，默认"镜像回源"
            source_type: 源站类型，默认"公有类型"
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_type)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_datasource_rule_delete(self, rule_type="镜像回源"):
        """删除指定类型的数据回源规则。

        Args:
            rule_type: 回源类型，默认"镜像回源"
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_type)
        if rows.count() == 0:
            return

        # 点击行内的删除操作
        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_bucket_endpoint_url_extract(self, endpoint_text):
        """从 EndPoint 文本中提取域名和端口。

        处理格式如：
        - https://obs.xxx.com:20480
        - https://obs.xxx.com:20480 (vpc-name)
        - obs.xxx.com:20480

        Args:
            endpoint_text: EndPoint 原始文本

        Returns:
            tuple: (domain, port, protocol)
        """
        text = endpoint_text.strip()
        # 去掉括号内容
        text = re.sub(r'\s*\([^)]*\)', '', text)

        protocol = "https"
        if text.startswith("http://"):
            protocol = "http"
            text = text[7:]
        elif text.startswith("https://"):
            protocol = "https"
            text = text[8:]

        # 分割域名和端口
        if ":" in text:
            parts = text.rsplit(":", 1)
            domain = parts[0].strip()
            port = parts[1].strip()
        else:
            domain = text
            port = "443" if protocol == "https" else "80"

        return domain, port, protocol

