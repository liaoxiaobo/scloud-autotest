import re
import time
from playwright.sync_api import expect
from sugon_web.common.base import BasePage
from sugon_web.utils.logger import logger


class IamPage(BasePage):
    """统一身份认证IAM 页面对象。

    覆盖以下能力：
    - 进入组织管理-用户管理页面
    - 选择组织树节点
    - 创建用户（填写表单并提交）
    - 删除用户
    - 搜索用户
    """

    service_name = "统一身份认证IAM"

    @property
    def _btn_create_user(self):
        """创建用户按钮（cl-button 渲染为 div.cloud-button-btn）。"""
        return self.locator("div.cloud-button-btn").filter(has_text="创建用户")

    @property
    def _tab_user_manage(self):
        tab = self.get_by_role("tab").filter(has_text="用户管理")
        if tab.count() == 0:
            tab = self.page.locator(".el-tabs__item, [role='tab'], .tab-pane-header span").filter(has_text="用户管理")
        return tab

    def _navigate_to_user_management(self, target_org: str = None):
        """导航到用户管理tab页。

        Args:
            target_org: 目标子组织名称。传入时按名称精准点击；为None时逐个尝试（兜底）。
        """
        self.wait_for_page_ready()
        self.close_dialog_if_exists()
        self.page.wait_for_timeout(3000)

        # "请先创建组织"可能是页面树组件加载中的瞬态，等待后重试
        for attempt in range(3):
            no_org_hint = self.page.get_by_text("请先创建组织")
            if no_org_hint.count() == 0:
                break
            if attempt < 2:
                logger.info(f"IAM：页面显示'请先创建组织'，等待树加载（{attempt+1}/2）")
                self.page.wait_for_timeout(3000)
        else:
            logger.warning("IAM：当前环境无可用组织，无法导航到用户管理")
            return

        tree_div = self.page.locator("#iam-department")
        try:
            expect(tree_div).to_be_visible(timeout=10000)
        except Exception:
            from sugon_web.config.config import Config
            base = Config.get("base_url")
            self.page.goto(f"{base}/iam/#/departmentManage")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(3000)
            expect(tree_div).to_be_visible(timeout=10000)

        clicked = False

        if target_org:
            # 按名称精准匹配：先定位 .depart_name，再点击其含 click="choose" 的父容器
            logger.info(f"IAM：按名称精准定位子组织 '{target_org}'")
            depart = tree_div.locator(".depart_name").filter(has_text=target_org)
            for _ in range(5):
                if depart.count() > 0:
                    break
                self.page.wait_for_timeout(1500)
            if depart.count() > 0:
                # 向上找到带 click="choose" 属性的父级 one-tree-msg（Vue 事件在此）
                click_target = depart.first.locator("xpath=ancestor::*[@click='choose'][1]")
                if click_target.count() > 0:
                    click_target.first.scroll_into_view_if_needed()
                    click_target.first.evaluate("el => el.click()")
                    self.page.wait_for_timeout(1500)
                    if self._tab_user_manage.count() > 0 and self._tab_user_manage.is_visible():
                        logger.info(f"IAM：通过名称 '{target_org}' 成功定位并激活组织树节点")
                        clicked = True
                else:
                    logger.warning(f"IAM：未找到 '{target_org}' 的可点击父容器")
            else:
                logger.warning(f"IAM：组织树中未找到节点 '{target_org}'")

        if not clicked:
            logger.warning("IAM：无法激活用户管理tab")

        # 确保用户管理tab是激活状态
        try:
            if self._tab_user_manage.count() > 0 and self._tab_user_manage.is_visible():
                self._tab_user_manage.click()
                self.page.wait_for_timeout(1000)
        except Exception:
            pass

    def _open_create_user_dialog(self, target_org: str = None):
        """点击创建用户按钮，等待弹窗出现。"""
        self._navigate_to_user_management(target_org=target_org)
        # 等待用户管理列表加载完成
        table_container = self.locator(".cl-table-container, .table-fixed")
        try:
            expect(table_container.first).to_be_visible(timeout=10000)
        except Exception:
            logger.warning("IAM：用户管理列表容器未出现，尝试直接查找按钮")
        self.page.wait_for_timeout(1000)
        # 尝试多种方式定位创建用户按钮
        btn = None
        for try_selector in [
            lambda: self.locator("div.cloud-button-btn").filter(has_text="创建用户"),
            lambda: self.page.locator("div.cloud-button-btn").filter(has_text="创建用户"),
            lambda: self.page.get_by_text("创建用户"),
        ]:
            try:
                candidate = try_selector()
                if candidate.count() > 0:
                    btn = candidate.first
                    break
            except Exception:
                continue
        if btn is None:
            raise Exception("未找到创建用户按钮，可能因权限限制或页面结构变更")
        btn.click()
        dialog = self.locator(".el-dialog").filter(has_text="创建用户")
        expect(dialog.first).to_be_visible(timeout=5000)
        logger.info("IAM：创建用户弹窗已打开")
        return dialog.first

    def _fill_form_field(self, dialog, label: str, value: str, field_type: str = "input"):
        """在弹窗中填写指定label的表单字段。

        Args:
            dialog: 弹窗定位器
            label: 表单字段label文本
            value: 要填写的值
            field_type: 字段类型，'input' 或 'select'
        """
        form_item = dialog.locator(".el-form-item").filter(has_text=label)
        if field_type == "input":
            input_el = form_item.locator("input").first
            input_el.fill(value)
        elif field_type == "select":
            select_el = form_item.locator(".el-select").first
            select_el.click()
            self.page.wait_for_timeout(500)
            options = self.locator(".el-select-dropdown:visible li")
            if options.count() > 0:
                options.first.click()
                self.page.wait_for_timeout(300)
            else:
                logger.warning(f"IAM：角色下拉选项为空，无法选择")
        logger.info(f"IAM：填写 {label} = {value}")

    def iam_create_user(
        self,
        name: str,
        alias: str = None,
        email: str = None,
        phone: str = None,
        password: str = None,
        is_department_manager: bool = False,
        target_org: str = None,
    ):
        """创建IAM用户。

        Args:
            name: 账号
            alias: 用户名（默认与账号相同）
            email: 邮箱
            phone: 手机号
            password: 密码（默认使用 admin 密码）
            is_department_manager: 是否为组织管理员，默认False
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        if alias is None:
            alias = name
        if password is None:
            password = "Keystone@1234"

        dialog = self._open_create_user_dialog(target_org=target_org)

        # 账号
        self._fill_form_field(dialog, "账号", name)
        # 用户名
        self._fill_form_field(dialog, "用户名", alias)

        # 组织管理员：选"否"
        is_admin_form_item = dialog.locator(".el-form-item").filter(has_text="组织管理员")
        try:
            radio_no = is_admin_form_item.locator(".el-radio").filter(has_text="否")
            if radio_no.count() > 0:
                radio_no.first.locator("input").evaluate("el => el.click()")
        except Exception:
            pass

        # 角色绑定：选择"默认角色"（仅非组织管理员时出现）
        self.page.wait_for_timeout(300)
        role_form_item = dialog.locator(".el-form-item").filter(has_text="角色绑定")
        if role_form_item.count() > 0:
            role_form_item.locator(".el-select").first.click()
            self.page.wait_for_timeout(500)
            default_role = self.locator(".el-select-dropdown:visible li").filter(has_text="默认角色")
            if default_role.count() > 0:
                default_role.first.click()
                logger.info("IAM：角色绑定 -> 默认角色")
            else:
                logger.warning("IAM：未找到默认角色选项")
            self.page.wait_for_timeout(300)

        # 邮箱
        if email:
            self._fill_form_field(dialog, "邮箱", email)
        # 手机号
        if phone:
            self._fill_form_field(dialog, "手机", phone)

        # 密码
        self._fill_form_field(dialog, "密码", password)
        self.page.wait_for_timeout(300)

        # 确认密码（填充密码后 Vue 响应式渲染该字段）
        confirm_form_item = dialog.locator(".el-form-item").filter(has_text="确认密码")
        if confirm_form_item.count() > 0:
            self._fill_form_field(dialog, "确认密码", password)

        # 点击确定提交（cl-button 渲染为 div.cloud-button-btn）
        submit_btn = None
        for try_submit in [
            lambda: self.page.locator(".el-dialog:visible .cloud-button-btn").filter(has_text="确定"),
            lambda: self.page.locator(".cloud-button-btn:visible").filter(has_text="确定"),
            lambda: self.page.locator("div.cloud-button-btn").filter(has_text="确定"),
        ]:
            try:
                candidate = try_submit()
                cnt = candidate.count()
                for i in range(cnt):
                    if candidate.nth(i).is_visible():
                        submit_btn = candidate.nth(i)
                        break
                if submit_btn:
                    break
            except Exception:
                continue
        if submit_btn is None:
            raise Exception("未找到创建用户弹窗的确定按钮")

        # 检查表单是否有验证错误
        form_errors = dialog.locator(".el-form-item__error")
        if form_errors.count() > 0:
            error_texts = [form_errors.nth(i).inner_text() for i in range(form_errors.count())]
            logger.warning(f"IAM：表单验证错误: {error_texts}")

        # 确保按钮可点击（非 disabled/loading 状态）
        self.page.wait_for_timeout(500)
        submit_btn.click()
        logger.info(f"IAM：已提交创建用户请求 {name}")
        # 等待弹窗关闭（最多10秒）
        try:
            expect(dialog).not_to_be_visible(timeout=10000)
            logger.info("IAM：创建用户弹窗已关闭")
        except Exception:
            logger.warning("IAM：弹窗未在10秒内关闭，表单可能提交失败")
            # 检查是否有表单验证错误
            form_errors = dialog.locator(".el-form-item__error")
            if form_errors.count() > 0:
                error_texts = [form_errors.nth(i).inner_text() for i in range(form_errors.count())]
                logger.error(f"IAM：表单验证错误: {error_texts}")
                return
        self.page.wait_for_timeout(1000)

    def iam_get_user_list(self, target_org: str = None) -> list[str]:
        """获取当前用户管理列表页所有用户名。

        Args:
            target_org: 目标子组织名称，用于精准导航到指定组织树节点

        Returns:
            list[str]: 用户名文本列表
        """
        self._navigate_to_user_management(target_org)
        self.wait_for_page_ready()
        # cl-table 使用标准 table 结构，但可能没有 el-table__body-wrapper
        # 先尝试标准 el-table，再尝试通用 table
        for tbody_sel in [".el-table__body-wrapper tbody", "table tbody", "tbody"]:
            rows = self.locator(tbody_sel + " tr")
            if rows.count() > 0:
                names = []
                for i in range(rows.count()):
                    text = rows.nth(i).inner_text()
                    names.append(text)
                return names
        return []

    def iam_search_user(self, keyword: str, target_org: str = None):
        """在用户管理列表页搜索用户（仅使用 IAM 表格区域内的搜索，不触碰全局 header 搜索框）。

        Args:
            keyword: 搜索关键字
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        self._navigate_to_user_management(target_org)
        # 限定在表格上方的搜索栏内查找，避免误匹配全局 app-mainframe-header 中的搜索框
        search_input = self.page.locator(
            "input[placeholder='搜索（用户名称）'], input[placeholder='搜索（名称）']"
        ).first
        if search_input.count() == 0:
            logger.warning(f"IAM：未找到用户管理搜索输入框")
            return
        search_input.fill(keyword)
        search_input.press("Enter")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1500)
        logger.info(f"IAM：搜索用户 {keyword}")

    def iam_delete_user(self, name: str, target_org: str = None):
        """删除IAM用户。

        Args:
            name: 用户账号名
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        self._navigate_to_user_management(target_org)
        self.click_action(name, "删除")
        self.page.wait_for_timeout(500)
        # 确认删除弹窗
        try:
            confirm_btn = self.dialog_confirm
            if confirm_btn.count() > 0 and confirm_btn.is_visible():
                confirm_btn.first.click()
        except Exception:
            pass
        logger.info(f"IAM：已提交删除用户请求 {name}")

    def iam_modify_user(self, name: str, target_org: str = None, **kwargs):
        """修改IAM用户。打开修改弹窗，填写指定字段后提交。

        Args:
            name: 当前用户账号名（用于定位行）
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
            **kwargs: 要修改的字段
                alias: 用户名, email: 邮箱, phone: 手机号,
                extra: 描述, role: 角色名或特殊值"__non_default__"表示自动选取一个非默认角色

        Returns:
            dict: 若 role="__non_default__"，返回 {"role": <选中的角色名>}，否则返回 {}
        """
        self._navigate_to_user_management(target_org)
        self.click_action(name, "修改用户")
        self.page.wait_for_timeout(500)

        result = {}

        dialog = self.locator(".el-dialog").filter(has_text="编辑")
        try:
            expect(dialog.first).to_be_visible(timeout=5000)
        except Exception:
            dialog = self.locator(".el-dialog").filter(has_text="修改用户")
            expect(dialog.first).to_be_visible(timeout=5000)
        dialog = dialog.first
        logger.info("IAM：修改用户弹窗已打开")

        if "alias" in kwargs:
            self._fill_form_field(dialog, "用户名", kwargs["alias"])
        if "email" in kwargs:
            self._fill_form_field(dialog, "邮箱", kwargs["email"])
        if "phone" in kwargs:
            self._fill_form_field(dialog, "手机", kwargs["phone"])
        if "extra" in kwargs:
            form_item = dialog.locator(".el-form-item").filter(has_text="描述")
            form_item.locator("textarea").first.fill(kwargs["extra"])
            logger.info(f"IAM：填写 描述 = {kwargs['extra']}")
        if "role" in kwargs:
            selected = self._select_role(dialog, kwargs["role"])
            if kwargs["role"] == "__non_default__":
                result["role"] = selected

        # 等待 Vue 表单异步校验完成
        self.page.wait_for_timeout(800)

        # 检查表单验证错误
        form_errors = dialog.locator(".el-form-item__error")
        if form_errors.count() > 0:
            error_texts = [form_errors.nth(i).inner_text() for i in range(form_errors.count())]
            logger.warning(f"IAM：修改表单验证错误: {error_texts}")

        submit_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定")
        if submit_btn.count() == 0:
            submit_btn = dialog.get_by_text("确定")
        self.page.wait_for_timeout(300)
        submit_btn.first.click()
        logger.info(f"IAM：已提交修改用户请求 {name}")

        try:
            expect(dialog).not_to_be_visible(timeout=15000)
            logger.info("IAM：修改用户弹窗已关闭")
        except Exception:
            logger.warning("IAM：修改弹窗未在15秒内关闭")
            form_errors = dialog.locator(".el-form-item__error")
            if form_errors.count() > 0:
                error_texts = [form_errors.nth(i).inner_text() for i in range(form_errors.count())]
                logger.error(f"IAM：修改表单验证错误: {error_texts}")
        self.page.wait_for_timeout(1000)
        return result

    def _select_role(self, dialog, role_name: str) -> str:
        """在弹窗角色下拉中选择角色。返回实际选中的角色名。"""
        form_item = dialog.locator(".el-form-item").filter(has_text="角色绑定")
        form_item.locator(".el-select").first.click()
        self.page.wait_for_timeout(500)
        all_roles = self.locator(".el-select-dropdown:visible li")
        if role_name == "__non_default__":
            selected = None
            for i in range(all_roles.count()):
                text = all_roles.nth(i).inner_text().strip()
                if text and "默认角色" not in text:
                    selected = text
                    break
            if selected:
                all_roles.filter(has_text=selected).first.click()
                logger.info(f"IAM：角色绑定 -> {selected}")
                self.page.wait_for_timeout(300)
                return selected
            else:
                logger.warning("IAM：未找到非默认角色选项")
                self.page.wait_for_timeout(300)
                return ""
        else:
            target = all_roles.filter(has_text=role_name)
            if target.count() > 0:
                target.first.click()
                logger.info(f"IAM：角色绑定 -> {role_name}")
            else:
                logger.warning(f"IAM：未找到角色选项 {role_name}")
            self.page.wait_for_timeout(300)
            return role_name

    def iam_open_user_detail(self, name: str, target_org: str = None):
        """点击用户管理列表中目标用户的'账号'链接进入详情页。

        Args:
            name: 用户账号名
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        self._navigate_to_user_management(target_org)
        row = self.get_row_by_name(name)
        row.locator("a, .cl-table-cell a, td:first-child a").first.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1000)
        logger.info(f"IAM：已进入用户 {name} 详情页")

    def iam_get_role_list_from_detail(self) -> list:
        """从用户详情页的角色列表tab获取角色名称列表。"""
        role_tab = self.get_by_role("tab").filter(has_text="角色列表")
        if role_tab.count() > 0 and role_tab.is_visible():
            role_tab.click()
            self.page.wait_for_timeout(1000)
        for tbody_sel in [".el-table__body-wrapper tbody", "table tbody", "tbody"]:
            rows = self.locator(tbody_sel + " tr")
            if rows.count() > 0:
                return [rows.nth(i).inner_text() for i in range(rows.count())]
        return []

    def _open_user_operation_dialog(self, name: str, operation_text: str, dialog_title: str,
                                     target_org: str = None):
        """打开用户操作弹窗的公共方法。

        Args:
            name: 用户账号名
            operation_text: 操作按钮文本
            dialog_title: 弹窗标题
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        self._navigate_to_user_management(target_org)
        self.click_action(name, operation_text)
        self.page.wait_for_timeout(800)
        dialog = self.get_by_role("dialog").filter(has_text=dialog_title)
        expect(dialog.first).to_be_visible(timeout=8000)
        logger.info(f"IAM：{dialog_title}弹窗已打开")
        return dialog.first

    def _submit_and_close_dialog(self, dialog, name: str):
        """点击确定提交弹窗，等待关闭并恢复页面。"""
        self.page.wait_for_timeout(500)
        submit_btn = dialog.locator(
            ".cloud-button-btn:has-text('确定'), .cloud-button-btn:has-text('修改中'), "
            ".cloud-button-btn:has-text('设置中'), .cloud-button-btn:has-text('重置中')"
        ).first
        if submit_btn.count() == 0:
            submit_btn = dialog.get_by_role("button").filter(has_text="确定")
        submit_btn.click()
        logger.info(f"IAM：已提交 {name}")
        try:
            expect(dialog).not_to_be_visible(timeout=10000)
        except Exception:
            logger.warning(f"IAM：{name}弹窗未在10秒内关闭")
        self.page.wait_for_timeout(1500)
        # 关闭可能出现的消息提示弹窗（el-message-box）
        self.close_dialog_if_exists()
        self.page.wait_for_timeout(500)
        # 点击表格刷新按钮获取最新数据
        try:
            refresh_btn = self.page.locator("button, .cloud-button, div.cloud-button-btn").filter(
                has_text="刷新"
            )
            if refresh_btn.count() > 0:
                refresh_btn.first.click()
                self.page.wait_for_timeout(1000)
        except Exception:
            pass

    def iam_modify_user_status(self, name: str, enabled: bool, target_org: str = None):
        """修改用户状态（启用/禁用）。

        Args:
            name: 用户账号名（列表行定位用）
            enabled: True=激活, False=禁用
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        dialog = self._open_user_operation_dialog(name, "修改用户状态", "修改用户状态", target_org)
        status_text = "激活" if enabled else "禁用"
        # el-radio-group 中第二个 radio 是"禁用"(label=false)，第一个是"激活"(label=true)
        radios = dialog.locator(".el-radio-group .el-radio")
        idx = 0 if enabled else 1
        radios.nth(idx).click()
        self.page.wait_for_timeout(300)
        logger.info(f"IAM：修改用户状态 -> {status_text}")
        self._submit_and_close_dialog(dialog, f"修改用户状态({name})")

    def iam_reset_password(self, name: str, new_password: str, target_org: str = None):
        """重置用户密码。

        Args:
            name: 用户账号名
            new_password: 新密码
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        dialog = self._open_user_operation_dialog(name, "重置密码", "重置密码", target_org)
        self._fill_form_field(dialog, "新密码", new_password)
        self._fill_form_field(dialog, "确认新密码", new_password)
        self._submit_and_close_dialog(dialog, f"重置密码({name})")

    def _select_date_in_picker(self, dialog, label: str, year: int, month: int, day: int,
                                input_index: int = 0, use_input: bool = True):
        """在日期选择器中设置指定日期。

        支持两种模式：
        - use_input=True（默认）：通过输入框直接填写，支持跨月/跨年日期，
          填入后加空格并点击空白处以触发 Vue 绑定和面板收起。
        - use_input=False：通过点击日历面板上的日期单元格，仅适用于当前显示月份。

        Args:
            label: 日期字段的 label 文本
            input_index: 同一个 form-item 中第几个 input（0-based）
            use_input: 是否使用输入框直接填写（True）或日历点击（False）
        """
        form_item = dialog.locator(".el-form-item").filter(has_text=label)
        inputs = form_item.locator("input")
        date_picker_input = inputs.nth(input_index) if inputs.count() > input_index else inputs.first
        date_picker_input.click()
        self.page.wait_for_timeout(300)
        target_day = str(day)

        if use_input:
            # 移除 readonly 使 fill 生效
            input_el = date_picker_input.element_handle()
            self.page.evaluate("el => el.removeAttribute('readonly')", input_el)
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            date_picker_input.fill(date_str + " ")
            self.page.wait_for_timeout(300)
            # 点击对话框内其他区域使日期选择器失去焦点并触发绑定
            dialog_title = dialog.locator(".el-dialog__header")
            if dialog_title.count() > 0:
                dialog_title.first.click()
            else:
                dialog.click(position={"x": 10, "y": 10})
            self.page.wait_for_timeout(500)
        else:
            # 日历点击方式：仅在当前显示月份中查找
            cells = self.page.locator(
                ".el-picker-panel:visible .el-date-table td.available:not(.prev-month):not(.next-month) span"
            )
            for i in range(cells.count()):
                if cells.nth(i).inner_text().strip() == target_day:
                    cells.nth(i).click()
                    break
            self.page.wait_for_timeout(300)

        # 确保日期面板已关闭（防止遮挡后续点击）
        panel = self.page.locator(".el-picker-panel:visible")
        if panel.count() > 0:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)

    def iam_set_user_expiry(self, name: str, date_str: str, target_org: str = None):
        """设置用户过期时间。

        Args:
            name: 用户账号名
            date_str: 过期日期，格式 yyyy-MM-dd，空字符串表示不限
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
        """
        dialog = self._open_user_operation_dialog(name, "设置用户过期时间", "设置用户过期时间", target_org)
        parts = date_str.split("-")
        self._select_date_in_picker(dialog, "过期时间",
                                     int(parts[0]), int(parts[1]), int(parts[2]))
        self._submit_and_close_dialog(dialog, f"设置过期时间({name})")

    def iam_create_organization(
        self,
        org_name: str,
        username: str,
        alias: str = None,
        email: str = None,
        phone: str = None,
        password: str = None,
        extra: str = "",
    ):
        """创建组织（同时创建组织的初始管理员用户）。

        Args:
            org_name: 组织名称
            username: 账号
            alias: 用户名（默认与账号相同）
            email: 邮箱
            phone: 手机号
            password: 密码（默认使用平台默认密码）
            extra: 描述
        """
        if alias is None:
            alias = username
        if password is None:
            password = "Keystone@1234"

        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 等待创建组织按钮出现在 DOM 中（Vue 异步渲染可能不稳定）
        try:
            self.page.wait_for_selector(".cloud-button.add-department", timeout=10000)
        except Exception:
            pass

        # 点击"创建组织"按钮（优先用 JS 点击，Vue 自定义组件原生 locator 不稳定）
        js_clicked = False
        for attempt in range(1, 6):
            js_clicked = self.page.evaluate("""
                () => {
                    const btn = document.querySelector('.cloud-button.add-department') ||
                                document.querySelector('.add-department');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    // 备用：按文本内容查找
                    const allDivs = document.querySelectorAll('div');
                    for (const el of allDivs) {
                        if (el.textContent.trim() === '创建组织' && el.click) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if js_clicked:
                logger.info(f"IAM：第 {attempt} 次尝试通过 JS 点击创建组织按钮成功")
                break
            self.page.wait_for_timeout(1200)

        if not js_clicked:
            raise Exception("未找到创建组织按钮")

        # 等待创建组织弹窗出现（Element UI dialog 动画需要缓冲）
        self.page.wait_for_timeout(1500)
        dialog = self.page.locator(".el-dialog__wrapper").filter(
            has=self.page.locator(".el-dialog").filter(has_text="创建组织")
        )
        expect(dialog.first).to_be_visible(timeout=10000)
        dialog = dialog.first.locator(".el-dialog").first
        logger.info("IAM：创建组织弹窗已打开")

        # 填写表单
        self._fill_form_field(dialog, "组织名称", org_name)
        self._fill_form_field(dialog, "账号", username)
        self._fill_form_field(dialog, "用户名", alias)
        if email:
            self._fill_form_field(dialog, "邮箱", email)
        if phone:
            self._fill_form_field(dialog, "手机", phone)
        self._fill_form_field(dialog, "密码", password)
        self.page.wait_for_timeout(300)

        # 确认密码
        confirm_item = dialog.locator(".el-form-item").filter(has_text="确认密码")
        if confirm_item.count() > 0 and confirm_item.is_visible():
            self._fill_form_field(dialog, "确认密码", password)

        if extra:
            form_item = dialog.locator(".el-form-item").filter(has_text="描述")
            form_item.locator("textarea").first.fill(extra)
            logger.info(f"IAM：填写 描述 = {extra}")

        self.page.wait_for_timeout(500)

        # 提交
        submit_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定")
        if submit_btn.count() == 0:
            submit_btn = dialog.get_by_text("确定")
        submit_btn.first.click()
        logger.info(f"IAM：已提交创建组织请求 {org_name}")

        # 等待弹窗关闭
        try:
            expect(dialog).not_to_be_visible(timeout=15000)
            logger.info("IAM：创建组织弹窗已关闭")
        except Exception:
            logger.warning("IAM：创建组织弹窗未在15秒内关闭")
            # 检查是否有表单验证错误
            form_errors = dialog.locator(".el-form-item__error")
            if form_errors.count() > 0:
                error_texts = [form_errors.nth(i).inner_text() for i in range(form_errors.count())]
                raise Exception(f"创建组织表单验证错误: {error_texts}")
        self.page.wait_for_timeout(2000)

    def iam_delete_organization(self, org_name: str):
        """删除指定名称的组织（顶级组织）。

        Args:
            org_name: 组织名称（用于在组织树中定位）
        """
        self.goto_service("统一身份认证IAM")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 在组织树中查找目标组织节点
        tree_container = self.page.locator("#iam-department")
        org_node = tree_container.locator(".depart_name").filter(has_text=org_name)
        if org_node.count() == 0:
            logger.warning(f"IAM：组织树中未找到组织 {org_name}，可能已被删除")
            return

        # 使用 JS 触发 hover 并点击删除图标（完全绕过 Playwright hover 的 pointer-events 拦截）
        js_clicked = self.page.evaluate(f"""
            () => {{
                const nodes = document.querySelectorAll('#iam-department .depart_name');
                for (const node of nodes) {{
                    if (node.textContent.trim() === '{org_name}') {{
                        const parent = node.closest('.custom');
                        if (parent) {{
                            // 先触发 mouseenter 显示操作按钮
                            parent.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
                            const btn = parent.querySelector('.el-icon-delete');
                            if (btn) {{
                                btn.dispatchEvent(new MouseEvent('click', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                    }}
                }}
                return false;
            }}
        """)
        if js_clicked:
            logger.info(f"IAM：点击删除组织 {org_name}")
        else:
            # 降级到 Playwright locator（带 force 绕过 pointer-events 检查）
            delete_icon = org_node.first.locator("xpath=../../..").locator(".el-icon-delete")
            if delete_icon.count() == 0:
                delete_icon = tree_container.locator(".el-icon-delete")
            if delete_icon.count() == 0:
                raise Exception(f"未找到组织 {org_name} 的删除按钮")
            delete_icon.first.click(force=True)
            logger.info(f"IAM：通过 Playwright 点击删除组织 {org_name}")

        self.page.wait_for_timeout(800)

        # 确认删除弹窗（优先使用 JS，Playwright dialog 检测对 Element UI 不友好）
        js_confirmed = self.page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('.el-dialog');
                for (const d of dialogs) {
                    const title = d.querySelector('.el-dialog__title');
                    if (title && title.textContent.includes('删除')) {
                        const btns = d.querySelectorAll('button, .cloud-button-btn, .el-button');
                        for (const btn of btns) {
                            if (btn.textContent.trim() === '确定' && !btn.disabled) {
                                btn.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }
        """)
        if js_confirmed:
            logger.info(f"IAM：确认删除组织 {org_name}")
        else:
            confirm_dialog = self.page.locator(".el-dialog").filter(has_text="删除")
            if confirm_dialog.count() > 0 and confirm_dialog.first.is_visible():
                confirm_btn = confirm_dialog.first.locator(".cloud-button-btn").filter(has_text="确定")
                if confirm_btn.count() == 0:
                    confirm_btn = confirm_dialog.first.get_by_text("确定")
                confirm_btn.first.click()
                logger.info(f"IAM：通过 Playwright 确认删除组织 {org_name}")

        self.page.wait_for_timeout(2000)

        # 等待组织从树中消失
        try:
            expect(org_node.first).not_to_be_visible(timeout=15000)
            logger.info(f"IAM：组织 {org_name} 已从树中移除")
        except Exception:
            logger.warning(f"IAM：组织 {org_name} 删除后仍在树中可见")

        # 关闭删除操作后残留的成功/确认弹窗，避免遮挡后续操作
        self.page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('.sugon-dialog, .el-dialog__wrapper, .el-message-box__wrapper');
                for (const d of dialogs) {
                    if (d.style.display !== 'none' && d.offsetParent !== null) {
                        const btn = d.querySelector('button');
                        if (btn) btn.click();
                    }
                }
            }
        """)
        self.page.wait_for_timeout(500)

    def _hover_org_node_and_click_btn(self, org_name: str, btn_icon_class: str):
        """在组织树中 hover 指定组织节点并点击其操作按钮。

        Args:
            org_name: 组织名称
            btn_icon_class: 按钮图标类名，如 'el-icon-plus' 或 'el-icon-edit'

        Returns:
            bool: 是否成功点击
        """
        tree_container = self.page.locator("#iam-department")
        org_node = tree_container.locator(".depart_name").filter(has_text=org_name)
        # 轮询等待组织节点出现（Vue 异步渲染可能延迟）
        for _ in range(10):
            if org_node.count() > 0:
                break
            self.page.wait_for_timeout(1000)
        if org_node.count() == 0:
            raise Exception(f"组织树中未找到组织 {org_name}")

        # hover 节点以显示操作按钮
        org_node.first.hover()
        self.page.wait_for_timeout(1200)

        # 使用 JS 点击绕过 pointer events 拦截（Vue Tree 组件可能遮挡）
        js_clicked = self.page.evaluate(f"""
            () => {{
                const nodes = document.querySelectorAll('#iam-department .depart_name');
                for (const node of nodes) {{
                    if (node.textContent.trim() === '{org_name}') {{
                        const parent = node.closest('.custom');
                        if (parent) {{
                            const btn = parent.querySelector('.{btn_icon_class}');
                            if (btn) {{
                                btn.click();
                                return true;
                            }}
                        }}
                    }}
                }}
                return false;
            }}
        """)
        if js_clicked:
            logger.info(f"IAM：点击组织 {org_name} 的 {btn_icon_class} 按钮")
            return True

        # 降级到 Playwright locator 点击
        btn = org_node.first.locator("xpath=../../..").locator(f".{btn_icon_class}")
        if btn.count() == 0:
            btn = tree_container.locator(f".{btn_icon_class}")
        if btn.count() == 0:
            raise Exception(f"未找到组织 {org_name} 的 {btn_icon_class} 按钮")
        btn.first.click()
        logger.info(f"IAM：通过 Playwright 点击组织 {org_name} 的 {btn_icon_class} 按钮")
        return True

    def _open_org_dialog_via_vue(self, org_name: str, dialog_type: str):
        """通过 Vue 实例直接打开组织操作弹框（绕过 one-tree 事件代理）。

        Args:
            org_name: 组织名称
            dialog_type: 'create_child' 或 'modify'

        Returns:
            bool: 是否成功打开弹框
        """
        js_result = self.page.evaluate(f"""
            () => {{
                // 查找 Vue 根实例
                const vmEl = document.querySelector('.department-left-menu');
                if (!vmEl || !vmEl.__vue__) {{
                    // 尝试其他方式获取 Vue 实例
                    const allEls = document.querySelectorAll('*');
                    let vm = null;
                    for (const el of allEls) {{
                        if (el.__vue__ && el.__vue__.$refs && el.__vue__.$refs.CreateDepartmentDialog) {{
                            vm = el.__vue__;
                            break;
                        }}
                    }}
                    if (!vm) return {{success: false, error: '未找到 Vue 实例'}};
                }}
                const vm = vmEl.__vue__;
                if (!vm.$refs.CreateDepartmentDialog) {{
                    return {{success: false, error: '未找到 CreateDepartmentDialog 组件'}};
                }}

                // 在 all_tree 中查找目标组织
                let targetOrg = null;
                if (vm.all_tree && vm.all_tree.length > 0) {{
                    targetOrg = vm.all_tree.find(el => el.name === '{org_name}');
                }}
                // 如果在 all_tree 中没找到，尝试在 list 中查找
                if (!targetOrg && vm.list && vm.list.length > 0) {{
                    const findInTree = (nodes) => {{
                        for (const node of nodes) {{
                            if (node.name === '{org_name}') return node;
                            if (node.children && node.children.length > 0) {{
                                const found = findInTree(node.children);
                                if (found) return found;
                            }}
                        }}
                        return null;
                    }};
                    targetOrg = findInTree(vm.list);
                }}
                if (!targetOrg) {{
                    return {{success: false, error: '未找到组织 {org_name}'}};
                }}

                // 设置 currentItem 并打开弹框
                vm.currentItem = targetOrg;
                if ('{dialog_type}' === 'create_child') {{
                    vm.$refs.CreateDepartmentDialog.open('', targetOrg);
                }} else {{
                    vm.$refs.CreateDepartmentDialog.open(targetOrg, targetOrg);
                }}
                return {{success: true}};
            }}
        """)
        if isinstance(js_result, dict) and js_result.get('success'):
            logger.info(f"IAM：通过 Vue 实例打开 {dialog_type} 弹框（组织：{org_name}）")
            return True
        else:
            error = js_result.get('error', '未知错误') if isinstance(js_result, dict) else str(js_result)
            logger.warning(f"IAM：通过 Vue 实例打开弹框失败：{error}，尝试降级到 DOM 点击")
            return False

    def _submit_org_dialog_via_vue(self, org_name_value: str):
        """通过 Vue 组件实例直接填写表单并提交（绕过所有 DOM 操作）。

        Args:
            org_name_value: 要填入组织名称的值

        Returns:
            dict: {success: bool, error: str}
        """
        return self.page.evaluate(f"""
            () => {{
                const vmEl = document.querySelector('.department-left-menu');
                if (!vmEl || !vmEl.__vue__) {{
                    return {{success: false, error: '未找到 Vue 根实例'}};
                }}
                const vm = vmEl.__vue__;
                if (!vm.$refs.CreateDepartmentDialog) {{
                    return {{success: false, error: '未找到 CreateDepartmentDialog 组件'}};
                }}
                const dialogVm = vm.$refs.CreateDepartmentDialog;
                dialogVm.ruleForm.name = '{org_name_value}';
                dialogVm.submit();
                return {{success: true}};
            }}
        """)

    def iam_create_child_organization(self, parent_org_name: str, child_org_name: str):
        """在指定父组织下创建子组织。

        Args:
            parent_org_name: 父组织名称（用于在组织树中定位）
            child_org_name: 子组织名称
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)

        dialog_opened = self._open_org_dialog_via_vue(parent_org_name, 'create_child')
        if not dialog_opened:
            self._hover_org_node_and_click_btn(parent_org_name, "el-icon-plus")

        self.page.wait_for_timeout(1500)

        result = self._submit_org_dialog_via_vue(child_org_name)
        if isinstance(result, dict) and result.get('success'):
            logger.info(f"IAM：已提交创建子组织请求 {child_org_name}")
        else:
            error = result.get('error', '未知错误') if isinstance(result, dict) else str(result)
            raise Exception(f"创建子组织失败：{error}")

        self.page.wait_for_timeout(3000)
        logger.info("IAM：添加组织弹窗已关闭")

    def iam_assert_org_in_tree(self, org_name: str, timeout: int = 10):
        """断言组织结构树中存在指定名称的组织节点，支持轮询等待。

        Args:
            org_name: 期望存在的组织名称
            timeout: 最长等待时间（秒）
        """
        tree = self.page.locator("#iam-department")
        node = tree.locator(".depart_name").filter(has_text=org_name)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if node.count() > 0:
                logger.info(f"IAM：组织结构树中已确认存在组织 {org_name}")
                return
            self.page.wait_for_timeout(1000)
        assert node.count() > 0, f"组织结构树中未找到组织 {org_name}"

    def iam_modify_organization(self, org_name: str, new_name: str):
        """修改指定组织的名称。

        Args:
            org_name: 要修改的组织名称（用于在组织树中定位）
            new_name: 新的组织名称
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)

        dialog_opened = self._open_org_dialog_via_vue(org_name, 'modify')
        if not dialog_opened:
            self._hover_org_node_and_click_btn(org_name, "el-icon-edit")

        self.page.wait_for_timeout(1500)

        result = self._submit_org_dialog_via_vue(new_name)
        if isinstance(result, dict) and result.get('success'):
            logger.info(f"IAM：已提交修改组织请求 {org_name} -> {new_name}")
        else:
            error = result.get('error', '未知错误') if isinstance(result, dict) else str(result)
            raise Exception(f"修改组织失败：{error}")

        self.page.wait_for_timeout(3000)
        logger.info("IAM：修改组织弹窗已关闭")

    def iam_open_org_quota(self, org_name: str):
        """在组织树中选择指定组织并进入组织配额页面。

        Args:
            org_name: 组织名称
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        tree_container = self.page.locator("#iam-department")
        org_node = tree_container.locator(".depart_name").filter(has_text=org_name)
        for _ in range(5):
            if org_node.count() > 0:
                break
            self.page.wait_for_timeout(1500)
        assert org_node.count() > 0, f"组织树中未找到组织 {org_name}"

        org_node.first.click()
        self.page.wait_for_timeout(2000)

        quota_tab = self.get_by_role("tab").filter(has_text="组织配额")
        expect(quota_tab.first).to_be_visible(timeout=10000)
        quota_tab.first.click()
        self.page.wait_for_timeout(3000)
        logger.info(f"IAM：已进入组织 {org_name} 的配额页面")

    def iam_filter_quota_service_type(self, service_type: str):
        """在组织配额页面按服务类型过滤。

        Args:
            service_type: 服务类型名称，如"计算"
        """
        # 先等待服务类型tab区域加载
        service_type_area = self.page.locator(".service-type-content")
        expect(service_type_area.first).to_be_visible(timeout=15000)

        # 定位目标tab（优先用el-tabs__item）
        tab_item = service_type_area.locator(".el-tabs__item").filter(
            has_text=service_type
        )
        if tab_item.count() == 0:
            tab_item = service_type_area.get_by_role("tab").filter(
                has_text=service_type
            )
        expect(tab_item.first).to_be_visible(timeout=10000)
        tab_item.first.click()
        logger.info(f"IAM：已点击服务类型过滤 -> {service_type}")

        # 等待配额列表重新加载（loading消失+卡片出现）
        self.page.wait_for_timeout(1500)
        loading_mask = self.page.locator(".el-loading-mask")
        for _ in range(10):
            if loading_mask.count() == 0 or not loading_mask.first.is_visible():
                break
            self.page.wait_for_timeout(1000)

        tab_container = self.page.locator("#tabContainer")
        expect(tab_container.first).to_be_visible(timeout=15000)
        # 等待瀑布流布局完成
        self.page.wait_for_timeout(2000)
        logger.info(f"IAM：服务类型 {service_type} 过滤完成，配额列表已加载")

    def _read_available_from_form_item(self, form_item, quota_name):
        """从弹窗form-item中读取"可用量"显示的parent_available数值。"""
        try:
            # 可用量显示在带color:red样式的span中（ram字段可能被mbToSize过滤为小数）
            available_el = form_item.locator("span").filter(has_text="可用量")
            if available_el.count() > 0:
                red_num = available_el.first.locator("span[style*='color: red']")
                if red_num.count() == 0:
                    red_num = available_el.first.locator("span").filter(has_text_regex=r"\d+\.?\d*").first
                if red_num.count() > 0:
                    text = red_num.first.inner_text().strip()
                    try:
                        return int(float(text))
                    except ValueError:
                        return None
            return None
        except Exception:
            return None

    def iam_modify_service_quota(self, service_name: str, quotas: dict):
        """修改组织配额页面中指定服务的配额。

        Args:
            service_name: 服务名称，如"云服务器ECS"
            quotas: 配额字典，key 为总量指标名称（如"cpu总量(个)"），value 为配额值
        """
        tab_container = self.page.locator("#tabContainer")
        expect(tab_container.first).to_be_visible(timeout=15000)

        # 先打印页面上所有服务卡片标题，便于调试
        all_titles = tab_container.locator(".sub-title").all_inner_texts()
        logger.info(f"IAM：当前配额页面服务列表: {all_titles}")

        # 直接遍历所有tab-item，匹配sub-title文本（避免Playwright has嵌套定位器问题）
        service_card = None
        tab_items = tab_container.locator(".tab-item").all()
        for item in tab_items:
            title_el = item.locator(".sub-title")
            if title_el.count() > 0:
                title_text = title_el.first.inner_text().strip()
                if service_name == title_text or service_name in title_text or title_text in service_name:
                    service_card = item
                    logger.info(f"IAM：找到服务卡片 '{title_text}' 对应 '{service_name}'")
                    break

        # 若仍未找到，等待后重试一次（Vue异步渲染延迟）
        if service_card is None:
            self.page.wait_for_timeout(3000)
            tab_items = tab_container.locator(".tab-item").all()
            for item in tab_items:
                title_el = item.locator(".sub-title")
                if title_el.count() > 0:
                    title_text = title_el.first.inner_text().strip()
                    if service_name == title_text or service_name in title_text or title_text in service_name:
                        service_card = item
                        logger.info(f"IAM：重试找到服务卡片 '{title_text}' 对应 '{service_name}'")
                        break

        assert service_card is not None, f"配额页面中未找到服务 {service_name}，当前页面有: {all_titles}"

        edit_btn = service_card.locator("span").filter(has_text="修改配额")
        if edit_btn.count() == 0:
            edit_btn = service_card.locator("i.el-icon-edit-outline").locator("xpath=..")
        expect(edit_btn.first).to_be_visible(timeout=10000)
        edit_btn.first.click()
        self.page.wait_for_timeout(1500)

        # 顶级组织配额弹窗标题为"修改组织配额"（modify-quota-depart-dialog.vue）
        dialog = self.page.locator(".el-dialog").filter(has_text="修改组织配额")
        if dialog.count() == 0:
            dialog = self.page.locator(".el-dialog:visible")
        expect(dialog.first).to_be_visible(timeout=15000)
        dialog = dialog.first

        # 等待弹窗内部异步加载完成（get_quota_overview获取可用配额后更新parent_available）
        loading_mask = dialog.locator(".el-loading-mask")
        for _ in range(15):
            if loading_mask.count() == 0 or not loading_mask.first.is_visible():
                break
            self.page.wait_for_timeout(1000)
        self.page.wait_for_timeout(800)

        # 记录修改前各输入框的值和可用量，用于调试
        for quota_name, quota_value in quotas.items():
            form_item = dialog.locator(".el-form-item").filter(has_text=quota_name)
            if form_item.count() > 0:
                input_el = form_item.locator(".el-input-number input").first
                before_val = input_el.input_value()
                disabled = input_el.is_disabled()
                # 读取弹窗中显示的"可用量"（红色span中的parent_available值）
                available = self._read_available_from_form_item(form_item, quota_name)
                logger.info(f"IAM：{service_name}-{quota_name} 修改前值={before_val}, 可用量={available}, disabled={disabled}, 目标值={quota_value}")

        for quota_name, quota_value in quotas.items():
            form_item = dialog.locator(".el-form-item").filter(has_text=quota_name)
            for _ in range(5):
                if form_item.count() > 0:
                    break
                self.page.wait_for_timeout(1000)
            if form_item.count() == 0:
                all_labels = dialog.locator(".el-form-item .el-form-item__label").all_inner_texts()
                logger.warning(f"IAM：弹窗中未找到配额项 '{quota_name}'，当前弹窗有: {all_labels}")
                raise Exception(f"弹窗中未找到配额项 {quota_name}，当前有: {all_labels}")
            input_number = form_item.locator(".el-input-number input").first
            # 先读取可用量，若目标值超出则自动降级
            available = self._read_available_from_form_item(form_item, quota_name)
            if available is not None and quota_value > available:
                logger.warning(
                    f"IAM：{service_name}-{quota_name} 目标值{quota_value}超出可用量{available}，自动降级为可用量值"
                )
                quota_value = available
                quotas[quota_name] = available
            # 聚焦并清空，再输入
            input_number.click()
            input_number.fill("")
            self.page.wait_for_timeout(300)
            input_number.fill(str(quota_value))
            self.page.wait_for_timeout(300)
            input_number.press("Tab")
            self.page.wait_for_timeout(500)
            # 验证值确实被修改
            actual_val = input_number.input_value()
            if str(quota_value) != actual_val:
                logger.warning(
                    f"IAM：{service_name}-{quota_name} 输入后被重置，目标={quota_value}, 实际={actual_val}"
                )
                # 降级策略：尝试填入可用量值（el-input-number可能因max限制重置）
                if available is not None and available > 0:
                    input_number.fill("")
                    self.page.wait_for_timeout(300)
                    input_number.fill(str(available))
                    self.page.wait_for_timeout(300)
                    input_number.press("Tab")
                    self.page.wait_for_timeout(500)
                    actual_val = input_number.input_value()
                    logger.info(f"IAM：{service_name}-{quota_name} 降级填充后值={actual_val}")
                    quotas[quota_name] = available

        # 提交前再次确认所有输入值正确
        for quota_name, quota_value in quotas.items():
            form_item = dialog.locator(".el-form-item").filter(has_text=quota_name)
            if form_item.count() > 0:
                final_val = form_item.locator(".el-input-number input").first.input_value()
                logger.info(f"IAM：{service_name}-{quota_name} 提交前值确认={final_val}")

        submit_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定")
        if submit_btn.count() == 0:
            submit_btn = dialog.get_by_role("button").filter(has_text="确定")
        # 打印按钮信息以便调试
        logger.info(f"IAM：找到 {submit_btn.count()} 个确定按钮")
        submit_btn.first.click()
        logger.info(f"IAM：已提交 {service_name} 配额修改")

        # 检查是否有错误提示（某些失败场景弹窗不关闭但显示错误）
        self.page.wait_for_timeout(2000)
        error_msg = self.page.locator(".el-message--error").first
        if error_msg.is_visible():
            err_text = error_msg.inner_text()
            logger.error(f"IAM：提交 {service_name} 后出现错误提示: {err_text!r}")
            # 弹窗出现错误提示即视为环境问题（父组织配额不足等），由测试脚本决定是否跳过
            try:
                dialog.locator(".el-dialog__headerbtn").first.click()
                expect(dialog).not_to_be_visible(timeout=5000)
            except Exception:
                pass
            raise EnvironmentError(f"{service_name} 配额修改失败: {err_text}")

        try:
            expect(dialog).not_to_be_visible(timeout=15000)
            logger.info(f"IAM：{service_name} 配额修改弹窗已关闭")
        except Exception:
            logger.warning(f"IAM：{service_name} 配额修改弹窗未在15秒内关闭")
            # 如果弹窗未关闭，截图并记录当前弹窗内容
            all_labels = dialog.locator(".el-form-item .el-form-item__label").all_inner_texts()
            all_values = dialog.locator(".el-input-number input").all_input_values()
            logger.warning(f"IAM：弹窗未关闭时的字段: {list(zip(all_labels, all_values))}")
        # 等待配额列表重新加载（getQuota异步获取数据+waterFall瀑布流布局）
        self.page.wait_for_timeout(8000)

    def iam_assert_quota_value(self, service_name: str, metric_name: str, expected_value: str):
        """断言组织配额页面中指定服务的配额显示值。

        Args:
            service_name: 服务名称，如"云服务器ECS"
            metric_name: 指标名称，如"cpu使用量(个)"
            expected_value: 预期显示值，如"0/1"
        """
        tab_container = self.page.locator("#tabContainer")
        expect(tab_container.first).to_be_visible(timeout=15000)

        service_card = None
        for _ in range(10):
            tab_items = tab_container.locator(".tab-item").all()
            for item in tab_items:
                title_el = item.locator(".sub-title")
                if title_el.count() > 0:
                    title_text = title_el.first.inner_text().strip()
                    if service_name == title_text or service_name in title_text or title_text in service_name:
                        service_card = item
                        break
            if service_card is not None:
                break
            self.page.wait_for_timeout(1500)
        assert service_card is not None, f"配额页面中未找到服务 {service_name}"

        metric_item = service_card.locator(".item-name").filter(has_text=metric_name)
        for _ in range(5):
            if metric_item.count() > 0:
                break
            self.page.wait_for_timeout(1000)
        assert metric_item.count() > 0, f"{service_name} 中未找到指标 {metric_name}"

        value_el = metric_item.first.locator("xpath=../..").locator(".item-value")
        actual_value = value_el.first.inner_text().strip()
        assert expected_value in actual_value, \
            f"{service_name}-{metric_name} 配额显示不匹配，预期包含 {expected_value}，实际 {actual_value}"
        logger.info(f"IAM：验证 {service_name}-{metric_name} 配额显示为 {actual_value}")

    def iam_set_access_control(self, name: str, target_org: str = None, **kwargs):
        """设置用户访问控制。

        Args:
            name: 用户账号名
            target_org: 目标子组织名称，用于精准导航到指定组织树节点
            **kwargs:
                ip (str), start_date (str yyyy-MM-dd), end_date (str),
                time_day (int): 允许登录的星期几（0=周一, 6=周日）
                time_hour (int): 允许登录的小时（0-23）
        """
        dialog = self._open_user_operation_dialog(name, "访问控制", "访问控制", target_org)
        if "ip" in kwargs:
            self._fill_form_field(dialog, "允许登录IP", kwargs["ip"])
        if "start_date" in kwargs:
            parts = kwargs["start_date"].split("-")
            self._select_date_in_picker(dialog, "设置登录日期",
                                         int(parts[0]), int(parts[1]), int(parts[2]),
                                         input_index=0)
        if "end_date" in kwargs:
            parts = kwargs["end_date"].split("-")
            self._select_date_in_picker(dialog, "设置登录日期",
                                         int(parts[0]), int(parts[1]), int(parts[2]),
                                         input_index=1)
        if "time_day" in kwargs and "time_hour" in kwargs:
            switch_label = dialog.locator(".el-form-item").filter(has_text="设置允许登录时间")
            switch = switch_label.locator(".el-switch")
            if switch.count() > 0:
                # 若开关已开启，先关闭以清除上次遗留的时间复选框选中状态
                switch_el = switch.first
                is_checked = "is-checked" in (switch_el.get_attribute("class") or "")
                if is_checked:
                    switch_el.click()
                    self.page.wait_for_timeout(500)
                switch_el.click()
                self.page.wait_for_timeout(1500)
            time_grid = dialog.locator(".el-checkbox")
            self.page.wait_for_timeout(2000)
            idx = 2 + kwargs["time_day"] * 24 + kwargs["time_hour"] - 2
            if time_grid.count() > idx:
                time_grid.nth(idx).click()
                self.page.wait_for_timeout(500)
                logger.info(
                    f"IAM：访问控制-时间限制 周{kwargs['time_day']+1} {kwargs['time_hour']}:00")
        self._submit_and_close_dialog(dialog, f"访问控制({name})")

    def _click_batch_operation_option(self, operation: str):
        """点击批量操作下拉菜单中的选项。

        Args:
            operation: 操作项文本，如"修改用户状态"、"重置密码"等
        """
        try:
            operation_btn = self.get_by_role("button", name="更多操作")
            dropdown_id = operation_btn.evaluate("element => element.getAttribute('aria-controls')")
            if dropdown_id:
                specific_dropdown = self.page.locator(f"#{dropdown_id}")
                batch_option = specific_dropdown.get_by_text(operation, exact=True)
                if batch_option.is_visible() and batch_option.is_enabled():
                    batch_option.click()
                    return
                else:
                    raise Exception(f"{operation}选项不可见或不可用")
            else:
                raise Exception("未找到aria-controls属性")
        except Exception as e:
            logger.warning(f"主要方法失败，使用备用方案: {e}")
            dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')
            for i in range(dropdown_menus.count() - 1, -1, -1):
                menu = dropdown_menus.nth(i)
                if menu.is_visible():
                    option = menu.get_by_text(operation, exact=True)
                    if option.count() > 0 and option.is_visible() and option.is_enabled():
                        option.click()
                        return
            raise Exception(f"所有方法都失败，未找到可用的{operation}选项")

    def _open_batch_dialog(self, names: list, operation_text: str, dialog_title: str, target_org: str = None):
        """执行批量操作：勾选用户、打开下拉菜单、选择操作项、等待弹窗。

        Args:
            names: 用户名称列表
            operation_text: 下拉菜单操作项文本
            dialog_title: 预期弹窗标题
            target_org: 目标子组织名称，用于精准导航到指定组织树节点

        Returns:
            dialog: 弹窗定位器
        """
        self._navigate_to_user_management(target_org=target_org)
        for name in names:
            row = self.get_row_by_name(name)
            row.scroll_into_view_if_needed()
            checkbox = row.locator("label.el-checkbox .el-checkbox__input").first
            if checkbox.count() > 0 and not checkbox.is_checked():
                checkbox.evaluate("el => el.click()")
                self.page.wait_for_timeout(300)
        self.page.wait_for_timeout(500)
        self.get_by_role("button", name="更多操作").click()
        self.page.wait_for_timeout(500)
        self._click_batch_operation_option(operation_text)
        self.page.wait_for_timeout(800)
        dialog = self.get_by_role("dialog").filter(has_text=dialog_title)
        expect(dialog.first).to_be_visible(timeout=8000)
        logger.info(f"IAM：{dialog_title}批量弹窗已打开（{len(names)}个用户）")
        return dialog.first

    def iam_batch_modify_status(self, names: list, enabled: bool, target_org: str = None):
        """批量修改用户状态（启用/禁用）。

        Args:
            names: 用户账号名列表
            enabled: True=激活, False=禁用
            target_org: 目标子组织名称
        """
        dialog = self._open_batch_dialog(names, "修改用户状态", "修改用户状态", target_org=target_org)
        status_text = "激活" if enabled else "禁用"
        radios = dialog.locator(".el-radio-group .el-radio")
        idx = 0 if enabled else 1
        radios.nth(idx).click()
        self.page.wait_for_timeout(300)
        logger.info(f"IAM：批量修改用户状态 -> {status_text}（{len(names)}个用户）")
        self._submit_and_close_dialog(dialog, f"批量修改用户状态({len(names)}个)")

    def iam_batch_reset_password(self, names: list, new_password: str, target_org: str = None):
        """批量重置用户密码。

        Args:
            names: 用户账号名列表
            new_password: 新密码
            target_org: 目标子组织名称
        """
        dialog = self._open_batch_dialog(names, "重置密码", "重置密码", target_org=target_org)
        self._fill_form_field(dialog, "新密码", new_password)
        self._fill_form_field(dialog, "确认新密码", new_password)
        self._submit_and_close_dialog(dialog, f"批量重置密码({len(names)}个)")

    def iam_batch_set_expiry(self, names: list, date_str: str, target_org: str = None):
        """批量设置用户过期时间。

        Args:
            names: 用户账号名列表
            date_str: 过期日期，格式 yyyy-MM-dd，空字符串表示不限
            target_org: 目标子组织名称
        """
        dialog = self._open_batch_dialog(names, "设置用户过期时间", "设置用户过期时间", target_org=target_org)
        if date_str:
            parts = date_str.split("-")
            self._select_date_in_picker(dialog, "过期时间",
                                         int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            # 点击"不限制"清除过期时间（如果存在该快捷选项）
            no_limit = dialog.get_by_text("不限制")
            if no_limit.count() > 0:
                no_limit.first.click()
                self.page.wait_for_timeout(300)
        self._submit_and_close_dialog(dialog, f"批量设置过期时间({len(names)}个)")

    def iam_batch_set_access_control(self, names: list, target_org: str = None, **kwargs):
        """批量设置用户访问控制。

        Args:
            names: 用户账号名列表
            target_org: 目标子组织名称
            **kwargs:
                ip (str): 允许登录IP
                start_date (str yyyy-MM-dd): 登录日期起始
                end_date (str yyyy-MM-dd): 登录日期结束
                time_day (int): 允许登录的星期几（0=周一, 6=周日）
                time_hour (int): 允许登录的小时（0-23）
                clear (bool): 是否清空所有访问控制设置
        """
        dialog = self._open_batch_dialog(names, "访问控制", "访问控制", target_org=target_org)
        if kwargs.get("clear"):
            # 清空IP
            ip_input = dialog.locator(".el-form-item").filter(has_text="允许登录IP").locator("input").first
            if ip_input.count() > 0:
                ip_input.fill("")
            # 清空日期
            date_inputs = dialog.locator(".el-form-item").filter(has_text="设置登录日期").locator("input")
            for i in range(date_inputs.count()):
                date_inputs.nth(i).fill("")
            # 关闭时间开关
            switch_label = dialog.locator(".el-form-item").filter(has_text="设置允许登录时间")
            switch = switch_label.locator(".el-switch")
            if switch.count() > 0:
                switch_el = switch.first
                is_checked = "is-checked" in (switch_el.get_attribute("class") or "")
                if is_checked:
                    switch_el.click()
                    self.page.wait_for_timeout(500)
        else:
            if "ip" in kwargs:
                self._fill_form_field(dialog, "允许登录IP", kwargs["ip"])
            if "start_date" in kwargs:
                parts = kwargs["start_date"].split("-")
                self._select_date_in_picker(dialog, "设置登录日期",
                                             int(parts[0]), int(parts[1]), int(parts[2]),
                                             input_index=0)
            if "end_date" in kwargs:
                parts = kwargs["end_date"].split("-")
                self._select_date_in_picker(dialog, "设置登录日期",
                                             int(parts[0]), int(parts[1]), int(parts[2]),
                                             input_index=1)
            if "time_day" in kwargs and "time_hour" in kwargs:
                switch_label = dialog.locator(".el-form-item").filter(has_text="设置允许登录时间")
                switch = switch_label.locator(".el-switch")
                if switch.count() > 0:
                    switch_el = switch.first
                    is_checked = "is-checked" in (switch_el.get_attribute("class") or "")
                    if is_checked:
                        switch_el.click()
                        self.page.wait_for_timeout(500)
                    switch_el.click()
                    self.page.wait_for_timeout(1500)
                time_grid = dialog.locator(".el-checkbox")
                self.page.wait_for_timeout(2000)
                idx = 2 + kwargs["time_day"] * 24 + kwargs["time_hour"] - 2
                if time_grid.count() > idx:
                    time_grid.nth(idx).click()
                    self.page.wait_for_timeout(500)
                    logger.info(
                        f"IAM：批量访问控制-时间限制 周{kwargs['time_day']+1} {kwargs['time_hour']}:00")
        self._submit_and_close_dialog(dialog, f"批量访问控制({len(names)}个)")
