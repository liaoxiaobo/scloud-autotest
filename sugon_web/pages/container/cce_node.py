import re
import time

from sugon_web.common.playwright import expect


class CceNodeMixin:
    """集群节点操作：调度、标签、规格、排水、IP、挂载。"""

    def cce_node_schedule_stop(self, node_name):
        """停止指定节点的调度。"""
        self.click_action(node_name, "停止调度")
        self.dialog_confirm.click()

    def cce_node_schedule_start(self, node_name):
        """开启指定节点的调度。"""
        self.click_action(node_name, "开启调度")
        self.dialog_confirm.click()

    def cce_node_delete(self, node_name):
        """删除指定节点。

        Args:
            node_name: 节点名称
        """
        self.click_action(node_name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def cce_node_label_edit(self, node_name, labels):
        """编辑节点自定义标签，覆盖设置为指定键值对。

        Args:
            node_name: 节点名称
            labels: 自定义标签字典，为空时清空所有自定义标签
        """
        self.click_action(node_name, "编辑标签")
        dialog = self.page.locator(".el-dialog").filter(has_text="编辑标签")
        dialog.wait_for(state="visible", timeout=10000)
        while True:
            del_btns = dialog.locator("i.el-icon-delete")
            if del_btns.count() == 0:
                break
            del_btns.first.click()
            self.page.wait_for_timeout(300)
        for key, value in labels.items():
            dialog.get_by_text("添加标签").click()
            key_inputs = dialog.locator(".el-form-item").filter(has_text="键").locator("input:not([disabled])")
            key_inputs.last.fill(key)
            value_inputs = dialog.locator(".el-form-item").filter(has_text="值").locator("input:not([disabled])")
            value_inputs.last.fill(value)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def cce_node_label_add(self, node_name, key, value):
        """为节点添加单个自定义标签。"""
        self.click_action(node_name, "编辑标签")
        dialog = self.page.locator(".el-dialog").filter(has_text="编辑标签")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_text("添加标签").click()
        self.page.wait_for_timeout(800)
        key_inputs = dialog.locator(".el-form-item").filter(has_text="键").locator("input:not([disabled])")
        key_inputs.last.wait_for(state="visible", timeout=5000)
        key_inputs.last.fill(key)
        value_inputs = dialog.locator(".el-form-item").filter(has_text="值").locator("input:not([disabled])")
        value_inputs.last.wait_for(state="visible", timeout=5000)
        value_inputs.last.fill(value)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def cce_node_label_delete(self, node_name, key):
        """删除节点指定自定义标签。"""
        self.click_action(node_name, "编辑标签")
        dialog = self.page.locator(".el-dialog").filter(has_text="编辑标签")
        dialog.wait_for(state="visible", timeout=10000)
        key_inputs = dialog.locator(".el-form-item").filter(has_text="键").locator("input:not([disabled])")
        for i in range(key_inputs.count()):
            if key_inputs.nth(i).input_value() == key:
                key_inputs.nth(i).evaluate(
                    "el => el.closest('div[style*=\"display: flex\"][style*=\"width: 100%\"]').querySelector('i.el-icon-delete').click()"
                )
                break
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def cce_node_create(self, num=1, volume_size=50, flavor="4C8G", max_pods=110):
        """新增计算节点。

        Args:
            num: 节点数量，默认1
            volume_size: 云硬盘大小(GiB)，默认50
            flavor: 节点规格，默认"4C8G"
            max_pods: POD上限，默认110
        """
        self.page.locator(".cloud-button-btn").filter(has_text="新增计算节点").click()
        dialog = self.page.locator(".el-dialog").filter(has_text="新增计算节点")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="新增计算节点数").locator("input").fill(str(num))
        dialog.locator(".el-form-item").filter(has_text="云硬盘大小(GiB)").locator("input").fill(str(volume_size))
        self._select_flavor_in_dialog(dialog, flavor)
        dialog.locator(".el-form-item").filter(has_text="POD上限").locator("input").fill(str(max_pods))
        dialog.get_by_text("确定").click()

    def cce_node_drain(self, node_name):
        """对指定节点执行排水操作。"""
        self.click_action(node_name, "节点排水")
        # 等待可能的确认对话框，并尝试多种按钮文本
        self.page.wait_for_timeout(500)
        dialog = self.page.locator(".el-dialog__wrapper:visible .el-dialog")
        if dialog.count() > 0:
            for text in ["确定", "确认", "是"]:
                btn = dialog.get_by_text(text, exact=True)
                if btn.count() > 0:
                    btn.click()
                    break

    def cce_node_flavor_expand(self, node_name, target_flavor):
        """扩容指定节点的规格。

        Args:
            node_name: 节点名称
            target_flavor: 目标规格名称
        """
        self.click_action(node_name, "修改规格")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改规格")
        dialog.wait_for(state="visible", timeout=10000)
        self._select_flavor_in_dialog(dialog, target_flavor)
        dialog.get_by_text("确定").click()

    def cce_node_flavor_shrink(self, node_name, target_flavor):
        """缩容指定节点的规格（会触发风险提示二次确认）。

        Args:
            node_name: 节点名称
            target_flavor: 目标规格名称
        """
        self.click_action(node_name, "修改规格")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改规格")
        dialog.wait_for(state="visible", timeout=10000)
        self._select_flavor_in_dialog(dialog, target_flavor)
        dialog.get_by_text("确定").click()

        # 缩容场景可能出现风险提示二次确认
        try:
            risk_dialog = self.page.locator(".el-dialog").filter(has_text="风险提示")
            risk_dialog.get_by_text("确认关机并重启").click()
        except TimeoutError:
            pass

    def get_node_status(self, node_name):
        """获取指定节点的当前状态文本。

        Args:
            node_name: 节点名称

        Returns:
            str: 节点状态文本，如"正常调度"、"无法调度"等
        """
        row_data = self.get_row_data(node_name)
        return row_data.get("状态", "") if row_data else ""

    def get_node_count(self):
        """获取节点列表中的节点数量。

        通过遍历表格行并提取第二列（名称列）来统计，避免多表格干扰。

        Returns:
            int: 节点数量
        """
        rows = self.page.locator(".el-table__body-wrapper .el-table__row")
        count = 0
        seen = set()
        for i in range(rows.count()):
            row = rows.nth(i)
            try:
                name = row.locator("td").nth(1).inner_text()
                if name and name not in seen:
                    seen.add(name)
                    count += 1
            except Exception:
                pass
        return count

    def get_public_ip_text(self, timeout=0, refresh_interval=3):
        """获取页面中公网IP的显示文本。

        支持轮询等待模式：当指定 timeout > 0 时，会在超时前持续刷新页面并重试获取，
        用于处理绑定/解绑公网IP后的异步数据刷新场景。

        Args:
            timeout: 轮询等待超时时间（秒），默认0表示只检查一次
            refresh_interval: 每次刷新后等待间隔（秒），默认3秒

        Returns:
            str: 公网IP地址，未绑定返回空字符串
        """
        start_time = time.time()

        while True:
            ip_locator = self.page.locator(".cloud-item-col").filter(has_text="公网IP")
            if ip_locator.count() > 0:
                text = ip_locator.inner_text()
                match = re.search(r"公网IP\s*[:：]?\s*(\S+)", text)
                ip = match.group(1) if match else ""
            else:
                ip = ""

            # 无超时模式：直接返回
            if timeout <= 0:
                return ip

            # 有超时模式：已超时则返回
            if time.time() - start_time >= timeout:
                return ip

            # 未超时：刷新页面后等待
            self.wait_for_page_ready()
            time.sleep(refresh_interval)

    def assert_public_ip_displayed(self, displayed=True):
        """断言页面详情中公网IP的显示状态。

        解绑后页面仍保留"公网IP"字段（值显示为--），因此通过字段值而非元素存在性判断。

        Args:
            displayed: True 断言公网IP已绑定（值不为--），False 断言未绑定（值为--或空）
        """
        ip = self.get_public_ip_text()
        if displayed:
            assert ip and ip != "--", f"Expected public IP to be bound, but got: {ip!r}"
        else:
            assert not ip or ip == "--", f"Expected public IP to be unbound, but got: {ip!r}"

    def get_public_domain_text(self):
        """获取页面中公网域名的显示文本。

        Returns:
            str: 公网域名，未绑定返回空字符串
        """
        domain_locator = self.page.locator(".cloud-item-col").filter(has_text="公网域名")
        if domain_locator.count() == 0:
            return ""
        text = domain_locator.inner_text()
        match = re.search(r"公网域名\s*[:：]?\s*(\S+)", text)
        return match.group(1) if match else ""

    def get_node_public_ip_text(self, node_name):
        """获取指定节点行中的公网IP文本。

        Args:
            node_name: 节点名称

        Returns:
            str: 节点公网IP地址，未绑定返回空字符串
        """
        row_data = self.get_row_data(node_name)
        return row_data.get("公网IP", "") if row_data else ""

    def cce_node_volume_mount_new(self, node_name, name, volume_type, volume_mode, size, mount_path):
        """为节点挂载新创建的云硬盘。

        Args:
            node_name: 节点名称
            name: 云硬盘名称
            volume_type: 云硬盘类型
            volume_mode: 云硬盘模式（thin/thick）
            size: 容量(GiB)
            mount_path: 挂载目录
        """
        self.click_action(node_name, "挂载云硬盘")
        dialog = self.page.locator(".el-dialog").filter(has_text="挂载云硬盘")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="云硬盘名称").locator("input").fill(name)
        dialog.locator(".el-form-item").filter(has_text="类型").locator(".el-select").click()
        self._select_option(volume_type, exact=False)
        dialog.locator(".el-form-item").filter(has_text="云硬盘模式").locator(".el-select").click()
        self._select_option(volume_mode, exact=False)
        dialog.locator(".el-form-item").filter(has_text="云硬盘容量").locator("input").fill(str(size))
        dialog.locator(".el-form-item").filter(has_text="云硬盘挂载目录").locator("input").fill(mount_path)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def cce_node_volume_mount_exist(self, node_name, volume_name):
        """为节点挂载已有的云硬盘。

        Args:
            node_name: 节点名称
            volume_name: 已有云硬盘名称
        """
        self.click_action(node_name, "挂载云硬盘")
        dialog = self.page.locator(".el-dialog").filter(has_text="挂载云硬盘")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_role("radio", name="选择已有云硬盘").click()
        row = dialog.locator(".el-table__row").filter(has_text=volume_name)
        row.locator(".el-radio__input").click(force=True)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def cce_public_ip_bind(self, network="public_net(基础版)"):
        """为集群绑定公网IP。

        Args:
            network: 网络名称，默认"public_net(基础版)"

        Returns:
            str: 实际绑定的公网IP地址
        """
        self.page.get_by_text("绑定公网IP").first.click()
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()
        self.wait_for_page_ready()
        return ip_address

    def cce_public_ip_unbind(self):
        """为集群解绑公网IP。"""
        self.page.get_by_text("解绑公网IP").first.click()
        self.get_by_label("解除绑定公网IP", exact=True).get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    def cce_node_public_ip_bind(self, node_name, network="public_net(基础版)"):
        """为节点绑定公网IP。

        Args:
            node_name: 节点名称
            network: 网络名称，默认"public_net(基础版)"

        Returns:
            str: 实际绑定的公网IP地址
        """
        self.click_action(node_name, "绑定公网IP")
        dialog = self.page.get_by_role("dialog", name="绑定公网IP", exact=True)
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为"关闭"的IP
        ip_row = dialog.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()
        return ip_address

    def cce_node_public_ip_unbind(self, node_name):
        """为节点解绑公网IP。

        Args:
            node_name: 节点名称
        """
        self.click_action(node_name, "解绑公网IP")
        dialog = self.page.locator(".el-dialog").filter(has_text="解除绑定公网IP")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()
