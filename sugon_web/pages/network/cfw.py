import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect


class CfwMixin(BasePage):
    """云防火墙页面动作。"""

    def _cfw_select_option(self, dropdown, option_text):
        """打开下拉框并选择指定选项（实例创建页 el-select）。"""
        dropdown.click()
        self.page.wait_for_timeout(500)
        # 在 el-select 下拉列表项内精确查找，避免全局 li 干扰
        option = self.locator(".el-select-dropdown__item").filter(
            has_text=option_text
        ).first
        option.click()

    def _strategy_select_option(self, dropdown, option_text):
        """策略表单中的下拉框选择（使用 listitem 角色）。"""
        dropdown.click()
        self.page.wait_for_timeout(500)
        option = self.get_by_role("listitem").filter(has_text=option_text).first
        option.click()

    def cfw_create(self, name, version=None, cluster=None, protected_resource=None, spec=None):
        """创建云防火墙。

        Args:
            name: 云防火墙名称
            version: 防火墙版本，如 "山石引擎-5.5"
            cluster: 部署集群，如 "Autotest"
            protected_resource: 待防护资源标识，用于表格行 radio 前缀匹配
            spec: 规格名称，如 "cfw.d6.large"；不传时默认选择第一个可用规格
        """
        self.goto_service("云防火墙")
        self.page.wait_for_timeout(3000)
        self.goto_submenu("实例管理")
        self.page.wait_for_timeout(2000)

        self.btn_create.click()
        self.page.wait_for_timeout(2000)

        # 基础配置表单
        form = self.locator("form").filter(has_text=re.compile(r"基础配置"))
        name_input = form.get_by_role("textbox").first
        name_input.click()
        name_input.fill(name)

        # 选择版本
        if version:
            version_dropdown = self.locator("div").filter(
                has_text=re.compile(r"^版本")
            ).get_by_placeholder("请选择")
            self._cfw_select_option(version_dropdown, version)

        # 选择集群：精确匹配包含"集群" label 的 el-form-item 容器
        if cluster:
            cluster_dropdown = self.locator(".el-form-item").filter(
                has=self.get_by_text("集群", exact=False)
            ).get_by_placeholder("请选择")
            self._cfw_select_option(cluster_dropdown, cluster)

        # 选择规格（高级配置区域）
        self.page.wait_for_timeout(1000)
        if spec:
            spec_radio = self.locator(".el-table__body-wrapper").get_by_role(
                "radio", name=re.compile(re.escape(spec))
            )
            if spec_radio.count() > 0:
                spec_radio.first.click()
            else:
                self.get_by_text(spec, exact=False).first.click()
        else:
            # 默认选择第一个规格：点击第一行第一个单元格（radio 列）
            first_row = self.locator(".el-table__body-wrapper tbody tr").first
            if first_row.count() > 0:
                first_row.locator("td").first.click(force=True)

        # 选择防护资源
        if protected_resource:
            self.get_by_role(
                "radio", name=re.compile(re.escape(protected_resource))
            ).click()
            self.locator(".el-table").first.click()

        # 提交创建
        create_btn = self.get_by_text("立即创建")
        expect(create_btn).to_be_visible(timeout=10000)
        create_btn.click()

        self.wait_for_page_ready()

    def cfw_strategy_create(self, cfw_name, strategy_name, security_domain=None, target=None):
        """在指定云防火墙实例下创建策略。

        前置条件：云防火墙实例已处于运行中状态。

        Args:
            cfw_name: 云防火墙实例名称
            strategy_name: 策略名称
            security_domain: 安全域，如 "mgt"
            target: 目标对象，如 "游戏平台"
        """

        # 选择目标实例并进入策略菜单：在行内点击名称进入详情
        # Element UI 固定列可能创建覆盖层拦截点击，使用 force 绕过可见性检查
        self.get_row_by_name(cfw_name).get_by_text(cfw_name, exact=True).first.click(force=True)
        self.page.wait_for_timeout(1000)
        self.get_by_role("menuitem", name="策略").click()
        self.page.wait_for_timeout(1000)

        # 点击新建
        self.get_by_text("新建").click()
        self.page.wait_for_timeout(1000)

        # 填写策略名称
        name_input = self.locator(".el-form-item").filter(
            has=self.get_by_text("名称", exact=False)
        ).get_by_role("textbox")
        name_input.click()
        name_input.fill(strategy_name)

        # 选择安全域
        if security_domain:
            domain_dropdown = self.locator(".el-form-item").filter(
                has=self.get_by_text("安全域", exact=False)
            ).get_by_placeholder("请选择")
            self._strategy_select_option(domain_dropdown, security_domain)

        # 选择目标对象（第7个表单项）
        if target:
            target_select = self.locator(".el-form-item").nth(6).locator(".el-select").first
            self._strategy_select_option(target_select, target)

        # 提交创建
        self.get_by_text("立即创建").click()

    @submenu("云防火墙CFW")
    def cfw_delete(self, names):
        """删除云防火墙，支持单个和批量操作。

        Args:
            names: 云防火墙名称（字符串）或名称列表（列表）
        """
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.assert_popup_success()
