import re

from sugon_web.common.base import BasePage


class CceBaseMixin(BasePage):
    """CCE 通用辅助方法。"""

    def _select_option(self, option_text, exact=True):
        """在已展开的 el-select 下拉菜单中选择指定选项。

        Args:
            option_text: 选项文本
            exact: 是否精确匹配（默认True）。对于label包含前后缀的选项（如云硬盘类型）可设为False使用子串匹配。
        """
        # 等待可见下拉菜单数量稳定为1，避免前一个dropdown关闭动画与新打开的dropdown重叠，导致.last选错
        self.page.wait_for_selector(".el-select-dropdown:visible", state="attached", timeout=10000)
        for _ in range(20):
            if self.page.locator(".el-select-dropdown:visible").count() == 1:
                break
            self.page.wait_for_timeout(100)

        # 在所有可见下拉菜单中查找包含目标选项的项（避免.last选错）
        if exact:
            pattern = re.compile(rf"^{re.escape(option_text)}$")
        else:
            pattern = option_text

        dropdowns = self.page.locator(".el-select-dropdown:visible").all()
        for dropdown in dropdowns:
            item = dropdown.locator(".el-select-dropdown__item").filter(has_text=pattern)
            if item.count() > 0:
                item.first.dispatch_event("click")
                # 等待下拉菜单关闭动画完成，避免遮挡后续操作
                self.page.wait_for_timeout(800)
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
                return

        # 兜底：使用.last（兼容旧行为）
        dropdown = self.page.locator(".el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=10000)
        item = dropdown.locator(".el-select-dropdown__item").filter(has_text=pattern)
        item.first.dispatch_event("click")
        self.page.wait_for_timeout(800)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(200)

    def _fill_cidr(self, label, cidr):
        """填写CIDR网段（分段输入框）。

        Args:
            label: 表单标签名称
            cidr: CIDR字符串，如"10.0.0.0/16"
        """
        # 解析CIDR
        parts = cidr.replace("/", ".").split(".")
        # 定位到该表单项下的可编辑输入框（排除 el-select 的 readonly 显示框）
        form_item = self.page.locator(".el-form-item").filter(has_text=label)
        inputs = form_item.locator("input:not([readonly])")
        for i, part in enumerate(parts):
            if i < inputs.count():
                inputs.nth(i).fill(part)

    def _select_flavor(self, flavor):
        """在规格表格中选择指定规格。

        Args:
            flavor: 规格名称，如"cce.d6.xlarge"
        """
        self.page.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)
        row = self.page.locator(".el-table__row").filter(has_text=flavor)
        if row.count() == 0:
            row = self.page.locator(".el-table__row").first
        row.first.locator(".el-radio").dispatch_event("click")

    def _select_flavor_in_dialog(self, container, flavor):
        """在指定容器（如对话框）内的规格表格中选择指定规格。

        Args:
            container: 对话框容器 Locator
            flavor: 规格名称，如"cce.d6.xlarge"
        """
        container.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)
        row = container.locator(".el-table__row").filter(has_text=flavor)
        if row.count() == 0:
            row = container.locator(".el-table__row").first
        row.first.locator(".el-radio").dispatch_event("click")
