"""传输策略组 (Transfer Strategy Group) 页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data


class TransferStrategyMixin(BasePage):
    """传输策略组模块页面对象，封装列表、创建、编辑、详情、删除等操作。"""

    service_name = "虚拟私有云"

    def _ensure_list_page(self):
        """确保当前位于传输策略组列表页。"""
        for attempt in range(3):
            current_url = self.page.url
            if "#/transfer-strategy" in current_url:
                # 轻量等待：只等loading消失，不触发load事件（hash路由不触发load）
                try:
                    loading = self.page.locator(".el-loading-mask:visible")
                    if loading.count() > 0:
                        expect(loading).to_have_count(0, timeout=15000)
                except Exception:
                    pass
                self.page.wait_for_timeout(2000)
                return

            self.logger.info(f"当前不在传输策略组列表页({current_url})，尝试导航(第{attempt + 1}次)")

            # 策略1: 直接设置hash（Vue Router客户端路由，无页面刷新）
            try:
                self.page.evaluate("window.location.hash = '#/transfer-strategy'")
                self.page.wait_for_timeout(5000)
                if "#/transfer-strategy" in self.page.url:
                    # hash路由不触发load事件，轻量等待即可
                    try:
                        loading = self.page.locator(".el-loading-mask:visible")
                        if loading.count() > 0:
                            expect(loading).to_have_count(0, timeout=15000)
                    except Exception:
                        pass
                    self.page.wait_for_timeout(2000)
                    return
            except Exception as e:
                self.logger.debug(f"直接设置hash失败: {e}")

            # 策略2: 先goto服务根路径，再设置hash
            try:
                base_url = Config.get("base_url").rstrip("/")
                self.page.goto(f"{base_url}/vpc", wait_until="commit")
                self.page.wait_for_timeout(3000)
                self.page.evaluate("window.location.hash = '#/transfer-strategy'")
                self.page.wait_for_timeout(5000)
                if "#/transfer-strategy" in self.page.url:
                    try:
                        loading = self.page.locator(".el-loading-mask:visible")
                        if loading.count() > 0:
                            expect(loading).to_have_count(0, timeout=15000)
                    except Exception:
                        pass
                    self.page.wait_for_timeout(2000)
                    return
            except Exception as e:
                self.logger.debug(f"goto + hash 失败: {e}")

        # 兜底策略: 使用菜单导航
        try:
            self.goto_service("虚拟私有云")
            self.goto_submenu("机密互联")
            self.page.wait_for_timeout(5000)
        except Exception as e:
            self.logger.warning(f"菜单导航兜底也失败: {e}")

        self.wait_for_page_ready()

    def transfer_strategy_create(self, name=None, description=""):
        """创建传输策略组。

        Args:
            name: 策略组名称，为None时自动生成随机名称。
            description: 策略组描述，默认为空字符串。

        Returns:
            str: 创建的策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()

        # 点击新建按钮（cl-button 自定义组件，用 get_by_text）
        self.get_by_text("新建", exact=True).click()

        if not name:
            name = f"tsg-{random_data()}"

        # 定位弹窗
        dialog = self.page.locator(".el-dialog:visible").first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写名称
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).get_by_role("textbox")
        name_input.click()
        name_input.fill(name)
        expect(name_input).to_have_value(name, timeout=5000)

        # 填写描述（如有）
        if description:
            desc_input = dialog.get_by_placeholder("请输入描述")
            desc_input.click()
            desc_input.fill(description)
            expect(desc_input).to_have_value(description, timeout=5000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    def transfer_strategy_edit(self, name, new_name=None, new_description=None):
        """编辑指定传输策略组的名称和描述。

        打开编辑弹窗，可选修改名称和/或描述，点击确定提交。

        Args:
            name: 策略组当前名称，用于列表页定位。
            new_name: 新名称，为None时不修改名称。
            new_description: 新描述，为None时不修改描述。

        Returns:
            dict: 包含修改前数据的字典，键为 "name" 和 "description"。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()

        # 搜索并点击编辑
        self.search(name)
        self.click_action(name, "编辑")

        # 等待弹窗出现
        dialog = self.page.locator(".el-dialog:visible").first
        dialog.wait_for(state="visible", timeout=15000)

        # 获取修改前的值
        original_data = {}

        # 名称输入框
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).get_by_role("textbox")
        name_input.wait_for(state="visible", timeout=10000)
        original_data["name"] = name_input.input_value()

        # 描述输入框（textarea）
        desc_input = dialog.get_by_placeholder("请输入描述")
        desc_input.wait_for(state="visible", timeout=10000)
        original_data["description"] = desc_input.input_value()

        # 修改名称
        if new_name is not None:
            name_input.fill("")
            name_input.fill(new_name)
            expect(name_input).to_have_value(new_name, timeout=5000)

        # 修改描述
        if new_description is not None:
            desc_input.fill("")
            desc_input.fill(new_description)
            expect(desc_input).to_have_value(new_description, timeout=5000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return original_data

    def transfer_strategy_delete(self, name):
        """删除指定名称的传输策略组。

        Args:
            name: 策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        # 先搜索缩小范围，再点击删除
        self.search(name)
        self.click_action(name, "删除")
        # 确认删除弹窗
        self.dialog_confirm.click()

    def goto_transfer_strategy_detail(self, name):
        """进入指定传输策略组的详情页。

        Args:
            name: 策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        # 先按名称搜索，避免列表仍残留上一次的过滤条件导致目标行不可见
        self.search(name)
        self.wait_for_page_ready()
        # 点击名称链接进入详情页 - 使用 scoped 在表格行内定位
        row = self.get_row_by_name(name)
        name_link = row.get_by_text(name, exact=True)
        expect(name_link).to_be_visible(timeout=10000)
        name_link.click()
        self.wait_for_page_ready()

    def encrypt_rule_create(self, key_name, remote_cidr, protocol="全部", ip_version="IPv4"):
        """在当前加密规则tab下创建加密规则。

        调用前必须已位于传输策略组详情页的加密规则tab。
        操作步骤：
        1. 点击新建按钮打开规则创建弹窗
        2. 选择协议、密钥、IP版本，输入远端CIDR
        3. 点击确定提交

        Args:
            key_name: 密钥名称（如 sm4-ossl1）。
            remote_cidr: 远端CIDR地址（如 10.0.0.0/24）。
            protocol: 协议，可选值 "全部"/"TCP"/"UDP"/"ICMP"，默认 "全部"。
            ip_version: IP版本，可选值 "IPv4"/"IPv6"，默认 "IPv4"。

        Returns:
            dict: 包含创建规则的关键字段信息。
        """
        # 点击新建按钮（cl-button 自定义组件，用 get_by_text）
        self.get_by_text("新建", exact=True).click()

        # 定位弹窗
        dialog = self.page.locator(".el-dialog:visible").first
        expect(dialog).to_be_visible(timeout=10000)

        # 1. 确认策略组名称（disabled input，只读校验）
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"传输策略组名称")
        ).get_by_role("textbox")
        expect(name_input).to_be_visible(timeout=5000)
        # 返回实际策略组名称供调用方校验
        actual_strategy_name = name_input.input_value()

        # 2. 选择协议（el-radio-group）
        radio_group = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"协议")
        ).locator(".el-radio-group")
        radio_item = radio_group.locator("label[role='radio']").filter(
            has_text=re.compile(rf"^{re.escape(protocol)}$")
        )
        expect(radio_item).to_be_visible(timeout=5000)
        radio_item.click()

        # 3. 选择密钥 - 点击"选择密钥"按钮，在弹出的密钥选择drawer中选择
        select_key_btn = dialog.get_by_text("选择密钥", exact=True).first
        if select_key_btn.count() > 0 and select_key_btn.is_visible():
            select_key_btn.click()
            # 等待密钥选择drawer出现（SecretKey组件渲染为el-drawer）
            key_drawer = self.page.locator(".el-drawer:visible").first
            expect(key_drawer).to_be_visible(timeout=10000)
            # 在密钥列表中按文案定位并选择
            key_row = key_drawer.locator(".el-table__body-wrapper tr").filter(
                has_text=re.compile(rf"\b{re.escape(key_name)}\b")
            ).first
            if key_row.count() == 0:
                # 如果按名称找不到，尝试第一行（环境可能只有一条密钥）
                key_row = key_drawer.locator(".el-table__body-wrapper tr").first
            expect(key_row).to_be_visible(timeout=10000)
            key_row.locator(".el-radio").first.click()
            key_drawer.get_by_text("确定", exact=True).first.click()
            expect(key_drawer).to_be_hidden(timeout=10000)
        else:
            # 检查已选中的密钥tag是否匹配
            tag_info = dialog.locator(".tag-info").filter(
                has_text=re.compile(rf"{re.escape(key_name)}")
            )
            if tag_info.count() == 0:
                # 尝试点击已存在的tag上的删除按钮重新选择
                delete_tag = dialog.locator(".tag-info .icon-close").first
                if delete_tag.count() > 0 and delete_tag.is_visible():
                    delete_tag.click()
                    dialog.get_by_text("选择密钥", exact=True).first.click()
                    key_drawer = self.page.locator(".el-drawer:visible").first
                    expect(key_drawer).to_be_visible(timeout=10000)
                    key_row = key_drawer.locator(".el-table__body-wrapper tr").filter(
                        has_text=re.compile(rf"\b{re.escape(key_name)}\b")
                    ).first
                    if key_row.count() == 0:
                        key_row = key_drawer.locator(".el-table__body-wrapper tr").first
                    expect(key_row).to_be_visible(timeout=10000)
                    key_row.locator(".el-radio").first.click()
                    key_drawer.get_by_text("确定", exact=True).first.click()
                    expect(key_drawer).to_be_hidden(timeout=10000)

        # 4. 选择IP版本（el-select）
        ip_select = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"IP版本")
        ).locator(".el-select")
        expect(ip_select).to_be_visible(timeout=5000)
        ip_select.click()
        # 选项在body级的dropdown中
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(ip_version)}$")
        ).click()

        # 5. 输入远端CIDR
        cidr_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"远端CIDR")
        ).get_by_role("textbox")
        cidr_input.click()
        cidr_input.fill(remote_cidr)
        expect(cidr_input).to_have_value(remote_cidr, timeout=5000)

        # 提交前确认按钮可点
        submit_btn = dialog.get_by_text("确定", exact=True)
        expect(submit_btn).to_be_enabled(timeout=5000)

        # 点击确定提交
        submit_btn.click()

        return {
            "strategy_name": actual_strategy_name,
            "protocol": protocol,
            "key_name": key_name,
            "ip_version": ip_version,
            "remote_cidr": remote_cidr,
        }

    def encrypt_rule_delete(self, remote_cidr):
        """删除当前加密规则tab下的指定远端CIDR的加密规则。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            remote_cidr: 远端CIDR，用于定位要删除的规则。
        """
        # 在加密规则列表中按远端CIDR定位行并删除
        self.click_action(remote_cidr, "删除")
        # 确认删除弹窗
        self.dialog_confirm.click()

    def get_encrypt_rule_row_data(self, remote_cidr):
        """获取加密规则列表中指定远端CIDR的行数据。

        Args:
            remote_cidr: 远端CIDR值，用于定位行。

        Returns:
            dict: 行数据字典。
        """
        return self.get_row_data(remote_cidr)

    def assert_tab_visible(self, tab_name, timeout=10):
        """断言指定标签页可见。

        Args:
            tab_name: 标签页名称。
            timeout: 最长等待秒数，默认 10。
        """
        from sugon_web.common.playwright import expect
        tab = self.get_by_role("tab", name=tab_name)
        expect(tab).to_be_visible(timeout=timeout * 1000)
        self.logger.info(f"断言通过: 标签页 '{tab_name}' 可见")

    def get_transfer_strategy_row_data(self, name):
        """获取列表页指定传输策略组的行数据。

        Args:
            name: 策略组名称。

        Returns:
            dict: 行数据字典，包含名称、描述等字段。
        """
        return self.get_row_data(name)

    def transfer_strategy_exists(self, name):
        """检查指定名称的传输策略组是否已存在于列表中。

        会先确保位于列表页（与新建/编辑同样的进入方式），再按名称搜索后读取行数据判断。
        未找到时返回 False（不抛异常）。

        Args:
            name: 策略组名称。

        Returns:
            bool: 存在返回 True，否则 False。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.search(name)
        self.wait_for_page_ready()
        try:
            row_data = self.get_row_data(name)
        except AssertionError:
            # 列表中无该记录时 get_row_data 会抛 AssertionError，视为不存在
            return False
        return bool(row_data and row_data.get("名称") == name)

