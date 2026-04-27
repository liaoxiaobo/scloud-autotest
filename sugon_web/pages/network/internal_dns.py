import re

from playwright.sync_api import expect

from sugon_web.common.base import BasePage, submenu


class InternalDnsMixin(BasePage):
    """内网解析页面动作。"""

    def _get_dns_dialog(self, title: str):
        """获取内网解析对话框。"""
        dialog = self.get_by_role("dialog", name=title)
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")
        return dialog

    def _get_dns_form_item(self, dialog, label: str):
        """根据表单标签获取当前表单项。"""
        pattern = re.compile(rf"^\s*\*?\s*{re.escape(label)}")
        return dialog.locator(".el-form-item").filter(has_text=pattern).first

    def _fill_dns_vpcs(self, dialog, vpc_names):
        """填写内网解析关联 VPC。"""
        if isinstance(vpc_names, str):
            vpc_names = [vpc_names]

        vpc_item = self._get_dns_form_item(dialog, "VPC")
        vpc_select = vpc_item.locator(".el-select").first
        vpc_select.click()

        for vpc_name in vpc_names:
            option = self.locator(".el-select-dropdown:visible li").filter(
                has_text=re.compile(rf"^{re.escape(vpc_name)}$")
            ).first
            expect(option).to_be_visible(timeout=8000)
            option.click()

        dialog.locator(".el-dialog__header").click()

    @submenu("内网解析")
    def internal_dns_create(self, domain, vpc_name, email="", desc=""):
        """创建内网解析。

        Args:
            domain: 内网解析域名。
            vpc_name: 关联的 VPC 名称，支持字符串或名称列表。
            email: 管理员邮箱，默认为空。
            desc: 描述信息，默认为空。
        """
        self.btn_create.click()

        dialog = self._get_dns_dialog("新建内网解析")
        self._get_dns_form_item(dialog, "域名").locator("input").first.fill(domain)
        self._fill_dns_vpcs(dialog, vpc_name)

        if email:
            self._get_dns_form_item(dialog, "邮箱").locator("input").first.fill(email)

        if desc:
            self._get_dns_form_item(dialog, "描述").locator("textarea").fill(desc)

        dialog.get_by_text("确定", exact=True).click()

    @submenu("内网解析")
    def internal_dns_edit(self, domain, new_email=None, new_desc=None):
        """修改内网解析的邮箱和描述。

        Args:
            domain: 待修改的内网解析域名。
            new_email: 新邮箱。
            new_desc: 新描述。
        """
        self.click_action(domain, "修改")

        dialog = self._get_dns_dialog("修改内网解析")
        if new_email is not None:
            self._get_dns_form_item(dialog, "邮箱").locator("input").first.fill(new_email)

        if new_desc is not None:
            self._get_dns_form_item(dialog, "描述").locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()

    @submenu("内网解析")
    def internal_dns_delete(self, domains):
        """删除内网解析，支持单个和批量操作。

        Args:
            domains: 单个域名字符串或域名列表。
        """
        if isinstance(domains, list):
            self.select_rows_by_names(domains)
            self.btn_batch_delete.click()
        else:
            self.click_action(domains, "删除")

        self.dialog_confirm.click()

    @submenu("内网解析")
    def internal_dns_search(self, keyword):
        """搜索内网解析。"""
        self.search(keyword)

    @submenu("内网解析")
    def internal_dns_reset(self):
        """重置内网解析搜索条件。"""
        self.btn_reset.click()
        self.page.wait_for_timeout(1000)

    @staticmethod
    def internal_dns_record_alias(domain: str, host_record: str) -> str:
        """返回解析记录列表中的完整域名。"""
        return f"{host_record}.{domain}" if host_record else domain

    @submenu("内网解析")
    def goto_internal_dns_detail(self, domain: str, tab_name: str = "详情", row_name: str = None):
        """进入内网解析详情页，并切换到指定页签。"""
        return self.goto_detail_page(domain, row_name=row_name, tab_name=tab_name)

    def _get_dns_record_form_item(self, dialog, label: str):
        """根据表单标签获取解析记录表单项。"""
        pattern = re.compile(rf"^\s*\*?\s*{re.escape(label)}")
        return dialog.locator(".el-form-item").filter(has_text=pattern).first

    def _get_active_dns_record_tab(self):
        """获取当前激活的解析记录页签容器。"""
        return self.page.locator(".cl-table-container:visible").first

    def _select_dns_record_type(self, dialog, record_type: str):
        """选择解析记录类型。"""
        self._get_dns_record_form_item(dialog, "类型").locator(".el-select").first.click()
        option = self.locator(".el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(record_type)}(?:\s|-|$)")
        ).first
        expect(option).to_be_visible(timeout=8000)
        option.click()

    def _fill_dns_record_values(self, dialog, record_type: str, values):
        """填写解析记录值。

        Args:
            dialog: 当前可见的记录集弹窗定位器。
            record_type: 记录类型，当前支持 ``A`` 和 ``SRV``。
            values: 记录值。A 记录支持单个 IP 或 IP 列表；SRV 记录使用单个
                ``priority weight port target`` 格式字符串。
        """
        record_values = values if isinstance(values, list) else [values]
        if record_type == "A":
            value_inputs = dialog.get_by_placeholder("例如：192.168.10.10")
            while value_inputs.count() < len(record_values):
                dialog.get_by_role("button", name=re.compile("添加")).click()
                value_inputs = dialog.get_by_placeholder("例如：192.168.10.10")

            for index, value in enumerate(record_values):
                value_inputs.nth(index).fill(str(value))
            return

        if record_type == "SRV":
            srv_input = dialog.get_by_placeholder("例如：[优先级][权重][端口][目标地址],以空格隔开").first
            srv_input.fill(str(record_values[0]))
            return

        raise ValueError(f"当前仅支持 A 或 SRV 记录，收到类型: {record_type}")

    def internal_dns_record_create(
        self,
        domain: str,
        host_record: str,
        record_type: str = "A",
        ttl: int = 600,
        values="192.168.10.10",
        desc: str = "",
    ):
        """在内网解析详情页创建解析记录。

        操作步骤：
            1. 进入指定内网解析详情页的“解析记录”页签；
            2. 打开“新建记录集”弹窗并填写主机记录、类型、TTL、值和描述；
            3. 提交后等待页面刷新完成。

        Args:
            domain: 所属内网解析域名。
            host_record: 主机记录，传空字符串表示根域记录。
            record_type: 记录类型，当前支持 ``A`` 和 ``SRV``。
            ttl: TTL 值。
            values: 记录值。A 记录支持单值或多值；SRV 记录传单个格式化字符串。
            desc: 记录描述。
        """
        self.goto_internal_dns_detail(domain, tab_name="解析记录")
        self.page.get_by_text("新建", exact=True).click()

        dialog = self._get_dns_dialog("新建记录集")
        self._get_dns_record_form_item(dialog, "主机记录").locator("input").first.fill(host_record)
        self._select_dns_record_type(dialog, record_type)
        self._get_dns_record_form_item(dialog, "TTL").locator("input").first.fill(str(ttl))
        self._get_dns_record_form_item(dialog, "描述").locator("textarea, input").first.fill(desc)
        self._fill_dns_record_values(dialog, record_type, values)
        dialog.get_by_text("立即创建", exact=True).click()

    def internal_dns_record_edit(
        self,
        domain: str,
        record_alias: str,
        new_host_record: str | None = None,
        new_ttl: int | None = None,
        new_values=None,
        new_desc: str | None = None,
        record_type: str = "A",
    ):
        """修改解析记录。

        操作步骤：
            1. 进入指定内网解析详情页的“解析记录”页签；
            2. 在目标记录行点击“修改”；
            3. 按需回填主机记录、TTL、值和描述后提交。

        Args:
            domain: 所属内网解析域名。
            record_alias: 待修改记录在列表中展示的完整域名。
            new_host_record: 修改后的主机记录，传空字符串表示根域记录。
            new_ttl: 修改后的 TTL。
            new_values: 修改后的记录值。
            new_desc: 修改后的描述。
            record_type: 当前记录类型，决定值区域的填写方式。
        """
        self.goto_internal_dns_detail(domain, tab_name="解析记录")
        """修改解析记录。"""
        self.goto_internal_dns_detail(domain, tab_name="解析记录", row_name=record_alias)
        self.click_action(record_alias, "修改")

        dialog = self._get_dns_dialog("修改记录集")
        if new_host_record is not None:
            self._get_dns_record_form_item(dialog, "主机记录").locator("input").first.fill(new_host_record)
        if new_ttl is not None:
            self._get_dns_record_form_item(dialog, "TTL").locator("input").first.fill(str(new_ttl))
        if new_desc is not None:
            self._get_dns_record_form_item(dialog, "描述").locator("textarea, input").first.fill(new_desc)
        if new_values is not None:
            self._fill_dns_record_values(dialog, record_type, new_values)
        dialog.get_by_text("确定", exact=True).click()

    def internal_dns_record_delete(self, domain: str, record_aliases):
        """删除一个或多个解析记录。"""
        aliases = [record_aliases] if isinstance(record_aliases, str) else record_aliases
        self.goto_internal_dns_detail(domain, tab_name="解析记录", row_name=aliases[0])
        if len(aliases) == 1:
            self.click_action(aliases[0], "删除")
        else:
            self.select_rows_by_names(aliases)
            self.page.get_by_text("批量删除", exact=True).click()

        self.dialog_confirm.click()

    def internal_dns_record_search(self, domain: str, keyword: str):
        """搜索解析记录。"""
        self.goto_internal_dns_detail(domain, tab_name="解析记录")
        self.page.get_by_placeholder("搜索（类型、TTL、值、描述）").fill(keyword)
        self.page.get_by_text("搜索", exact=True).click()

    def internal_dns_record_reset(self, domain: str):
        """重置解析记录搜索条件。"""
        self.goto_internal_dns_detail(domain, tab_name="解析记录")
        self.btn_reset.click()
