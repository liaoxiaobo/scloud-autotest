import ipaddress
import random
import re
import time

import pytest

from sugon_web.common.playwright import expect
from sugon_web.common.base import BasePage, submenu


class VpcMixin(BasePage):
    """虚拟私有云相关页面动作。"""

    def _ensure_vpc_network_list(self):
        """确保当前位于虚拟私有云列表页。

        VPC 服务的概览页（/vpc/#/vpc-overview）没有左侧菜单，
        goto_submenu 无法通过菜单导航到列表页。此方法在
        goto_submenu 失败时直接导航到列表页 URL 作为兜底。
        """
        self.goto_service(self.service_name)
        try:
            self.goto_submenu("虚拟私有云")
        except Exception:
            pass
        # Fallback: 如果当前不在列表页，直接导航到列表页
        if "vpc-network-list" not in self.page.url:
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/vpc-network-list")
            self.wait_for_page_ready()

    @property
    def _input_name(self):
        """VPC名称输入框"""
        return self.get_by_placeholder("请输入名称")

    @property
    def _input_desc(self):
        """VPC描述输入框"""
        return self.locator("textarea").nth(0)

    def _select_cluster(self, cluster_name="Autotest"):
        """选择VPC所属集群。"""
        self.get_by_role("textbox", name="请选择集群").click()
        # 限定在下拉框内点击，避免匹配到页面其他同名元素
        dropdown = self.page.locator(".el-select-dropdown:visible").first
        expect(dropdown).to_be_visible(timeout=10000)
        dropdown.get_by_text(cluster_name, exact=True).click()

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
        return self.get_by_placeholder("请输入1~16777215之间的正整数")

    @submenu("虚拟私有云")
    def vpc_create(self, name, subnet_name, cidr, desc="", subnet_desc="",
                   network_type="Geneve", cluster="Autotest", physical_network="physnet1",
                   ipv6_pool="provider-ipv6(基础版)（2000:c00", gateway_mode="分布式网关", gateway_ip=None, available_ip=None,
                   dns=None, vlan_id=None, mac=None, enable_ipv6=False, acl_policy=None):
        """创建虚拟私有云"""
        # 兜底：若子菜单导航将页面带到了概览页，确保回到列表页
        if "vpc-network-list" not in self.page.url:
            self._ensure_vpc_network_list()
        self.btn_create.click()

        self._input_name.fill(name)
        self._select_cluster(cluster)
        self._input_desc.fill(desc)
        self.get_by_role("radio", name=network_type).click()

        if network_type == "Vlan":
            self.get_by_role("radio", name=gateway_mode).click()
            if vlan_id is not None:
                self._input_vlan_id.fill(str(vlan_id))

        if network_type in ["Vlan", "Flat"] and mac is not None:
            self.get_by_placeholder("默认mac地址aa:bb:cc:dd:ee:ff").fill(mac)

        if network_type in ["Vlan", "Flat"] and physical_network is not None:
            self.get_by_role("textbox", name="请选择二层网络").click()
            self.get_by_role("listitem").filter(has_text=physical_network).click()

        if network_type == "Geneve" and enable_ipv6 and ipv6_pool:
            ipv6_checkbox = self.get_by_text("开启IPv6", exact=True)
            if ipv6_checkbox.is_visible() and ipv6_checkbox.is_enabled():
                ipv6_checkbox.click()
                self.get_by_role("textbox", name="请选择").nth(3).click()
                self.get_by_text(ipv6_pool).click()
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
        self.logger.info(f"创建虚拟私有云成功, VPC: {name}, 子网: {subnet_name}, acl: {acl_policy}")

    @submenu("虚拟私有云")
    def vpc_delete(self, names):
        """删除虚拟私有云，支持单个和批量操作"""
        # 兜底：若子菜单导航将页面带到了概览页，确保回到列表页
        if "vpc-network-list" not in self.page.url:
            self._ensure_vpc_network_list()
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()

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

    def goto_vpc_detail(self, name: str):
        """导航到VPC详情页（点击VPC名称链接）。

        Args:
            name: VPC名称。
        """
        self.get_row_by_name(name).locator("a").first.click()
        self.wait_for_page_ready()

    def goto_route_tab(self):
        """在VPC详情页点击路由表tab。"""
        self.get_by_role("tab", name="路由表").click()
        self.wait_for_page_ready()

    @submenu("虚拟私有云")
    def vpc_edit(self, name, new_name=None, new_desc=None):
        """修改虚拟私有云"""
        self.click_action(name, "修改")

        if new_name:
            self.get_by_label("修改网络").locator("input[type=\"text\"]").fill(new_name)

        if new_desc:
            self.locator("textarea").fill(new_desc)

        self.dialog_confirm.click()

    @submenu("虚拟私有云")
    def vpc_generate_auth_code(self, name):
        """生成VPC授权码并复制"""
        self.click_action(name, "生成授权码")

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
        self.logger.info(f"vpc {vpc_name}新建子网: {subnet_name}, acl: {acl_policy}")

    @submenu("虚拟私有云")
    def subnet_create_in_detail(self, vpc_name, subnet_name, cidr, desc="",
                                available_ip=None, dns=None, acl_policy=None, gateway_ip=None):
        """在VPC详情页的子网tab页中新建子网"""
        self.get_by_role("row", name=vpc_name).locator("a").click()

        self.get_by_role("tab", name="子网").click()

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

    def subnet_delete(self, vpc_name, names):
        """在VPC详情页的子网tab页中删除子网，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.dialog_confirm.click()

    def subnet_edit(self, subnet_name, new_name=None, new_desc=None, new_available_ip=None, new_dns=None):
        """在VPC详情页的子网tab页中修改子网"""
        self.click_action(subnet_name, "修改")
        dialog = self.get_by_role("dialog", name="修改子网")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^子网名称$")).get_by_role("textbox")
        expect(name_input).to_have_value(subnet_name, timeout=10000)

        if new_name is not None:
            name_input.fill(new_name)

        if new_desc is not None:
            dialog.locator("div").filter(has_text=re.compile(r"^描述")).get_by_role("textbox").fill(new_desc)

        if new_available_ip is not None:
            dialog.get_by_role("textbox", name="选填（默认子网内全部IP可用）").fill(new_available_ip)

        if new_dns is not None:
            dialog.get_by_role("textbox", name="选填(默认:114.114.114.114)").fill(new_dns)

        self.dialog_confirm.click()

    @submenu("虚拟私有云")
    def vip_create(self, vpc_name, subnet_name, ip_address=None):
        """创建虚拟IP地址"""
        self.get_by_role("row", name=vpc_name).locator("a").click()
        self.get_by_role("tab", name="虚拟IP管理").click()

        # GUI模式下：点击VPC名称后鼠标停留在链接上，会触发Element UI tooltip遮挡按钮
        # 按Escape关闭可能存在的tooltip，同时确保鼠标不在触发tooltip的元素上
        self.page.keyboard.press("Escape")
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)
        self.get_by_text("申请虚拟IP地址").first.click()
        self.get_by_label("申请虚拟IP地址").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=subnet_name).click()

        if ip_address is not None:
            self.locator("label").filter(has_text="手动分配").click()
            # last_segment = ip_address.split(".")[-1]
            last_segment = ip_address
            self.get_by_role("textbox", name="例如：").fill(last_segment)

        self.get_by_label("申请虚拟IP地址").get_by_text("确定").click()

    def vip_delete(self, names):
        """删除虚拟IP，支持单个和批量操作"""
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        # 等待可能的确认对话框出现，然后点击确认
        # VIP删除有时有确认对话框，有时直接删除（取决于是否绑定资源）
        self.page.wait_for_timeout(2500)
        from playwright.sync_api import expect

        # GUI模式下：鼠标可能停留在操作按钮上触发tooltip，遮挡确认弹窗内的按钮
        # 先按Escape关闭可能存在的tooltip，同时确保鼠标不在触发tooltip的元素上
        self.page.keyboard.press("Escape")
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)

        # 产品使用了多种对话框组件：
        # 1. el-dialog（有role="dialog"）
        # 2. el-message-box（class="el-message-box"）
        # 3. sugon-dialog（class="sugon-dialog"）
        # 同时查找这三种对话框
        dialog = None

        # 1. 查找 role="dialog" 的对话框（el-dialog）
        all_dialogs = self.page.get_by_role("dialog").all()
        if all_dialogs:
            dialog = all_dialogs[-1]
            self.logger.info(f"VIP删除：找到 el-dialog 对话框")

        # 2. 查找 el-message-box（Element UI MessageBox组件）
        if not dialog:
            msg_box = self.page.locator(".el-message-box").first
            try:
                msg_box.wait_for(state="visible", timeout=3000)
                dialog = msg_box
                self.logger.info(f"VIP删除：找到 el-message-box 对话框")
            except Exception:
                pass

        # 3. 查找 sugon-dialog（产品自定义对话框组件）
        # 注意：sugon-dialog 可能有动画过渡，is_visible 在动画期间可能返回 false
        # 使用 wait_for(state="visible") 更可靠
        if not dialog:
            sugon_dialog = self.page.locator(".sugon-dialog").first
            try:
                sugon_dialog.wait_for(state="visible", timeout=5000)
                dialog = sugon_dialog
                self.logger.info(f"VIP删除：找到 sugon-dialog 对话框")
            except Exception:
                pass

        # 4. 如果对话框存在，二次确认其可见
        if dialog:
            try:
                expect(dialog).to_be_visible(timeout=3000)
            except AssertionError:
                self.logger.warning("VIP删除：对话框未在3秒内变为可见，视为无对话框")
                dialog = None

        if dialog:
            # 有确认对话框，尝试多种方式定位确认按钮
            # 覆盖 el-dialog 和 el-message-box 两种结构的按钮
            confirm_locators = [
                # 通过 role + name 匹配（el-dialog 方式）
                dialog.get_by_role("button", name=re.compile(r"确定|删除|确认")),
                # 在对话框内部查找 button 元素，filter 过滤文本
                dialog.locator("button").filter(has_text=re.compile(r"确定|删除|确认")),
                # 精确匹配 "确定" 文本
                dialog.get_by_text("确定", exact=True),
                # 精确匹配 "删除" 文本
                dialog.get_by_text("删除", exact=True),
                # 通过 span 过滤文本（按钮内部可能是 span 包裹文本）
                dialog.locator("span").filter(has_text=re.compile(r"确定|删除|确认")),
                # el-message-box 的按钮结构：.el-message-box__btns > button
                dialog.locator(".el-message-box__btns button"),
                # el-dialog 的按钮结构：.el-dialog__footer button
                dialog.locator(".el-dialog__footer button"),
                # cloud-button-btn 类名
                dialog.locator(".cloud-button-btn"),
            ]
            clicked = False
            for confirm_btn in confirm_locators:
                try:
                    count = confirm_btn.count()
                    if count > 0:
                        for i in range(count):
                            btn = confirm_btn.nth(i)
                            if btn.is_visible():
                                btn.click()
                                clicked = True
                                self.logger.info(f"VIP删除：通过选择器 {i} 点击确认按钮成功")
                                break
                        if clicked:
                            break
                except Exception as e:
                    self.logger.debug(f"VIP删除：选择器尝试失败: {e}")
                    continue

            if not clicked:
                # 最后尝试：遍历对话框内所有可见的 button 元素，点击最后一个（通常是确认）
                try:
                    buttons = dialog.locator("button").all()
                    self.logger.info(f"VIP删除：对话框内共找到 {len(buttons)} 个 button 元素")
                    for btn in reversed(buttons):
                        if btn.is_visible():
                            btn.click()
                            clicked = True
                            self.logger.info("VIP删除：点击对话框内最后一个可见button成功")
                            break
                except Exception as e:
                    self.logger.warning(f"VIP删除：fallback按钮点击失败: {e}")

            if not clicked:
                # 终极fallback：通过JavaScript点击对话框内的确认按钮
                try:
                    self.page.evaluate("""
                        () => {
                            // 尝试找到确认按钮并点击
                            const dialog = document.querySelector('.el-message-box, [role="dialog"]');
                            if (dialog) {
                                const buttons = dialog.querySelectorAll('button');
                                for (let i = buttons.length - 1; i >= 0; i--) {
                                    const text = buttons[i].textContent || buttons[i].innerText || '';
                                    if (text.includes('确定') || text.includes('删除') || text.includes('确认')) {
                                        buttons[i].click();
                                        return true;
                                    }
                                }
                                // 如果没找到文本匹配的，点击最后一个按钮
                                if (buttons.length > 0) {
                                    buttons[buttons.length - 1].click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    clicked = True
                    self.logger.info("VIP删除：通过JavaScript点击确认按钮成功")
                except Exception as e:
                    self.logger.warning(f"VIP删除：JavaScript点击失败: {e}")

            if not clicked:
                raise AssertionError("VIP删除确认对话框出现，但未能定位到确认按钮")
            # 等待对话框关闭
            expect(dialog).not_to_be_visible(timeout=5000)
        else:
            self.logger.info("VIP删除：未检测到确认对话框，尝试直接验证删除结果")

        # 验证VIP已从列表中删除（最多等待5秒）
        for _ in range(10):
            self.page.wait_for_timeout(500)
            try:
                self.get_row_by_name(names)
            except Exception:
                self.logger.info(f"VIP {names} 删除成功")
                return
        raise AssertionError(f"VIP删除未生效，{names}仍在列表中")

    def vip_bind_eip(self, vip_address, network_type="public_net(基础版)", eip_ip=None):
        """绑定公网IP。

        Args:
            vip_address: 虚拟IP地址。
            network_type: 资源池名称，默认public_net(基础版)。
            eip_ip: 指定要绑定的弹性公网IP地址。为None时随机选择可用IP。

        Returns:
            str: 绑定的弹性公网IP地址。
        """
        self.click_action(vip_address, "绑定公网IP")
        dialog = self.get_by_role("dialog", name="绑定公网IP")
        dialog.get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=network_type).click()

        if eip_ip:
            # 在表格中查找指定IP地址的行，支持分页/滚动
            for page_attempt in range(10):
                rows = dialog.get_by_role("row").all()
                for row in rows:
                    cells = row.get_by_role("cell").all_text_contents()
                    if any(eip_ip in cell for cell in cells):
                        row.get_by_role("radio").click()
                        self.dialog_confirm.click()
                        self.logger.info(f"VIP {vip_address} 绑定公网IP: {eip_ip}")
                        return eip_ip
                # 尝试多种方式翻页/加载更多
                clicked = False
                # 策略1: 标准 Element UI 分页下一页按钮
                for selector in [
                    ".el-pagination .btn-next:not([disabled])",
                    ".el-pagination__next:not([disabled])",
                    ".pagination .next:not([disabled])",
                    ".btn-next:not(.is-disabled)",
                    "button[class*='next']:not([disabled])",
                ]:
                    try:
                        btns = dialog.locator(selector).all()
                        for btn in btns:
                            if btn.is_visible() and btn.is_enabled():
                                btn.click()
                                self.page.wait_for_timeout(1500)
                                clicked = True
                                break
                        if clicked:
                            break
                    except Exception:
                        continue
                # 策略2: 尝试点击页码数字（当前页+1）
                if not clicked:
                    try:
                        current_page = dialog.locator(".el-pagination .active, .el-pager .active, .pagination .active").first
                        if current_page.count() > 0:
                            current_text = current_page.text_content() or "1"
                            next_page_num = str(int(current_text) + 1)
                            next_page = dialog.locator(".el-pager li, .pagination .page-item").filter(
                                has_text=re.compile(rf"^{re.escape(next_page_num)}$")
                            ).first
                            if next_page.count() > 0 and next_page.is_visible():
                                next_page.click()
                                self.page.wait_for_timeout(1500)
                                clicked = True
                    except Exception:
                        pass
                # 策略3: 尝试滚动表格主体加载更多
                if not clicked:
                    try:
                        body = dialog.locator(".el-table__body-wrapper, .table-body").first
                        if body.count() > 0:
                            body.evaluate("el => el.scrollTop = el.scrollHeight")
                            self.page.wait_for_timeout(1500)
                            clicked = True
                    except Exception:
                        pass
                if not clicked:
                    break
            raise AssertionError(f"[FieldAssertion] 未在绑定公网IP弹窗中找到指定FIP: {eip_ip}")

        available_rows = dialog.get_by_role("row").filter(has_text="关闭").all()
        if not available_rows:
            raise AssertionError("当前环境无可用的弹性公网IP（状态为'关闭'）")
        selected_row = random.choice(available_rows)
        selected_row.get_by_role("radio").click()
        ip_info = selected_row.get_by_role("cell")
        ip = ip_info.nth(1).text_content().strip()
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

    @submenu("虚拟私有云")
    def port_create(self, vpc_name: str, subnet_name: str, ip_address: str = None,
                    quick_select=True, mac_address: str = None, port_security: bool = False):
        """在虚拟私有云中创建端口"""
        self.logger.info(f"开始在 VPC '{vpc_name}' 中创建端口")

        self.goto_detail_page(vpc_name, tab_name="端口")

        self.get_by_label("端口", exact=True).get_by_text("新建", exact=True).click()
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

    def port_delete(self, names):
        """删除端口，支持单个和批量操作"""
        self.logger.info(f"开始删除端口: {names}")

        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")

        self.locator("#cloud-container-content").get_by_text("确定", exact=True).click()

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

    def route_table_edit(self, new_name=None, new_desc=None):
        """修改路由表的名称和描述（需已在VPC详情页路由表Tab下）"""
        self.locator(".el-icon-edit").click()

        if new_name is not None:
            name_input = self.get_by_label("编辑").locator("input[type=\"text\"]")
            name_input.fill(new_name)

        if new_desc is not None:
            self.locator("textarea").fill(new_desc)

        self.get_by_label("编辑").get_by_text("确定").click()

    @submenu("虚拟私有云")
    def route_rule_create(self, vpc_name, dest_cidr, next_hop, next_hop_type="ECS实例", ip_version="IPv4", desc=None):
        """在VPC详情页的路由表tab中新建路由表规则"""
        self.get_row_by_name(vpc_name).locator("a").first.click()

        self.get_by_role("tab", name="路由表").click()

        self.get_by_label("路由表", exact=True).get_by_text("新建").click()

        if ip_version != "IPv4":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="IP版本")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=ip_version).click()

        self.get_by_placeholder(re.compile(r"必填")).fill(dest_cidr)
        self.page.wait_for_timeout(1000)

        if next_hop_type != "ECS实例":
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="下一跳类型")).get_by_placeholder("请选择").click()
            self.locator("li").filter(has_text=re.compile(f"^{next_hop_type}$")).click()
            self.page.wait_for_timeout(2000)

        self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text=re.compile(r"^下一跳$"))).get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=next_hop).first.click()

        if desc:
            self.locator(".el-form-item").filter(has=self.locator("label").filter(has_text="描述")).locator("textarea").fill(desc)

        self.get_by_label("新建路由表规则").get_by_text("确定").click()

    def route_rule_edit(self, dest_cidr, new_dest_cidr=None, new_next_hop_type=None,
                        new_next_hop=None, new_ip_version=None, new_desc=None):
        """修改路由表规则（需已在VPC详情页路由表Tab下）"""
        self.click_action(dest_cidr, "修改")

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
            self.page.wait_for_timeout(2000)

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

    def route_rule_delete(self, dest_cidrs):
        """删除路由表规则，支持单个和批量操作"""
        if isinstance(dest_cidrs, list):
            self.select_rows_by_names(dest_cidrs)
            self.btn_batch_delete.click()
        else:
            self.click_action(dest_cidrs, "删除")

        self.get_by_label("删除").get_by_text("确定", exact=True).click()
