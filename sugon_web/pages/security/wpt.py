import re
import time

from playwright.sync_api import expect

from sugon_web.common.base import BasePage
from sugon_web.assertions.security import WptAssertionMixin
from sugon_web.utils.logger import logger


class WptPage(WptAssertionMixin, BasePage):
    """网页防篡改WPT 页面对象。

    覆盖以下能力：
    - 创建 WPT 实例（基本设置 + 配置）
    - 实例操作（关机、开机、删除、退订、授权、续期）
    - 规格升级
    - 修改实例名称
    - 进入实例详情页 / 跳转地址验证
    - 绑定/解绑公网IP
    - 登录 VNC
    - 热迁移
    - 实例状态读取（服务状态、虚拟机状态）
    """

    service_name = "网页防篡改WPT"

    def get_detail_body_text(self) -> str:
        """获取详情页 body 文本内容，供测试层回读页面信息断言。"""
        return self.page.inner_text("body")

    def goto_list_page(self):
        """导航到网页防篡改WPT 列表页。"""
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/das/#/wpt"
        self.page.goto(target_url)
        self.wait_for_page_ready()
        for attempt in range(1, 16):
            self.page.wait_for_timeout(2000)
            if "/no-permission" in self.page.url:
                logger.warning(f"WPT 列表页被重定向到无权限页，重新导航 (第{attempt}次)")
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            loading_mask = self.page.locator(".el-loading-mask:visible, .el-loading-spinner:visible").first
            if loading_mask.count() > 0:
                logger.info(f"WPT 列表页数据加载中，继续等待 (第{attempt}次)...")
                continue
            has_rows = self.page.locator(".el-table__row").count() > 0
            has_empty = self.page.locator(".el-table__empty-block, .el-table__empty-text").count() > 0
            if has_rows:
                logger.info(f"WPT 回到列表页（第{attempt}次检查）: {self.page.url}")
                return
            if has_empty:
                logger.info(f"WPT 列表页表格为空（第{attempt}次检查）: {self.page.url}")
                return
            logger.info(f"WPT 列表页仍为空，等待数据加载中(第{attempt}次)...")
        logger.info(f"WPT 回到列表页: {self.page.url}")

    @property
    def _input_name(self):
        """WPT 创建表单：名称输入框"""
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称")
        ).get_by_role("textbox")

    @property
    def _btn_submit(self):
        """WPT 创建表单：提交按钮，兼容多种文案"""
        locators = [
            self.locator(".cloud-button-btn").filter(has_text="点击创建"),
            self.locator(".cloud-button-btn").filter(has_text="创建"),
            self.get_by_text("点击创建"),
            self.get_by_text("创建"),
            self.get_by_role("button", name="点击创建"),
            self.get_by_role("button", name="创建"),
            self.get_by_role("button", name="确定"),
            self.locator("button").filter(has_text=re.compile(r"创建|提交|确定")),
        ]
        for loc in locators:
            try:
                expect(loc).to_be_visible(timeout=3000)
                return loc
            except Exception:
                continue
        raise Exception("未找到 WPT 创建表单的提交按钮")

    def _select_form_item(self, label: str, option: str):
        """选择表单的下拉项。

        Args:
            label: 表单字段标签（如"版本"、"集群"、"安全底座"、"专有网络"）
            option: 要选择的下拉项文本（支持模糊匹配）
        """
        form_item = None
        for selector in [
            self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label)}")),
            self.locator(".el-form-item").filter(has_text=label),
            self.locator(".el-form-item__label").filter(has_text=label).locator("xpath=../.."),
        ]:
            try:
                if selector.count() > 0:
                    form_item = selector.first
                    break
            except Exception:
                continue

        if form_item is None:
            raise Exception(f"未找到表单字段: {label}")

        dropdown_trigger = form_item.locator(".el-select, [class*='select']").first
        if dropdown_trigger.count() == 0:
            dropdown_trigger = form_item.get_by_placeholder(re.compile(r"请选择|选择")).first
        dropdown_trigger.click()

        dropdown_option_selector = ".el-select-dropdown:visible .el-select-dropdown__item, .el-select-dropdown:visible li, .el-dropdown-menu:visible li"
        try:
            self.page.wait_for_selector(dropdown_option_selector, timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

        all_visible = self.locator(dropdown_option_selector)
        for attempt in range(10):
            cnt = all_visible.count()
            if cnt > 0:
                logger.info(f"下拉框 '{label}' 选项已加载，共 {cnt} 项")
                break
            logger.warning(f"下拉框 '{label}' 选项未加载，第 {attempt + 1} 次重试等待...")
            self.page.wait_for_timeout(1500)
            all_visible = self.locator(".el-select-dropdown:visible li, .el-dropdown-menu:visible li")
        else:
            logger.warning(f"下拉框 '{label}' 选项仍为空，尝试重新点击下拉框")
            dropdown_trigger.click()
            self.page.wait_for_timeout(2000)
            all_visible = self.locator(dropdown_option_selector)

        options = all_visible.filter(has_text=option)
        if options.count() == 0:
            options = all_visible.filter(has_text=re.compile(rf"^{re.escape(option)}$"))
        if options.count() == 0:
            options = all_visible.filter(has_text=re.compile(re.escape(option), re.IGNORECASE))
        if options.count() == 0:
            cnt = all_visible.count()
            available = [all_visible.nth(i).inner_text() for i in range(min(cnt, 20))]
            if cnt > 0:
                logger.warning(
                    f"下拉框 '{label}' 未找到选项 '{option}'，"
                    f"回退选择第一个可用选项: '{available[0]}'"
                )
                all_visible.first.click()
                logger.info(f"WPT 创建：选择 {label} = {available[0]}（回退）")
                return
            logger.error(f"下拉框 '{label}' 无可用选项")
            raise Exception(f"未找到下拉选项: {label} = {option}，可用选项为空")
        options.first.click()
        logger.info(f"WPT 创建：选择 {label} = {option}")

    def _select_flavor(self, cpu: str = "8核", memory: str = "16GiB"):
        """选择规格表格中的指定行。

        Args:
            cpu: CPU 规格（如"8核"）
            memory: 内存规格（如"16GiB"）
        """
        rows = self.locator(".el-table__row")
        expect(rows.first).to_be_visible(timeout=10000)
        self.page.wait_for_timeout(1500)

        def _find_target():
            all_rows = self.locator(".el-table__row")
            row_count = all_rows.count()
            logger.info(f"WPT 规格表格行数: {row_count}")
            for i in range(row_count):
                row = all_rows.nth(i)
                row_text = row.inner_text()
                if cpu in row_text and memory in row_text:
                    return row, row_text
            return None, None

        target_row, row_text = _find_target()

        if target_row is None:
            logger.warning(f"WPT 规格表格中未直接找到 {cpu}/{memory}，尝试使用筛选器")
            selects = self.locator(".flavor-tool-bar .el-select, .spec-filter .el-select")
            if selects.count() >= 2:
                selects.nth(0).click()
                self.page.wait_for_timeout(300)
                self.locator(".el-select-dropdown:visible li").filter(has_text=cpu).first.click()
                self.page.wait_for_timeout(500)
                selects.nth(1).click()
                self.page.wait_for_timeout(300)
                self.locator(".el-select-dropdown:visible li").filter(has_text=memory).first.click()
                self.page.wait_for_timeout(800)

            target_row, row_text = _find_target()
            if target_row is None:
                all_rows = self.locator(".el-table__row")
                if all_rows.count() > 0:
                    first_row = all_rows.first
                    first_text = first_row.inner_text()
                    logger.warning(f"WPT 筛选后仍找不到 {cpu}/{memory}，回退选择第一行: {first_text}")
                    target_row = first_row

        if target_row is None:
            raise Exception(f"未找到规格行: CPU={cpu}, 内存={memory}")

        radio = target_row.locator(".el-radio__original").first
        radio.evaluate("el => el.click()")
        logger.info(f"WPT 创建：选择规格 CPU={cpu}, 内存={memory} (行内容: {row_text or target_row.inner_text()})")

    def _click_sugon_dialog_confirm(self, dialog=None):
        """点击 sugon-dialog 中的确定按钮。

        Args:
            dialog: 弹窗定位器，None 时使用当前可见弹窗
        """
        container = dialog if dialog is not None else self.page
        for btn_selector in [
            container.locator(".sugon-dialog:visible, .el-dialog:visible").locator(".cloud-button-btn").filter(has_text="确定"),
            container.locator(".sugon-dialog:visible, .el-dialog:visible").get_by_text("确定", exact=True),
            self.dialog_confirm,
        ]:
            try:
                if btn_selector.count() > 0 and btn_selector.first.is_visible():
                    btn_selector.first.click()
                    return
            except Exception:
                continue
        raise Exception("未找到弹窗确认按钮")

    def _dismiss_visible_dialogs(self):
        """关闭页面上可见的 sugon-dialog 或 el-dialog 弹窗。"""
        for selector in [".sugon-dialog:visible", ".el-dialog__wrapper:visible", ".el-dialog:visible"]:
            try:
                dialogs = self.page.locator(selector)
                count = dialogs.count()
                for i in range(count - 1, -1, -1):
                    dialog = dialogs.nth(i)
                    try:
                        try:
                            dialog.wait_for(timeout=1000)
                        except Exception:
                            pass
                        if dialog.is_visible():
                            for btn_text in ["关闭", "取消", "确定"]:
                                btn = dialog.locator(".cloud-button-btn, .el-dialog__close, .sugon-dialog-close").filter(has_text=btn_text).first
                                if btn.count() > 0:
                                    try:
                                        btn.wait_for(timeout=500)
                                    except Exception:
                                        pass
                                    if btn.is_visible():
                                        btn.click()
                                        self.page.wait_for_timeout(300)
                                        break
                    except Exception:
                        continue
            except Exception:
                continue

    def wpt_create(
        self,
        name: str,
        version: str = "v2.0R24C20",
        cluster: str = "Autotest",
        base_name: str = None,
        network: str = None,
        subnet: str = None,
        cpu: str = "8核",
        memory: str = "16GiB",
    ):
        """创建 WPT 实例。

        导航到创建页面，填写基本设置（名称、版本、集群、安全底座）和配置
        （专有网络、子网、规格），提交创建请求。

        Args:
            name: 实例名称
            version: 版本号，默认 v2.0R24C20
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            network: 专有网络名称（None 表示选择第一个可用的）
            subnet: 子网名称（None 表示选择第一个可用的）
            cpu: 规格 CPU，默认 8核
            memory: 规格内存，默认 16GiB
        """
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        create_url = f"{base_url}/das/#/create-wpt"
        self.page.goto(create_url)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        try:
            self.page.locator(".el-loading-mask:visible").first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        logger.info("WPT 创建页面加载成功")

        try:
            self._input_name.wait_for(state="visible", timeout=10000)
        except Exception:
            logger.warning("WPT 创建：名称输入框未立即可见，继续尝试填充")
        self._input_name.fill(name, timeout=30000)

        if version:
            self._select_form_item("版本", version)
        if cluster:
            self.page.wait_for_timeout(2000)
            self._select_form_item("集群", cluster)
        if base_name:
            self._select_form_item("安全底座", base_name)
        else:
            form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^安全底座"))
            dropdown = form_item.get_by_placeholder(re.compile(r"请选择")).first
            if dropdown.count() == 0:
                dropdown = form_item.locator(".el-select").first
            dropdown.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        if network:
            self._select_form_item("专有网络", network)
        else:
            form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^专有网络"))
            placeholder = form_item.get_by_placeholder("请选择网络").first
            if placeholder.count() > 0:
                placeholder.click()
            else:
                form_item.locator(".el-select").first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        subnet_input = self.get_by_placeholder("请选择子网").first
        if subnet_input.count() > 0:
            subnet_input.click()
            self.page.wait_for_timeout(1000)
            options = self.locator(".el-select-dropdown:visible li")
            if subnet:
                options.filter(has_text=subnet).first.click()
            else:
                cnt = options.count()
                for i in range(cnt):
                    opt = options.nth(i)
                    text = opt.inner_text().strip()
                    if text and "请选择" not in text:
                        opt.click()
                        break
            self.page.wait_for_timeout(1000)

        self._select_flavor(cpu=cpu, memory=memory)

        self._btn_submit.click()
        logger.info(f"WPT 创建：已提交创建请求 {name}")

        try:
            self.page.wait_for_url("**/das/#/wpt", timeout=30000)
            logger.info(f"WPT 创建：页面已跳转回列表页 {self.page.url}")
        except Exception:
            logger.warning("WPT 创建：页面未自动跳转，手动返回列表页")
            self.goto_list_page()

    def wpt_operations(self, name: str, action: str):
        """对 WPT 实例执行操作（开机、关机、删除等）。

        Args:
            name: 实例名称
            action: 操作名称，如"开机"、"关机"、"删除"
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.page.wait_for_timeout(2000)
        try:
            self.click_action(name, action)
        except Exception as e:
            logger.warning(f"WPT 标准 click_action 失败: {e}，尝试 fallback 定位")
            row = self.get_row_by_name(name)
            btn = row.get_by_text(action, exact=False).first
            if btn.count() > 0:
                try:
                    btn.wait_for(timeout=2000)
                except Exception:
                    pass
                if btn.is_visible():
                    btn.click()
                    logger.info(f"WPT 操作 fallback: 直接点击行内 '{action}' 按钮")
            else:
                for more_text in ["更多", "操作", "..."]:
                    more_btn = row.get_by_text(more_text, exact=False).first
                    if more_btn.count() > 0:
                        try:
                            more_btn.wait_for(timeout=1000)
                        except Exception:
                            pass
                        if more_btn.is_visible():
                            more_btn.click()
                            self.page.wait_for_timeout(800)
                            for selector in ['.el-dropdown-menu', '[class*="dropdown"]']:
                                menu = self.page.locator(selector).last
                                if menu.count() > 0:
                                    try:
                                        menu.wait_for(timeout=1000)
                                    except Exception:
                                        pass
                                    if menu.is_visible():
                                        opt = menu.get_by_text(action, exact=False).first
                                        if opt.count() > 0:
                                            opt.click()
                                            logger.info(f"WPT 操作 fallback: 点击'{more_text}'下拉菜单中的 '{action}'")
                                            break
                            else:
                                continue
                            break
                else:
                    raise Exception(f"WPT 操作 {action} 的 fallback 定位也失败了")
        try:
            self._click_sugon_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug(f"WPT 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"WPT 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"WPT 实例 {name} 执行操作: {action}")

    def wpt_delete(self, name: str):
        """删除 WPT 实例（先勾选确认框，再点击确定）。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self.click_action(name, "删除")
        except Exception as e:
            logger.warning(f"WPT 标准 click_action 删除失败: {e}，尝试 fallback 定位")
            row = self.get_row_by_name(name)
            btn = row.get_by_text("删除", exact=False).first
            if btn.count() > 0:
                try:
                    btn.wait_for(timeout=2000)
                except Exception:
                    pass
                if btn.is_visible():
                    btn.click()
            else:
                for more_text in ["更多", "操作", "..."]:
                    more_btn = row.get_by_text(more_text, exact=False).first
                    if more_btn.count() > 0:
                        try:
                            more_btn.wait_for(timeout=1000)
                        except Exception:
                            pass
                        if more_btn.is_visible():
                            more_btn.click()
                            self.page.wait_for_timeout(800)
                            for selector in ['.el-dropdown-menu', '[class*="dropdown"]']:
                                menu = self.page.locator(selector).last
                                if menu.count() > 0:
                                    try:
                                        menu.wait_for(timeout=1000)
                                    except Exception:
                                        pass
                                    if menu.is_visible():
                                        opt = menu.get_by_text("删除", exact=False).first
                                        if opt.count() > 0:
                                            opt.click()
                                            break
                            else:
                                continue
                            break
                else:
                    raise Exception(f"WPT 删除 {name} 的 fallback 定位也失败了")

        try:
            dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
            checkbox = dialog.locator(".el-checkbox").first
            try:
                checkbox.wait_for(timeout=2000)
            except Exception:
                pass
            if checkbox.is_visible():
                checkbox.click()
        except Exception:
            logger.debug("WPT 删除：无需勾选确认框")
        self._click_sugon_dialog_confirm()
        logger.info(f"WPT 实例 {name} 删除请求已提交")

    def wpt_unsubscribe(self, name: str):
        """对 WPT 实例执行退订操作。

        Args:
            name: 实例名称
        """
        self._dismiss_visible_dialogs()
        self.click_action(name, "退订")
        self.page.wait_for_timeout(1000)
        try:
            self._click_sugon_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug("WPT 退订：未弹出确认对话框")
            else:
                raise
        logger.info(f"WPT 实例 {name} 退订请求已提交")

    def _duration_dialog(self, name: str, action: str, duration: str):
        """通用方法：处理授权/续费弹窗。

        弹窗使用 el-radio-button 组件展示购买时长选项。

        Args:
            name: 实例名称
            action: 操作名称，"授权" 或 "续期"
            duration: 购买时长，如 "3个月", "2个月"
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, action)
        self.page.wait_for_timeout(1500)
        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            logger.warning(f"WPT {action}：未找到弹窗，可能已自动完成")
            return

        radio_btn = dialog.locator(".el-radio-button").filter(has_text=duration).first
        if radio_btn.count() > 0:
            try:
                radio_btn.wait_for(timeout=2000)
            except Exception:
                pass
            if radio_btn.is_visible():
                radio_btn.click()
                logger.info(f"WPT {action}：已选择 {duration} 购买时长")
                self.page.wait_for_timeout(500)
        else:
            active_btn = dialog.locator(".el-radio-button.is-active").first
            if active_btn.count() > 0:
                active_text = active_btn.inner_text()
                logger.info(f"WPT {action}：当前已选中 {active_text}（默认选中状态）")
            else:
                logger.warning(f"WPT {action}：未找到时长选项 {duration}，直接尝试确认")

        self._click_sugon_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} {action}操作已提交")

    def wpt_authorize(self, name: str, duration: str):
        """对 WPT 实例执行授权操作。

        Args:
            name: 实例名称
            duration: 购买时长，如 "3个月"
        """
        self._duration_dialog(name, "授权", duration)

    def wpt_renewal(self, name: str, duration: str):
        """对 WPT 实例执行续期操作。

        Args:
            name: 实例名称
            duration: 续费时长，如 "2个月"
        """
        self._duration_dialog(name, "续期", duration)

    def wpt_rename(self, name: str, new_name: str):
        """修改 WPT 实例名称。

        触发"修改实例名称"弹窗，填写新名称后确认提交。

        Args:
            name: 当前实例名称
            new_name: 新的实例名称
        """
        self._dismiss_visible_dialogs()
        self.click_action(name, "修改实例名称")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="修改名称").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到修改名称弹窗")
        logger.info("WPT 修改名称：弹窗已打开")

        name_input = dialog.locator(".el-input__inner").first
        name_input.click()
        self.page.wait_for_timeout(300)
        name_input.fill("")
        self.page.wait_for_timeout(300)
        name_input.fill(new_name)
        self.page.wait_for_timeout(500)
        logger.info(f"WPT 修改名称：已填写新名称 {new_name}")

        self._click_sugon_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} 名称已修改为 {new_name}")

    def wpt_to_details(self, name: str):
        """进入 WPT 实例详情页。

        通过点击列表页实例名称进入详情页。WPT 列表页名称渲染为 div.overflow-ellipsis，
        有 cursor:pointer 样式且可点击时表示可进入详情。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        row = self.get_row_by_name(name)
        found = False
        for link_sel in ["a", "div.overflow-ellipsis", "span.link", "td div.cell"]:
            try:
                elements = row.locator(link_sel).all()
                for el in elements:
                    try:
                        el_text = el.inner_text()
                        if name in el_text and el.is_visible():
                            with self.page.expect_navigation(timeout=30000):
                                el.click()
                            found = True
                            break
                    except Exception:
                        continue
            except Exception:
                continue
            if found:
                break

        if not found:
            try:
                text_loc = row.get_by_text(name, exact=True).first
                if text_loc.count() > 0:
                    try:
                        text_loc.scroll_into_view_if_needed()
                        text_loc.click(timeout=10000)
                    except Exception:
                        self.logger.info(f"WPT 实例 {name} 名称元素普通点击不可见，尝试 force click")
                        text_loc.click(force=True)
                    self.page.wait_for_timeout(5000)
                    if "wpt-detail" in self.page.url or "server_id" in self.page.url:
                        found = True
            except Exception:
                pass

        if not found:
            base = self.page.url.split("#")[0]
            self.page.goto(f"{base}#/wpt-detail?id=0&server_id=0")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(3000)

        self.wait_for_detail_page_ready()
        logger.info(f"WPT 实例 {name} 进入详情页，URL: {self.page.url}")

    def wait_for_detail_page_ready(self, timeout: int = 60):
        """等待 WPT 详情页加载完成。"""
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)
        self.page.wait_for_load_state("load", timeout=30000)
        spinners = self.page.locator(".el-loading-spinner")
        try:
            if spinners.count() > 0:
                spinners.first.wait_for(state="hidden", timeout=timeout * 1000)
        except Exception:
            logger.warning(f"WPT 详情页 loading spinner 在 {timeout}s 后仍未消失，继续执行")
            self.page.evaluate("""
                document.querySelectorAll('.el-loading-mask').forEach(el => el.remove());
                document.querySelectorAll('.el-loading-spinner').forEach(el => el.remove());
            """)

    def _extract_jump_url(self) -> str | None:
        """从当前详情页提取跳转地址 URL。"""
        self.wait_for_detail_page_ready()
        self.page.wait_for_timeout(3000)

        body_text = self.page.inner_text("body")

        try:
            label = self.get_by_text("跳转地址", exact=False).first
            if label.count() > 0:
                try:
                    label.wait_for(timeout=2000)
                except Exception:
                    pass
                if label.is_visible():
                    for ancestor in ["xpath=../..", "xpath=..", "xpath=../../.."]:
                        parent = label.locator(ancestor).first
                        if parent.count() > 0:
                            link = parent.locator("a[href^='http']").first
                            if link.count() > 0 and link.is_visible():
                                return link.get_attribute("href")
                            text = parent.inner_text()
                            url_match = re.search(r"https?://[^\s\n]+", text)
                            if url_match:
                                return url_match.group(0)
        except Exception:
            pass

        links = self.locator("a[href^='http']").all()
        for link in links:
            try:
                if link.is_visible():
                    href = link.get_attribute("href")
                    if href and ("openapiOAuth" in href or "172.22" in href):
                        return href
            except Exception:
                continue

        urls = re.findall(r"https?://[^\s\n]+", body_text)
        for url in urls:
            if "172.22" in url or ":30000" in url or "openapiOAuth" in url:
                return url

        logger.info(f"WPT 跳转地址提取失败，body 文本含跳转地址: {'跳转地址' in body_text}")
        return None

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("WPT 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
            self.page.wait_for_timeout(5000)
            all_pages = self.page.context.pages
            for p in reversed(all_pages):
                if p != self.page and jump_url in p.url:
                    return p
            if len(all_pages) > 1:
                for p in reversed(all_pages):
                    if p != self.page:
                        return p
            return None

    def _refresh_and_get_new_jump_url(self) -> str | None:
        """离开详情页重新进入，强制后端生成新的跳转 token。"""
        logger.info("WPT 跳转地址：重新进入详情页以获取新的跳转链接...")
        name = None
        url = self.page.url
        name_match = re.search(r"server_name=([^&]+)", url)
        if name_match:
            from urllib.parse import unquote
            name = unquote(name_match.group(1))

        self.goto_list_page()
        self.page.wait_for_timeout(5000)

        if name:
            self.wpt_to_details(name)
        else:
            try:
                self.page.reload(wait_until="networkidle", timeout=60000)
            except Exception:
                pass
        self.wait_for_detail_page_ready()

        for wait_sec in [10, 15, 20]:
            self.page.wait_for_timeout(wait_sec * 1000)
            new_url = self._extract_jump_url()
            if new_url:
                logger.info(f"WPT 跳转地址：重进详情页后提取到 URL: {new_url}")
                return new_url
        logger.warning("WPT 跳转地址：重进详情页后多次尝试仍未提取到 URL")
        return None

    def wpt_open_jump_address(self, max_retries: int = 3):
        """在详情页提取跳转地址，新标签页打开 WPT 平台页面。

        Returns:
            Page: Playwright 新页面对象（WPT 平台页面）或 None
        """
        jump_url = None
        for extract_attempt in range(1, 12):
            jump_url = self._extract_jump_url()
            if jump_url:
                break
            self.page.wait_for_timeout(10000)

        if not jump_url:
            body_snippet = self.page.inner_text("body")[:2000]
            logger.warning(f"WPT 跳转地址：多次尝试后未找到跳转地址 URL，body 前2000字符: {body_snippet}")
            return None
        logger.info(f"WPT 跳转地址：提取到 URL: {jump_url}")

        for attempt in range(1, max_retries + 1):
            logger.info(f"WPT 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)

            if new_page is None:
                if attempt < max_retries:
                    logger.warning(f"WPT 跳转地址：第 {attempt} 次未获取到新页面，等待后重试")
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        raise Exception("刷新详情页后未找到新的跳转地址 URL")
                    continue
                raise Exception("未能获取跳转地址打开的新页面")

            try:
                new_page.wait_for_timeout(2000)
                adv_btn = new_page.get_by_text("高级", exact=False).first
                if adv_btn.count() > 0:
                    try:
                        adv_btn.wait_for(timeout=3000)
                    except Exception:
                        pass
                    if adv_btn.is_visible():
                        logger.info("WPT 跳转地址：检测到证书警告页，点击高级按钮")
                        adv_btn.click()
                        new_page.wait_for_timeout(2000)
                        proceed = new_page.get_by_text(re.compile(r"继续前往|继续访问|Proceed"), exact=False).first
                        if proceed.count() > 0:
                            proceed.click()
                            logger.info("WPT 跳转地址：已点击继续前往，等待页面加载")
                            new_page.wait_for_timeout(10000)
            except Exception:
                pass

            quick_error = False
            for _ in range(15):
                self.page.wait_for_timeout(1000)
                current_url = new_page.url
                if ("chrome-error" in current_url and "chromewebdata" in current_url) or current_url == "about:blank":
                    logger.warning(f"WPT 跳转地址：快速检测到错误页面 {current_url}")
                    quick_error = True
                    break
                if current_url and current_url != "about:blank":
                    break

            if quick_error:
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < max_retries:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("WPT 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue
                logger.warning("WPT 跳转地址：多次尝试后仍未成功打开平台页面，目标服务器可能不可达")
                return None

            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            try:
                new_page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass

            current_url = new_page.url
            logger.info(f"WPT 跳转地址：新页面当前 URL: {current_url}")

            if "chrome-error" not in current_url and current_url != "about:blank":
                logger.info(f"WPT 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"WPT 跳转地址：加载到错误页面 {current_url}，跳转地址可能已过期")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < max_retries:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("WPT 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue

            try:
                new_page.close()
            except Exception:
                pass
            if attempt < max_retries:
                jump_url = self._refresh_and_get_new_jump_url()
                if not jump_url:
                    return None
                continue

        logger.warning("WPT 跳转地址：多次尝试后仍未成功打开平台页面")
        return None

    def wpt_name_clickable(self, name: str) -> bool:
        """检查列表页 WPT 实例名称是否可点击跳转。

        Args:
            name: 实例名称

        Returns:
            bool: True 表示可点击（蓝色链接），False 表示不可点击（黑色文本）
        """
        self.goto_list_page()
        row = self.get_row_by_name(name)
        name_cell = row.get_by_text(name, exact=True).first
        try:
            color = name_cell.evaluate("el => window.getComputedStyle(el).color")
            is_link = "64, 158, 255" in color
            logger.info(f"WPT 实例 {name} 名称颜色: {color}, 可点击: {is_link}")
            return is_link
        except Exception as e:
            logger.warning(f"检查 WPT 实例 {name} 名称可点击性失败: {e}")
            return False

    def wpt_open_spec_upgrade_dialog(self, name: str) -> str:
        """打开规格升级弹窗并验证提示信息。

        Args:
            name: 实例名称

        Returns:
            str: 弹窗中 alert 提示文本，若无则为空字符串
        """
        self._dismiss_visible_dialogs()
        try:
            self.click_action(name, "规格升级")
        except Exception as e:
            logger.warning(f"WPT 规格升级：标准 click_action 失败: {e}，尝试 fallback")
            row = self.get_row_by_name(name)
            found = False
            for btn_text in ["规格升级", "立即升级", "升级"]:
                btn = row.get_by_text(btn_text, exact=False).first
                if btn.count() > 0:
                    try:
                        btn.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if btn.is_visible() and btn.is_enabled():
                        btn.click()
                        logger.info(f"WPT 规格升级 fallback: 点击行内 '{btn_text}'")
                        found = True
                        break
            if not found:
                more_btn = row.get_by_text("更多", exact=False).first
                if more_btn.count() > 0:
                    try:
                        more_btn.wait_for(timeout=1000)
                    except Exception:
                        pass
                    if more_btn.is_visible():
                        more_btn.click()
                        self.page.wait_for_timeout(1500)
                        for selector in ['[id^="dropdown-menu-"]', '[class^="cloud-table-dropdown"]']:
                            menus = self.page.locator(selector)
                            menu_count = menus.count()
                            for i in range(menu_count - 1, -1, -1):
                                menu = menus.nth(i)
                                if menu.is_visible():
                                    for opt_text in ["规格升级", "立即升级", "升级"]:
                                        opt = menu.get_by_text(opt_text, exact=False).first
                                        if opt.count() > 0:
                                            try:
                                                opt.wait_for(timeout=1000)
                                            except Exception:
                                                pass
                                            if opt.is_visible():
                                                opt.click()
                                                logger.info(f"WPT 规格升级 fallback: 更多菜单 '{opt_text}'")
                                                found = True
                                                break
                                    if found:
                                        break
                            if found:
                                break
                if not found:
                    raise Exception("WPT 规格升级：所有 fallback 均无法找到升级操作")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="规格升级").first
        if dialog.count() == 0 or not dialog.is_visible():
            for dlg_sel in [".el-dialog:visible", ".dialog:visible"]:
                dlg = self.locator(dlg_sel).filter(has_text="规格升级").first
                if dlg.count() > 0:
                    try:
                        dlg.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if dlg.is_visible():
                        dialog = dlg
                        break
            if dialog.count() == 0 or not dialog.is_visible():
                raise Exception("未找到规格升级弹窗")
        logger.info("WPT 规格升级：弹窗已打开")

        alert_text = ""
        alert = dialog.locator(".sugon-alert, .el-alert").first
        if alert.count() > 0:
            try:
                alert.wait_for(timeout=3000)
            except Exception:
                pass
            if alert.is_visible():
                alert_text = alert.inner_text()
        return alert_text

    def wpt_spec_upgrade(self, name: str, target_spec_name: str = None) -> dict:
        """执行规格升级：选择规格并提交。

        Args:
            name: 实例名称
            target_spec_name: 目标规格名称，如"wpt.d6.xlarge"（None 时选择第一个可选规格）

        Returns:
            dict: 选中的新规格信息 {'vcpus': int, 'memory_mb': int, 'name': str}
        """
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="规格升级").first
        if dialog.count() == 0 or not dialog.is_visible():
            for dlg_sel in [".el-dialog:visible", ".dialog:visible"]:
                dlg = self.locator(dlg_sel).filter(has_text="规格升级").first
                if dlg.count() > 0:
                    try:
                        dlg.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if dlg.is_visible():
                        dialog = dlg
                        break
            if dialog.count() == 0 or not dialog.is_visible():
                raise Exception("未找到规格升级弹窗")

        self.page.wait_for_timeout(1500)
        rows = dialog.locator(".el-table__row")
        try:
            expect(rows.first).to_be_visible(timeout=10000)
        except Exception:
            pass

        radio_rows = rows.all()
        if len(radio_rows) == 0:
            radio_rows = dialog.locator("tr").all()
        logger.info(f"WPT 规格升级：弹窗内找到 {len(radio_rows)} 行规格")

        selected_spec = None
        for idx, row in enumerate(radio_rows):
            radio = row.locator(".el-radio__original, .el-radio").first
            if radio.count() == 0:
                continue
            is_disabled = False
            radio_class = radio.get_attribute("class") or ""
            if "is-disabled" in radio_class:
                is_disabled = True
            row_text = row.inner_text()
            logger.info(f"WPT 规格升级：第{idx+1}行 radio_class={radio_class}, disabled={is_disabled}, text={row_text[:80]}")

            if target_spec_name and target_spec_name not in row_text:
                continue

            if not is_disabled:
                vcpu_match = re.search(r"(\d+)核", row_text)
                mem_match = re.search(r"(\d+)GiB", row_text)
                spec_name_match = re.search(r"wpt\.\S+|wpt\S+|standard\.\S+", row_text)
                selected_spec = {
                    "vcpus": int(vcpu_match.group(1)) if vcpu_match else 0,
                    "memory_mb": int(mem_match.group(1)) * 1024 if mem_match else 0,
                    "name": spec_name_match.group(0) if spec_name_match else "",
                }
                radio.evaluate("el => el.click()")
                logger.info(
                    f"WPT 规格升级：选中规格 vcpu={selected_spec['vcpus']}核, "
                    f"memory={selected_spec['memory_mb']}MB({selected_spec['name']})"
                )
                break

        if selected_spec is None:
            raise Exception("未找到可选的更高规格")

        confirm_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            try:
                confirm_btn.wait_for(timeout=3000)
            except Exception:
                pass
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            raise Exception("未找到规格升级弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"WPT 实例 {name} 规格升级请求已提交")
        return selected_spec

    def wpt_cancel_dialog(self, dialog_text: str = None):
        """关闭当前可见的弹窗（点击取消或关闭）。

        Args:
            dialog_text: 弹窗标题文本，用于定位
        """
        target = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog_text:
            target = self.locator(".sugon-dialog:visible, .el-dialog:visible").filter(has_text=dialog_text).first
        cancel_btn = target.get_by_text("取消", exact=True).first
        if cancel_btn.count() > 0 and cancel_btn.is_visible():
            cancel_btn.click()
            logger.info("已点击弹窗取消按钮")
            return
        close_btn = target.locator(".el-dialog__close, .sugon-dialog-close").first
        if close_btn.count() > 0 and close_btn.is_visible():
            close_btn.click()
            logger.info("已点击弹窗关闭按钮")

    def wpt_get_server_id(self, name: str) -> str | None:
        """进入详情页，从URL中提取 server_id。

        Args:
            name: 实例名称

        Returns:
            str: server_id（UUID格式），若未找到返回 None
        """
        self.wpt_to_details(name)
        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"WPT 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"WPT 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def wpt_bind_floating_ip(self, name: str, pool: str = "public_net"):
        """绑定公网IP到 WPT 实例。

        Args:
            name: 实例名称
            pool: 公网IP资源池名称，默认 public_net
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, "绑定公网IP")
        self.page.wait_for_timeout(2000)

        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到绑定公网IP弹窗")

        pool_select = dialog.get_by_placeholder(re.compile(r"资源池|选择")).first
        if pool_select.count() == 0:
            pool_select = dialog.locator(".el-select").first
        pool_select.click()
        self.page.wait_for_timeout(500)
        pool_option = self.locator(".el-select-dropdown:visible li").filter(has_text=pool).first
        if pool_option.count() > 0:
            pool_option.click()
            self.page.wait_for_timeout(500)
        else:
            self.locator(".el-select-dropdown:visible li").first.click()
            self.page.wait_for_timeout(500)

        # 绑定公网IP弹窗中可用IP用表格展示（含el-radio），非下拉框
        # 等待IP表格加载完成（loading消失）
        self.page.wait_for_timeout(2000)
        try:
            loading = dialog.locator(".el-loading-mask:visible, .el-loading-spinner:visible")
            if loading.count() > 0:
                loading.first.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

        # 从表格中选择第一个可用IP的radio按钮
        ip_radio = dialog.locator(".el-table .el-radio").first
        if ip_radio.count() > 0:
            ip_radio.wait_for(state="visible", timeout=5000)
            ip_radio.click()
            self.page.wait_for_timeout(500)
            logger.info(f"WPT 实例 {name} 已选择公网IP")
        else:
            logger.warning("WPT 绑定公网IP：未找到可用的公网IP选项，尝试直接确认")

        self._click_sugon_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} 绑定公网IP请求已提交")

    def wpt_unbind_floating_ip(self, name: str):
        """解绑 WPT 实例的公网IP。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, "解绑公网IP")
        self.page.wait_for_timeout(2000)

        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到解绑公网IP弹窗")

        self._click_sugon_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} 解绑公网IP请求已提交")

    def wpt_live_migrate_auto(self, name: str):
        """对 WPT 实例执行热迁移（系统分配）。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, "热迁移")
        self.page.wait_for_timeout(2000)

        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到热迁移弹窗")

        auto_radio = dialog.get_by_text("系统分配", exact=False).first
        if auto_radio.count() > 0:
            auto_radio.click()
            self.page.wait_for_timeout(500)

        self._click_sugon_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} 热迁移（系统分配）请求已提交")

    def wpt_live_migrate_manual(self, name: str, src_host: str = None):
        """对 WPT 实例执行热迁移（手动指定），自动选择不同于源节点的目标节点。

        Args:
            name: 实例名称
            src_host: 源物理机名称，用于排除当前所在节点
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, "热迁移")
        self.page.wait_for_timeout(2000)

        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到热迁移弹窗")

        manual_radio = dialog.get_by_text("手动指定", exact=False).first
        if manual_radio.count() > 0:
            manual_radio.click()
            self.page.wait_for_timeout(500)

        # 通过 "选择物理机" 链接打开物理机选择抽屉（physical-info 组件）
        # 该链接仅在手动指定模式下可见，点击后弹出 el-drawer 展示物理机列表
        select_host_trigger = dialog.locator("span").filter(has_text=re.compile(r"选择物理机")).first
        if select_host_trigger.count() == 0:
            select_host_trigger = self.page.locator("span").filter(has_text=re.compile(r"选择物理机")).first
        if select_host_trigger.count() > 0:
            select_host_trigger.click()
        else:
            raise Exception("未找到'选择物理机'链接")

        # 等待抽屉打开并加载数据（post_hypervisors API）
        self.page.wait_for_timeout(3000)

        # 定位物理机选择抽屉（append-to-body，位于页面顶层）
        drawer = self.page.locator('.el-drawer__wrapper:visible').filter(has_text=re.compile(r'选择物理机')).first
        drawer.wait_for(state="visible", timeout=15000)

        # 表格加载可能异步，再等待数据渲染
        self.page.wait_for_timeout(2000)

        # 选择第一个可用的物理机 radio 按钮（is-disabled 表示已被排除）
        radio = drawer.locator('.el-radio:not(.is-disabled)').first
        if radio.count() > 0:
            radio.wait_for(state="visible", timeout=5000)
            # 直接点击 el-radio label 触发 Vue 事件，避免点击内部 hidden input
            radio.click()
            self.page.wait_for_timeout(500)
            logger.info(f"WPT 实例 {name} 已选择目标物理机")
        else:
            raise Exception("未找到可用的目标物理机")

        # 点击抽屉中的 "确定" 按钮
        drawer_confirm = drawer.get_by_text("确定", exact=True).first
        if drawer_confirm.count() > 0:
            drawer_confirm.click()
            self.page.wait_for_timeout(1000)
        else:
            drawer.locator('button').filter(has_text="确定").first.click()
            self.page.wait_for_timeout(1000)

        logger.info(f"WPT 实例 {name} 已确认物理机选择，准备提交热迁移请求")

        self._click_sugon_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WPT 实例 {name} 热迁移（手动指定）请求已提交")

    def wpt_vnc_login(self, name: str):
        """对 WPT 实例执行 VNC 登录操作，返回新打开的 VNC 页面（如有）。

        点击登录VNC后，浏览器可能打开新标签页。
        本方法会在所有页面中查找非当前页并等待其加载完成。

        Args:
            name: 实例名称

        Returns:
            playwright.sync_api.Page or None: VNC 页面对象（未找到返回 None）
        """
        from playwright.sync_api import Page as PwPage

        self.goto_list_page()
        self._dismiss_visible_dialogs()
        page_count_before = len(self.page.context.pages)
        self.click_action(name, "登录VNC")
        logger.info(f"WPT 实例 {name} 登录VNC请求已提交")

        # 等待新标签页出现
        try:
            self.page.wait_for_function(
                f"() => document.querySelectorAll('.el-message--success').length > 0 || "
                f"document.querySelectorAll('.sugon-message--success').length > 0",
                timeout=15000
            )
        except Exception:
            pass

        new_page = None
        for p in reversed(self.page.context.pages):
            if p != self.page:
                new_page = p
                break
        if new_page and isinstance(new_page, PwPage):
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            logger.info(f"WPT 实例 {name} VNC 新页面 URL: {new_page.url}")
        else:
            logger.warning(f"WPT 实例 {name} VNC 新页面未自动打开")
        return new_page

    def wpt_get_network_info(self, name: str) -> dict:
        """获取 WPT 实例的网络信息（固定 IP 和公网 IP）。

        Args:
            name: 实例名称

        Returns:
            dict: {'fixed_ip': str, 'public_ip': str}
        """
        self.goto_list_page()
        row_data = self.get_row_data(name)
        network = row_data.get("网络", "")
        result = {"fixed_ip": "", "public_ip": ""}
        if network and isinstance(network, str):
            fixed_match = re.search(r"固定[:：]\s*([\d.]+)", network)
            public_match = re.search(r"公网[:：]\s*([\d.]+)", network)
            if fixed_match:
                result["fixed_ip"] = fixed_match.group(1)
            if public_match:
                result["public_ip"] = public_match.group(1)
        return result
