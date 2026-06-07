import re
import time
from playwright.sync_api import expect
from sugon_web.common.base import BasePage
from sugon_web.assertions.security import AptAssertionMixin
from sugon_web.utils.logger import logger


class AptPage(AptAssertionMixin, BasePage):
    """攻击预警 页面对象。

    覆盖以下能力：
    - 创建 APT 实例（基本设置 + 配置）
    - 实例操作（开机、关机、删除）
    - 实例状态读取（服务状态、虚拟机状态）
    - 进入实例详情页 / 跳转地址验证
    """

    service_name = "攻击预警"

    def goto_list_page(self):
        """导航到 APT 列表页。从详情页或跳转地址页回到列表时必须用此方法。"""
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/das/#/apt"
        self.page.goto(target_url)
        self.wait_for_page_ready()
        for attempt in range(1, 16):
            self.page.wait_for_timeout(2000)
            if "/no-permission" in self.page.url:
                logger.warning(f"APT 列表页被重定向到无权限页，重新导航 (第{attempt}次)")
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            loading_mask = self.page.locator(".el-loading-mask:visible, .el-loading-spinner:visible").first
            if loading_mask.count() > 0:
                logger.info(f"APT 列表页数据加载中，继续等待 (第{attempt}次)...")
                continue
            has_rows = self.page.locator(".el-table__row").count() > 0
            has_empty = self.page.locator(".el-table__empty-block, .el-table__empty-text").count() > 0
            if has_rows or has_empty:
                logger.info(f"APT 回到列表页（第{attempt}次检查）: {self.page.url}")
                return
            logger.info(f"APT 列表页仍为空，等待数据加载中(第{attempt}次)...")
            if attempt >= 3 and not has_rows and not has_empty:
                logger.warning(f"APT 列表页数据未就绪，继续等待 (第{attempt}次)...")
        logger.info(f"APT 回到列表页: {self.page.url}")

    @property
    def _input_name(self):
        """APT 创建表单：名称输入框"""
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称")
        ).get_by_role("textbox")

    @property
    def _btn_submit(self):
        """APT 创建表单：提交按钮（立即创建）"""
        locators = [
            self.locator(".cloud-button-btn").filter(has_text="立即创建"),
            self.get_by_text("立即创建"),
            self.get_by_role("button", name="立即创建"),
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
        raise Exception("未找到 APT 创建表单的提交按钮")

    def _select_form_item_first(self, label: str):
        """选择表单下拉项的第一个可见选项。

        Args:
            label: 表单字段标签（如"安全底座"）
        """
        form_item = self.locator(".el-form-item").filter(has_text=re.compile(rf"^{re.escape(label)}"))
        dropdown = form_item.locator(".el-select").first
        dropdown.click()
        self.page.wait_for_timeout(500)
        self.locator(".el-select-dropdown:visible li").first.click()
        logger.info(f"APT 创建：选择 {label} = 第一个可用选项")

    def _select_form_item(self, label: str, option: str):
        """选择表单的下拉项。

        Args:
            label: 表单字段标签（如"版本"、"集群"、"安全底座"、"云硬盘类型"）
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
        self.page.wait_for_timeout(1500)
        options = self.locator(".el-select-dropdown:visible li, .el-dropdown-menu:visible li").filter(has_text=option)
        if options.count() == 0:
            options = self.locator(".el-select-dropdown:visible li, .el-dropdown-menu:visible li").filter(has_text=re.compile(rf"^{re.escape(option)}$"))
        if options.count() == 0:
            raise Exception(f"未找到下拉选项: {label} = {option}")
        options.first.click()
        logger.info(f"APT 创建：选择 {label} = {option}")

    def _select_flavor(self, cpu: str = "4核", memory: str = "8GiB"):
        """选择规格表格中的指定行。

        Args:
            cpu: CPU 规格（如"4核"）
            memory: 内存规格（如"8GiB"）
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
        logger.info(f"APT 创建：选择规格 CPU={cpu}, 内存={memory}")

    def apt_create(
        self,
        name: str,
        version: str = "v2.0.76",
        cluster: str = "Autotest",
        base_name: str = None,
        volume_type: str = "xbd-type",
        cpu: str = "4核",
        memory: str = "8GiB",
    ):
        """创建 APT 实例。

        通过菜单导航进入列表页后点击"新建"按钮进入创建页面。

        Args:
            name: 实例名称
            version: 版本号，默认 v2.0.76
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            volume_type: 云硬盘类型，默认 xbd-type
            cpu: 规格 CPU，默认 4核
            memory: 规格内存，默认 8GiB
        """
        # 从列表页点击"新建"按钮进入创建页面（如不在列表页则先导航）
        current_url = self.page.url
        if "/apt" not in current_url or "create-apt" in current_url or "detail" in current_url:
            self.goto_service(self.service_name)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)
        # 等待"新建"按钮可见
        btn = self.btn_create
        btn.click()
        self.wait_for_page_ready()
        # 等待创建表单渲染就绪
        expect(self._input_name).to_be_visible(timeout=10000)
        logger.info("APT 创建页面加载成功")

        self._input_name.fill(name)

        if version:
            self._select_form_item("版本", version)
        if cluster:
            self._select_form_item("集群", cluster)
        if base_name:
            self._select_form_item("安全底座", base_name)
        else:
            self._select_form_item_first("安全底座")

        if volume_type:
            self._select_form_item("云硬盘类型", volume_type)

        self._select_flavor(cpu=cpu, memory=memory)

        self._btn_submit.click()
        logger.info(f"APT 创建：已提交创建请求 {name}")

        self.page.wait_for_timeout(3000)

        # 检查是否有错误 toast（el-message）
        error_toast = self.page.locator(".el-message--error, .el-message.el-message--error").first
        try:
            try:
                error_toast.wait_for(timeout=3000)
            except Exception:
                pass
            if error_toast.is_visible():
                toast_text = error_toast.inner_text()
                logger.error(f"APT 创建失败，检测到错误提示: {toast_text}")
                raise Exception(f"APT 创建失败: {toast_text}")
        except Exception as e:
            if "APT 创建失败" in str(e):
                raise
            logger.debug(f"APT 创建：未检测到错误 toast")

        # 检查是否有确认弹窗（如二次确认）
        try:
            popup = self.page.locator(".el-message-box__wrapper:visible, .sugon-dialog:visible, .el-dialog:visible").first
            try:
                popup.wait_for(timeout=3000)
            except Exception:
                pass
            if popup.is_visible():
                popup_text = popup.inner_text()
                logger.info(f"APT 创建弹窗内容: {popup_text}")
                self._click_dialog_confirm()
                self.page.wait_for_timeout(2000)
        except Exception as e:
            logger.debug(f"APT 创建：未检测到确认弹窗: {e}")

        # 等待页面自动跳转（成功时会跳转到 /apt），最多等待 10 秒
        try:
            self.page.wait_for_url(lambda url: "/apt" in url and "create-apt" not in url, timeout=10000)
            logger.info(f"APT 创建：页面已自动跳转到列表页")
        except Exception:
            logger.warning("APT 创建：页面未自动跳转，手动导航到列表页")
            base_url = self.page.url.split('#')[0].rstrip('/')
            if not base_url.endswith('/das'):
                base_url = f"{base_url}/das"
            self.page.goto(f"{base_url}/#/apt")

        self.wait_for_page_ready()
        logger.info(f"APT 创建：已到达列表页")

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
                                                            if btn.count() > 0 and btn.is_visible(timeout=500):
                                                                btn.click()
                                                                self.page.wait_for_timeout(300)
                                                                break
                    except Exception:
                        continue
            except Exception:
                continue

    def apt_operations(self, name: str, action: str):
        """对 APT 实例执行操作（开机/启动、关机、删除等）。

        Args:
            name: 实例名称
            action: 操作名称，如"开机"、"关机"、"删除"、"启动"
        """
        self.goto_list_page()
        # 等待表格固定列（含操作按钮）渲染完成
        self.page.wait_for_timeout(2000)
        try:
            self.page.wait_for_selector(".el-table__fixed-right", timeout=5000)
        except Exception:
            pass
        self._dismiss_visible_dialogs()
        # 滚动目标行到可见区域，确保操作按钮不被遮挡
        try:
            row = self.get_row_by_name(name)
            row.evaluate("el => el.scrollIntoView({block: 'center'})")
            self.page.wait_for_timeout(500)
        except Exception:
            pass
        self.click_action(name, action)
        try:
            self._click_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug(f"APT 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"APT 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"APT 实例 {name} 执行操作: {action}")

    def apt_delete(self, name: str):
        """删除 APT 实例（先勾选确认框，再点击确定）。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        try:
            self.page.wait_for_selector(".el-table__fixed-right", timeout=5000)
        except Exception:
            pass
        self._dismiss_visible_dialogs()
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
            logger.debug("APT 删除：无需勾选确认框")
        self._click_dialog_confirm()
        logger.info(f"APT 实例 {name} 删除请求已提交")

    def apt_to_details(self, name: str):
        """点击实例名称，进入详情页。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        row = self.get_row_by_name(name)

        # 方法1: 查找行内包含名称的 <a> 标签，提取 href
        links = row.locator("a").all()
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                link_text = link.inner_text().strip()
                if name in link_text or "apt-detail" in href or "server_id" in href:
                    base = self.page.url.split("#")[0]
                    if href.startswith("http"):
                        target = href
                    elif href.startswith("#") or href.startswith("/"):
                        target = f"{base}{href}"
                    else:
                        target = f"{base}#/apt-detail?server_id={href}"
                    self.page.goto(target)
                    self.wait_for_page_ready()
                    if "/apt-detail" in self.page.url:
                        logger.info(f"APT 实例 {name} 通过链接进入详情页，URL: {self.page.url}")
                        return
            except Exception:
                continue

        # 方法2: 找到包含名称的单元格 <td>，用 JS dispatchEvent 点击触发 Vue Router
        cells = row.locator("td").all()
        for cell in cells:
            try:
                cell_text = cell.text_content().strip() if cell.count() > 0 else ""
                if cell_text == name or cell_text.startswith(name):
                    cell.evaluate("el => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/apt-detail" in u, timeout=5000)
                        self.wait_for_page_ready()
                        logger.info(f"APT 实例 {name} 通过单元格点击进入详情页，URL: {self.page.url}")
                        return
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 方法3: 搜索全页面精确文本，逐级向上找可点击父元素
        name_el = self.page.get_by_text(name, exact=True).first
        if name_el.count() > 0:
            for level in range(4):
                try:
                    target = name_el
                    for _ in range(level):
                        target = target.locator("xpath=..")
                    tag = target.evaluate("el => el.tagName").lower() if target.count() > 0 else ""
                    target.evaluate("el => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/apt-detail" in u, timeout=3000)
                        self.wait_for_page_ready()
                        logger.info(f"APT 实例 {name} 通过{level}级父元素点击进入详情页(tag={tag})，URL: {self.page.url}")
                        return
                    except Exception:
                        pass
                except Exception:
                    continue

        # 方法4: 从行 HTML 中提取 server_id
        server_id = None
        try:
            row_html = row.evaluate("el => el.outerHTML")
            # 优先匹配 server_id 的 href 参数
            sid_match = re.search(r'server_id[=:]\s*["\']?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', row_html)
            if sid_match:
                server_id = sid_match.group(1)
            else:
                # 降级匹配任意 UUID
                id_match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', row_html)
                if id_match:
                    server_id = id_match.group(0)
            if server_id:
                logger.info(f"APT 实例 {name} 从行 HTML 获取 server_id: {server_id}")
        except Exception as e:
            logger.debug(f"APT 从行 HTML 提取 server_id 失败: {e}")

        base = self.page.url.split("#")[0]
        if server_id:
            self.page.goto(f"{base}#/apt-detail?server_id={server_id}")
            self.wait_for_page_ready()
            logger.info(f"APT 实例 {name} 通过 server_id 进入详情页，URL: {self.page.url}")
        else:
            raise Exception(f"无法进入 APT 实例 {name} 的详情页：未找到链接、点击无效且无法提取 server_id")

    def apt_open_jump_address(self, refresh_interval: int = 5, max_wait: int = 300):
        """在详情页点击跳转地址 URL，新打开 APT 平台页面。

        若跳转地址尚未生成（显示"--"），会每 refresh_interval 秒刷新页面重试，
        直至获取到有效 URL 或超过 max_wait 秒。

        Args:
            refresh_interval: 刷新间隔（秒），默认 5
            max_wait: 最大等待时间（秒），默认 300

        Returns:
            Page: Playwright 新页面对象（APT 平台登录页）
        """
        jump_url = None
        self.wait_for_page_ready()

        start_time = time.time()
        while time.time() - start_time < max_wait:
            self.page.wait_for_timeout(2000)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(500)

            # 从详情页提取跳转地址
            jump_url = None
            for keyword in ["跳转地址", "访问地址", "管理地址", "登录地址", "控制台", "链接"]:
                if jump_url:
                    break
                try:
                    label = self.get_by_text(keyword, exact=False).first
                    if label.count() > 0:
                        try:
                            label.wait_for(timeout=3000)
                        except Exception:
                            pass
                        if label.is_visible():
                                                for ancestor in ["xpath=../..", "xpath=..", "xpath=../../..", "xpath=../../../../.."]:
                                                    parent = label.locator(ancestor).first
                                                    if parent.count() > 0:
                                                        link = parent.locator("a[href^='http']").first
                                                        if link.count() > 0 and link.is_visible():
                                                            jump_url = link.get_attribute("href")
                                                            if jump_url and jump_url != "--":
                                                                logger.info(f"APT 跳转地址：关键词'{keyword}'从 <a> 获取 URL: {jump_url}")
                                                                break
                                                        try:
                                                            text = parent.inner_text()
                                                        except Exception:
                                                            text = parent.text_content() or ""
                                                        url_match = re.search(r"https?://[^\s\n]+", text)
                                                        if url_match:
                                                            jump_url = url_match.group(0)
                                                            logger.info(f"APT 跳转地址：关键词'{keyword}'从文本提取 URL: {jump_url}")
                                                            break
                except Exception as e:
                    logger.debug(f"APT 跳转地址：关键词'{keyword}'查找失败: {e}")
                    continue

            if not jump_url:
                links = self.locator("a[href^='http']").all()
                for link in links:
                    try:
                        if link.is_visible():
                            href = link.get_attribute("href")
                            if href and "apt" in href.lower():
                                jump_url = href
                                logger.info(f"APT 跳转地址：从全局 <a> 获取 URL: {jump_url}")
                                break
                    except Exception:
                        continue

            if jump_url and jump_url != "--":
                break

            logger.info(f"APT 跳转地址尚未生成，{refresh_interval}秒后刷新页面重试...")
            time.sleep(refresh_interval)
            self.page.reload()
            self.wait_for_page_ready()

        if not jump_url or jump_url == "--":
            raise Exception("未找到跳转地址 URL")

        for attempt in range(1, 4):
            logger.info(f"APT 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)

            if new_page is None:
                if attempt < 3:
                    logger.warning(f"APT 跳转地址：第 {attempt} 次未获取到新页面，等待60秒后重试")
                    time.sleep(60)
                    continue
                raise Exception("未能获取跳转地址打开的新页面")

            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=120000)
            except Exception:
                logger.warning("APT 跳转地址：新页面 domcontentloaded 超时")
            try:
                new_page.wait_for_load_state("networkidle", timeout=120000)
            except Exception:
                logger.warning("APT 跳转地址：新页面 networkidle 超时")

            current_url = new_page.url
            logger.info(f"APT 跳转地址：新页面当前 URL: {current_url}")

            if "openapiOAuth" in current_url:
                try:
                    logger.info("APT 跳转地址：当前在 OAuth 认证页，等待自动重定向...")
                    new_page.wait_for_url(lambda url: "/home" in url or "/dashboard" in url, timeout=120000)
                    current_url = new_page.url
                    logger.info(f"APT 跳转地址：重定向后 URL: {current_url}")
                except Exception:
                    logger.warning("APT 跳转地址：等待自动重定向超时")

            is_apt_platform = "apt" in current_url.lower() or "/dashboard" in current_url or "/home" in current_url

            has_apt_content = False
            try:
                body_text = new_page.inner_text("body")
                if any(k in body_text for k in ["DASAPT", "APT", "攻击预警", "工作台", "首页"]):
                    has_apt_content = True
                    logger.info(f"APT 跳转地址：页面内容验证通过，包含 APT 平台标识")
            except Exception:
                pass

            if is_apt_platform or has_apt_content:
                logger.info(f"APT 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"APT 跳转地址：加载到错误页面 {current_url}，关闭后等待60秒重试")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < 3:
                    time.sleep(60)
                    continue

            logger.warning(f"APT 跳转地址：页面未进入 APT 平台，等待60秒后重试")
            try:
                new_page.close()
            except Exception:
                pass
            if attempt < 3:
                time.sleep(60)
                continue

        raise Exception("APT 跳转地址：多次尝试后仍未成功打开 APT 平台登录页")

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("APT 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
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

    def apt_name_clickable(self, name: str) -> bool:
        """检查列表页 APT 实例名称是否可点击跳转（用于验证关机后不可点击的预期）。

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
            logger.info(f"APT 实例 {name} 名称颜色: {color}, 可点击: {is_link}")
            return is_link
        except Exception as e:
            logger.warning(f"检查 APT 实例 {name} 名称可点击性失败: {e}")
            return False

    def delete_existing_apt(self, timeout: int = 300):
        """检查并删除列表页已存在的 APT 实例。

        Args:
            timeout: 删除后等待确认的超时时间（秒），默认 300
        """
        self.goto_list_page()
        self.wait_for_page_ready()

        # 等待表格数据加载完成（最多等10秒）
        try:
            self.page.wait_for_selector(".el-table__body-wrapper table tbody tr", timeout=30000)
        except Exception:
            logger.info("APT 列表页表格未加载，视为无实例")
            return None

        # 检查是否有"暂无数据"提示
        empty_text = self.page.locator(".el-table__empty-text, .el-table__empty-block").first
        try:
            try:
                empty_text.wait_for(timeout=3000)
            except Exception:
                pass
            if empty_text.is_visible():
                logger.info("APT 列表页显示暂无数据，无需清理")
                return None
        except Exception:
            pass

        # 获取表格行并检查
        rows = self.page.locator(".el-table__body-wrapper table tbody tr").all()
        for row in rows:
            try:
                td_count = row.locator("td").count()
                if td_count <= 1:
                    continue
                row_data = self.get_row_data_by_locator(row)
                existing_name = row_data.get("名称", "")
                if existing_name and existing_name != "--":
                    logger.info(f"发现已有APT实例: {existing_name}，先删除")
                    self.apt_delete(existing_name)
                    self.assert_deleted(existing_name, timeout=timeout, refresh=True)
                    logger.info(f"已有APT实例 {existing_name} 删除完成")
                    return existing_name
            except Exception as e:
                logger.warning(f"检查/删除已有APT实例时出错: {e}")
                continue
        logger.info("APT 列表页无已有实例，无需清理")
        return None
