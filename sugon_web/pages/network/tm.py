"""流量镜像 (Traffic Mirror) 页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.utils.util import random_data


class TmMixin(BasePage):
    """流量镜像模块页面对象，封装列表、创建、详情、删除等操作。"""

    service_name = "流量镜像"

    def _ensure_list_page(self):
        """确保当前位于流量镜像列表页。"""
        current_url = self.page.url
        if "#/traffic-manage" not in current_url:
            base_url = Config.get("base_url").rstrip("/")
            # Vue Router hash模式，先reload确保页面状态重置，再设置hash导航
            self.page.goto(f"{base_url}/vpc")
            self.page.wait_for_timeout(3000)
            self.page.evaluate("window.location.hash = '#/traffic-manage'")
            self.page.wait_for_timeout(3000)
            # 二次确认，若仍未跳转成功则强制reload再导航
            if "#/traffic-manage" not in self.page.url:
                self.page.reload()
                self.page.wait_for_timeout(3000)
                self.page.evaluate("window.location.hash = '#/traffic-manage'")
                self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()
        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass

    @submenu("流量镜像")
    def tm_create_inner_ecs(self, name=None, server_name=None):
        """创建云内实例-ECS类型的流量镜像。

        Args:
            name: 流量镜像名称，为None时自动生成随机名称。
            server_name: 目的ECS实例名称，用于选择目的实例。

        Returns:
            str: 创建的流量镜像名称。
        """
        self.wait_for_page_ready()
        self.page.get_by_text("新建流量镜像", exact=True).click()

        if not name:
            name = f"tm-{random_data()}"

        dialog = self.page.locator(".el-dialog:visible").first

        # 填写名称
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role(
            "textbox"
        ).fill(name)

        # 选择目的类型：云内实例
        dialog.locator("label").filter(has_text=re.compile(r"^云内实例$")).first.click()

        # 选择实例类型：云服务器
        dialog.locator("label").filter(has_text=re.compile(r"^云服务器$")).first.click()

        # 选择目的实例
        if server_name:
            dialog.get_by_placeholder("请选择").click()
            self.page.locator("li").filter(has_text=re.compile(rf"{re.escape(server_name)}")).first.click()

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    @submenu("流量镜像")
    def tm_create_outside_device(self, name=None, vlan=None, mac=None):
        """创建云外设备类型的流量镜像。

        Args:
            name: 流量镜像名称，为None时自动生成随机名称。
            vlan: VLAN值，1~4096之间的正整数。
            mac: MAC地址，格式如 fa:16:e3:44:53:47。

        Returns:
            str: 创建的流量镜像名称。
        """
        self.wait_for_page_ready()
        self.page.get_by_text("新建流量镜像", exact=True).click()

        if not name:
            name = f"tm-outside-{random_data()}"

        dialog = self.page.locator(".el-dialog:visible").first

        # 填写名称
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role(
            "textbox"
        ).fill(name)

        # 选择目的类型：云外设备
        dialog.locator("label").filter(has_text=re.compile(r"^云外设备$")).first.click()

        # 填写VLAN
        if vlan is not None:
            dialog.locator("div").filter(has_text=re.compile(r"^VLAN$")).get_by_role(
                "textbox"
            ).fill(str(vlan))

        # 填写MAC地址
        if mac:
            dialog.locator("div").filter(has_text=re.compile(r"^MAC地址$")).get_by_role(
                "textbox"
            ).fill(mac)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    def tm_delete(self, name):
        """删除指定名称的流量镜像。

        Args:
            name: 流量镜像名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)
        # 先搜索缩小范围，再点击删除
        self.search(name)
        self.page.wait_for_timeout(1000)
        self.click_action(name, "删除")
        # 确认删除弹窗，使用 BasePage 通用的确定按钮
        self.dialog_confirm.click()

    def tm_cleanup_by_mac(self, mac):
        """清理使用指定MAC地址的流量镜像。

        Args:
            mac: MAC地址，用于查找并删除对应的流量镜像。
        """
        self._ensure_list_page()
        try:
            rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) > 7:
                        row_mac = cells[7].inner_text().strip()
                        if row_mac == mac:
                            name_cell = cells[1].inner_text().strip()
                            self.logger.info(f"发现使用MAC {mac} 的流量镜像: {name_cell}，准备清理")
                            self.tm_delete(name_cell)
                            self.wait_for_page_ready()
                            return
                except Exception:
                    continue
        except Exception as e:
            self.logger.warning(f"清理流量镜像时出错: {e}")

    def goto_tm_detail(self, name):
        """进入指定流量镜像的详情页。

        Args:
            name: 流量镜像名称。
        """
        self._ensure_list_page()
        row = self.get_row_by_name(name)
        # 名称列为 cl-button type="link"，不是标准 <a> 标签
        row.get_by_text(name, exact=True).first.click()
        self.wait_for_page_ready()

    def get_tm_detail_data(self):
        """获取流量镜像详情页的数据。

        Returns:
            dict: 详情页字段数据，包含名称、类型、状态等字段。
        """
        data = {}
        self.wait_for_page_ready()

        # 流量镜像详情页使用 cl-item-col 组件，结构为：
        # <cl-item-col label="名称"><p>value</p></cl-item-col>
        # 尝试通过 label 属性或文本匹配来定位字段
        fields = ["名称", "类型", "状态", "VLAN", "MAC地址", "描述", "虚拟机名称", "实例状态", "ID", "电源状态", "集群"]

        for field in fields:
            try:
                # 方式1: 通过属性 label 定位
                field_locators = self.page.locator(f"[label='{field}']").all()
                for loc in field_locators:
                    try:
                        p_text = loc.locator("p").first.inner_text(timeout=2000).strip()
                        if p_text:
                            data[field] = p_text
                            break
                    except Exception:
                        continue

                if field not in data:
                    # 方式2: 查找包含 label 文本的元素，然后获取相邻的 p 标签
                    all_items = self.page.locator(".cl-item-col, .el-form-item, .detail-item").all()
                    for item in all_items:
                        try:
                            label_text = item.inner_text(timeout=1000)
                            if field in label_text:
                                p_val = item.locator("p").first.inner_text(timeout=2000).strip()
                                if p_val and p_val != field:
                                    data[field] = p_val
                                    break
                        except Exception:
                            continue
            except Exception:
                continue

        return data

    def get_tm_row_data(self, name):
        """获取列表页指定流量镜像的行数据。

        Args:
            name: 流量镜像名称。

        Returns:
            dict: 行数据字典，包含名称、类型、状态、VLAN、MAC地址等。
        """
        return self.get_row_data(name)
