from sugon_web.common.base import submenu
from sugon_web.common.playwright import expect


class CceConfigMixin:
    """配置管理：配置项(ConfigMap) + 密钥(Secret)。"""

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

        # 填写名称（取第一个匹配，避免与数据表格中的"名称"列冲突）
        dialog.locator(".el-form-item").filter(has_text="名称").locator("input").first.fill(name)

        # 填写标签
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

        # 填写数据
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
        # 断言名称
        title = self.page.locator(".detail-top_message .title")
        expect(title).to_have_text(name)

        # 断言标签
        if labels:
            for key, value in labels.items():
                tag = self.page.locator(".el-tag").filter(has_text=f"{key}:{value}")
                expect(tag).to_be_visible()

        # 断言数据
        if datas:
            data_tab = self.page.locator(".el-tabs__item").filter(has_text="数据")
            data_tab.click()
            self.page.wait_for_timeout(500)
            for data_name in datas.keys():
                row = self.page.locator(".el-table__row").filter(has_text=data_name)
                expect(row).to_be_visible()
