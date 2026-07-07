import re
import time

from playwright.sync_api import expect

from sugon_web.common.base import BasePage
from sugon_web.assertions.security import WafAssertionMixin
from sugon_web.config.constants import (
    SECURITY_CREATE_PATH_MAP,
    SECURITY_DEFAULT_FIP_POOL,
    SERVICE_PATH_MAP,
)
from sugon_web.pages.security._base import ElementUiMixin, SecurityEipMixin
from sugon_web.pages.security.utils import get_security_volume_type
from sugon_web.utils.logger import logger


class WafPage(WafAssertionMixin, SecurityEipMixin, ElementUiMixin, BasePage):
    """WEB应用防火墙WAF 页面对象。

    覆盖以下能力：
    - 创建 WAF 实例（基本设置 + 配置）
    - 实例操作（开机、关机、删除、退订）
    - 授权 / 续期
    - 规格升级
    - 云硬盘扩容
    - 修改实例名称
    - 进入实例详情页 / 跳转地址验证
    - 实例状态读取（服务状态、虚拟机状态）
    """

    service_name = "WEB应用防火墙"
    _service_label = "WAF"

    @property
    def _btn_submit(self):
        """WAF 创建表单：提交按钮（点击创建）"""
        return self._find_submit_button(
            ["点击创建", "创建", "提交", "确定"]
        )

    def _select_form_item(self, label: str, option: str):
        """选择表单下拉项；未找到指定项时回退到第一个可用项。"""
        return super()._select_form_item(label, option, fallback_first=True)

    def waf_create(
        self,
        name: str,
        version: str = "V4.0.68",
        cluster: str = "Autotest",
        base_name: str = None,
        network: str = None,
        subnet: str = None,
        volume_type: str = None,
        cpu: str = "4核",
        memory: str = "8GiB",
    ):
        """创建 WAF 实例。

        导航到创建页面，填写基本设置（名称、版本、集群、安全底座）和配置
        （专有网络、子网、云硬盘类型、规格），提交创建请求。

        Args:
            name: 实例名称
            version: 版本号，默认 V4.0.68
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            network: 专有网络名称（None 表示选择第一个可用的）
            subnet: 子网名称（None 表示选择第一个可用的）
            volume_type: 云硬盘类型（None 表示根据 Config.stor 自动推断）
            cpu: 规格 CPU，默认 4核
            memory: 规格内存，默认 8GiB
        """
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        create_url = f"{base_url}{SECURITY_CREATE_PATH_MAP[self.service_name]}"
        self.page.goto(create_url)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        self._wait_loading_mask_hidden()
        logger.info("WAF 创建页面加载成功")

        try:
            self._input_name.wait_for(state="visible", timeout=10000)
        except Exception:
            logger.warning("WAF 创建：名称输入框未立即可见，继续尝试填充")
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
            form_item.get_by_placeholder(re.compile(r"请选择")).first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        if network:
            self._select_form_item("专有网络", network)
        else:
            form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^专有网络"))
            form_item.get_by_placeholder("请选择网络").first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

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

        vol_type = volume_type or get_security_volume_type()
        try:
            self._select_form_item("云硬盘类型", vol_type)
        except Exception:
            logger.warning(f"WAF 创建：云硬盘类型 '{vol_type}' 不可用，选择第一个可用选项")
            form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^云硬盘类型"))
            form_item.get_by_placeholder(re.compile(r"请选择")).first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        self._select_flavor(cpu=cpu, memory=memory)

        self._btn_submit.click()
        logger.info(f"WAF 创建：已提交创建请求 {name}")

        try:
            self.page.wait_for_url(f"**{SERVICE_PATH_MAP[self.service_name]}", timeout=30000)
            logger.info(f"WAF 创建：页面已跳转回列表页 {self.page.url}")
        except Exception:
            logger.warning("WAF 创建：页面未自动跳转，手动返回列表页")
            self.goto_list_page()

    def waf_operations(self, name: str, action: str):
        """对 WAF 实例执行操作（开机、关机、删除等）。

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
            logger.warning(f"WAF 标准 click_action 失败: {e}，尝试 fallback 定位")
            row = self.get_row_by_name(name)
            btn = row.get_by_text(action, exact=False).first
            if btn.count() > 0:
                try:
                    btn.wait_for(timeout=2000)
                except Exception:
                    pass
                if btn.is_visible():
                    btn.click()
                    logger.info(f"WAF 操作 fallback: 直接点击行内 '{action}' 按钮")
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
                                            logger.info(f"WAF 操作 fallback: 点击'{more_text}'下拉菜单中的 '{action}'")
                                            break
                            else:
                                continue
                            break
                else:
                    raise Exception(f"WAF 操作 {action} 的 fallback 定位也失败了")
        try:
            self._click_dialog_confirm()
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug(f"WAF 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"WAF 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"WAF 实例 {name} 执行操作: {action}")

    def waf_delete(self, name: str):
        """删除 WAF 实例（先勾选确认框，再点击确定）。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        try:
            self.click_action(name, "删除")
        except Exception as e:
            logger.warning(f"WAF 标准 click_action 删除失败: {e}，尝试 fallback 定位")
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
                    raise Exception(f"WAF 删除 {name} 的 fallback 定位也失败了")

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
            logger.debug("WAF 删除：无需勾选确认框")
        self._click_dialog_confirm()
        logger.info(f"WAF 实例 {name} 删除请求已提交")

    def waf_unsubscribe(self, name: str, timeout: int = 120):
        """对 WAF 实例执行退订操作，并等待状态收敛到已退订/不可用。

        Args:
            name: 实例名称
            timeout: 状态收敛等待超时（秒），默认 120
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()
        self.click_action(name, "退订")
        self.page.wait_for_timeout(1000)
        try:
            self._click_dialog_confirm()
            logger.info(f"WAF 实例 {name} 退订确认已点击")
        except Exception as e:
            if "未找到弹窗确认按钮" in str(e):
                logger.debug("WAF 退订：未弹出确认对话框")
            else:
                raise

        # 等待退订弹窗关闭
        try:
            self.page.locator(".sugon-dialog:visible, .el-dialog:visible").first.wait_for(
                state="hidden", timeout=15000
            )
        except Exception:
            self._dismiss_visible_dialogs()

        # 轮询列表状态，直到服务状态变为 已退订/不可用
        start_time = time.time()
        last_status = ""
        while time.time() - start_time < timeout:
            try:
                self.goto_list_page()
                row_data = self.get_row_data(name)
                last_status = row_data.get("服务状态", "")
                if "已退订" in last_status or "不可用" in last_status:
                    logger.info(f"WAF 实例 {name} 退订后状态收敛: {last_status}")
                    return row_data
            except Exception as e:
                logger.debug(f"WAF 退订后读取状态失败: {e}")
            time.sleep(5)
        raise AssertionError(
            f"WAF 实例 {name} 退订后状态未收敛到已退订/不可用，当前服务状态: {last_status}"
        )

    def waf_authorize(self, name: str, duration: str):
        """对 WAF 实例执行授权操作。

        Args:
            name: 实例名称
            duration: 购买时长，如 "3个月"
        """
        self._duration_dialog(name, "授权", duration)

    def waf_renewal(self, name: str, duration: str):
        """对 WAF 实例执行续期操作。

        Args:
            name: 实例名称
            duration: 续费时长，如 "2个月"
        """
        self._duration_dialog(name, "续期", duration)

    def waf_rename(self, name: str, new_name: str):
        """修改 WAF 实例名称。

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
        logger.info("WAF 修改名称：弹窗已打开")

        name_input = dialog.locator(".el-input__inner").first
        name_input.click()
        self.page.wait_for_timeout(300)
        name_input.fill("")
        self.page.wait_for_timeout(300)
        name_input.fill(new_name)
        self.page.wait_for_timeout(500)
        logger.info(f"WAF 修改名称：已填写新名称 {new_name}")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"WAF 实例 {name} 名称已修改为 {new_name}")

    def waf_to_details(self, name: str):
        """进入 WAF 实例详情页。

        通过点击列表页实例名称进入详情页。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        row = self.get_row_by_name(name)
        found = False
        # 策略1: 查找 standard link elements
        for link_sel in ["a", "span.link", "span[class*='link']", "td div.cell"]:
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
            # 策略2: 直接点击名称所在cell区域
            # 兼容 div.overflow-ellipsis（CSS overflow:hidden 使元素对 Playwright 不可见）
            try:
                text_loc = row.get_by_text(name, exact=True).first
                if text_loc.count() > 0:
                    try:
                        text_loc.scroll_into_view_if_needed()
                        text_loc.click(timeout=10000)
                    except Exception:
                        self.logger.info(f"WAF 实例 {name} 名称元素普通点击不可见，尝试 force click")
                        text_loc.click(force=True)
                    self.page.wait_for_timeout(5000)
                    if "waf-detail" in self.page.url or "server_id" in self.page.url:
                        found = True
            except Exception:
                pass

        if not found:
            # 策略3: 尝试从 row 中提取 server_id 构造正确的详情页URL
            base = self.page.url.split("#")[0]
            self.page.goto(f"{base}#/waf-detail?id=0&server_id=0")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(3000)

        self.wait_for_detail_page_ready()
        logger.info(f"WAF 实例 {name} 进入详情页，URL: {self.page.url}")

    def _extract_jump_url(self) -> str | None:
        """从当前详情页提取跳转地址 URL。"""
        self.wait_for_detail_page_ready()
        self.page.wait_for_timeout(3000)

        body_text = self.page.inner_text("body")

        # 策略1: 搜索"跳转地址"附近的链接
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

        # 策略2: 搜索所有可见的http链接
        links = self.locator("a[href^='http']").all()
        for link in links:
            try:
                if link.is_visible():
                    href = link.get_attribute("href")
                    if href and ("openapiOAuth" in href or "172.22" in href):
                        return href
            except Exception:
                continue

        # 策略3: 从body文本中提取URL
        urls = re.findall(r"https?://[^\s\n]+", body_text)
        for url in urls:
            if "172.22" in url or ":30000" in url or "openapiOAuth" in url:
                return url

        logger.info(f"WAF 跳转地址提取失败，body 文本含跳转地址: {'跳转地址' in body_text}")
        return None

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("WAF 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
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
        logger.info("WAF 跳转地址：重新进入详情页以获取新的跳转链接...")
        name = None
        url = self.page.url
        name_match = re.search(r"server_name=([^&]+)", url)
        if name_match:
            from urllib.parse import unquote
            name = unquote(name_match.group(1))

        self.goto_list_page()
        self.page.wait_for_timeout(5000)

        if name:
            self.waf_to_details(name)
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
                logger.info(f"WAF 跳转地址：重进详情页后提取到 URL: {new_url}")
                return new_url
        logger.warning("WAF 跳转地址：重进详情页后多次尝试仍未提取到 URL")
        return None

    def waf_open_jump_address(self, max_retries: int = 3):
        """在详情页提取跳转地址，新标签页打开 WAF 平台页面。

        Returns:
            Page: Playwright 新页面对象（WAF 平台页面）或 None
        """
        jump_url = None
        for extract_attempt in range(1, 12):
            jump_url = self._extract_jump_url()
            if jump_url:
                break
            self.page.wait_for_timeout(10000)

        if not jump_url:
            body_snippet = self.page.inner_text("body")[:2000]
            logger.warning(f"WAF 跳转地址：多次尝试后未找到跳转地址 URL，body 前2000字符: {body_snippet}")
            return None
        logger.info(f"WAF 跳转地址：提取到 URL: {jump_url}")

        for attempt in range(1, max_retries + 1):
            logger.info(f"WAF 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)

            if new_page is None:
                if attempt < max_retries:
                    logger.warning(f"WAF 跳转地址：第 {attempt} 次未获取到新页面，等待后重试")
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
                        logger.info("WAF 跳转地址：检测到证书警告页，点击高级按钮")
                        adv_btn.click()
                        new_page.wait_for_timeout(2000)
                        proceed = new_page.get_by_text(re.compile(r"继续前往|继续访问|Proceed"), exact=False).first
                        if proceed.count() > 0:
                            proceed.click()
                            logger.info("WAF 跳转地址：已点击继续前往，等待页面加载")
                            new_page.wait_for_timeout(10000)
            except Exception:
                pass

            quick_error = False
            for _ in range(15):
                self.page.wait_for_timeout(1000)
                current_url = new_page.url
                if ("chrome-error" in current_url and "chromewebdata" in current_url) or current_url == "about:blank":
                    logger.warning(f"WAF 跳转地址：快速检测到错误页面 {current_url}")
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
                        logger.warning("WAF 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue
                logger.warning("WAF 跳转地址：多次尝试后仍未成功打开平台页面，目标服务器可能不可达")
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
            logger.info(f"WAF 跳转地址：新页面当前 URL: {current_url}")

            if "chrome-error" not in current_url and current_url != "about:blank":
                logger.info(f"WAF 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"WAF 跳转地址：加载到错误页面 {current_url}，跳转地址可能已过期")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < max_retries:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("WAF 跳转地址：刷新详情页后未找到新的跳转地址 URL")
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

        logger.warning("WAF 跳转地址：多次尝试后仍未成功打开平台页面")
        return None

    def waf_name_clickable(self, name: str) -> bool:
        """检查列表页 WAF 实例名称是否可点击跳转。

        Args:
            name: 实例名称

        Returns:
            bool: True 表示可点击（蓝色链接），False 表示不可点击（黑色文本）
        """
        return self._is_row_name_clickable(name)

    def waf_spec_upgrade(self, name: str) -> dict:
        """执行规格升级：选择比当前规格更高的第一个可选规格并提交。

        Args:
            name: 实例名称

        Returns:
            dict: 选中的新规格信息 {'vcpus': int, 'memory_mb': int, 'name': str}
        """
        self._dismiss_visible_dialogs()
        try:
            self.click_action(name, "规格升级")
        except Exception as e:
            logger.warning(f"WAF 规格升级：标准 click_action 失败: {e}，尝试 fallback")
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
                        logger.info(f"WAF 规格升级 fallback: 点击行内 '{btn_text}'")
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
                        self.page.wait_for_timeout(800)
                        menu = self.page.locator('[class*="dropdown"]').last
                        if menu.count() > 0:
                            for opt_text in ["规格升级", "立即升级", "升级"]:
                                opt = menu.get_by_text(opt_text, exact=False).first
                                if opt.count() > 0:
                                    opt.click()
                                    logger.info(f"WAF 规格升级 fallback: 更多菜单 '{opt_text}'")
                                    found = True
                                    break
                if not found:
                    raise Exception("WAF 规格升级：所有 fallback 均无法找到升级操作")
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
        logger.info("WAF 规格升级：弹窗已打开")

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
                    logger.info("WAF 规格升级：提示信息验证通过（包含关机和再启动提醒）")
                else:
                    logger.warning(f"WAF 规格升级：提示信息缺少关机和再启动提醒，内容: {alert_text[:200]}")
                if "云硬盘" in alert_text:
                    logger.info("WAF 规格升级：提示信息验证通过（包含云硬盘大小提示）")
                else:
                    logger.warning(f"WAF 规格升级：提示信息缺少云硬盘大小提示，内容: {alert_text[:200]}")
        else:
            logger.warning("WAF 规格升级：未找到 alert 提示信息，跳过验证")

        self.page.wait_for_timeout(1500)
        rows = dialog.locator(".el-table__row")
        try:
            expect(rows.first).to_be_visible(timeout=10000)
        except Exception:
            pass

        radio_rows = rows.all()
        if len(radio_rows) == 0:
            radio_rows = dialog.locator("tr").all()
        logger.info(f"WAF 规格升级：弹窗内找到 {len(radio_rows)} 行规格")

        selected_spec = None
        for idx, row in enumerate(radio_rows):
            radio = row.locator(".el-radio").first
            if radio.count() == 0:
                continue
            radio_class = radio.get_attribute("class") or ""
            if "is-disabled" in radio_class:
                continue
            row_text = row.inner_text()
            vcpu_match = re.search(r"(\d+)核", row_text)
            mem_match = re.search(r"(\d+)GiB", row_text)
            spec_name_match = re.search(r"waf\.\S+|waf\S+|standard\.\S+", row_text)
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
                radio.click()
            self.page.wait_for_timeout(500)
            # 校验 radio 已真正选中
            checked_class = radio.get_attribute("class") or ""
            if "is-checked" not in checked_class:
                row.click()
                self.page.wait_for_timeout(300)
                checked_class = radio.get_attribute("class") or ""
            logger.info(
                f"WAF 规格升级：选中规格 vcpu={selected_spec['vcpus']}核, "
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
        # 确定按钮在 flavor_id 为空时会被禁用，确保已选中规格后再点击
        confirm_class = confirm_btn.get_attribute("class") or ""
        if "disabled" in confirm_class:
            try:
                expect(confirm_btn).not_to_have_class(re.compile(r"disabled"), timeout=5000)
            except Exception:
                confirm_class = confirm_btn.get_attribute("class") or ""
                raise Exception(
                    f"规格升级弹窗的确定按钮仍被禁用，可能是规格未真正选中，"
                    f"当前按钮 class: {confirm_class}"
                )
        confirm_btn.click()
        logger.info(f"WAF 实例 {name} 规格升级请求已提交")

        # 等待弹窗关闭，含错误检测
        try:
            dialog.wait_for(state="hidden", timeout=180000)
            logger.info("WAF 规格升级：弹窗已关闭")
        except Exception:
            error_text = ""
            static_warning = "规格升级后，云硬盘大小可能与规格不匹配"
            for err_sel in [".el-message--error", ".el-form-item__error"]:
                err_elem = self.page.locator(err_sel).first
                if err_elem.count() > 0 and err_elem.is_visible():
                    text = err_elem.inner_text()[:200]
                    if static_warning not in text:
                        error_text = text
                        break
            if error_text:
                logger.error(f"WAF 规格升级失败: {error_text}")
            else:
                logger.error("WAF 规格升级：弹窗未关闭（可能 API 超时或静默失败）")
            self._dismiss_visible_dialogs()
            raise Exception(
                f"规格升级弹窗未关闭，升级可能失败"
                + (f": {error_text}" if error_text else "")
            )
        return selected_spec

    def waf_volume_expand(self, name: str, new_size: int) -> str | None:
        """在详情页执行云硬盘扩容，填写新大小并提交。

        进入实例详情页，点击"扩容"按钮，填写目标大小后提交。

        Args:
            name: 实例名称
            new_size: 目标云硬盘大小（GiB），如 350

        Returns:
            str: server_id 或 None
        """
        self.waf_to_details(name)
        self.wait_for_detail_page_ready()
        self.page.wait_for_timeout(10000)
        try:
            self.page.wait_for_selector(".el-form-item, .detail-item", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(3000)

        body_text = self.page.inner_text("body")
        logger.info(f"详情页 body 文本 (前1500字符): {body_text[:1500]}")
        vol_match = re.search(r"(\d+)\s*GiB", body_text)
        current_size = int(vol_match.group(1)) if vol_match else None
        logger.info(f"WAF 实例 {name} 当前云硬盘大小: {current_size}GiB")

        try:
            self.page.wait_for_selector(".el-loading-mask", state="detached", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)

        expand_btn = self.page.get_by_text("扩容", exact=True).first
        try:
            expand_btn.wait_for(timeout=10000)
        except Exception:
            pass
        if expand_btn.count() > 0 and expand_btn.is_visible():
            expand_btn.click()
            logger.info("WAF 云硬盘扩容：已点击扩容")
        else:
            raise Exception("未找到扩容按钮")

        try:
            self.page.wait_for_selector(".sugon-dialog:visible .el-input__inner, .el-dialog:visible .el-input__inner, .sugon-dialog:visible input, .el-dialog:visible input", timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(500)

        vol_input = None
        for input_sel in [
            ".sugon-dialog:visible .el-input__inner",
            ".el-dialog:visible .el-input__inner",
            ".sugon-dialog:visible input.el-input__inner",
            ".sugon-dialog:visible input[type='text']",
            ".sugon-dialog:visible input",
            ".el-dialog:visible input",
        ]:
            inp = self.page.locator(input_sel).first
            if inp.count() > 0 and inp.is_visible():
                vol_input = inp
                break
        if vol_input is None:
            raise Exception("未找到扩容弹窗输入框")
        vol_input.click()
        self.page.wait_for_timeout(300)
        vol_input.fill("")
        self.page.wait_for_timeout(300)
        vol_input.fill(str(new_size))
        self.page.wait_for_timeout(500)
        logger.info(f"WAF 云硬盘扩容：已填写 {new_size}GiB")

        confirm_btn = None
        for btn_sel in [
            ".sugon-dialog:visible .cloud-button-btn.cl-btn-primary",
            ".el-dialog:visible .cloud-button-btn.cl-btn-primary",
            ".sugon-dialog:visible .cloud-button-btn",
            ".sugon-dialog:visible button",
            ".el-dialog:visible button",
        ]:
            btn = self.page.locator(btn_sel).filter(has_text="确定").first
            if btn.count() > 0 and btn.is_visible():
                confirm_btn = btn
                break
        if confirm_btn is not None:
            confirm_btn.click()
            logger.info("WAF 云硬盘扩容：已点击确定")
        else:
            raise Exception("未找到扩容弹窗确定按钮")

        self.page.wait_for_timeout(3000)
        start = time.time()
        while time.time() - start < 120:
            self.page.wait_for_timeout(3000)
            body_text = self.page.inner_text("body")
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            updated_size = int(vol_match.group(1)) if vol_match else None
            if updated_size == new_size:
                logger.info(f"WAF 实例 {name} 云硬盘扩容完成: {updated_size}GiB")
                break
            logger.debug(f"WAF 实例 {name} 云硬盘大小当前: {updated_size}GiB，等待更新到 {new_size}GiB")
        else:
            raise AssertionError(f"WAF 实例 {name} 云硬盘扩容超时，期望 {new_size}GiB")

        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"WAF 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"WAF 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def waf_get_server_id(self, name: str) -> str | None:
        """进入详情页，从URL中提取 server_id。

        Args:
            name: 实例名称

        Returns:
            str: server_id（UUID格式），若未找到返回 None
        """
        self.waf_to_details(name)
        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"WAF 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"WAF 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def waf_bind_floating_ip(
        self, name: str, eip_ip: str | None = None, pool: str | None = None
    ) -> str | None:
        """绑定公网IP到 WAF 实例。

        Args:
            name: 实例名称
            eip_ip: 指定要绑定的公网IP；为 None 时选择第一个可用IP
            pool: 公网IP资源池名称，默认读取配置 network

        Returns:
            str | None: 绑定的公网IP地址
        """
        from sugon_web.config.config import Config
        if pool is None:
            pool = Config.get("network") or SECURITY_DEFAULT_FIP_POOL

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

        # 从表格中选择指定或第一个可用IP的radio按钮（支持分页）
        selected_ip = self._select_eip_in_paginated_dialog(dialog, eip_ip=eip_ip)
        if not selected_ip:
            raise Exception("WAF 绑定公网IP: 没有可用的公网 IP")
        logger.info(f"WAF 实例 {name} 已选择公网IP {selected_ip}")

        self._click_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WAF 实例 {name} 绑定公网IP请求已提交")
        return selected_ip

    def waf_unbind_floating_ip(self, name: str):
        """解绑 WAF 实例的公网IP。

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

        self._click_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WAF 实例 {name} 解绑公网IP请求已提交")

    def waf_live_migrate_auto(self, name: str):
        """对 WAF 实例执行热迁移（系统分配）。

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

        self._click_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WAF 实例 {name} 热迁移（系统分配）请求已提交")

    def waf_live_migrate_manual(self, name: str, src_host: str = None):
        """对 WAF 实例执行热迁移（手动指定），自动选择不同于源节点的目标节点。

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
            logger.info(f"WAF 实例 {name} 已选择目标物理机")
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

        logger.info(f"WAF 实例 {name} 已确认物理机选择，准备提交热迁移请求")

        self._click_dialog_confirm(dialog)
        self.page.wait_for_timeout(2000)
        logger.info(f"WAF 实例 {name} 热迁移（手动指定）请求已提交")

    def waf_vnc_login(self, name: str):
        """对 WAF 实例执行 VNC 登录操作，返回新打开的 VNC 页面（如有）。

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

        # 登录VNC 异步打开新标签页：在 expect_page 上下文内触发点击，
        # 由 Playwright 事件等待捕获新标签页（与 _open_jump_url 同范式），
        # 避免一次性查 context.pages 时新标签页尚未打开而漏捕获。
        new_page = None
        try:
            with self.page.context.expect_page(timeout=60000) as new_page_info:
                self.click_action(name, "登录VNC")
                logger.info(f"WAF 实例 {name} 登录VNC请求已提交")
            new_page = new_page_info.value
        except Exception:
            logger.debug("WAF 登录VNC：expect_page 未捕获，尝试从 pages 列表获取")
            self.page.wait_for_timeout(5000)
            for p in reversed(self.page.context.pages):
                if p != self.page:
                    new_page = p
                    break

        if new_page and isinstance(new_page, PwPage):
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            logger.info(f"WAF 实例 {name} VNC 新页面 URL: {new_page.url}")
        else:
            logger.warning(f"WAF 实例 {name} VNC 新页面未自动打开")
        return new_page

    def waf_get_network_info(self, name: str) -> dict:
        """获取 WAF 实例的网络信息（固定 IP 和公网 IP）。

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
