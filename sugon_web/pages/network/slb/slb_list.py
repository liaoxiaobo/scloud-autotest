import random
import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data
from sugon_web.common.playwright import expect
from sugon_web.assertions.network.slb import SlbAssertionMixin


class SlbListMixin(SlbAssertionMixin, BasePage):
    """SLB列表页。"""

    def _get_slb_basic_settings_form(self):
        """获取创建负载均衡页面中的"基础设置"表单区域。"""
        return self.locator("form").filter(has_text=re.compile(r"基础设置")).first

    @submenu("负载均衡（基础版）")
    def slb_create(self, name=None, version="V2", cluster=None, vpc=None,
                   ip_type="自动分配", ip_address=None, spec=None, desc=None,
                   ha_enable=False):
        """创建负载均衡

        Args:
            name: 负载均衡名称，可以为None，将会自动生成随机名称
            version: 版本类型，"V1" 或 "V2"，默认"V2"
            cluster: 集群名称，V2版本适用
            vpc: 虚拟私有云(VPC)名称
            ip_type: IP分配方式，"自动分配"、"快速选择" 或 "手动输入"
            ip_address: 当ip_type为"快速选择"或"手动输入"时的IP地址，此时为必填项
            spec: 规格设置，V2版本适用 (例如: "slb.d6.large 2核 4GiB 内网带宽")
            desc: 描述信息
            ha_enable: 是否启用HA开关 (True=开启, False=不开启)
        """
        self.btn_create.click()

        # 填写名称
        if not name:
            name = f"slb-{random_data()}"
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").click()
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        # 选择版本类型
        self.get_by_role("radio", name=version).click()

        # HA开关设置（对V1和V2通用）
        deploy_mode = Config.get("deploy_mode")
        if deploy_mode == "stack" and ha_enable:
            ha_switch = self._get_slb_basic_settings_form().get_by_role("switch").first
            if ha_switch.count() > 0 and ha_switch.is_visible():
                is_checked = ha_switch.get_attribute("aria-checked") == "true"
                if is_checked != ha_enable:
                    ha_switch.locator("span").click()
        else:
            self.logger.info(f"当前 deploy_mode={deploy_mode}，创建页不展示 HA 开关")

        # 只有在V2时才需要选择集群和规格
        if version == "V2":
            # 集群选择
            if cluster:
                cluster_form_item = self._get_slb_basic_settings_form().locator("div.el-form-item").filter(has_text=re.compile(r"集群"))
                cluster_form_item.get_by_placeholder("请选择").click()
                self.locator("li").filter(has_text=re.compile(rf"^{re.escape(cluster)}$")).click()

        # 网络配置 - VPC
        if vpc:
            if version == "V1":
                self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            else:
                self.locator("form div").filter(has_text="网络配置 子网网络 子网 IPv4 IPv6").get_by_placeholder(
                    "请选择").click()
            # 使用包含名称的项
            self.get_by_text(vpc).first.click()

        # 网络配置 - IP分配方式
        if ip_type == "自动分配":
            self.locator("label").filter(has_text="自动分配").click()
        elif ip_type in ["快速选择", "手动输入"]:
            # 当IP分配方式为手动分配的时候才能快速选择或手动输入ip，且ip是必填
            if not ip_address:
                raise ValueError("在IPv4分配方式为手动分配且选择快速选择或手动输入时，IP是必填项")

            # 先点击"手动分配"
            self.locator("label").filter(has_text="手动分配").click()
            # 在 IPv4 分配方式为手动分配的时候，选择具体的子选项并填入 IP
            self.locator("label").filter(has_text=ip_type).click()

            # 锚定包含 "快速选择/手动输入" 单选按钮的表单项容器
            container = self.locator("div.el-form-item__content").filter(has=self.get_by_role("radio", name="快速选择"))

            if ip_type == "快速选择":
                # 点击该容器内的下拉框。
                container.get_by_placeholder("请选择").click()
                self.get_by_text(ip_address, exact=True).click()
            elif ip_type == "手动输入":
                # 同理填入手动输入框
                container.get_by_placeholder("请输入", exact=True).click()
                container.get_by_placeholder("请输入", exact=True).fill(ip_address)

        # 规格设置 - 只有在V2才需要选择
        if version == "V2" and spec:
            self.get_by_role("row", name=spec).get_by_role("radio").click()

        # 描述
        if desc:
            self.locator("textarea").click()
            self.locator("textarea").fill(desc)

        # 提交
        self.btn_submit.click()

        self.logger.info(f"负载均衡创建完成: {name} ({version})")
        return name

    @submenu("负载均衡（基础版）")
    def goto_slb_detail(self, slb_name, tab_name="详情"):
        """进入负载均衡详情页并切换到指定Tab页

        Args:
            slb_name: 负载均衡名称
            tab_name: 详情页中的Tab名称，如："详情"、"监听器"、"后端服务器组" 等
        """
        # @submenu 装饰器已确保在负载均衡服务下，若从子页面（如resource-pool-detail）进入，
        # 子菜单点击会导航回SLB列表页

        # 先搜索目标SLB，避免分页导致定位失败
        try:
            self.search(slb_name)
        except Exception:
            self.logger.debug(f"搜索SLB {slb_name} 失败，尝试直接定位")

        # 点击SLB名称链接进入详情页
        # 搜索后列表通常只有一条，名称列在第二列（第一列为复选框）
        target_row = self.get_row_by_name(slb_name)
        name_cell = target_row.locator("td").nth(1)
        name_link = name_cell.locator("a").first
        if name_link.count() > 0 and name_link.is_visible():
            name_link.click(force=True)
        else:
            name_cell.click(force=True)

        # 等待页面加载，增加容错避免 loading spinner 等待卡住
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
            self.page.wait_for_load_state("load", timeout=15000)
        except Exception:
            pass
        try:
            self.wait_for_page_ready()
        except Exception as e:
            self.logger.warning(f"wait_for_page_ready 警告（继续执行）: {e}")
            self.page.wait_for_timeout(2000)

        # 兼容 tab 文本可能带计数后缀（如"监听器(1)"）
        tab = self.locator("[role='tab']").filter(has_text=re.compile(rf"^{re.escape(tab_name)}"))
        try:
            expect(tab.first).to_be_visible(timeout=15000)
        except Exception as e:
            self.logger.warning(f"Tab '{tab_name}' 未在15秒内可见（继续执行）: {e}")
        tab.first.evaluate("node => node.click()")
        # 点击tab后等待内容加载（监听器列表异步渲染）
        if tab_name == "监听器":
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            self.page.wait_for_timeout(3000)

        self.logger.info(f"进入负载均衡 {slb_name} 的 {tab_name}")

    @submenu("负载均衡（基础版）")
    def get_slb_detail_info(self, slb_name):
        """进入SLB详情页并获取详细信息。

        优先通过 JavaScript 读取 Vue 组件内部状态(balanceDetail)，
        若读取失败则降级为从 DOM 中提取关键字段。

        Args:
            slb_name: 负载均衡名称

        Returns:
            dict: 包含以下键的字典：
                - name: SLB 名称
                - id: SLB UUID
                - vip: 内网 VIP 地址
                - vip6: IPv6 地址（如有）
                - status: 状态
                - version: 版本类型（V1/V2）
                - ha: HA 是否开启
        """
        self.goto_slb_detail(slb_name, tab_name="详情")

        detail_box = self.page.locator(".detail-display-box").first
        detail_box.wait_for(state="visible", timeout=15000)

        # 等待 loading 消失
        try:
            self.page.wait_for_selector(
                ".detail-display-box .el-loading-mask",
                state="hidden",
                timeout=15000,
            )
        except Exception:
            pass

        # 优先从 Vue 实例读取完整数据
        balance_detail = detail_box.evaluate("""
            el => {
                let vue = el.__vue__;
                if (!vue) {
                    let parent = el;
                    while (parent) {
                        if (parent.__vue__) {
                            vue = parent.__vue__;
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
                if (vue && vue.balanceDetail) {
                    return vue.balanceDetail;
                }
                return null;
            }
        """)

        if balance_detail:
            return {
                "name": balance_detail.get("name", slb_name),
                "id": balance_detail.get("uuid", "") or balance_detail.get("id", ""),
                "vip": balance_detail.get("vip_address", ""),
                "vip6": balance_detail.get("vip6_address", ""),
                "status": balance_detail.get("status", ""),
                "version": "V2" if balance_detail.get("type") == "nfv" else "V1",
                "ha": balance_detail.get("topology") == "ACTIVE_STANDBY",
            }

        # 降级：从 DOM 读取关键字段
        info = {"name": slb_name, "id": "", "vip": "", "vip6": "", "status": "", "version": "", "ha": False}

        # VIP
        vip_el = self.locator("cl-item-col[label='网络IP'] span").first
        if vip_el.count() > 0 and vip_el.is_visible():
            text = vip_el.inner_text().strip()
            if text and text != "--":
                info["vip"] = text

        # UUID
        uuid_el = self.locator("cl-item-col[label='负载均衡UUID']").first
        if uuid_el.count() > 0 and uuid_el.is_visible():
            text = uuid_el.inner_text().strip()
            if text and text != "--":
                info["id"] = text

        # 状态
        status_el = self.locator("cl-item-col[label='状态'] span").first
        if status_el.count() > 0 and status_el.is_visible():
            info["status"] = status_el.inner_text().strip()

        self.logger.info(f"从详情页获取SLB '{slb_name}' 信息: {info}")
        return info

    @submenu("负载均衡（基础版）")
    def slb_list_goto_lb_detail(self, slb_name, lb_name, column_name="配置监听器(前端协议/端口)"):
        """从SLB列表页点击指定监听器入口并进入其详情页

        Args:
            slb_name: 负载均衡名称，用于精确定位所在行
            lb_name: 监听器名称，用于在目标列中精确定位对应入口
            column_name: 监听器所在列名，默认"配置监听器(前端协议/端口)"
        """
        target_row = self.get_row_by_name(slb_name)

        table_index = target_row.evaluate("""
            el => {
                const table = el.closest('.el-table');
                if (!table) return -1;
                return Array.from(document.querySelectorAll('.el-table')).indexOf(table);
            }
        """)

        if table_index != -1:
            header_wrapper = self.locator(".el-table").nth(table_index).locator(".el-table__header-wrapper")
            th_elements = header_wrapper.locator("th").all()
            headers = [self._extract_header_text(th) for th in th_elements]
        else:
            headers = self.table_headers

        headers = [re.sub(r"\s+", " ", item).strip() for item in headers]
        if column_name not in headers:
            raise AssertionError(f"未找到表头 '{column_name}'，当前表头: {headers}")

        target_col_index = headers.index(column_name)
        target_cell = target_row.get_by_role("cell").nth(target_col_index)
        lb_pattern = re.compile(rf"^{re.escape(lb_name)}\s*\([^)]+\)$")

        text_nodes = target_cell.locator("span.text-content")
        matched_indexes = []

        all_texts = text_nodes.all_text_contents()
        for i, text in enumerate(all_texts):
            text_value = re.sub(r"\s+", " ", text or "").strip()
            if lb_pattern.match(text_value):
                matched_indexes.append(i)

        if not matched_indexes:
            raise AssertionError(
                f"在 SLB '{slb_name}' 的列 '{column_name}' 中未找到监听器 '{lb_name}' 的跳转入口，"
                f"单元格内容: '{target_cell.text_content()}'"
            )

        if len(matched_indexes) > 1:
            matched_texts = [
                re.sub(r"\s+", " ", text or "").strip()
                for i, text in enumerate(all_texts) if i in matched_indexes
            ]
            raise AssertionError(
                f"在 SLB '{slb_name}' 的列 '{column_name}' 中找到多个匹配监听器 '{lb_name}': {matched_texts}"
            )

        target_text = text_nodes.nth(matched_indexes[0])
        clickable = target_text.locator("xpath=ancestor::div[contains(@class,'cloud-button-btn')][1]")
        if clickable.count() == 0:
            clickable = target_text.locator("xpath=ancestor::*[@title][1]")
        if clickable.count() == 0:
            clickable = target_text

        clickable.click()
        self.logger.info(f"从SLB列表页进入监听器详情成功: SLB={slb_name}, LB={lb_name}")

    @submenu("负载均衡（基础版）")
    def slb_delete(self, names):
        """负载均衡

        Args:
            names: 负载均衡名称或名称列表
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作 ").click()

            # 点击批量删除选项
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

    @submenu("负载均衡（基础版）")
    def get_slb_vip(self, slb_name):
        """
        获取负载均衡的内网VIP地址。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 内网VIP地址
        """
        row_data = self.get_row_data(slb_name)
        vip = row_data.get("VIP地址") or row_data.get("内网地址") or row_data.get("网络IP") or row_data.get("地址")
        if not vip:
            headers = self.table_headers
            for key in ["VIP地址", "内网地址", "网络IP", "地址", "IPv4地址"]:
                if key in headers:
                    vip = row_data.get(key)
                    if vip:
                        break
        if not vip:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取内网VIP地址，当前行数据: {row_data}")
        self.logger.info(f"获取SLB '{slb_name}' 内网VIP地址: {vip}")
        return vip.strip()

    @submenu("负载均衡（基础版）")
    def get_slb_uuid(self, slb_name):
        """获取负载均衡的uuid。

        通过JavaScript从el-table行元素的Vue内部状态中读取uuid。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 负载均衡uuid
        """
        row = self.get_row_by_name(slb_name)
        uuid = row.evaluate("""
            el => {
                let current = el;
                while (current) {
                    if (current.__vue__ && current.__vue__.row && current.__vue__.row.uuid) {
                        return current.__vue__.row.uuid;
                    }
                    current = current.parentElement;
                }
                const tr = el.closest('tr');
                if (tr && tr.dataset && tr.dataset.uuid) return tr.dataset.uuid;
                const tableRow = el.closest('.el-table__row');
                if (tableRow && tableRow.__vue__ && tableRow.__vue__.row && tableRow.__vue__.row.uuid) {
                    return tableRow.__vue__.row.uuid;
                }
                return null;
            }
        """)
        if not uuid:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取uuid")
        self.logger.info(f"获取SLB '{slb_name}' uuid: {uuid}")
        return uuid

    @submenu("负载均衡（基础版）")
    def get_slb_project_id(self, slb_name):
        """获取负载均衡的project_id。

        通过JavaScript从el-table行元素的Vue内部状态中读取project_id。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: project_id
        """
        row = self.get_row_by_name(slb_name)
        project_id = row.evaluate("""
            el => {
                let current = el;
                while (current) {
                    if (current.__vue__ && current.__vue__.row && current.__vue__.row.project_id) {
                        return current.__vue__.row.project_id;
                    }
                    current = current.parentElement;
                }
                const tr = el.closest('tr');
                if (tr && tr.dataset && tr.dataset.projectId) return tr.dataset.projectId;
                const tableRow = el.closest('.el-table__row');
                if (tableRow && tableRow.__vue__ && tableRow.__vue__.row && tableRow.__vue__.row.project_id) {
                    return tableRow.__vue__.row.project_id;
                }
                return null;
            }
        """)
        if not project_id:
            raise AssertionError(f"未能从SLB '{slb_name}' 获取project_id")
        self.logger.info(f"获取SLB '{slb_name}' project_id: {project_id}")
        return project_id

    @submenu("负载均衡（基础版）")
    def goto_slb_monitor(self, slb_name):
        """在SLB列表页点击"查看监控"进入监控详情页。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 监控页面URL
        """
        self.search(slb_name)
        self.click_action(slb_name, "查看监控")
        self.logger.info(f"点击SLB '{slb_name}' 查看监控")
        # 等待页面导航完成
        self.page.wait_for_timeout(3000)
        return self.page.url

    @submenu("负载均衡（基础版）")
    def get_slb_eip(self, slb_name):
        """
        获取负载均衡绑定的公网IP地址。

        Args:
            slb_name: 负载均衡名称

        Returns:
            str: 公网IP地址，如果未绑定则返回None
        """
        row_data = self.get_row_data(slb_name)
        eip = row_data.get("公网IPv4") or row_data.get("公网IP") or row_data.get("弹性公网IP")
        if eip and eip.strip() and eip.strip() not in ["-", "--", "无", ""]:
            self.logger.info(f"获取SLB '{slb_name}' 公网IP地址: {eip.strip()}")
            return eip.strip()
        self.logger.info(f"SLB '{slb_name}' 未绑定公网IP")
        return None

    @submenu("负载均衡（基础版）")
    def get_available_eips(self, slb_name, network_type="public_net(基础版)", ip_version="IPv4"):
        """获取负载均衡可绑定的可用公网IP列表（不执行绑定）

        Args:
            slb_name: 负载均衡名称
            network_type: IP池名称，默认"public_net(基础版)"
            ip_version: IP版本，默认"IPv4"

        Returns:
            list[str]: 可用EIP地址列表（状态为'关闭'的IP）
        """
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        try:
            expect(rows_locator.first).to_be_visible(timeout=10000)
            available_rows = rows_locator.all()
        except AssertionError:
            available_rows = []

        eips = [row.get_by_role("cell").nth(1).text_content().strip() for row in available_rows]

        # 关闭对话框，不执行绑定
        try:
            dialog.get_by_text("取消").click()
        except Exception:
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
        self.logger.info(f"负载均衡 {slb_name} 可用公网IP: {eips}")
        return eips

    @submenu("负载均衡（基础版）")
    def slb_bind_eip(self, slb_name, network_type="public_net(基础版)", ip_version="IPv4"):
        """为负载均衡绑定公网IP，并返回绑定的EIP地址"""
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)
        available_rows = rows_locator.all()
        if not available_rows:
            raise AssertionError("当前环境无可用的弹性公网IPv4（状态为'关闭'）")

        selected_row = random.choice(available_rows)
        eip = selected_row.get_by_role("cell").nth(1).text_content().strip()
        selected_row.get_by_role("radio").click()
        dialog.get_by_text("确定").click()
        self.logger.info(f"负载均衡 {slb_name} {action_name}成功: {eip}")
        return eip

    @submenu("负载均衡（基础版）")
    def slb_bind_eip_by_ip(self, slb_name, eip, network_type="public_net(基础版)", ip_version="IPv4"):
        """为负载均衡绑定指定公网IP

        Args:
            slb_name: 负载均衡名称
            eip: 要绑定的公网IP地址
            network_type: IP池名称，默认"public_net(基础版)"
            ip_version: IP版本，默认"IPv4"

        Returns:
            str: 绑定的EIP地址
        """
        action_name = f"绑定公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)

        available_rows = rows_locator.all()
        target_row = None
        for row in available_rows:
            cell_text = row.get_by_role("cell").nth(1).text_content().strip()
            if eip in cell_text:
                target_row = row
                break

        if target_row is None:
            raise AssertionError(
                f"在绑定公网IP对话框中未找到IP {eip}，"
                f"可用IP: {[r.get_by_role('cell').nth(1).text_content().strip() for r in available_rows]}"
            )
        target_row.get_by_role("radio").click()
        dialog.get_by_text("确定").click()
        self.logger.info(f"负载均衡 {slb_name} 绑定公网IP {eip} 成功")
        return eip

    @submenu("负载均衡（基础版）")
    def slb_unbind_eip(self, slb_name, ip_version="IPv4"):
        """解绑负载均衡绑定的公网IP"""
        action_name = f"解绑公网{ip_version}"
        self.click_action(slb_name, action_name)
        dialog = self._find_element([
            self.get_by_role("dialog", name=action_name),
            self.get_by_label(action_name),
        ], f"{action_name}对话框", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()
        self.assert_popup_success("执行成功")
        self.logger.info(f"负载均衡 {slb_name} {action_name}成功")
