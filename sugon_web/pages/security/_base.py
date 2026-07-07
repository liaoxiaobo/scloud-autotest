"""安全合规模块共享的 Page Object 扩展。"""

import re
import time

from playwright.sync_api import expect

from sugon_web.utils.logger import logger


class SecurityEipMixin:
    """安全合规页面共享的公网IP绑定弹窗分页选择能力。"""

    def _is_clickable_element(self, locator) -> bool:
        """判断元素是否可点击。

        优先通过 DOM 语义（<a> 标签）或样式 cursor:pointer 判断；
        无法确定时 fallback 到 Element UI 主题蓝 RGB，避免换肤后误判。
        """
        try:
            tag = locator.evaluate("el => el.tagName.toLowerCase()")
            if tag == "a":
                return True
            cursor = locator.evaluate("el => window.getComputedStyle(el).cursor")
            if cursor == "pointer":
                return True
            color = locator.evaluate("el => window.getComputedStyle(el).color")
            return "64, 158, 255" in color
        except Exception:
            return False

    def _is_row_name_clickable(self, name: str) -> bool:
        """判断列表页指定实例名称是否为可点击链接。

        Args:
            name: 实例名称。

        Returns:
            bool: True 表示可点击，False 表示不可点击。
        """
        self.goto_list_page()
        row = self.get_row_by_name(name)
        name_cell = row.get_by_text(name, exact=True).first
        try:
            is_link = self._is_clickable_element(name_cell)
            logger.info(f"实例 {name} 名称可点击性: {is_link}")
            return is_link
        except Exception as e:
            logger.warning(f"检查实例 {name} 名称可点击性失败: {e}")
            return False

    def goto_security_list_page(self, max_attempts: int = 15) -> None:
        """通过框架导航进入安全合规服务列表页，并等待表格数据就绪。

        兼容 session 过期、无权限页、loading 状态等异常场景。
        针对 USM 等 SPA 从详情页/跳转地址页返回列表时，框架的 `goto_service`
        会把子页面误判为当前服务内页面而不导航，因此这里强制重新导航到列表 URL。
        """
        from sugon_web.common.auth import prepare_page_session
        from sugon_web.config.config import Config
        from sugon_web.config.constants import SERVICE_PATH_MAP

        base_url = Config.get("base_url").rstrip("/")
        service = self.service_name
        target_url = f"{base_url}{SERVICE_PATH_MAP[service]}"

        # 强制导航到列表页，避免当前处于详情/跳转子页面时 _is_current_service_path 误判
        self.goto_service(service, force=True)
        self.wait_for_page_ready()
        for attempt in range(1, max_attempts + 1):
            self.page.wait_for_timeout(2000)
            if "/no-permission" in self.page.url:
                logger.warning(f"{service} 列表页被重定向到无权限页，重新导航 (第{attempt}次)")
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            if "/login" in self.page.url:
                logger.warning(f"{service} 列表页被重定向到登录页，尝试重新登录 (第{attempt}次)")
                prepare_page_session(self.page, Config)
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            loading_mask = self.page.locator(
                ".el-loading-mask:visible, .el-loading-spinner:visible"
            ).first
            if loading_mask.count() > 0:
                logger.info(f"{service} 列表页数据加载中，继续等待 (第{attempt}次)...")
                continue
            has_rows = self.page.locator(".el-table__row").count() > 0
            has_empty = self.page.locator(".el-table__empty-block, .el-table__empty-text").count() > 0
            if has_rows or has_empty:
                logger.info(f"{service} 回到列表页（第{attempt}次检查）: {self.page.url}")
                return
            logger.info(f"{service} 列表页仍为空，等待数据加载中(第{attempt}次)...")
        raise AssertionError(
            f"{service} 列表页数据未能加载，当前URL={self.page.url}"
        )

    def _select_eip_in_paginated_dialog(
        self,
        dialog,
        eip_ip: str | None = None,
        max_pages: int = 5,
    ) -> str | None:
        """在支持分页的绑定公网IP弹窗中选择指定 IP，未指定时选择第一个可用 IP。

        部分资源池下可用公网IP较多，弹窗按 5 条/页展示；直接读取首屏可能漏掉目标 IP，
        因此按页遍历。若指定 IP 在所有页均未找到，则回退到选择第一个可用 IP。

        Args:
            dialog: 绑定公网IP弹窗定位器。
            eip_ip: 指定要选择的公网IP；为 None 时选择第一个可用IP。
            max_pages: 最大翻页次数，防止异常情况下无限循环。

        Returns:
            str | None: 选中的公网IP地址，未找到时返回 None。
        """
        target_ip = (eip_ip or "").strip()

        def _select_from_rows(rows, fallback: bool = False) -> str | None:
            for row in rows:
                try:
                    if not row.is_visible():
                        continue
                except Exception:
                    continue
                row_text = row.inner_text()
                ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", row_text)
                if not ip_match:
                    continue
                if target_ip and not fallback and target_ip not in row_text:
                    continue
                # 跳过明显已绑定的行（状态列包含“已绑定”）
                if "已绑定" in row_text:
                    continue
                radio = row.locator(".el-radio").first
                try:
                    if radio.count() > 0 and radio.is_visible():
                        radio.click()
                    else:
                        row.click()
                except Exception:
                    continue
                return ip_match.group(0)
            return None

        def _click_page_button(btn_locator) -> bool:
            try:
                if btn_locator.count() == 0:
                    return False
                btn = btn_locator.first
                if not btn.is_visible():
                    return False
                if btn.is_disabled():
                    return False
                btn.click()
                return True
            except Exception:
                return False

        # 第一遍：优先查找指定的 IP
        for _ in range(max_pages):
            selected = _select_from_rows(dialog.locator(".el-table__body .el-table__row").all())
            if selected:
                return selected
            if not _click_page_button(dialog.locator(".el-pagination .btn-next")):
                break
            self.page.wait_for_timeout(1200)

        # 第二遍：未指定或指定 IP 未找到时，回退到第一个可用 IP
        if not target_ip:
            return None

        self.logger.warning(f"未在弹窗首屏找到指定公网IP {target_ip}，尝试翻页查找/回退第一个可用IP")
        # 先回到第一页
        for _ in range(max_pages):
            if not _click_page_button(dialog.locator(".el-pagination .btn-prev")):
                break
            self.page.wait_for_timeout(800)

        for _ in range(max_pages):
            selected = _select_from_rows(
                dialog.locator(".el-table__body .el-table__row").all(), fallback=True
            )
            if selected:
                return selected
            if not _click_page_button(dialog.locator(".el-pagination .btn-next")):
                break
            self.page.wait_for_timeout(1200)

        return None

    def _eip_service_label(self) -> str:
        """返回当前服务日志前缀。"""
        return getattr(self, "_service_label", None) or getattr(
            self, "service_name", type(self).__name__
        )

    def _assert_eip_bound(self, name: str, eip: str, timeout: int = 120) -> None:
        """断言列表页实例网络列已显示绑定的公网IP。

        Args:
            name: 实例名称
            eip: 期望显示的公网IP地址
            timeout: 超时时间（秒）
        """
        svc = self._eip_service_label()
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                network = row_data.get("网络", "")
                if eip in str(network):
                    logger.info(f"{svc} 实例 {name} 网络列已显示公网IP: {network}")
                    return
                logger.debug(
                    f"{svc} 实例 {name} 网络列当前: {network}，等待公网IP {eip} 出现..."
                )
            except Exception as e:
                logger.debug(f"验证公网IP绑定状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"{svc} 实例 {name} 网络列未显示公网IP {eip}")

    def _assert_eip_unbound(self, name: str, timeout: int = 60) -> None:
        """断言列表页实例网络列不再显示公网IP（解绑后仅剩固定IP）。

        Args:
            name: 实例名称
            timeout: 超时时间（秒）
        """
        svc = self._eip_service_label()
        start = time.time()
        while time.time() - start < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                network = row_data.get("网络", "")
                fip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", str(network))
                if len(fip_patterns) <= 1:
                    logger.info(f"{svc} 实例 {name} 已解绑公网IP，网络列: {network}")
                    return
                logger.debug(
                    f"{svc} 实例 {name} 网络列仍含公网IP: {network}，等待解绑生效..."
                )
            except Exception as e:
                logger.debug(f"验证公网IP解绑状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"{svc} 实例 {name} 网络列仍显示公网IP，解绑未生效")


class ElementUiMixin:
    """安全合规各服务页共享的 Element UI 原子操作能力。

    提供“通用骨架 + 可配置参数”的表单/弹窗/详情页交互方法，
    供 APT/RAS/USM/VER/VDB/WAF/WPT 页面对象复用。各服务页仅需在存在差异时
    覆写薄封装（如 _btn_submit 的候选顺序、_input_name 的定位方式）。

    约定：子类可设置类属性 ``_service_label``（如 "APT"）用于日志前缀，
    未设置时回退到 ``service_name`` 或类名。
    """

    _service_label = None

    @property
    def _svc(self) -> str:
        """服务日志前缀，优先取 _service_label，其次 service_name。"""
        return self._service_label or getattr(self, "service_name", type(self).__name__)

    def get_detail_body_text(self) -> str:
        """获取详情页 body 文本内容，供测试层回读页面信息断言。"""
        return self.page.inner_text("body")

    def goto_list_page(self):
        """导航到服务列表页。从详情页或跳转地址页回到列表时必须用此方法。"""
        self.goto_security_list_page()

    @property
    def _input_name(self):
        """创建表单：名称输入框（默认 get_by_role 定位）。"""
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称")
        ).get_by_role("textbox")

    def _find_submit_button(self, candidates: list[str] | None = None):
        """按候选文案顺序查找并返回创建表单的提交按钮定位器。

        Args:
            candidates: 按优先级排列的按钮文案；为 None 时用通用默认顺序。

        Returns:
            Locator: 首个可见的提交按钮定位器。
        """
        if candidates is None:
            candidates = ["立即创建", "点击创建", "创建", "提交", "确定"]
        locators = []
        for text in candidates:
            locators.append(self.locator(".cloud-button-btn").filter(has_text=text))
            locators.append(self.get_by_text(text))
            locators.append(self.get_by_role("button", name=text))
        locators.append(
            self.locator("button").filter(has_text=re.compile(r"创建|提交|确定"))
        )
        for loc in locators:
            try:
                expect(loc).to_be_visible(timeout=3000)
                return loc
            except Exception:
                continue
        raise Exception(f"未找到 {self._svc} 创建表单的提交按钮")

    @property
    def _btn_submit(self):
        """创建表单：提交按钮（默认候选顺序）。"""
        return self._find_submit_button()

    def _select_form_item_first(self, label: str):
        """选择表单下拉项的第一个可见选项。

        兼容下拉框已打开/已关闭等多种状态，先关闭可能已打开的下拉框，
        再重新打开并等待选项加载，提高从“指定选项未找到”异常中回退时的稳定性。

        Args:
            label: 表单字段标签
        """
        form_item = self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label)}"))
        dropdown = form_item.locator(".el-select").first

        # 先关闭页面上可能已打开的下拉框，避免状态混乱
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        except Exception:
            pass

        # 确保下拉框可见后点击打开
        dropdown.wait_for(state="visible", timeout=10000)
        dropdown.click()
        self.page.wait_for_timeout(500)

        # 等待选项渲染，先尝试一次性等待
        try:
            self.page.wait_for_selector(".el-select-dropdown:visible li", timeout=10000)
        except Exception:
            pass

        # 轮询等待选项加载，最多 30 次（约 15 秒）
        for attempt in range(30):
            options = self.locator(".el-select-dropdown:visible li")
            if options.count() > 0:
                logger.info(f"{self._svc} 下拉框 '{label}' 选项已加载，共 {options.count()} 项")
                options.first.click()
                logger.info(f"{self._svc} 创建：选择 {label} = 第一个可用选项")
                return
            logger.warning(f"{self._svc} 下拉框 '{label}' 选项为空，第 {attempt + 1} 次重试等待...")
            self.page.wait_for_timeout(500)

        # 最后尝试重新打开一次下拉框
        dropdown.click()
        self.page.wait_for_timeout(1000)
        options = self.locator(".el-select-dropdown:visible li")
        if options.count() > 0:
            options.first.click()
            logger.info(f"{self._svc} 创建：选择 {label} = 第一个可用选项（二次打开）")
            return

        raise Exception(f"下拉选项为空: {label}")

    def _select_form_item(self, label: str, option: str, fallback_first: bool = False):
        """选择表单的下拉项。

        Args:
            label: 表单字段标签（如"版本"、"集群"、"安全底座"、"云硬盘类型"）
            option: 要选择的下拉项文本（支持模糊匹配）
            fallback_first: 未找到指定选项且下拉有可用项时，是否回退选择第一个可用项。
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

        dropdown_option_selector = (
            ".el-select-dropdown:visible .el-select-dropdown__item, "
            ".el-select-dropdown:visible li, .el-dropdown-menu:visible li"
        )
        try:
            self.page.wait_for_selector(dropdown_option_selector, timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

        all_visible = self.locator(dropdown_option_selector)
        for attempt in range(10):
            cnt = all_visible.count()
            if cnt > 0:
                logger.info(f"{self._svc} 下拉框 '{label}' 选项已加载，共 {cnt} 项")
                break
            logger.warning(f"{self._svc} 下拉框 '{label}' 选项未加载，第 {attempt + 1} 次重试等待...")
            self.page.wait_for_timeout(1500)
            all_visible = self.locator(dropdown_option_selector)
        else:
            logger.warning(f"{self._svc} 下拉框 '{label}' 选项仍为空，尝试重新点击下拉框")
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
            if fallback_first and cnt > 0:
                logger.warning(
                    f"{self._svc} 下拉框 '{label}' 未找到选项 '{option}'，"
                    f"回退选择第一个可用选项: '{available[0]}'"
                )
                all_visible.first.click()
                logger.info(f"{self._svc} 创建：选择 {label} = {available[0]}（回退）")
                return
            logger.error(f"{self._svc} 下拉框 '{label}' 可用选项: {available}")
            raise Exception(f"未找到下拉选项: {label} = {option}，可用选项: {available}")
        options.first.click()
        logger.info(f"{self._svc} 创建：选择 {label} = {option}")

    def _select_flavor(self, cpu: str = "4核", memory: str = "8GiB"):
        """选择规格表格中的指定行。

        Args:
            cpu: CPU 规格（如"4核"）
            memory: 内存规格（如"8GiB"）
        """
        rows = self.locator(".el-table__row")
        expect(rows.first).to_be_visible(timeout=10000)
        self.page.wait_for_timeout(1500)

        def _find_target():
            all_rows = self.locator(".el-table__row")
            row_count = all_rows.count()
            for i in range(row_count):
                row = all_rows.nth(i)
                row_text = row.inner_text()
                if cpu in row_text and memory in row_text:
                    return row
            return None

        target_row = _find_target()

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

            target_row = _find_target()
            if target_row is None:
                all_rows = self.locator(".el-table__row")
                if all_rows.count() > 0:
                    target_row = all_rows.first

        if target_row is None:
            raise Exception(f"未找到规格行: CPU={cpu}, 内存={memory}")

        # Element UI 表格单元格内 .el-radio 标签常因 label 文本为空/塌陷而被判定
        # not visible，原生点击 <label> 会超时。优先点击始终有尺寸的 .el-radio__inner
        # 圆圈（真实原生 click，触发 Vue @change），其次回退 force 点击隐藏的
        # .el-radio__original input，最后才点 label。
        clicked = False
        for sel in (".el-radio__inner", ".el-radio__original", ".el-radio"):
            target = target_row.locator(sel).first
            if target.count() == 0:
                continue
            try:
                target.click(timeout=5000)
                clicked = True
                break
            except Exception:
                try:
                    target.click(force=True, timeout=5000)
                    clicked = True
                    break
                except Exception:
                    continue
        if not clicked:
            raise Exception(f"{self._svc} 创建：规格行 radio 无法点击")
        logger.info(f"{self._svc} 创建：选择规格 CPU={cpu}, 内存={memory}")

    def _click_dialog_confirm(self, dialog=None):
        """点击当前可见弹窗的确认/确定按钮（兼容 el-dialog 和 sugon-dialog）。

        Args:
            dialog: 弹窗定位器，None 时在整页范围内查找当前可见弹窗。
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

    def _click_duration_action(self, name: str, action: str) -> None:
        """打开指定实例的授权/续期操作入口。

        默认通过行内"操作"列点击；子类若使用下拉菜单等自定义入口可覆写此方法。

        Args:
            name: 实例名称。
            action: 操作名称，如"授权"、"续期"。
        """
        self.click_action(name, action)

    def _duration_dialog(self, name: str, action: str, duration: str) -> None:
        """处理授权/续期弹窗（共用 el-radio-button 时长选择组件）。

        Args:
            name: 实例名称。
            action: 操作名称，如"授权"、"续期"。
            duration: 购买时长，如"3个月"、"2个月"。
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self._click_duration_action(name, action)
        self.page.wait_for_timeout(1500)
        dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=3000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            logger.warning(f"{self._svc} {action}：未找到弹窗，可能已自动完成")
            return

        radio_btn = dialog.locator(".el-radio-button").filter(has_text=duration).first
        if radio_btn.count() > 0:
            try:
                radio_btn.wait_for(timeout=2000)
            except Exception:
                pass
            if radio_btn.is_visible():
                radio_btn.click()
                logger.info(f"{self._svc} {action}：已选择 {duration} 购买时长")
                self.page.wait_for_timeout(500)
        else:
            active_btn = dialog.locator(".el-radio-button.is-active").first
            if active_btn.count() > 0:
                active_text = active_btn.inner_text()
                logger.info(f"{self._svc} {action}：当前已选中 {active_text}（默认选中状态）")
            else:
                logger.warning(f"{self._svc} {action}：未找到时长选项 {duration}，直接尝试确认")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"{self._svc} 实例 {name} {action}操作已提交")

    def _wait_loading_mask_hidden(self, container=None, timeout: int = 30) -> None:
        """等待 container 内的 el-loading-mask 消失（忽略异常）。

        Args:
            container: 查找范围定位器；None 时在整个页面查找。
            timeout: 最大等待时间（秒），默认 30。
        """
        scope = container if container is not None else self.page
        try:
            scope.locator(".el-loading-mask:visible").first.wait_for(
                state="hidden", timeout=timeout * 1000
            )
        except Exception:
            pass

    def wait_for_detail_page_ready(self, timeout: int = 60):
        """等待详情页加载完成。

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
            logger.warning(f"{self._svc} 详情页 loading spinner 在 {timeout}s 后仍未消失，继续执行")
            self.page.evaluate("""
                document.querySelectorAll('.el-loading-mask').forEach(el => el.remove());
                document.querySelectorAll('.el-loading-spinner').forEach(el => el.remove());
            """)
