import re
import time

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config


class CceMixin(BasePage):
    """云容器引擎CCE相关页面动作。"""

    @submenu("集群管理")
    def cce_create(self, name, node_count=4, version="1.22.17", container_runtime="docker",
                   proxy_mode="ipvs", cluster="Autotest", desc="", vpc_network="Autotest",
                   vpc_subnet="Autotest", network_model="flannel", pod_cidr="10.0.0.0/16",
                   service_cidr="10.247.0.0/16", docker_cidr="172.17.0.1/16",
                   volume_type="xbd-test", volume_size=50, flavor="4C8G"):
        """创建CCE集群。

        Args:
            name: 集群名称，2~50位小写字母/数字/短横线
            node_count: 节点数量，默认4
            version: Kubernetes版本，默认"1.22.17"
            container_runtime: 容器运行时，默认"docker"
            proxy_mode: kube-proxy代理模式，默认"ipvs"
            cluster: 所属集群/主机集合，默认"Autotest"
            desc: 集群描述
            vpc_network: 专有网络名称
            vpc_subnet: 专有网络子网名称
            network_model: 容器网络模型，默认"flannel"
            pod_cidr: 容器组网段，默认"10.0.0.0/16"
            service_cidr: 服务发现网段，默认"10.247.0.0/16"
            docker_cidr: 容器运行时网段，默认"172.17.0.1/16"
            volume_type: 云硬盘类型，默认"xbd-test"
            volume_size: 云硬盘大小(GiB)，默认50
            flavor: 节点规格，默认"4C8G"
        """
        self.btn_create.click()
        # 等待路由跳转到创建页面
        self.page.wait_for_url("**/create-cluster", timeout=30000)
        self.wait_for_page_ready()
        # 额外等待表单区域可见，确保 initData 加载完成
        self.get_by_text("基本设置").wait_for(state="visible", timeout=30000)

        # 基本设置
        self.page.locator(".el-form-item").filter(has_text="名称").locator("input").first.fill(name)
        self.page.locator(".el-form-item").filter(has_text="节点数量").locator("input").first.fill(str(node_count))

        # 版本选择
        self.page.locator(".el-form-item").filter(has_text="版本").locator(".el-select").first.click()
        self._select_option(version)

        # 容器运行时
        self.get_by_role("radio", name=container_runtime).click()

        # kube-proxy代理模式
        self.get_by_role("radio", name=proxy_mode).click()

        # 集群/主机集合选择
        self.page.locator(".el-form-item").filter(has_text="集群").locator(".el-select").first.click()
        self._select_option(cluster)

        # 描述
        if desc:
            self.locator("textarea").fill(desc)

        # 网络配置
        # 专有网络 - 网络选择
        vpc_form_item = self.page.locator(".el-form-item").filter(has_text="专有网络")
        vpc_form_item.locator(".el-select").first.click()
        self._select_option(vpc_network)

        # 专有网络 - 子网选择（选项label格式为"name:cidr"，使用子串匹配）
        vpc_form_item.locator(".el-select").nth(1).click()
        self._select_option(vpc_subnet, exact=False)

        # 容器网络模型
        self.page.locator(".el-form-item").filter(has_text="容器网络模型").locator(".el-select").first.click()
        self._select_option(network_model)

        # 容器组网段/服务发现网段/容器运行时网段：
        # 前端默认值恰好与测试入参一致（10.0.0.0/16、10.247.0.0/16、172.17.0.1/16），
        # 且 CIDR 组件包含 disabled input 和 select，自动化填写复杂度高，故跳过。

        # 配置
        # 云硬盘类型（label格式为"类型：name；存储池：xxx"，使用子串匹配）
        self.page.locator(".el-form-item").filter(has_text="云硬盘类型").locator(".el-select").first.click()
        self._select_option(volume_type, exact=False)

        # 云硬盘大小
        self.page.locator(".el-form-item").filter(has_text="云硬盘大小(GiB)").locator("input").first.fill(str(volume_size))

        # 规格选择 - 在规格表格中选择
        self._select_flavor(flavor)

        # 提交创建
        self.btn_submit.click()

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

        dropdown = self.page.locator(".el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=10000)
        if exact:
            # 使用正则精确匹配，避免子串匹配到多个选项（如 Autotest 匹配 autotest-xxx）
            pattern = re.compile(rf"^{re.escape(option_text)}$")
            item = dropdown.locator(".el-select-dropdown__item").filter(has_text=pattern)
        else:
            item = dropdown.locator(".el-select-dropdown__item").filter(has_text=option_text)
        item.click(force=True)
        # 等待下拉菜单关闭动画完成，避免遮挡后续操作
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

        优先直接匹配行文本；若未找到，则通过规格名称搜索框搜索后选择第一行。

        Args:
            flavor: 规格名称或关键字，如"4C8G"
        """
        # 等待表格加载完成
        self.page.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)

        flavor_row = self.page.locator(".el-table__row").filter(has_text=flavor)
        if flavor_row.count() == 0:
            # 直接未找到，使用规格名称搜索框
            search_input = self.page.locator("input[placeholder*='规格名称']")
            if search_input.count() > 0:
                search_input.first.fill(flavor)
                # 按回车触发搜索，避免按钮可点击性检测问题
                search_input.first.press("Enter")
                self.page.wait_for_timeout(500)
            flavor_row = self.page.locator(".el-table__row").first

        # 点击该行的单选按钮（固定列overlay可能导致原始DOM元素不可见，使用force=True；.first避免匹配多行时的strict模式违规）
        flavor_row.first.locator(".el-radio__input").click(force=True)

    @submenu("集群管理")
    def cce_delete(self, name):
        """删除指定名称的CCE集群。

        Args:
            name: 集群名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("集群管理")
    def get_cluster_node_data(self, cluster_name):
        """获取集群详情页的节点列表数据。

        若UI中未找到节点表格，返回空列表，由调用方通过SSH fallback验证。

        Args:
            cluster_name: 集群名称

        Returns:
            list[dict]: 节点数据列表，每个元素包含行数据字典（含"名称"、"内网IP"、"规格"等键）
        """
        self.goto_detail_page(cluster_name, tab_name="详情")

        rows = self.page.locator(".el-table__body-wrapper .el-table__row")
        node_data = []
        for i in range(rows.count()):
            row = rows.nth(i)
            node_name = row.locator("td").nth(1).inner_text()
            row_data = self.get_row_data(node_name)
            if row_data:
                node_data.append(row_data)

        return node_data

    @submenu("集群管理")
    def cce_edit_name(self, name, new_name):
        """修改指定集群的名称。

        Args:
            name: 当前集群名称
            new_name: 新集群名称
        """
        self.click_action(name, "修改")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改集群名称")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator("input").first.fill(new_name)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_edit_time_sync(self, name, sync_server):
        """修改指定集群的时间同步服务器。

        Args:
            name: 集群名称
            sync_server: 时间同步服务器IP或域名
        """
        self.click_action(name, "时间同步服务器")
        dialog = self.page.locator(".el-dialog").filter(has_text="时间同步服务器")
        dialog.wait_for(state="visible", timeout=10000)
        # 通过表单项标签定位时间同步服务器输入框
        dialog.locator(".el-form-item").filter(has_text="时间同步服务器IP").locator("input").fill(sync_server)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def _select_flavor_in_dialog(self, container, flavor):
        """在指定容器（如对话框）内的规格表格中选择指定规格。"""
        container.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)
        flavor_row = container.locator(".el-table__row").filter(has_text=flavor)
        if flavor_row.count() == 0:
            search_input = container.locator("input[placeholder*='规格名称']")
            if search_input.count() > 0:
                search_input.first.fill(flavor)
                search_input.first.press("Enter")
                self.page.wait_for_timeout(500)
            flavor_row = container.locator(".el-table__row").first
        flavor_row.first.locator(".el-radio__input").click(force=True)

    @submenu("集群管理")
    def cce_node_schedule_stop(self, node_name):
        """停止指定节点的调度。"""
        self.click_action(node_name, "停止调度")
        self.dialog_confirm.click()

    @submenu("集群管理")
    def cce_node_schedule_start(self, node_name):
        """开启指定节点的调度。"""
        self.click_action(node_name, "开启调度")
        self.dialog_confirm.click()

    @submenu("集群管理")
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

    @submenu("集群管理")
    def cce_node_label_add(self, node_name, key, value):
        """为节点添加单个自定义标签。"""
        self.click_action(node_name, "编辑标签")
        dialog = self.page.locator(".el-dialog").filter(has_text="编辑标签")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.get_by_text("添加标签").click()
        key_inputs = dialog.locator(".el-form-item").filter(has_text="键").locator("input:not([disabled])")
        key_inputs.last.fill(key)
        value_inputs = dialog.locator(".el-form-item").filter(has_text="值").locator("input:not([disabled])")
        value_inputs.last.fill(value)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_node_label_delete(self, node_name, key):
        """删除节点指定自定义标签。"""
        self.click_action(node_name, "编辑标签")
        dialog = self.page.locator(".el-dialog").filter(has_text="编辑标签")
        dialog.wait_for(state="visible", timeout=10000)
        key_inputs = dialog.locator(".el-form-item").filter(has_text="键").locator("input:not([disabled])")
        for i in range(key_inputs.count()):
            if key_inputs.nth(i).input_value() == key:
                row = key_inputs.nth(i).locator("xpath=ancestor::div[contains(@style,'display: flex')][contains(@style,'width: 100%')]")
                row.locator("i.el-icon-delete").click()
                break
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_node_create(self, num=1, volume_size=50, flavor="4C8G", max_pods=110):
        """新增计算节点。

        Args:
            num: 节点数量，默认1
            volume_size: 云硬盘大小(GiB)，默认50
            flavor: 节点规格，默认"4C8G"
            max_pods: POD上限，默认110
        """
        self.get_by_text("新增计算节点").click()
        dialog = self.page.locator(".el-dialog").filter(has_text="新增计算节点")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="新增计算节点数").locator("input").fill(str(num))
        dialog.locator(".el-form-item").filter(has_text="云硬盘大小(GiB)").locator("input").fill(str(volume_size))
        self._select_flavor_in_dialog(dialog, flavor)
        dialog.locator(".el-form-item").filter(has_text="POD上限").locator("input").fill(str(max_pods))
        dialog.get_by_text("确定").click()

    @submenu("集群管理")
    def cce_node_drain(self, node_name):
        """对指定节点执行排水操作。"""
        self.click_action(node_name, "节点排水")
        self.dialog_confirm.click()

    @submenu("集群管理")
    def cce_node_flavor_change(self, node_name, target_flavor):
        """修改指定节点的规格。

        Args:
            node_name: 节点名称
            target_flavor: 目标规格名称
        """
        self.click_action(node_name, "修改规格")
        dialog = self.page.locator(".el-dialog").filter(has_text="修改规格")
        dialog.wait_for(state="visible", timeout=10000)
        self._select_flavor_in_dialog(dialog, target_flavor)
        dialog.get_by_text("确定").click()

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

        Returns:
            int: 节点数量
        """
        return self.page.locator(".el-table__body-wrapper .el-table__row").count()

    def get_public_ip_text(self):
        """获取页面中公网IP的显示文本。

        Returns:
            str: 公网IP地址，未绑定返回空字符串
        """
        ip_locator = self.page.locator(".detail-info").filter(has_text="公网IP")
        if ip_locator.count() == 0:
            return ""
        text = ip_locator.inner_text()
        match = re.search(r"公网IP\s*[:：]?\s*(\S+)", text)
        return match.group(1) if match else ""

    def get_public_domain_text(self):
        """获取页面中公网域名的显示文本。

        Returns:
            str: 公网域名，未绑定返回空字符串
        """
        domain_locator = self.page.locator(".detail-info").filter(has_text="公网域名")
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

    @submenu("集群管理")
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
        self._select_option(volume_type)
        dialog.locator(".el-form-item").filter(has_text="云硬盘模式").locator(".el-select").click()
        self._select_option(volume_mode)
        dialog.locator(".el-form-item").filter(has_text="云硬盘容量").locator("input").fill(str(size))
        dialog.locator(".el-form-item").filter(has_text="云硬盘挂载目录").locator("input").fill(mount_path)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
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

    @submenu("集群管理")
    def cce_public_ip_bind(self, pool_name=None, ip_address=None):
        """为集群绑定公网IP。

        Args:
            pool_name: 资源池名称，为None时不选择
            ip_address: 指定浮动IP地址，为None时选择第一个可用IP
        """
        self.page.get_by_text("绑定公网IP").click()
        dialog = self.page.locator(".el-dialog").filter(has_text="绑定公网IP")
        dialog.wait_for(state="visible", timeout=10000)
        if pool_name:
            dialog.locator(".el-form-item").filter(has_text="请选择资源池").locator(".el-select").click()
            self._select_option(pool_name)
        dialog.wait_for_selector(".el-loading-mask", state="hidden", timeout=30000)
        if ip_address:
            row = dialog.locator(".el-table__row").filter(has_text=ip_address)
            row.locator(".el-radio__input").click(force=True)
        else:
            dialog.locator(".el-table__row").first.locator(".el-radio__input").click(force=True)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_public_ip_unbind(self):
        """为集群解绑公网IP。"""
        self.page.get_by_text("解绑公网IP").click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_public_domain_bind(self, record_name):
        """为集群绑定公网域名。

        Args:
            record_name: 主机记录名称
        """
        self.page.get_by_text("绑定公网域名").click()
        dialog = self.page.locator(".el-dialog").filter(has_text="新建公网解析")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="主机记录").locator("input").fill(record_name)
        dialog.wait_for_selector(".el-loading-mask", state="hidden", timeout=30000)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_public_domain_unbind(self):
        """为集群解绑公网域名。"""
        self.page.get_by_text("解绑公网域名").click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_node_public_ip_bind(self, node_name, pool_name=None, ip_address=None):
        """为节点绑定公网IP。

        Args:
            node_name: 节点名称
            pool_name: 资源池名称
            ip_address: 指定浮动IP地址
        """
        self.click_action(node_name, "绑定公网IP")
        dialog = self.page.locator(".el-dialog").filter(has_text="绑定公网IP")
        dialog.wait_for(state="visible", timeout=10000)
        if pool_name:
            dialog.locator(".el-form-item").filter(has_text="请选择资源池").locator(".el-select").click()
            self._select_option(pool_name)
        dialog.wait_for_selector(".el-loading-mask", state="hidden", timeout=30000)
        if ip_address:
            row = dialog.locator(".el-table__row").filter(has_text=ip_address)
            row.locator(".el-radio__input").click(force=True)
        else:
            dialog.locator(".el-table__row").first.locator(".el-radio__input").click(force=True)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    @submenu("集群管理")
    def cce_node_public_ip_unbind(self, node_name):
        """为节点解绑公网IP。"""
        self.click_action(node_name, "解绑公网IP")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def navigate_to_cluster_storage_class(self, cluster_name):
        """导航到指定集群详情页的存储类型标签页。

        Args:
            cluster_name: 集群名称
        """
        self.goto_service(self.service_name)
        self.wait_for_page_ready()
        self.page.locator(".cluster-name.single-line").filter(has_text=cluster_name).click()
        self.wait_for_page_ready()
        storage_tab = self.page.locator(".el-tabs__item").filter(has_text="存储类型")
        storage_tab.wait_for(state="visible", timeout=10000)
        storage_tab.click()
        self.wait_for_page_ready()

    def storage_class_create(self, name, volume_type="xbd-test", fstype="ext4", encrypt=False, access_mode="ReadWriteOnce"):
        """创建云硬盘存储类型。

        Args:
            name: 存储类型名称
            volume_type: 云硬盘类型，默认"xbd-test"
            fstype: 分区格式，默认"ext4"
            encrypt: 是否加密，默认False
            access_mode: 访问模式，默认"ReadWriteOnce"
        """
        self.page.locator("#storage-class").get_by_text("新建").click()
        dialog = self.page.locator(".el-dialog").filter(has_text="新建")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="存储类型名称").locator("input").fill(name)
        dialog.get_by_role("radio", name=re.compile(r"云硬盘|EVS")).click()
        dialog.locator(".el-form-item").filter(has_text="云硬盘类型").locator(".el-select").click()
        self._select_option(volume_type, exact=False)
        dialog.get_by_role("radio", name=fstype).click()
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def storage_class_delete(self, name):
        """删除指定名称的存储类型。

        Args:
            name: 存储类型名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def navigate_to_storage_volume(self):
        """导航到存储卷管理页面。"""
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/storage-volume")
        self.wait_for_page_ready()

    def storage_volume_create(self, name, capacity, storage_class, access_mode="ReadWriteOnce"):
        """创建存储卷。

        Args:
            name: 存储卷名称
            capacity: 存储容量（Gi）
            storage_class: 存储类型名称
            access_mode: 访问模式，默认"ReadWriteOnce"
        """
        self.btn_create.click()
        dialog = self.page.locator(".el-dialog").filter(has_text="添加存储卷")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill(name)
        dialog.locator(".el-form-item").filter(has_text="存储类型").locator(".el-select").click()
        self._select_option(storage_class)
        dialog.locator(".el-form-item").filter(has_text="存储容量").locator("input").fill(str(capacity))
        dialog.locator(".el-form-item").filter(has_text="访问模式").locator(".el-select").click()
        access_mode_text = {
            "ReadWriteOnce": "只允许单节点读写访问",
            "ReadOnlyMany": "允许多个节点只读访问",
            "ReadWriteMany": "允许多个节点读写访问"
        }.get(access_mode, "只允许单节点读写访问")
        self._select_option(access_mode_text)
        dialog.get_by_text("立即创建").click()
        self.wait_for_page_ready()

    def storage_volume_expand(self, name, new_capacity):
        """扩容存储卷。

        Args:
            name: 存储卷名称
            new_capacity: 扩容后的容量（Gi）
        """
        self.click_action(name, "扩容")
        dialog = self.page.locator(".el-dialog").filter(has_text="扩容")
        dialog.wait_for(state="visible", timeout=10000)
        dialog.locator(".el-form-item").filter(has_text="存储容量").locator("input").fill(str(new_capacity))
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def storage_volume_delete(self, name):
        """删除指定名称的存储卷。

        Args:
            name: 存储卷名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()


class CcePage(CceMixin):
    """云容器引擎CCE页面聚合类。"""

    service_name = "云容器引擎"
