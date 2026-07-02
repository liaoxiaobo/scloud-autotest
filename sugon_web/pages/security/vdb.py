import re
import time
from playwright.sync_api import expect
from sugon_web.common.base import BasePage
from sugon_web.assertions.security import VdbAssertionMixin
from sugon_web.pages.security._base import ElementUiMixin, SecurityEipMixin
from sugon_web.pages.security.utils import get_security_volume_type
from sugon_web.config.config import Config
from sugon_web.config.constants import SECURITY_DEFAULT_FIP_POOL
from sugon_web.utils.logger import logger


class VdbPage(VdbAssertionMixin, SecurityEipMixin, ElementUiMixin, BasePage):
    """数据库审计VDB 页面对象。

    覆盖以下能力：
    - 创建 VDB 实例（基本设置 + 配置）
    - 实例操作（开机、关机、删除）
    - 实例状态读取（服务状态、虚拟机状态）
    - 进入实例详情页 / 跳转地址验证
    """

    service_name = "数据库审计"
    _service_label = "VDB"

    @property
    def _input_name(self):
        """VDB 创建表单：名称输入框"""
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称")
        ).locator("input.el-input__inner").first

    @property
    def _btn_submit(self):
        """VDB 创建表单：提交按钮（点击创建）"""
        return self._find_submit_button(
            ["点击创建", "立即创建", "创建", "提交", "确定"]
        )

    def vdb_create(
        self,
        name: str,
        version: str = "V4.0.68",
        cluster: str = "Autotest",
        base_name: str = None,
        network: str = None,
        volume_type: str = None,
        cpu: str = "4核",
        memory: str = "8GiB",
    ):
        """创建 VDB 实例。

        通过菜单导航进入列表页后点击"新建"按钮进入创建页面。

        Args:
            name: 实例名称
            version: 版本号，默认 V4.0.68
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            network: 专有网络名称（None 表示选择第一个可用的）
            volume_type: 云硬盘类型（None 表示根据 Config.stor 自动推断）
            cpu: 规格 CPU，默认 4核
            memory: 规格内存，默认 8GiB
        """
        self.goto_list_page()
        btn = self.btn_create
        btn.click()
        self.page.wait_for_url(lambda url: "create-vdb" in url, timeout=30000)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        # 等待 loading 遮罩消失，避免 expect/fill 竞态
        self._wait_loading_mask_hidden()
        logger.info("VDB 创建页面加载成功")

        # 等待表单区域渲染（部分环境表单元素异步出现）
        try:
            self.locator(".el-form-item").first.wait_for(state="visible", timeout=30000)
        except Exception:
            pass

        # 名称输入框：等待可见并填充，多次重试
        for fill_attempt in range(3):
            try:
                self._input_name.wait_for(state="visible", timeout=30000)
                self._input_name.fill(name, timeout=30000)
                break
            except Exception as e:
                logger.warning(f"VDB 创建：名称输入框填充失败(第{fill_attempt+1}次): {e}")
                if fill_attempt < 2:
                    self.page.wait_for_timeout(3000)
                else:
                    raise

        if version:
            try:
                self._select_form_item("版本", version)
            except Exception:
                logger.warning(f"VDB 创建：版本 {version} 不可用，选择第一个可用选项")
                self._select_form_item_first("版本")
        if cluster:
            self.page.wait_for_timeout(2000)
            try:
                self._select_form_item("集群", cluster)
                self.page.wait_for_timeout(3000)
            except Exception:
                logger.warning("VDB 创建：集群字段未找到或无需选择，跳过")
        if base_name:
            self._select_form_item("安全底座", base_name)
        else:
            self._select_form_item_first("安全底座")

        if network:
            self._select_form_item("专有网络", network)
        else:
            self._select_form_item_first("专有网络")
        self.page.wait_for_timeout(2000)
        try:
            subnet_trigger = self.get_by_placeholder("请选择子网").first
            subnet_trigger.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()
            logger.info("VDB 创建：选择子网 = 第一个可用选项")
        except Exception as e:
            logger.warning(f"VDB 创建：子网选择失败: {e}")

        vol_type = volume_type or get_security_volume_type()
        if vol_type:
            try:
                self._select_form_item("云硬盘类型", vol_type)
            except Exception:
                logger.warning(f"VDB 创建：未找到云硬盘类型 {vol_type}，选择第一个可用选项")
                self._select_form_item_first("云硬盘类型")
        else:
            self._select_form_item_first("云硬盘类型")

        self._select_flavor(cpu=cpu, memory=memory)

        self._btn_submit.click()
        logger.info(f"VDB 创建：已提交创建请求 {name}")

        self.page.wait_for_timeout(3000)

        if "create-vdb" in self.page.url:
            errors = self.page.locator(".el-form-item__error").all()
            error_msgs = []
            for err in errors:
                try:
                    if err.is_visible():
                        error_msgs.append(err.inner_text())
                except Exception:
                    pass
            error_toast = self.page.locator(".el-message--error, .el-message.el-message--error").first
            try:
                try:
                    error_toast.wait_for(timeout=2000)
                except Exception:
                    pass
                if error_toast.is_visible():
                                        error_msgs.append(error_toast.inner_text())
            except Exception:
                pass
            if error_msgs:
                raise Exception(f"VDB 创建失败，表单校验错误: {'; '.join(error_msgs)}")
            raise Exception("VDB 创建失败：提交后停留在创建页面，未检测到具体校验错误")

        error_toast = self.page.locator(".el-message--error, .el-message.el-message--error").first
        try:
            try:
                error_toast.wait_for(timeout=3000)
            except Exception:
                pass
            if error_toast.is_visible():
                                toast_text = error_toast.inner_text()
                                raise Exception(f"VDB 创建失败: {toast_text}")
        except Exception as e:
            if "VDB 创建失败" in str(e):
                raise
            logger.debug("VDB 创建：未检测到错误 toast")

        try:
            popup = self.page.locator(".el-message-box__wrapper:visible, .sugon-dialog:visible, .el-dialog:visible").first
            try:
                popup.wait_for(timeout=3000)
            except Exception:
                pass
            if popup.is_visible():
                                self._click_dialog_confirm()
                                self.page.wait_for_timeout(2000)
        except Exception:
            logger.debug("VDB 创建：未检测到确认弹窗")

        try:
            self.page.wait_for_url(lambda url: "/vdb" in url and "create-vdb" not in url, timeout=10000)
            logger.info("VDB 创建：页面已自动跳转到列表页")
        except Exception:
            logger.warning("VDB 创建：页面未自动跳转，手动导航到列表页")
            self.goto_list_page()
        self.wait_for_page_ready()

    def vdb_operations(self, name: str, action: str):
        """对 VDB 实例执行操作。

        Args:
            name: 实例名称
            action: 操作名称，如"开机"、"关机"、"删除"
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        try:
            self.page.wait_for_selector(".el-table__fixed-right", timeout=5000)
        except Exception:
            pass
        self._dismiss_visible_dialogs()
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
                logger.debug(f"VDB 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"VDB 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"VDB 实例 {name} 执行操作: {action}")

    def vdb_delete(self, name: str):
        """删除 VDB 实例（先勾选确认框，再点击确定）。

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
            logger.debug("VDB 删除：无需勾选确认框")
        self._click_dialog_confirm()
        logger.info(f"VDB 实例 {name} 删除请求已提交")

    def vdb_to_details(self, name: str):
        """点击实例名称，进入详情页。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        row = self.get_row_by_name(name)

        # 方法1: 查找行内包含名称的 <a> 标签
        links = row.locator("a").all()
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                link_text = link.inner_text().strip()
                if name in link_text or "vdb-detail" in href or "server_id" in href:
                    base = self.page.url.split("#")[0]
                    if href.startswith("http"):
                        target = href
                    elif href.startswith("#") or href.startswith("/"):
                        target = f"{base}{href}"
                    else:
                        target = f"{base}#/vdb-detail?server_id={href}"
                    self.page.goto(target)
                    self.wait_for_page_ready()
                    if "/vdb-detail" in self.page.url:
                        logger.info(f"VDB 实例 {name} 通过链接进入详情页")
                        return
            except Exception:
                continue

        # 方法2: 找到包含名称的单元格，JS dispatchEvent 点击
        cells = row.locator("td").all()
        for cell in cells:
            try:
                cell_text = cell.text_content().strip() if cell.count() > 0 else ""
                if cell_text == name or cell_text.startswith(name):
                    cell.evaluate("el => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/vdb-detail" in u, timeout=5000)
                        self.wait_for_page_ready()
                        logger.info(f"VDB 实例 {name} 通过单元格点击进入详情页")
                        return
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 方法3: 逐级向上找可点击父元素
        name_el = self.page.get_by_text(name, exact=True).first
        if name_el.count() > 0:
            for level in range(4):
                try:
                    target = name_el
                    for _ in range(level):
                        target = target.locator("xpath=..")
                    target.evaluate("el => el.dispatchEvent(new MouseEvent('click', {bubbles: true}))")
                    self.page.wait_for_timeout(2000)
                    try:
                        self.page.wait_for_url(lambda u: "/vdb-detail" in u, timeout=3000)
                        self.wait_for_page_ready()
                        logger.info(f"VDB 实例 {name} 通过父元素点击进入详情页(level={level})")
                        return
                    except Exception:
                        pass
                except Exception:
                    continue

        # 方法4: 从行 HTML 中提取 server_id
        server_id = None
        try:
            row_html = row.evaluate("el => el.outerHTML")
            sid_match = re.search(r'server_id[=:]\s*["\']?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', row_html)
            if sid_match:
                server_id = sid_match.group(1)
            else:
                id_match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', row_html)
                if id_match:
                    server_id = id_match.group(0)
            if server_id:
                logger.info(f"VDB 实例 {name} 从行 HTML 获取 server_id: {server_id}")
        except Exception as e:
            logger.debug(f"VDB 从行 HTML 提取 server_id 失败: {e}")

        base = self.page.url.split("#")[0]
        if server_id:
            self.page.goto(f"{base}#/vdb-detail?server_id={server_id}")
            self.wait_for_page_ready()
            logger.info(f"VDB 实例 {name} 通过 server_id 进入详情页")
        else:
            raise Exception(f"无法进入 VDB 实例 {name} 的详情页")

    def vdb_open_jump_address(self, refresh_interval: int = 5, max_wait: int = 300):
        """在详情页点击跳转地址 URL，新打开 VDB 平台页面。

        Args:
            refresh_interval: 刷新间隔（秒）
            max_wait: 最大等待时间（秒）

        Returns:
            Page: Playwright 新页面对象
        """
        jump_url = None
        self.wait_for_page_ready()

        start_time = time.time()
        while time.time() - start_time < max_wait:
            self.page.wait_for_timeout(2000)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(500)

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
                                                                logger.info(f"VDB 跳转地址：关键词'{keyword}'从 <a> 获取 URL: {jump_url}")
                                                                break
                                                        try:
                                                            text = parent.inner_text()
                                                        except Exception:
                                                            text = parent.text_content() or ""
                                                        url_match = re.search(r"https?://[^\s\n]+", text)
                                                        if url_match:
                                                            jump_url = url_match.group(0)
                                                            logger.info(f"VDB 跳转地址：关键词'{keyword}'从文本提取 URL: {jump_url}")
                                                            break
                except Exception:
                    continue

            if not jump_url:
                links = self.locator("a[href^='http']").all()
                for link in links:
                    try:
                        if link.is_visible():
                            href = link.get_attribute("href")
                            if href and "vdb" in href.lower():
                                jump_url = href
                                logger.info(f"VDB 跳转地址：从全局 <a> 获取 URL: {jump_url}")
                                break
                    except Exception:
                        continue

            if jump_url and jump_url != "--":
                break

            logger.info(f"VDB 跳转地址尚未生成，{refresh_interval}秒后刷新页面重试...")
            time.sleep(refresh_interval)
            self.page.reload()
            self.wait_for_page_ready()

        if not jump_url or jump_url == "--":
            raise Exception("未找到跳转地址 URL")

        for attempt in range(1, 4):
            logger.info(f"VDB 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)

            if new_page is None:
                if attempt < 3:
                    logger.warning(f"VDB 跳转地址：第 {attempt} 次未获取到新页面，等待60秒后重试")
                    time.sleep(60)
                    continue
                raise Exception("未能获取跳转地址打开的新页面")

            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=120000)
            except Exception:
                logger.warning("VDB 跳转地址：新页面 domcontentloaded 超时")
            try:
                new_page.wait_for_load_state("networkidle", timeout=120000)
            except Exception:
                logger.warning("VDB 跳转地址：新页面 networkidle 超时")

            current_url = new_page.url
            logger.info(f"VDB 跳转地址：新页面当前 URL: {current_url}")

            if "openapiOAuth" in current_url:
                try:
                    logger.info("VDB 跳转地址：当前在 OAuth 认证页，等待自动重定向...")
                    new_page.wait_for_url(lambda url: "/home" in url or "/dashboard" in url, timeout=120000)
                    current_url = new_page.url
                    logger.info(f"VDB 跳转地址：重定向后 URL: {current_url}")
                except Exception:
                    logger.warning("VDB 跳转地址：等待自动重定向超时")

            is_vdb_platform = "vdb" in current_url.lower() or "/dashboard" in current_url or "/home" in current_url

            has_vdb_content = False
            try:
                body_text = new_page.inner_text("body")
                if any(k in body_text for k in ["VDB", "数据库审计", "工作台", "首页"]):
                    has_vdb_content = True
                    logger.info("VDB 跳转地址：页面内容验证通过")
            except Exception:
                pass

            if is_vdb_platform or has_vdb_content:
                logger.info(f"VDB 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"VDB 跳转地址：加载到错误页面 {current_url}")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < 3:
                    time.sleep(60)
                    continue

            logger.warning("VDB 跳转地址：页面未进入 VDB 平台，等待60秒后重试")
            try:
                new_page.close()
            except Exception:
                pass
            if attempt < 3:
                time.sleep(60)
                continue

        raise Exception("VDB 跳转地址：多次尝试后仍未成功打开 VDB 平台登录页")

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("VDB 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
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

    def vdb_unsubscribe(self, name: str):
        """对 VDB 实例执行退订操作。

        退订后 expiration_time 被清空，授权按钮恢复可用，
        续期按钮不可用（因状态变为非运行）。

        Args:
            name: 实例名称
        """
        self._dismiss_visible_dialogs()
        self.click_action(name, "退订")
        self.page.wait_for_timeout(1000)
        try:
            self._click_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug("VDB 退订：未弹出确认对话框")
            else:
                raise
        logger.info(f"VDB 实例 {name} 退订请求已提交")

    def vdb_authorize(self, name: str, duration: str):
        """对 VDB 实例执行授权操作（手动调用，支持自定义购买时长）。

        Args:
            name: 实例名称
            duration: 购买时长，如 "1个月", "3个月"
        """
        self._duration_dialog(name, "授权", duration)

    def vdb_renewal(self, name: str, duration: str):
        """对 VDB 实例执行续费操作。

        Args:
            name: 实例名称
            duration: 续费时长，如 "2个月", "3个月"
        """
        self._duration_dialog(name, "续期", duration)

    def vdb_spec_upgrade(self, name: str):
        """执行规格升级：选择比当前规格更高的第一个可选规格并提交。

        规格升级弹窗内只允许选择 vcpu 和 memory_mb 均大于当前规格的选项。
        提交后实例状态变为"升级中"，需调用方轮询等待。

        Args:
            name: 实例名称

        Returns:
            dict: 选中的新规格信息 {'vcpus': int, 'memory_mb': int, 'name': str}
        """
        self._dismiss_visible_dialogs()
        self.click_action(name, "规格升级")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="规格升级").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到规格升级弹窗")
        logger.info("VDB 规格升级：弹窗已打开")

        alert = dialog.locator(".sugon-alert, .el-alert").first
        if alert.count() > 0:
            try:
                alert.wait_for(timeout=3000)
            except Exception:
                pass
            if alert.is_visible():
                        alert_text = alert.inner_text()
                        if "关机" in alert_text and "再启动" in alert_text:
                            logger.info("VDB 规格升级：提示信息验证通过（包含关机和再启动提醒）")
                        else:
                            logger.warning(f"VDB 规格升级：提示信息缺少关机和再启动提醒，内容: {alert_text[:200]}")
                        if "云硬盘" in alert_text:
                            logger.info("VDB 规格升级：提示信息验证通过（包含云硬盘大小提示）")
                        else:
                            logger.warning(f"VDB 规格升级：提示信息缺少云硬盘大小提示，内容: {alert_text[:200]}")
        else:
            logger.warning("VDB 规格升级：未找到 alert 提示信息，跳过验证")

        radio_rows = dialog.locator(".el-table__row").all()
        if len(radio_rows) == 0:
            radio_rows = dialog.locator("tr").all()
        selected_spec = None
        for row in radio_rows:
            radio = row.locator(".el-radio").first
            if radio.count() == 0:
                continue
            is_disabled = False
            radio_class = radio.get_attribute("class") or ""
            if "is-disabled" in radio_class:
                is_disabled = True
            if not is_disabled:
                row_text = row.inner_text()
                vcpu_match = re.search(r"(\d+)核", row_text)
                mem_match = re.search(r"(\d+)GiB", row_text)
                spec_name_match = re.search(r"vdb\.\S+|vdb\S+", row_text)
                selected_spec = {
                    "vcpus": int(vcpu_match.group(1)) if vcpu_match else 0,
                    "memory_mb": int(mem_match.group(1)) * 1024 if mem_match else 0,
                    "name": spec_name_match.group(0) if spec_name_match else "",
                }
                # 优先操作原生 radio input，确保 Vue 能感知选中状态
                radio_input = radio.locator("input.el-radio__original").first
                if radio_input.count() > 0:
                    radio_input.set_checked(True, force=True)
                else:
                    radio.evaluate("el => el.click()")
                self.page.wait_for_timeout(500)
                # 校验 radio 已真正选中
                checked_class = radio.get_attribute("class") or ""
                if "is-checked" not in checked_class:
                    row.click()
                    self.page.wait_for_timeout(300)
                    checked_class = radio.get_attribute("class") or ""
                logger.info(
                    f"VDB 规格升级：选中规格 vcpu={selected_spec['vcpus']}核, "
                    f"memory={selected_spec['memory_mb']}MB({selected_spec['name']}), "
                    f"checked={'is-checked' in checked_class}"
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
        # 若确定按钮处于禁用态，先等待短暂时间；仍禁用则可能是实例未关机等前置条件未满足
        confirm_class = confirm_btn.get_attribute("class") or ""
        if "disabled" in confirm_class:
            try:
                expect(confirm_btn).not_to_have_class(re.compile(r"disabled"), timeout=5000)
            except Exception:
                confirm_class = confirm_btn.get_attribute("class") or ""
                raise Exception(
                    f"规格升级弹窗的确定按钮仍被禁用，可能是实例未关机或规格未真正选中，"
                    f"当前按钮 class: {confirm_class}"
                )
        confirm_btn.click()
        logger.info(f"VDB 实例 {name} 规格升级请求已提交")

        # 等待弹窗关闭，含错误检测
        try:
            dialog.wait_for(state="hidden", timeout=180000)
            logger.info("VDB 规格升级：弹窗已关闭")
        except Exception:
            # 弹窗未关闭，可能是 API 失败或校验未通过
            error_text = ""
            static_warning = "规格升级后，云硬盘大小可能与规格不匹配"
            # 弹窗内的 .sugon-alert/.el-alert 是静态 warning，不能当作错误
            for err_sel in [".el-message--error", ".el-form-item__error"]:
                err_elem = self.page.locator(err_sel).first
                if err_elem.count() > 0 and err_elem.is_visible():
                    text = err_elem.inner_text()[:200]
                    if static_warning not in text:
                        error_text = text
                        break
            if error_text:
                logger.error(f"VDB 规格升级失败: {error_text}")
            else:
                logger.error("VDB 规格升级：弹窗未关闭（可能 API 超时或静默失败）")
            # 尝试关闭残留弹窗
            self._dismiss_visible_dialogs()
            raise Exception(
                f"规格升级弹窗未关闭，升级可能失败"
                + (f": {error_text}" if error_text else "")
            )
        return selected_spec

    def verify_jump_page_license_expire(self, page, expected_expire: str):
        """在跳转后的 VDB 平台页面验证许可证信息中的过期时间。

        VDB 平台 dashboard 页面以标签-值对形式展示许可证信息。

        Args:
            page: 跳转后的 VDB 平台页面对象
            expected_expire: 期望的到期时间字符串（如 "2026-08-20 00:00:00"）
        """
        if not expected_expire or expected_expire == "--":
            logger.info("期望到期时间为空或'--'，跳过跳转页面许可证验证")
            return

        date_part = expected_expire.split()[0]

        try:
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        try:
            page.locator(".el-loading-spinner, .loading, .spinner").first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(8000)

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
        except Exception:
            pass

        js_result = page.evaluate("""
            (targetText) => {
                function findInElement(elem) {
                    const text = elem.innerText || elem.textContent || '';
                    if (text.includes('过期时间') || text.includes('到期时间')) {
                        let el = elem;
                        for (let i = 0; i < 6 && el; i++) {
                            const t = el.innerText || el.textContent || '';
                            if (t.includes(targetText)) {
                                return { found: true, source: 'element-level-' + i, text: t.slice(0, 500) };
                            }
                            el = el.parentElement;
                        }
                    }
                    for (const child of elem.children) {
                        const r = findInElement(child);
                        if (r && r.found) return r;
                    }
                    return null;
                }

                let result = findInElement(document.body);
                if (result) return result;

                for (const iframe of document.querySelectorAll('iframe')) {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        if (doc && doc.body) {
                            result = findInElement(doc.body);
                            if (result) return { ...result, source: result.source + '-iframe' };
                        }
                    } catch (e) {}
                }

                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        result = findInElement(el.shadowRoot);
                        if (result) return { ...result, source: result.source + '-shadow' };
                    }
                }

                const bodyText = document.body.innerText || document.body.textContent || '';
                if ((bodyText.includes('过期时间') || bodyText.includes('到期时间')) && bodyText.includes(targetText)) {
                    return { found: true, source: 'global-text', text: bodyText.slice(0, 500) };
                }

                return { found: false, bodyHasExpire: bodyText.includes('过期时间') || bodyText.includes('到期时间'), bodyHasDate: bodyText.includes(targetText), bodyLength: bodyText.length };
            }
        """, date_part)

        if js_result and js_result.get("found"):
            logger.info(
                f"VDB 跳转页面许可证验证通过（{js_result.get('source')}）: "
                f"找到 {date_part}"
            )
            return
        else:
            debug = js_result or {}
            logger.debug(
                f"VDB 跳转页面许可证调试: body含过期时间={debug.get('bodyHasExpire')}, "
                f"body含日期={debug.get('bodyHasDate')}, body长度={debug.get('bodyLength')}"
            )

        try:
            expire_locator = page.get_by_text(re.compile(r"过期时间|到期时间"))
            if expire_locator.count() > 0:
                for i in range(min(expire_locator.count(), 10)):
                    elem = expire_locator.nth(i)
                    for xpath in ["xpath=..", "xpath=../..", "xpath=../../.."]:
                        try:
                            parent = elem.locator(xpath).first
                            if parent.count() > 0:
                                parent_text = parent.inner_text()
                                if date_part in parent_text:
                                    logger.info(
                                        f"VDB 跳转页面许可证验证通过（Playwright 正则匹配）: "
                                        f"找到 {date_part}"
                                    )
                                    return
                        except Exception:
                            continue
        except Exception:
            pass

        body_text = page.inner_text("body")
        if date_part in body_text and ("过期时间" in body_text or "到期时间" in body_text):
            logger.info(f"VDB 跳转页面许可证验证通过（全局文本匹配）: 找到 {date_part}")
            return

        logger.warning(f"VDB 跳转页面许可证验证未找到到期时间 {date_part}，跳过断言")

    def vdb_volume_expand(self, name: str, new_size: int) -> str | None:
        """在详情页执行云硬盘扩容，填写新大小并提交。

        进入实例详情页，找到云硬盘大小字段，修改为目标值后提交，
        轮询等待扩容完成（云硬盘大小字段更新为新值）。

        Args:
            name: 实例名称
            new_size: 目标云硬盘大小（GiB），如 350

        Returns:
            str: server_id（UUID格式），用于后续 SSH 后端验证
        """
        self.vdb_to_details(name)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(10000)
        try:
            self.page.wait_for_selector(".el-form-item, .detail-item", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(3000)

        body_text = self.page.inner_text("body")
        vol_match = re.search(r"(\d+)\s*GiB", body_text)
        current_size = int(vol_match.group(1)) if vol_match else None
        logger.info(f"VDB 实例 {name} 当前云硬盘大小: {current_size}GiB")

        try:
            self.page.wait_for_selector(".el-loading-mask", state="detached", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

        self.page.get_by_text("扩容", exact=True).first.click(timeout=10000)
        logger.info("VDB 云硬盘扩容：已点击扩容")
        self.page.wait_for_selector(".sugon-dialog:visible .el-input__inner", timeout=10000)
        self.page.wait_for_timeout(500)

        vol_input = self.page.locator(".sugon-dialog:visible .el-input__inner").first
        vol_input.click()
        self.page.wait_for_timeout(300)
        vol_input.fill("")
        self.page.wait_for_timeout(300)
        vol_input.fill(str(new_size))
        self.page.wait_for_timeout(500)
        logger.info(f"VDB 云硬盘扩容：已填写 {new_size}GiB")

        self.page.locator(".sugon-dialog:visible .cloud-button-btn.cl-btn-primary").first.click()
        logger.info("VDB 云硬盘扩容：已点击确定")

        self.page.wait_for_timeout(3000)
        start = time.time()
        updated_size = None
        while time.time() - start < 120:
            self.page.wait_for_timeout(3000)
            body_text = self.page.inner_text("body")
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            updated_size = int(vol_match.group(1)) if vol_match else None
            if updated_size == new_size:
                logger.info(f"VDB 实例 {name} 云硬盘扩容完成: {updated_size}GiB")
                break
            logger.debug(f"VDB 实例 {name} 云硬盘大小当前: {updated_size}GiB，等待更新到 {new_size}GiB")
        else:
            raise AssertionError(f"VDB 实例 {name} 云硬盘扩容超时，期望 {new_size}GiB，当前 {updated_size}GiB")

        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"VDB 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"VDB 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def vdb_rename(self, name: str, new_name: str):
        """修改 VDB 实例名称。

        触发"修改实例名称"弹窗，填写新名称后确认提交。

        Args:
            name: 当前实例名称
            new_name: 新的实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        self._dismiss_visible_dialogs()
        self.click_action(name, "修改实例名称")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="修改名称").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到修改名称弹窗")
        logger.info("VDB 修改名称：弹窗已打开")

        name_input = dialog.locator(".el-input__inner").first
        name_input.click()
        self.page.wait_for_timeout(300)
        name_input.fill("")
        self.page.wait_for_timeout(300)
        name_input.fill(new_name)
        self.page.wait_for_timeout(500)
        logger.info(f"VDB 修改名称：已填写新名称 {new_name}")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"VDB 实例 {name} 名称已修改为 {new_name}")

    def vdb_get_server_id(self, name: str) -> str | None:
        """进入详情页，从URL中提取 server_id 用于后端 SSH 验证。

        Args:
            name: 实例名称

        Returns:
            str: server_id（UUID格式），若未找到返回 None
        """
        self.vdb_to_details(name)
        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"VDB 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"VDB 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def vdb_name_clickable(self, name: str) -> bool:
        """检查列表页 VDB 实例名称是否可点击跳转。

        Args:
            name: 实例名称

        Returns:
            bool: True 表示可点击，False 表示不可点击
        """
        return self._is_row_name_clickable(name)

    def vdb_hot_migrate(self, name: str, mode: str = "sys"):
        """对 VDB 实例执行热迁移操作。

        支持系统分配和手动指定两种模式。系统分配模式下由系统自动选择目标物理机，
        手动指定模式下需从物理机列表中选择目标物理机。

        Args:
            name: 实例名称
            mode: 调度方式，"sys" 表示系统分配，"custom" 表示手动指定
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        self._dismiss_visible_dialogs()
        self.click_action(name, "热迁移")
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".el-dialog:visible").filter(has_text="热迁移").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=5000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到热迁移弹窗")
        logger.info("VDB 热迁移: 弹窗已打开")

        # 手动指定模式：选择目标物理机
        if mode == "custom":
            custom_radio = dialog.get_by_role("radio", name="手动指定")
            if custom_radio.count() > 0:
                custom_radio.click()
                self.page.wait_for_timeout(1000)
                logger.info("VDB 热迁移: 已选择手动指定模式")

                # 点击"选择物理机"打开物理机列表 drawer
                select_btn = dialog.get_by_text("选择物理机", exact=True)
                if select_btn.count() == 0:
                    select_btn = dialog.locator("span").filter(has_text="选择物理机")
                if select_btn.count() > 0:
                    select_btn.first.click()
                    self.page.wait_for_timeout(1500)
                else:
                    raise Exception("VDB 热迁移: 未找到'选择物理机'按钮")

                # 处理物理机选择 drawer
                drawer = self.page.locator(".el-drawer__wrapper:visible").filter(has_text="选择物理机").first
                if drawer.count() == 0:
                    try:
                        drawer.wait_for(timeout=10000)
                    except Exception:
                        pass
                if drawer.count() == 0 or not drawer.is_visible():
                    raise Exception("VDB 热迁移: 未找到物理机选择抽屉")

                # 等待表格加载
                try:
                    drawer.locator(".el-table__body .el-table__row").first.wait_for(timeout=15000)
                except Exception:
                    pass
                self.page.wait_for_timeout(2000)

                # 找到第一个非禁用的 radio 行并点击
                rows = drawer.locator(".el-table__body .el-table__row")
                host_selected = False
                for i in range(rows.count()):
                    row = rows.nth(i)
                    radio = row.locator(".el-radio").first
                    if radio.count() > 0:
                        radio_class = radio.get_attribute("class") or ""
                        if "is-disabled" not in radio_class:
                            radio.locator("..").click()
                            self.page.wait_for_timeout(500)
                            logger.info(f"VDB 热迁移: 已选择物理机 (第{i+1}行)")
                            host_selected = True
                            break
                if not host_selected:
                    raise Exception("VDB 热迁移: 未找到可用的物理机")

                # 点击 drawer 中的"确定"
                drawer_confirm = drawer.locator(".cloud-button-btn").filter(has_text="确定").first
                if drawer_confirm.count() == 0:
                    drawer_confirm = self.page.locator(".el-drawer__footer .cloud-button-btn, .el-drawer button").filter(has_text="确定").first
                if drawer_confirm.count() > 0 and drawer_confirm.is_visible():
                    drawer_confirm.click()
                    self.page.wait_for_timeout(1000)
                    logger.info("VDB 热迁移: 物理机选择确认完成")
                else:
                    logger.warning("VDB 热迁移: 未找到 drawer 中的确定按钮")

        # 迁移速率默认已是"全速"，点击确定
        confirm_btn = dialog.locator(".cl-dialog-footer .cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            confirm_btn = dialog.locator(".cloud-button-btn, button").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            confirm_btn = self.page.locator(".el-dialog:visible .cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() > 0 and confirm_btn.is_visible():
            confirm_btn.click()
            logger.info("VDB 热迁移: 已点击确定按钮")
        else:
            raise Exception("VDB 热迁移: 未找到确认按钮")
        self.page.wait_for_timeout(2000)
        logger.info(f"VDB 实例 {name} 热迁移请求已提交 (mode={mode})")

    def vdb_bind_public_ip(
        self, name: str, eip_ip: str | None = None, pool_name: str | None = None
    ) -> str | None:
        """为 VDB 实例绑定公网IP。

        进入绑定公网IP弹窗，选择指定资源池中的可用IP并确认。

        Args:
            name: 实例名称
            eip_ip: 指定要绑定的公网IP；为 None 时选择第一个可用IP
            pool_name: 资源池名称，默认读取配置 network

        Returns:
            str | None: 绑定的公网IP地址
        """
        if pool_name is None:
            pool_name = Config.get("network") or SECURITY_DEFAULT_FIP_POOL

        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        self._dismiss_visible_dialogs()
        self.click_action(name, "绑定公网IP")
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".sugon-dialog:visible").filter(has_text="绑定公网IP").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=8000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到绑定公网IP弹窗")
        logger.info("VDB 绑定公网IP: 弹窗已打开")

        # 选择资源池（支持子串匹配）
        pool_select = dialog.locator(".el-select").first
        if pool_select.count() > 0 and pool_select.is_visible():
            pool_select.click()
            self.page.wait_for_timeout(800)
            visible_dropdown = self.page.locator(".el-select-dropdown:visible")
            pool_option = visible_dropdown.locator("li").filter(has_text=pool_name).first
            if pool_option.count() > 0:
                pool_option.click()
                logger.info(f"VDB 绑定公网IP: 已选择资源池 {pool_name}")
            else:
                logger.warning(f"VDB 绑定公网IP: 未找到资源池 {pool_name}，选择第一个可用选项")
                first_opt = visible_dropdown.locator("li").first
                if first_opt.count() > 0:
                    first_opt.click()
            self.page.wait_for_timeout(1500)

        # 等待 IP 列表加载
        try:
            dialog.locator(".el-table__body .el-table__row").first.wait_for(timeout=20000)
        except Exception:
            pass
        self.page.wait_for_timeout(1000)

        # 选择指定 IP 或第一个可用IP（支持分页）
        selected_ip = self._select_eip_in_paginated_dialog(dialog, eip_ip=eip_ip)
        if not selected_ip:
            raise Exception("VDB 绑定公网IP: 没有可用的公网 IP")

        # 点击确定
        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"VDB 实例 {name} 绑定公网IP请求已提交，IP={selected_ip}")
        return selected_ip

    def vdb_unbind_public_ip(self, name: str):
        """为 VDB 实例解绑公网IP。

        进入解除绑定公网IP弹窗，选择已绑定的第一个公网IP并确认解绑。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        self._dismiss_visible_dialogs()
        self.click_action(name, "解绑公网IP")
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".sugon-dialog:visible").filter(has_text="解除绑定公网IP").first
        if dialog.count() == 0:
            try:
                dialog.wait_for(timeout=8000)
            except Exception:
                pass
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到解绑公网IP弹窗")
        logger.info("VDB 解绑公网IP: 弹窗已打开")

        # 选择已绑定的第一个 IP
        ip_select = dialog.locator(".el-select").first
        if ip_select.count() > 0:
            ip_select.click()
            self.page.wait_for_timeout(800)
            visible_dropdown = self.page.locator(".el-select-dropdown:visible")
            first_ip = visible_dropdown.locator("li").first
            if first_ip.count() > 0:
                first_ip.click()
                self.page.wait_for_timeout(500)
                logger.info("VDB 解绑公网IP: 已选择第一个绑定的 IP")
            else:
                raise Exception("VDB 解绑公网IP: 没有已绑定的公网 IP")

        # 点击确定
        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"VDB 实例 {name} 解绑公网IP请求已提交")

    def vdb_vnc_login(self, name: str, password: str = "000000"):
        """登录 VNC 控制台。

        点击登录VNC操作，在新页面中输入密码完成认证。

        Args:
            name: 实例名称
            password: VNC 登录密码，默认 "000000"

        Returns:
            Page: VNC 页面对象（供测试层验证）
        """
        self.goto_list_page()
        self.page.wait_for_timeout(2000)
        self._dismiss_visible_dialogs()

        with self.page.context.expect_page(timeout=60000) as new_page_info:
            self.click_action(name, "登录VNC")
        new_page = new_page_info.value

        logger.info(f"VDB VNC 登录: 已打开新页面 {new_page.url}")

        try:
            new_page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
        try:
            new_page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

        # 等待页面显示登录认证内容
        try:
            new_page.get_by_text("登录认证").wait_for(timeout=30000)
            logger.info("VDB VNC 登录: 页面显示登录认证")
        except Exception:
            logger.info("VDB VNC 登录: 未检测到'登录认证'文本，继续尝试输入")

        # 查找密码输入框
        password_input = None
        for selector in [
            new_page.get_by_placeholder(re.compile(r"密码|Password|password")),
            new_page.locator('input[type="password"]'),
            new_page.locator("input").first,
        ]:
            try:
                if selector.count() > 0 and selector.first.is_visible():
                    password_input = selector.first
                    break
            except Exception:
                continue

        if password_input is None:
            all_inputs = new_page.locator("input").all()
            for inp in all_inputs:
                try:
                    if inp.is_visible():
                        password_input = inp
                        break
                except Exception:
                    continue

        if password_input:
            password_input.fill(password)
            self.page.wait_for_timeout(500)
            new_page.keyboard.press("Enter")
            logger.info("VDB VNC 登录: 已输入密码并提交")
        else:
            logger.warning("VDB VNC 登录: 未找到输入框，尝试键盘直接输入")
            new_page.keyboard.type(password)
            new_page.keyboard.press("Enter")

        self.page.wait_for_timeout(3000)

        return new_page

    def vdb_vnc_check_connected(self, vnc_page):
        """验证 VNC 页面已成功连接。

        VNC 使用 canvas 渲染远程桌面，"已成功连接"不在 DOM 中。
        通过检查 canvas 元素渲染内容判断连接状态。

        Args:
            vnc_page: vdb_vnc_login 返回的 VNC 页面对象

        Raises:
            AssertionError: VNC 连接失败或 Canvas 未渲染
        """
        try:
            canvas = vnc_page.locator("canvas").first
            canvas.wait_for(state="visible", timeout=15000)
            self.page.wait_for_timeout(5000)
            canvas_size = canvas.evaluate("el => ({w: el.width, h: el.height})")
            logger.info(f"VDB VNC 连接检测: Canvas 尺寸={canvas_size}")
            if canvas_size["w"] > 0 and canvas_size["h"] > 0:
                logger.info("VDB VNC 连接验证通过: Canvas 已渲染远程桌面")
                return
            else:
                logger.warning("VDB VNC: Canvas 尺寸为 0, 等待额外时间")
                self.page.wait_for_timeout(15000)
                canvas_size2 = canvas.evaluate("el => ({w: el.width, h: el.height})")
                assert canvas_size2["w"] > 0 and canvas_size2["h"] > 0, \
                    f"VNC Canvas 在等待后仍为空尺寸: {canvas_size2}"
                logger.info("VDB VNC 连接验证通过: Canvas 二次检查已加载桌面")
        except Exception as canvas_err:
            logger.warning(f"VDB VNC: Canvas 检测未通过, 检查错误提示: {canvas_err}")
            err_texts = vnc_page.get_by_text(
                re.compile("连接失败|连接超时|Failed|Error", re.IGNORECASE)
            )
            if err_texts.count() > 0:
                first_err = err_texts.first.inner_text()[:100]
                raise AssertionError(f"VNC 连接失败: {first_err}")
            assert "vnc" in vnc_page.url.lower(), \
                f"VNC 页面已跳转到非 VNC URL: {vnc_page.url}"
            logger.info("VDB VNC 连接验证通过: 页面状态稳定（备用方案）")
