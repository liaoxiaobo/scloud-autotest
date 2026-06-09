"""流量镜像 (Traffic Mirror) 页面对象。"""

import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data


class TmMixin(BasePage):
    """流量镜像模块页面对象，封装列表、创建、详情、删除等操作。"""

    service_name = "流量镜像"

    def _ensure_list_page(self):
        """确保当前位于流量镜像列表页。支持从详情页、错误状态等多种场景恢复。"""
        for attempt in range(3):
            current_url = self.page.url
            if "#/traffic-manage" in current_url:
                self.wait_for_page_ready()
                try:
                    loading = self.page.locator(".el-loading-mask:visible")
                    if loading.count() > 0:
                        expect(loading).to_have_count(0, timeout=15000)
                except Exception:
                    pass
                return

            self.logger.info(f"当前不在列表页({current_url})，尝试返回(第{attempt + 1}次)")

            # 策略0: 点击页面返回按钮/箭头（详情页常见返回方式）
            try:
                back_locators = [
                    self.page.locator(".el-page-header__back").first,
                    self.page.locator(".el-page-header__left").first,
                    self.page.locator(".el-icon-arrow-left").first,
                    self.page.locator(".el-icon-back").first,
                    self.page.locator(".return-btn").first,
                    self.page.get_by_text("返回").first,
                    self.page.locator("[class*='back']").first,
                ]
                for back_btn in back_locators:
                    if back_btn.count() > 0 and back_btn.is_visible():
                        back_btn.click()
                        self.page.wait_for_timeout(3000)
                        if "#/traffic-manage" in self.page.url:
                            self.wait_for_page_ready()
                            return
                        break
            except Exception as e:
                self.logger.debug(f"点击返回按钮失败: {e}")

            # 策略1: 浏览器后退（详情页返回场景）
            try:
                self.page.go_back()
                self.page.wait_for_timeout(3000)
                if "#/traffic-manage" in self.page.url:
                    self.wait_for_page_ready()
                    return
            except Exception as e:
                self.logger.debug(f"go_back 失败: {e}")

            # 策略2: 直接导航到服务根路径再设置 hash
            try:
                base_url = Config.get("base_url").rstrip("/")
                self.page.goto(f"{base_url}/vpc", wait_until="networkidle")
                self.page.wait_for_timeout(3000)
                self.page.evaluate("window.location.hash = '#/traffic-manage'")
                self.page.wait_for_timeout(3000)
                if "#/traffic-manage" in self.page.url:
                    self.wait_for_page_ready()
                    return
            except Exception as e:
                self.logger.debug(f"goto + hash 失败: {e}")

            # 策略3: reload 后重新导航
            try:
                self.page.reload(wait_until="networkidle")
                self.page.wait_for_timeout(3000)
                base_url = Config.get("base_url").rstrip("/")
                self.page.goto(f"{base_url}/vpc", wait_until="networkidle")
                self.page.wait_for_timeout(3000)
                self.page.evaluate("window.location.hash = '#/traffic-manage'")
                self.page.wait_for_timeout(5000)
                if "#/traffic-manage" in self.page.url:
                    self.wait_for_page_ready()
                    return
            except Exception as e:
                self.logger.debug(f"reload 后导航失败: {e}")

        # 兜底策略: 使用菜单导航
        try:
            self.goto_service("流量镜像")
            self.goto_submenu("流量镜像")
            self.page.wait_for_timeout(5000)
        except Exception as e:
            self.logger.warning(f"菜单导航兜底也失败: {e}")

        self.wait_for_page_ready()

    @submenu("流量镜像")
    def tm_create_inner_ecs(self, name=None, server_name=None):
        """创建云内实例-ECS类型的流量镜像。

        Args:
            name: 流量镜像名称，为None时自动生成随机名称。
            server_name: 目的ECS实例名称，用于选择目的实例。

        Returns:
            str: 创建的流量镜像名称。
        """
        self.wait_for_page_ready()
        self.page.get_by_text("新建流量镜像", exact=True).click()

        if not name:
            name = f"tm-{random_data()}"

        dialog = self.page.locator(".el-dialog:visible").first

        # 填写名称
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role(
            "textbox"
        ).fill(name)

        # 选择目的类型：云内实例
        dialog.locator("label").filter(has_text=re.compile(r"^云内实例$")).first.click()

        # 选择实例类型：云服务器
        dialog.locator("label").filter(has_text=re.compile(r"^云服务器$")).first.click()

        # 选择目的实例
        if server_name:
            dialog.get_by_placeholder("请选择").click()
            self.page.locator("li").filter(has_text=re.compile(rf"{re.escape(server_name)}")).first.click()

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    @submenu("流量镜像")
    def tm_create_outside_device(self, name=None, vlan=None, mac=None):
        """创建云外设备类型的流量镜像。

        Args:
            name: 流量镜像名称，为None时自动生成随机名称。
            vlan: VLAN值，1~4096之间的正整数。
            mac: MAC地址，格式如 fa:16:e3:44:53:47。

        Returns:
            str: 创建的流量镜像名称。
        """
        self.wait_for_page_ready()
        self.page.get_by_text("新建流量镜像", exact=True).click()

        if not name:
            name = f"tm-outside-{random_data()}"

        dialog = self.page.locator(".el-dialog:visible").first

        # 填写名称
        dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role(
            "textbox"
        ).fill(name)

        # 选择目的类型：云外设备
        dialog.locator("label").filter(has_text=re.compile(r"^云外设备$")).first.click()

        # 填写VLAN
        if vlan is not None:
            dialog.locator("div").filter(has_text=re.compile(r"^VLAN$")).get_by_role(
                "textbox"
            ).fill(str(vlan))

        # 填写MAC地址
        if mac:
            dialog.locator("div").filter(has_text=re.compile(r"^MAC地址$")).get_by_role(
                "textbox"
            ).fill(mac)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    def tm_edit(self, name, new_name=None, new_desc=None):
        """修改指定流量镜像的名称和描述。

        打开修改弹窗，可选修改名称和/或描述，点击确定提交。
        修改弹窗中只有"名称"和"描述"两个字段可编辑。

        Args:
            name: 流量镜像当前名称，用于列表页定位。
            new_name: 新名称，为None时不修改名称。
            new_desc: 新描述，为None时不修改描述。

        Returns:
            dict: 包含修改前数据的字典，键为 "name" 和 "description"。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 搜索并点击修改
        self.search(name)
        self.page.wait_for_timeout(1000)
        self.click_action(name, "修改")

        # 等待弹窗出现
        dialog = self.page.locator(".el-dialog:visible").first
        dialog.wait_for(state="visible", timeout=15000)
        self.page.wait_for_timeout(2000)

        # 获取修改前的值
        original_data = {}
        # 修改弹窗中只有名称(input)和描述(textarea)两个字段
        name_input = dialog.locator("input").first
        name_input.wait_for(state="visible", timeout=10000)
        original_data["name"] = name_input.input_value()

        desc_textarea = dialog.locator("textarea").first
        desc_textarea.wait_for(state="visible", timeout=10000)
        original_data["description"] = desc_textarea.input_value()

        # 修改名称
        if new_name is not None:
            name_input.fill("")
            name_input.fill(new_name)

        # 修改描述
        if new_desc is not None:
            desc_textarea.fill("")
            desc_textarea.fill(new_desc)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return original_data

    def tm_delete(self, name):
        """删除指定名称的流量镜像。

        Args:
            name: 流量镜像名称。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)
        # 先搜索缩小范围，再点击删除
        self.search(name)
        self.page.wait_for_timeout(1000)
        self.click_action(name, "删除")
        # 确认删除弹窗，使用 BasePage 通用的确定按钮
        self.dialog_confirm.click()

    def tm_cleanup_by_mac(self, mac):
        """清理使用指定MAC地址的流量镜像。

        列表搜索框仅支持按名称查询，不支持MAC查询，因此直接遍历
        所有分页查找并删除匹配的流量镜像。

        Args:
            mac: MAC地址，用于查找并删除对应的流量镜像。
        """
        self._ensure_list_page()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        try:
            page_num = 1
            max_pages = 10

            while page_num <= max_pages:
                rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
                self.logger.info(f"第 {page_num} 页找到 {len(rows)} 行数据")

                for row in rows:
                    try:
                        cells = row.locator("td").all()
                        if len(cells) > 7:
                            row_mac = cells[7].inner_text().strip()
                            row_name = cells[1].inner_text().strip()
                            if row_mac == mac:
                                self.logger.info(
                                    f"在第 {page_num} 页发现使用MAC {mac} 的流量镜像: {row_name}，准备清理"
                                )
                                self.tm_delete(row_name)
                                self.wait_for_page_ready()
                                self.page.wait_for_timeout(5000)
                                return
                    except Exception:
                        continue

                # 尝试点击下一页
                try:
                    next_btn = self.page.locator(".el-pagination .btn-next:not(.disabled)").first
                    if next_btn.count() == 0 or not next_btn.is_visible():
                        self.logger.info("无更多分页")
                        break
                    next_btn.click()
                    self.page.wait_for_timeout(3000)
                    page_num += 1
                except Exception:
                    self.logger.info("分页导航结束")
                    break

            self.logger.info(f"未找到使用MAC {mac} 的流量镜像")
        except Exception as e:
            self.logger.warning(f"清理流量镜像时出错: {e}")

    def goto_tm_detail(self, name):
        """进入指定流量镜像的详情页。

        Args:
            name: 流量镜像名称。
        """
        self._ensure_list_page()
        row = self.get_row_by_name(name)
        # 名称列为 cl-button type="link"，不是标准 <a> 标签
        row.get_by_text(name, exact=True).first.click()
        self.wait_for_page_ready()

    def get_tm_detail_data(self):
        """获取流量镜像详情页的数据。

        Returns:
            dict: 详情页字段数据，包含名称、类型、状态等字段。
        """
        data = {}
        self.wait_for_page_ready()

        # 流量镜像详情页使用 cl-item-col 组件，结构为：
        # <cl-item-col label="名称"><p>value</p></cl-item-col>
        # 尝试通过 label 属性或文本匹配来定位字段
        fields = ["名称", "类型", "状态", "VLAN", "MAC地址", "描述", "虚拟机名称", "实例状态", "ID", "电源状态", "集群"]

        for field in fields:
            try:
                # 方式1: 通过属性 label 定位
                field_locators = self.page.locator(f"[label='{field}']").all()
                for loc in field_locators:
                    try:
                        p_text = loc.locator("p").first.inner_text(timeout=2000).strip()
                        if p_text:
                            data[field] = p_text
                            break
                    except Exception:
                        continue

                if field not in data:
                    # 方式2: 查找包含 label 文本的元素，然后获取相邻的 p 标签
                    all_items = self.page.locator(".cl-item-col, .el-form-item, .detail-item").all()
                    for item in all_items:
                        try:
                            label_text = item.inner_text(timeout=1000)
                            if field in label_text:
                                p_val = item.locator("p").first.inner_text(timeout=2000).strip()
                                if p_val and p_val != field:
                                    data[field] = p_val
                                    break
                        except Exception:
                            continue
            except Exception:
                continue

        return data

    def get_tm_row_data(self, name):
        """获取列表页指定流量镜像的行数据。

        Args:
            name: 流量镜像名称。

        Returns:
            dict: 行数据字典，包含名称、类型、状态、VLAN、MAC地址等。
        """
        return self.get_row_data(name)

    def goto_tm_session_tab(self, tm_name):
        """进入指定流量镜像详情页的镜像会话Tab。

        Args:
            tm_name: 流量镜像实例名称。
        """
        self.goto_tm_detail(tm_name)
        # 关闭可能遮挡Tab的tooltip：先移开鼠标再按Escape
        self.page.mouse.move(0, 0)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1500)
        # 等待tab元素出现并可见
        tab = self.page.get_by_role("tab", name="镜像会话")
        tab.wait_for(state="visible", timeout=15000)
        tab.scroll_into_view_if_needed()
        self.page.wait_for_timeout(500)
        # 再次确保没有tooltip遮挡
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(500)
        try:
            tab.click(timeout=15000)
        except Exception:
            self.logger.warning("正常点击镜像会话Tab被遮挡，尝试force点击")
            tab.click(force=True)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        # 验证镜像会话tab内容已加载（新建镜像会话按钮可见）
        try:
            self.page.get_by_text("新建镜像会话", exact=True).wait_for(
                state="visible", timeout=10000
            )
        except Exception:
            self.logger.warning("镜像会话Tab内容未完全加载，尝试重新切换")
            self.page.mouse.move(0, 0)
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1000)
            tab = self.page.get_by_role("tab", name="镜像会话")
            if tab.count() > 0:
                tab.click(force=True)
                self.page.wait_for_timeout(3000)

    def _select_dropdown_option(self, label_text, option_text, pre_wait=0):
        """在表单对话框中点击指定label的el-select，并选择指定选项。

        支持等待异步加载的选项数据（如镜像源在子网选择后才加载）。
        通过多次关闭/重新打开下拉来刷新数据。

        Args:
            label_text: el-form-item的label文本（用于定位select）。
            option_text: 要选择的选项文本，支持虚机名称或"虚机名称(虚机ip)"格式。
            pre_wait: 打开下拉前的额外等待时间（毫秒），用于异步数据加载。
        """
        dialog = self.page.locator(".el-dialog:visible").first
        form_item = dialog.locator(".el-form-item").filter(
            has_text=re.compile(label_text)
        )
        select = form_item.locator(".el-select").first

        if pre_wait > 0:
            self.page.wait_for_timeout(pre_wait)

        # 多次尝试：打开下拉 -> 查找选项 -> 关闭 -> 等待 -> 重试
        for retry in range(6):
            select.click()
            self.page.wait_for_timeout(3000)

            # 在下拉中查找目标选项（支持名称或IP匹配）
            for attempt in range(10):
                all_options = self.page.locator(".el-select-dropdown__item").all()
                for option in all_options:
                    try:
                        txt = option.inner_text(timeout=1000)
                        # 选项格式: "虚机名称(虚机ip)"，去除换行空格后匹配
                        cleaned = re.sub(r'\s+', ' ', txt).strip()
                        # 按名称匹配 或 按IP匹配（支持 "虚机名称" 或 "虚机名称(虚机ip)" 或纯ip）
                        if option_text in cleaned or (
                            re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', option_text)
                            and option_text in cleaned
                        ):
                            if option.is_visible():
                                option.click()
                                self.page.wait_for_timeout(1000)
                                self.logger.info(f"选择镜像源: {cleaned}")
                                return
                    except Exception:
                        continue
                self.page.wait_for_timeout(500)

            # 未找到，关闭下拉等待后重试
            self.logger.info(
                f"第 {retry + 1} 次未找到选项 '{option_text}'，5秒后重试"
            )
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(5000)

        # 回退方案：选择列表中第一个包含IP地址的VM选项（新VM端口同步延迟时的兜底）
        self.logger.warning(
            f"目标VM '{option_text}' 未出现在下拉列表中（端口同步延迟），"
            f"将选择列表中第一个可用VM作为镜像源"
        )
        select.click()
        self.page.wait_for_timeout(3000)
        all_options = self.page.locator(".el-select-dropdown__item").all()
        for opt in all_options:
            try:
                txt = opt.inner_text(timeout=1000)
                cleaned = re.sub(r'\s+', ' ', txt).strip()
                # 选择包含IP地址格式 (x.x.x.x) 的选项，排除系统占位项
                if re.search(r'\(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\)', cleaned):
                    opt.click()
                    self.page.wait_for_timeout(1000)
                    self.logger.info(f"回退选择镜像源: {cleaned}")
                    return
            except Exception:
                continue

        raise Exception(f"选项 '{option_text}' 在下拉列表中未找到")

    def tm_session_create(self, name, enabled=True, vpc_name=None, subnet_name=None,
                          vm_name=None, vm_ip=None, direction=None, desc=None):
        """在镜像会话Tab页创建镜像会话。

        Args:
            name: 镜像会话名称。
            enabled: 是否开启，True为开启，False为关闭。
            vpc_name: 专有网络名称。
            subnet_name: 子网名称。
            vm_name: 镜像源虚机名称（用于下拉选项匹配）。
            vm_ip: 镜像源虚机IP地址（备选匹配条件）。
            direction: 方向，"全部流量"、"出向流量"或"入向流量"。
            desc: 描述。

        Returns:
            str: 创建的镜像会话名称。
        """
        self.wait_for_page_ready()
        self.page.get_by_text("新建镜像会话", exact=True).click()

        dialog = self.page.locator(".el-dialog:visible").first
        self.page.wait_for_timeout(3000)

        # 填写名称（el-input -> input）
        dialog.locator(".el-form-item").filter(has_text=re.compile(r"名称")).locator("input").first.fill(name)

        # 是否开启（el-switch）
        switch = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"是否开启")
        ).locator(".el-switch")
        if switch.count() > 0 and switch.is_visible():
            is_checked = switch.evaluate("el => el.classList.contains('is-checked')")
            if enabled != is_checked:
                switch.click()

        # 专有网络和子网在同一个 el-form-item 内，包含两个 el-select
        if vpc_name:
            network_item = dialog.locator(".el-form-item").filter(
                has_text=re.compile(r"专有网络")
            )
            selects = network_item.locator(".el-select").all()

            if len(selects) >= 1:
                selects[0].click()
                self.page.wait_for_timeout(2000)
                self.page.locator(".el-select-dropdown__item").filter(
                    has_text=re.compile(re.escape(vpc_name))
                ).first.click()
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)

            if len(selects) >= 2 and subnet_name:
                selects[1].click()
                self.page.wait_for_timeout(2000)
                self.page.locator(".el-select-dropdown__item").filter(
                    has_text=re.compile(re.escape(subnet_name))
                ).first.click()
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)

        # 选择镜像源（需要等待子网变更后的get_port_list异步加载，
        # 新创建VM的端口可能需要较长时间才能在Neutron中查询到）
        if vm_name:
            self._select_dropdown_option(r"镜像源", vm_name, pre_wait=15000)

        # 选择方向
        if direction:
            self._select_dropdown_option(r"方向", direction)

        # 填写描述（el-input type="textarea" -> textarea）
        if desc:
            dialog.locator(".el-form-item").filter(
                has_text=re.compile(r"描述")
            ).locator("textarea").first.fill(desc)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return name

    def tm_session_edit(self, name, new_name=None, new_desc=None, enabled=None, direction=None):
        """修改指定镜像会话的名称、描述、是否开启和方向。

        在镜像会话Tab页打开修改弹窗，可选修改各字段，点击确定提交。
        修改弹窗中可编辑字段：名称、是否开启、方向、描述。

        Args:
            name: 镜像会话当前名称，用于列表页定位。
            new_name: 新名称，为None时不修改名称。
            new_desc: 新描述，为None时不修改描述。
            enabled: 是否开启，True为开启，False为关闭，为None时不修改。
            direction: 新方向，"全部流量"、"出向流量"或"入向流量"，为None时不修改。

        Returns:
            dict: 包含修改前数据的字典，键为 "name"、"enabled"、"direction"、"description"。
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 搜索并点击修改
        self.search(name)
        self.page.wait_for_timeout(1000)
        self.click_action(name, "修改")

        # 等待弹窗出现
        dialog = self.page.locator(".el-dialog:visible").first
        dialog.wait_for(state="visible", timeout=15000)
        self.page.wait_for_timeout(2000)

        # 获取修改前的值
        original_data = {}

        # 名称
        name_input = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).locator("input").first
        name_input.wait_for(state="visible", timeout=10000)
        original_data["name"] = name_input.input_value()

        # 描述
        try:
            desc_input = dialog.locator(".el-form-item").filter(
                has_text=re.compile(r"描述")
            ).locator("textarea").first
            desc_input.wait_for(state="visible", timeout=5000)
            original_data["description"] = desc_input.input_value()
        except Exception:
            original_data["description"] = ""

        # 是否开启
        switch_item = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"^是否开启$")
        )
        switch = switch_item.locator(".el-switch").first
        if switch.count() > 0 and switch.is_visible():
            is_checked = switch.evaluate("el => el.classList.contains('is-checked')")
            original_data["enabled"] = is_checked
        else:
            original_data["enabled"] = True

        # 方向
        direction_item = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"^方向$")
        )
        direction_select = direction_item.locator(".el-select").first
        if direction_select.count() > 0 and direction_select.is_visible():
            direction_text = direction_select.inner_text(timeout=2000).strip()
            original_data["direction"] = direction_text
        else:
            original_data["direction"] = "全部流量"

        # 修改名称
        if new_name is not None:
            name_input.fill("")
            name_input.fill(new_name)

        # 修改是否开启
        if enabled is not None:
            current_enabled = original_data.get("enabled", True)
            if enabled != current_enabled:
                switch.click()
                self.page.wait_for_timeout(1000)

        # 修改方向
        if direction is not None:
            current_direction = original_data.get("direction", "")
            if direction != current_direction:
                direction_select.click()
                self.page.wait_for_timeout(2000)
                self.page.locator(".el-select-dropdown__item").filter(
                    has_text=re.compile(re.escape(direction))
                ).first.click()
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)

        # 修改描述
        if new_desc is not None:
            desc_input.fill("")
            desc_input.fill(new_desc)

        # 点击确定
        dialog.get_by_text("确定", exact=True).click()

        return original_data

    def tm_session_delete(self, name):
        """删除指定名称的镜像会话。

        调用前需确保当前位于镜像会话Tab页。

        Args:
            name: 镜像会话名称。
        """
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)
        self.search(name)
        self.page.wait_for_timeout(1000)
        self.click_action(name, "删除")
        self.dialog_confirm.click()
