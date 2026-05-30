import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.utils.util import random_data


class CertMixin(BasePage):
    """证书管理页面。"""

    @submenu("证书管理")
    def cert_create(self, name=None, cert_type="国际服务器证书", cert_content=None, private_key=None, desc=None):
        """创建证书。

        Args:
            name: 证书名称，默认自动生成
            cert_type: 证书类型，"国际服务器证书"、"国密服务器证书" 或 "CA证书"
            cert_content: 证书内容（PEM格式）
            private_key: 私钥内容（仅国际/国密服务器证书需要）
            desc: 描述信息

        Returns:
            str: 创建的证书名称
        """
        self.btn_create.click()

        if not name:
            name = f"cert-{random_data()}"

        dialog = self.get_by_role("dialog", name="新建证书")

        # 证书名称
        dialog.get_by_placeholder("请输入证书名称").fill(name)

        # 证书类型
        dialog.get_by_role("radio", name=cert_type).click()

        # 证书内容
        dialog.get_by_placeholder("请输入证书内容").fill(cert_content)

        # 私钥（仅服务器证书）
        if cert_type in ("国际服务器证书", "国密服务器证书") and private_key:
            dialog.get_by_placeholder("请输入私钥").fill(private_key)

        # 描述
        if desc:
            dialog.get_by_placeholder("请输描述内容").fill(desc)

        self.dialog_confirm.click()
        self.logger.info(f"证书创建完成: {name} ({cert_type})")
        return name

    @submenu("证书管理")
    def cert_delete(self, name):
        """删除证书。

        Args:
            name: 证书名称
        """
        self.search(name)
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        # 等待删除确认对话框关闭，避免影响后续导航
        self.page.wait_for_timeout(1000)
        self.close_dialog_if_exists()
        self.logger.info(f"证书删除完成: {name}")

    @submenu("证书管理")
    def cert_click_modify(self, name):
        """点击证书修改按钮，打开修改对话框。

        Args:
            name: 证书名称
        """
        self.search(name)
        self.click_action(name, "修改")
        self.logger.info(f"点击证书修改: {name}")

    def cert_get_modify_dialog_content(self):
        """获取修改证书对话框中的证书内容。

        Returns:
            str: 证书内容文本
        """
        dialog = self.get_by_role("dialog", name="修改证书")
        return dialog.get_by_placeholder("请输入证书内容").input_value()

    def cert_close_modify_dialog(self):
        """关闭修改证书对话框。"""
        dialog = self.get_by_role("dialog", name="修改证书")
        dialog.get_by_text("取消").click()
        self.logger.info("关闭修改证书对话框")

    @submenu("证书管理")
    def cert_get_bound_listeners(self, cert_name):
        """获取证书绑定的监听器名称列表。

        在证书管理列表页搜索指定证书，展开其监听器列，
        提取所有绑定的监听器名称。

        Args:
            cert_name: 证书名称。

        Returns:
            list[str]: 绑定的监听器名称列表。
        """
        self.search(cert_name)

        row = self.get_row_by_name(cert_name)
        expand_icon = row.locator(".el-table__expand-icon").first
        if expand_icon.count() == 0:
            return []

        is_expanded = "el-table__expand-icon--expanded" in (
            expand_icon.get_attribute("class") or ""
        )
        if not is_expanded:
            expand_icon.click()
            self.page.wait_for_timeout(800)

        expanded_cells = self.page.locator(".el-table__expanded-cell")
        listener_names = []
        for i in range(expanded_cells.count()):
            cell = expanded_cells.nth(i)
            if not cell.is_visible():
                continue
            tags = cell.locator(".el-tag")
            for j in range(tags.count()):
                tag_text = tags.nth(j).inner_text()
                match = re.match(r"^(.+?)\(", tag_text)
                if match:
                    listener_names.append(match.group(1))
            if listener_names:
                break

        self.logger.info(f"证书 {cert_name} 绑定监听器: {listener_names}")
        return listener_names
