"""
【职责】封装项目下拉框、网络选择、数据盘类型等常见选择器，处理 Element UI 下拉框展开与选项点击。

【层级】Page 层；被 BasePage 组合，page object 通过 BasePage 间接使用。

【接口】
- project_dropdown() -> Locator：项目下拉框。
- project_autotest() -> Locator：项目下拉框中的“Autotest”选项。
- disk_type_dropdown() -> Locator：数据盘类型下拉框。
- select_network(placeholder_name, option_name)：选择网络和子网。
- select_disk_type_like_doris(disk_type, label_texts=None)：选择数据盘类型，支持按标签定位并回退到页面最后一个下拉框。
- select_labeled_dropdown(label_texts, dropdown_index=0) -> Locator：按字段标签定位下拉框。

【示例】
class EcsPage(BasePage):
    def config_network(self):
        self.project_dropdown().click()
        self.project_autotest().click()
        self.select_network("请选择网络", "Autotest")
"""

import re
from time import sleep

from playwright.sync_api import Locator


class SelectorsMixin:
    """选择器/下拉框类组件 Mixin。"""

    def project_dropdown(self) -> Locator:
        """获取项目下拉框定位器。"""
        return self.locator("form").filter(has_text="基本设置").get_by_placeholder("请选择").nth(1)

    def disk_type_dropdown(self) -> Locator:
        """获取数据盘类型下拉框定位器。"""
        return self.locator("div").filter(has_text=re.compile(r"^数据盘类型")).get_by_placeholder("请选择")

    def select_labeled_dropdown(self, label_texts, dropdown_index: int = 0) -> Locator:
        """按字段标签文本定位下拉框。

        适用于页面结构一致、仅字段名称文案不同的场景。

        Args:
            label_texts: 标签文案或文案列表
            dropdown_index: 同一表单项下第几个"请选择"

        Returns:
            下拉框定位器
        """
        if isinstance(label_texts, str):
            label_texts = [label_texts]

        for label_text in label_texts:
            patterns = [
                ("div", re.compile(rf"^{re.escape(label_text)}$")),
                (".el-form-item", re.compile(re.escape(label_text))),
            ]
            for selector, pattern in patterns:
                containers = self.locator(selector).filter(has_text=pattern)
                count = containers.count()
                for i in range(count):
                    container = containers.nth(i)
                    fields = container.get_by_placeholder("请选择", exact=True)
                    if fields.count() == 0:
                        fields = container.locator("input[placeholder='请选择']")
                    if fields.count() <= dropdown_index:
                        continue
                    return fields.nth(dropdown_index)

        raise RuntimeError(f"未找到标签为 {label_texts} 的下拉框")

    def select_disk_type_like_doris(self, disk_type: str, label_texts=None) -> None:
        """选择数据盘类型。

        优先按字段标签定位；仅在标签定位失败时，回退到页面最后一个"请选择"。

        Args:
            disk_type: 磁盘类型名称
            label_texts: 数据盘类型字段标签，可传字符串或列表
        """
        dropdown = None
        label_texts = label_texts or ["数据盘类型", "云硬盘类型"]

        try:
            dropdown = self.select_labeled_dropdown(label_texts)
            dropdown.scroll_into_view_if_needed()
            dropdown.click(timeout=3000)
        except Exception:
            dropdown = None

        if dropdown is None:
            dropdowns = self.locator("#cloud-container-content").get_by_placeholder("请选择", exact=True)
            count = dropdowns.count()
            if count > 0:
                dropdown = dropdowns.nth(count - 1)
                try:
                    dropdown.scroll_into_view_if_needed()
                    dropdown.click(timeout=3000)
                except Exception:
                    dropdown = None

        if dropdown is None:
            raise RuntimeError("当前页面未找到可点击的数据盘类型下拉框")

        self.page.wait_for_timeout(1000)
        self.get_by_text(disk_type).last.click()

    def project_autotest(self) -> Locator:
        """获取 Autotest 项目选项定位器。"""
        dropdown_locator = self.page.locator("body > div.el-select-dropdown:visible").last
        dropdown_locator.wait_for(state="visible", timeout=5000)
        return dropdown_locator.locator("li").filter(has_text="Autotest").first

    def select_network(self, placeholder_name: str, option_name: str) -> None:
        """选择网络和子网。

        Args:
            placeholder_name: placeholder 名称
            option_name: 下拉框选项（支持精确匹配或前缀匹配）
        """
        page = self.page
        page.get_by_role("textbox", name=placeholder_name).click()
        sleep(1)
        dropdown = page.locator("body > div.el-select-dropdown:visible").last
        dropdown.wait_for(state="visible")
        items = dropdown.locator("li.el-select-dropdown__item")
        if option_name == "Autotest":
            pattern = re.compile(rf"^{re.escape(option_name)}$")
        else:
            pattern = re.compile(rf"^{re.escape(option_name)}.*")

        target = items.filter(has_text=pattern)
        target.first.scroll_into_view_if_needed()
        target.first.click()
