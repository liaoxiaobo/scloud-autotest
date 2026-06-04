"""企业路由器 (Enterprise Router) 页面对象。"""

import re

from sugon_web.common.base import BasePage
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log


class ErMixin(BasePage):
    """企业路由器模块页面对象，封装列表、创建、详情、删除等操作。"""

    service_name = "企业路由器"

    def _ensure_list_page(self):
        """确保当前位于企业路由器列表页。"""
        current_url = self.page.url
        if "#/vpc-er-list" not in current_url:
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/vpc#/vpc-er-list")
            # hash路由不触发页面重载时，等待Vue Router组件切换及表格数据加载
            self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()
        # 等待页面 loading 消失
        try:
            loading = self.page.locator(".el-loading-mask:visible")
            if loading.count() > 0:
                expect(loading).to_have_count(0, timeout=15000)
        except Exception:
            pass
        # 等待列表表格渲染完成（表头+至少一行数据）
        try:
            expect(self.page.locator(".el-table__header-wrapper").first).to_be_visible(timeout=15000)
        except Exception:
            self.logger.warning("等待表格渲染超时，继续执行")
        try:
            expect(self.page.locator(".el-table__body-wrapper .el-table__row").first).to_be_visible(timeout=15000)
        except Exception:
            self.logger.warning("等待表格数据行超时，继续执行")

    def er_create(self, name: str, cluster_name: str = "Autotest", ha_enable: bool = True, description: str = ""):
        """创建企业路由器。

        Args:
            name: 企业路由器名称。
            cluster_name: 集群名称，默认为 "Autotest"。
            ha_enable: 是否开启HA，默认True（开启）。
            description: 描述，可选。
        """
        self._ensure_list_page()
        with allure_step_log("点击新建按钮"):
            create_btn = self.page.locator("#cloud-container-content").get_by_text("新建", exact=True).first
            expect(create_btn).to_be_visible(timeout=5000)
            create_btn.click()

        with allure_step_log("等待创建弹窗可见"):
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog).to_contain_text("创建企业路由器", timeout=5000)
            # 等待弹窗内表单加载完成
            self.page.wait_for_timeout(1000)

        # 获取弹窗body作为定位上下文
        dialog_body = dialog.locator(".el-dialog__body")

        with allure_step_log("填写企业路由器名称"):
            # 通过label文本定位表单项，然后找input
            name_label = dialog_body.get_by_text("名称", exact=True)
            expect(name_label).to_be_visible(timeout=5000)
            # 向上找到el-form-item，然后找input
            name_item = name_label.locator("xpath=ancestor::div[contains(@class,'el-form-item')]")
            name_input = name_item.locator("input.el-input__inner").first
            expect(name_input).to_be_visible(timeout=5000)
            name_input.fill(name)

        with allure_step_log("选择集群"):
            cluster_label = dialog_body.get_by_text("集群", exact=True)
            expect(cluster_label).to_be_visible(timeout=5000)
            cluster_item = cluster_label.locator("xpath=ancestor::div[contains(@class,'el-form-item')]")
            cluster_select = cluster_item.get_by_placeholder("请选择集群")
            expect(cluster_select).to_be_visible(timeout=5000)
            cluster_select.click()
            self.page.wait_for_timeout(500)
            dropdown = self.page.locator(".el-select-dropdown:visible")
            expect(dropdown).to_be_visible(timeout=5000)
            # 先尝试精确匹配集群名称
            option = dropdown.locator(".el-select-dropdown__item").filter(
                has_text=re.compile(rf"^{re.escape(cluster_name)}$")
            )
            if option.count() == 0:
                # 降级：模糊匹配
                option = dropdown.get_by_text(cluster_name, exact=False)
            expect(option.first).to_be_visible(timeout=5000)
            option.first.click()
            self.page.wait_for_timeout(300)

        # HA开关：条件渲染，先检查是否存在
        ha_items = dialog_body.locator(".el-form-item").filter(has_text="HA")
        if ha_items.count() > 0:
            ha_item = ha_items.first
            if ha_item.is_visible():
                with allure_step_log(f"设置HA开关: {'开启' if ha_enable else '关闭'}"):
                    ha_switch = ha_item.locator(".el-switch").first
                    is_checked = ha_switch.evaluate("el => el.classList.contains('is-checked')")
                    if is_checked != ha_enable:
                        ha_switch.click()
                        self.page.wait_for_timeout(300)

        with allure_step_log("点击立即创建"):
            submit_btn = dialog.get_by_text("立即创建", exact=True)
            expect(submit_btn).to_be_visible(timeout=5000)
            submit_btn.click()

    def er_delete(self, name: str):
        """删除企业路由器。

        Args:
            name: 企业路由器名称。
        """
        with allure_step_log(f"删除企业路由器: {name}"):
            self._ensure_list_page()
            self.page.wait_for_timeout(2000)
            self.click_action(name, "删除")
            # 确认删除对话框
            self.dialog_confirm.click()

    def get_detail_field_value(self, field_name: str) -> str:
        """获取详情页指定字段的值。

        Args:
            field_name: 字段名称，如"名称"、"状态"、"高可用"、"描述"等。

        Returns:
            str: 字段值文本。
        """
        # 企业路由器详情页中，"名称"使用 er-detail-name 类
        if field_name == "名称":
            name_loc = self.page.locator(".er-detail-name")
            if name_loc.count() > 0:
                return name_loc.first.text_content().strip()

        # 其他字段使用 er-detail-label / er-detail-value 结构
        label_loc = self.page.locator(".er-detail-label").filter(
            has_text=re.compile(rf"^{re.escape(field_name)}[:：]")
        )
        if label_loc.count() == 0:
            raise AssertionError(f"详情页未找到字段: {field_name}")

        # 找到 label 后，在同一父元素下找 value
        value_loc = label_loc.locator("xpath=../div[contains(@class,'er-detail-value')]")
        if value_loc.count() == 0:
            value_loc = label_loc.locator("xpath=following-sibling::*[contains(@class,'er-detail-value')]")
        # 描述字段使用 MyTooltip 组件，不是 er-detail-value 类
        if value_loc.count() == 0:
            value_loc = label_loc.locator("xpath=following-sibling::*")
        if value_loc.count() == 0:
            raise AssertionError(f"详情页未找到字段 {field_name} 的值")

        # 等待值加载完成（可能有异步数据）
        value_loc.first.wait_for(state="visible", timeout=5000)
        return value_loc.first.text_content().strip()

    def goto_connection_tab(self, er_name: str):
        """从ER列表页点击"管理连接"进入详情页的连接tab。

        Args:
            er_name: 企业路由器名称。
        """
        with allure_step_log(f"进入 {er_name} 的连接管理"):
            self._ensure_list_page()
            self.page.wait_for_timeout(1000)
            self.click_action(er_name, "管理连接")
            self.wait_for_page_ready()
            # 等待连接tab内容渲染
            self.page.wait_for_timeout(2000)

    def er_generate_auth_code(self, er_name: str) -> str:
        """生成ER授权码并返回。

        Args:
            er_name: 企业路由器名称。

        Returns:
            str: 授权码文本。
        """
        self._ensure_list_page()
        with allure_step_log(f"生成授权码: {er_name}"):
            self.click_action(er_name, "生成授权码")
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog).to_contain_text("ER对等连接授权码", timeout=5000)
            # 等待授权码加载
            self.page.wait_for_timeout(1000)
            code_loc = dialog.locator(".container")
            expect(code_loc.first).to_be_visible(timeout=5000)
            code_text = code_loc.first.text_content().strip()
            self.logger.info(f"授权码: {code_text}")
            # 点击取消关闭弹窗
            dialog.get_by_text("取消", exact=True).click()
            self.page.wait_for_timeout(500)
            return code_text

    def er_connection_create(
        self,
        name: str,
        conn_type: str = "VPC",
        vpc_name: str = None,
        subnet_name: str = None,
        auth_code: str = None,
        description: str = "",
    ):
        """添加ER连接。

        Args:
            name: 连接名称。
            conn_type: 连接类型，"VPC" 或 "ER"，默认 "VPC"。
            vpc_name: VPC名称（仅当 conn_type="VPC" 时需要）。
            subnet_name: 子网名称（仅当 conn_type="VPC" 时可选，未提供则选择第一个子网）。
            auth_code: 授权码（仅当 conn_type="ER" 时需要）。
            description: 描述，可选。
        """
        with allure_step_log(f"添加{conn_type}连接: {name}"):
            # 点击添加连接按钮
            add_btn = self.page.locator("#cloud-container-content").get_by_text(
                "添加连接", exact=True
            ).first
            expect(add_btn).to_be_visible(timeout=10000)
            add_btn.click()

            # 等待弹窗
            self.page.wait_for_timeout(1500)
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=15000)
            expect(dialog).to_contain_text("添加连接", timeout=5000)
            self.page.wait_for_timeout(1000)

            dialog_body = dialog.locator(".el-dialog__body")

            # 填写名称
            with allure_step_log("填写连接名称"):
                name_input = dialog_body.get_by_placeholder("请输入名称")
                expect(name_input).to_be_visible(timeout=5000)
                name_input.fill(name)

            # 切换连接类型（如需要）
            if conn_type == "ER":
                with allure_step_log("切换连接类型为: 企业路由器"):
                    radio_group = dialog_body.locator(".el-radio-group")
                    er_radio = radio_group.get_by_text("企业路由器", exact=True)
                    expect(er_radio).to_be_visible(timeout=5000)
                    er_radio.click()
                    self.page.wait_for_timeout(500)

            if conn_type == "VPC":
                with allure_step_log("选择虚拟私有云"):
                    vpc_select = dialog_body.get_by_placeholder("请选择虚拟私有云")
                    expect(vpc_select).to_be_visible(timeout=5000)
                    vpc_select.click()
                    self.page.wait_for_timeout(500)
                    dropdown = self.page.locator(".el-select-dropdown:visible")
                    expect(dropdown).to_be_visible(timeout=5000)
                    option = dropdown.locator(".el-select-dropdown__item").filter(
                        has_text=re.compile(rf"^{re.escape(vpc_name)}$")
                    )
                    if option.count() == 0:
                        option = dropdown.get_by_text(vpc_name, exact=False)
                    expect(option.first).to_be_visible(timeout=5000)
                    option.first.click()
                    self.page.wait_for_timeout(500)

                with allure_step_log("选择子网"):
                    subnet_select = dialog_body.get_by_placeholder("请选择子网")
                    expect(subnet_select).to_be_visible(timeout=5000)
                    subnet_select.click()
                    self.page.wait_for_timeout(500)
                    dropdown = self.page.locator(".el-select-dropdown:visible")
                    expect(dropdown).to_be_visible(timeout=5000)
                    if subnet_name:
                        option = dropdown.locator(".el-select-dropdown__item").filter(
                            has_text=re.compile(rf"^{re.escape(subnet_name)}$")
                        )
                        if option.count() == 0:
                            option = dropdown.get_by_text(subnet_name, exact=False)
                    else:
                        option = dropdown.locator(".el-select-dropdown__item").first
                    expect(option).to_be_visible(timeout=5000)
                    option.click()
                    self.page.wait_for_timeout(300)

            if conn_type == "ER":
                with allure_step_log("填写授权码"):
                    auth_input = dialog_body.get_by_placeholder("请输入授权码")
                    expect(auth_input).to_be_visible(timeout=5000)
                    auth_input.fill(auth_code)

            # 填写描述（如有）
            if description:
                with allure_step_log("填写描述"):
                    desc_input = dialog_body.locator("textarea")
                    if desc_input.count() > 0:
                        desc_input.first.fill(description)

            with allure_step_log("点击确定"):
                submit_btn = dialog.get_by_text("确定", exact=True)
                expect(submit_btn).to_be_visible(timeout=5000)
                submit_btn.click()

    def er_connection_delete(self, name: str):
        """删除ER连接。

        Args:
            name: 连接名称。
        """
        with allure_step_log(f"删除连接: {name}"):
            self.click_action(name, "删除")
            # 确认删除对话框
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=5000)
            expect(dialog).to_contain_text("删除", timeout=3000)
            self.dialog_confirm.click()
            self.page.wait_for_timeout(1000)

    def er_edit(self, name: str, new_name: str = None, description: str = None):
        """修改企业路由器基本信息。

        Args:
            name: 当前企业路由器名称。
            new_name: 新名称，为None则不修改名称。
            description: 新描述，为None则不修改描述。
        """
        with allure_step_log(f"修改企业路由器 {name} 的基本信息"):
            self._ensure_list_page()
            self.click_action(name, "修改基本信息")

            # 等待弹窗
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=10000)
            expect(dialog).to_contain_text("修改基本信息", timeout=5000)
            self.page.wait_for_timeout(500)

            dialog_body = dialog.locator(".el-dialog__body")

            if new_name is not None:
                with allure_step_log(f"修改名称为: {new_name}"):
                    name_input = dialog_body.get_by_placeholder("请输入名称")
                    expect(name_input).to_be_visible(timeout=5000)
                    name_input.fill("")
                    name_input.fill(new_name)

            if description is not None:
                with allure_step_log(f"修改描述为: {description}"):
                    desc_input = dialog_body.locator("textarea").first
                    expect(desc_input).to_be_visible(timeout=5000)
                    desc_input.fill("")
                    desc_input.fill(description)

            with allure_step_log("点击确定提交"):
                submit_btn = dialog.get_by_text("确定", exact=True)
                expect(submit_btn).to_be_visible(timeout=5000)
                submit_btn.click()

    def goto_er_detail(self, er_name: str):
        """从列表页点击ER名称进入详情页。

        Args:
            er_name: 企业路由器名称。
        """
        with allure_step_log(f"进入ER详情页: {er_name}"):
            self._ensure_list_page()
            row = self.get_row_by_name(er_name)
            name_link = row.locator("a").first
            expect(name_link).to_be_visible(timeout=5000)
            name_link.click()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(1000)

    def goto_route_table_tab(self, er_name: str):
        """从ER列表页点击"管理路由表"进入详情页的路由表tab。

        Args:
            er_name: 企业路由器名称。
        """
        with allure_step_log(f"进入 {er_name} 的路由表管理"):
            self._ensure_list_page()
            self.page.wait_for_timeout(2000)
            self.click_action(er_name, "管理路由表")
            self.wait_for_page_ready()
            # 等待路由表tab内容渲染
            self.page.wait_for_timeout(2000)

    def er_route_rule_create(
        self,
        destination: str,
        next_hop_type: str = "企业路由器",
        connection: str = None,
        next_hop: str = None,
        description: str = "",
    ):
        """创建ER路由表规则。

        Args:
            destination: 目的地址CIDR，如 "10.0.0.0/24"。
            next_hop_type: 下一跳类型，默认"企业路由器"。
            connection: 连接名称（当下一跳类型为"企业路由器"时需要）。
            next_hop: 下一跳资源名称（当下一跳类型为"企业路由器"时需要）。
            description: 描述，可选。
        """
        with allure_step_log(f"新建路由表规则: {destination}"):
            # 点击新建路由表规则按钮
            add_btn = self.page.locator("#cloud-container-content").get_by_text(
                "新建路由表规则", exact=True
            ).first
            expect(add_btn).to_be_visible(timeout=5000)
            add_btn.click()

            # 等待弹窗
            self.page.wait_for_timeout(500)
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=15000)
            expect(dialog).to_contain_text("新建路由表规则", timeout=5000)
            self.page.wait_for_timeout(500)

            dialog_body = dialog.locator(".el-dialog__body")

            # 填写目的地址
            with allure_step_log("填写目的地址"):
                dest_input = dialog_body.get_by_placeholder("必填 如：10.0.13.0/24")
                expect(dest_input).to_be_visible(timeout=5000)
                dest_input.fill(destination)

            # 选择下一跳类型
            with allure_step_log(f"选择下一跳类型: {next_hop_type}"):
                type_select = dialog_body.locator(".el-form-item").filter(
                    has_text="下一跳类型"
                ).locator("input").first
                expect(type_select).to_be_visible(timeout=5000)
                type_select.click()
                self.page.wait_for_timeout(500)
                dropdown = self.page.locator(".el-select-dropdown:visible")
                expect(dropdown).to_be_visible(timeout=5000)
                option = dropdown.get_by_text(next_hop_type, exact=True)
                expect(option).to_be_visible(timeout=5000)
                option.click()
                # 等待下拉框关闭
                expect(dropdown).to_have_count(0, timeout=5000)
                # 等待表单联动，连接和下一跳字段异步加载选项
                self.page.wait_for_timeout(1500)

            # 选择连接
            if connection:
                with allure_step_log(f"选择连接: {connection}"):
                    conn_select = dialog_body.locator(".el-form-item").filter(
                        has_text="连接"
                    ).locator("input").first
                    expect(conn_select).to_be_visible(timeout=5000)
                    conn_select.click()
                    self.page.wait_for_timeout(800)
                    dropdown = self.page.locator(".el-select-dropdown:visible").last
                    expect(dropdown).to_be_visible(timeout=5000)
                    # 获取所有选项文本
                    all_options = dropdown.locator(".el-select-dropdown__item").all()
                    option_texts = [opt.text_content().strip() for opt in all_options if opt.text_content()]
                    self.logger.info(f"连接下拉选项: {option_texts}")
                    # 优先精确匹配，再模糊匹配，最后选第一个
                    target_opt = None
                    for opt in all_options:
                        txt = opt.text_content().strip() if opt.text_content() else ""
                        if txt == connection:
                            target_opt = opt
                            break
                    if target_opt is None:
                        for opt in all_options:
                            txt = opt.text_content().strip() if opt.text_content() else ""
                            if connection in txt:
                                target_opt = opt
                                break
                    if target_opt is None and all_options:
                        target_opt = all_options[0]
                    if target_opt is None:
                        raise AssertionError(f"连接下拉框无可用选项，期望: {connection}")
                    target_opt.click()
                    # 等待下拉框关闭
                    expect(self.page.locator(".el-select-dropdown:visible")).to_have_count(0, timeout=5000)
                    # 等待下一跳字段异步加载选项
                    self.page.wait_for_timeout(1500)

            # 选择下一跳（与"下一跳类型"是完全不同的字段）
            if next_hop:
                with allure_step_log(f"选择下一跳: {next_hop}"):
                    # 先点击弹窗标题区域确保所有下拉框关闭
                    dialog.locator(".el-dialog__header").first.click()
                    self.page.wait_for_timeout(300)

                    # 使用精确文本匹配，避免匹配到"下一跳类型"
                    hop_label = dialog_body.get_by_text("下一跳", exact=True)
                    hop_item = hop_label.locator("xpath=ancestor::div[contains(@class,'el-form-item')]")
                    hop_select = hop_item.locator("input").first
                    expect(hop_select).to_be_visible(timeout=5000)
                    hop_select.click()
                    self.page.wait_for_timeout(800)
                    dropdown = self.page.locator(".el-select-dropdown:visible").last
                    expect(dropdown).to_be_visible(timeout=5000)
                    # 获取所有选项文本
                    all_options = dropdown.locator(".el-select-dropdown__item").all()
                    option_texts = [opt.text_content().strip() for opt in all_options if opt.text_content()]
                    self.logger.info(f"下一跳下拉选项: {option_texts}")
                    # 如果选项仍是类型选项，说明下拉框未正确切换，重试一次
                    if option_texts and option_texts[0] in ['虚拟私有云VPC', 'VPN', 'NAT', '云专线', '云防火墙CFW', '企业路由器', 'NAT网关（性能版）', '云防火墙SFW']:
                        self.logger.warning("下一跳下拉框显示类型选项，关闭重试")
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)
                        hop_select.click()
                        self.page.wait_for_timeout(800)
                        dropdown = self.page.locator(".el-select-dropdown:visible").last
                        all_options = dropdown.locator(".el-select-dropdown__item").all()
                        option_texts = [opt.text_content().strip() for opt in all_options if opt.text_content()]
                        self.logger.info(f"下一跳下拉选项(重试): {option_texts}")
                    # 优先精确匹配，再模糊匹配，最后选第一个
                    target_opt = None
                    for opt in all_options:
                        txt = opt.text_content().strip() if opt.text_content() else ""
                        if txt == next_hop:
                            target_opt = opt
                            break
                    if target_opt is None:
                        for opt in all_options:
                            txt = opt.text_content().strip() if opt.text_content() else ""
                            if next_hop in txt:
                                target_opt = opt
                                break
                    if target_opt is None and all_options:
                        target_opt = all_options[0]
                    if target_opt is None:
                        raise AssertionError(f"下一跳下拉框无可用选项，期望: {next_hop}")
                    target_opt.click()
                    # 等待下拉框关闭
                    expect(self.page.locator(".el-select-dropdown:visible")).to_have_count(0, timeout=5000)
                    self.page.wait_for_timeout(500)

            # 填写描述
            if description:
                with allure_step_log("填写描述"):
                    desc_input = dialog_body.locator("textarea").first
                    if desc_input.count() > 0:
                        desc_input.fill(description)

            with allure_step_log("点击确定"):
                submit_btn = dialog.get_by_text("确定", exact=True)
                expect(submit_btn).to_be_visible(timeout=5000)
                submit_btn.click()

    def er_route_rule_delete(self, destination: str):
        """删除ER路由表规则（根据目的地址）。

        Args:
            destination: 目的地址CIDR，用于定位要删除的规则。
        """
        with allure_step_log(f"删除路由表规则: {destination}"):
            # 在路由表列表中找到包含目的地址的行，点击删除
            self.click_action(destination, "删除")
            # 确认删除对话框
            dialog = self.page.locator(".el-dialog__wrapper:visible")
            expect(dialog).to_be_visible(timeout=5000)
            expect(dialog).to_contain_text("删除", timeout=3000)
            self.dialog_confirm.click()
            self.page.wait_for_timeout(1000)
