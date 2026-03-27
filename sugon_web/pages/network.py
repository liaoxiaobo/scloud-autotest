import re
import time
import random
import pytest
from playwright.sync_api import Page, expect
from sugon_web.common.base import BasePage, submenu
import ipaddress


class VpcPage(BasePage):
    """虚拟私有云页面类"""

    EIP_COLUMN_CANDIDATES = ("IP地址", "公网IP", "弹性公网IP")

    @property
    def _input_name(self):
        """VPC名称输入框"""
        return self.get_by_placeholder("请输入名称")

    @property
    def _input_desc(self):
        """VPC描述输入框"""
        return self.locator("textarea").nth(0)
        # return self.locator("form").filter(has_text="名称 网络GeneveVlanFlat 描述0/").locator("textarea")

    @property
    def _input_subnet_name(self):
        """子网名称输入框"""
        return self.get_by_placeholder("请输入子网名称")

    @property
    def _input_subnet_desc(self):
        """子网描述输入框"""
        return self.locator("textarea").nth(1)

    @property
    def _input_cidr(self):
        """子网CIDR输入框"""
        return self.get_by_placeholder("必填 如：10.0.13.0/")

    @property
    def _input_gateway(self):
        """网关IP输入框"""
        return self.get_by_placeholder("（默认xx.xx.xx.1）")

    @property
    def _input_available_ip(self):
        """可用IP输入框"""
        return self.get_by_placeholder("选填（默认子网内全部IP可用）")

    @property
    def _input_dns(self):
        """DNS输入框"""
        return self.get_by_placeholder("选填(默认:114.114.114.114)")

    @property
    def _input_vlan_id(self):
        """VLAN ID输入框（仅VLAN网络类型显示）"""
        return self.get_by_placeholder("请输入1到4094的正整数")

    @submenu("虚拟私有云")
    def vpc_create(self, name, subnet_name, cidr, desc="", subnet_desc="",
                   network_type="Geneve", gateway_mode="分布式网关",
                   gateway_ip=None, available_ip=None, dns=None, vlan_id=None, mac=None,
                   enable_ipv6=False, acl_policy=None):
        """创建虚拟私有云

        Args:
            name: VPC名称
            subnet_name: 子网名称
            cidr: 子网CIDR，如 "100.0.0.0/24"
            desc: VPC描述，默认为空
            subnet_desc: 子网描述，默认为空
            network_type: 网络类型，支持 "Geneve"/"Vlan"/"Flat"，默认为 "Geneve"
            gateway_mode: 网关模式，支持 "分布式网关"/"集中式网关"，默认为 "分布式网关"
                        (仅当 network_type="Vlan" 时有效)
            gateway_ip: 网关IP，如果为None则使用默认值
            available_ip: 可用IP，如果为None则使用默认值
            dns: DNS服务器地址，如果为None则使用默认值
            vlan_id: VLAN ID，范围1-4094，仅当 network_type="Vlan" 时有效
            mac: MAC地址，仅当 network_type="Vlan" 或 "Flat" 时有效
            enable_ipv6: 是否开启IPv6，默认为False（仅当 network_type="Geneve" 时有效）
            acl_policy: 访问控制策略，默认为None
        """
        # 打开创建页面
        self.btn_create.click()
        self.wait_for_page_ready()

        # 填写VPC基本信息
        self._input_name.fill(name)
        self._input_desc.fill(desc)

        # 选择网络类型
        self.get_by_role("radio", name=network_type).click()

        # - Vlan 类型：需要选择网关模式
        if network_type == "Vlan":
            self.get_by_role("radio", name=gateway_mode).click()

            # 填写 VLAN ID（如果提供）
            if vlan_id is not None:
                self._input_vlan_id.fill(str(vlan_id))

        # - Vlan 和 Flat 类型：可以填写 MAC 地址
        if network_type in ["Vlan", "Flat"]:
            # 填写 MAC 地址（如果提供）
            if mac is not None:
                self.get_by_placeholder("默认mac地址aa:bb:cc:dd:ee:ff").fill(mac)

        # - Geneve 类型：支持 IPv6
        if network_type == "Geneve" and enable_ipv6:
            # 检查"开启IPv6"元素是否可见
            ipv6_checkbox = self.get_by_text("开启IPv6", exact=True)
            if ipv6_checkbox.is_visible() and ipv6_checkbox.is_enabled():
                ipv6_checkbox.click()
            else:
                self.goto_service("虚拟私有云")
                pytest.skip("当前环境不支持双栈VPC")

        # 填写子网信息
        self._input_subnet_name.fill(subnet_name)
        self._input_subnet_desc.fill(subnet_desc)
        self._input_cidr.fill(cidr)

        # 如果指定了网关IP，则填写
        if gateway_ip:
            self._input_gateway.fill(gateway_ip)
        else:
            ip = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
            self._input_gateway.fill(ip)

        # 处理关联ACL策略
        acl_item = self.locator(".el-form-item").filter(has_text="关联ACL策略")
        # 悬浮容器显示清空按钮
        acl_item.hover()
        clear_icon = acl_item.locator(".el-icon-circle-close")
        if clear_icon.is_visible():
            clear_icon.click()

        if acl_policy:
            # 选择ACL策略
            self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=acl_policy).click()

        # 如果指定了可用IP，则填写
        if available_ip:
            self._input_available_ip.fill(available_ip)

        # 如果指定了DNS，则填写
        if dns:
            self._input_dns.fill(dns)

        # 提交创建
        self.btn_submit.click()
        self.wait_for_page_ready()

    @submenu("虚拟私有云")
    def vpc_delete(self, names):
        """删除虚拟私有云，支持单个和批量操作

        Args:
            names: VPC名称（字符串）或VPC名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 确认删除
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vpc_details_get(self, name) -> dict:
        """
        获取VPC详情页面的数据

        Returns:
            dict: 包含VPC详情的字典
        """
        self.get_by_role("row", name=name).locator("a").click()

        common_fields = ["ID", "状态", "共享的", "MTU"]
        result = {}
        for field in common_fields:
            # 选择器逻辑：label 包含“字段:”，下一个兄弟 .el-form-item__content 内的 span
            selector = f"label:has-text('{field}:') + .el-form-item__content p"
            value = self.page.text_content(selector).strip()
            result[field] = value

        # 名称：label含“名称:”，值在相邻 .el-form-item__content 的 span 里
        name = self.page.text_content("label:has-text('名称:') + .el-form-item__content span").strip()
        result["名称"] = name

        # 虚拟私有云类型：label含“虚拟私有云:”，但值在内部 span（“虚拟私有云类型：GENEVE”）
        vpc_type_text = self.page.text_content("span:has-text('虚拟私有云类型：')")
        vpc_type = vpc_type_text.split(":", 1)[-1].strip()
        result["虚拟私有云类型"] = vpc_type

        # 段ID：label含“虚拟私有云:”，但值在内部另一个 span（“段ID：7386”）
        segment_id_text = self.page.text_content("span:has-text('段ID：')")
        segment_id = segment_id_text.split(":", 1)[-1].strip()
        result["段ID"] = segment_id

        return result

    @submenu("虚拟私有云")
    def vpc_edit(self, name, new_name=None, new_desc=None):
        """修改虚拟私有云

        Args:
            name: VPC名称
            new_name: 新名称，如果不提供则不修改
            new_desc: 新描述，如果不提供则不修改
        """
        # 点击操作按钮
        self.click_action(name, "修改")

        # 修改名称（如果提供）
        if new_name:
            self.get_by_label("修改网络").locator("input[type=\"text\"]").fill(new_name)

        # 修改描述（如果提供）
        if new_desc:
            self.locator("textarea").fill(new_desc)

        # 提交修改
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vpc_generate_auth_code(self, name):
        """生成VPC授权码并复制

        Args:
            name: VPC名称

        Returns:
            str: 生成的授权码
        """
        # 点击操作按钮并选择"生成授权码"
        self.click_action(name, "生成授权码")

        # 等待授权码弹窗出现
        self.wait_for_page_ready()

        # 获取授权码文本
        auth_code = self.get_by_text('eyJ').inner_text()

        # 点击"复制"按钮
        self.get_by_text("复制").click()

        # 点击授权码文本关闭弹窗（或按ESC）
        self.get_by_text("取 消").click()

        return auth_code

    @submenu("虚拟私有云")
    def subnet_create(self, vpc_name, subnet_name, cidr, desc="",
                          available_ip=None, dns=None, acl_policy=None, gateway_ip=None):
        """在VPC中新建子网

        Args:
            vpc_name: VPC名称（用于定位VPC）
            subnet_name: 子网名称
            cidr: 子网CIDR，如 "10.0.100.0/24"
            desc: 子网描述，默认为空
            available_ip: 可用IP范围，如 "10.0.100.10-10.0.100.100"，如果为None则使用默认
            dns: DNS服务器地址，如果为None则使用默认
            acl_policy: 关联的ACL策略名称，如果为None则不选择
            gateway_ip: 网关IP，如果为None则使用默认
        """

        # 点击VPC行的操作按钮并选择"新建子网"
        self.click_action(vpc_name, "新建子网")

        # 填写子网名称
        self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(subnet_name)

        # 填写子网描述
        if desc:
            self.locator("div").filter(has_text=re.compile(r"^描述0/255$")).get_by_role("textbox").fill(desc)

        # 填写CIDR
        self._input_cidr.fill(cidr)

        # 如果指定了网关IP，则填写
        if gateway_ip:
            self._input_gateway.fill(gateway_ip)
        # else:
        #     # 使用默认网关IP（CIDR的第一个可用IP）
        #     ip = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
        #     self._input_gateway.fill(ip)

        # 处理关联ACL策略
        acl_item = self.locator(".el-form-item").filter(has_text="关联ACL策略")
        acl_item.hover()
        clear_icon = acl_item.locator(".el-icon-circle-close")
        if clear_icon.is_visible():
            clear_icon.click()

        # 如果提供了ACL策略，则关联ACL
        if acl_policy:
            # 查找ACL策略下拉框并选择
            acl_selector = self.locator("div").filter(has_text=f"关联ACL策略{acl_policy}")
            acl_selector.locator("i").nth(1).click()

        # 如果指定了可用IP，则填写
        if available_ip:
            self._input_available_ip.fill(available_ip)

        # 如果指定了DNS，则填写
        if dns:
            self._input_dns.fill(dns)

        # 提交创建
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_create_in_detail(self, vpc_name, subnet_name, cidr, desc="",
                                available_ip=None, dns=None, acl_policy=None, gateway_ip=None):
        """在VPC详情页的子网tab页中新建子网

        Args:
            vpc_name: VPC名称
            subnet_name: 子网名称
            cidr: 子网CIDR，如 "10.0.100.0/24"
            desc: 子网描述，默认为空
            available_ip: 可用IP范围，如 "10.0.100.10-10.0.100.100"，如果为None则使用默认
            dns: DNS服务器地址，如果为None则使用默认
            acl_policy: 关联的ACL策略名称，如果为None则不选择
            gateway_ip: 网关IP，如果为None则使用默认值
        """
        # 进入VPC详情页面
        self.get_by_role("row", name=vpc_name).locator("a").click()
        self.wait_for_page_ready()

        # 点击"子网"tab
        self.get_by_role("tab", name="子网").click()
        self.wait_for_page_ready()

        # 点击"新建子网"按钮
        new_button = self.get_by_label("子网", exact=True).get_by_text("新建")
        # expect(new_button).to_be_visible()
        # expect(new_button).to_be_enabled()
        time.sleep(3)   # 等待元素可点击
        new_button.click()

        # 填写子网名称
        self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(subnet_name)

        # 填写子网描述
        if desc:
            self.locator("div").filter(has_text=re.compile(r"^描述0/255$")).get_by_role("textbox").fill(desc)

        # 填写CIDR
        self._input_cidr.fill(cidr)

        # 如果指定了网关IP，则填写
        if gateway_ip:
            self._input_gateway.fill(gateway_ip)
        # else:
        #     # 使用默认网关IP（CIDR的第一个可用IP）
        #     ip = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
        #     self._input_gateway.fill(ip)

        # 如果指定了可用IP，则填写
        if available_ip:
            self._input_available_ip.fill(available_ip)

        # 如果指定了DNS，则填写
        if dns:
            self._input_dns.fill(dns)

        # 如果提供了ACL策略，则关联ACL
        if acl_policy:
            acl_select = self.get_by_text("关联ACL策略").locator("..//..").get_by_role("combobox")
            acl_select.click()
            self.get_by_role("option", name=acl_policy).click()

        # 提交创建
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_delete(self, vpc_name, names):
        """在VPC详情页的子网tab页中删除子网，支持单个和批量操作

        Args:
            vpc_name: VPC名称
            names: 子网名称（字符串）或子网名称列表（列表）
        """
        # # 进入VPC详情页面
        # self.get_by_role("row", name=vpc_name).locator("a").click()
        # self.wait_for_page_ready()

        # 点击"子网"tab
        # self.get_by_role("tab", name="子网").click()
        # self.wait_for_page_ready()

        if isinstance(names, list):
            # 批量删除模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个删除模式
            self.click_action(names, "删除")

        # 确认删除
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_edit(self, subnet_name, new_name=None, new_desc=None, new_available_ip=None, new_dns=None):
        """在VPC详情页的子网tab页中修改子网

        Args:
            subnet_name: 要修改的子网当前名称
            new_name: 新名称，如果为None则不修改
            new_desc: 新描述，如果为None则不修改
            new_available_ip: 新IP地址池，如果为None则不修改
            new_dns: 新DNS，如果为None则不修改
        """
        # 点击编辑按钮 (按钮文本为"修改")
        self.click_action(subnet_name, "修改")
        self.wait_for_page_ready()

        # 修改子网名称
        if new_name is not None:
            self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(new_name)

        # 修改子网描述
        if new_desc is not None:
            # 使用 ^描述 匹配所有以“描述”开头的文本
            self.locator("div").filter(has_text=re.compile(r"^描述")).get_by_role("textbox").fill(new_desc)

        # 修改可用IP
        if new_available_ip is not None:
            self.get_by_role("textbox", name="选填（默认子网内全部IP可用）").fill(new_available_ip)

        # 修改DNS
        if new_dns is not None:
            self.get_by_role("textbox", name="选填(默认:114.114.114.114)").fill(new_dns)

        # 提交修改
        self.dialog_confirm.click()
        self.wait_for_page_ready()



    def vip_create(self, vpc_name, subnet_name, ip_address=None):
        """创建虚拟IP地址

        Args:
            vpc_name: VPC名称（如 "autotest-cdi"）
            subnet_name: 子网名称（如 "autotest-01yks"）
            ip_address: 手动分配的IP地址，如果为None则使用自动分配模式
        """
        # 点击VPC名称进入详情页
        self.get_by_role("row", name=vpc_name).locator("a").click()

        # 点击"虚拟IP管理"tab
        self.get_by_role("tab", name="虚拟IP管理").click()
        self.wait_for_page_ready()

        # 点击"申请虚拟IP地址"按钮
        self.get_by_text("申请虚拟IP地址").first.click()

        # 选择子网
        self.get_by_label("申请虚拟IP地址").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=subnet_name).click()

        # 根据ip_address参数选择分配方式
        if ip_address is None:
            # 自动分配模式（默认）
            pass  # 默认就是自动分配，不需要额外操作
        else:
            # 手动分配模式
            self.locator("label").filter(has_text="手动分配").click()

            # 只取IP地址的最后一段
            last_segment = ip_address.split('.')[-1]
            self.get_by_label("申请虚拟IP地址").get_by_role("textbox").nth(4).fill(last_segment)

        # 点击确定
        self.get_by_label("申请虚拟IP地址").get_by_text("确定").click()
        self.wait_for_page_ready()


    def vip_delete(self, names):
        """删除虚拟IP，支持单个和批量操作

        Args:
            names: VIP名称（字符串）或VIP名称列表（列表）
        """
        if isinstance(names, list):
            # 批量删除模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个删除模式
            self.click_action(names, "删除")

        # 确认删除
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vip_bind_eip(self, vip_address, network_type="public_net(基础版)"):
        """绑定公网IP

        Args:
            vip_address: 虚拟IP地址
            network_type: 公网网络类型名称
        """
        self.click_action(vip_address, "绑定公网IP")
        # 选择公网ip资源池
        dialog = self.get_by_role("dialog", name="绑定公网IP")
        dialog.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=network_type).click()
        # 随机选择一个EIP（假设列表中有数据）
        available_rows = dialog.get_by_role("row").filter(has_text="关闭").all()
        selected_row = random.choice(available_rows)
        selected_row.get_by_role("radio").click()
        ip_info = selected_row.get_by_role("cell")
        ip = ip_info.nth(1).text_content()
        self.dialog_confirm.click()
        return ip

    def vip_unbind_eip(self, vip_address):
        """解绑公网IP"""
        self.click_action(vip_address, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_text("确定").click()

    def vip_bind_instance(self, vip_address, instance_name):
        """虚拟IP绑定实例

        Args:
            vip_address: 虚拟IP地址
            instance_name: 实例名称
        """
        self.click_action(vip_address, "绑定实例")

        dialog = self.get_by_role("dialog", name="绑定实例")
        # 在弹窗内进行搜索，而不是使用全局的self.search
        dialog.get_by_role("textbox", name="请输入设备名称").fill(instance_name)
        dialog.get_by_text("搜索").click()
        self.wait_for_page_ready()
        # 选择搜索结果中的第一行
        dialog.get_by_role("row", name="ID 固定IP 连接设备 状态").locator("span").nth(1).click()
        dialog.get_by_text("确定").click()

    def vip_unbind_instance(self, vip_address, instance_name):
        """虚拟IP解绑实例"""

        self.click_action(vip_address, "解绑实例")

        dialog = self.get_by_role("dialog", name="解绑实例")
        dialog.get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=instance_name).click()
        dialog.get_by_text("确定").click()

    def _get_eip_column_name(self):
        """获取弹性公网IP列表中的公网IP列名"""
        for column_name in self.EIP_COLUMN_CANDIDATES:
            try:
                if self.get_column_data(column_name):
                    return column_name
            except Exception:
                continue

        for column_name in self.EIP_COLUMN_CANDIDATES:
            try:
                headers = self.table_headers
                if column_name in headers:
                    return column_name
            except Exception:
                continue

        raise AssertionError(f"未找到弹性公网IP列表列，候选列名: {self.EIP_COLUMN_CANDIDATES}")

    def _get_eip_list(self):
        """获取当前列表中的弹性公网IP"""
        column_name = self._get_eip_column_name()
        raw_values = self.get_column_data(column_name)
        eips = []
        for value in raw_values:
            match = re.search(r"((?:\d{1,3}\.){3}\d{1,3})(?!\.)", value)
            if match:
                eips.append(match.group())
        return eips

    def _get_eip_rows(self):
        """获取当前页弹性公网IP及其状态"""
        rows = []
        for row in self.table_rows:
            try:
                row_data = self.get_row_data_by_locator(row)
            except Exception:
                continue

            ip_value = ""
            status_value = ""
            for key, value in row_data.items():
                if "IP地址" in key:
                    ip_value = value
                if "状态" in key:
                    status_value = value

            match = re.search(r"((?:\d{1,3}\.){3}\d{1,3})(?!\.)", ip_value)
            if match:
                rows.append({"ip": match.group(), "status": status_value})
        return rows

    def _open_eip_allocate_dialog(self):
        """打开分配公网IP弹窗并返回弹窗定位器。"""
        self.get_by_text("分配公网IP").first.click()
        dialog = self.get_by_label("分配公网IP")
        expect(dialog).to_be_visible(timeout=8000)
        return dialog

    def _get_eip_allocate_ip_options(self, dialog):
        """获取分配公网IP弹窗中的可选IP列表。"""
        form_item = dialog.locator(".el-form-item").filter(has_text="IP").last
        ip_select = form_item.locator(".el-input").first
        expect(ip_select).to_be_visible(timeout=8000)
        ip_select.click()

        visible_ips = self.locator("body *").evaluate_all(
            """
            (elements) => {
                const isVisible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                const result = [];
                for (const el of elements) {
                    if (!isVisible(el)) continue;
                    const text = (el.textContent || '').trim();
                    if (/^(?:\\d{1,3}\\.){3}\\d{1,3}$/.test(text) && !result.includes(text)) {
                        result.push(text);
                    }
                }
                return result;
            }
            """
        )
        current_ips = set(self._get_eip_list())
        candidate_ips = [ip for ip in visible_ips if ip not in current_ips]
        return candidate_ips or visible_ips

    @submenu("弹性公网IPv4")
    def get_eip_list(self):
        """获取当前列表中的弹性公网IP"""
        return self._get_eip_list()

    @submenu("弹性公网IPv4")
    def eip_allocate(self, pool: str = "public_net(基础版)", count: int = 1, method: str = "快速选择", ip: str = None):
        """分配弹性公网IP并返回本次新分配的IP列表"""
        dialog = self._open_eip_allocate_dialog()

        dialog.get_by_placeholder("请选择").first.click()
        self.locator("li").filter(has_text=pool).click()

        dialog.get_by_placeholder("请选择").nth(1).click()
        self.locator("li").filter(has_text=re.compile(rf"^{count}$")).last.click()

        selected_ips = []
        if count == 1:
            if method == "快速选择":
                available_ips = self._get_eip_allocate_ip_options(dialog)
                assert available_ips, "快速选择模式下未获取到可选公网IP"
                selected_ip = ip or available_ips[0]
                if ip is None:
                    self.page.keyboard.press("ArrowDown")
                    self.page.keyboard.press("Enter")
                else:
                    option_locator = self.get_by_text(selected_ip, exact=True)
                    for i in range(option_locator.count()):
                        option = option_locator.nth(i)
                        if option.is_visible():
                            option.click(force=True)
                            break
                    else:
                        raise AssertionError(f"快速选择模式下未找到可点击的公网IP选项: {selected_ip}")
                selected_ips = [selected_ip]
            elif method == "手动输入":
                if ip is None:
                    dialog.get_by_text("快速选择", exact=True).click()
                    available_ips = self._get_eip_allocate_ip_options(dialog)
                    assert available_ips, "手动输入模式下未获取到可输入的公网IP"
                    ip = available_ips[0]
                    dialog.get_by_text("手动输入", exact=True).click()

                dialog.get_by_text("手动输入", exact=True).click()
                ip_loc = dialog.locator(".el-form-item").filter(has_text=re.compile(r"^\*?\s*IP")).get_by_role("textbox")
                ip_loc.clear()
                ip_loc.fill(ip)
                selected_ips = [ip]
            else:
                raise AssertionError(f"不支持的分配模式: {method}")

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()
        expect(dialog).not_to_be_visible(timeout=10000)

        if selected_ips:
            return selected_ips

        raise AssertionError("当前仅支持数量为1的弹性公网IP精确分配场景")

    @submenu("弹性公网IPv4")
    def eip_release(self, ips):
        """释放弹性公网IP，支持单个和批量操作"""
        if isinstance(ips, str):
            for action_name in ("释放公网IP", "释放"):
                try:
                    self.click_action(ips, action_name)
                    break
                except Exception:
                    continue
            else:
                raise AssertionError(f"未找到公网IP {ips} 的释放操作")
        else:
            self.select_rows_by_names(ips)
            batch_buttons = [
                self.get_by_text("批量释放公网IP", exact=True),
                self.get_by_text("批量释放公网IP").first,
            ]
            for btn in batch_buttons:
                try:
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        break
                except Exception:
                    continue
            else:
                raise AssertionError("未找到'批量释放公网IP'按钮")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("弹性公网IPv4")
    def assert_eip_list_contain(self, keyword: str, exact_match: bool = True):
        """断言弹性公网IP列表包含指定IP"""
        eips = self._get_eip_list()
        if exact_match:
            matched = keyword in eips
            assert matched, f"验证失败：期望弹性公网IP列表包含 '{keyword}'，实际: {eips}"
        else:
            matched = all(keyword in item for item in eips)
            assert matched, f"验证失败：期望弹性公网IP列表模糊包含 '{keyword}'，实际: {eips}"

    def port_create(self, vpc_name: str, subnet_name: str, ip_address: str = None,
                    quick_select=True, mac_address: str = None, port_security: bool = False):
        """
        在虚拟私有云中创建端口

        Args:
            vpc_name: 虚拟私有云名称（用于定位VPC列表行并进入详情页）
            subnet_name: 子网名称
            ip_address: IPv4地址
            quick_select: 是否快速选择可用IP地址（默认为True）
            mac_address: MAC地址
            port_security: 是否开启端口安全（默认为 False）
        """
        self.logger.info(f"开始在 VPC '{vpc_name}' 中创建端口")

        # 1. 查找VPC数据行并点击进入详情，切换到"端口"Tab
        self.get_row_by_name(vpc_name).locator("a").first.click()
        self.wait_for_page_ready()

        self.get_by_role("tab", name="端口").click()
        self.wait_for_page_ready()

        # 2. 点击新建端口 (✅ 复用 BasePage 的公共新建按钮)
        self.get_by_label("端口", exact=True).get_by_text("新建").click()
        self.wait_for_page_ready()

        # 3. 选择子网
        self.get_by_placeholder("请选择子网").click()
        self.get_by_title(subnet_name).click()

        # 4. 根据ip_address参数判断是否需要填写 IP 和 MAC
        if ip_address:
            self.locator("label").filter(has_text="手动分配").click()

            if quick_select:
                # 快速随机选择一个可用IP地址
                self.get_by_placeholder("请选择IPv4地址").click()
                self.page.wait_for_timeout(2000)
                self.page.wait_for_load_state("domcontentloaded")
                self.get_by_placeholder("请选择IPv4地址").fill(ip_address)
                self.page.wait_for_timeout(2000)
                self.get_by_text(ip_address, exact=True).click()
            else:
                # 手动输入IP地址
                self.locator("label").filter(has_text="手动输入").click()
                self.get_by_placeholder("请输入IP地址").fill(ip_address)

            if mac_address:
                self.get_by_placeholder("请按照6c:88:14:dd:25:59格式输入").fill(mac_address)

            if port_security:
                self.get_by_role("switch").locator("span").click()

        # 5. 提交保存
        self.get_by_label("新建端口").get_by_text("确定").click()
        # 也可以使用框架公共的确定按钮: self.dialog_confirm.click()
        self.wait_for_page_ready()

    def port_delete(self, names):
        """
        删除端口，支持单个和批量操作

        Args:
            names: 端口标识（字符串ip）或标识列表（列表）
        """
        self.logger.info(f"开始删除端口: {names}")

        if isinstance(names, list):
            # 批量删除模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个删除
            self.click_action(names, "删除")

        # 2. 弹窗确认删除
        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    def port_edit(self, old_ip: str, new_ip: str = None, new_mac: str = None):
        """
        修改端口

        Args:
            old_ip: 需要修改的端口的当前IP地址（用于在列表中定位行）
            new_ip: 新的IP地址（可选）
            new_mac: 新的MAC地址（可选）
        """
        self.logger.info(f"开始修改端口: {old_ip}")

        # 1. 在列表中找到该端口并点击"修改"
        self.click_action(old_ip, "编辑")

        # 2. 在弹窗中进行修改
        if new_ip:
            # 先清空输入框，确保输入新值
            self.get_by_placeholder("请输入IPv4地址").click()
            self.get_by_placeholder("请输入IPv4地址").fill(new_ip)
            self.page.wait_for_timeout(1000)
            
        if new_mac:
            # 匹配以 "请按照" 开头，并包含 "格式输入" 的占位符
            self.get_by_placeholder(re.compile(r"请按照.*格式输入")).click()
            self.get_by_placeholder(re.compile(r"请按照.*格式输入")).fill(new_mac)

        # 3. 提交修改
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def route_table_edit(self, new_name=None, new_desc=None):
        """修改路由表的名称和描述（需已在VPC详情页路由表Tab下）

        Args:
            new_name: 新路由表名称，如果为None则不修改
            new_desc: 新路由表描述，如果为None则不修改
        """
        # 点击路由表名称旁边的编辑图标
        self.locator(".el-icon-edit").click()
        self.wait_for_page_ready()

        # 修改名称
        if new_name is not None:
            name_input = self.get_by_label("编辑").locator("input[type=\"text\"]")
            name_input.fill(new_name)

        # 修改描述
        if new_desc is not None:
            self.locator("textarea").fill(new_desc)

        # 确认提交
        self.get_by_label("编辑").get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_create(self, vpc_name, dest_cidr, next_hop, next_hop_type="ECS实例", ip_version="IPv4", desc=None):
        """在VPC详情页的路由表tab中新建路由表规则
        
        Args:
            vpc_name: VPC名称
            dest_cidr: 目的地址，例如 "10.0.13.0/24"
            next_hop: 下一跳的具体值（如选填的具体实例的IP等）
            next_hop_type: 下一跳类型，默认为 "ECS实例"，可选 "虚拟IP" 等
            ip_version: IP版本，可选 "IPv4" 或 "IPv6"
            desc: 描述信息
        """
        # 进入 VPC 详情及路由表 tab 页
        self.get_row_by_name(vpc_name).locator("a").first.click()
        self.wait_for_page_ready()
        
        self.get_by_role("tab", name="路由表").click()
        self.wait_for_page_ready()

        # 点击新建路由表规则
        self.get_by_label("路由表", exact=True).get_by_text("新建").click()
        self.wait_for_page_ready()
        
        # 选择 IP版本
        if ip_version != "IPv4":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="IP版本")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=ip_version).click()
            
        # 填写目的地址
        self.get_by_placeholder(re.compile(r"必填")).fill(dest_cidr)
        
        # 选择下一跳类型
        if next_hop_type != "ECS实例":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="下一跳类型")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=re.compile(f"^{next_hop_type}$")).click()
            
        # 选择下一跳
        self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text=re.compile(r"^下一跳$"))).get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=next_hop).first.click()
        
        # 填写描述
        if desc:
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="描述")).locator("textarea").fill(desc)
            
        # 提交确认
        self.get_by_label("新建路由表规则").get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_edit(self, dest_cidr, new_dest_cidr=None, new_next_hop_type=None,
                        new_next_hop=None, new_ip_version=None, new_desc=None):
        """修改路由表规则（需已在VPC详情页路由表Tab下）

        Args:
            dest_cidr: 当前规则的目的地址，用于在列表中定位该行
            new_dest_cidr: 新目的地址，如果为None则不修改
            new_next_hop_type: 新下一跳类型，如果为None则不修改
            new_next_hop: 新下一跳，如果为None则不修改
            new_ip_version: 新IP版本（"IPv4"/"IPv6"），如果为None则不修改
            new_desc: 新描述，如果为None则不修改
        """
        # 点击该行的"修改"操作
        self.click_action(dest_cidr, "修改")
        self.wait_for_page_ready()

        dialog = self.get_by_label("修改路由表规则")

        # 修改 IP 版本
        if new_ip_version is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="IP版本")
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=new_ip_version).click()

        # 修改目的地址
        if new_dest_cidr is not None:
            self.get_by_placeholder(re.compile(r"必填")).fill(new_dest_cidr)

        # 修改下一跳类型
        if new_next_hop_type is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="下一跳类型")
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=re.compile(f"^{new_next_hop_type}$")).click()

        # 修改下一跳
        if new_next_hop is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text=re.compile(r"^下一跳$"))
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=new_next_hop).first.click()

        # 修改描述
        if new_desc is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="描述")
            ).locator("textarea").fill(new_desc)

        # 确认提交
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_delete(self, dest_cidrs):

        """删除路由表规则，支持单个和批量操作
        
        Args:
            dest_cidrs: 目的地址字符串，或目的地址列表
        """
        if isinstance(dest_cidrs, list):
            self.select_rows_by_names(dest_cidrs)
            self.btn_batch_delete.click()
        else:
            self.click_action(dest_cidrs, "删除")
            
        self.get_by_label("删除").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def nat_create(self, name, vpc_name, public_ip_pool="public_net(基础版)", eip=None, desc=""):
        """创建NAT网关
        
        Args:
            name: NAT网关名称
            vpc_name: 绑定的VPC名称
            public_ip_pool: 公网IP资源池
            eip: 弹性公网IP，如果未提供则随机选择一个可用的
            desc: 描述信息
        """
        # 点击新建按钮
        self.get_by_text("新建").click()
        self.wait_for_page_ready()
        
        # 填写名称
        self.locator("form div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)
        
        # 选择虚拟私有云
        self.get_by_role("radiogroup").locator("label").filter(has_text="虚拟私有云").click()
        self.get_by_placeholder("请选择虚拟私有云").click()
        # self.get_by_text(vpc_name, exact=True).click()
        self.locator("li").filter(has_text=vpc_name).click()
        
        # 选择公网IP资源池
        self.get_by_placeholder("请选择公网IP资源池").click()
        self.get_by_text(public_ip_pool).click()
        
        # 选择弹性公网IP
        self.get_by_placeholder("请选择弹性公网IP").click()
        if eip:
            self.get_by_text(eip).click()
        else:
            # 随机选择一个可用的弹性公网IP
            self.page.wait_for_timeout(1000)
            # 假设下拉列表的选项是 li 标签
            # 找到当前打开的下拉列表中的所有选项并随机选择一个
            options = self.page.locator(".el-select-dropdown:visible li.el-select-dropdown__item").all()
            if options:
                random.choice(options).click()
            else:
                self.logger.warning("未找到可用的弹性公网IP")
                # 如果找不到，随便点一下关闭下拉框
                self.page.mouse.click(0, 0)
                
        # 填写描述
        if desc:
            self.locator("textarea").fill(desc)
            
        # 点击确定
        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def nat_delete(self, names):
        """删除NAT网关，支持单个和批量操作
        
        Args:
            names: NAT网关名称（字符串）或名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")
            
        # 确认删除
        self.get_by_label("删除NAT网关").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def nat_edit(self, name, new_name=None, new_desc=None):
        """修改NAT网关名称和描述

        Args:
            name: 当前NAT网关名称（用于定位行）
            new_name: 新名称，如果为None则不修改
            new_desc: 新描述，如果为None则不修改
        """
        # 点击操作按钮中的"修改"
        self.click_action(name, "修改")
        self.wait_for_page_ready()

        # 修改名称
        if new_name is not None:
            name_input = self.locator("form").locator("input[type=\"text\"]")
            name_input.click()
            name_input.fill(new_name)

        # 修改描述
        if new_desc is not None:
            self.locator("textarea").click()
            self.locator("textarea").fill(new_desc)

        # 点击确定
        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def nat_unbind_eip(self, name):
        """解绑NAT网关的弹性公网IP

        Args:
            name: NAT网关名称

        Returns:
            str: 被解绑的 EIP 地址（从列表行读取）
        """
        # 先获取当前绑定的 EIP（用于后续断言）
        data = self.get_row_data(name)
        eip = data.get("弹性公网IP", "")

        # 点击"解绑公网IP"操作
        self.click_action(name, "解绑公网IP")

        # 在弹窗中确认
        self.get_by_label("解绑公网IP").get_by_text("确定").click()
        self.wait_for_page_ready()

        return eip

    @submenu("NAT网关")
    def nat_bind_eip(self, name, network_type="public_net(基础版)"):
        """为NAT网关绑定弹性公网IP

        Args:
            name: NAT网关名称
            network_type: 公网IP资源池名称，默认 "public_net(基础版)"

        Returns:
            str: 绑定的 EIP 地址
        """
        # 点击"绑定公网IP"操作
        self.click_action(name, "绑定公网IP")

        dialog = self.get_by_label("绑定公网IP")

        # 选择公网IP资源池
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network_type).click()

        # # 随机选择一个可用的 EIP（状态为"关闭"表示未绑定）
        # self.wait_for_page_ready()
        # available_rows = dialog.get_by_role("row").filter(has_text="关闭").all()
        # 使用 expect 显式等待 EIP 行加载，避免异步渲染导致的空列表竞争条件
        rows_locator = dialog.get_by_role("row").filter(has_text="关闭")
        expect(rows_locator.first).to_be_visible(timeout=10000)
        available_rows = rows_locator.all()
        if not available_rows:
            pytest.skip("当前环境无可用的弹性公网IP（状态为'关闭'）")
        selected_row = random.choice(available_rows)
        eip = selected_row.get_by_role("cell").nth(1).text_content().strip()
        selected_row.get_by_role("radio").click()

        # 确认绑定
        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

        return eip

    @submenu("NAT网关")
    def dnat_rule_create(self, nat_name, ext_port, subnet_cidr, protocol="TCP",
                         private_ip=None, int_port=None, desc=""):
        """在NAT网关详情页创建DNAT规则

        Args:
            nat_name: NAT网关名称（用于点击进入详情页）
            ext_port: 外部端口，范围 1~32767
            subnet_cidr: 私有子网 CIDR（用于在下拉框中定位子网选项）
            protocol: 协议类型，默认 "TCP"，可选 "UDP"/"ALL" 等
            private_ip: 私网IP，如果为 None 则选择第一个可用选项
            int_port: 内部端口，范围 1~65535，如果为 None 则不填
            desc: 描述信息
        """
        # 进入 NAT 网关详情页
        self.get_by_role("cell", name=nat_name).locator("a").click()
        self.wait_for_page_ready()

        # 切换到 DNAT 规则 Tab
        self.get_by_role("tab", name="DNAT规则").click()
        self.wait_for_page_ready()

        # 点击新建
        self.get_by_text("新建").click()
        self.wait_for_page_ready()

        # 选择协议
        self.locator("label").filter(has_text=protocol).click()

        # 填写外部端口
        self.get_by_placeholder("端口范围1~32767").fill(str(ext_port))

        # 选择私有子网（通过 CIDR 定位）
        subnet_row = self.locator("form div").filter(has_text=re.compile(r"私有子网"))
        subnet_row.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=subnet_cidr).first.click()

        # 选择私网IP
        ip_row = self.locator("form div").filter(has_text=re.compile(r"私网IP"))
        ip_row.get_by_placeholder("请选择").click()
        if private_ip:
            # 等待包含该IP的选项出现后点击
            ip_option = self.locator("li").filter(has_text=private_ip).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()
        else:
            # 等待并选择第一个可用选项
            first_option = self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").first
            expect(first_option).to_be_visible(timeout=8000)
            if not self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").count():
                pytest.skip("私网IP下拉无可用选项，请确认子网内有已创建的虚机")
            first_option.click()

        # 填写内部端口
        if int_port is not None:
            self.get_by_placeholder("端口范围1~65535").fill(str(int_port))

        # 填写描述
        if desc:
            self.locator("textarea").fill(desc)

        # 提交
        self.get_by_label("创建DNAT规则").get_by_text("确定").click()
        self.wait_for_page_ready()

    def _nat_open_detail_tab(self, nat_name, tab_name):
        """进入 NAT 网关详情并切换到指定 Tab。"""
        self.get_by_role("cell", name=nat_name).locator("a").click()
        self.wait_for_page_ready()
        self.get_by_role("tab", name=tab_name).click()
        self.wait_for_page_ready()

    def _select_form_option_by_label(self, form_root, label_pattern, option_text=None):
        """在表单中按标签选择下拉框选项，未指定 option_text 时默认选择第一个可用项。"""
        form_item = form_root.locator(".el-form-item").filter(
            has=self.locator("label").filter(has_text=label_pattern)
        )
        dropdown = form_item.get_by_placeholder("请选择")
        dropdown.click()

        if option_text:
            option = self.locator("li").filter(has_text=option_text).first
            expect(option).to_be_visible(timeout=8000)
            option.click()
            return option_text

        first_option = self.locator(".el-select-dropdown:visible li.el-select-dropdown__item").first
        expect(first_option).to_be_visible(timeout=8000)
        selected_text = first_option.text_content().strip()
        first_option.click()
        return selected_text

    def _snat_fill_source(self, dialog, source_type, source_value=None):
        """填写 SNAT 规则源地址。"""
        dialog.get_by_role("radio", name=source_type).click()

        if source_value is None:
            return

        if source_type == "私网IP" and isinstance(source_value, dict):
            dropdowns = dialog.get_by_placeholder("请选择")
            visible_dropdowns = [dropdowns.nth(i) for i in range(dropdowns.count()) if dropdowns.nth(i).is_visible()]

            if len(visible_dropdowns) < 2:
                raise AssertionError("私网IP类型未找到足够的下拉框，期望至少包含子网和私网IP两个选择框")

            visible_dropdowns[0].click()
            subnet_option = self.locator("li").filter(has_text=source_value["subnet_cidr"]).first
            expect(subnet_option).to_be_visible(timeout=8000)
            subnet_option.click()

            visible_dropdowns[1].click()
            ip_option = self.locator("li").filter(has_text=source_value["private_ip"]).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()
            return

        select_locator = dialog.get_by_placeholder("请选择")
        if select_locator.count() > 0:
            for i in range(select_locator.count()):
                dropdown = select_locator.nth(i)
                if dropdown.is_visible():
                    dropdown.click()
                    option = self.locator("li").filter(has_text=source_value).first
                    expect(option).to_be_visible(timeout=8000)
                    option.click()
                    return

        inputs = dialog.locator("input:not([disabled]):not([type='radio'])")
        for i in range(inputs.count()):
            input_box = inputs.nth(i)
            if input_box.is_visible():
                input_box.fill(source_value)
                return

        raise AssertionError(f"未找到可填写的SNAT源地址输入控件，source_type={source_type}, source_value={source_value}")

    @submenu("NAT网关")
    def snat_rule_create(self, nat_name, source_type="所有", source_value=None, desc=""):
        """在 NAT 网关详情页创建 SNAT 规则。"""
        self._nat_open_detail_tab(nat_name, "SNAT规则")

        self.get_by_text("新建").click()
        self.wait_for_page_ready()

        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"创建SNAT规则")).last

        self._snat_fill_source(dialog, source_type, source_value)

        if desc and dialog.locator("textarea").count() > 0:
            dialog.locator("textarea").fill(desc)

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def snat_rule_edit(self, nat_name, source_address, new_source_type=None, new_source_value=None, new_desc=None):
        """在 NAT 网关详情页修改 SNAT 规则。"""
        self._nat_open_detail_tab(nat_name, "SNAT规则")

        self.click_action(source_address, "修改")
        self.wait_for_page_ready()

        dialog = self.get_by_role("dialog").filter(has_text=re.compile(r"SNAT规则")).last

        if new_source_type is not None:
            self._snat_fill_source(dialog, new_source_type, new_source_value)

        if new_desc is not None and dialog.locator("textarea").count() > 0:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    def snat_rule_delete(self, source_addresses):
        """删除 SNAT 规则，支持单个和批量操作（需已在 NAT 网关详情页的 SNAT 规则 Tab 下）。"""
        if isinstance(source_addresses, list):
            self.select_rows_by_names(source_addresses)
            self.btn_batch_delete.click()
        else:
            self.click_action(str(source_addresses), "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("NAT网关")
    def dnat_rule_edit(self, nat_name, ext_port, new_ext_port=None, new_protocol=None,
                       new_private_ip=None, new_int_port=None, new_desc=None):
        """在NAT网关详情页修改DNAT规则

        Args:
            nat_name: NAT网关名称（用于点击进入详情页）
            ext_port: 需要修改的公网端口（用于定位规则行）
            new_ext_port: 新公网端口
            new_protocol: 新协议类型，如 "TCP"/"UDP"/"ALL"
            new_private_ip: 新私网IP
            new_int_port: 新内部端口
            new_desc: 新描述
        """
        # 进入 NAT 网关详情页
        self.get_by_role("cell", name=nat_name).locator("a").click()
        self.wait_for_page_ready()

        # 切换到 DNAT 规则 Tab
        self.get_by_role("tab", name="DNAT规则").click()
        self.wait_for_page_ready()

        # 打开修改弹窗
        self.click_action(str(ext_port), "修改")
        self.wait_for_page_ready()

        dialog = self.get_by_label("修改DNAT规则")

        # 修改协议
        if new_protocol:
            dialog.locator("label").filter(has_text=new_protocol).click()

        # 修改公网端口
        if new_ext_port is not None:
            dialog.get_by_placeholder("端口范围1~32767").fill(str(new_ext_port))

        # 修改私网IP
        if new_private_ip:
            ip_row = dialog.locator("form div").filter(has_text=re.compile(r"私网IP"))
            ip_row.get_by_placeholder("请选择").click()
            ip_option = self.locator("li").filter(has_text=new_private_ip).first
            expect(ip_option).to_be_visible(timeout=8000)
            ip_option.click()

        # 修改内部端口
        if new_int_port is not None:
            dialog.get_by_placeholder("端口范围1~65535").fill(str(new_int_port))

        # 修改描述
        if new_desc is not None:
            dialog.locator("textarea").fill(new_desc)

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    def dnat_rule_delete(self, ext_ports):
        """删除DNAT规则，支持单个和批量操作（需已在NAT网关详情页的DNAT规则Tab下）

        Args:
            ext_ports: 外部端口号（字符串/整数）或外部端口号列表（列表）
        """
        if isinstance(ext_ports, list):
            # 批量删除：将端口号转为字符串列表后勾选
            self.select_rows_by_names(ext_ports)
            self.btn_batch_delete.click()
        else:
            # 单条删除
            self.click_action(str(ext_ports), "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()
