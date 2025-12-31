import re
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
                   gateway_ip=None, available_ip=None, dns=None, vlan_id=None):
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
    def vpc_delete(self, name):
        """删除虚拟私有云

        Args:
            name: VPC名称
        """
        # 点击操作按钮
        self.click_dropdown_option(name, "删除")

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
        self.click_dropdown_option(name, "修改")

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
                          available_ip=None, dns=None, acl_policy=None):
        """在VPC中新建子网

        Args:
            vpc_name: VPC名称（用于定位VPC）
            subnet_name: 子网名称
            cidr: 子网CIDR，如 "10.0.100.0/24"
            desc: 子网描述，默认为空
            available_ip: 可用IP范围，如 "10.0.100.10-10.0.100.100"，如果为None则使用默认
            dns: DNS服务器地址，如果为None则使用默认
            acl_policy: 关联的ACL策略名称，如果为None则不选择
        """

        # 点击VPC行的操作按钮并选择"新建子网"
        self.click_dropdown_option(vpc_name, "新建子网")

        # 填写子网名称
        self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(subnet_name)

        # 填写子网描述
        if desc:
            self.locator("div").filter(has_text=re.compile(r"^描述0/255$")).get_by_role("textbox").fill(desc)

        # 填写CIDR
        self._input_cidr.fill(cidr)

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





