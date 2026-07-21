import re
from sugon_web.common.base import submenu


class CceClusterMixin:
    """集群管理：创建、删除、编辑、详情查询。"""

    @submenu("集群管理")
    def cce_create(self, name, node_count=4, version="1.22.17", container_runtime="docker",
                   proxy_mode="ipvs", cluster="Autotest", desc="", vpc_network="Autotest",
                   vpc_subnet="Autotest", network_model="flannel", pod_cidr="10.0.0.0/16",
                   service_cidr="10.247.0.0/16", docker_cidr="172.17.0.1/16",
                   volume_type="", volume_size=50, flavor="4C8G"):
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
            volume_type: 云硬盘类型，未指定时自动从配置读取（如 ceph-type）
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
        # 云硬盘类型：未指定时从配置自动推导（参照 evs_create 模式）
        volume_type = volume_type or self.volume_type
        self.page.locator(".el-form-item").filter(has_text="云硬盘类型").locator(".el-select").first.click()
        self._select_option(volume_type, exact=False)

        # 云硬盘大小
        self.page.locator(".el-form-item").filter(has_text="云硬盘大小(GiB)").locator("input").first.fill(str(volume_size))

        # 规格选择 - 在规格表格中选择
        self._select_flavor(flavor)

        # 提交创建
        self.btn_submit.click()

    @submenu("集群管理")
    def cce_delete(self, name):
        """删除指定名称的CCE集群。

        Args:
            name: 集群名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("集群管理")
    def cce_batch_delete(self, names):
        """批量删除CCE集群。

        集群管理页存在定时轮询刷新表格，可能冲掉 checkbox 选中状态。
        若首次点击批量删除后确认对话框未出现，则重新勾选并重试。

        Args:
            names: 集群名称列表
        """
        # self.select_rows_by_names(names)
        # self.btn_batch_delete.click()
        # self.dialog_confirm.click()
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()
        self.get_by_text("批量删除").click()
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
        # 显式 wait_for(visible) 用于区分"locator 匹配到隐藏 input"和"可见 input"
        # 若命中隐藏元素会抛 TimeoutError: Element is not visible，避免 fill 填到"影子"元素
        input_locator = dialog.locator(".el-form-item").filter(has_text="时间同步服务器IP").locator("input")
        input_locator.wait_for(state="visible", timeout=5000)
        # 在 fill 前增加 click() 确保 focus，规避 Element UI 组件 focus 时机问题
        input_locator.click()
        input_locator.fill(sync_server)
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()
