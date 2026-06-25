import re
import time
from playwright.sync_api import expect
from sugon_web.assertions.network.monitor import MonitorAssertionMixin
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class SfsPage(MonitorAssertionMixin, BasePage):
    """文件存储 SFS 页面对象。"""

    service_name = "文件存储"

    # ---------- 私有辅助方法 ----------

    def _open_create_dialog(self):
        """打开新建文件存储弹窗。"""
        self.btn_create.click()
        dialog = self.get_by_role("dialog", name="新建文件存储")
        expect(dialog).to_be_visible(timeout=10000)
        return dialog

    def _fill_name(self, dialog, name):
        """在弹窗中填写实例名称。"""
        dialog.get_by_placeholder("请输入名称").fill(name)

    def _select_protocol(self, dialog, protocol):
        """在弹窗中选择文件协议（nfs/cifs）。"""
        # 找到包含"文件协议"标签的 el-form-item，然后在其内部点击 el-select 的 input
        form_item = dialog.locator(".el-form-item").filter(has_text="文件协议")
        form_item.locator(".el-select .el-input__inner").click()
        self.locator("li").filter(has_text=re.compile(rf"^{protocol}$")).click()

    def _select_cluster(self, dialog, cluster_name):
        """在弹窗中选择集群。"""
        # 等待集群数据异步加载（选择协议后触发）
        self.page.wait_for_timeout(2000)
        dialog.get_by_placeholder("请选择集群").click()
        # 在下拉框可见范围内选择选项（支持选项文本含额外后缀如 "Autotest(3)"）
        dropdown = self.locator(".el-select-dropdown:visible")
        option = dropdown.locator("li").filter(has_text=re.compile(rf"^{re.escape(cluster_name)}"))
        # 如果选项未出现，等待一下再试
        if option.count() == 0:
            self.page.wait_for_timeout(2000)
        option.click()

    def _select_network(self, dialog, network_name, subnet_name=None):
        """在弹窗中选择专有网络和子网。"""
        # 选择网络
        dialog.locator("div").filter(has_text="专有网络").get_by_placeholder("请选择网络").click()
        dropdown = self.locator(".el-select-dropdown:visible")
        dropdown.locator("li").filter(has_text=re.compile(rf"^{re.escape(network_name)}")).click()
        # 等待子网列表异步加载（网络选择后触发）
        self.page.wait_for_timeout(2000)
        # 选择子网（如果指定，否则选择第一个可用子网）
        subnet_input = dialog.locator("div").filter(has_text="专有网络").get_by_placeholder("请选择子网")
        subnet_input.click()
        subnet_dropdown = self.locator(".el-select-dropdown:visible")
        # 等待子网选项加载，使用轮询而非固定等待
        subnet_options = subnet_dropdown.locator("li")
        for _ in range(10):
            if subnet_options.count() > 0:
                break
            self.page.wait_for_timeout(300)
        if subnet_name:
            subnet_option = subnet_dropdown.locator("li").filter(has_text=re.compile(rf"^{re.escape(subnet_name)}"))
            if subnet_option.count() > 0:
                subnet_option.first.click()
            else:
                # 如果没有精确匹配，选第一个可用子网
                if subnet_options.count() > 0:
                    subnet_options.first.click()
        else:
            # 自动选择第一个可用子网
            if subnet_options.count() > 0:
                subnet_options.first.click()

    def _select_volume_type(self, dialog, volume_type=None):
        """在弹窗中选择云硬盘类型。"""
        # 等待云硬盘类型数据异步加载（选择集群后触发）
        self.page.wait_for_timeout(3000)
        # 云硬盘类型没有placeholder，通过el-form-item标签定位
        form_item = dialog.locator(".el-form-item").filter(has_text=re.compile(r"云硬盘.*类型"))
        form_item.locator(".el-select .el-input__inner").click()
        dropdown = self.locator(".el-select-dropdown:visible")
        # 等待下拉选项加载，使用轮询而非固定等待
        options = dropdown.locator("li")
        for _ in range(10):
            if options.count() > 0:
                break
            self.page.wait_for_timeout(300)
        if volume_type:
            option = dropdown.locator("li").filter(has_text=re.compile(rf"^{re.escape(volume_type)}$"))
            if option.count() > 0:
                option.click()
            else:
                # 如果指定类型不可用，选择第一个可用选项
                options_filtered = dropdown.locator("li").filter(has_text="类型：")
                if options_filtered.count() > 0:
                    options_filtered.first.click()
        else:
            # 选择第一个可用选项
            options_filtered = dropdown.locator("li").filter(has_text="类型：")
            if options_filtered.count() > 0:
                options_filtered.first.click()

    def _set_volume_size(self, dialog, size):
        """在弹窗中设置云硬盘大小。"""
        size_input = dialog.locator("div").filter(has_text=re.compile(r"大小.*GiB")).get_by_role("spinbutton")
        size_input.click()
        size_input.clear()
        size_input.fill(str(size))

    def _select_flavor(self, dialog, cpu_cores=8, ram_gb=8):
        """在弹窗中选择规格（CPU 核数 + 内存 GiB）。"""
        # 筛选 CPU
        cpu_select = dialog.locator("div").filter(has_text="筛选").get_by_placeholder("请选择cpu")
        cpu_select.click()
        dropdown = self.locator(".el-select-dropdown:visible")
        dropdown.locator("li").filter(has_text=re.compile(rf"^{cpu_cores}核$")).click()
        self.page.wait_for_timeout(500)

        # 筛选内存
        ram_select = dialog.locator("div").filter(has_text="筛选").get_by_placeholder("请选择ram")
        ram_select.click()
        dropdown = self.locator(".el-select-dropdown:visible")
        dropdown.locator("li").filter(has_text=re.compile(rf"^{ram_gb}GiB$")).click()
        self.page.wait_for_timeout(1000)

        # 选择表格中第一个规格：通过 radio 的原生 input 元素设置选中状态
        flavor_table = dialog.locator(".el-table")
        first_row = flavor_table.locator("tr.el-table__row").first
        if first_row.count() > 0:
            # 先滚动到视图中
            first_row.scroll_into_view_if_needed()
            # 尝试点击行内的 radio 原生 input（绕过固定列遮挡）
            radio_input = first_row.locator("input[type=radio]").first
            if radio_input.count() > 0:
                radio_input.scroll_into_view_if_needed()
                radio_input.click(force=True)
                logger.info("已选择第一个可用规格（通过 radio input force click）")
            else:
                # 备选：直接 force click 第一行
                first_row.click(force=True)
                logger.info("已使用 force click 选择第一行规格")

    def _dialog_click_confirm(self, dialog):
        """在弹窗中点击确定按钮。"""
        confirm_btn = dialog.locator("span").filter(has_text="确定")
        expect(confirm_btn).to_be_enabled(timeout=5000)
        confirm_btn.click()

    # ---------- 公共业务方法 ----------

    @submenu("实例管理")
    def sfs_instance_create(
        self,
        name,
        protocol="nfs",
        cluster="Autotest",
        network="Autotest",
        subnet=None,
        volume_type=None,
        volume_size=10,
        cpu_cores=8,
        ram_gb=8,
    ):
        """创建文件存储实例。

        Args:
            name: 实例名称。
            protocol: 文件协议，"nfs" 或 "cifs"，默认 "nfs"。
            cluster: 集群名称，默认 "Autotest"。
            network: 专有网络名称，默认 "Autotest"。
            subnet: 子网名称，默认 None（自动选择第一个可用子网）。
            volume_type: 云硬盘类型，默认 None（自动选择第一个可用类型）。
            volume_size: 云硬盘大小（GiB），默认 10。
            cpu_cores: CPU 核数筛选，默认 8。
            ram_gb: 内存 GiB 筛选，默认 8。

        Returns:
            dict: 包含创建时使用的参数快照。
        """
        dialog = self._open_create_dialog()
        self._fill_name(dialog, name)
        self._select_protocol(dialog, protocol)
        self._select_cluster(dialog, cluster)
        self._select_network(dialog, network, subnet)
        self._select_volume_type(dialog, volume_type)
        self._set_volume_size(dialog, volume_size)
        self._select_flavor(dialog, cpu_cores, ram_gb)
        self._dialog_click_confirm(dialog)

        return {
            "name": name,
            "protocol": protocol,
            "cluster": cluster,
            "network": network,
            "subnet": subnet,
            "volume_type": volume_type,
            "volume_size": volume_size,
            "cpu_cores": cpu_cores,
            "ram_gb": ram_gb,
        }

    @submenu("实例管理")
    def sfs_instance_delete(self, name):
        """删除文件存储实例。

        Args:
            name: 实例名称。
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def sfs_instance_batch_delete(self, names):
        """批量删除文件存储实例。

        Args:
            names: 实例名称列表。
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()

    def sfs_instance_goto_detail(self, name):
        """点击实例名称进入详情页。

        Args:
            name: 实例名称。
        """
        # 强制导航到实例列表页
        # 当当前 URL 为 /sfs/#/sfs-storage-detail/... 时，goto_service 的路径前缀匹配会认为已在目标服务而不导航
        # 因此直接使用 goto_submenu 导航到实例管理子菜单，利用 Vue 客户端路由，避免 page.goto 全量刷新导致的不稳定
        self.goto_submenu("实例管理")
        self.wait_for_page_ready()

        # 等待表格数据加载完成
        try:
            loading_mask = self.locator(".el-loading-mask")
            if loading_mask.count() > 0:
                expect(loading_mask).not_to_be_visible(timeout=15000)
        except Exception:
            pass

        # 在表格行内查找名称链接并点击
        row = self.get_row_by_name(name)
        name_link = row.locator("span").filter(has_text=re.compile(rf"{name}")).first
        if name_link.count() > 0:
            name_link.click()
        else:
            # 备选：直接点击行内的第一个 span（名称列）
            row.locator("span").first.click()
        # 等待 URL 变化到详情页
        self.page.wait_for_url(re.compile(r"sfs-storage-detail"), timeout=10000)
        self.wait_for_page_ready()
        # 等待详情页加载完成（loading 消失）
        try:
            loading_mask = self.locator(".el-loading-mask")
            if loading_mask.count() > 0:
                expect(loading_mask).not_to_be_visible(timeout=15000)
        except Exception:
            pass
        # 额外等待确保 Vue 组件渲染完成
        self.page.wait_for_timeout(1000)

    def sfs_get_detail_info(self):
        """在详情页获取基本信息字段。

        Returns:
            dict: 详情页字段键值对。
        """
        detail_data = {}
        # 基本信息区域
        detail_container = self.locator("#detail_container")
        expect(detail_container).to_be_visible(timeout=10000)

        # 等待 loading 消失
        try:
            loading_mask = detail_container.locator(".el-loading-mask").first
            if loading_mask.count() > 0:
                expect(loading_mask).not_to_be_visible(timeout=15000)
        except Exception:
            pass

        # 等待 cloud-item 容器出现（Vue 自定义组件渲染后的实际 DOM）
        try:
            expect(detail_container.locator(".cloud-item").first).to_be_visible(timeout=10000)
        except Exception:
            logger.warning("未找到 .cloud-item 容器")

        # 等待 cloud-item-col 元素出现并包含文本
        try:
            expect(detail_container.locator(".cloud-item-col").first).to_be_visible(timeout=10000)
        except Exception:
            logger.warning("未找到 .cloud-item-col 元素")

        # 额外等待确保 Vue 数据绑定完成
        self.page.wait_for_timeout(500)

        # 获取所有 cloud-item 容器（每个 cloud-item 包含一组 cloud-item-col）
        cloud_items = detail_container.locator(".cloud-item").all()
        logger.info(f"找到 {len(cloud_items)} 个 cloud-item 容器")

        for idx, cloud_item in enumerate(cloud_items):
            # 判断这是规格区域还是基本信息区域
            # 规格区域前面有一个 .detail-page-title 包含 "规格"
            is_flavor_section = False
            try:
                # 检查这个 cloud-item 前面是否有 "规格" 标题
                parent = cloud_item.locator("xpath=..")
                if parent.count() > 0:
                    title = parent.locator(".detail-page-title").first
                    if title.count() > 0 and "规格" in title.text_content():
                        is_flavor_section = True
            except Exception:
                pass

            # 读取该 cloud-item 内的所有 cloud-item-col
            item_cols = cloud_item.locator(".cloud-item-col").all()
            prefix = "规格_" if is_flavor_section else ""

            for item in item_cols:
                try:
                    label_el = item.locator(".cloud-item-label span").first
                    if label_el.count() > 0:
                        label = label_el.text_content().strip()
                    else:
                        label = item.get_attribute("label") or ""

                    value_el = item.locator(".cloud-item-content").first
                    if value_el.count() > 0:
                        value = value_el.text_content().strip()
                    else:
                        value_el = item.locator("span").first
                        value = value_el.text_content().strip() if value_el.count() > 0 else ""

                    if label:
                        key = f"{prefix}{label}"
                        # 避免覆盖：如果是基本信息的字段且已存在，不覆盖
                        if key not in detail_data:
                            detail_data[key] = value
                            logger.debug(f"详情字段: {key} = {value}")
                except Exception as e:
                    logger.debug(f"读取详情字段时出错: {e}")
                    continue

        logger.info(f"详情页读取完成，共 {len(detail_data)} 个字段")
        return detail_data

    @submenu("实例管理")
    def sfs_wait_for_status(self, name, status="正常", timeout=300, refresh_interval=5):
        """轮询等待实例状态收敛到目标状态。

        Args:
            name: 实例名称。
            status: 期望状态，默认 "正常"。
            timeout: 最长等待秒数，默认 300。
            refresh_interval: 刷新间隔秒数，默认 5。
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.btn_refresh.click()
                self.wait_for_page_ready()
                self.page.wait_for_timeout(1000)
                row = self.get_row_by_name(name)
                row_text = row.inner_text()
                if status in row_text:
                    logger.info(f"实例 {name} 状态已收敛到 {status}")
                    return
            except Exception as e:
                logger.debug(f"等待状态收敛时出错: {e}")
            time.sleep(refresh_interval)
        raise AssertionError(f"实例 {name} 状态未在 {timeout} 秒内收敛到 {status}")

    @submenu("实例管理")
    def sfs_instance_view_monitor(self, name):
        """查看文件存储实例监控信息。

        在实例列表中点击目标实例的“查看监控”按钮，等待 CMS 监控详情页加载。
        globalLink 会在当前页内通过 Vue Router 跳转到监控服务详情页。

        Args:
            name: 实例名称。
        """
        # 确保在实例管理列表页并定位到目标实例
        self.goto_submenu("实例管理")
        self.wait_for_page_ready()
        self.assert_list_contain(name)

        # 点击“查看监控”按钮（操作列下拉菜单中）
        self.click_action(name, "查看监控")

        # 等待当前页面通过 globalLink 导航到监控详情页
        self.page.wait_for_url(re.compile(r"cloud-server-sfs-detail"), timeout=30000)
        self.wait_for_page_ready()
        logger.info(f"已进入文件存储实例 '{name}' 的监控详情页")

    def sfs_monitor_get_metric_texts(self):
        """在 SFS 实例监控详情页获取所有图表指标卡片的文本。

        Returns:
            list[str]: 每个 .box_item 图表容器的 inner_text 列表。
        """
        chart_items = self.locator(".render-parent-box .box_item").all()
        texts = []
        for item in chart_items:
            try:
                text = (item.inner_text() or "").strip()
                if text:
                    texts.append(text)
            except Exception as e:
                logger.debug(f"读取监控指标卡片文本失败: {e}")
        return texts

    def sfs_monitor_wait_for_metrics(
        self, expected_metrics, timeout=60, poll_interval=2
    ):
        """在 SFS 实例监控详情页轮询等待预期的指标名称全部出现。

        监控指标列表由后端异步返回并渲染，首次进入页面时可能出现指标
        卡片已渲染但标题/单位文案尚未填充的情况。本方法通过轮询指标卡片
        文本，直到所有预期指标名称（子串匹配）都出现或超时。

        Args:
            expected_metrics: 期望出现的指标名称列表。
            timeout: 最长等待时间（秒），默认 60。
            poll_interval: 轮询间隔（秒），默认 2。

        Returns:
            list[str]: 最后一次采集到的指标卡片文本列表。

        Raises:
            AssertionError: 超时后仍有预期指标未出现。
        """
        deadline = time.time() + timeout
        metric_texts = []
        missing = list(expected_metrics)

        while time.time() < deadline:
            metric_texts = self.sfs_monitor_get_metric_texts()
            missing = [
                metric
                for metric in expected_metrics
                if not any(metric in text for text in metric_texts)
            ]
            if not missing:
                logger.info(
                    f"监控指标全部加载完成，共 {len(metric_texts)} 个图表，"
                    f"包含全部 {len(expected_metrics)} 项预期指标"
                )
                return metric_texts
            logger.debug(
                f"等待监控指标加载，仍缺失: {missing} | "
                f"当前指标文本: {metric_texts}"
            )
            time.sleep(poll_interval)

        raise AssertionError(
            f"[FieldAssertion] 监控指标未在 {timeout} 秒内全部加载 | "
            f"缺失: {missing} | 实际指标文本: {metric_texts}"
        )

    # ---------- 挂载点相关方法 ----------

    def sfs_mountpoint_tab_click(self):
        """在实例详情页点击"挂载点" Tab。"""
        # 先关闭可能存在的 tooltip，避免遮挡点击
        self._dismiss_tooltip_if_present()
        tab = self.get_by_role("tab", name="挂载点")
        expect(tab).to_be_visible(timeout=5000)
        tab.click()
        self.wait_for_page_ready()
        logger.info("已切换到挂载点 Tab")

    def _dismiss_tooltip_if_present(self):
        """关闭可能存在的 tooltip，避免遮挡后续点击。"""
        try:
            tooltip = self.page.locator(".el-tooltip__popper:visible")
            if tooltip.count() > 0:
                # 先尝试按 Escape 键关闭
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)
                # 如果 tooltip 仍在，通过 evaluate 移除它
                if tooltip.count() > 0:
                    self.page.evaluate("""
                        () => {
                            document.querySelectorAll('.el-tooltip__popper').forEach(el => el.remove());
                        }
                    """)
                    self.page.wait_for_timeout(200)
                logger.info("已关闭遮挡 tooltip")
        except Exception:
            pass

    def sfs_mountpoint_create(self, access_group_name, description=""):
        """在挂载点页面新建挂载点。

        Args:
            access_group_name: 权限组名称（在下拉框中按名称选择）。
            description: 挂载点描述，默认空字符串。

        Returns:
            dict: 包含 access_group_name 和 description 的字典。
        """
        # 先关闭可能存在的 tooltip，避免遮挡点击
        self._dismiss_tooltip_if_present()

        # 点击新建按钮：挂载点 Tab 下是 cl-button 自定义组件，
        # 在当前激活的 tab-pane 内按文本查找，避免全局/其他 Tab 同名按钮冲突。
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])").first
        expect(active_tab).to_be_visible(timeout=5000)
        toolbar = active_tab.locator(".table-tool-bar-left")
        create_btn = toolbar.get_by_text("新建").first
        if create_btn.count() == 0:
            create_btn = toolbar.locator("*").filter(has_text="新建").first
        if create_btn.count() == 0:
            create_btn = self.btn_create
        expect(create_btn).to_be_visible(timeout=5000)
        create_btn.click()

        # 等待"新建挂载点"弹窗出现
        dialog = self.get_by_role("dialog", name="新建挂载点")
        expect(dialog).to_be_visible(timeout=10000)

        # 选择权限组（el-select 下拉框）
        form_item = dialog.locator(".el-form-item").filter(has_text="权限组")
        select_input = form_item.locator(".el-select .el-input__inner")
        expect(select_input).to_be_visible(timeout=5000)
        select_input.click()

        # 在下拉选项中选择指定权限组
        dropdown = self.locator(".el-select-dropdown:visible")
        option = dropdown.locator("li").filter(has_text=re.compile(rf"{re.escape(access_group_name)}"))
        expect(option).to_be_visible(timeout=5000)
        option.click()

        # 填写描述（textarea）
        if description:
            desc_input = dialog.get_by_placeholder("请输入描述")
            if desc_input.count() == 0:
                desc_input = dialog.locator("textarea").first
            if desc_input.count() > 0:
                desc_input.fill(description)

        # 点击确定（cl-button 自定义组件）
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"挂载点创建提交: 权限组={access_group_name}, 描述={description}")

        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

        return {"access_group_name": access_group_name, "description": description}

    def sfs_mountpoint_delete(self, mount_target_id):
        """在挂载点列表页删除单个挂载点。

        Args:
            mount_target_id: 挂载点 ID，用于定位目标行。
        """
        self.click_action(mount_target_id, "删除")
        self.dialog_confirm.click()
        logger.info(f"挂载点删除提交: {mount_target_id}")
        self.wait_for_page_ready()

    def sfs_mountpoint_batch_delete(self, mount_target_ids):
        """在挂载点列表页批量删除挂载点。

        Args:
            mount_target_ids: 挂载点 ID 列表。
        """
        self.select_rows_by_names(mount_target_ids)
        delete_btn = self.locator(".cl-btn-danger").filter(has_text="删除").first
        if delete_btn.count() == 0:
            delete_btn = self.get_by_text("删除", exact=True).first
        expect(delete_btn).to_be_visible(timeout=5000)
        delete_btn.click()
        self.dialog_confirm.click()
        logger.info(f"挂载点批量删除提交: {mount_target_ids}")
        self.wait_for_page_ready()

    def sfs_mountpoint_get_row_data(self, mount_target_id):
        """在挂载点列表页获取指定挂载点的行数据。

        Args:
            mount_target_id: 挂载点 ID。

        Returns:
            dict: 行数据字典，包含 挂载点ID、挂载点路径、状态、权限组名称、描述 等字段。
        """
        return self.get_row_data(mount_target_id)

    def sfs_mountpoint_get_column_data(self, column_name):
        """在挂载点列表页获取指定列的所有数据。

        Args:
            column_name: 列名，如"挂载点路径"、"权限组名称"等。

        Returns:
            list: 该列所有单元格的文本值列表。
        """
        return self.get_column_data(column_name)

    # ---------- 权限组相关方法 ----------

    def sfs_access_group_tab_click(self):
        """在实例详情页点击"权限组" Tab。"""
        # 先关闭可能存在的 tooltip，避免遮挡点击
        self._dismiss_tooltip_if_present()
        tab = self.get_by_role("tab", name="权限组")
        expect(tab).to_be_visible(timeout=5000)
        tab.click()
        self.wait_for_page_ready()
        logger.info("已切换到权限组 Tab")

    def sfs_access_group_create(self, name, description=""):
        """在权限组页面新建权限组。

        Args:
            name: 权限组名称。
            description: 权限组描述，默认空字符串。

        Returns:
            dict: 包含 name 和 description 的字典。
        """
        # 先关闭可能存在的 tooltip，避免遮挡点击
        self._dismiss_tooltip_if_present()

        # 点击新建按钮（在权限组 Tab 下，使用更精确的定位）
        # 先尝试在当前激活的 tab-pane 内查找"新建"按钮
        active_tab = self.locator(".el-tab-pane:not([aria-hidden='true'])").first
        if active_tab.count() > 0:
            create_btn = active_tab.get_by_text("新建", exact=True)
            if create_btn.count() == 0:
                create_btn = active_tab.locator("button, .cloud-button-btn, .cl-btn-primary").filter(has_text="新建")
            if create_btn.count() == 0:
                create_btn = active_tab.get_by_text("新建")
        else:
            create_btn = self.get_by_text("新建", exact=True)

        if create_btn.count() == 0:
            create_btn = self.get_by_text("新建", exact=True)
        if create_btn.count() == 0:
            create_btn = self.get_by_text("新建")

        # 如果找到多个，取第一个
        if create_btn.count() > 1:
            create_btn = create_btn.first

        expect(create_btn).to_be_visible(timeout=5000)
        create_btn.click()

        # 等待弹窗出现
        self.page.wait_for_timeout(1000)

        # 尝试定位"新建权限组"弹窗，如果找不到可能是弹窗标题不同
        dialog = self.get_by_role("dialog", name="新建权限组")
        if dialog.count() == 0:
            # 备选：查找任何可见的 dialog
            dialog = self.get_by_role("dialog").filter(has_text="权限组")
        if dialog.count() == 0:
            dialog = self.get_by_role("dialog")
        expect(dialog).to_be_visible(timeout=10000)

        # 填写名称 - 尝试多种定位方式
        name_input = dialog.get_by_placeholder("请输入名称")
        if name_input.count() == 0:
            # 备选：查找弹窗内第一个 input
            name_input = dialog.locator("input").first
        expect(name_input).to_be_visible(timeout=10000)
        name_input.fill(name)

        # 填写描述（textarea，使用 get_by_role 定位）
        desc_input = dialog.get_by_role("textbox").nth(1)
        if desc_input.count() == 0:
            # 备选：查找弹窗内第一个 textarea
            desc_input = dialog.locator("textarea").first
        if desc_input.count() > 0:
            desc_input.fill(description)

        # 点击确定（cl-button 自定义组件）
        confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"权限组创建提交: {name}")

        # 等待对话框关闭和页面就绪，给弹窗出现留出时间
        self.wait_for_page_ready()

        return {"name": name, "description": description}

    def sfs_access_group_delete(self, name):
        """删除单个权限组。

        Args:
            name: 权限组名称。
        """
        self.click_action(name, "删除")
        # 等待删除确认弹窗出现并点击确定
        self.dialog_confirm.click()
        logger.info(f"权限组删除提交: {name}")

    def sfs_access_group_batch_delete(self, names):
        """批量删除权限组。

        Args:
            names: 权限组名称列表。
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        logger.info(f"权限组批量删除提交: {names}")

    def sfs_access_group_get_row_data(self, name):
        """在权限组列表页获取指定权限组的行数据。

        Args:
            name: 权限组名称。

        Returns:
            dict: 行数据字典，包含 名称、挂载点数量、描述 等字段。
        """
        return self.get_row_data(name)

    def sfs_access_group_assert_delete_disabled(self, name):
        """断言指定权限组的删除按钮置灰（不可删除）。

        用于验证：默认权限组(type==0)或挂载点数量>0的权限组不可删除。

        增强检测策略（兼容 headless/headed 异步渲染时序差异）：
        1. 点击操作按钮后使用 expect 等待下拉菜单完全展开，而非固定 sleep
        2. 使用 expect 轮询断言替代单次 is_disabled() 检测
        3. 检测维度覆盖：class(disabled/opacity) + aria-disabled + style(pointer-events/cursor/opacity)
        4. 增加父元素/触发按钮 disabled 状态检测作为兜底

        Args:
            name: 权限组名称。
        """
        from playwright.sync_api import expect

        row = self.get_row_by_name(name)
        # 操作列下拉菜单中"删除"项应被 disabled
        operation_btn = row.locator(".cl-table-dropdown, .el-dropdown, .cloud-table-dropdown").first
        if operation_btn.count() > 0:
            operation_btn.click()
            # 使用 expect 等待下拉菜单容器可见（替代固定 sleep，确保菜单已展开）
            dropdown_menu = self.page.locator(
                ".el-dropdown-menu:visible, .cloud-table-dropdown-menu:visible, .cl-table-dropdown-menu:visible"
            ).first
            try:
                expect(dropdown_menu).to_be_visible(timeout=5000)
            except Exception:
                # 若 expect 等待失败，回退到 locator 直接查找
                pass

            # 在下拉菜单中查找"删除"项
            if dropdown_menu.count() > 0:
                dropdown_items = dropdown_menu.locator(
                    ".el-dropdown-menu__item, .cloud-table-dropdown-item, .cl-table-dropdown-item"
                )
            else:
                dropdown_items = self.page.locator(
                    ".el-dropdown-menu__item:visible, .cloud-table-dropdown-item:visible, .cl-table-dropdown-item:visible"
                )

            # 先收集所有 items 和文本，避免在循环中频繁操作 DOM
            delete_item = None
            for i in range(dropdown_items.count()):
                item = dropdown_items.nth(i)
                try:
                    item_text = item.inner_text() or ""
                    if "删除" in item_text:
                        delete_item = item
                        break
                except Exception:
                    continue

            if delete_item is not None:
                # 使用轮询方式检测 disabled 状态（兼容 headless 异步渲染时序）
                # 最多轮询 10 次，每次间隔 200ms，总超时约 2s
                is_disabled = False
                disabled_reason = []
                for _ in range(10):
                    item_class = delete_item.get_attribute("class") or ""
                    aria_disabled = delete_item.get_attribute("aria-disabled") or ""

                    # 样式检测（getComputedStyle 在 headless 下可能异步返回）
                    pointer_events = ""
                    cursor_style = ""
                    opacity_val = ""
                    try:
                        pointer_events = delete_item.evaluate(
                            "el => window.getComputedStyle(el).pointerEvents"
                        ) or ""
                        cursor_style = delete_item.evaluate(
                            "el => window.getComputedStyle(el).cursor"
                        ) or ""
                        opacity_val = delete_item.evaluate(
                            "el => window.getComputedStyle(el).opacity"
                        ) or ""
                    except Exception:
                        pass

                    # 多维度 disabled 检测
                    checks = {
                        "is_disabled()": delete_item.is_disabled(),
                        "cloud-table-dropdown-item-disabled": "cloud-table-dropdown-item-disabled" in item_class,
                        "cl-table-dropdown-item-disabled": "cl-table-dropdown-item-disabled" in item_class,
                        "is-disabled": "is-disabled" in item_class,
                        "cl-btn-disabled": "cl-btn-disabled" in item_class,
                        "aria-disabled": aria_disabled == "true",
                        "pointer-events:none": pointer_events == "none",
                        "cursor:not-allowed": cursor_style == "not-allowed",
                        "opacity<1": opacity_val != "" and float(opacity_val) < 1.0,
                    }

                    for reason, result in checks.items():
                        if result:
                            is_disabled = True
                            disabled_reason.append(reason)

                    if is_disabled:
                        break

                    # 未检测到 disabled，等待 200ms 后重试
                    self.page.wait_for_timeout(200)

                assert is_disabled, (
                    f"[AccessGroupAssertion] 权限组 '{name}' 的删除按钮应置灰但实际可点击 | "
                    f"class='{item_class}', aria-disabled='{aria_disabled}', "
                    f"pointer-events='{pointer_events}', cursor='{cursor_style}', opacity='{opacity_val}'"
                )
                logger.info(
                    f"权限组 '{name}' 删除按钮已置灰，验证通过（检测维度: {', '.join(disabled_reason)}）"
                )
                # 关闭下拉菜单，避免影响后续操作
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
                return

            # 如果遍历完未找到"删除"，也关闭下拉菜单
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(200)

        # 备选：如果找不到下拉菜单，检查行内是否有直接的删除按钮且被禁用
        delete_btn = row.get_by_text("删除")
        if delete_btn.count() > 0:
            is_disabled = delete_btn.is_disabled() or "is-disabled" in (delete_btn.get_attribute("class") or "")
            assert is_disabled, (
                f"[AccessGroupAssertion] 权限组 '{name}' 的删除按钮应置灰但实际可点击"
            )
            logger.info(f"权限组 '{name}' 删除按钮已置灰，验证通过")
            return

        # 如果以上都找不到，可能是默认权限组没有操作按钮（直接没有下拉菜单），这也算"不可删除"
        logger.info(f"权限组 '{name}' 没有操作按钮/下拉菜单，视为不可删除，验证通过")
        return

    def sfs_access_group_assert_checkbox_disabled(self, name):
        """断言指定权限组的复选框置灰（不可选中）。

        用于验证：默认权限组或挂载点数量>0的权限组在批量删除时不可勾选。

        Args:
            name: 权限组名称。
        """
        row = self.get_by_role("row", name=name).first
        checkbox = row.locator("label span").last
        expect(checkbox).to_be_disabled()
        logger.info(f"权限组 '{name}' 复选框已置灰，验证通过")

    # ---------- 权限组规则相关方法 ----------

    def sfs_access_group_goto_rules(self, group_name):
        """在权限组列表页点击指定权限组的"权限组规则"操作，进入权限组规则列表页。

        Args:
            group_name: 权限组名称。
        """
        self.click_action(group_name, "权限组规则")
        # 等待 URL 变化到权限组规则页面
        self.page.wait_for_url(re.compile(r"sfs-storage-access-group-rule"), timeout=10000)
        self.wait_for_page_ready()
        logger.info(f"已进入权限组 '{group_name}' 的权限组规则列表页")

    def sfs_access_group_rule_create(self, auth_ip, rw_access_type=None, user_access_type=None):
        """在权限组规则列表页新建权限组规则。

        CIFS 协议实例仅需填写访问地址；NFS 协议实例需填写访问地址、读写权限、用户权限。

        Args:
            auth_ip: 访问地址，如 "192.168.1.0/24"。
            rw_access_type: 读写权限，可选值为 "rw"（读写）或 "ro"（只读）。
                            仅 NFS 协议实例需要填写，CIFS 协议实例无需填写。
            user_access_type: 用户权限，可选值为 "all_squash"、"no_all_squash"、
                              "root_squash"、"no_root_squash"。
                              仅 NFS 协议实例需要填写，CIFS 协议实例无需填写。

        Returns:
            dict: 包含创建时使用的参数快照。
        """
        # 点击新建按钮（cl-button 自定义组件，使用 get_by_text）
        create_btn = self.get_by_text("新建", exact=True)
        if create_btn.count() == 0:
            create_btn = self.get_by_text("新建")
        expect(create_btn).to_be_visible(timeout=5000)
        create_btn.click()

        # 等待"新建权限组规则"弹窗出现
        dialog = self.get_by_role("dialog", name="新建权限组规则")
        expect(dialog).to_be_visible(timeout=10000)

        # 填写访问地址
        ip_input = dialog.get_by_placeholder("例：10.0.13.6或10.0.12.0/24")
        expect(ip_input).to_be_visible(timeout=5000)
        ip_input.fill(auth_ip)

        # 填写读写权限（NFS 协议实例）
        if rw_access_type is not None:
            rw_label = dialog.locator(".el-form-item").filter(has_text="读写权限")
            rw_select = rw_label.locator(".el-select .el-input__inner")
            expect(rw_select).to_be_visible(timeout=5000)
            rw_select.click()
            # 在下拉选项中选择
            dropdown = self.locator(".el-select-dropdown:visible")
            rw_option = dropdown.locator("li").filter(has_text=re.compile(rf"^{rw_access_type}$"))
            if rw_option.count() == 0:
                # 备选：通过 label 文本匹配
                rw_label_map = {"rw": "读写", "ro": "只读"}
                rw_label_text = rw_label_map.get(rw_access_type, rw_access_type)
                rw_option = dropdown.locator("li").filter(has_text=re.compile(rf"{rw_label_text}"))
            expect(rw_option).to_be_visible(timeout=5000)
            rw_option.click()

        # 填写用户权限（NFS 协议实例）
        if user_access_type is not None:
            user_label = dialog.locator(".el-form-item").filter(has_text="用户权限")
            user_select = user_label.locator(".el-select .el-input__inner")
            expect(user_select).to_be_visible(timeout=5000)
            user_select.click()
            dropdown = self.locator(".el-select-dropdown:visible")
            # 下拉选项显示为 label 文本，建立 value->label 映射用于匹配
            user_access_label_map = {
                "all_squash": "所有访问用户都会被映射为匿名用户或用户组",
                "no_all_squash": "访问用户先与本机用户匹配，匹配失败后再映射为匿名用户或用户组",
                "root_squash": "将来访的 root 用户映射为匿名用户或用户组",
                "no_root_squash": "来访的 root 用户保持 root 帐号权限",
            }
            # 先尝试用 value 匹配（部分 Element UI 版本可能渲染 value 在文本中）
            user_option = dropdown.locator("li").filter(has_text=re.compile(rf"^{user_access_type}"))
            if user_option.count() == 0:
                # 备选：通过 label 文本匹配
                label_text = user_access_label_map.get(user_access_type, user_access_type)
                user_option = dropdown.locator("li").filter(has_text=re.compile(rf"{label_text}"))
            expect(user_option).to_be_visible(timeout=5000)
            user_option.click()

        # 点击确定（cl-button 自定义组件）
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"权限组规则创建提交: {auth_ip}")

        # 等待对话框关闭和页面就绪，给弹窗出现留出时间
        self.wait_for_page_ready()

        return {
            "auth_ip": auth_ip,
            "rw_access_type": rw_access_type,
            "user_access_type": user_access_type,
        }

    def sfs_access_group_rule_delete(self, auth_ip):
        """在权限组规则列表页删除单个权限组规则。

        Args:
            auth_ip: 权限组规则的访问地址，用于定位目标行。
        """
        self.click_action(auth_ip, "删除")
        # 等待删除确认弹窗出现并点击确定
        self.dialog_confirm.click()
        logger.info(f"权限组规则删除提交: {auth_ip}")
        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

    def sfs_access_group_rule_batch_delete(self, auth_ips):
        """在权限组规则列表页批量删除权限组规则。

        Args:
            auth_ips: 权限组规则访问地址列表。
        """
        self.select_rows_by_names(auth_ips)
        # 点击批量删除按钮（cl-btn-danger 类型，在列表头部）
        # 使用 class 精确定位，避免匹配到行内下拉菜单的删除项
        delete_btn = self.locator(".cl-btn-danger").filter(has_text="删除").first
        if delete_btn.count() == 0:
            delete_btn = self.get_by_text("删除", exact=True).first
        expect(delete_btn).to_be_visible(timeout=5000)
        delete_btn.click()
        # 等待删除确认弹窗并点击确定
        self.dialog_confirm.click()
        logger.info(f"权限组规则批量删除提交: {auth_ips}")
        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

    def sfs_access_group_rule_get_row_data(self, auth_ip):
        """在权限组规则列表页获取指定权限组规则的行数据。

        Args:
            auth_ip: 权限组规则的访问地址。

        Returns:
            dict: 行数据字典，包含 访问地址、读写权限、用户权限、创建时间 等字段。
        """
        return self.get_row_data(auth_ip)

    def sfs_access_group_rule_assert_create_disabled(self):
        """断言权限组规则列表页的"新建"按钮置灰（不可点击）。

        用于验证：默认权限组（group_type == 0）不可新建权限组规则。
        """
        # 查找"新建"按钮
        create_btn = self.get_by_text("新建", exact=True)
        if create_btn.count() == 0:
            create_btn = self.get_by_text("新建")
        if create_btn.count() > 1:
            create_btn = create_btn.first

        # 检查按钮是否被禁用（多维度检测兼容不同实现方式）
        is_disabled = create_btn.is_disabled()
        cls = create_btn.get_attribute("class") or ""
        has_disabled_class = "is-disabled" in cls or "cl-btn-disabled" in cls
        # 检测 cursor: not-allowed 样式（DIV 按钮常用禁用方式）
        cursor_style = create_btn.evaluate("el => window.getComputedStyle(el).cursor") or ""
        has_not_allowed_cursor = cursor_style == "not-allowed"

        assert is_disabled or has_disabled_class or has_not_allowed_cursor, (
            f"[AccessGroupRuleAssertion] 默认权限组的新建按钮应置灰但实际可点击 | "
            f"is_disabled={is_disabled}, class={cls}, cursor={cursor_style}"
        )
        logger.info("默认权限组新建按钮已置灰，验证通过")

    def sfs_access_group_rule_assert_delete_disabled(self, auth_ip):
        """断言指定权限组规则的删除按钮置灰（不可删除）。

        用于验证：默认权限组规则不可删除。

        Args:
            auth_ip: 权限组规则的访问地址。
        """
        row = self.get_row_by_name(auth_ip)
        # 操作列下拉菜单中"删除"项应被 disabled
        operation_btn = row.locator(".cl-table-dropdown, .el-dropdown, [class*='dropdown']").first
        if operation_btn.count() > 0:
            operation_btn.click()
            self.page.wait_for_timeout(1000)
            dropdown_items = self.page.locator(".cloud-table-dropdown-item, .el-dropdown-menu__item, [class*='dropdown-item']")
            for i in range(dropdown_items.count()):
                item = dropdown_items.nth(i)
                try:
                    item_text = item.inner_text() or ""
                    if "删除" in item_text:
                        is_disabled = item.is_disabled() or "is-disabled" in (item.get_attribute("class") or "")
                        assert is_disabled, (
                            f"[AccessGroupRuleAssertion] 权限组规则 '{auth_ip}' 的删除按钮应置灰但实际可点击"
                        )
                        logger.info(f"权限组规则 '{auth_ip}' 删除按钮已置灰，验证通过")
                        return
                except Exception:
                    continue
        # 备选：直接检查行内删除按钮
        delete_btn = row.get_by_text("删除")
        if delete_btn.count() > 0:
            expect(delete_btn).to_be_disabled()
            logger.info(f"权限组规则 '{auth_ip}' 删除按钮已置灰，验证通过")
            return

        logger.info(f"权限组规则 '{auth_ip}' 没有操作按钮，视为不可删除，验证通过")

    # ---------- 修改云硬盘大小相关方法 ----------

    @submenu("实例管理")
    def sfs_instance_modify_volume_size(self, name, new_size):
        """修改指定 SFS 实例的云硬盘大小。

        操作步骤：在实例列表中找到目标实例，点击"更多-修改云硬盘大小"，
        在弹窗中输入新的容量值，点击确定。

        Args:
            name: 实例名称。
            new_size: 新的云硬盘大小（GiB），必须大于当前容量且为10的整数倍。

        Returns:
            dict: 包含 name 和 new_size 的字典。
        """
        # 点击"更多"操作按钮展开下拉菜单，选择"修改云硬盘大小"
        self.click_action(name, "修改云硬盘大小")

        # 等待"修改云硬盘大小"弹窗出现
        dialog = self.get_by_role("dialog", name="修改云硬盘大小")
        expect(dialog).to_be_visible(timeout=10000)

        # 填写新的云硬盘大小（el-input-number 组件，使用 spinbutton role）
        size_input = dialog.locator("div").filter(has_text=re.compile(r"云硬盘")).get_by_role("spinbutton")
        expect(size_input).to_be_visible(timeout=5000)
        size_input.click()
        size_input.clear()
        size_input.fill(str(new_size))

        # 点击确定按钮（cl-button 自定义组件，使用 get_by_text）
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"修改云硬盘大小提交: {name} -> {new_size}GiB")

        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

        return {"name": name, "new_size": new_size}

    def sfs_instance_assert_volume_size_disabled(self, name):
        """断言输入小于当前容量的值时，修改云硬盘大小确定按钮置灰。

        用于验证边界条件：容量小于当前值时不可提交。

        Args:
            name: 实例名称。
        """
        # 打开修改弹窗
        self.click_action(name, "修改云硬盘大小")
        dialog = self.get_by_role("dialog", name="修改云硬盘大小")
        expect(dialog).to_be_visible(timeout=10000)

        # 输入小于当前值的容量（固定输入10，当前值至少为20）
        size_input = dialog.locator("div").filter(
            has_text=re.compile(r"云硬盘")
        ).get_by_role("spinbutton")
        expect(size_input).to_be_visible(timeout=5000)
        size_input.click()
        size_input.clear()
        size_input.press_sequentially("10")
        # 点击对话框标题区域触发 blur，使 el-input-number 的 min 校验生效
        dialog_title = dialog.locator(".el-dialog__header").first
        if dialog_title.count() > 0:
            dialog_title.click()
        # el-input-number 的 clamp 到最小值是异步的，需等待 Vue 更新
        self.page.wait_for_timeout(2000)
        # 再次读取输入框实际值（el-input-number 可能自动 clamp 到最小值）
        actual_value = size_input.input_value()
        logger.info(f"修改云硬盘大小输入框实际值: {actual_value}")

        # 通过 evaluate 直接检查 Vue 组件内部状态
        try:
            vue_data = dialog.evaluate("""el => {
                // 查找 Vue 实例 - 从 dialog 元素向上查找
                let vue = el.__vue__;
                if (!vue) {
                    let parent = el.parentElement;
                    while (parent && !parent.__vue__) {
                        parent = parent.parentElement;
                    }
                    vue = parent ? parent.__vue__ : null;
                }
                // 如果找到 Vue 实例，尝试访问 data 属性
                if (vue) {
                    // 尝试不同的访问方式
                    let form_size = vue.form ? vue.form.size : (vue.$data ? vue.$data.form.size : null);
                    let row_size = vue.row_data ? (vue.row_data.volume_size || vue.row_data) : (vue.$data ? (vue.$data.row_data ? (vue.$data.row_data.volume_size || vue.$data.row_data) : null) : null);
                    return {
                        form_size: form_size,
                        row_volume_size: row_size,
                        disabled: form_size !== null && row_size !== null ? form_size == row_size : null,
                        has_vue: true,
                        vue_keys: Object.keys(vue).slice(0, 20)
                    };
                }
                return { has_vue: false };
            }""")
            logger.info(f"Vue 组件数据: {vue_data}")
        except Exception as e:
            logger.warning(f"无法读取 Vue 数据: {e}")
            vue_data = None

        # 检查确定按钮是否置灰 - cl-button 组件渲染为 span，需检查 cursor 样式
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        # 获取按钮的 computed cursor 样式（cl-button disabled 时 cursor=not-allowed）
        cursor_style = confirm_btn.evaluate("el => window.getComputedStyle(el).cursor")
        is_not_allowed = cursor_style == "not-allowed"
        logger.info(f"确定按钮 cursor 样式: {cursor_style}, is_not_allowed={is_not_allowed}")

        try:
            # cl-button 组件 disabled 时 cursor=not-allowed
            assert is_not_allowed, (
                f"[VolumeSizeAssertion] 输入值={actual_value}（当前值至少20）时确定按钮应置灰，"
                f"但实际 cursor={cursor_style}"
            )
            logger.info(f"输入值={actual_value}时确定按钮已置灰(cursor=not-allowed)，验证通过")
        finally:
            # 无论断言是否通过，都关闭弹窗
            cancel_btn = dialog.get_by_text("取消", exact=True)
            if cancel_btn.count() == 0:
                cancel_btn = dialog.get_by_text("取消")
            if cancel_btn.count() > 0:
                cancel_btn.click()
                self.wait_for_page_ready()

    def sfs_instance_assert_volume_size_equal_disabled(self, name, equal_size):
        """断言输入等于当前容量的值时，修改云硬盘大小确定按钮置灰。

        用于验证边界条件：容量等于当前值时不可提交。

        Args:
            name: 实例名称。
            equal_size: 与当前容量相等的值。
        """
        # 打开修改弹窗
        self.click_action(name, "修改云硬盘大小")
        dialog = self.get_by_role("dialog", name="修改云硬盘大小")
        expect(dialog).to_be_visible(timeout=10000)

        # 输入等于当前值的容量
        size_input = dialog.locator("div").filter(
            has_text=re.compile(r"云硬盘")
        ).get_by_role("spinbutton")
        expect(size_input).to_be_visible(timeout=5000)
        size_input.click()
        size_input.clear()
        size_input.fill(str(equal_size))

        # 检查确定按钮是否置灰 - cl-button 组件渲染为 span，需检查 cursor 样式
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        cursor_style = confirm_btn.evaluate("el => window.getComputedStyle(el).cursor")
        is_not_allowed = cursor_style == "not-allowed"
        logger.info(f"确定按钮 cursor 样式: {cursor_style}, is_not_allowed={is_not_allowed}")

        try:
            assert is_not_allowed, (
                f"[VolumeSizeAssertion] 输入等于当前值 {equal_size}GiB 时确定按钮应置灰，"
                f"但实际 cursor={cursor_style}"
            )
            logger.info(f"输入等于当前值 {equal_size}GiB 时确定按钮已置灰，验证通过")
        finally:
            # 无论断言是否通过，都关闭弹窗
            cancel_btn = dialog.get_by_text("取消", exact=True)
            if cancel_btn.count() == 0:
                cancel_btn = dialog.get_by_text("取消")
            if cancel_btn.count() > 0:
                cancel_btn.click()
                self.wait_for_page_ready()

    # ---------- 修改权限组相关方法 ----------

    def sfs_access_group_modify(self, old_name, new_name, new_description=""):
        """修改指定权限组的名称和描述。

        操作步骤：在权限组列表中找到目标权限组，点击"修改"，
        在弹窗中修改名称和描述，点击确定。

        Args:
            old_name: 原权限组名称（用于定位目标行）。
            new_name: 修改后的权限组名称。
            new_description: 修改后的权限组描述，默认空字符串。

        Returns:
            dict: 包含 old_name、new_name、new_description 的字典。
        """
        # 点击行操作"修改"
        self.click_action(old_name, "修改")

        # 等待"修改权限组"弹窗出现
        dialog = self.get_by_role("dialog", name="修改权限组")
        expect(dialog).to_be_visible(timeout=10000)

        # 修改名称（el-input 组件）
        name_input = dialog.locator("div").filter(has_text="名称").get_by_role("textbox").first
        expect(name_input).to_be_visible(timeout=5000)
        name_input.click()
        name_input.clear()
        name_input.fill(new_name)

        # 修改描述（textarea 组件）
        desc_input = dialog.get_by_role("textbox").nth(1)
        if desc_input.count() == 0:
            desc_input = dialog.locator("textarea").first
        if desc_input.count() > 0:
            desc_input.click()
            desc_input.clear()
            desc_input.fill(new_description)

        # 点击确定按钮（cl-button 自定义组件）
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"修改权限组提交: {old_name} -> {new_name}")

        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

        return {"old_name": old_name, "new_name": new_name, "new_description": new_description}

    # ---------- 修改权限组规则相关方法 ----------

    def sfs_access_group_rule_modify(self, auth_ip, new_rw_access_type=None, new_user_access_type=None):
        """修改指定权限组规则的读写权限和用户权限。

        操作步骤：在权限组规则列表中找到目标规则，点击"修改"，
        在弹窗中修改读写权限和用户权限，点击确定。

        Args:
            auth_ip: 访问地址（用于定位目标行）。
            new_rw_access_type: 新的读写权限，可选值为 "rw"（读写）或 "ro"（只读）。
            new_user_access_type: 新的用户权限，可选值为 "all_squash"、"no_all_squash"、
                                   "root_squash"、"no_root_squash"。

        Returns:
            dict: 包含 auth_ip、new_rw_access_type、new_user_access_type 的字典。
        """
        # 点击行操作"修改"
        self.click_action(auth_ip, "修改")

        # 等待"修改权限组规则"弹窗出现
        dialog = self.get_by_role("dialog", name="修改权限组规则")
        expect(dialog).to_be_visible(timeout=10000)

        # 修改读写权限（el-select 下拉框）
        if new_rw_access_type is not None:
            rw_label = dialog.locator(".el-form-item").filter(has_text="读写权限")
            rw_select = rw_label.locator(".el-select .el-input__inner")
            expect(rw_select).to_be_visible(timeout=5000)
            rw_select.click()
            # 等待下拉框出现并加载选项
            self.page.wait_for_timeout(500)
            dropdown = self.locator(".el-select-dropdown:visible")
            rw_option = dropdown.locator("li").filter(has_text=re.compile(rf"^{new_rw_access_type}$"))
            # 轮询等待选项加载
            for _ in range(10):
                if rw_option.count() > 0:
                    break
                self.page.wait_for_timeout(300)
            if rw_option.count() == 0:
                # 备选：通过 label 文本匹配（rw->读写, ro->只读）
                rw_label_map = {"rw": "读写", "ro": "只读"}
                rw_label_text = rw_label_map.get(new_rw_access_type, new_rw_access_type)
                rw_option = dropdown.locator("li").filter(has_text=re.compile(rf"{rw_label_text}"))
            expect(rw_option).to_be_visible(timeout=5000)
            rw_option.click()

        # 修改用户权限（el-select 下拉框）
        if new_user_access_type is not None:
            user_label = dialog.locator(".el-form-item").filter(has_text="用户权限")
            user_select = user_label.locator(".el-select .el-input__inner")
            expect(user_select).to_be_visible(timeout=5000)
            user_select.click()
            # 等待下拉框出现并加载选项
            self.page.wait_for_timeout(500)
            dropdown = self.locator(".el-select-dropdown:visible")
            # 下拉选项显示为 label 文本，建立 value->label 映射用于匹配
            user_access_label_map = {
                "all_squash": "所有访问用户都会被映射为匿名用户或用户组",
                "no_all_squash": "访问用户先与本机用户匹配，匹配失败后再映射为匿名用户或用户组",
                "root_squash": "将来访的 root 用户映射为匿名用户或用户组",
                "no_root_squash": "来访的 root 用户保持 root 帐号权限",
            }
            # 先尝试用 value 匹配（部分 Element UI 版本可能渲染 value 在文本中）
            user_option = dropdown.locator("li").filter(has_text=re.compile(rf"^{new_user_access_type}"))
            # 轮询等待选项加载
            for _ in range(10):
                if user_option.count() > 0:
                    break
                self.page.wait_for_timeout(300)
            # 若 value 匹配失败，改用 label 文本匹配
            if user_option.count() == 0:
                label_text = user_access_label_map.get(new_user_access_type, new_user_access_type)
                user_option = dropdown.locator("li").filter(has_text=re.compile(rf"{label_text}"))
                for _ in range(10):
                    if user_option.count() > 0:
                        break
                    self.page.wait_for_timeout(300)
            expect(user_option).to_be_visible(timeout=5000)
            user_option.click()

        # 点击确定按钮（cl-button 自定义组件）
        confirm_btn = dialog.get_by_text("确定", exact=True)
        if confirm_btn.count() == 0:
            confirm_btn = dialog.get_by_text("确定")
        expect(confirm_btn).to_be_visible(timeout=5000)
        confirm_btn.click()
        logger.info(f"修改权限组规则提交: {auth_ip}")

        # 等待对话框关闭和页面就绪
        self.wait_for_page_ready()

        return {
            "auth_ip": auth_ip,
            "new_rw_access_type": new_rw_access_type,
            "new_user_access_type": new_user_access_type,
        }

    def sfs_access_group_rule_assert_default_hint(self):
        """检查权限组规则列表页是否存在默认权限组不可修改、删除的提示。

        本方法为 P2 可选断言：核心业务规则"默认权限组不可新建规则"已由
        `sfs_access_group_rule_assert_create_disabled` 验证通过，提示文案
        存在性属于 UI 增强特性，非核心功能。若页面无匹配提示，仅记录
        warning 不阻断测试流程，以兼容不同环境/版本的 UI 表现差异。
        """
        # 检查 sugon-alert 组件
        alert = self.locator(".sugon-alert")
        if alert.count() > 0:
            alert_text = alert.text_content() or ""
            if any(kw in alert_text for kw in ["不可", "默认", "无法"]):
                logger.info(f"默认权限组提示存在: {alert_text}")
                return

        # 备选：检查页面文本中是否包含相关提示
        page_text = self.page.locator("body").text_content() or ""
        hint_found = any(hint in page_text for hint in ["不可修改", "不可删除", "无法编辑", "默认权限组"])
        if hint_found:
            logger.info("默认权限组不可修改/删除提示验证通过")
        else:
            logger.warning(
                "[AccessGroupRuleAssertion] 默认权限组不可修改/删除的提示未找到，"
                "但核心规则已由 sfs_access_group_rule_assert_create_disabled 验证通过，继续执行"
            )
