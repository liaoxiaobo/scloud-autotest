import re

from sugon_web.common.base import submenu
from sugon_web.common.playwright import expect


class CceConfigMixin:
    """配置管理：配置项(ConfigMap) + 密钥(Secret)。"""

    # ------------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------------
    def _goto_configmap_tab(self):
        """切换到"配置项"Tab。"""
        tab = self.page.locator(".el-tabs__item").filter(has_text="配置项").first
        tab.click()
        self.wait_for_page_ready()

    def _goto_secret_tab(self):
        """切换到"密钥"Tab。"""
        tab = self.page.locator(".el-tabs__item").filter(has_text="密钥").first
        tab.click()
        self.wait_for_page_ready()

    def _fill_config_dialog(self, dialog, name, labels=None, datas=None):
        """在创建/编辑弹窗中填写名称、标签、数据公共逻辑。

        Args:
            dialog: 弹窗 Locator
            name: 名称
            labels: 标签字典
            datas: 数据字典
        """
        dialog.locator(".el-form-item").filter(has_text="名称").locator("input").first.fill(name)

        if labels:
            label_form = dialog.locator(".el-form-item").filter(has_text="标签")
            for key, value in labels.items():
                label_form.get_by_text("添加标签").click()
                self.page.wait_for_timeout(300)
                table = label_form.locator(".el-table")
                last_row = table.locator(".el-table__row").last
                inputs = last_row.locator("input")
                inputs.nth(0).fill(key)
                inputs.nth(1).fill(value)

        if datas:
            data_form = dialog.locator(".el-form-item").filter(has_text="数据")
            table = data_form.locator(".el-table")
            rows = table.locator(".el-table__row")
            for i, (data_name, data_content) in enumerate(datas.items()):
                if i < rows.count():
                    row = rows.nth(i)
                else:
                    data_form.get_by_text("添加数据").click()
                    self.page.wait_for_timeout(300)
                    row = table.locator(".el-table__row").last
                row.locator("input").first.fill(data_name)
                row.locator("textarea").first.fill(data_content)

    def _open_data_dialog_and_fill(self, title, data_name, content, submit_text="确定"):
        """打开添加/编辑数据弹窗并填写内容（兼容 sugon-code / CodeMirror 编辑器）。

        Args:
            title: 弹窗标题（用于定位）
            data_name: 数据名称（编辑时可能已禁用）
            content: 数据内容
            submit_text: 提交按钮文案，默认"确定"；配置项编辑弹窗为"保存"
        """
        dialog = self.page.locator(".el-dialog").filter(has_text=title)
        dialog.wait_for(state="visible", timeout=10000)

        name_input = dialog.locator(".el-form-item").filter(has_text="名称").locator("input").first
        if not name_input.is_disabled():
            name_input.fill(data_name)
            # element-ui 表单验证在 blur 时触发，fill 后需显式 blur 以完成验证
            name_input.blur()
            self.page.wait_for_timeout(300)

        # sugon-code 组件内部是 CodeMirror 6（.cm-content contenteditable），
        # 直接修改 innerText 无法同步其内部状态，需通过真实键盘事件输入。
        cm_content = dialog.locator(".cm-content").first
        if cm_content.count() > 0:
            cm_content.click()
            self.page.keyboard.press("Control+a")
            self.page.keyboard.type(content)
        else:
            # 兜底：尝试标准 textarea
            dialog.locator("textarea").first.fill(content)

        submit_btn = dialog.get_by_text(submit_text, exact=True)
        # 如果表单验证未收敛导致按钮 disabled，短暂等待后重试
        for _ in range(10):
            if submit_btn.is_enabled():
                break
            self.page.wait_for_timeout(200)
        submit_btn.click()
        self.wait_for_page_ready()

    # ------------------------------------------------------------------
    # 配置项
    # ------------------------------------------------------------------
    @submenu("配置项")
    def configmap_create(self, name, labels=None, datas=None):
        """创建配置项。

        Args:
            name: 配置项名称，2~253个字符，由小写字母/数字/短横线/点组成
            labels: 标签字典，如 {"test": "1024"}
            datas: 数据字典，如 {"cce-test2": "cce_test-122333322"}
        """
        self.btn_create.click()

        dialog = self.page.locator(".el-dialog").filter(has_text="创建配置项")
        dialog.wait_for(state="visible", timeout=10000)
        self._fill_config_dialog(dialog, name, labels=labels, datas=datas)

        dialog.get_by_text("立即创建").click()
        self.wait_for_page_ready()

    @submenu("配置项")
    def configmap_delete(self, name):
        """删除指定名称的配置项。

        Args:
            name: 配置项名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("配置项")
    def configmap_batch_delete(self, names):
        """批量删除配置项。

        Args:
            names: 配置项名称列表
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("配置项")
    def configmap_goto_detail(self, name):
        """点击配置项名称进入详情页。

        Args:
            name: 配置项名称
        """
        self.page.locator(".el-table__row").filter(has_text=name).locator("a").first.click()
        self.wait_for_page_ready()

    def configmap_assert_detail(self, name, labels=None, datas=None):
        """断言配置项详情页数据。

        Args:
            name: 期望的配置项名称
            labels: 期望的标签字典
            datas: 期望的数据字典
        """
        title = self.page.locator(".detail-top_message .title")
        expect(title).to_have_text(name)

        if labels:
            for key, value in labels.items():
                tag = self.page.locator(".el-tag").filter(has_text=f"{key}:{value}")
                expect(tag).to_be_visible()

        if datas:
            data_tab = self.page.locator(".el-tabs__item").filter(has_text="数据")
            data_tab.click()
            self.page.wait_for_timeout(500)
            for data_name in datas.keys():
                row = self.page.locator(".el-table__row").filter(has_text=data_name)
                expect(row).to_be_visible()

    # ------------------------------------------------------------------
    # 配置项-详情页数据操作
    # ------------------------------------------------------------------
    def _detail_add_data_click(self):
        """在详情页点击"添加数据"按钮（限定在详情内容区域，避免与弹窗内按钮冲突）。"""
        detail_content = self.page.locator(".detail-content").first
        detail_content.get_by_text("添加数据").click()

    def configmap_data_add(self, data_name, content):
        """在配置项详情页添加一条数据。

        Args:
            data_name: 数据名称
            content: 数据内容
        """
        self._detail_add_data_click()
        self._open_data_dialog_and_fill("添加配置数据", data_name, content)

    def configmap_data_edit(self, data_name, content):
        """在配置项详情页编辑一条数据。

        Args:
            data_name: 数据名称
            content: 新的数据内容
        """
        self.click_action(data_name, "编辑")
        self._open_data_dialog_and_fill("修改配置数据", data_name, content, submit_text="保存")

    def configmap_data_delete(self, data_name):
        """在配置项详情页删除一条数据。

        Args:
            data_name: 数据名称
        """
        self.click_action(data_name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def configmap_data_batch_delete(self, data_names):
        """在配置项详情页批量删除数据。

        Args:
            data_names: 数据名称列表
        """
        detail_content = self.page.locator(".detail-content").first
        detail_content.locator(".el-table__row").first.wait_for(state="visible", timeout=10000)
        self.select_rows_by_names(data_names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def configmap_data_assert_list(self, expected_names):
        """断言配置项详情页数据列表包含指定名称。

        Args:
            expected_names: 期望存在的数据名称（str 或 list）
        """
        if isinstance(expected_names, str):
            expected_names = [expected_names]
        detail_content = self.page.locator(".detail-content").first
        for name in expected_names:
            row = detail_content.locator(".el-table__row").filter(has_text=name)
            expect(row).to_be_visible()

    def configmap_data_assert_not_list(self, expected_names):
        """断言配置项详情页数据列表不包含指定名称。

        Args:
            expected_names: 期望不存在的数据名称（str 或 list）
        """
        if isinstance(expected_names, str):
            expected_names = [expected_names]
        detail_content = self.page.locator(".detail-content").first
        for name in expected_names:
            row = detail_content.locator(".el-table__row").filter(has_text=name)
            expect(row).not_to_be_visible()

    # ------------------------------------------------------------------
    # 密钥
    # ------------------------------------------------------------------
    @submenu("密钥")
    def secret_create(self, name, secret_type="Opaque", labels=None, datas=None):
        """创建密钥。

        Args:
            name: 密钥名称
            secret_type: 密钥类型，如 "Opaque"（默认）
            labels: 标签字典
            datas: 数据字典，如 {"cce-test2": "cce_test-122333322"}
        """
        self.btn_create.click()

        dialog = self.page.locator(".el-dialog").filter(has_text="创建密钥")
        dialog.wait_for(state="visible", timeout=10000)

        # 默认已选中"系统"单选和 Opaque，如需切换类型再处理
        if secret_type != "Opaque":
            dialog.locator(".el-form-item").filter(has_text="类型").get_by_text("自定义").click()
            dialog.locator(".el-form-item").filter(has_text="类型").locator("input").last.fill(secret_type)

        self._fill_config_dialog(dialog, name, labels=labels, datas=datas)

        dialog.get_by_text("立即创建").click()
        self.wait_for_page_ready()

    @submenu("密钥")
    def secret_delete(self, name):
        """删除指定名称的密钥。

        Args:
            name: 密钥名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("密钥")
    def secret_goto_detail(self, name):
        """点击密钥名称进入详情页。

        Args:
            name: 密钥名称
        """
        self.page.locator(".el-table__row").filter(has_text=name).locator("a").first.click()
        self.wait_for_page_ready()

    @submenu("密钥")
    def secret_assert_list(self, name, secret_type=None):
        """断言密钥列表页包含指定密钥，并可选断言类型。

        Args:
            name: 期望的密钥名称
            secret_type: 期望的类型（可选）
        """
        row = self.page.locator(".el-table__row").filter(has_text=name)
        expect(row).to_be_visible()
        if secret_type:
            expect(row).to_contain_text(secret_type)

    # ------------------------------------------------------------------
    # 密钥-详情页数据操作
    # ------------------------------------------------------------------
    def secret_data_add(self, data_name, content):
        """在密钥详情页添加一条数据。

        Args:
            data_name: 数据名称
            content: 数据内容
        """
        self._detail_add_data_click()
        self._open_data_dialog_and_fill("添加密钥数据", data_name, content)

    def secret_data_edit(self, data_name, content):
        """在密钥详情页编辑一条数据。

        Args:
            data_name: 数据名称
            content: 新的数据内容
        """
        self.click_action(data_name, "编辑")
        self._open_data_dialog_and_fill("修改密钥数据", data_name, content)

    def secret_data_delete(self, data_name):
        """在密钥详情页删除一条数据。

        Args:
            data_name: 数据名称
        """
        self.click_action(data_name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def secret_data_assert_list(self, expected_names):
        """断言密钥详情页数据列表包含指定名称。

        Args:
            expected_names: 期望存在的数据名称（str 或 list）
        """
        if isinstance(expected_names, str):
            expected_names = [expected_names]
        detail_content = self.page.locator(".detail-content").first
        for name in expected_names:
            row = detail_content.locator(".el-table__row").filter(has_text=name)
            expect(row).to_be_visible()

    def secret_data_assert_not_list(self, expected_names):
        """断言密钥详情页数据列表不包含指定名称。

        Args:
            expected_names: 期望不存在的数据名称（str 或 list）
        """
        if isinstance(expected_names, str):
            expected_names = [expected_names]
        detail_content = self.page.locator(".detail-content").first
        for name in expected_names:
            row = detail_content.locator(".el-table__row").filter(has_text=name)
            expect(row).not_to_be_visible()
