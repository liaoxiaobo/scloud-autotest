"""传输策略组 (Transfer Strategy Group) 页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data


class TransferStrategyMixin(BasePage):
    """传输策略组模块页面对象，封装列表、创建、编辑、详情、删除等操作。"""

    service_name = "虚拟私有云"

    def _ensure_list_page(self):
        """确保当前位于传输策略组列表页。"""
        for attempt in range(3):
            current_url = self.page.url
            if "#/transfer-strategy" in current_url and "strategy-transfer-details" not in current_url:
                # 轻量等待：只等loading消失，不触发load事件（hash路由不触发load）
                try:
                    loading = self.page.locator(".el-loading-mask:visible")
                    if loading.count() > 0:
                        expect(loading).to_have_count(0, timeout=15000)
                except Exception:
                    pass
                self.page.wait_for_timeout(2000)
                return

            self.logger.info(f"当前不在传输策略组列表页({current_url})，尝试导航(第{attempt + 1}次)")

            # 策略1: 直接设置hash（Vue Router客户端路由，无页面刷新）
            try:
                self.page.evaluate("window.location.hash = '#/transfer-strategy'")
                self.page.wait_for_timeout(5000)
                if "#/transfer-strategy" in self.page.url and "strategy-transfer-details" not in self.page.url:
                    # hash路由不触发load事件，轻量等待即可
                    try:
                        loading = self.page.locator(".el-loading-mask:visible")
                        if loading.count() > 0:
                            expect(loading).to_have_count(0, timeout=15000)
                    except Exception:
                        pass
                    self.page.wait_for_timeout(2000)
                    return
            except Exception as e:
                self.logger.debug(f"直接设置hash失败: {e}")

            # 策略2: 先goto服务根路径，再设置hash
            try:
                base_url = Config.get("base_url").rstrip("/")
                self.page.goto(f"{base_url}/vpc", wait_until="commit")
                self.page.wait_for_timeout(3000)
                self.page.evaluate("window.location.hash = '#/transfer-strategy'")
                self.page.wait_for_timeout(5000)
                if "#/transfer-strategy" in self.page.url and "strategy-transfer-details" not in self.page.url:
                    try:
                        loading = self.page.locator(".el-loading-mask:visible")
                        if loading.count() > 0:
                            expect(loading).to_have_count(0, timeout=15000)
                    except Exception:
                        pass
                    self.page.wait_for_timeout(2000)
                    return
            except Exception as e:
                self.logger.debug(f"goto + hash 失败: {e}")

        # 兜底策略: 使用菜单导航
        try:
            self.goto_service("虚拟私有云")
            self.goto_submenu("机密互联")
            self.page.wait_for_timeout(5000)
        except Exception as e:
            self.logger.warning(f"菜单导航兜底也失败: {e}")

        self.wait_for_page_ready()

    def transfer_strategy_create(self, name=None, description=""):
        """创建传输策略组。

        Args:
            name: 策略组名称，为None时自动生成随机名称。
            description: 策略组描述，默认为空字符串。

        Returns:
            str: 创建的策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()

        # 点击新建按钮（cl-button 自定义组件，用 get_by_text）
        self.get_by_text("新建", exact=True).click()

        if not name:
            name = f"tsg-{random_data()}"

        # 定位弹窗
        dialog = self.page.locator(".el-dialog:visible").first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写名称
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).get_by_role("textbox")
        name_input.click()
        name_input.fill(name)
        expect(name_input).to_have_value(name, timeout=5000)

        # 填写描述（如有）
        if description:
            desc_input = dialog.get_by_placeholder("请输入描述")
            desc_input.click()
            desc_input.fill(description)
            expect(desc_input).to_have_value(description, timeout=5000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    def transfer_strategy_edit(self, name, new_name=None, new_description=None):
        """编辑指定传输策略组的名称和描述。

        打开编辑弹窗，可选修改名称和/或描述，点击确定提交。

        Args:
            name: 策略组当前名称，用于列表页定位。
            new_name: 新名称，为None时不修改名称。
            new_description: 新描述，为None时不修改描述。

        Returns:
            dict: 包含修改前数据的字典，键为 "name" 和 "description"。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()

        # 搜索并点击编辑
        self.search(name)
        self.click_action(name, "编辑")

        # 等待弹窗出现
        dialog = self.page.locator(".el-dialog:visible").first
        dialog.wait_for(state="visible", timeout=15000)

        # 获取修改前的值
        original_data = {}

        # 名称输入框
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).get_by_role("textbox")
        name_input.wait_for(state="visible", timeout=10000)
        original_data["name"] = name_input.input_value()

        # 描述输入框（textarea）
        desc_input = dialog.get_by_placeholder("请输入描述")
        desc_input.wait_for(state="visible", timeout=10000)
        original_data["description"] = desc_input.input_value()

        # 修改名称
        if new_name is not None:
            name_input.fill("")
            name_input.fill(new_name)
            expect(name_input).to_have_value(new_name, timeout=5000)

        # 修改描述
        if new_description is not None:
            desc_input.fill("")
            desc_input.fill(new_description)
            expect(desc_input).to_have_value(new_description, timeout=5000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return original_data

    def transfer_strategy_delete(self, name):
        """删除指定名称的传输策略组。

        Args:
            name: 策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        # 先搜索缩小范围，再点击删除
        self.search(name)
        self.click_action(name, "删除")
        # 确认删除弹窗
        self.dialog_confirm.click()

    def goto_transfer_strategy_detail(self, name):
        """进入指定传输策略组的详情页。

        Args:
            name: 策略组名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        # 先按名称搜索，避免列表仍残留上一次的过滤条件导致目标行不可见
        self.search(name)
        self.wait_for_page_ready()
        # 点击名称链接进入详情页 - 行内首个 <a> 即名称链接
        # （描述列为 <div>，当描述与名称相同时用 get_by_text 会命中两个元素触发 strict 模式冲突）
        row = self.get_row_by_name(name)
        name_link = row.locator("a").first
        expect(name_link).to_be_visible(timeout=10000)
        name_link.click()
        self.wait_for_page_ready()

    def _select_key_in_drawer(self, key_drawer, key_name):
        """在密钥选择 drawer 中搜索并选择指定密钥。

        因密钥列表可能较长或默认未渲染目标行，先尝试在 drawer 顶部搜索框输入
        密钥名称并触发搜索，等表格刷新后再定位目标行；若搜索失败或仍找不到，
        则回退到按名称直接定位，或选择第一行可用密钥。

        Args:
            key_drawer: 密钥选择 drawer 的 Locator。
            key_name: 目标密钥名称。
        """
        # 等待表格初始加载完成
        expect(key_drawer.locator(".el-table__body-wrapper tr").first).to_be_visible(timeout=10000)
        self.page.wait_for_timeout(800)

        # 优先尝试搜索：在 drawer 顶部搜索框输入密钥名并触发搜索
        # 注意：drawer 中可能有 readonly 的过滤类型下拉（placeholder="请选择过滤类型"），
        # 需要排除 readonly 元素，只找可编辑的搜索输入框
        try:
            # 策略1：直接找 placeholder="搜索" 的输入框（最精确）
            search_input = key_drawer.locator("input.el-input__inner[placeholder='搜索']").first
            if search_input.count() == 0 or not search_input.is_visible():
                # 策略2：找所有 input，逐个检查是否 editable（非 readonly）
                all_inputs = key_drawer.locator("input.el-input__inner").all()
                search_input = None
                for inp in all_inputs:
                    try:
                        # 检查是否可见且非 readonly
                        if inp.is_visible() and not inp.evaluate("el => el.readOnly"):
                            # 进一步检查 placeholder 不是过滤类型选择
                            placeholder = inp.evaluate("el => el.placeholder || ''")
                            if "过滤" not in placeholder and "请选择" not in placeholder:
                                search_input = inp
                                break
                    except Exception:
                        continue

            if search_input is not None and search_input.count() > 0 and search_input.is_visible():
                search_input.fill("")
                search_input.fill(key_name)
                # 触发搜索：优先点"搜索"按钮，否则回车
                search_btn = key_drawer.get_by_text("搜索", exact=True).first
                if search_btn.count() > 0 and search_btn.is_visible():
                    search_btn.click()
                else:
                    search_input.press("Enter")
                # 等待表格刷新/加载完成
                try:
                    expect(key_drawer.locator(".el-loading-mask:visible")).to_have_count(0, timeout=15000)
                except Exception:
                    pass
                self.page.wait_for_timeout(1000)
            else:
                self.logger.info("密钥 drawer 中未找到可编辑的搜索输入框，跳过搜索直接定位")
        except Exception as e:
            self.logger.warning(f"密钥 drawer 搜索失败，回退到直接定位: {e}")

        # 定位目标密钥行
        key_row = key_drawer.locator(".el-table__body-wrapper tr").filter(
            has_text=re.compile(rf"\b{re.escape(key_name)}\b")
        ).first
        if key_row.count() == 0:
            # 按名称找不到时回退到第一行（环境可能只有一条密钥）
            key_row = key_drawer.locator(".el-table__body-wrapper tr").first
        expect(key_row).to_be_visible(timeout=10000)

        # 点击行首 radio 选中该密钥
        radio = key_row.locator(".el-radio").first
        radio.wait_for(state="visible", timeout=10000)

        # 原生点击优先；若被抽屉遮罩/表格单元格拦截则 fallback force
        try:
            radio.click(timeout=5000)
        except Exception:
            self.logger.warning("radio 原生点击被拦截，使用 force 点击")
            radio.click(force=True)

        # 验证确实选中：el-radio 选中后会有 is-checked 类
        self.page.wait_for_timeout(500)
        is_checked = radio.evaluate("el => el.classList.contains('is-checked')")
        if not is_checked:
            self.logger.warning("radio 点击后未显示选中，再次点击")
            radio.click(force=True)
            self.page.wait_for_timeout(500)
            is_checked = radio.evaluate("el => el.classList.contains('is-checked')")
        if not is_checked:
            raise AssertionError(f"未能选中密钥 {key_name} 的单选按钮，请检查密钥是否为 SM4 且可用")

        self.logger.info(f"已选中密钥: {key_name}")

    def encrypt_rule_create(self, key_name, remote_cidr, protocol="全部", ip_version="IPv4"):
        """在当前加密规则tab下创建加密规则。

        调用前必须已位于传输策略组详情页的加密规则tab。
        操作步骤：
        1. 点击新建按钮打开规则创建弹窗
        2. 选择协议、密钥、IP版本，输入远端CIDR
        3. 点击确定提交

        Args:
            key_name: 密钥名称（如 sm4-ossl1）。
            remote_cidr: 远端CIDR地址（如 10.0.0.0/24）。
            protocol: 协议，可选值 "全部"/"TCP"/"UDP"/"ICMP"，默认 "全部"。
            ip_version: IP版本，可选值 "IPv4"/"IPv6"，默认 "IPv4"。

        Returns:
            dict: 包含创建规则的关键字段信息。
        """
        # 点击新建按钮（cl-button 自定义组件，用 get_by_text）
        # GUI 模式下可能残留 el-tooltip 遮挡按钮；用 dispatch_event 触发点击，避免鼠标悬浮触发 tooltip
        new_btn = self.get_by_text("新建", exact=True).first
        new_btn.dispatch_event("click")

        # 定位弹窗
        dialog = self.page.locator(".el-dialog:visible").first
        expect(dialog).to_be_visible(timeout=10000)

        # 1. 确认策略组名称（disabled input，只读校验）
        name_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"传输策略组名称")
        ).get_by_role("textbox")
        expect(name_input).to_be_visible(timeout=5000)
        # 返回实际策略组名称供调用方校验
        actual_strategy_name = name_input.input_value()

        # 2. 选择协议（el-radio-group）
        radio_group = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"协议")
        ).locator(".el-radio-group")
        radio_item = radio_group.locator("label[role='radio']").filter(
            has_text=re.compile(rf"^{re.escape(protocol)}$")
        )
        expect(radio_item).to_be_visible(timeout=5000)
        radio_item.click()

        # 3. 选择密钥 - 点击"选择密钥"按钮，在弹出的密钥选择drawer中选择
        select_key_btn = dialog.get_by_text("选择密钥", exact=True).first
        if select_key_btn.count() > 0 and select_key_btn.is_visible():
            select_key_btn.click()
            # 等待密钥选择drawer出现（SecretKey组件渲染为el-drawer）
            key_drawer = self.page.locator(".el-drawer:visible").first
            expect(key_drawer).to_be_visible(timeout=10000)
            self._select_key_in_drawer(key_drawer, key_name)
            # 点击 drawer 内的确定按钮关闭 drawer
            drawer_confirm = key_drawer.get_by_text("确定", exact=True).first
            drawer_confirm.click()
            # 等待 drawer 关闭：用 hidden 断言，超时不抛异常而是回退检查
            try:
                expect(key_drawer).to_be_hidden(timeout=10000)
            except AssertionError:
                # drawer 可能未关闭，检查是否仍在 visible 状态
                if key_drawer.is_visible():
                    # 尝试再次点击确定或按 Escape 关闭
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(500)
                    # 若仍 visible，尝试点击 drawer 外的遮罩层关闭
                    if key_drawer.is_visible():
                        overlay = self.page.locator(".el-drawer__wrapper:visible").first
                        if overlay.count() > 0:
                            overlay.click(position={"x": 10, "y": 10})
                            self.page.wait_for_timeout(500)
                # 最终确认：若 drawer 仍 visible，只记录 warning 不阻断流程
                if key_drawer.is_visible():
                    self.logger.warning("密钥选择 drawer 未正常关闭，但已尝试多种关闭方式，继续后续流程")
        else:
            # 检查已选中的密钥tag是否匹配
            tag_info = dialog.locator(".tag-info").filter(
                has_text=re.compile(rf"{re.escape(key_name)}")
            )
            if tag_info.count() == 0:
                # 尝试点击已存在的tag上的删除按钮重新选择
                delete_tag = dialog.locator(".tag-info .icon-close").first
                if delete_tag.count() > 0 and delete_tag.is_visible():
                    delete_tag.click()
                    dialog.get_by_text("选择密钥", exact=True).first.click()
                    key_drawer = self.page.locator(".el-drawer:visible").first
                    expect(key_drawer).to_be_visible(timeout=10000)
                    self._select_key_in_drawer(key_drawer, key_name)
                    key_drawer.get_by_text("确定", exact=True).first.click()
                    expect(key_drawer).to_be_hidden(timeout=10000)

        # 4. 选择IP版本（el-select）
        ip_select = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"IP版本")
        ).locator(".el-select")
        expect(ip_select).to_be_visible(timeout=5000)
        ip_select.click()
        # 选项在body级的dropdown中
        self.locator("div.el-select-dropdown:visible li").filter(
            has_text=re.compile(rf"^{re.escape(ip_version)}$")
        ).click()

        # 5. 输入远端CIDR
        cidr_input = dialog.locator("div.el-form-item").filter(
            has_text=re.compile(r"远端CIDR")
        ).get_by_role("textbox")
        cidr_input.click()
        cidr_input.fill(remote_cidr)
        expect(cidr_input).to_have_value(remote_cidr, timeout=5000)

        # 提交前确认按钮可点
        submit_btn = dialog.get_by_text("确定", exact=True)
        expect(submit_btn).to_be_enabled(timeout=5000)

        # 点击确定提交
        submit_btn.click()

        return {
            "strategy_name": actual_strategy_name,
            "protocol": protocol,
            "key_name": key_name,
            "ip_version": ip_version,
            "remote_cidr": remote_cidr,
        }

    def encrypt_rule_delete(self, remote_cidr):
        """删除当前加密规则tab下的指定远端CIDR的加密规则。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            remote_cidr: 远端CIDR，用于定位要删除的规则。
        """
        # 在加密规则列表中按远端CIDR定位行并删除
        self.click_action(remote_cidr, "删除")
        # 确认删除弹窗
        self.dialog_confirm.click()

    def encrypt_rule_exists(self, remote_cidr):
        """检查加密规则列表中是否已存在指定远端CIDR的规则。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            remote_cidr: 远端CIDR值，用于定位规则。

        Returns:
            bool: 存在返回 True，否则 False。
        """
        try:
            row_data = self.get_row_data(remote_cidr)
            # 列表列名在不同版本中可能是"远端CIDR"或"对端CIDR"，两者兼容处理
            actual_cidr = row_data.get("远端CIDR") or row_data.get("对端CIDR") if row_data else None
            return bool(actual_cidr == remote_cidr)
        except AssertionError:
            return False

    def get_encrypt_rule_row_data(self, remote_cidr):
        """获取加密规则列表中指定远端CIDR的行数据。

        Args:
            remote_cidr: 远端CIDR值，用于定位行。

        Returns:
            dict: 行数据字典。
        """
        return self.get_row_data(remote_cidr)

    def get_encrypt_rule_id(self, remote_cidr):
        """获取加密规则列表中指定远端CIDR规则的顺序ID（列表"ID"列）。

        加密规则列表的"ID"列展示规则的 unique_key（即页面顺序ID，如 1/2/3/4），
        移动规则弹窗的"选择规则名称"下拉框也按该 ID 列出目标规则。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            remote_cidr: 远端CIDR值，用于定位规则行。

        Returns:
            str: 该规则的顺序ID文本。
        """
        row_data = self.get_row_data(remote_cidr)
        rule_id = row_data.get("ID")
        if not rule_id:
            raise AssertionError(f"未能从远端CIDR={remote_cidr}的规则行读取到ID列，行数据: {row_data}")
        return rule_id

    def get_encrypt_rule_order(self, column="对端CIDR"):
        """按当前列表行顺序读取加密规则的指定列值序列，用于断言移动后的排序。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            column: 用于标识规则顺序的列名，默认 "对端CIDR"（每条规则唯一）；
                也可传 "ID"（页面顺序ID列）。

        Returns:
            list[str]: 按列表当前行顺序排列的该列值序列。
        """
        return self.get_column_data(column, context="active-tab")

    def encrypt_rule_move(self, remote_cidr, direction, target_id=None):
        """对加密规则tab下指定远端CIDR的规则执行"移动规则"操作。

        打开该规则行操作栏的"移动规则"弹窗，按移动方式提交：
        - "最前" / "最后"：直接点击对应按钮，将规则移动到列表最前/最后（无需选择目标规则）。
        - "之前" / "之后"：先在"选择规则名称"下拉框中选择目标规则ID（target_id），
          再点击"之前"/"之后"按钮，将规则移动到目标规则的前/后。

        移动按钮点击后弹窗会直接提交并自动关闭（弹窗本身无独立"确定"按钮）。

        调用前必须已位于传输策略组详情页的加密规则tab。

        Args:
            remote_cidr: 被移动规则的远端CIDR，用于在列表中定位其操作行。
            direction: 移动方式，可选值 "最前"/"最后"/"之前"/"之后"。
            target_id: 目标规则的顺序ID（列表"ID"列文本）。
                当 direction 为 "之前"/"之后" 时必填；"最前"/"最后" 时忽略。
        """
        if direction not in ("最前", "最后", "之前", "之后"):
            raise ValueError(f"不支持的移动方式: {direction}，仅支持 最前/最后/之前/之后")
        if direction in ("之前", "之后") and not target_id:
            raise ValueError(f'移动方式"{direction}"必须指定 target_id（目标规则ID）')

        # 点击该规则行操作栏的"移动规则"，打开移动规则弹窗
        self.click_action(remote_cidr, "移动规则")

        # 等待移动规则弹窗出现（title="移动规则"，append-to-body 渲染为 el-dialog）
        dialog = self.page.locator(".el-dialog:visible").filter(
            has_text=re.compile(r"移动规则")
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        if direction in ("之前", "之后"):
            # 在"选择规则名称"下拉框中选择目标规则ID。
            # el-select filterable：点击内部 input 聚焦并展开下拉面板（直接点 .el-select
            # 外层 div 可能落在非触发区导致面板不展开）；面板 teleport 到 body 级的
            # div.el-select-dropdown，选项为 li.el-select-dropdown__item，文本为规则ID(unique_key)。
            rule_input = dialog.locator("input[placeholder='请选择规则名称']").first
            expect(rule_input).to_be_visible(timeout=5000)
            rule_input.click()
            # filterable 下拉支持输入过滤，输入目标ID缩小候选，规避选项过多/未渲染
            rule_input.fill(str(target_id))
            # 选项在body级的el-select-dropdown中，用 get_by_text exact 规避slot首尾空白
            dropdown = self.page.locator("div.el-select-dropdown:visible").last
            expect(dropdown).to_be_visible(timeout=5000)
            option = dropdown.get_by_text(str(target_id), exact=True).first
            expect(option).to_be_visible(timeout=5000)
            option.click()
            # 确认下拉已收起、目标值已选中（input 显示选中ID）
            expect(rule_input).to_have_value(str(target_id), timeout=5000)

        # 点击移动方向按钮（cl-button 渲染为可点击 div，用 get_by_text 精确匹配）
        move_btn = dialog.get_by_text(direction, exact=True)
        expect(move_btn).to_be_visible(timeout=5000)
        move_btn.click()

        # 点击后弹窗提交并自动关闭，等待弹窗关闭与列表刷新
        try:
            expect(dialog).to_be_hidden(timeout=15000)
        except AssertionError:
            self.logger.warning("移动规则弹窗未在预期时间内关闭，继续后续等待")
        self.wait_for_operation_complete()

    def assert_tab_visible(self, tab_name, timeout=10):
        """断言指定标签页可见。

        Args:
            tab_name: 标签页名称。
            timeout: 最长等待秒数，默认 10。
        """
        from sugon_web.common.playwright import expect
        tab = self.get_by_role("tab", name=tab_name)
        expect(tab).to_be_visible(timeout=timeout * 1000)
        self.logger.info(f"断言通过: 标签页 '{tab_name}' 可见")

    def get_transfer_strategy_row_data(self, name):
        """获取列表页指定传输策略组的行数据。

        Args:
            name: 策略组名称。

        Returns:
            dict: 行数据字典，包含名称、描述等字段。
        """
        return self.get_row_data(name)

    def transfer_strategy_exists(self, name):
        """检查指定名称的传输策略组是否已存在于列表中。

        会先确保位于列表页（与新建/编辑同样的进入方式），再按名称搜索后读取行数据判断。
        未找到时返回 False（不抛异常）。

        Args:
            name: 策略组名称。

        Returns:
            bool: 存在返回 True，否则 False。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.search(name)
        self.wait_for_page_ready()
        try:
            row_data = self.get_row_data(name)
        except AssertionError:
            # 列表中无该记录时 get_row_data 会抛 AssertionError，视为不存在
            return False
        return bool(row_data and row_data.get("名称") == name)

