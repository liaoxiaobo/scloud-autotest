"""云专线DC (Dedicated Connect) 页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log


class DcMixin(BasePage):
    """云专线DC模块页面对象，封装物理连接等页面的交互操作。"""

    service_name = "云专线DC"

    def _ensure_physical_connection_list(self):
        """确保当前位于物理连接列表页。"""
        self.goto_service(self.service_name)
        try:
            self.goto_submenu("物理连接")
        except Exception:
            # 菜单重复时 fallback 到 URL 导航
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/physical-connection-list")
            self.wait_for_page_ready()
        self.wait_for_page_ready()

        # 等待页面 loading 消失
        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass

    def _is_list_page(self):
        """判断当前是否显示列表页（有新建按钮）。"""
        try:
            create_btn = self.page.locator("#cloud-container-content").get_by_text("新建", exact=True)
            return create_btn.count() > 0 and create_btn.first.is_visible()
        except Exception:
            return False

    def _is_view_dc_page(self):
        """判断当前是否显示 viewDc 空状态页。"""
        try:
            # viewDc 页面有"创建物理连接"按钮
            btn = self.page.locator("#cloud-container-content").get_by_text("创建物理连接", exact=True)
            return btn.count() > 0 and btn.first.is_visible()
        except Exception:
            return False

    def _navigate_to_create_page(self):
        """导航到物理连接创建页面。兼容列表页弹窗和 viewDc 独立页面两种方式。"""
        # 先尝试列表页的"新建"按钮（弹窗方式）
        if self._is_list_page():
            self.logger.info("检测到列表页，使用弹窗方式创建")
            create_btn = self.page.locator("#cloud-container-content").get_by_text("新建", exact=True)
            create_btn.first.click()
            self.wait_for_page_ready()
            return "dialog"

        # 尝试 viewDc 的"创建物理连接"按钮（独立页面方式）
        if self._is_view_dc_page():
            self.logger.info("检测到 viewDc 空状态页，直接导航到创建页面")
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/physical-connection-add")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(2000)
            return "page"

        # 兜底：直接 URL 导航到创建页面
        self.logger.info("未检测到创建入口，直接导航到创建页面")
        base_url = self.page.url.split("#")[0]
        self.page.goto(f"{base_url}#/physical-connection-add")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        return "page"

    def _get_form_context(self, mode):
        """获取表单定位上下文。弹窗模式下限制在弹窗内，页面模式下在表单容器内。"""
        if mode == "dialog":
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            return dialog
        # 独立页面模式：使用 .add-box 或 body 作为上下文
        add_box = self.page.locator(".add-box")
        if add_box.count() > 0:
            return add_box
        return self.page.locator("body")

    @submenu("物理连接")
    def dc_physical_connection_create(
        self,
        name: str,
        operator: str,
        port_type: str,
        contact_name: str,
        contact_phone: str,
        contact_email: str,
        ha_enable: bool = False,
        machine_room: str = "",
        description: str = "",
    ):
        """创建物理连接。

        Args:
            name: 物理连接名称，长度2~64字符，支持中文、英文、数字、横线。
            operator: 运营商，可选值：telecom(电信)、mobile(移动)、unicom(联通)、other(其他)。
            port_type: 端口类型，可选值：1GE 单模光口、10GE 单模光口、40GE 单模光口、100GE 单模光口。
            contact_name: 联系人姓名。
            contact_phone: 联系人手机号。
            contact_email: 联系人Email。
            ha_enable: 是否开启HA，默认False（关闭）。
            machine_room: 机房地址，可选。
            description: 描述，可选。
        """
        with allure_step_log("进入物理连接创建页面"):
            mode = self._navigate_to_create_page()

        ctx = self._get_form_context(mode)

        with allure_step_log("填写物理连接名称"):
            name_input = ctx.get_by_placeholder("请输入物理连接名称")
            name_input.fill(name)

        with allure_step_log("选择运营商"):
            operator_select = ctx.get_by_placeholder("请选择运营商")
            operator_select.click()
            self.page.wait_for_timeout(500)
            operator_labels = {
                "telecom": "电信",
                "mobile": "移动",
                "unicom": "联通",
                "other": "其他",
            }
            operator_label = operator_labels.get(operator, operator)
            # 下拉选项可能被 teleport 到 body，使用可见下拉菜单上下文定位
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=5000)
            dropdown.get_by_text(operator_label, exact=True).click()

        with allure_step_log("选择端口类型"):
            port_select = ctx.get_by_placeholder("请选择端口类型")
            port_select.click()
            self.page.wait_for_timeout(500)
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=5000)
            dropdown.get_by_text(port_type, exact=True).click()

        # HA开关条件渲染
        try:
            ha_switch = ctx.locator(".el-switch")
            if ha_switch.count() > 0 and ha_switch.first.is_visible():
                with allure_step_log("设置HA开关"):
                    is_checked = ha_switch.first.locator("input").is_checked()
                    if ha_enable and not is_checked:
                        ha_switch.first.click()
                    elif not ha_enable and is_checked:
                        ha_switch.first.click()
        except Exception:
            self.logger.info("HA开关未显示，跳过HA设置")

        if machine_room:
            with allure_step_log("填写机房地址"):
                room_input = ctx.get_by_placeholder("请输入机房地址")
                room_input.fill(machine_room)

        if description:
            with allure_step_log("填写描述"):
                desc_input = ctx.locator("textarea")
                if desc_input.count() > 0:
                    desc_input.first.fill(description)

        with allure_step_log("填写联系人姓名"):
            contact_name_input = ctx.get_by_placeholder("请输入联系人姓名")
            contact_name_input.fill(contact_name)

        with allure_step_log("填写联系人手机"):
            contact_phone_input = ctx.get_by_placeholder("请输入联系人手机")
            contact_phone_input.fill(contact_phone)

        with allure_step_log("填写联系人Email"):
            contact_email_input = ctx.get_by_placeholder("请输入联系人Email")
            contact_email_input.fill(contact_email)

        with allure_step_log("点击立即创建按钮"):
            submit_btn = ctx.get_by_text("立即创建", exact=True)
            submit_btn.click()

    @submenu("物理连接")
    def dc_physical_connection_terminate(self, name: str):
        """注销指定物理连接。

        Args:
            name: 需要注销的物理连接名称。
        """
        with allure_step_log(f"点击物理连接 '{name}' 的注销操作"):
            self.click_action(name, "注销")

        with allure_step_log("确认注销"):
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            self.dialog_confirm.click()

    def open_detail_by_name(self, name: str):
        """点击列表中的实例名称，进入详情页（独立页面）。

        Args:
            name: 实例名称。
        """
        with allure_step_log(f"点击实例名称 '{name}' 进入详情页"):
            self.page.locator("#cloud-container-content").get_by_text(name, exact=True).first.click()
            # 等待页面导航到详情页
            self.page.wait_for_url("**/details-physical-connection-list/**", timeout=15000)
            self.wait_for_page_ready()
            self.page.wait_for_timeout(2000)

    def get_detail_field_value(self, label: str) -> str:
        """从详情页中获取指定标签对应的值。

        详情页使用 cl-item-col 组件展示字段，通过 label 文本定位。

        Args:
            label: 字段标签，如"物理连接名称"、"运营商"、"端口类型"等。

        Returns:
            str: 字段值文本。
        """
        # 在详情页中查找包含 label 的元素
        detail_box = self.page.locator(".dc-detail-box")
        expect(detail_box).to_be_visible(timeout=10000)

        # 策略1: 查找 .cloud-item-label 文本匹配的元素
        try:
            labels = detail_box.locator(".cloud-item-label")
            for i in range(labels.count()):
                lbl = labels.nth(i)
                try:
                    text = lbl.inner_text(timeout=2000)
                    if label in text:
                        # 获取父元素的文本，去掉 label 部分
                        parent = lbl.locator("..")
                        full_text = parent.inner_text()
                        return full_text.replace(text, "").strip()
                except Exception:
                    continue
        except Exception:
            pass

        # 策略2: 使用 get_by_text 查找 label，然后获取父元素的文本
        try:
            label_elem = detail_box.get_by_text(label, exact=True)
            if label_elem.count() > 0:
                parent = label_elem.first.locator("..")
                full_text = parent.inner_text()
                return full_text.replace(label, "").strip()
        except Exception:
            pass

        # 策略3: 遍历所有包含标签和值的 dl/dt/dd 结构
        try:
            dls = detail_box.locator("dl")
            for i in range(dls.count()):
                dl = dls.nth(i)
                dt = dl.locator("dt")
                if dt.count() > 0:
                    dt_text = dt.inner_text()
                    if label in dt_text:
                        dd = dl.locator("dd")
                        if dd.count() > 0:
                            return dd.inner_text().strip()
        except Exception:
            pass

        raise AssertionError(f"详情页中未找到字段: {label}")

    def _open_approve_dialog(self, name: str):
        """打开指定物理连接的审批弹窗。

        Args:
            name: 需要审批的物理连接名称。
        """
        with allure_step_log(f"打开物理连接 '{name}' 的审批弹窗"):
            self.click_action(name, "审批")
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            # 等待弹窗标题确认
            expect(dialog.get_by_text("审批", exact=True)).to_be_visible(timeout=5000)
            return dialog

    def _select_approve_status(self, dialog, status: str):
        """在审批弹窗中选择审批状态。

        Args:
            dialog: 审批弹窗定位器。
            status: 审批状态，"DONE"（通过）或 "REJECTED"（驳回）。
        """
        with allure_step_log(f"选择审批状态: {status}"):
            radio_group = dialog.locator(".el-radio-group")
            expect(radio_group).to_be_visible(timeout=5000)
            if status == "DONE":
                radio_group.get_by_text("通过", exact=True).click()
            else:
                radio_group.get_by_text("驳回", exact=True).click()
            self.page.wait_for_timeout(500)

    def _fill_vlan_code(self, dialog, vlan_code: str):
        """在审批弹窗中填写VLAN号。

        Args:
            dialog: 审批弹窗定位器。
            vlan_code: VLAN号，1~4094的正整数。
        """
        with allure_step_log(f"填写VLAN号: {vlan_code}"):
            vlan_input = dialog.get_by_placeholder("请输入VLAN号")
            expect(vlan_input).to_be_visible(timeout=5000)
            vlan_input.fill(str(vlan_code))

    def _select_cluster(self, dialog, cluster_name: str = "Autotest"):
        """在审批弹窗中选择集群。

        优先选择指定名称的集群，若不存在则选择第一个可用集群。

        Args:
            dialog: 审批弹窗定位器。
            cluster_name: 首选集群名称，默认为 "Autotest"。

        Returns:
            str: 实际选择的集群显示名称。
        """
        with allure_step_log(f"选择集群（首选: {cluster_name}）"):
            cluster_select = dialog.get_by_placeholder("请选择集群")
            expect(cluster_select).to_be_visible(timeout=5000)
            cluster_select.click()
            self.page.wait_for_timeout(1000)

            # 等待下拉选项加载
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=10000)

            options = dropdown.locator(".el-select-dropdown__item")
            expect(options.first).to_be_visible(timeout=10000)

            # 优先匹配指定集群名
            for i in range(options.count()):
                option = options.nth(i)
                text = option.inner_text()
                if cluster_name in text:
                    option.click()
                    self.page.wait_for_timeout(500)
                    return text.strip()

            # 未匹配到指定集群，选择第一个可用选项
            first_option = options.first
            first_text = first_option.inner_text().strip()
            first_option.click()
            self.page.wait_for_timeout(500)
            return first_text

    @submenu("物理连接")
    def dc_physical_connection_approve(
        self,
        name: str,
        status: str = "DONE",
        vlan_code: str = "",
        cluster_name: str = "Autotest",
    ):
        """审批指定物理连接。

        Args:
            name: 需要审批的物理连接名称。
            status: 审批状态，"DONE"（通过，默认）或 "REJECTED"（驳回）。
            vlan_code: VLAN号，status为"DONE"时必须提供，1~4094的正整数。
            cluster_name: 首选集群名称，status为"DONE"时使用，默认为"Autotest"。
        """
        dialog = self._open_approve_dialog(name)

        self._select_approve_status(dialog, status)

        if status == "DONE":
            if vlan_code:
                self._fill_vlan_code(dialog, vlan_code)
            if cluster_name:
                selected = self._select_cluster(dialog, cluster_name)
                self.logger.info(f"实际选择的集群: {selected}")

        with allure_step_log("点击确定提交审批"):
            submit_btn = dialog.get_by_text("确定", exact=True)
            submit_btn.click()

    # ─────────────────────────────────────────────
    # 虚拟网关
    # ─────────────────────────────────────────────

    def _ensure_virtual_gateway_list(self):
        """确保当前位于虚拟网关列表页。"""
        self.goto_service(self.service_name)
        try:
            self.goto_submenu("虚拟网关")
        except Exception:
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/virtual-gateway-list")
            self.wait_for_page_ready()
        self.wait_for_page_ready()

        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass

    @submenu("虚拟网关")
    def virtual_gateway_create(
        self,
        name: str,
        association_mode: str = "vpc",
        vpc_name: str = "",
        er_name: str = "",
        bgp_asn: str = "",
    ):
        """创建虚拟网关。

        Args:
            name: 虚拟网关名称，长度2~64字符，支持中文、英文、数字、横线。
            association_mode: 关联模式，可选"vpc"（虚拟私有云，默认）或"er"（企业路由器）。
            vpc_name: 关联的虚拟私有云名称（association_mode="vpc"时必填）。
            er_name: 关联的企业路由器名称（association_mode="er"时必填）。
            bgp_asn: BGP ASN号，可选。填写后虚拟网关支持BGP路由模式。
        """
        with allure_step_log("点击新建按钮打开虚拟网关创建弹窗"):
            self.btn_create.click()

        with allure_step_log("获取弹窗上下文"):
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog.get_by_text("新建虚拟网关", exact=True)).to_be_visible(timeout=5000)

        with allure_step_log("填写虚拟网关名称"):
            name_input = dialog.get_by_placeholder("请输入名称")
            name_input.fill(name)

        with allure_step_log("选择关联模式"):
            radio_group = dialog.locator(".el-radio-group")
            if association_mode == "vpc":
                radio_btn = radio_group.get_by_text("虚拟私有云", exact=True)
            else:
                radio_btn = radio_group.get_by_text("企业路由器", exact=True)
            radio_btn.click()
            self.page.wait_for_timeout(500)

        if association_mode == "vpc" and vpc_name:
            with allure_step_log("选择虚拟私有云"):
                vpc_select = dialog.get_by_placeholder("请选择虚拟私有云")
                vpc_select.click()
                self.page.wait_for_timeout(500)
                dropdown = self.page.locator(".el-select-dropdown:visible")
                expect(dropdown).to_be_visible(timeout=5000)
                dropdown.get_by_text(vpc_name, exact=True).click()
                self.page.wait_for_timeout(500)

        if association_mode == "er" and er_name:
            with allure_step_log("选择企业路由器"):
                er_select = dialog.get_by_placeholder("请选择企业路由器")
                er_select.click()
                self.page.wait_for_timeout(500)
                dropdown = self.page.locator(".el-select-dropdown:visible")
                expect(dropdown).to_be_visible(timeout=5000)
                dropdown.get_by_text(er_name, exact=True).click()
                self.page.wait_for_timeout(500)

        if bgp_asn:
            with allure_step_log(f"填写BGP ASN: {bgp_asn}"):
                bgp_input = dialog.get_by_placeholder("请输入BGP ASN")
                bgp_input.fill(bgp_asn)
                self.page.wait_for_timeout(300)

        with allure_step_log("点击立即创建按钮"):
            submit_btn = dialog.get_by_text("立即创建", exact=True)
            submit_btn.click()

    @submenu("虚拟网关")
    def virtual_gateway_delete(self, name: str):
        """删除指定虚拟网关。

        Args:
            name: 需要删除的虚拟网关名称。
        """
        with allure_step_log(f"删除虚拟网关 '{name}'"):
            self.click_action(name, "删除")

        with allure_step_log("确认删除"):
            expect(self.dialog_confirm).to_be_visible(timeout=10000)
            self.dialog_confirm.click()

    # ─────────────────────────────────────────────
    # 虚拟网关 - 修改
    # ─────────────────────────────────────────────

    @submenu("虚拟网关")
    def virtual_gateway_edit(
        self,
        name: str,
        new_name: str = "",
        description: str = "",
    ):
        """修改指定虚拟网关。

        打开修改弹窗，验证关联模式、虚拟私有云、BGP ASN字段为禁用状态，
        修改名称和/或描述，提交修改。

        Args:
            name: 需要修改的虚拟网关名称。
            new_name: 新的虚拟网关名称，为空则不修改名称。
            description: 新的描述，为空则不修改描述。
        """
        with allure_step_log(f"点击虚拟网关 '{name}' 的修改按钮"):
            self.click_action(name, "修改")

        with allure_step_log("等待修改弹窗出现并加载数据"):
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog.get_by_text("修改虚拟网关", exact=True)).to_be_visible(timeout=5000)
            ctx = dialog.locator(".el-dialog__body")
            expect(ctx).to_be_visible(timeout=5000)
            # 等待表单数据加载完成（名称输入框有值）
            name_input = ctx.get_by_placeholder("请输入名称")
            expect(name_input).to_have_value(re.compile(r".+"), timeout=10000)
            self.page.wait_for_timeout(2000)

        with allure_step_log("验证只读字段（关联模式、虚拟私有云、BGP ASN）"):
            # 关联模式 - el-radio-button 均含 is-disabled 类
            type_buttons = ctx.locator(".el-radio-group .el-radio-button")
            expect(type_buttons.first).to_be_visible(timeout=5000)
            for i in range(type_buttons.count()):
                btn = type_buttons.nth(i)
                classes = btn.get_attribute("class") or ""
                assert "is-disabled" in classes, f"关联模式第{i + 1}个选项应为禁用状态，实际 class: {classes}"

            # 虚拟私有云 - 检查内部 input 是否 disabled
            vpc_item = ctx.locator(".el-form-item").filter(has_text="虚拟私有云")
            if vpc_item.count() > 0 and vpc_item.first.is_visible():
                vpc_input = vpc_item.first.locator("input")
                if vpc_input.count() > 0:
                    disabled = vpc_input.first.get_attribute("disabled")
                    assert disabled is not None, "虚拟私有云字段应为禁用状态"

            # BGP ASN - 检查内部 input 是否 disabled
            bgp_item = ctx.locator(".el-form-item").filter(has_text="BGP ASN")
            if bgp_item.count() > 0 and bgp_item.first.is_visible():
                bgp_input = bgp_item.first.locator("input")
                if bgp_input.count() > 0:
                    disabled = bgp_input.first.get_attribute("disabled")
                    assert disabled is not None, "BGP ASN字段应为禁用状态"

        if new_name:
            with allure_step_log(f"修改虚拟网关名称为: {new_name}"):
                name_input = ctx.get_by_placeholder("请输入名称")
                expect(name_input).to_be_visible(timeout=5000)
                name_input.clear()
                name_input.fill(new_name)

        if description:
            with allure_step_log(f"修改描述为: {description}"):
                desc_input = ctx.locator("textarea").first
                expect(desc_input).to_be_visible(timeout=5000)
                desc_input.clear()
                desc_input.fill(description)

        with allure_step_log("点击立即修改按钮"):
            submit_btn = dialog.get_by_text("立即修改", exact=True)
            expect(submit_btn).to_be_visible(timeout=5000)
            submit_btn.click()

    # ─────────────────────────────────────────────
    # 虚拟接口 - 修改
    # ─────────────────────────────────────────────

    def _ensure_virtual_interface_modify_page(self):
        """确保当前位于虚拟接口修改页面。"""
        self.page.wait_for_url("**/virtual-interface-modify**", timeout=15000)
        self.wait_for_page_ready()
        ctx = self.page.locator(".add-box")
        expect(ctx).to_be_visible(timeout=10000)
        return ctx

    @submenu("虚拟接口")
    def virtual_interface_edit(
        self,
        name: str,
        new_name: str = "",
        description: str = "",
    ):
        """修改指定虚拟接口。

        打开修改页面，验证物理连接、虚拟网关、虚拟子网、本端网关、远端网关、路由模式字段为禁用状态，
        修改名称和/或描述，提交修改。

        Args:
            name: 需要修改的虚拟接口名称。
            new_name: 新的虚拟接口名称，为空则不修改名称。
            description: 新的描述，为空则不修改描述。
        """
        with allure_step_log(f"点击虚拟接口 '{name}' 的修改按钮"):
            self.click_action(name, "修改")

        ctx = self._ensure_virtual_interface_modify_page()

        with allure_step_log("验证只读字段"):
            # 物理连接 - 检查内部 input 是否 disabled
            pc_item = ctx.locator(".el-form-item").filter(has_text="物理连接")
            if pc_item.count() > 0 and pc_item.first.is_visible():
                pc_input = pc_item.first.locator("input")
                if pc_input.count() > 0:
                    disabled = pc_input.first.get_attribute("disabled")
                    assert disabled is not None, "物理连接字段应为禁用状态"

            # 虚拟网关 - 检查内部 input 是否 disabled
            vgw_item = ctx.locator(".el-form-item").filter(has_text="虚拟网关")
            if vgw_item.count() > 0 and vgw_item.first.is_visible():
                vgw_input = vgw_item.first.locator("input")
                if vgw_input.count() > 0:
                    disabled = vgw_input.first.get_attribute("disabled")
                    assert disabled is not None, "虚拟网关字段应为禁用状态"

            # 虚拟子网 - 检查内部 input 是否 disabled（条件渲染）
            subnet_item = ctx.locator(".el-form-item").filter(has_text="虚拟子网")
            if subnet_item.count() > 0 and subnet_item.first.is_visible():
                subnet_input = subnet_item.first.locator("input")
                if subnet_input.count() > 0:
                    disabled = subnet_input.first.get_attribute("disabled")
                    assert disabled is not None, "虚拟子网字段应为禁用状态"

            # 本端网关 - 5个 ip_input 全部 disabled
            local_gw_items = ctx.locator(".el-form-item").filter(has_text="本端网关")
            if local_gw_items.count() > 0:
                local_inputs = local_gw_items.first.locator(".ip_input input")
                for i in range(min(local_inputs.count(), 5)):
                    inp = local_inputs.nth(i)
                    assert inp.is_disabled(), f"本端网关第{i+1}个输入框应为禁用状态"

            # 远端网关 - 5个 ip_input 全部 disabled
            remote_gw_items = ctx.locator(".el-form-item").filter(has_text="远端网关")
            if remote_gw_items.count() > 0:
                remote_inputs = remote_gw_items.first.locator(".ip_input input")
                for i in range(min(remote_inputs.count(), 5)):
                    inp = remote_inputs.nth(i)
                    assert inp.is_disabled(), f"远端网关第{i+1}个输入框应为禁用状态"

            # 路由模式 - 检查 el-radio-button 是否含 is-disabled 类
            route_buttons = ctx.locator(".el-radio-group .el-radio-button")
            if route_buttons.count() > 0:
                for i in range(route_buttons.count()):
                    btn = route_buttons.nth(i)
                    classes = btn.get_attribute("class") or ""
                    assert "is-disabled" in classes, f"路由模式第{i+1}个选项应为禁用状态，实际 class: {classes}"

        if new_name:
            with allure_step_log(f"修改虚拟接口名称为: {new_name}"):
                name_input = ctx.get_by_placeholder("请输入名称")
                expect(name_input).to_be_visible(timeout=5000)
                name_input.clear()
                name_input.fill(new_name)

        if description:
            with allure_step_log(f"修改描述为: {description}"):
                # 虚拟接口修改页面有多个textarea（远端子网和描述），描述是最后一个
                textareas = ctx.locator("textarea")
                desc_input = textareas.last
                expect(desc_input).to_be_visible(timeout=5000)
                desc_input.clear()
                desc_input.fill(description)

        with allure_step_log("点击立即修改按钮"):
            submit_btn = ctx.get_by_text("立即修改", exact=True)
            expect(submit_btn).to_be_visible(timeout=5000)
            submit_btn.click()

    # ─────────────────────────────────────────────
    # 虚拟接口
    # ─────────────────────────────────────────────

    def _ensure_virtual_interface_list(self):
        """确保当前位于虚拟接口列表页。"""
        self.goto_service(self.service_name)
        try:
            self.goto_submenu("虚拟接口")
        except Exception:
            base_url = self.page.url.split("#")[0]
            self.page.goto(f"{base_url}#/virtual-interface-list")
            self.wait_for_page_ready()
        self.wait_for_page_ready()

        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass

    def _fill_ip_inputs(self, ctx, ip_cidr: str, is_local: bool = True):
        """在表单中填写IP网关输入（5个输入框：IP四段+掩码）。

        Args:
            ctx: 表单上下文定位器。
            ip_cidr: IP地址及掩码，格式如 "11.22.0.2/24"。
            is_local: True表示本端网关，False表示远端网关。
        """
        ip_part, mask_part = ip_cidr.split("/")
        ip_segments = ip_part.split(".")
        parts = ip_segments + [mask_part]

        # 获取所有 .ip_input 元素（Element UI el-input 外层 div），前5个是本端网关，后5个是远端网关
        ip_inputs = ctx.locator(".ip_input")
        start_index = 0 if is_local else 5

        for i, value in enumerate(parts):
            # el-input 的实际 input 在内部
            actual_input = ip_inputs.nth(start_index + i).locator("input").first
            actual_input.fill(str(value))

    @submenu("虚拟接口")
    def virtual_interface_create(
        self,
        name: str,
        physical_connection_name: str,
        virtual_gateway_name: str,
        local_gateway: str,
        remote_gateway: str,
        route_mode: str = "static",
        remote_subnet: str = "",
        local_subnet: str = "",
        subnet_index: int = 0,
        bgp_peer_asn: str = "",
        bgp_md5_password: str = "",
    ):
        """创建虚拟接口。

        Args:
            name: 虚拟接口名称，长度2~64字符，支持中文、英文、数字、横线。
            physical_connection_name: 物理连接名称。
            virtual_gateway_name: 虚拟网关名称。
            local_gateway: 本端网关（云端侧），格式如 "11.22.0.2/24"。
            remote_gateway: 远端网关（用户侧），格式如 "11.22.0.3/24"。
            route_mode: 路由模式，"static"（静态路由，默认）或 "bgp"。
            remote_subnet: 远端子网，路由模式为static时必填，如 "123.12.0.0/24"。
            local_subnet: 本端子网，虚拟网关为ER关联模式时必填，如 "13.34.34.0/24"。
            subnet_index: 虚拟子网选择索引，默认0（第1个）。
            bgp_peer_asn: BGP邻居AS号，路由模式为bgp时必填，如 "65533"。
            bgp_md5_password: BGP MD5认证密码，路由模式为bgp时必填，如 "123123"。
        """
        with allure_step_log("点击新建按钮进入虚拟接口创建页面"):
            self.btn_create.click()
            self.page.wait_for_url("**/virtual-interface-add**", timeout=15000)
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)

        ctx = self.page.locator(".add-box")
        expect(ctx).to_be_visible(timeout=10000)

        with allure_step_log("填写虚拟接口名称"):
            name_input = ctx.get_by_placeholder("请输入名称")
            name_input.fill(name)

        with allure_step_log("选择物理连接"):
            pc_select = ctx.get_by_placeholder("请选择物理连接")
            pc_select.click()
            self.page.wait_for_timeout(500)
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=5000)
            option = dropdown.locator(".el-select-dropdown__item").filter(has_text=physical_connection_name).first
            expect(option).to_be_visible(timeout=5000)
            option.click()
            self.page.wait_for_timeout(500)

        with allure_step_log("选择虚拟网关"):
            vgw_select = ctx.get_by_placeholder("请选择虚拟网关")
            vgw_select.click()
            self.page.wait_for_timeout(500)
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=5000)
            option = dropdown.locator(".el-select-dropdown__item").filter(has_text=virtual_gateway_name).first
            expect(option).to_be_visible(timeout=5000)
            option.click()
            self.page.wait_for_timeout(1000)

        # 虚拟子网条件渲染：ER关联模式的虚拟网关可能不显示此字段
        subnet_select = ctx.get_by_placeholder("请选择虚拟子网")
        if subnet_select.count() > 0 and subnet_select.first.is_visible():
            with allure_step_log("选择虚拟子网"):
                subnet_select.click()
                self.page.wait_for_timeout(500)
                dropdown = self.page.locator(".el-select-dropdown:visible")
                expect(dropdown).to_be_visible(timeout=5000)
                options = dropdown.locator(".el-select-dropdown__item")
                if options.count() > 0:
                    options.nth(subnet_index).click()
                self.page.wait_for_timeout(500)
                # 点击空白处关闭下拉框
                ctx.click()
                self.page.wait_for_timeout(300)

        with allure_step_log(f"填写本端网关: {local_gateway}"):
            self._fill_ip_inputs(ctx, local_gateway, is_local=True)

        with allure_step_log(f"填写远端网关: {remote_gateway}"):
            self._fill_ip_inputs(ctx, remote_gateway, is_local=False)

        with allure_step_log(f"选择路由模式: {route_mode}"):
            radio_group = ctx.locator(".el-radio-group")
            if route_mode == "static":
                radio_group.get_by_text("静态路由", exact=True).click()
            else:
                radio_group.get_by_text("BGP", exact=True).click()
            self.page.wait_for_timeout(500)

        # ER关联模式下需要填写本端子网
        if local_subnet:
            with allure_step_log(f"填写本端子网: {local_subnet}"):
                local_subnet_item = ctx.locator(".el-form-item").filter(has_text="本端子网")
                if local_subnet_item.count() > 0 and local_subnet_item.first.is_visible():
                    local_subnet_textarea = local_subnet_item.first.locator("textarea").first
                    expect(local_subnet_textarea).to_be_visible(timeout=5000)
                    local_subnet_textarea.fill(local_subnet)

        if route_mode == "static" and remote_subnet:
            with allure_step_log(f"填写远端子网: {remote_subnet}"):
                # 远端子网textarea通过label精确定位，避免与描述/本端子网textarea混淆
                remote_subnet_item = ctx.locator(".el-form-item").filter(has_text="远端子网")
                expect(remote_subnet_item.first).to_be_visible(timeout=5000)
                remote_subnet_textarea = remote_subnet_item.first.locator("textarea").first
                expect(remote_subnet_textarea).to_be_visible(timeout=5000)
                remote_subnet_textarea.fill(remote_subnet)

        if route_mode == "bgp" and bgp_peer_asn:
            with allure_step_log(f"填写BGP邻居AS号: {bgp_peer_asn}"):
                bgp_as_input = ctx.get_by_placeholder("请输入BGP邻居AS号")
                expect(bgp_as_input).to_be_visible(timeout=5000)
                bgp_as_input.fill(bgp_peer_asn)
                self.page.wait_for_timeout(300)

        if route_mode == "bgp" and bgp_md5_password:
            with allure_step_log("填写BGP MD5认证密码"):
                bgp_md5_input = ctx.get_by_placeholder("请输入BGP MD5认证密码")
                expect(bgp_md5_input).to_be_visible(timeout=5000)
                bgp_md5_input.fill(bgp_md5_password)
                self.page.wait_for_timeout(300)

        with allure_step_log("点击立即创建按钮"):
            submit_btn = ctx.get_by_text("立即创建", exact=True)
            submit_btn.click()

    @submenu("虚拟接口")
    def virtual_interface_connectivity_test(self, name: str, dest_ip: str) -> str:
        """对指定虚拟接口执行互通测试。

        在虚拟接口列表页点击操作栏的"互通测试"按钮，在弹窗中输入目的地址并执行测试，
        等待测试完成后返回测试进度结果文本。

        Args:
            name: 虚拟接口名称。
            dest_ip: 目的地址IP，如 "123.12.0.10"。

        Returns:
            str: 测试结果文本，"连通成功"或"连通失败"。
        """
        with allure_step_log(f"点击虚拟接口 '{name}' 的互通测试按钮"):
            self.click_action(name, "互通测试")

        with allure_step_log("等待互通测试弹窗出现"):
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog.get_by_text("互通测试", exact=False)).to_be_visible(timeout=5000)
            ctx = dialog.locator(".el-dialog__body")
            expect(ctx).to_be_visible(timeout=5000)

        with allure_step_log(f"输入目的地址: {dest_ip}"):
            dest_input = ctx.get_by_placeholder("示例：10.10.0.0")
            expect(dest_input).to_be_visible(timeout=5000)
            dest_input.clear()
            dest_input.fill(dest_ip)
            self.page.wait_for_timeout(300)

        with allure_step_log("点击测试按钮"):
            test_btn = ctx.get_by_text("测试", exact=True)
            expect(test_btn).to_be_visible(timeout=5000)
            test_btn.click()

        with allure_step_log("等待测试进度完成"):
            # 等待进度条达到100%且结果显示
            # 进度条使用 el-progress，结果文本在进度条旁边
            # 结果文本为 "连通成功" 或 "连通失败"
            result_span = ctx.locator(".result-span")
            # 轮询等待结果出现，最长等待30秒
            import time
            start = time.monotonic()
            while time.monotonic() - start < 30:
                if result_span.count() > 0 and result_span.first.is_visible():
                    result_text = result_span.first.inner_text().strip()
                    if result_text in ("连通成功", "连通失败"):
                        self.logger.info(f"互通测试结果: {result_text}")
                        return result_text
                self.page.wait_for_timeout(1000)

            raise TimeoutError(f"互通测试在30秒内未完成，未获取到结果")

    @submenu("虚拟接口")
    def virtual_interface_delete(self, name: str):
        """删除指定虚拟接口。

        Args:
            name: 需要删除的虚拟接口名称。
        """
        with allure_step_log(f"删除虚拟接口 '{name}'"):
            self.click_action(name, "删除")

        with allure_step_log("确认删除"):
            expect(self.dialog_confirm).to_be_visible(timeout=10000)
            self.dialog_confirm.click()

    def wait_for_physical_connection_status(
        self,
        name: str,
        expected_status: str = "办结",
        expected_vm_status: str = "运行中",
        timeout: int = 600,
        interval: int = 10,
    ):
        """轮询等待物理连接状态达到预期。

        审批通过后，后台需要时间创建资源。此方法通过轮询列表页检查状态变化。

        Args:
            name: 物理连接名称。
            expected_status: 期望的状态文本（如"办结"）。
            expected_vm_status: 期望的实例状态文本（如"运行中"）。
            timeout: 最长等待时间（秒），默认600秒（10分钟）。
            interval: 轮询间隔（秒），默认10秒。

        Returns:
            dict: 最终行数据字典。

        Raises:
            TimeoutError: 超过timeout仍未达到预期状态。
        """
        with allure_step_log(f"轮询等待 '{name}' 状态变为 '{expected_status}'（最长{timeout}秒）"):
            import time
            start = time.monotonic()
            while time.monotonic() - start < timeout:
                self.page.reload()
                self.wait_for_page_ready()
                # 等待表格数据加载完成（表格有可见行）
                try:
                    t_body = self.page.locator(".el-table__body-wrapper")
                    expect(t_body.locator("tr").first).to_be_visible(timeout=15000)
                except Exception:
                    self.logger.debug("表格尚未加载，继续等待")
                    self.page.wait_for_timeout(interval * 1000)
                    continue

                try:
                    row_data = self.get_row_data(name)
                    # 表头可能包含筛选组件的额外文本，使用模糊匹配查找状态键
                    status_key = next((k for k in row_data.keys() if "状态" in k and "实例" not in k), "")
                    vm_status_key = next((k for k in row_data.keys() if "实例状态" in k), "")
                    current_status = row_data.get(status_key, "")
                    current_vm_status = row_data.get(vm_status_key, "")
                    self.logger.info(
                        f"当前状态: 状态={current_status}, 实例状态={current_vm_status}"
                    )

                    if expected_status in current_status and expected_vm_status in current_vm_status:
                        self.logger.info("状态已达到预期")
                        return row_data
                except Exception as e:
                    self.logger.debug(f"轮询获取状态失败: {e}")

                self.page.wait_for_timeout(interval * 1000)

            raise TimeoutError(
                f"物理连接 '{name}' 在 {timeout} 秒内未达到预期状态 "
                f"(期望: 状态='{expected_status}', 实例状态='{expected_vm_status}')"
            )

    def _get_edit_dialog_context(self):
        """获取修改物理连接弹窗的上下文定位器。

        Returns:
            tuple: (dialog定位器, form上下文定位器)
        """
        dialog = self.page.locator(".el-dialog__wrapper:visible")
        expect(dialog).to_be_visible(timeout=10000)
        expect(dialog.get_by_text("修改物理连接", exact=True)).to_be_visible(timeout=5000)

        ctx = dialog.locator(".add-box")
        expect(ctx).to_be_visible(timeout=5000)
        return dialog, ctx

    def _assert_field_disabled(self, ctx, label: str):
        """断言指定标签的表单项为禁用状态。

        Element UI 的 disabled select/switch 会在 .el-input 或组件本身添加 is-disabled 类。

        Args:
            ctx: 表单上下文定位器。
            label: 字段标签文本，如"运营商"、"端口类型"。
        """
        with allure_step_log(f"验证 '{label}' 字段为禁用状态"):
            form_item = ctx.locator(".el-form-item").filter(has_text=label)
            expect(form_item).to_be_visible(timeout=5000)

            # 检查 el-input 是否有 is-disabled 类
            input_elems = form_item.locator(".el-input")
            if input_elems.count() > 0:
                classes = input_elems.first.get_attribute("class") or ""
                assert "is-disabled" in classes, f"'{label}' 字段应为禁用状态，实际 class: {classes}"
                return

            # 检查 el-switch 是否有 is-disabled 类
            switch_elems = form_item.locator(".el-switch")
            if switch_elems.count() > 0:
                classes = switch_elems.first.get_attribute("class") or ""
                assert "is-disabled" in classes, f"'{label}' 字段应为禁用状态，实际 class: {classes}"
                return

            raise AssertionError(f"'{label}' 字段未找到可验证的输入元素")

    @submenu("物理连接")
    def dc_physical_connection_edit(
        self,
        name: str,
        new_name: str = "",
        description: str = "",
    ):
        """修改指定物理连接。

        打开修改弹窗，验证运营商、端口类型、HA字段为禁用状态，
        修改名称和/或描述，提交修改。

        Args:
            name: 需要修改的物理连接名称。
            new_name: 新的物理连接名称，为空则不修改名称。
            description: 新的描述，为空则不修改描述。
        """
        with allure_step_log(f"点击物理连接 '{name}' 的修改按钮"):
            self.click_action(name, "修改")

        dialog, ctx = self._get_edit_dialog_context()

        with allure_step_log("验证只读字段（运营商、端口类型、HA）"):
            self._assert_field_disabled(ctx, "运营商")
            self._assert_field_disabled(ctx, "端口类型")
            # HA 字段条件渲染，仅在 policy_document 开启时显示
            try:
                ha_item = ctx.locator(".el-form-item").filter(has_text="HA")
                if ha_item.count() > 0 and ha_item.first.is_visible():
                    self._assert_field_disabled(ctx, "HA")
            except AssertionError:
                raise
            except Exception:
                self.logger.info("HA 字段未显示，跳过HA禁用验证")

        if new_name:
            with allure_step_log(f"修改物理连接名称为: {new_name}"):
                name_input = ctx.get_by_placeholder("物理连接名称")
                expect(name_input).to_be_visible(timeout=5000)
                name_input.clear()
                name_input.fill(new_name)

        if description:
            with allure_step_log(f"修改描述为: {description}"):
                desc_input = ctx.locator("textarea").first
                expect(desc_input).to_be_visible(timeout=5000)
                desc_input.clear()
                desc_input.fill(description)

        with allure_step_log("点击立即修改按钮"):
            submit_btn = dialog.get_by_text("立即修改", exact=True)
            expect(submit_btn).to_be_visible(timeout=5000)
            submit_btn.click()
