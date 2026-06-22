import re
import time

from sugon_web.common.base import BasePage, submenu
from sugon_web.pages.container.cce_base import CceBaseMixin
from sugon_web.utils.logger import logger


class ScrPage(CceBaseMixin, BasePage):
    """容器镜像服务 SCR 页面操作封装。"""

    service_name = "容器镜像服务SCR"

    @staticmethod
    def _parse_flavor(flavor):
        """解析规格字符串为 CPU 核数和内存 GiB。

        支持格式如 "4C8G"、"2C4G"、"8C16G"。

        Args:
            flavor: 规格字符串。

        Returns:
            tuple[int, int]: (vcpus, memory_gb)
        """
        match = re.match(r"(\d+)C(\d+)G", flavor)
        if not match:
            raise ValueError(f"不支持的规格格式: {flavor}，期望格式如 '4C8G'")
        return int(match.group(1)), int(match.group(2))

    @submenu("实例管理")
    def scr_create(self, name, version=None, cluster="Autotest", network="Autotest",
                   subnet="Autotest", instance_type="ALONE", storage_type="EVS",
                   volume_type=None, volume_size=10, flavor="4C8G"):
        """创建 SCR 实例。

        Args:
            name: 实例名称。
            version: 仓库版本，默认 None 表示使用页面初始化后的默认选项。
            cluster: 集群名称，默认 "Autotest"。
            network: 专有网络名称，默认 "Autotest"。
            subnet: 子网名称（不含 CIDR 后缀），默认 "Autotest"。
            instance_type: 实例类型，默认 "ALONE"（单机），可选 "HA"。
            storage_type: 存储类型，ALONE 场景下默认 "EVS"，可选 "OSS"。
            volume_type: 云硬盘类型 ID，默认 None 表示使用 self.volume_type。
            volume_size: 云硬盘大小(GiB)，默认 10。
            flavor: 规格名称，默认 "4C8G"。
        """
        self.btn_create.click()
        self.page.wait_for_url("**/createSCR", timeout=30000)
        self.wait_for_page_ready()

        # 基本设置
        name_item = self.page.locator(".el-form-item").filter(has_text="名称")
        name_item.locator("input").first.fill(name)

        if version:
            self._select_version(version)

        self._select_cluster(cluster)

        # 网络配置
        self._select_network(network)
        self._select_subnet(subnet)

        # 实例类型（前端显示中文标签）
        instance_type_label = {"ALONE": "单机", "HA": "高可用"}.get(instance_type, instance_type)
        self.get_by_role("radio", name=instance_type_label).click()

        # 存储配置（仅单机场景）
        if instance_type == "ALONE":
            storage_type_label = {"EVS": "云硬盘", "OSS": "S3"}.get(storage_type, storage_type)
            self.get_by_role("radio", name=storage_type_label).click()
            if storage_type == "EVS":
                volume_type = volume_type or self.volume_type
                self._select_volume_type(volume_type)
                size_item = self.page.locator(".el-form-item").filter(has_text="云硬盘大小(GiB)")
                size_input = size_item.locator("input").first
                size_input.fill(str(volume_size))

        # 规格选择
        self._select_flavor(flavor)

        # 提交创建
        self.get_by_text("立即创建").click()

    def get_popup_message(self, timeout=10):
        """获取当前顶部弹窗文本。

        Args:
            timeout: 最长等待秒数，默认 10。

        Returns:
            str: 弹窗文本，未出现则返回空字符串。
        """
        try:
            self.popup.wait_for(state="visible", timeout=timeout * 1000)
            return self.popup.inner_text().strip()
        except TimeoutError:
            return ""

    @submenu("实例管理")
    def scr_delete(self, name):
        """删除指定名称的 SCR 实例。

        Args:
            name: 实例名称。
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("实例管理")
    def scr_edit_name(self, name, new_name):
        """修改指定 SCR 实例的名称。

        Args:
            name: 当前实例名称。
            new_name: 新的实例名称。
        """
        self.click_action(name, "修改实例名称")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改实例名称")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="实例名称").locator("input").first.fill(new_name)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("实例管理")
    def scr_batch_delete(self, names):
        """批量删除 SCR 实例。

        Args:
            names: 实例名称列表。
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def scr_instance_exists(self, name):
        """判断实例列表中是否存在指定名称的实例。

        Args:
            name: 实例名称。

        Returns:
            bool: 存在返回 True，否则返回 False。
        """
        try:
            self.get_row_by_name(name)
            return True
        except AssertionError:
            return False

    def _select_version(self, version):
        """选择仓库版本。"""
        version_item = self.page.locator(".el-form-item").filter(has_text="版本")
        version_item.locator(".el-select").first.click()
        self._select_option(version)

    def _select_cluster(self, cluster):
        """选择集群。"""
        cluster_item = self.page.locator(".el-form-item").filter(has_text="集群")
        cluster_item.locator(".el-select").first.click()
        self._select_option(cluster)

    def _select_network(self, network):
        """选择专有网络。"""
        network_item = self.page.locator(".el-form-item").filter(has_text="专有网络")
        network_item.locator(".el-select").first.click()
        self._select_option(network)

    def _select_subnet(self, subnet):
        """选择专有网络子网。

        子网选项文本格式为 "name:cidr"，使用子串匹配。
        """
        network_item = self.page.locator(".el-form-item").filter(has_text="专有网络")
        network_item.locator(".el-select").nth(1).click()
        self._select_option(subnet, exact=False)

    def _select_volume_type(self, volume_type):
        """选择云硬盘类型。"""
        volume_item = self.page.locator(".el-form-item").filter(has_text="云硬盘类型")
        volume_item.locator(".el-select").first.click()
        self._select_option(volume_type, exact=False)

    def _select_flavor(self, flavor):
        """在规格表格中选择指定规格。

        通过 CPU/内存列匹配，规格字符串格式如 "4C8G"。

        Args:
            flavor: 规格字符串，如 "4C8G"。
        """
        expected_cpu, expected_mem = self._parse_flavor(flavor)
        self.page.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)

        rows = self.page.locator(".el-table__row").all()
        for row in rows:
            cells = row.locator("td").all()
            cpu_text = ""
            mem_text = ""
            for cell in cells:
                text = cell.text_content() or ""
                if "核" in text and cpu_text == "":
                    cpu_text = text
                elif "GiB" in text and mem_text == "":
                    mem_text = text

            if f"{expected_cpu}核" in cpu_text and f"{expected_mem}GiB" in mem_text:
                row.locator(".el-radio").dispatch_event("click")
                return

        logger.warning(f"未找到规格 {flavor}，使用表格第一项作为兜底")
        rows[0].locator(".el-radio").dispatch_event("click")

    def get_first_node_name(self):
        """获取节点列表中第一个节点的名称。

        Returns:
            str: 节点名称
        """
        rows = self.page.locator(".el-table__body-wrapper:visible .el-table__row")
        rows.first.wait_for(state="visible", timeout=10000)
        if rows.count() == 0:
            raise AssertionError("节点列表为空，无法获取节点名称")
        cells = rows.first.locator("td").all()
        for i, cell in enumerate(cells):
            text = cell.inner_text().strip()
            if text and i > 0:
                return text
        raise AssertionError("无法从节点列表提取名称")

    def scr_node_volume_expand(self, node_name=None, new_size=20):
        """修改节点云硬盘大小（扩容）。

        支持两种调用模式：
        1. 传统模式：传入 node_name，在节点列表中点击操作按钮（兼容旧用法）
        2. 直接模式：不传 node_name，在实例详情页直接操作（先点击"更多操作"展开下拉，再点击"修改云硬盘大小"）

        Args:
            node_name: 节点名称（可选，不传表示在详情页直接操作）
            new_size: 新的云硬盘大小(GiB)
        """
        if node_name:
            self.click_action(node_name, "修改云硬盘大小")
        else:
            # 先尝试直接点击（平铺按钮模式）
            flat_btn = self.get_by_text("修改云硬盘大小")
            clicked = False
            for i in range(flat_btn.count()):
                btn = flat_btn.nth(i)
                if btn.is_visible() and btn.is_enabled():
                    btn.click()
                    clicked = True
                    break
            if not clicked:
                # 平铺按钮未找到，尝试点击"更多操作"展开下拉菜单
                more_btn = self.get_by_role("button", name=re.compile(r"更多操作"))
                if more_btn.count() > 0:
                    more_btn.first.click()
                    self.page.wait_for_timeout(500)
                # 在下拉菜单中点击"修改云硬盘大小"
                dropdown_item = self.page.locator(".cloud-table-dropdown-item").filter(has_text="修改云硬盘大小")
                if dropdown_item.count() > 0:
                    dropdown_item.first.click()
                else:
                    # 兜底：再次尝试直接点击
                    self.get_by_text("修改云硬盘大小").first.click()
        dialog = self.page.locator(".el-dialog").filter(has_text="修改云硬盘大小")
        dialog.wait_for(state="visible", timeout=10000)

        # 尝试多种方式定位云硬盘大小输入框
        size_input = None
        # 策略1：按标签文本匹配（兼容"云硬盘大小"和"云硬盘大小(GiB)"）
        for label_text in ["云硬盘大小", "大小", "GiB"]:
            item = dialog.locator(".el-form-item").filter(has_text=re.compile(re.escape(label_text)))
            if item.count() > 0:
                inp = item.locator("input").first
                if inp.count() > 0:
                    size_input = inp
                    self.logger.info(f"找到云硬盘大小输入框（策略1，标签: {label_text}）")
                    break
        # 策略2：直接在对话框中查找所有 input，取第一个可填写的
        if size_input is None:
            inputs = dialog.locator("input").all()
            for inp in inputs:
                if inp.is_visible():
                    size_input = inp
                    self.logger.info("找到云硬盘大小输入框（策略2：对话框中第一个可见input）")
                    break
        if size_input is None:
            raise AssertionError("在'修改云硬盘大小'对话框中未找到云硬盘大小输入框")
        size_input.fill(str(new_size))
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def scr_namespace_create(self, name):
        """创建命名空间。

        Args:
            name: 命名空间名称
        """
        # 命名空间页面的新建按钮在内容区域，使用 scoped 定位
        content_area = self.page.locator("#cloud-container-content")
        new_btn = content_area.locator("button, .el-button").filter(has_text="新建")
        if new_btn.count() == 0:
            new_btn = content_area.get_by_text("新建")
        new_btn.first.click()
        dialog = self.page.locator(".el-dialog").filter(has_text="新建命名空间")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="名称").locator("input").first.fill(name)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def scr_namespace_delete(self, name):
        """删除命名空间。

        Args:
            name: 命名空间名称
        """
        self.click_action(name, "删除")
        # 部分删除操作无二次确认弹窗，直接等待页面就绪
        try:
            self.dialog_confirm.click()
        except Exception:
            self.logger.info("命名空间删除无确认弹窗，直接等待页面就绪")
        self.wait_for_page_ready()

    def get_volume_size_text(self):
        """获取实例详情页中云硬盘大小的显示文本。

        Returns:
            str: 云硬盘大小文本，未找到返回空字符串。
        """
        # 策略1: 使用 .cloud-item-col 模式（详情页卡片布局）
        volume_locator = self.page.locator(".cloud-item-col").filter(has_text="云硬盘大小")
        if volume_locator.count() > 0:
            text = volume_locator.inner_text()
            match = re.search(r"云硬盘大小\s*[:：]?\s*(\S+)", text)
            if match:
                return match.group(1)

        # 策略2: 使用 .el-form-item 模式（表单布局）
        form_item = self.page.locator(".el-form-item").filter(has_text=re.compile(r"云硬盘大小"))
        if form_item.count() > 0:
            text = form_item.inner_text()
            match = re.search(r"云硬盘大小\s*[:：]?\s*(\S+)", text)
            if match:
                return match.group(1)

        # 策略3: 查找包含 "GiB" 或数字+"GB" 的文本
        all_text = self.page.locator("#cloud-container-content").inner_text()
        match = re.search(r"(\d+\.?\d*\s*GiB|\d+\.?\d*\s*GB)", all_text)
        if match:
            return match.group(1)

        return ""

    def get_public_ip_text(self, timeout=0, refresh_interval=3):
        """获取页面中公网IP的显示文本。

        支持轮询等待模式：当指定 timeout > 0 时，会在超时前持续刷新页面并重试获取，
        用于处理绑定/解绑公网IP后的异步数据刷新场景。

        Args:
            timeout: 轮询等待超时时间（秒），默认0表示只检查一次
            refresh_interval: 每次刷新后等待间隔（秒），默认3秒

        Returns:
            str: 公网IP地址，未绑定返回空字符串或"--"
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
            if timeout <= 0:
                return ip
            if time.time() - start_time >= timeout:
                return ip
            self.wait_for_page_ready()
            self.page.wait_for_timeout(refresh_interval * 1000)

    def scr_public_ip_bind(self, pool=None, ip_address=None):
        """绑定公网IP。

        Args:
            pool: 资源池名称，如 "public_net(基础版)"，用于在对话框中选择资源池
            ip_address: 指定要绑定的IP地址，为 None 时选择第一个可用IP

        Returns:
            str: 绑定的公网IP地址
        """
        self.get_by_text("绑定公网IP").first.click()
        dialog = self.page.locator(".el-dialog").filter(has_text=re.compile(r"^绑定公网IP"))
        dialog.wait_for(state="visible", timeout=10000)

        # 如果有资源池下拉框，先选择资源池
        if pool:
            pool_item = dialog.locator(".el-form-item").filter(has_text="资源池")
            if pool_item.count() > 0:
                pool_dropdown = pool_item.locator(".el-select").first
                pool_dropdown.click()
                self._select_option(pool)
                # 等待表格数据加载，使用轮询而非固定等待
                self.wait_for_page_ready()

        # 等待IP表格出现数据，最多等待10秒
        rows = dialog.locator("tr.el-table__row")
        for _ in range(20):
            if rows.count() > 0:
                break
            self.page.wait_for_timeout(500)

        if rows.count() == 0:
            raise AssertionError("绑定公网IP对话框中没有可用的IP地址，请检查资源池是否有可用IP")

        if ip_address:
            ip_row = dialog.locator("tr.el-table__row").filter(has_text=ip_address).first
            if ip_row.count() == 0:
                # 如果指定IP未找到，尝试选择第一个可用IP（可能是IP状态或显示格式不同）
                self.logger.warning(f"未找到指定的IP地址: {ip_address}，尝试选择第一个可用IP")
                ip_row = rows.first
        else:
            # 优先选择状态为'关闭'（未绑定）的IP
            ip_row = dialog.locator("tr.el-table__row:has-text('关闭')").first
            if ip_row.count() == 0:
                # 如果没有状态为'关闭'的IP，尝试选择第一个可用IP
                ip_row = rows.first

        selected_ip = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()
        return selected_ip.strip()

    def scr_public_ip_unbind(self):
        """解绑公网IP。"""
        self.get_by_text("解绑公网IP").first.click()
        self.page.wait_for_timeout(500)
        dialog = self.page.locator(".el-dialog:visible").filter(has_text=re.compile(r"^解绑公网IP"))
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("实例管理")
    def scr_flavor_change(self, instance_name, target_flavor, check_disabled=None):
        """修改实例规格。

        Args:
            instance_name: 实例名称
            target_flavor: 目标规格，如"8C16G"
            check_disabled: 要检查是否被禁用的规格，如"2C4G"
        """
        self.click_action(instance_name, "修改规格")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改规格")
        dialog.wait_for(state="visible", timeout=10000)

        if check_disabled:
            self._assert_flavor_disabled_in_dialog(dialog, check_disabled)

        self._select_scr_flavor_in_dialog(dialog, target_flavor)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def _select_scr_flavor_in_dialog(self, dialog, flavor):
        """在对话框内的规格表格中选择指定 SCR 规格。

        通过 CPU/内存列匹配，规格字符串格式如 "4C8G"。

        Args:
            dialog: 对话框容器 Locator
            flavor: 规格字符串，如"4C8G"、"8C16G"
        """
        expected_cpu, expected_mem = self._parse_flavor(flavor)
        dialog.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)

        rows = dialog.locator(".el-table__row").all()
        for row in rows:
            cells = row.locator("td").all()
            cpu_text = ""
            mem_text = ""
            for cell in cells:
                text = cell.text_content() or ""
                if "核" in text and cpu_text == "":
                    cpu_text = text
                elif "GiB" in text and mem_text == "":
                    mem_text = text

            if f"{expected_cpu}核" in cpu_text and f"{expected_mem}GiB" in mem_text:
                row.locator(".el-radio").dispatch_event("click")
                return

        logger.warning(f"未找到规格 {flavor}，使用表格第一项作为兜底")
        rows[0].locator(".el-radio").dispatch_event("click")

    def _assert_flavor_disabled_in_dialog(self, dialog, flavor):
        """断言对话框内指定规格选项被禁用。

        Args:
            dialog: 对话框容器 Locator
            flavor: 规格字符串，如"2C4G"

        Raises:
            AssertionError: 规格未被禁用或未找到
        """
        expected_cpu, expected_mem = self._parse_flavor(flavor)
        rows = dialog.locator(".el-table__row").all()
        found = False
        for row in rows:
            cells = row.locator("td").all()
            cpu_text = ""
            mem_text = ""
            for cell in cells:
                text = cell.text_content() or ""
                if "核" in text and cpu_text == "":
                    cpu_text = text
                elif "GiB" in text and mem_text == "":
                    mem_text = text

            if f"{expected_cpu}核" in cpu_text and f"{expected_mem}GiB" in mem_text:
                radio_input = row.locator(".el-radio__input").first
                is_disabled = radio_input.evaluate(
                    "el => el.classList.contains('is-disabled') || el.querySelector('input')?.disabled"
                )
                assert is_disabled, (
                    f"[FieldAssertion] 规格选项 | 禁用状态校验失败 | "
                    f"期望: {flavor} 被禁用 | 实际: 未被禁用"
                )
                found = True
                break

        assert found, f"[FieldAssertion] 规格选项 | 未找到规格 | 期望: {flavor}"
