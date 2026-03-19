import re
import time
import random
import pytest
from playwright.sync_api import Page, expect
from sugon_web.common.base import BasePage, submenu
import ipaddress


class VpcPage(BasePage):
    """虚拟私有云页面类"""

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

        if acl_policy:
            # 选择前先清空
            acl_box = self.locator(".el-form-item").filter(has_text="关联ACL策略")
            acl_box.hover()
            # 悬停后出现清除图标
            clear_icon = acl_box.locator(".el-icon-circle-close")
            clear_icon.click()

            # 选择ACL策略
            self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=acl_policy).click()
        else:
            acl_box = self.locator(".el-form-item").filter(has_text="关联ACL策略")
            acl_box.hover()
            # 悬停后出现清除图标
            clear_icon = acl_box.locator(".el-icon-circle-close")
            clear_icon.click()

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
            self.click_dropdown_option(names, "删除")

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
        self.click_option(name, "修改")

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
        self.click_dropdown_option(name, "生成授权码")

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
        self.click_option(vpc_name, "新建子网")

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
            self.click_option(names, "删除", t_type="body")

        # 确认删除
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
            self.click_dropdown_option(names, "删除")

        # 确认删除
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vip_bind_eip(self, vip_address, network_type="public_net(基础版)"):
        """绑定公网IP

        Args:
            vip_address: 虚拟IP地址
            network_type: 公网网络类型名称
        """
        self.click_option(vip_address, "绑定公网IP")
        # 选择公网ip资源池
        dialog = self.get_by_role("dialog", name="绑定公网IP")
        dialog.get_by_placeholder("请选择").click()
        dialog.get_by_text(network_type).click()
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
        self.click_dropdown_option(vip_address, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_text("确定").click()

    def vip_bind_instance(self, vip_address, instance_name):
        """虚拟IP绑定实例

        Args:
            vip_address: 虚拟IP地址
            instance_name: 实例名称
        """
        self.click_option(vip_address, "绑定实例")

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

        self.click_dropdown_option(vip_address, "解绑实例")

        dialog = self.get_by_role("dialog", name="解绑实例")
        dialog.get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=instance_name).click()
        dialog.get_by_text("确定").click()
