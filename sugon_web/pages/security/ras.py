import re
import time
from playwright.sync_api import expect
from sugon_web.common.base import BasePage
from sugon_web.assertions.security import RasAssertionMixin
from sugon_web.utils.logger import logger


class RasPage(RasAssertionMixin, BasePage):
    """漏洞扫描RAS 页面对象。

    覆盖以下能力：
    - 创建 RAS 实例（基本设置 + 配置）
    - 实例操作（开机、关机、退订、授权、续期、规格升级）
    - 实例状态读取（服务状态、虚拟机状态）
    - 进入实例详情页 / 跳转地址验证
    - 绑定/解绑公网IP、修改名称、热迁移
    """

    service_name = "漏洞扫描"

    def get_detail_body_text(self) -> str:
        """获取详情页 body 文本内容，供测试层回读页面信息断言。"""
        return self.page.inner_text("body")

    def goto_list_page(self):
        """导航到 RAS 列表页。从详情页或跳转地址页回到列表时必须用此方法。"""
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/das/#/ras"
        self.page.goto(target_url)
        self.wait_for_page_ready()
        for attempt in range(1, 16):
            self.page.wait_for_timeout(2000)
            if "/no-permission" in self.page.url:
                logger.warning(f"RAS 列表页被重定向到无权限页，重新导航 (第{attempt}次)")
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            if "/login" in self.page.url:
                logger.warning(f"RAS 列表页被重定向到登录页，尝试重新登录 (第{attempt}次)")
                from sugon_web.common.auth import prepare_page_session
                from sugon_web.config.config import Config
                prepare_page_session(self.page, Config)
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            loading_mask = self.page.locator(".el-loading-mask:visible, .el-loading-spinner:visible").first
            if loading_mask.count() > 0:
                logger.info(f"RAS 列表页数据加载中，继续等待 (第{attempt}次)...")
                continue
            has_rows = self.page.locator(".el-table__row").count() > 0
            has_empty = self.page.locator(".el-table__empty-block, .el-table__empty-text").count() > 0
            if has_rows or has_empty:
                logger.info(f"RAS 回到列表页（第{attempt}次检查）: {self.page.url}")
                return
            logger.info(f"RAS 列表页仍为空，等待数据加载中(第{attempt}次)...")
            if attempt >= 3 and not has_rows and not has_empty:
                logger.warning(f"RAS 列表页数据未就绪，继续等待 (第{attempt}次)...")
        logger.info(f"RAS 回到列表页: {self.page.url}")

    @property
    def _input_name(self):
        """RAS 创建表单：名称输入框"""
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称")
        ).get_by_role("textbox")

    @property
    def _btn_submit(self):
        """RAS 创建表单：提交按钮（点击创建）"""
        locators = [
            self.locator(".cloud-button-btn").filter(has_text="点击创建"),
            self.get_by_text("点击创建"),
            self.get_by_role("button", name="点击创建"),
            self.get_by_role("button", name="创建"),
            self.get_by_role("button", name="提交"),
            self.get_by_role("button", name="确定"),
            self.locator("button").filter(has_text=re.compile(r"创建|提交|确定")),
        ]
        for loc in locators:
            try:
                expect(loc).to_be_visible(timeout=3000)
                return loc
            except Exception:
                continue
        raise Exception("未找到 RAS 创建表单的提交按钮")

    def _select_form_item_first(self, label: str):
        """选择表单下拉项的第一个可见选项。

        Args:
            label: 表单字段标签（如"安全底座"、"专有网络"）
        """
        form_item = self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label)}"))
        dropdown = form_item.locator(".el-select").first
        dropdown.click()
        for attempt in range(10):
            self.page.wait_for_timeout(800)
            options = self.locator(".el-select-dropdown:visible li")
            if options.count() > 0:
                logger.info(f"RAS 下拉框 '{label}' 选项已加载，共 {options.count()} 项")
                break
            logger.warning(f"RAS 下拉框 '{label}' 选项为空，第 {attempt + 1} 次重试等待...")
        else:
            dropdown.click()
            raise Exception(f"下拉选项为空: {label}")
        options.first.click()
        logger.info(f"RAS 创建：选择 {label} = 第一个可用选项")

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
        dropdown_option_selector = ".el-select-dropdown:visible li, .el-dropdown-menu:visible li"
        try:
            self.page.wait_for_selector(dropdown_option_selector, timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(1500)
        for attempt in range(10):
            all_visible = self.locator(dropdown_option_selector)
            cnt = all_visible.count()
            if cnt > 0:
                logger.info(f"RAS 下拉框 '{label}' 选项已加载，共 {cnt} 项")
                break
            logger.warning(f"RAS 下拉框 '{label}' 选项未加载，第 {attempt + 1} 次重试等待...")
            self.page.wait_for_timeout(1500)
            all_visible = self.locator(".el-select-dropdown:visible li, .el-dropdown-menu:visible li")
        else:
            logger.warning(f"RAS 下拉框 '{label}' 选项仍为空，尝试重新点击下拉框")
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
            logger.error(f"RAS 下拉框 '{label}' 可用选项: {available}")
            raise Exception(f"未找到下拉选项: {label} = {option}，可用选项: {available}")
        options.first.click()
        logger.info(f"RAS 创建：选择 {label} = {option}")

    def _select_flavor(self, cpu: str = "8核", memory: str = "16GiB"):
        """选择规格表格中的指定行。

        Args:
            cpu: CPU 规格（如"8核"）
            memory: 内存规格（如"16GiB"）
        """
        self.page.wait_for_timeout(1000)
        rows = self.locator(".el-table__row")
        expect(rows.first).to_be_visible(timeout=10000)

        row_count = rows.count()
        target_row = None
        for i in range(row_count):
            row = rows.nth(i)
            row_text = row.inner_text()
            if cpu in row_text and memory in row_text:
                target_row = row
                break

        if target_row is None:
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

            rows = self.locator(".el-table__row")
            if rows.count() > 0:
                target_row = rows.first

        if target_row is None:
            raise Exception(f"未找到规格行: CPU={cpu}, 内存={memory}")

        radio_input = target_row.locator(".el-radio__original").first
        radio_input.evaluate("el => el.click()")
        logger.info(f"RAS 创建：选择规格 CPU={cpu}, 内存={memory}")

    def ras_create(
        self,
        name: str,
        version: str = "v5.0R23C04",
        cluster: str = "Autotest",
        base_name: str = None,
        network: str = None,
        subnet: str = None,
        cpu: str = "8核",
        memory: str = "16GiB",
    ):
        """创建 RAS 实例。

        通过菜单导航进入列表页后点击"新建"按钮进入创建页面。

        Args:
            name: 实例名称
            version: 版本号，默认 v5.0R23C04
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            network: 专有网络名称（None 表示选择第一个可用的）
            subnet: 子网名称（None 表示选择第一个可用的）
            cpu: 规格 CPU，默认 8核
            memory: 规格内存，默认 16GiB
        """
        self.goto_list_page()
        btn = self.btn_create
        btn.click()
        self.page.wait_for_url(lambda url: "create-ras" in url, timeout=30000)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        try:
            self.page.locator(".el-loading-mask:visible").first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        logger.info("RAS 创建页面加载成功")

        # 重试等待并填充名称输入框（Vue 渲染可能存在延迟）
        name_filled = False
        for retry_n in range(3):
            try:
                self._input_name.wait_for(state="visible", timeout=20000)
                self._input_name.fill(name, timeout=15000)
                name_filled = True
                break
            except Exception as e:
                if retry_n < 2:
                    logger.warning(f"RAS 创建：名称输入框操作失败（第{retry_n+1}次），等待后重试: {e}")
                    self.page.wait_for_timeout(3000)
                    self.page.evaluate("window.scrollTo(0, 0)")
                    self.page.wait_for_timeout(1000)
                else:
                    raise Exception(f"RAS 创建失败: 名称输入框无法填充 - {e}")
        if not name_filled:
            raise Exception(f"RAS 创建失败: 名称输入框无法填充（重试耗尽）")

        if version:
            self._select_form_item("版本", version)
        if cluster:
            self.page.wait_for_timeout(2000)
            self._select_form_item("集群", cluster)
        if base_name:
            self._select_form_item("安全底座", base_name)
        else:
            self._select_form_item_first("安全底座")

        if network:
            self._select_form_item("专有网络", network)
        else:
            network_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^专有网络"))
            network_item.get_by_placeholder("请选择网络").first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        # 选择子网
        subnet_input = self.get_by_placeholder("请选择子网").first
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
        logger.info(f"RAS 创建：已提交创建请求 {name}")

        self.page.wait_for_timeout(3000)

        # 检查是否有错误 toast
        error_toast = self.page.locator(".el-message--error, .el-message.el-message--error").first
        try:
            try:
                error_toast.wait_for(timeout=3000)
            except Exception:
                pass
            if error_toast.is_visible():
                toast_text = error_toast.inner_text()
                logger.error(f"RAS 创建失败，检测到错误提示: {toast_text}")
                raise Exception(f"RAS 创建失败: {toast_text}")
        except Exception as e:
            if "RAS 创建失败" in str(e):
                raise
            logger.debug("RAS 创建：未检测到错误 toast")

        # 等待页面自动跳转回列表页
        try:
            self.page.wait_for_url(lambda url: "/ras" in url and "create-ras" not in url, timeout=10000)
            logger.info("RAS 创建：页面已自动跳转到列表页")
        except Exception:
            logger.warning("RAS 创建：页面未自动跳转，手动导航到列表页")
            base_url = self.page.url.split('#')[0].rstrip('/')
            if not base_url.endswith('/das'):
                base_url = f"{base_url}/das"
            self.page.goto(f"{base_url}/#/ras")

        self.wait_for_page_ready()
        logger.info("RAS 创建：已到达列表页")

    def _click_dialog_confirm(self):
        """点击当前可见弹窗的确认/确定按钮（兼容 el-dialog 和 sugon-dialog）。"""
        for btn_selector in [
            self.locator(".sugon-dialog:visible, .el-dialog:visible").locator(".cloud-button-btn").filter(has_text="确定"),
            self.locator(".sugon-dialog:visible, .el-dialog:visible").get_by_text("确定", exact=True),
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

    def _click_dropdown_action(self, name: str, action: str):
        """从下拉菜单中点击操作项。

        RAS 操作位于 cl-table-dropdown 组件中。

        Args:
            name: 实例名称
            action: 操作名称，如"关机"、"开机"、"退订"等
        """
        row = self.get_row_by_name(name)
        # 滚动行到可见区域
        try:
            row.evaluate("el => el.scrollIntoView({block: 'center'})")
            self.page.wait_for_timeout(500)
        except Exception:
            pass

        # 尝试直接定位操作按钮（若有平铺按钮）
        direct_btn = row.get_by_text(action, exact=False).first
        if direct_btn.count() > 0:
            try:
                direct_btn.wait_for(timeout=2000)
            except Exception:
                pass
            if direct_btn.is_visible():
                direct_btn.click()
                logger.info(f"RAS 操作: 直接点击行内 '{action}' 按钮")
                return

        # 通过 cl-table-dropdown 触发
        # 先点击操作列中的 dropdown 触发器
        for trigger_text in ["操作", "更多", "..."]:
            trigger = row.locator("button, [class*='dropdown'], [class*='more']").filter(has_text=trigger_text).first
            if trigger.count() > 0:
                try:
                    trigger.wait_for(timeout=2000)
                except Exception:
                    pass
                if trigger.is_visible():
                    trigger.click()
                    self.page.wait_for_timeout(800)
                    # 在弹出菜单中查找操作项
                    menu = self.page.locator("[class*='dropdown']:visible, [class*='menu']:visible").last
                    if menu.count() > 0:
                        try:
                            menu.wait_for(timeout=2000)
                        except Exception:
                            pass
                        if menu.is_visible():
                            opt = menu.get_by_text(action, exact=False).first
                            if opt.count() > 0:
                                opt.click()
                                logger.info(f"RAS 操作: 通过 '{trigger_text}' 下拉菜单点击 '{action}'")
                                return
        raise Exception(f"RAS 操作 {action} 定位失败")

    def ras_operations(self, name: str, action: str):
        """对 RAS 实例执行操作（开机、关机等）。

        Args:
            name: 实例名称
            action: 操作名称，如"开机"、"关机"
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        try:
            self.page.wait_for_selector(".el-table__fixed-right", timeout=5000)
        except Exception:
            pass
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, action)
        except Exception as e:
            logger.warning(f"RAS 操作 {action} 标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, action)
        try:
            self._click_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug(f"RAS 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"RAS 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"RAS 实例 {name} 执行操作: {action}")

    def ras_unsubscribe(self, name: str):
        """对 RAS 实例执行退订操作。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, "退订")
        except Exception as e:
            logger.warning(f"RAS 退订标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "退订")
        self.page.wait_for_timeout(1000)
        try:
            self._click_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug("RAS 退订：未弹出确认对话框")
            else:
                raise
        logger.info(f"RAS 实例 {name} 退订请求已提交")

    def _duration_dialog(self, name: str, action: str, duration: str):
        """通用方法：处理授权/续期弹窗（共用 el-radio-button 时长选择组件）。

        Args:
            name: 实例名称
            action: 操作名称，"授权" 或 "续期"
            duration: 购买时长，如 "3个月", "2个月"
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, action)
        except Exception as e:
            logger.warning(f"RAS {action} 标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, action)
        self.page.wait_for_timeout(1500)
        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            logger.warning(f"RAS {action}：未找到弹窗，可能已自动完成")
            return

        # 前端使用 el-radio-button，匹配包含指定时长的按钮
        radio_btn = dialog.locator(".el-radio-button").filter(has_text=duration).first
        if radio_btn.count() > 0:
            try:
                radio_btn.wait_for(timeout=2000)
            except Exception:
                pass
            if radio_btn.is_visible():
                radio_btn.click()
                logger.info(f"RAS {action}：已选择 {duration} 购买时长")
                self.page.wait_for_timeout(500)
        else:
            active_btn = dialog.locator(".el-radio-button.is-active").first
            if active_btn.count() > 0:
                active_text = active_btn.inner_text()
                logger.info(f"RAS {action}：当前已选中 {active_text}（默认选中状态）")
            else:
                logger.warning(f"RAS {action}：未找到时长选项 {duration}，直接尝试确认")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"RAS 实例 {name} {action}操作已提交")

    def ras_authorize(self, name: str, duration: str):
        """对 RAS 实例执行授权操作。

        Args:
            name: 实例名称
            duration: 购买时长，如 "3个月"
        """
        self._duration_dialog(name, "授权", duration)

    def ras_renewal(self, name: str, duration: str):
        """对 RAS 实例执行续期操作。

        Args:
            name: 实例名称
            duration: 续期时长，如 "2个月"
        """
        self._duration_dialog(name, "续期", duration)

    def ras_rename(self, name: str, new_name: str):
        """修改 RAS 实例名称。

        触发"修改实例名称"弹窗，填写新名称后确认提交。

        Args:
            name: 当前实例名称
            new_name: 新的实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, "修改实例名称")
        except Exception as e:
            logger.warning(f"RAS 修改名称标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "修改实例名称")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="修改名称").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到修改名称弹窗")
        logger.info("RAS 修改名称：弹窗已打开")

        name_input = dialog.locator(".el-input__inner").first
        name_input.click()
        self.page.wait_for_timeout(300)
        name_input.fill("")
        self.page.wait_for_timeout(300)
        name_input.fill(new_name)
        self.page.wait_for_timeout(500)
        logger.info(f"RAS 修改名称：已填写新名称 {new_name}")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"RAS 实例 {name} 名称已修改为 {new_name}")

    def ras_delete(self, name: str):
        """删除 RAS 实例。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, "删除")
        except Exception as e:
            logger.warning(f"RAS 删除标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "删除")
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
            logger.debug("RAS 删除：无需勾选确认框")
        self._click_dialog_confirm()
        logger.info(f"RAS 实例 {name} 删除请求已提交")

    def ras_to_details(self, name: str):
        """点击实例名称，进入详情页。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        row = self.get_row_by_name(name)

        # 方法1: 查找行内包含名称的 <a> 标签或可点击 div，使用 Playwright force=true 点击
        # force=True 绕过 visibility:hidden 约束（Element 表格列常有此 CSS）
        name_links = row.locator("a, .overflow-ellipsis").all()
        for link in name_links:
            try:
                link_text = link.inner_text().strip()
                if name in link_text:
                    # 如果颜色是蓝色（可点击），force=True 点击触发 Vue router
                    color = link.evaluate("el => window.getComputedStyle(el).color")
                    if "64, 158, 255" in color:
                        link.click(force=True, timeout=5000)
                        self.page.wait_for_timeout(2000)
                        try:
                            self.page.wait_for_url(lambda u: "/ras-detail" in u, timeout=10000)
                            self.wait_for_page_ready()
                            logger.info(f"RAS 实例 {name} 通过名称链接进入详情页，URL: {self.page.url}")
                            return
                        except Exception:
                            pass
            except Exception:
                continue

        # 方法2: 点击包含名称的单元格（Playwright force=True 点击）
        cells = row.locator("td").all()
        for cell in cells:
            try:
                cell_text = cell.text_content().strip() if cell.count() > 0 else ""
                if cell_text == name or cell_text.startswith(name):
                    cell.click(force=True, timeout=5000)
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/ras-detail" in u, timeout=10000)
                        self.wait_for_page_ready()
                        logger.info(f"RAS 实例 {name} 通过单元格点击进入详情页，URL: {self.page.url}")
                        return
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 方法3: 搜索全页面精确文本，逐级向上找可点击父元素（Playwright force=True 点击）
        name_el = self.page.get_by_text(name, exact=True).first
        if name_el.count() > 0:
            for level in range(4):
                try:
                    target = name_el
                    for _ in range(level):
                        target = target.locator("xpath=..")
                    tag = target.evaluate("el => el.tagName").lower() if target.count() > 0 else ""
                    target.click(force=True, timeout=5000)
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/ras-detail" in u, timeout=10000)
                        self.wait_for_page_ready()
                        logger.info(f"RAS 实例 {name} 通过{level}级父元素点击进入详情页(tag={tag})，URL: {self.page.url}")
                        return
                    except Exception:
                        pass
                except Exception:
                    continue

        # 方法4: 从行 HTML 提取 server_id
        server_id = None
        try:
            row_html = row.evaluate("el => el.outerHTML")
            sid_match = re.search(
                r'server_id[=:]\s*["\']?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
                row_html
            )
            if sid_match:
                server_id = sid_match.group(1)
            else:
                id_match = re.search(
                    r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
                    row_html
                )
                if id_match:
                    server_id = id_match.group(0)
            if server_id:
                logger.info(f"RAS 实例 {name} 从行 HTML 获取 server_id: {server_id}")
        except Exception as e:
            logger.debug(f"RAS 从行 HTML 提取 server_id 失败: {e}")

        base = self.page.url.split("#")[0]
        if server_id:
            self.page.goto(f"{base}#/ras-detail?server_id={server_id}")
            self.wait_for_page_ready()
            logger.info(f"RAS 实例 {name} 通过 server_id 进入详情页，URL: {self.page.url}")
        else:
            raise Exception(f"无法进入 RAS 实例 {name} 的详情页")

    def ras_name_clickable(self, name: str) -> bool:
        """检查列表页 RAS 实例名称是否可点击跳转。

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
            logger.info(f"RAS 实例 {name} 名称颜色: {color}, 可点击: {is_link}")
            return is_link
        except Exception as e:
            logger.warning(f"检查 RAS 实例 {name} 名称可点击性失败: {e}")
            return False

    def ras_get_server_id(self, name: str) -> str | None:
        """进入详情页，从详情页 body 文本中提取 RAS 实例 ID。

        Args:
            name: 实例名称

        Returns:
            str: RAS 实例 ID（UUID格式），若未找到返回 None
        """
        self.ras_to_details(name)
        self.wait_for_detail_page_ready()
        body_text = self.page.inner_text("body")
        # 从 body 文本中提取 "id: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" 格式的 ID
        id_match = re.search(
            r'id:\s*([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})',
            body_text
        )
        if id_match:
            instance_id = id_match.group(1)
            logger.info(f"RAS 实例 {name} 页面 ID: {instance_id}")
            return instance_id
        logger.warning(f"RAS 实例 {name} 详情页 body 未找到 ID 字段")
        return None

    def ras_get_physical_host(self, name: str) -> str | None:
        """获取 RAS 实例所在物理机节点名称。

        Args:
            name: 实例名称

        Returns:
            str: 物理机名称，若未找到返回 None
        """
        self.goto_list_page()
        row_data = self.get_row_data(name)
        host = row_data.get("物理机", "")
        if host:
            logger.info(f"RAS 实例 {name} 物理节点: {host}")
            return host
        logger.warning(f"RAS 实例 {name} 未找到物理机字段")
        return None

    def ras_spec_upgrade(self, name: str) -> dict:
        """执行规格升级：选择比当前规格更高的可选规格并提交。

        Args:
            name: 实例名称

        Returns:
            dict: 选中的新规格信息 {'vcpus': int, 'memory_mb': int}
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()

        # 记录当前规格，用于后续严格选择"更高"规格
        row_data = self.get_row_data(name)
        current_spec = row_data.get("规格", "")
        current_vcpu = 0
        current_mem_mb = 0
        vcpu_match = re.search(r"(\d+)核", current_spec)
        mem_match = re.search(r"(\d+)\s*GiB", current_spec, re.IGNORECASE)
        if vcpu_match:
            current_vcpu = int(vcpu_match.group(1))
        if mem_match:
            current_mem_mb = int(mem_match.group(1)) * 1024
        logger.info(
            f"RAS 规格升级：当前规格 {current_spec}, "
            f"vcpu={current_vcpu}, memory={current_mem_mb}MB"
        )

        try:
            self._click_dropdown_action(name, "规格升级")
        except Exception as e:
            logger.warning(f"RAS 规格升级标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "规格升级")

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
        logger.info("RAS 规格升级：弹窗已打开")

        # 验证顶部提示信息
        alert = dialog.locator(".sugon-alert, .el-alert").first
        if alert.count() > 0:
            try:
                alert.wait_for(timeout=3000)
            except Exception:
                pass
            if alert.is_visible():
                alert_text = alert.inner_text()
                if "关机" in alert_text and "再启动" in alert_text:
                    logger.info("RAS 规格升级：提示信息验证通过（包含关机和再启动提醒）")
                else:
                    logger.warning(f"RAS 规格升级：提示信息缺少关机和再启动提醒，内容: {alert_text[:200]}")
        else:
            logger.warning("RAS 规格升级：未找到 alert 提示信息，跳过验证")

        # 等待表格渲染完成：表格体可见、至少一行有规格文本
        table_body = dialog.locator(".el-table__body-wrapper .el-table__body tbody")
        try:
            expect(table_body).to_be_visible(timeout=15000)
        except Exception:
            pass
        try:
            self.page.wait_for_selector(
                ".el-table__body-wrapper .el-table__row:has-text('核')",
                timeout=15000,
            )
        except Exception:
            logger.warning("RAS 规格升级：等待表格行渲染超时，继续尝试")

        rows = dialog.locator(".el-table__body-wrapper .el-table__row")
        try:
            expect(rows.first).to_be_visible(timeout=10000)
        except Exception:
            pass

        radio_rows = rows.all()
        if len(radio_rows) == 0:
            radio_rows = dialog.locator("tr").all()
        logger.info(f"RAS 规格升级：弹窗内找到 {len(radio_rows)} 行规格")

        def _parse_spec(text: str) -> tuple[int, int]:
            vcpu_match = re.search(r"(\d+)核", text)
            mem_match = re.search(r"(\d+)\s*GiB", text, re.IGNORECASE)
            vcpus = int(vcpu_match.group(1)) if vcpu_match else 0
            mem_mb = int(mem_match.group(1)) * 1024 if mem_match else 0
            return vcpus, mem_mb

        def _extract_spec_name(text: str) -> str:
            match = re.search(r"ras\.\S+|ras\S+", text)
            return match.group(0) if match else ""

        # 先按列表行文本尝试解析当前规格 CPU/内存
        current_vcpu, current_mem_mb = _parse_spec(current_spec)

        # 如果列表行只有规格名（如 ras.d6.large），从弹窗表格行中反查当前规格
        if current_vcpu == 0 and current_mem_mb == 0 and current_spec:
            for idx, row in enumerate(radio_rows):
                row_text = row.inner_text()
                spec_name = _extract_spec_name(row_text)
                if spec_name and (current_spec in row_text or spec_name in current_spec):
                    current_vcpu, current_mem_mb = _parse_spec(row_text)
                    logger.info(
                        f"RAS 规格升级：从弹窗第{idx+1}行反查当前规格 "
                        f"{current_spec} -> vcpu={current_vcpu}, mem={current_mem_mb}MB"
                    )
                    break

        logger.info(
            f"RAS 规格升级：当前规格 {current_spec}, "
            f"vcpu={current_vcpu}, memory={current_mem_mb}MB"
        )

        selected_spec = None
        for idx, row in enumerate(radio_rows):
            row_text = row.inner_text()
            vcpus, mem_mb = _parse_spec(row_text)
            spec_name = _extract_spec_name(row_text)

            # 跳过当前规格本身（按名称匹配）
            if spec_name and current_spec and spec_name == current_spec:
                logger.info(
                    f"RAS 规格升级：第{idx+1}行 {row_text[:80]} 为当前规格，跳过"
                )
                continue

            # 若已解析出当前规格资源，严格选择更高的规格
            if current_vcpu > 0 or current_mem_mb > 0:
                if vcpus <= current_vcpu and mem_mb <= current_mem_mb:
                    logger.info(
                        f"RAS 规格升级：第{idx+1}行 {row_text[:80]} "
                        f"不高于当前规格，跳过"
                    )
                    continue

            radio = row.locator(".el-radio__original, .el-radio").first
            if radio.count() == 0:
                continue
            is_disabled = False
            try:
                radio_class = radio.get_attribute("class") or ""
                if "is-disabled" in radio_class:
                    is_disabled = True
            except Exception:
                pass
            logger.info(
                f"RAS 规格升级：第{idx+1}行 disabled={is_disabled}, "
                f"vcpu={vcpus}, mem={mem_mb}MB, text={row_text[:80]}"
            )
            if is_disabled:
                continue

            selected_spec = {
                "vcpus": vcpus,
                "memory_mb": mem_mb,
                "name": spec_name,
            }

            # 优先点击可见的 .el-radio 包装元素
            radio_wrapper = row.locator(".el-radio").first
            if radio_wrapper.count() > 0 and radio_wrapper.is_visible():
                radio_wrapper.click()
            else:
                radio.evaluate("el => el.click()")
            logger.info(
                f"RAS 规格升级：选中规格 vcpu={selected_spec['vcpus']}核, "
                f"memory={selected_spec['memory_mb']}MB({selected_spec['name']})"
            )
            break

        if selected_spec is None:
            raise Exception("未找到可选的更高规格")

        confirm_btn = None
        for btn_sel in [
            dialog.locator(".cloud-button-btn").filter(has_text="确定"),
            dialog.locator("button").filter(has_text=re.compile(r"确定|确认")),
        ]:
            if btn_sel.count() > 0:
                try:
                    btn_sel.wait_for(timeout=3000)
                except Exception:
                    pass
                if btn_sel.is_visible():
                    confirm_btn = btn_sel
                    break
        if confirm_btn is None:
            raise Exception("未找到规格升级弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"RAS 实例 {name} 规格升级请求已提交")
        return selected_spec

    def ras_bind_eip(self, name: str) -> str | None:
        """为 RAS 实例绑定公网IP。

        Args:
            name: 实例名称

        Returns:
            str: 绑定的公网IP地址，若未找到返回 None
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, "绑定公网IP")
        except Exception as e:
            logger.warning(f"RAS 绑定公网IP标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "绑定公网IP")
        self.page.wait_for_timeout(1000)
        bind_dialog = self.locator(".sugon-dialog").filter(has_text="绑定公网IP")
        if bind_dialog.count() == 0 or not bind_dialog.first.is_visible():
            raise Exception("未找到绑定公网IP弹窗")
        dialog = bind_dialog.first

        # 选择资源池（优先选 public_net，否则选第一个）
        pool_selects = dialog.locator(".el-select").all()
        if len(pool_selects) > 0:
            pool_selects[0].click()
            self.page.wait_for_timeout(500)
            pool_options = self.locator(".el-select-dropdown:visible li")
            expect(pool_options.first).to_be_visible(timeout=5000)
            selected = False
            for keyword in ("public_net", "基础版", "public"):
                for i in range(pool_options.count()):
                    text = pool_options.nth(i).inner_text()
                    if keyword in text.lower():
                        pool_options.nth(i).click()
                        selected = True
                        break
                if selected:
                    break
            if not selected:
                pool_options.first.click()
            logger.info("RAS 绑定公网IP：已选择资源池")
            self.page.wait_for_timeout(1500)

        # 在弹窗中勾选第一个可用的公网IP
        eip_address = self._select_first_eip_in_dialog(dialog)
        if not eip_address:
            raise Exception("未在弹窗中找到可勾选的公网IP")
        logger.info(f"RAS 绑定公网IP：已勾选IP {eip_address}")

        # 点击确定
        confirm_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            try:
                confirm_btn.wait_for(timeout=3000)
            except Exception:
                pass
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            raise Exception("未找到绑定公网IP弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"RAS 实例 {name} 公网IP绑定请求已提交，IP={eip_address}")

        # 验证网络列显示已绑定的公网IP
        self._assert_eip_bound(name, eip_address, timeout=120)
        return eip_address

    def ras_unbind_eip(self, name: str):
        """解绑 RAS 实例的公网IP。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self._click_dropdown_action(name, "解绑公网IP")
        except Exception as e:
            logger.warning(f"RAS 解绑公网IP标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "解绑公网IP")
        self.page.wait_for_timeout(1000)
        unbind_dialog = self.locator(".sugon-dialog").filter(has_text="解绑公网IP")
        if unbind_dialog.count() == 0 or not unbind_dialog.first.is_visible():
            # 尝试匹配"解除绑定公网IP"或"解绑公网IP"
            unbind_dialog = self.locator(".sugon-dialog").filter(
                has_text=re.compile(r"解除绑定|解绑.*公网IP")
            )
            if unbind_dialog.count() == 0 or not unbind_dialog.first.is_visible():
                raise Exception("未找到解绑公网IP弹窗")
        dialog = unbind_dialog.first
        self.page.wait_for_timeout(1500)

        confirm_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            try:
                confirm_btn.wait_for(timeout=3000)
            except Exception:
                pass
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            raise Exception("未找到解绑公网IP弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"RAS 实例 {name} 公网IP解绑请求已提交")
        self.page.wait_for_timeout(3000)
        self._dismiss_visible_dialogs()

        # 验证网络列不再显示公网IP
        self._assert_eip_unbound(name, timeout=60)
        logger.info(f"RAS 实例 {name} 已解绑公网IP")

    def _assert_eip_unbound(self, name: str, timeout: int = 60):
        """断言列表页实例网络列不再显示公网IP。

        Args:
            name: 实例名称
            timeout: 超时时间（秒）
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                network = row_data.get("网络", "")
                fip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", str(network))
                if len(fip_patterns) <= 1:
                    logger.info(f"RAS 实例 {name} 已解绑公网IP，网络列: {network}")
                    return
                logger.debug(f"RAS 实例 {name} 网络列仍含公网IP: {network}，等待解绑生效...")
            except Exception as e:
                logger.debug(f"验证公网IP解绑状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"RAS 实例 {name} 网络列仍显示公网IP，解绑未生效")

    def _select_first_eip_in_dialog(self, dialog) -> str | None:
        """在绑定公网IP弹窗中选择第一个可用的IP，返回IP地址字符串。"""
        # 策略A: 表格行内有 radio 按钮
        rows = dialog.locator("tr, .el-table__row").all()
        for row in rows:
            if not row.is_visible():
                continue
            row_text = row.inner_text()
            ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", row_text)
            if ip_match:
                radio = row.locator(".el-radio__original, input[type='radio']").first
                if radio.count() > 0:
                    radio.evaluate("el => el.click()")
                else:
                    row.click()
                return ip_match.group(0)

        # 策略B: 独立 radio 列表
        radios = dialog.locator(".el-radio, input[type='radio']").all()
        for radio in radios:
            if not radio.is_visible():
                continue
            parent = radio.locator("xpath=../..").first
            if parent.count() == 0:
                parent = radio.locator("xpath=..").first
            if parent.count() > 0:
                parent_text = parent.inner_text()
                ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", parent_text)
                if ip_match:
                    radio.evaluate("el => el.click()")
                    return ip_match.group(0)

        return None

    def _assert_eip_bound(self, name: str, eip: str, timeout: int = 120):
        """断言列表页实例网络列已显示绑定的公网IP。

        Args:
            name: 实例名称
            eip: 期望显示的公网IP地址
            timeout: 超时时间（秒）
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                network = row_data.get("网络", "")
                if eip in str(network):
                    logger.info(f"RAS 实例 {name} 网络列已显示公网IP: {network}")
                    return
                logger.debug(f"RAS 实例 {name} 网络列当前: {network}，等待公网IP {eip} 出现...")
            except Exception as e:
                logger.debug(f"验证公网IP绑定状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"RAS 实例 {name} 网络列未显示公网IP {eip}")

    def ras_get_jump_address_text(self, name: str) -> str:
        """进入实例详情页并获取跳转地址字段的文本内容。

        Args:
            name: 实例名称

        Returns:
            str: 跳转地址字段的文本内容（可能是 URL 链接或警告文案）
        """
        max_retries = 3
        for attempt in range(max_retries):
            self.ras_to_details(name)
            self.wait_for_detail_page_ready()
            self.page.wait_for_timeout(3000)

            body_text = self.page.inner_text("body")
            if "跳转地址" in body_text:
                # 提取跳转地址行的文本
                items = self.page.locator("[class*='item-col'], [class*='cl-item-col']").all()
                for item in items:
                    text = item.inner_text()
                    if "跳转地址" in text:
                        logger.info(f"RAS 实例 {name} 跳转地址字段内容: {text}")
                        return text
                for line in body_text.split("\n"):
                    if "跳转地址" in line:
                        return line
                return body_text

            logger.warning(f"RAS 详情页第 {attempt + 1} 次未找到跳转地址，重试...")

        raise AssertionError(f"RAS 实例 {name} 详情页未找到跳转地址字段（已重试 {max_retries} 次）")

    def _extract_jump_url(self) -> str | None:
        """从当前详情页提取跳转地址 URL。"""
        self.wait_for_detail_page_ready()
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(500)

        body_text = self.page.inner_text("body")
        # 即使页面出现"非直连网络"等提示文案，仍尝试提取可能存在的管理公网 URL
        # （解绑用户绑定的 FIP 后平台可能保留管理 IP，跳转仍可成功）

        # 策略1: 按关键词搜索标签附近的内容
        for keyword in ["跳转地址", "访问地址", "管理地址", "登录地址", "控制台", "链接",
                        "平台地址", "RAS地址", "系统地址", "外链", "打开", "进入"]:
            try:
                label = self.get_by_text(keyword, exact=False).first
                if label.count() > 0:
                    try:
                        label.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if label.is_visible():
                        for ancestor in ["xpath=../..", "xpath=..", "xpath=../../..", "xpath=../../../../.."]:
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
                continue

        # 策略2: 搜索所有可见的http链接
        links = self.locator("a[href^='http']").all()
        for link in links:
            try:
                if link.is_visible():
                    href = link.get_attribute("href")
                    if href and ("openapiOAuth" in href or "172.22" in href or "ras" in href.lower()):
                        return href
            except Exception:
                continue

        # 策略3: 从body文本中提取URL
        urls = re.findall(r"https?://[^\s\n]+", body_text)
        for url in urls:
            if "172.22" in url or "openapiOAuth" in url:
                return url

        return None

    def ras_open_jump_address(self):
        """在详情页提取跳转地址，新标签页打开 RAS 平台页面。

        Returns:
            Page: Playwright 新页面对象（RAS 平台登录页），若不可用返回 None
        """
        jump_url = None
        for extract_attempt in range(1, 12):
            jump_url = self._extract_jump_url()
            if jump_url:
                break

            body_snippet = self.page.inner_text("body")[:2000]
            if "非直连网络" in body_snippet or "未绑定公网IP" in body_snippet:
                logger.warning(
                    f"RAS 跳转地址：第 {extract_attempt} 次提取失败，"
                    f"详情页显示'非直连网络需要绑定公网IP'"
                )
                return None  # 没有绑定EIP时，跳转地址不可用

            logger.warning(f"RAS 跳转地址：第 {extract_attempt} 次提取失败，等待10秒后重试")
            time.sleep(10)

        if not jump_url:
            logger.warning("RAS 跳转地址：未找到跳转地址 URL")
            return None
        logger.info(f"RAS 跳转地址：提取到 URL: {jump_url}")

        for attempt in range(1, 4):
            logger.info(f"RAS 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)
            if new_page is None:
                if attempt < 3:
                    logger.warning(f"RAS 跳转地址：第 {attempt} 次未获取到新页面，等待后重试")
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue
                return None

            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                logger.warning("RAS 跳转地址：新页面 domcontentloaded 超时")
            try:
                new_page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.warning("RAS 跳转地址：新页面 networkidle 超时")

            current_url = new_page.url
            logger.info(f"RAS 跳转地址：新页面当前 URL: {current_url}")

            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"RAS 跳转地址：加载到错误页面 {current_url}")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < 3:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        return None
                    continue
                return None

            # 验证页面
            has_ras_content = False
            try:
                body_text = new_page.inner_text("body")
                if any(k in body_text for k in ["DAS", "RAS", "漏洞扫描", "工作台", "首页"]):
                    has_ras_content = True
            except Exception:
                pass

            is_ras_platform = (
                "ras" in current_url.lower()
                or "/dashboard" in current_url
                or "openapiOAuth" in current_url
            )
            is_ras_ip = (
                "172.22" in current_url
                and "chrome-error" not in current_url
            )

            if has_ras_content or is_ras_platform or is_ras_ip:
                logger.info(f"RAS 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            logger.warning("RAS 跳转地址：页面未进入 RAS 平台，重试")
            try:
                new_page.close()
            except Exception:
                pass
            if attempt < 3:
                jump_url = self._refresh_and_get_new_jump_url()
                if not jump_url:
                    return None
                continue

        logger.warning("RAS 跳转地址：多次尝试后仍未成功打开 RAS 平台登录页")
        return None

    def ras_vnc_login(self, name: str, timeout: int = 60):
        """在 RAS 列表页点击实例「登录 VNC」，验证 VNC 控制台页面可打开。

        Args:
            name: 实例名称
            timeout: 等待 VNC 页面加载超时（秒）

        Returns:
            Page: VNC 控制台页面对象
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()

        logger.info(f"RAS 实例 {name} 准备点击登录VNC")
        with self.page.context.expect_page(timeout=timeout * 1000) as new_page_info:
            try:
                self._click_dropdown_action(name, "登录VNC")
            except Exception as e:
                logger.warning(f"RAS 登录VNC标准定位失败: {e}，尝试 click_action 兜底")
                self.click_action(name, "登录VNC")
        vnc_page = new_page_info.value

        try:
            vnc_page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
        try:
            vnc_page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass

        current_url = vnc_page.url
        logger.info(f"RAS 实例 {name} VNC 页面 URL: {current_url}")

        if "chrome-error" in current_url or "about:blank" in current_url:
            vnc_page.close()
            raise AssertionError(f"VNC 页面加载到错误页面: {current_url}")

        url_is_vnc = any(k in current_url.lower() for k in ["vnc", "novnc", "spice"])
        body_text = ""
        try:
            body_text = vnc_page.inner_text("body")[:500]
        except Exception:
            pass
        title = vnc_page.title()
        content_is_vnc = (
            url_is_vnc
            or any(k in body_text.lower() for k in ["vnc", "novnc", "spice", "connecting"])
            or any(k in title.lower() for k in ["vnc", "novnc", "spice"])
        )
        if not content_is_vnc:
            vnc_page.close()
            raise AssertionError(
                f"VNC 页面验证失败，URL={current_url}, title={title}, body={body_text}"
            )
        logger.info("RAS VNC 页面验证通过")
        return vnc_page

    def _refresh_and_get_new_jump_url(self) -> str | None:
        """离开详情页重新进入，强制后端生成新的跳转 token。"""
        logger.info("RAS 跳转地址：重新进入详情页以获取新的跳转链接...")
        name = None
        url = self.page.url
        name_match = re.search(r"server_name=([^&]+)", url)
        if name_match:
            from urllib.parse import unquote
            name = unquote(name_match.group(1))

        self.goto_list_page()
        self.page.wait_for_timeout(5000)

        if name:
            self.ras_to_details(name)
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
                logger.info(f"RAS 跳转地址：重进详情页后提取到 URL: {new_url}")
                return new_url
        logger.warning("RAS 跳转地址：重进详情页后多次尝试仍未提取到 URL")
        return None

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("RAS 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
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

    def wait_for_detail_page_ready(self, timeout: int = 60):
        """等待 RAS 详情页加载完成。

        Args:
            timeout: 超时时间（秒），默认 60
        """
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)
        self.page.wait_for_load_state("load", timeout=30000)
        spinners = self.page.locator(".el-loading-spinner")
        try:
            if spinners.count() > 0:
                spinners.first.wait_for(state="hidden", timeout=timeout * 1000)
        except Exception:
            logger.warning(f"RAS 详情页 loading spinner 在 {timeout}s 后仍未消失，继续执行")
            self.page.evaluate("""
                document.querySelectorAll('.el-loading-mask').forEach(el => el.remove());
                document.querySelectorAll('.el-loading-spinner').forEach(el => el.remove());
            """)

    def ras_hot_migration(self, name: str, target_host: str = None, m_type: str = "手动指定", bandwidth: str = "全速") -> str | None:
        """RAS 实例热迁移。

        通过"操作"下拉菜单中的"热迁移"打开热迁移弹窗，选择调度方式和目标物理机后确认。

        Args:
            name: RAS 实例名称
            target_host: 目标物理机名称，手动指定时有效
            m_type: 调度方式，"手动指定"或"系统分配"
            bandwidth: 迁移速率，"全速"

        Returns:
            str | None: 实际选择的目标物理机名称，系统分配时返回 None
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()

        try:
            self._click_dropdown_action(name, "热迁移")
        except Exception as e:
            logger.warning(f"RAS 热迁移标准定位失败: {e}，尝试 click_action 兜底")
            self.click_action(name, "热迁移")
        self.page.wait_for_timeout(1500)

        # 等待热迁移弹窗
        dialog = self.page.locator(".el-dialog__wrapper:visible, .sugon-dialog:visible").filter(has_text="热迁移").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到热迁移弹窗")
        logger.info("RAS 热迁移弹窗已打开")

        checked_host = None

        # 选择调度方式
        if m_type == "手动指定":
            dialog.get_by_role("radio", name="手动指定").click()
            self.page.wait_for_timeout(1000)

            # 点击"选择物理机"
            dialog.get_by_text("选择物理机").first.click()
            self.page.wait_for_timeout(1500)

            # 等待物理机选择 drawer
            drawer = self.page.locator(".el-drawer__wrapper:visible, .el-drawer:visible").filter(has_text="选择物理机").first
            if drawer.count() == 0 or not drawer.is_visible():
                raise Exception("未找到物理机选择弹窗")

            # 获取可用物理机列表
            available_hosts = self._get_available_migration_hosts(drawer)

            if not available_hosts:
                drawer.get_by_text("取消").click()
                self.page.wait_for_timeout(800)
                dialog.get_by_text("取消").click()
                logger.warning("没有可用的物理机可供选择，跳过热迁移")
                return None

            # 选择目标物理机
            if target_host:
                matched = [h for h in available_hosts if target_host in h]
                if matched:
                    drawer.get_by_role("radio", name=matched[0]).click()
                    checked_host = matched[0]
                    logger.info(f"已选择指定的目标物理机: {checked_host}")
                else:
                    drawer.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")
            else:
                drawer.get_by_role("radio", name=available_hosts[0]).click()
                checked_host = available_hosts[0]
                logger.info(f"已选择第一个可用的物理机: {checked_host}")

            # 点击确定关闭 drawer
            confirm_btn = drawer.locator(".cloud-button-btn, button").filter(has_text="确定").first
            if confirm_btn.count() == 0 or not confirm_btn.is_visible():
                confirm_btn = self.page.get_by_text("确定").filter(has_text="确定").first
            confirm_btn.click()
            self.page.wait_for_timeout(1000)

        # 确认热迁移
        confirm_btn = dialog.locator(".cloud-button-btn, button").filter(has_text="确定").first
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            confirm_btn = dialog.get_by_role("button", name="确定")
        confirm_btn.click()
        logger.info(
            f"RAS 实例 {name} 热迁移命令已下发: 调度方式={m_type}, "
            f"目标主机={checked_host}, 迁移速率={bandwidth}"
        )
        return checked_host

    def _get_available_migration_hosts(self, drawer) -> list[str]:
        """从物理机选择 drawer 中获取可用的迁移目标物理机列表。

        Args:
            drawer: 物理机选择 drawer 的定位器

        Returns:
            list[str]: 可用物理机名称列表
        """
        available_hosts = []
        self.page.wait_for_timeout(2000)

        all_rows = drawer.locator("tbody tr, .el-table__body-wrapper tr").all()
        logger.info(f"物理机选择弹窗中找到 {len(all_rows)} 个行")

        for row in all_rows:
            try:
                first_td = row.locator("td").first
                host_name = first_td.inner_text().strip()
                if not host_name:
                    continue

                radio = row.locator("input[type='radio']").first
                is_disabled = False
                if radio.count() > 0:
                    is_disabled = radio.is_disabled()

                row_classes = row.evaluate("el => el.className") or ""
                if "is-disabled" in row_classes:
                    is_disabled = True

                if not is_disabled and host_name:
                    available_hosts.append(host_name)
            except Exception as e:
                logger.debug(f"解析物理机行失败: {e}")
                continue

        logger.info(f"可用物理机列表: {available_hosts}")
        return available_hosts

    def delete_existing_ras(self, timeout: int = 300):
        """检查并删除列表页已存在的 RAS 实例。

        Args:
            timeout: 删除后等待确认的超时时间（秒），默认 300

        Returns:
            str or None: 被删除的实例名称，若无实例返回 None
        """
        self.goto_list_page()
        self.wait_for_page_ready()

        try:
            self.page.wait_for_selector(".el-table__body-wrapper table tbody tr", timeout=30000)
        except Exception:
            logger.info("RAS 列表页表格未加载，视为无实例")
            return None

        empty_text = self.page.locator(".el-table__empty-text, .el-table__empty-block").first
        try:
            try:
                empty_text.wait_for(timeout=3000)
            except Exception:
                pass
            if empty_text.is_visible():
                logger.info("RAS 列表页显示暂无数据，无需清理")
                return None
        except Exception:
            pass

        rows = self.page.locator(".el-table__body-wrapper table tbody tr").all()
        for row in rows:
            try:
                td_count = row.locator("td").count()
                if td_count <= 1:
                    continue
                row_data = self.get_row_data_by_locator(row)
                existing_name = row_data.get("名称", "")
                if existing_name and existing_name != "--":
                    logger.info(f"发现已有RAS实例: {existing_name}，先删除")
                    self.ras_delete(existing_name)
                    self.assert_deleted(existing_name, timeout=timeout, refresh=True)
                    logger.info(f"已有RAS实例 {existing_name} 删除完成")
                    return existing_name
            except Exception as e:
                logger.warning(f"检查/删除已有RAS实例时出错: {e}")
                continue
        logger.info("RAS 列表页无已有实例，无需清理")
        return None
