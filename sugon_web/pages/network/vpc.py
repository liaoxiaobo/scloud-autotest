import ipaddress
import random
import re
import time

import pytest

from sugon_web.common.base import submenu


class VpcMixin:
    """虚拟私有云相关页面动作。"""

    @property
    def _input_name(self):
        """VPC名称输入框"""
        return self.get_by_placeholder("请输入名称")

    @property
    def _input_desc(self):
        """VPC描述输入框"""
        return self.locator("textarea").nth(0)

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
        """创建虚拟私有云"""
        self.btn_create.click()
        self.wait_for_page_ready()

        self._input_name.fill(name)
        self._input_desc.fill(desc)
        self.get_by_role("radio", name=network_type).click()

        if network_type == "Vlan":
            self.get_by_role("radio", name=gateway_mode).click()
            if vlan_id is not None:
                self._input_vlan_id.fill(str(vlan_id))

        if network_type in ["Vlan", "Flat"] and mac is not None:
            self.get_by_placeholder("默认mac地址aa:bb:cc:dd:ee:ff").fill(mac)

        if network_type == "Geneve" and enable_ipv6:
            ipv6_checkbox = self.get_by_text("开启IPv6", exact=True)
            if ipv6_checkbox.is_visible() and ipv6_checkbox.is_enabled():
                ipv6_checkbox.click()
            else:
                self.goto_service("虚拟私有云")
                pytest.skip("当前环境不支持双栈VPC")

        self._input_subnet_name.fill(subnet_name)
        self._input_subnet_desc.fill(subnet_desc)
        self._input_cidr.fill(cidr)

        if gateway_ip:
            self._input_gateway.fill(gateway_ip)
        else:
            ip = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
            self._input_gateway.fill(ip)

        acl_item = self.locator(".el-form-item").filter(has_text="关联ACL策略")
        acl_item.hover()
        clear_icon = acl_item.locator(".el-icon-circle-close")
        if clear_icon.is_visible():
            clear_icon.click()

        if acl_policy:
            self.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=acl_policy).click()

        if available_ip:
            self._input_available_ip.fill(available_ip)

        if dns:
            self._input_dns.fill(dns)

        self.btn_submit.click()
        self.wait_for_page_ready()

    @submenu("虚拟私有云")
    def vpc_delete(self, names):
        """删除虚拟私有云，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vpc_details_get(self, name) -> dict:
        """获取VPC详情页面的数据"""
        self.get_by_role("row", name=name).locator("a").click()

        common_fields = ["ID", "状态", "共享的", "MTU"]
        result = {}
        for field in common_fields:
            selector = f"label:has-text('{field}:') + .el-form-item__content p"
            value = self.page.text_content(selector).strip()
            result[field] = value

        name = self.page.text_content("label:has-text('名称:') + .el-form-item__content span").strip()
        result["名称"] = name

        vpc_type_text = self.page.text_content("span:has-text('虚拟私有云类型：')")
        vpc_type = vpc_type_text.split(":", 1)[-1].strip()
        result["虚拟私有云类型"] = vpc_type

        segment_id_text = self.page.text_content("span:has-text('段ID：')")
        segment_id = segment_id_text.split(":", 1)[-1].strip()
        result["段ID"] = segment_id

        return result

    @submenu("虚拟私有云")
    def vpc_edit(self, name, new_name=None, new_desc=None):
        """修改虚拟私有云"""
        self.click_action(name, "修改")

        if new_name:
            self.get_by_label("修改网络").locator("input[type=\"text\"]").fill(new_name)

        if new_desc:
            self.locator("textarea").fill(new_desc)

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vpc_generate_auth_code(self, name):
        """生成VPC授权码并复制"""
        self.click_action(name, "生成授权码")
        self.wait_for_page_ready()

        auth_code = self.get_by_text("eyJ").inner_text()
        self.get_by_text("复制").click()
        self.get_by_text("取 消").click()
        return auth_code

    @submenu("虚拟私有云")
    def subnet_create(self, vpc_name, subnet_name, cidr, desc="",
                      available_ip=None, dns=None, acl_policy=None, gateway_ip=None):
        """在VPC中新建子网"""
        self.click_action(vpc_name, "新建子网")
        self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(subnet_name)

        if desc:
            self.locator("div").filter(has_text=re.compile(r"^描述0/255$")).get_by_role("textbox").fill(desc)

        self._input_cidr.fill(cidr)

        if gateway_ip:
            self._input_gateway.fill(gateway_ip)

        acl_item = self.get_by_role("dialog", name="新建子网").locator(".el-form-item").filter(has_text="关联ACL策略")
        acl_select = acl_item.locator(".el-select")
        acl_select.hover()
        acl_select.locator(".el-icon-circle-close").click(timeout=1000)

        if acl_policy:
            self.get_by_role("dialog", name="新建子网").get_by_placeholder("请选择").click()
            self.get_by_text(acl_policy).click()

        if available_ip:
            self._input_available_ip.fill(available_ip)

        if dns:
            self._input_dns.fill(dns)

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_create_in_detail(self, vpc_name, subnet_name, cidr, desc="",
                                available_ip=None, dns=None, acl_policy=None, gateway_ip=None):
        """在VPC详情页的子网tab页中新建子网"""
        self.get_by_role("row", name=vpc_name).locator("a").click()
        self.wait_for_page_ready()

        self.get_by_role("tab", name="子网").click()
        self.wait_for_page_ready()

        new_button = self.get_by_label("子网", exact=True).get_by_text("新建")
        time.sleep(3)
        new_button.click()

        self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(subnet_name)

        if desc:
            self.locator("div").filter(has_text=re.compile(r"^描述0/255$")).get_by_role("textbox").fill(desc)

        self._input_cidr.fill(cidr)

        if gateway_ip:
            self._input_gateway.fill(gateway_ip)

        if available_ip:
            self._input_available_ip.fill(available_ip)

        if dns:
            self._input_dns.fill(dns)

        if acl_policy:
            acl_select = self.get_by_text("关联ACL策略").locator("..//..").get_by_role("combobox")
            acl_select.click()
            self.get_by_role("option", name=acl_policy).click()

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_delete(self, vpc_name, names):
        """在VPC详情页的子网tab页中删除子网，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def subnet_edit(self, subnet_name, new_name=None, new_desc=None, new_available_ip=None, new_dns=None):
        """在VPC详情页的子网tab页中修改子网"""
        self.click_action(subnet_name, "修改")
        self.wait_for_page_ready()

        if new_name is not None:
            self.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox").fill(new_name)

        if new_desc is not None:
            self.locator("div").filter(has_text=re.compile(r"^描述")).get_by_role("textbox").fill(new_desc)

        if new_available_ip is not None:
            self.get_by_role("textbox", name="选填（默认子网内全部IP可用）").fill(new_available_ip)

        if new_dns is not None:
            self.get_by_role("textbox", name="选填(默认:114.114.114.114)").fill(new_dns)

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vip_create(self, vpc_name, subnet_name, ip_address=None):
        """创建虚拟IP地址"""
        self.get_by_role("row", name=vpc_name).locator("a").click()
        self.get_by_role("tab", name="虚拟IP管理").click()
        self.wait_for_page_ready()

        self.get_by_text("申请虚拟IP地址").first.click()
        self.get_by_label("申请虚拟IP地址").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=subnet_name).click()

        if ip_address is not None:
            self.locator("label").filter(has_text="手动分配").click()
            last_segment = ip_address.split(".")[-1]
            self.get_by_label("申请虚拟IP地址").get_by_role("textbox").nth(4).fill(last_segment)

        self.get_by_label("申请虚拟IP地址").get_by_text("确定").click()
        self.wait_for_page_ready()

    def vip_delete(self, names):
        """删除虚拟IP，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def vip_bind_eip(self, vip_address, network_type="public_net(基础版)"):
        """绑定公网IP"""
        self.click_action(vip_address, "绑定公网IP")
        dialog = self.get_by_role("dialog", name="绑定公网IP")
        dialog.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=network_type).click()
        available_rows = dialog.get_by_role("row").filter(has_text="关闭").all()
        selected_row = random.choice(available_rows)
        ip_info = selected_row.get_by_role("cell")
        ip = ip_info.nth(1).text_content()
        self.dialog_confirm.click()
        return ip

    def vip_unbind_eip(self, vip_address):
        """解绑公网IP"""
        self.click_action(vip_address, "解绑公网IP")
        self.get_by_role("dialog", name="解除绑定公网IP").get_by_text("确定").click()

    def vip_bind_instance(self, vip_address, instance_name):
        """虚拟IP绑定实例"""
        self.click_action(vip_address, "绑定实例")

        dialog = self.get_by_role("dialog", name="绑定实例")
        dialog.get_by_role("textbox", name="请输入设备名称").fill(instance_name)
        dialog.get_by_text("搜索").click()
        self.wait_for_page_ready()

        rows = dialog.locator(".el-table__body-wrapper tr")
        if rows.count() == 0:
            raise AssertionError(f"未找到可绑定实例: {instance_name}，请确认实例与VIP位于同一VPC且已创建完成")

        target_row = rows.first
        checkbox = target_row.locator(".el-checkbox__inner").first
        if checkbox.count() == 0:
            raise AssertionError(f"未找到实例 '{instance_name}' 对应的可勾选项")

        checkbox.click()
        dialog.get_by_text("确定").click()

    def vip_unbind_instance(self, vip_address, instance_name):
        """虚拟IP解绑实例"""
        self.click_action(vip_address, "解绑实例")

        dialog = self.get_by_role("dialog", name="解绑实例")
        dialog.get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=instance_name).click()
        dialog.get_by_text("确定").click()

    def port_create(self, vpc_name: str, subnet_name: str, ip_address: str = None,
                    quick_select=True, mac_address: str = None, port_security: bool = False):
        """在虚拟私有云中创建端口"""
        self.logger.info(f"开始在 VPC '{vpc_name}' 中创建端口")

        self.get_row_by_name(vpc_name).locator("a").first.click()
        self.wait_for_page_ready()

        self.get_by_role("tab", name="端口").click()
        self.wait_for_page_ready()

        self.get_by_label("端口", exact=True).get_by_text("新建").click()
        self.wait_for_page_ready()

        self.get_by_placeholder("请选择子网").click()
        self.get_by_title(subnet_name).click()

        if ip_address:
            self.locator("label").filter(has_text="手动分配").click()

            if quick_select:
                self.get_by_placeholder("请选择IPv4地址").click()
                self.page.wait_for_timeout(2000)
                self.page.wait_for_load_state("domcontentloaded")
                self.get_by_placeholder("请选择IPv4地址").fill(ip_address)
                self.page.wait_for_timeout(2000)
                self.get_by_text(ip_address, exact=True).click()
            else:
                self.locator("label").filter(has_text="手动输入").click()
                self.get_by_placeholder("请输入IP地址").fill(ip_address)

            if mac_address:
                self.get_by_placeholder("请按照6c:88:14:dd:25:59格式输入").fill(mac_address)

            if port_security:
                self.get_by_role("switch").locator("span").click()

        self.get_by_label("新建端口").get_by_text("确定").click()
        self.wait_for_page_ready()

    def port_delete(self, names):
        """删除端口，支持单个和批量操作"""
        self.logger.info(f"开始删除端口: {names}")

        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    def port_edit(self, old_ip: str, new_ip: str = None, new_mac: str = None):
        """修改端口"""
        self.logger.info(f"开始修改端口: {old_ip}")
        self.click_action(old_ip, "编辑")

        if new_ip:
            self.get_by_placeholder("请输入IPv4地址").click()
            self.get_by_placeholder("请输入IPv4地址").fill(new_ip)
            self.page.wait_for_timeout(1000)

        if new_mac:
            self.get_by_placeholder(re.compile(r"请按照.*格式输入")).click()
            self.get_by_placeholder(re.compile(r"请按照.*格式输入")).fill(new_mac)

        self.dialog_confirm.click()
        self.wait_for_page_ready()

    def route_table_edit(self, new_name=None, new_desc=None):
        """修改路由表的名称和描述（需已在VPC详情页路由表Tab下）"""
        self.locator(".el-icon-edit").click()
        self.wait_for_page_ready()

        if new_name is not None:
            name_input = self.get_by_label("编辑").locator("input[type=\"text\"]")
            name_input.fill(new_name)

        if new_desc is not None:
            self.locator("textarea").fill(new_desc)

        self.get_by_label("编辑").get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_create(self, vpc_name, dest_cidr, next_hop, next_hop_type="ECS实例", ip_version="IPv4", desc=None):
        """在VPC详情页的路由表tab中新建路由表规则"""
        self.get_row_by_name(vpc_name).locator("a").first.click()
        self.wait_for_page_ready()

        self.get_by_role("tab", name="路由表").click()
        self.wait_for_page_ready()

        self.get_by_label("路由表", exact=True).get_by_text("新建").click()
        self.wait_for_page_ready()

        if ip_version != "IPv4":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="IP版本")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=ip_version).click()

        self.get_by_placeholder(re.compile(r"必填")).fill(dest_cidr)

        if next_hop_type != "ECS实例":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="下一跳类型")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=re.compile(f"^{next_hop_type}$")).click()

        self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text=re.compile(r"^下一跳$"))).get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=next_hop).first.click()

        if desc:
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="描述")).locator("textarea").fill(desc)

        self.get_by_label("新建路由表规则").get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_edit(self, dest_cidr, new_dest_cidr=None, new_next_hop_type=None,
                        new_next_hop=None, new_ip_version=None, new_desc=None):
        """修改路由表规则（需已在VPC详情页路由表Tab下）"""
        self.click_action(dest_cidr, "修改")
        self.wait_for_page_ready()

        dialog = self.get_by_label("修改路由表规则")

        if new_ip_version is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="IP版本")
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=new_ip_version).click()

        if new_dest_cidr is not None:
            self.get_by_placeholder(re.compile(r"必填")).fill(new_dest_cidr)

        if new_next_hop_type is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="下一跳类型")
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=re.compile(f"^{new_next_hop_type}$")).click()

        if new_next_hop is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text=re.compile(r"^下一跳$"))
            ).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=new_next_hop).first.click()

        if new_desc is not None:
            dialog.locator(".el-form-item").filter(
                has=self.locator("label").filter(has_text="描述")
            ).locator("textarea").fill(new_desc)

        dialog.get_by_text("确定").click()
        self.wait_for_page_ready()

    def route_rule_delete(self, dest_cidrs):
        """删除路由表规则，支持单个和批量操作"""
        if isinstance(dest_cidrs, list):
            self.select_rows_by_names(dest_cidrs)
            self.btn_batch_delete.click()
        else:
            self.click_action(dest_cidrs, "删除")

        self.get_by_label("删除").get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()
