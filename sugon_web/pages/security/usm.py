import re
import time
import allure
import pytest
from playwright.sync_api import expect
from sugon_web.common.base import BasePage
from sugon_web.assertions.security import UsmAssertionMixin
from sugon_web.utils.logger import logger


class UsmPage(UsmAssertionMixin, BasePage):
    """云堡垒机高级版USM 页面对象。

    覆盖以下能力：
    - 创建 USM 实例（基本设置 + 配置）
    - 实例操作（开机、关机、删除、绑定公网IP）
    - 实例状态读取（服务状态、虚拟机状态）
    - 进入实例详情页 / 跳转地址验证
    """
    """云堡垒机高级版USM 页面对象。

    覆盖以下能力：
    - 创建 USM 实例（基本设置 + 配置）
    - 实例操作（开机、关机、删除、绑定公网IP）
    - 实例状态读取（服务状态、虚拟机状态）
    - 进入实例详情页 / 跳转地址验证
    """

    service_name = "云堡垒机高级版"

    def get_detail_body_text(self) -> str:
        """获取详情页 body 文本内容，供测试层回读页面信息断言。"""
        return self.page.inner_text("body")

    def goto_list_page(self):
        """导航到 USM 列表页。从详情页或跳转地址页回到列表时必须用此方法。"""
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/das/#/usm"
        self.page.goto(target_url)
        self.wait_for_page_ready()
        # 等待列表数据加载完成（先等 loading 消失，再检查行数据）
        for attempt in range(1, 16):
            self.page.wait_for_timeout(2000)
            # 若被重定向到无权限页，重新导航
            if "/no-permission" in self.page.url:
                logger.warning(f"USM 列表页被重定向到无权限页，重新导航 (第{attempt}次)")
                self.page.goto(target_url)
                self.wait_for_page_ready()
                continue
            # 等待 loading 遮罩消失
            loading_mask = self.page.locator(".el-loading-mask:visible, .el-loading-spinner:visible").first
            if loading_mask.count() > 0:
                logger.info(f"USM 列表页数据加载中，继续等待 (第{attempt}次)...")
                continue
            has_rows = self.page.locator(".el-table__row").count() > 0
            has_empty = self.page.locator(".el-table__empty-block, .el-table__empty-text").count() > 0
            if has_rows:
                logger.info(f"USM 回到列表页（第{attempt}次检查）: {self.page.url}")
                return
            if has_empty:
                logger.info(f"USM 列表页表格为空（第{attempt}次检查）: {self.page.url}")
                return
            logger.info(f"USM 列表页仍为空，等待数据加载中(第{attempt}次)...")
            if attempt >= 3 and not has_rows and not has_empty:
                logger.warning(f"USM 列表页数据未就绪，继续等待 (第{attempt}次)...")
        logger.info(f"USM 回到列表页: {self.page.url}")

    def get_first_usm_name(self) -> str:
        """获取 USM 列表中第一个实例的名称。

        Returns:
            str: 第一个 USM 实例的名称

        Raises:
            AssertionError: 当列表中没有实例时
        """
        self.goto_list_page()
        rows = self.page.locator(".el-table__row").all()
        if not rows:
            raise AssertionError("USM 列表页没有找到任何实例")
        first_row = rows[0]
        # 优先通过 get_row_data_by_locator 获取整行数据，从中找名称
        row_data = self.get_row_data_by_locator(first_row)
        # 优先查找包含 autotest 或 usm 的字段（这才是实例名称）
        name = ""
        for key, value in row_data.items():
            text = str(value).strip() if value else ""
            if text and ("autotest" in text.lower() or "usm" in text.lower()):
                name = text
                break
        if not name:
            # 兜底：取第一个长度大于3且不是常见状态值的非空字段
            for key, value in row_data.items():
                text = str(value).strip() if value else ""
                if text and len(text) > 3 and text not in ["运行", "关机", "创建中", "不可用", "--", "GiB"]:
                    name = text
                    break
        logger.info(f"USM 列表第一个实例名称: {name}")
        return name

    @property
    def _input_name(self):
        """USM 创建表单：名称输入框"""
        # 通过表单标签精确定位，避免 strict mode violation
        return self.locator(".el-form-item").filter(
            has_text=re.compile(r"^名称$")
        ).get_by_role("textbox")

    @property
    def _btn_submit(self):
        """USM 创建表单：提交按钮，兼容多种文案"""
        locators = [
            self.locator(".cloud-button-btn").filter(has_text="点击创建"),
            self.locator(".cloud-button-btn").filter(has_text="创建"),
            self.get_by_text("点击创建"),
            self.get_by_text("创建"),
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
        raise Exception("未找到 USM 创建表单的提交按钮")

    def _select_form_item(self, label: str, option: str):
        """选择表单的下拉项。

        Args:
            label: 表单字段标签（如"版本"、"集群"、"安全底座"、"专有网络"、"云硬盘类型"）
            option: 要选择的下拉项文本（支持模糊匹配）
        """
        # 支持多种定位策略
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

        # 点击下拉框
        dropdown_trigger = form_item.locator(".el-select, [class*='select']").first
        if dropdown_trigger.count() == 0:
            dropdown_trigger = form_item.get_by_placeholder(re.compile(r"请选择|选择")).first
        dropdown_trigger.click()
        # 等待下拉框选项加载完成（至少出现一个选项）
        dropdown_option_selector = ".el-select-dropdown:visible .el-select-dropdown__item, .el-select-dropdown:visible li, .el-dropdown-menu:visible li"
        try:
            self.page.wait_for_selector(dropdown_option_selector, timeout=10000)
        except Exception:
            pass
        self.page.wait_for_timeout(1500)
        # 选择选项
        all_visible = self.locator(dropdown_option_selector)
        # 如果选项还没加载出来，多等几次
        for _ in range(10):
            if all_visible.count() > 0:
                break
            self.page.wait_for_timeout(2000)
            all_visible = self.locator(".el-select-dropdown:visible li, .el-dropdown-menu:visible li")
        options = all_visible.filter(has_text=option)
        if options.count() == 0:
            # 尝试精确匹配
            options = all_visible.filter(has_text=re.compile(rf"^{re.escape(option)}$"))
        if options.count() == 0:
            # 尝试大小写不敏感匹配
            options = all_visible.filter(has_text=re.compile(re.escape(option), re.IGNORECASE))
        if options.count() == 0:
            # 调试：打印所有可用选项
            available = [all_visible.nth(i).inner_text() for i in range(min(all_visible.count(), 20))]
            logger.error(f"下拉框 '{label}' 可用选项: {available}")
            raise Exception(f"未找到下拉选项: {label} = {option}，可用选项: {available}")
        options.first.click()
        logger.info(f"USM 创建：选择 {label} = {option}")

    def _select_flavor(self, cpu: str = "2核", memory: str = "8GiB"):
        """选择规格表格中的指定行。

        Args:
            cpu: CPU 规格（如"2核"）
            memory: 内存规格（如"8GiB"）
        """
        # 等待表格加载完成
        self.page.wait_for_timeout(1000)
        rows = self.locator(".el-table__row")
        expect(rows.first).to_be_visible(timeout=10000)

        # 在表格行中查找匹配 CPU 和内存的行
        row_count = rows.count()
        target_row = None
        for i in range(row_count):
            row = rows.nth(i)
            row_text = row.inner_text()
            if cpu in row_text and memory in row_text:
                target_row = row
                break

        # 如果没找到匹配行，尝试通过筛选器缩小范围（点击下拉框）
        if target_row is None:
            # CPU 筛选：定位规格区域的前两个下拉框
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

        # 点击行的 radio 按钮：使用 JavaScript 确保选中
        radio_input = target_row.locator(".el-radio__original").first
        radio_input.evaluate("el => el.click()")
        logger.info(f"USM 创建：选择规格 CPU={cpu}, 内存={memory}")

    def usm_create(
        self,
        name: str,
        version: str = "V2.0.8.8.6",
        cluster: str = "Autotest",
        base_name: str = None,
        network: str = None,
        subnet: str = None,
        volume_type: str = None,
        cpu: str = "2核",
        memory: str = "8GiB",
    ):
        """创建 USM 实例。

        Args:
            name: 实例名称
            version: 版本号，默认 V2.0.8.8.6
            cluster: 集群名称，默认 Autotest
            base_name: 安全底座名称（None 表示选择第一个可用的）
            network: 专有网络名称（None 表示选择第一个可用的）
            subnet: 子网名称（None 表示选择第一个可用的）
            volume_type: 云硬盘类型（None 表示使用默认 xbd-type）
            cpu: 规格 CPU，默认 2核
            memory: 规格内存，默认 8GiB
        """
        # 导航到列表页，点击"新建"进入创建页面
        self.goto_list_page()
        btn = self.btn_create
        btn.click()
        self.wait_for_page_ready()
        expect(self._input_name).to_be_visible(timeout=10000)
        logger.info("USM 创建页面加载成功")

        # 等待创建页面所有异步数据加载完成（版本、集群等下拉框选项）
        self.page.wait_for_timeout(5000)
        # 额外等待至少一个 el-select 组件就绪
        try:
            self.page.wait_for_selector(".el-select .el-input__inner", timeout=10000)
        except Exception:
            pass

        self._input_name.fill(name)

        if version:
            self._select_form_item("版本", version)
        if cluster:
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

        # 选择子网：专有网络选择后子网可能异步加载，需要等待
        subnet_input = self.get_by_placeholder("请选择子网").first
        subnet_input.click()
        self.page.wait_for_timeout(1000)
        options = self.locator(".el-select-dropdown:visible li")
        if subnet:
            options.filter(has_text=subnet).first.click()
        else:
            # 跳过可能的"请选择"占位项，选择第一个真实子网
            cnt = options.count()
            for i in range(cnt):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                if text and "请选择" not in text:
                    opt.click()
                    break
        self.page.wait_for_timeout(1000)

        # 子网选择后可能出现 IP 地址字段，需要选择
        ip_form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"IP地址"))
        if ip_form_item.count() > 0:
            ip_select = ip_form_item.locator(".el-select").first
            if ip_select.count() > 0 and ip_select.is_visible():
                ip_select.click()
                self.page.wait_for_timeout(500)
                ip_options = self.locator(".el-select-dropdown:visible li")
                if ip_options.count() > 0:
                    ip_options.first.click()
                    logger.info("USM 创建：选择 IP 地址")
                self.page.wait_for_timeout(500)

        vol_type = volume_type or self.volume_type
        try:
            self._select_form_item("云硬盘类型", vol_type)
        except Exception:
            logger.warning(f"云硬盘类型 '{vol_type}' 不可用，选择第一个可用选项")
            form_item = self.locator(".el-form-item").filter(has_text=re.compile(r"^云硬盘类型"))
            form_item.get_by_placeholder(re.compile(r"请选择")).first.click()
            self.page.wait_for_timeout(500)
            self.locator(".el-select-dropdown:visible li").first.click()

        self._select_flavor(cpu=cpu, memory=memory)

        self._btn_submit.click()
        logger.info(f"USM 创建：已提交创建请求 {name}")

        # 等待页面自动跳转回列表页（创建提交后会自动返回列表）
        try:
            self.page.wait_for_url("**/das/#/usm", timeout=30000)
            logger.info(f"USM 创建：页面已跳转回列表页 {self.page.url}")
        except Exception:
            # 如果URL未变化，可能还在创建页或跳转失败，手动返回列表页
            logger.warning("USM 创建：页面未自动跳转，手动返回列表页")
            self.goto_list_page()

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
                # 倒序遍历，避免关闭弹窗后索引变化导致遗漏或越界
                for i in range(count - 1, -1, -1):
                    dialog = dialogs.nth(i)
                    try:
                        try:
                            dialog.wait_for(timeout=1000)
                        except Exception:
                            pass
                        if dialog.is_visible():
                                                        # 尝试点击关闭按钮或取消按钮
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

    def usm_operations(self, name: str, action: str):
        """对 USM 实例执行操作（开机、关机、删除等）。

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
            logger.warning(f"USM 标准 click_action 失败: {e}，尝试 fallback 定位")
            # Fallback: 在行内直接查找 action 文本并点击
            row = self.get_row_by_name(name)
            # 先尝试平铺按钮（不限制 interactive_row，直接在行内查找）
            btn = row.get_by_text(action, exact=False).first
            if btn.count() > 0:
                try:
                    btn.wait_for(timeout=2000)
                except Exception:
                    pass
                if btn.is_visible():
                                btn.click()
                                logger.info(f"USM 操作 fallback: 直接点击行内 '{action}' 按钮")
            else:
                # Fallback2: 尝试点击"更多"或"操作"按钮展开下拉菜单
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
                                                # 在下拉菜单中查找 action
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
                                                                logger.info(f"USM 操作 fallback: 点击'{more_text}'下拉菜单中的 '{action}'")
                                                                break
                                                else:
                                                    continue
                                                break
                else:
                    raise Exception(f"USM 操作 {action} 的 fallback 定位也失败了")
        try:
            self._click_dialog_confirm()
        except Exception as e:
            # 区分"无确认框"和"点击失败"：后者需要暴露异常
            if "未找到弹窗确认按钮" in str(e):
                logger.debug(f"USM 操作 {action} 未弹出确认对话框")
            else:
                logger.warning(f"USM 操作 {action} 确认对话框点击失败: {e}")
                raise
        logger.info(f"USM 实例 {name} 执行操作: {action}")

    def usm_rename(self, name: str, new_name: str):
        """修改 USM 实例名称。

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
        logger.info("USM 修改名称：弹窗已打开")

        # 填写新名称
        name_input = dialog.locator(".el-input__inner").first
        name_input.click()
        self.page.wait_for_timeout(300)
        name_input.fill("")
        self.page.wait_for_timeout(300)
        name_input.fill(new_name)
        self.page.wait_for_timeout(500)
        logger.info(f"USM 修改名称：已填写新名称 {new_name}")

        # 点击确定
        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"USM 实例 {name} 名称已修改为 {new_name}")

    def usm_delete(self, name: str):
        """删除 USM 实例（先勾选确认框，再点击确定）。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()

        # 尝试标准 click_action，失败则使用 fallback 定位
        try:
            self.click_action(name, "删除")
        except Exception as e:
            logger.warning(f"USM 标准 click_action 删除失败: {e}，尝试 fallback 定位")
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
                    raise Exception(f"USM 删除 {name} 的 fallback 定位也失败了")

        try:
            # 兼容 sugon-dialog 和 el-dialog
            dialog = self.locator(".sugon-dialog:visible, .el-dialog:visible").first
            checkbox = dialog.locator(".el-checkbox").first
            try:
                checkbox.wait_for(timeout=2000)
            except Exception:
                pass
            if checkbox.is_visible():
                                checkbox.click()
        except Exception:
            logger.debug("USM 删除：无需勾选确认框")
        self._click_dialog_confirm()
        logger.info(f"USM 实例 {name} 删除请求已提交")

    def usm_verify_detail_name(self, name: str) -> None:
        """验证详情页展示的名称与预期一致。

        进入详情页后处理项目选择弹窗、等待数据加载，验证名称字段。

        Args:
            name: 期望显示的实例名称
        """
        self.usm_to_details(name)
        self.page.wait_for_timeout(3000)

        # 处理项目选择弹窗
        for btn_text in ["确定", "确认", "进入"]:
            try:
                btn = self.page.get_by_text(btn_text, exact=True).first
                if btn.count() > 0:
                    try:
                        btn.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if btn.is_visible():
                                        btn.click()
                                        self.page.wait_for_timeout(3000)
                                        break
            except Exception:
                continue

        # 如果详情页未显示名称，刷新页面重试
        body_text = self.page.inner_text("body")
        if name not in body_text:
            self.page.reload()
            self.wait_for_detail_page_ready()
            self.page.wait_for_timeout(5000)
            # 再次处理弹窗
            for btn_text in ["确定", "确认", "进入"]:
                try:
                    btn = self.page.get_by_text(btn_text, exact=True).first
                    if btn.count() > 0:
                        try:
                            btn.wait_for(timeout=2000)
                        except Exception:
                            pass
                        if btn.is_visible():
                                                btn.click()
                                                self.page.wait_for_timeout(3000)
                                                break
                except Exception:
                    continue

        body_text = self.page.inner_text("body")
        assert name in body_text, f"详情页未展示名称: {name}"

    def usm_bind_eip(self, name: str):
        """为 USM 实例绑定公网IP：先选资源池，再勾选IP，最后确认。

        Args:
            name: 实例名称

        Returns:
            str: 绑定的公网IP地址
        """
        self.goto_list_page()
        self.click_action(name, "绑定公网IP")
        self.page.wait_for_timeout(1000)
        bind_dialog = self.locator(".sugon-dialog").filter(has_text="绑定公网IP")
        if bind_dialog.count() == 0 or not bind_dialog.first.is_visible():
            raise Exception("未找到绑定公网IP弹窗")
        dialog = bind_dialog.first

        # 步骤1: 选择资源池（优先选 public_net，否则选第一个）
        pool_selects = dialog.locator(".el-select").all()
        if len(pool_selects) > 0:
            pool_selects[0].click()
            self.page.wait_for_timeout(500)
            pool_options = self.locator(".el-select-dropdown:visible li")
            expect(pool_options.first).to_be_visible(timeout=5000)
            # 优先选择包含"public_net"或"基础版"的资源池
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
            logger.info("USM 绑定公网IP：已选择资源池")
            # 等待下方IP列表加载
            self.page.wait_for_timeout(1500)

        # 步骤2: 在弹窗中勾选第一个可用的公网IP
        eip_address = self._select_first_eip_in_dialog(dialog)
        if not eip_address:
            raise Exception("未在弹窗中找到可勾选的公网IP")
        logger.info(f"USM 绑定公网IP：已勾选IP {eip_address}")

        # 步骤3: 点击确认
        confirm_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            try:
                confirm_btn.wait_for(timeout=3000)
            except Exception:
                pass
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            raise Exception("未找到绑定公网IP弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"USM 实例 {name} 公网IP绑定请求已提交，IP={eip_address}")

        # 在列表页验证网络列显示已绑定的公网IP
        self._assert_eip_bound(name, eip_address, timeout=120)

        # 绑定成功后等待120秒，让网络配置在USM实例内部生效
        logger.info("USM 绑定公网IP成功，等待120秒让网络配置生效...")
        self.page.wait_for_timeout(120000)
        return eip_address

    def usm_unbind_eip(self, name: str):
        """解绑 USM 实例的公网IP。

        弹出"解除绑定公网IP"对话框，前端自动选中第一个公网IP，确认后验证网络列不再显示公网IP。

        Args:
            name: 实例名称
        """
        self.goto_list_page()
        self.click_action(name, "解绑公网IP")
        self.page.wait_for_timeout(1000)
        unbind_dialog = self.locator(".sugon-dialog").filter(has_text="解除绑定公网IP")
        if unbind_dialog.count() == 0 or not unbind_dialog.first.is_visible():
            raise Exception("未找到解除绑定公网IP弹窗")
        dialog = unbind_dialog.first

        # 前端 openDialog 时自动调用 getDeviceFloatip() 选中第一个IP，等待填充完成
        self.page.wait_for_timeout(1500)

        confirm_btn = dialog.locator(".cloud-button-btn").filter(has_text="确定").first
        if confirm_btn.count() == 0:
            try:
                confirm_btn.wait_for(timeout=3000)
            except Exception:
                pass
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            raise Exception("未找到解除绑定公网IP弹窗的确定按钮")
        confirm_btn.click()
        logger.info(f"USM 实例 {name} 公网IP解绑请求已提交")

        # 验证网络列不再显示公网IP
        self._assert_eip_unbound(name, timeout=60)
        logger.info(f"USM 实例 {name} 已解绑公网IP")

    def _assert_eip_unbound(self, name: str, timeout: int = 60):
        """断言列表页实例网络列不再显示公网IP（解绑后仅剩固定IP）。

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
                # 解绑后网络列不应包含FIP格式的公网IP地址
                fip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", network)
                if len(fip_patterns) <= 1:
                    logger.info(f"USM 实例 {name} 已解绑公网IP，网络列: {network}")
                    return
                logger.debug(f"USM 实例 {name} 网络列仍含公网IP: {network}，等待解绑生效...")
            except Exception as e:
                logger.debug(f"验证公网IP解绑状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"USM 实例 {name} 网络列仍显示公网IP，解绑未生效")

    def _select_first_eip_in_dialog(self, dialog) -> str | None:
        """在绑定公网IP弹窗中选择第一个可用的IP，返回IP地址字符串。"""
        # 策略A: 表格行内有 radio 按钮（最常见）
        rows = dialog.locator("tr, .el-table__row").all()
        for row in rows:
            if not row.is_visible():
                continue
            row_text = row.inner_text()
            ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", row_text)
            if ip_match:
                # 尝试点击行内的 radio
                radio = row.locator(".el-radio__original, input[type='radio']").first
                if radio.count() > 0:
                    radio.evaluate("el => el.click()")
                else:
                    row.click()
                return ip_match.group(0)

        # 策略B: 独立 radio/checkbox 列表
        radios = dialog.locator(".el-radio, input[type='radio']").all()
        for radio in radios:
            if not radio.is_visible():
                continue
            # 获取radio同级的文本或父级文本
            parent = radio.locator("xpath=../..").first
            if parent.count() == 0:
                parent = radio.locator("xpath=..").first
            if parent.count() > 0:
                parent_text = parent.inner_text()
                ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", parent_text)
                if ip_match:
                    radio.evaluate("el => el.click()")
                    return ip_match.group(0)

        # 策略C: 列表项直接包含IP
        items = dialog.locator("li, .list-item").all()
        for item in items:
            if not item.is_visible():
                continue
            item_text = item.inner_text()
            ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", item_text)
            if ip_match:
                item.click()
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
                if eip in network:
                    logger.info(f"USM 实例 {name} 网络列已显示公网IP: {network}")
                    return
                logger.debug(f"USM 实例 {name} 网络列当前: {network}，等待公网IP {eip} 出现...")
            except Exception as e:
                logger.debug(f"验证公网IP绑定状态失败: {e}")
            time.sleep(5)
        raise AssertionError(f"USM 实例 {name} 网络列未显示公网IP {eip}")

    def _usm_authorize(self, name: str, duration: str = "1个月"):
        """对 USM 实例执行授权操作（自动触发，仅用于创建后授权失败场景）。

        弹窗使用 el-radio-button 组件展示购买时长选项（1个月/2个月/3个月/...），
        选中后按钮变红（is-active 状态）。
        """
        self._duration_dialog(name, "授权", duration)

    def usm_renewal(self, name: str, duration: str):
        """对 USM 实例执行续费操作。

        Args:
            name: 实例名称
            duration: 续费时长，如 "2个月", "3个月"
        """
        self._duration_dialog(name, "续期", duration)

    def usm_authorize(self, name: str, duration: str):
        """对 USM 实例执行授权操作（手动调用，支持自定义购买时长）。

        Args:
            name: 实例名称
            duration: 购买时长，如 "1个月", "3个月"
        """
        self._duration_dialog(name, "授权", duration)

    def usm_unsubscribe(self, name: str):
        """对 USM 实例执行退订操作。

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
                logger.debug("USM 退订：未弹出确认对话框")
            else:
                raise
        logger.info(f"USM 实例 {name} 退订请求已提交")

    def _duration_dialog(self, name: str, action: str, duration: str):
        """通用方法：处理授权/续费弹窗（共用同一个 el-radio-button 时长选择组件）。

        前端实现：add-authorization-dialog.vue，购买时长使用 el-radio-button，
        type==='服务授权' 走 add_auth API，否则走 retime_auth API。

        Args:
            name: 实例名称
            action: 操作名称，"授权" 或 "续费"
            duration: 购买时长，如 "1个月", "2个月", "3个月"
        """
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
            logger.warning(f"USM {action}：未找到弹窗，可能已自动完成")
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
                        logger.info(f"USM {action}：已选择 {duration} 购买时长（el-radio-button）")
                        self.page.wait_for_timeout(500)
        else:
            # 兜底：通过 is-active 类验证是否已默认选中
            active_btn = dialog.locator(".el-radio-button.is-active").first
            if active_btn.count() > 0:
                active_text = active_btn.inner_text()
                logger.info(f"USM {action}：当前已选中 {active_text}（默认选中状态）")
            else:
                logger.warning(f"USM {action}：未找到时长选项 {duration}，直接尝试确认")

        self._click_dialog_confirm()
        self.page.wait_for_timeout(2000)
        logger.info(f"USM 实例 {name} {action}操作已提交")

    def _extract_jump_url(self) -> str | None:
        """从当前详情页提取跳转地址 URL。"""
        self.wait_for_detail_page_ready()
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(500)

        # 检查是否显示"未绑定公网IP"提示，如果是则刷新页面
        body_text = self.page.inner_text("body")
        if "未绑定公网IP" in body_text or "暂不可使用" in body_text:
            logger.warning("USM 详情页显示'未绑定公网IP暂不可使用'，刷新页面重试...")
            self.page.reload()
            self.wait_for_detail_page_ready()
            self.page.wait_for_timeout(3000)
            body_text = self.page.inner_text("body")

        # 策略1: 按关键词搜索标签附近的内容
        for keyword in ["跳转地址", "访问地址", "管理地址", "登录地址", "控制台", "链接",
                        "平台地址", "USM地址", "系统地址", "外链", "外部链接", "打开", "进入"]:
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

        # 策略2: 搜索所有可见的http链接，优先匹配USM相关
        links = self.locator("a[href^='http']").all()
        for link in links:
            try:
                if link.is_visible():
                    href = link.get_attribute("href")
                    if href and ("openapiOAuth" in href or "172.22" in href or "usm" in href.lower()):
                        return href
            except Exception:
                continue

        # 策略3: 搜索所有input/textarea中可能包含的URL
        for selector in ["input[readonly]", ".el-input__inner", "textarea"]:
            try:
                inputs = self.page.locator(selector).all()
                for inp in inputs:
                    if inp.is_visible():
                        val = inp.input_value() or inp.get_attribute("value") or ""
                        if val and (val.startswith("http") or "openapiOAuth" in val):
                            return val
            except Exception:
                continue

        # 策略4: 从body文本中提取URL
        body_text = self.page.inner_text("body")
        urls = re.findall(r"https?://[^\s\n]+", body_text)
        for url in urls:
            if "172.22" in url or ":30000" in url or "usm" in url.lower() or "openapiOAuth" in url:
                return url

        # 策略5: 搜索可能包含跳转地址的data属性或title属性
        try:
            all_links = self.page.locator("a").all()
            for link in all_links:
                if link.is_visible():
                    href = link.get_attribute("href") or ""
                    title = link.get_attribute("title") or ""
                    data_href = link.get_attribute("data-href") or ""
                    for val in [href, title, data_href]:
                        if val and (val.startswith("http") or "openapiOAuth" in val):
                            return val
        except Exception:
            pass

        # 策略6: 尝试点击可能生成跳转地址的按钮
        for btn_text in ["获取跳转地址", "刷新", "生成链接", "点击获取", "跳转",
                         "打开", "进入平台", "获取链接", "更新链接", "平台入口"]:
            try:
                btn = self.get_by_text(btn_text, exact=False).first
                if btn.count() > 0:
                    try:
                        btn.wait_for(timeout=2000)
                    except Exception:
                        pass
                    if btn.is_visible():
                                        logger.info(f"USM 发现可能生成跳转地址的按钮: '{btn_text}'，尝试点击")
                                        btn.click()
                                        self.page.wait_for_timeout(3000)
                                        # 点击后重新搜索URL
                                        body_text = self.page.inner_text("body")
                                        urls = re.findall(r'https?://[^\s\n<>"]+', body_text)
                                        for url in urls:
                                            if "172.22" in url or ":30000" in url or "usm" in url.lower() or "openapiOAuth" in url:
                                                logger.info(f"USM 点击按钮后发现跳转地址: {url}")
                                                return url
                                        # 也搜索input
                                        for selector in ["input[readonly]", ".el-input__inner"]:
                                            inputs = self.page.locator(selector).all()
                                            for inp in inputs:
                                                if inp.is_visible():
                                                    val = inp.input_value() or inp.get_attribute("value") or ""
                                                    if val and (val.startswith("http") or "openapiOAuth" in val):
                                                        logger.info(f"USM 点击按钮后从input发现跳转地址: {val}")
                                                        return val
            except Exception:
                continue

        # 策略7: 记录页面body内容用于调试
        try:
            body_text = self.page.inner_text("body")[:3000]
            logger.info(f"USM 跳转地址提取失败，页面body前3000字符: {body_text}")
            all_urls = re.findall(r'https?://[^\s\n<>"]+', body_text)
            logger.info(f"USM 页面中找到的所有URL: {all_urls}")
        except Exception as e:
            logger.warning(f"USM 记录页面body失败: {e}")

        return None

    def wait_for_detail_page_ready(self, timeout: int = 60):
        """等待 USM 详情页加载完成，兼容较慢的后端数据加载。

        详情页在实例刚创建/状态变更后可能需要较长时间加载，
        因此使用比默认更长的超时时间，且允许 spinner 持续存在时不直接报错。
        """
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)
        self.page.wait_for_load_state("load", timeout=30000)
        # 对 el-loading-spinner 使用更长超时，若仍不消失则记录警告继续
        spinners = self.page.locator(".el-loading-spinner")
        try:
            if spinners.count() > 0:
                spinners.first.wait_for(state="hidden", timeout=timeout * 1000)
        except Exception:
            logger.warning(f"USM 详情页 loading spinner 在 {timeout}s 后仍未消失，继续执行")
            # 强制移除 loading mask，避免遮挡后续操作
            self.page.evaluate("""
                document.querySelectorAll('.el-loading-mask').forEach(el => el.remove());
                document.querySelectorAll('.el-loading-spinner').forEach(el => el.remove());
            """)

    def _find_server_info_from_vue(self, name: str) -> dict | None:
        """通过 Vue 组件内部数据查找实例完整信息（包含所有详情页所需参数）。"""
        result = self.page.evaluate("""
            (name) => {
                // 方法A: 遍历所有 DOM 元素的 __vue__ 属性
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let vm = el.__vue__;
                        while (vm) {
                            // 查找 listInfo / tableData / data 等常见列表属性
                            for (const key of ['listInfo', 'tableData', 'data', 'list', 'items', 'rows', 'tableData1']) {
                                const arr = vm[key];
                                if (Array.isArray(arr)) {
                                    for (const item of arr) {
                                        if (item.server_name === name || item.name === name) {
                                            // 提取浮动IP地址
                                            let addr = '';
                                            let fixed_ip = '';
                                            if (item.addresses && Array.isArray(item.addresses)) {
                                                item.addresses.forEach(a => {
                                                    if (a.type === 'floating') addr = a.addr || '';
                                                    if (a.type === 'fixed') fixed_ip = a.addr || '';
                                                });
                                            }
                                            return {
                                                id: item.id || '',
                                                server_id: item.server_id || '',
                                                server_name: item.server_name || item.name || '',
                                                create_time: item.create_time || item.createTime || '',
                                                image_id: item.image_id || item.imageId || '',
                                                port: item.port || '',
                                                addresses: addr,
                                                fixed_ip: fixed_ip
                                            };
                                        }
                                    }
                                }
                            }
                            vm = vm.$parent;
                        }
                    }
                }
                // 方法B: 全局搜索 Vue 实例（部分版本暴露）
                if (window.__VUE__ && window.__VUE__.listInfo) {
                    for (const item of window.__VUE__.listInfo) {
                        if (item.server_name === name || item.name === name) {
                            let addr = '';
                            let fixed_ip = '';
                            if (item.addresses && Array.isArray(item.addresses)) {
                                item.addresses.forEach(a => {
                                    if (a.type === 'floating') addr = a.addr || '';
                                    if (a.type === 'fixed') fixed_ip = a.addr || '';
                                });
                            }
                            return {
                                id: item.id || '',
                                server_id: item.server_id || '',
                                server_name: item.server_name || item.name || '',
                                create_time: item.create_time || item.createTime || '',
                                image_id: item.image_id || item.imageId || '',
                                port: item.port || '',
                                addresses: addr,
                                fixed_ip: fixed_ip
                            };
                        }
                    }
                }
                return null;
            }
        """, name)
        return result if result else None

    def _find_server_info_from_api(self, name: str) -> dict | None:
        """通过拦截 API 响应查找实例完整信息（包含所有详情页所需参数）。"""
        result = {"info": None, "done": False}

        def handle_response(response):
            if result["done"] or "/api/" not in response.url:
                return
            try:
                data = response.json()
            except Exception:
                return

            def search(obj):
                if isinstance(obj, dict):
                    if obj.get("server_name") == name or obj.get("name") == name:
                        # 提取浮动IP地址
                        addr = ''
                        fixed_ip = ''
                        addresses = obj.get("addresses", [])
                        if isinstance(addresses, list):
                            for a in addresses:
                                if isinstance(a, dict):
                                    if a.get("type") == "floating":
                                        addr = a.get("addr", "")
                                    if a.get("type") == "fixed":
                                        fixed_ip = a.get("addr", "")
                        result["info"] = {
                            "id": obj.get("id", ""),
                            "server_id": obj.get("server_id", ""),
                            "server_name": obj.get("server_name", obj.get("name", "")),
                            "create_time": obj.get("create_time", obj.get("createTime", "")),
                            "image_id": obj.get("image_id", obj.get("imageId", "")),
                            "port": obj.get("port", ""),
                            "addresses": addr,
                            "fixed_ip": fixed_ip
                        }
                        result["done"] = True
                        return
                    for v in obj.values():
                        search(v)
                        if result["done"]:
                            return
                elif isinstance(obj, list):
                    for item in obj:
                        search(item)
                        if result["done"]:
                            return

            search(data)

        self.page.on("response", handle_response)
        try:
            self.goto_list_page()
            for _ in range(10):
                if self.page.locator(".el-table__row").count() > 0:
                    break
                self.page.wait_for_timeout(2000)
            else:
                self.page.wait_for_selector(".el-table__row", timeout=30000)
            self.page.wait_for_timeout(2000)
        finally:
            try:
                self.page.remove_listener("response", handle_response)
            except Exception:
                pass
        return result["info"]

    def usm_to_details(self, name: str):
        """进入 USM 实例详情页。

        优先点击操作列的"详情"按钮进入详情页（数据最准确），
        若失败则尝试从 Vue 内部数据提取 server_id 直接导航，
        最终兜底使用无参详情页。

        Args:
            name: 实例名称
        """
        base = self.page.url.split("#")[0] if "#" in self.page.url else self.page.url.rstrip("/") + "/"

        # 方法1: 点击操作列的"详情"按钮（最可靠）
        try:
            self.goto_list_page()
            row = self.get_row_by_name(name)
            # 查找操作列中的"详情"按钮/链接
            detail_btn = row.locator("button, a").filter(has_text="详情").first
            if detail_btn.count() == 0:
                # 可能在更多操作菜单中
                more_btn = row.locator("button").filter(has_text="更多").first
                if more_btn.count() > 0:
                    more_btn.click()
                    self.page.wait_for_timeout(800)
                    detail_btn = self.page.locator(".el-dropdown-menu").locator("li, a, button").filter(has_text="详情").first
            if detail_btn.count() > 0:
                with self.page.expect_navigation(timeout=30000):
                    detail_btn.click()
                self.wait_for_detail_page_ready()
                logger.info(f"USM 实例 {name} 进入详情页（操作按钮），URL: {self.page.url}")
                return
        except Exception as e:
            logger.warning(f"USM 实例 {name} 点击详情按钮失败: {e}")

        def _build_detail_url(info: dict) -> str:
            """构建详情页URL，包含所有必要参数。"""
            from urllib.parse import quote
            parts = [f"id={info.get('id', '')}"]
            if info.get("server_id"):
                parts.append(f"server_id={info['server_id']}")
            if info.get("server_name"):
                parts.append(f"server_name={quote(info['server_name'])}")
            if info.get("create_time"):
                parts.append(f"create_time={quote(str(info['create_time']))}")
            if info.get("image_id"):
                parts.append(f"image_id={info['image_id']}")
            if info.get("port"):
                parts.append(f"port={info['port']}")
            if info.get("addresses"):
                parts.append(f"addresses={quote(str(info['addresses']))}")
            if info.get("fixed_ip"):
                parts.append(f"fixed_ip={quote(str(info['fixed_ip']))}")
            return "&".join(parts)

        # 方法2: 从 Vue 内部数据获取完整信息并导航
        server_info = self._find_server_info_from_vue(name)
        if server_info and server_info.get("id"):
            params = _build_detail_url(server_info)
            self.page.goto(f"{base}#/usm-version-detail?{params}")
            self.wait_for_detail_page_ready()
            logger.info(f"USM 实例 {name} 进入详情页（Vue id={server_info.get('id')}），URL: {self.page.url}")
            return

        # 方法3: 通过 API 响应拦截获取完整信息并导航
        server_info = self._find_server_info_from_api(name)
        if server_info and server_info.get("id"):
            params = _build_detail_url(server_info)
            self.page.goto(f"{base}#/usm-version-detail?{params}")
            self.wait_for_detail_page_ready()
            logger.info(f"USM 实例 {name} 进入详情页（API id={server_info.get('id')}），URL: {self.page.url}")
            return

        # 方法4: 尝试点击名称链接（如果可点击）
        try:
            row = self.get_row_by_name(name)
            name_link = row.locator("a").filter(has_text=name).first
            if name_link.count() > 0:
                href = name_link.get_attribute("href")
                if href and ("http" in href or "/usm-version-detail" in href):
                    target = href if href.startswith("http") else f"{base}{href}"
                    self.page.goto(target)
                    self.wait_for_detail_page_ready()
                    logger.info(f"USM 实例 {name} 进入详情页（href），URL: {self.page.url}")
                    return
        except Exception as e:
            logger.warning(f"USM 实例 {name} 点击名称链接失败: {e}")

        # 方法5: 兜底，使用无参详情页
        logger.warning(f"USM 实例 {name} 未找到 server_id，尝试无参详情页")
        self.page.goto(f"{base}#/usm-version-detail")
        self.wait_for_detail_page_ready()
        logger.info(f"USM 实例 {name} 进入详情页（无参），URL: {self.page.url}")

    def usm_get_jump_address_text(self, name: str) -> str:
        """进入实例详情页并获取跳转地址字段的文本内容。

        先在列表页定位实例，再通过点击实例名称进入详情页（保活 Vue 路由上下文），
        查找跳转地址字段的显示内容并返回。

        Args:
            name: 实例名称

        Returns:
            str: 跳转地址字段的文本内容（可能是 URL 链接或警告文案）
        """
        max_retries = 3
        for attempt in range(max_retries):
            self.goto_list_page()
            self._dismiss_visible_dialogs()

            row = self.get_row_by_name(name)
            # 点击实例名称链接进入详情页
            name_link = row.locator("a, span.link").all()
            found = False
            for link in name_link:
                try:
                    link_text = link.inner_text()
                    if name in link_text and link.is_visible():
                        with self.page.expect_navigation(timeout=30000):
                            link.click()
                        found = True
                        break
                except Exception:
                    continue

            if not found:
                # Fallback: 通过 URL 导航
                base = self.page.url.split("#")[0]
                server_info = self._find_server_info_from_vue(name)
                if server_info and server_info.get("id"):
                    from urllib.parse import quote
                    params = f"id={server_info.get('id', '')}&server_id={server_info.get('server_id', '')}"
                    if server_info.get("server_name"):
                        params += f"&server_name={quote(server_info['server_name'])}"
                    self.page.goto(f"{base}#/usm-version-detail?{params}")

            self.wait_for_detail_page_ready()
            self._dismiss_visible_dialogs()
            self.page.wait_for_timeout(2000)

            body_text = self.page.inner_text("body")
            if "跳转地址" in body_text:
                # 提取跳转地址行的文本
                items = self.page.locator("[class*='item-col'], [class*='cl-item-col']").all()
                for item in items:
                    text = item.inner_text()
                    if "跳转地址" in text:
                        logger.info(f"USM 实例 {name} 跳转地址字段内容: {text}")
                        return text
                # 若未单独定位到，返回 body 中包含跳转地址的行
                for line in body_text.split("\n"):
                    if "跳转地址" in line or "公网ip" in line.lower():
                        return line
                return body_text

            logger.warning(f"USM 详情页第 {attempt + 1} 次未找到跳转地址，重试...")

        raise AssertionError(f"USM 实例 {name} 详情页未找到跳转地址字段（已重试 {max_retries} 次）")

    def usm_open_jump_address(self):
        """在详情页提取跳转地址，新标签页打开 USM 平台页面。

        跳转地址有 120 秒失效窗口：若打开后出现 chrome-error，
        会刷新当前详情页获取新的跳转链接后重试。

        绑定公网IP后详情页可能需要时间同步，遇到"未绑定公网IP"时
        会返回列表页重新进入详情页，最多重试10次（约5分钟）。

        Returns:
            Page: Playwright 新页面对象（USM 平台登录页）
        """
        jump_url = None
        no_ip_count = 0
        # 从当前URL提取实例名称（用于重新进入详情页）
        current_name = None
        for extract_attempt in range(1, 12):
            jump_url = self._extract_jump_url()
            if jump_url:
                break

            body_snippet = self.page.inner_text("body")[:2000]
            if "未绑定公网IP" in body_snippet or "暂不可使用" in body_snippet:
                no_ip_count += 1
                logger.warning(
                    f"USM 跳转地址：第 {extract_attempt} 次提取失败，"
                    f"详情页显示'未绑定公网IP暂不可使用'（第{no_ip_count}次），"
                    f"返回列表页重新进入详情页..."
                )
                # 返回列表页刷新数据后再进入详情页
                self.goto_list_page()
                self.page.wait_for_timeout(5000)
                # 尝试从当前URL或页面内容获取实例名称
                if not current_name:
                    url = self.page.url
                    import re
                    # 尝试从URL参数获取server_id对应的名称（不行）
                    # 尝试从页面查找最近操作的实例
                    body = self.page.inner_text("body")
                    for line in body.split("\n"):
                        if "autotest-usm-" in line:
                            match = re.search(r"autotest-usm-[a-z0-9]+", line)
                            if match:
                                current_name = match.group(0)
                                break
                if current_name:
                    self.usm_to_details(current_name)
                    self.page.wait_for_timeout(5000)
                else:
                    self.page.reload()
                    self.wait_for_detail_page_ready()
                    self.page.wait_for_timeout(3000)
                continue

            logger.warning(f"USM 跳转地址：第 {extract_attempt} 次提取失败，等待10秒后重试")
            time.sleep(10)

        if not jump_url:
            body_snippet = self.page.inner_text("body")[:2000]
            logger.debug(f"USM 跳转地址：页面 body 前2000字符: {body_snippet}")
            raise Exception("未找到跳转地址 URL")
        logger.info(f"USM 跳转地址：提取到 URL: {jump_url}")

        for attempt in range(1, 4):
            logger.info(f"USM 跳转地址：第 {attempt} 次尝试打开 {jump_url}")
            new_page = self._open_jump_url(jump_url)

            if new_page is None:
                if attempt < 3:
                    logger.warning(f"USM 跳转地址：第 {attempt} 次未获取到新页面，等待后重试")
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        raise Exception("刷新详情页后未找到新的跳转地址 URL")
                    continue
                raise Exception("未能获取跳转地址打开的新页面")

            # 处理自签名证书警告页面：点击"高级" → "继续前往"
            try:
                new_page.wait_for_timeout(2000)
                # 检查是否是证书警告页
                adv_btn = new_page.get_by_text("高级", exact=False).first
                if adv_btn.count() > 0:
                    try:
                        adv_btn.wait_for(timeout=3000)
                    except Exception:
                        pass
                    if adv_btn.is_visible():
                                        logger.info("USM 跳转地址：检测到证书警告页，点击高级按钮")
                                        adv_btn.click()
                                        new_page.wait_for_timeout(2000)
                                        proceed = new_page.get_by_text(re.compile(r"继续前往|继续访问|Proceed"), exact=False).first
                                        if proceed.count() > 0:
                                            proceed.click()
                                            logger.info("USM 跳转地址：已点击继续前往，等待页面加载")
                                            new_page.wait_for_timeout(10000)
            except Exception:
                pass

            # 快速检测：打开后立刻轮询URL，避免长时间等待已失效的token
            quick_error = False
            for _ in range(15):  # 最多等待15秒
                self.page.wait_for_timeout(1000)
                current_url = new_page.url
                # 证书警告页面通常也以 chrome-error 开头，但上面已处理，这里只检测真正的错误
                if ("chrome-error" in current_url and "chromewebdata" in current_url) or current_url == "about:blank":
                    logger.warning(
                        f"USM 跳转地址：快速检测到错误页面 {current_url}，"
                        f"token 可能已过期或目标不可达"
                    )
                    quick_error = True
                    break
                if current_url and current_url != "about:blank":
                    # URL 已经变成有效地址，提前退出快速检测
                    break

            if quick_error:
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < 3:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("USM 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue
                logger.warning("USM 跳转地址：多次尝试后仍未成功打开 USM 平台登录页，目标服务器可能不可达")
                return None

            # 正常页面才继续等待完整加载（缩短超时，避免token过期）
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                logger.warning("USM 跳转地址：新页面 domcontentloaded 超时")
            try:
                new_page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                logger.warning("USM 跳转地址：新页面 networkidle 超时")

            current_url = new_page.url
            logger.info(f"USM 跳转地址：新页面当前 URL: {current_url}")

            has_dasusm = False
            try:
                das_label = new_page.get_by_text("DASUSM", exact=False).first
                if das_label.count() > 0:
                    try:
                        das_label.wait_for(timeout=5000)
                    except Exception:
                        pass
                    if das_label.is_visible():
                                        has_dasusm = True
                                        logger.info("USM 跳转地址：页面验证通过，包含 DASUSM")
            except Exception:
                pass

            # 验证方式1：URL 包含 USM 平台路径特征
            is_usm_platform = (
                "u-s-m-" in current_url
                or "/dashboard" in current_url
                or "openapiOAuth" in current_url
            )
            # 验证方式2：URL 是 USM 的 IP 地址（172.22.x.x）且不是 chrome-error
            is_usm_ip = (
                "172.22" in current_url
                and "chrome-error" not in current_url
                and "about:blank" not in current_url
            )

            if has_dasusm or is_usm_platform or is_usm_ip:
                logger.info(f"USM 跳转地址：页面验证通过，URL={current_url}")
                return new_page

            # chrome-error / about:blank → 跳转地址可能已过期，刷新详情页获取新链接
            if "chrome-error" in current_url or "about:blank" in current_url:
                logger.warning(f"USM 跳转地址：加载到错误页面 {current_url}，跳转地址可能已过期，刷新详情页获取新链接")
                try:
                    new_page.close()
                except Exception:
                    pass
                if attempt < 3:
                    jump_url = self._refresh_and_get_new_jump_url()
                    if not jump_url:
                        logger.warning("USM 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                        return None
                    continue

            logger.warning("USM 跳转地址：页面未进入 USM 平台，等待后重试")
            try:
                new_page.close()
            except Exception:
                pass
            if attempt < 3:
                jump_url = self._refresh_and_get_new_jump_url()
                if not jump_url:
                    logger.warning("USM 跳转地址：刷新详情页后未找到新的跳转地址 URL")
                    return None
                continue

        logger.warning("USM 跳转地址：多次尝试后仍未成功打开 USM 平台登录页，目标服务器可能不可达")
        return None

    def _refresh_and_get_new_jump_url(self) -> str | None:
        """离开详情页重新进入，强制后端生成新的跳转 token（应对 120s 失效机制）。

        简单的 page.reload() 可能导致页面缓存旧 token，
        这里改用 goto_list_page → usm_to_details 完整重进详情页，
        触发新的 API 请求确保获取到有效 token。
        """
        logger.info("USM 跳转地址：重新进入详情页以获取新的跳转链接...")
        # 保存当前实例名（从 URL 或页面提取）
        name = None
        import re
        url = self.page.url
        name_match = re.search(r"server_name=([^&]+)", url)
        if name_match:
            from urllib.parse import unquote
            name = unquote(name_match.group(1))

        # 离开详情页回列表，等数据刷新后再进详情页
        self.goto_list_page()
        self.page.wait_for_timeout(5000)  # 等列表数据完全加载

        if name:
            self.usm_to_details(name)
        else:
            # 无名称时回退到 reload
            try:
                self.page.reload(wait_until="networkidle", timeout=60000)
            except Exception:
                pass
        self.wait_for_detail_page_ready()

        # 详情页重新加载后等待跳转地址渲染
        for wait_sec in [10, 15, 20]:
            self.page.wait_for_timeout(wait_sec * 1000)
            new_url = self._extract_jump_url()
            if new_url:
                logger.info(f"USM 跳转地址：重进详情页后提取到 URL: {new_url}")
                return new_url
        logger.warning("USM 跳转地址：重进详情页后多次尝试仍未提取到 URL")
        return None

    def _open_jump_url(self, jump_url: str):
        """在新标签页打开跳转 URL，返回新页面对象。"""
        try:
            with self.page.context.expect_page(timeout=120000) as new_page_info:
                self.page.evaluate("url => window.open(url, '_blank')", jump_url)
            return new_page_info.value
        except Exception:
            logger.debug("USM 跳转地址：expect_page 未捕获，尝试从 pages 列表获取")
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

    def verify_jump_page_license_expire(self, page, expected_expire: str):
        """在跳转后的 USM 平台页面验证许可证信息中的过期时间。

        USM 平台 dashboard 页面右下角以标签-值对形式展示许可证信息：
            许可证信息
            客户信息      xxx
            授权类型      正式版
            过期时间      2026-08-20 00:00:00
            维保时间      2026-08-20 00:00:00
        本方法使用 JavaScript 遍历 DOM 文本节点定位"过期时间"标签，
        再比对其容器内的值文本，避免 Playwright  locator 因渲染方式差异而失效。

        Args:
            page: 跳转后的 USM 平台页面对象
            expected_expire: 期望的到期时间字符串（如 "2026-08-20 00:00:00"）
        """
        if not expected_expire or expected_expire == "--":
            logger.info("期望到期时间为空或'--'，跳过跳转页面许可证验证")
            return

        # 提取日期部分用于匹配（页面上可能是完整日期时间，也可能只有日期）
        date_part = expected_expire.split()[0]  # 如 "2026-08-20"

        # 等待页面加载完成（许可证信息可能异步加载，给予充足时间）
        try:
            page.wait_for_load_state("domcontentloaded", timeout=30000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        # 等待 loading spinner 消失
        try:
            page.locator(".el-loading-spinner, .loading, .spinner").first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(8000)  # 许可证信息可能延迟加载

        # 处理项目选择弹窗（若跳转后先弹出"可选项目"）
        try:
            project_dialog = page.locator("text=可选项目, text=项目选择").first
            if project_dialog.count() > 0:
                try:
                    project_dialog.wait_for(timeout=3000)
                except Exception:
                    pass
                if project_dialog.is_visible():
                                for confirm_text in ["确定", "确认", "进入"]:
                                    btn = page.get_by_text(confirm_text, exact=True).first
                                    if btn.count() > 0:
                                        try:
                                            btn.wait_for(timeout=1000)
                                        except Exception:
                                            pass
                                        if btn.is_visible():
                                            btn.click()
                                            page.wait_for_timeout(3000)
                                            logger.info(f"USM 跳转页面：点击项目选择弹窗 '{confirm_text}'")
                                            break
        except Exception:
            pass

        # 滚动到页面底部（许可证信息通常在右下角）
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
        except Exception:
            pass

        # 策略1: 搜索所有元素（含 shadow DOM、iframe）的 innerText，
        # 找包含"过期时间"或"到期时间"的标签，再检查同容器内是否有预期日期
        js_result = page.evaluate("""
            (targetText) => {
                function findInElement(elem) {
                    const text = elem.innerText || elem.textContent || '';
                    if (text.includes('过期时间') || text.includes('到期时间')) {
                        // 检查自身及父级是否包含目标日期
                        let el = elem;
                        for (let i = 0; i < 6 && el; i++) {
                            const t = el.innerText || el.textContent || '';
                            if (t.includes(targetText)) {
                                return { found: true, source: 'element-level-' + i, text: t.slice(0, 500) };
                            }
                            el = el.parentElement;
                        }
                    }
                    // 递归子元素
                    for (const child of elem.children) {
                        const r = findInElement(child);
                        if (r && r.found) return r;
                    }
                    return null;
                }

                // 主文档
                let result = findInElement(document.body);
                if (result) return result;

                // 搜索所有 iframe
                for (const iframe of document.querySelectorAll('iframe')) {
                    try {
                        const doc = iframe.contentDocument || iframe.contentWindow.document;
                        if (doc && doc.body) {
                            result = findInElement(doc.body);
                            if (result) return { ...result, source: result.source + '-iframe' };
                        }
                    } catch (e) {}
                }

                // 搜索所有 shadow DOM
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        result = findInElement(el.shadowRoot);
                        if (result) return { ...result, source: result.source + '-shadow' };
                    }
                }

                // 兜底：全局文本搜索
                const bodyText = document.body.innerText || document.body.textContent || '';
                if ((bodyText.includes('过期时间') || bodyText.includes('到期时间')) && bodyText.includes(targetText)) {
                    return { found: true, source: 'global-text', text: bodyText.slice(0, 500) };
                }

                return { found: false, bodyHasExpire: bodyText.includes('过期时间') || bodyText.includes('到期时间'), bodyHasDate: bodyText.includes(targetText), bodyLength: bodyText.length };
            }
        """, date_part)

        if js_result and js_result.get("found"):
            logger.info(
                f"USM 跳转页面许可证验证通过（{js_result.get('source')}）: "
                f"找到 {date_part}"
            )
            return
        else:
            # 记录调试信息，帮助排查
            debug = js_result or {}
            logger.debug(
                f"USM 跳转页面许可证调试: body含过期时间={debug.get('bodyHasExpire')}, "
                f"body含日期={debug.get('bodyHasDate')}, body长度={debug.get('bodyLength')}"
            )

        # 策略2: 使用 Playwright 正则文本匹配（绕过可能的空格/换行问题）
        try:
            expire_locator = page.get_by_text(re.compile(r"过期时间|到期时间"))
            if expire_locator.count() > 0:
                # 获取包含该文本的所有元素的父级文本
                for i in range(min(expire_locator.count(), 10)):
                    elem = expire_locator.nth(i)
                    for xpath in ["xpath=..", "xpath=../..", "xpath=../../.."]:
                        try:
                            parent = elem.locator(xpath).first
                            if parent.count() > 0:
                                parent_text = parent.inner_text()
                                if date_part in parent_text:
                                    logger.info(
                                        f"USM 跳转页面许可证验证通过（Playwright 正则匹配）: "
                                        f"找到 {date_part}"
                                    )
                                    return
                        except Exception:
                            continue
        except Exception:
            pass

        # 策略3: 页面全局文本搜索（兜底）
        try:
            body_text = page.inner_text("body")
            if ("过期时间" in body_text or "到期时间" in body_text) and date_part in body_text:
                logger.info(
                    f"USM 跳转页面许可证验证通过（页面全局文本）: "
                    f"页面同时含'过期时间/到期时间'和 {date_part}"
                )
                return
        except Exception:
            pass

        # 策略4: 搜索原始 HTML（某些文本可能通过 JS 动态插入但不在 innerText 中）
        try:
            html = page.content()
            if ("过期时间" in html or "到期时间" in html) and date_part in html:
                logger.info(
                    f"USM 跳转页面许可证验证通过（原始 HTML）: "
                    f"HTML 中同时含'过期时间/到期时间'和 {date_part}"
                )
                return
        except Exception:
            pass

        # 策略3: 页面右下角/底部兜底搜索
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
        except Exception:
            pass

        for selector in ["footer", ".footer", "[class*='footer']", "[class*='bottom']"]:
            try:
                elems = page.locator(selector).all()
                for elem in elems:
                    if not elem.is_visible():
                        continue
                    text = elem.inner_text()
                    if "过期时间" in text and date_part in text:
                        logger.info(
                            f"USM 跳转页面许可证验证通过（右下角 {selector}）"
                        )
                        return
            except Exception:
                continue

        # 未找到，记录 warning 但不阻断测试
        logger.warning(
            f"USM 跳转页面许可证验证跳过：未找到包含 {date_part} 的过期时间字段"
        )

    def usm_name_clickable(self, name: str) -> bool:
        """检查列表页 USM 实例名称是否可点击跳转（用于验证关机后不可点击的预期）。

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
            logger.info(f"USM 实例 {name} 名称颜色: {color}, 可点击: {is_link}")
            return is_link
        except Exception as e:
            logger.warning(f"检查 USM 实例 {name} 名称可点击性失败: {e}")
            return False

    def usm_spec_upgrade(self, name: str):
        """执行规格升级：选择比当前规格更高的第一个可选规格并提交。

        规格升级弹窗内只允许选择 vcpu 和 memory_mb 均大于当前规格的选项。
        提交后实例状态变为"升级中"，需调用方轮询等待。

        Args:
            name: 实例名称

        Returns:
            dict: 选中的新规格信息 {'vcpus': int, 'memory_mb': int, 'name': str,
                  'quota_name': str}
        """
        self._dismiss_visible_dialogs()
        self.click_action(name, "规格升级")
        self.page.wait_for_timeout(1500)

        dialog = self.locator(".sugon-dialog:visible").filter(has_text="规格升级").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到规格升级弹窗")
        logger.info("USM 规格升级：弹窗已打开")

        # 验证顶部提示信息
        alert = dialog.locator(".sugon-alert, .el-alert").first
        if alert.count() > 0:
            try:
                alert.wait_for(timeout=3000)
            except Exception:
                pass
            if alert.is_visible():
                        alert_text = alert.inner_text()
                        assert "关机" in alert_text and "再启动" in alert_text, \
                            f"提示信息缺少关机和再启动提醒: {alert_text}"
                        assert "云硬盘" in alert_text, \
                            f"提示信息缺少云硬盘大小提示: {alert_text}"
                        logger.info(f"USM 规格升级：提示信息验证通过")
        else:
            logger.warning("USM 规格升级：未找到 alert 提示信息，跳过验证")

        # 选择第一个可用的（比当前大的）规格
        radio_rows = dialog.locator(".el-table__row").all()
        if len(radio_rows) == 0:
            radio_rows = dialog.locator("tr").all()
        selected_spec = None
        for row in radio_rows:
            radio = row.locator(".el-radio").first
            if radio.count() == 0:
                continue
            # 检查是否被 disabled（class 包含 is-disabled 或 disabled 属性）
            is_disabled = False
            radio_class = radio.get_attribute("class") or ""
            if "is-disabled" in radio_class:
                is_disabled = True
            if not is_disabled:
                # 获取行文本以提取规格信息
                row_text = row.inner_text()
                vcpu_match = re.search(r"(\d+)核", row_text)
                mem_match = re.search(r"(\d+)GiB", row_text)
                spec_name_match = re.search(r"usm\.\S+|usm\S+", row_text)
                quota_match = re.search(r"(\d+)个资产|(\d+)\s*个", row_text)
                selected_spec = {
                    "vcpus": int(vcpu_match.group(1)) if vcpu_match else 0,
                    "memory_mb": int(mem_match.group(1)) * 1024 if mem_match else 0,
                    "name": spec_name_match.group(0) if spec_name_match else "",
                    "quota_name": quota_match.group(0) if quota_match else "",
                }
                radio.evaluate("el => el.click()")
                logger.info(
                    f"USM 规格升级：选中规格 vcpu={selected_spec['vcpus']}核, "
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
        logger.info(f"USM 实例 {name} 规格升级请求已提交")
        return selected_spec

    def usm_get_server_id(self, name: str) -> str | None:
        """进入详情页，从URL中提取 server_id 用于后端 SSH 验证。

        Args:
            name: 实例名称

        Returns:
            str: server_id（UUID格式），若未找到返回 None
        """
        self.usm_to_details(name)
        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"USM 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"USM 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def usm_volume_expand(self, name: str, new_size: int) -> str | None:
        """在详情页执行云硬盘扩容，填写新大小并提交。

        进入实例详情页，找到云硬盘大小字段，修改为目标值后提交，
        轮询等待扩容完成（云硬盘大小字段更新为新值）。

        Args:
            name: 实例名称
            new_size: 目标云硬盘大小（GiB），如 350

        Returns:
            str: server_id（UUID格式），用于后续 SSH 后端验证
        """
        self.usm_to_details(name)
        self.wait_for_detail_page_ready()
        # 等待详情页所有异步数据加载完成（云硬盘字段可能靠后渲染）
        self.page.wait_for_timeout(10000)
        try:
            self.page.wait_for_selector(".el-form-item, .detail-item", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(3000)

        # 获取当前云硬盘大小
        body_text = self.page.inner_text("body")
        logger.info(f"详情页 body 文本 (前1500字符): {body_text[:1500]}")
        vol_match = re.search(r"(\d+)\s*GiB", body_text)
        current_size = int(vol_match.group(1)) if vol_match else None
        logger.info(f"USM 实例 {name} 当前云硬盘大小: {current_size}GiB")

        # 等待 loading mask 消失后再点击扩容
        try:
            self.page.wait_for_selector(".el-loading-mask", state="detached", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(2000)
        # 点击"扩容"
        self.page.get_by_text("扩容", exact=True).first.click(timeout=10000)
        logger.info("USM 云硬盘扩容：已点击扩容")
        # 等弹窗
        self.page.wait_for_selector(".sugon-dialog:visible .el-input__inner", timeout=10000)
        self.page.wait_for_timeout(500)

        # 填新大小
        vol_input = self.page.locator(".sugon-dialog:visible .el-input__inner").first
        vol_input.click()
        self.page.wait_for_timeout(300)
        vol_input.fill("")
        self.page.wait_for_timeout(300)
        vol_input.fill(str(new_size))
        self.page.wait_for_timeout(500)
        logger.info(f"USM 云硬盘扩容：已填写 {new_size}GiB")

        # 点确定
        self.page.locator(".sugon-dialog:visible .cloud-button-btn.cl-btn-primary").first.click()
        logger.info("USM 云硬盘扩容：已点击确定")

        # 轮询等待扩容完成
        self.page.wait_for_timeout(3000)
        start = time.time()
        while time.time() - start < 120:
            self.page.wait_for_timeout(3000)
            body_text = self.page.inner_text("body")
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            updated_size = int(vol_match.group(1)) if vol_match else None
            if updated_size == new_size:
                logger.info(f"USM 实例 {name} 云硬盘扩容完成: {updated_size}GiB")
                break
            logger.debug(f"USM 实例 {name} 云硬盘大小当前: {updated_size}GiB，等待更新到 {new_size}GiB")
        else:
            raise AssertionError(f"USM 实例 {name} 云硬盘扩容超时，期望 {new_size}GiB，当前 {updated_size}GiB")

        # 从 URL 提取 server_id
        url = self.page.url
        match = re.search(r"server_id=([a-f0-9-]+)", url)
        if match:
            server_id = match.group(1)
            logger.info(f"USM 实例 {name} server_id: {server_id}")
            return server_id
        logger.warning(f"USM 实例 {name} 详情页 URL 未找到 server_id 参数: {url}")
        return None

    def usm_vnc_login(self, name: str, vncpwd: str = "000000"):
        """登录 USM 实例 VNC 控制台。

        在列表页点击"登录VNC"，打开新标签页输入密码并确认，
        验证 VNC canvas 渲染成功。

        Args:
            name: USM 实例名称
            vncpwd: VNC 密码，默认为 000000

        Returns:
            Page: VNC 新页面对象
        """
        logger.info(f"USM 实例 {name}：登录 VNC")
        self.goto_list_page()

        # 点击"登录VNC"打开新页面
        with self.new_tab_context(
            trigger_action=lambda: self.click_action(name, "登录VNC")
        ) as new_page:
            # 等待 VNC iframe 加载
            new_page.wait_for_selector("#app iframe", timeout=30000)
            iframe = new_page.locator("#app iframe").content_frame

            # 输入 VNC 密码
            try:
                iframe.get_by_label("Password:").fill(vncpwd)
            except Exception:
                iframe.get_by_label("密码：").fill(vncpwd)
            logger.info(f"USM 实例 {name}：已输入 VNC 密码")

            # 点击确认
            try:
                iframe.get_by_role("button", name="确认").click()
            except Exception:
                iframe.get_by_role("button", name="Send Credentials").click()
            logger.info(f"USM 实例 {name}：已点击 VNC 确认按钮")

            # 等待 canvas 可见
            iframe.locator("canvas").wait_for(state="visible", timeout=30000)
            logger.info(f"USM 实例 {name}：VNC canvas 已可见")

            # 截图保存到 Allure
            screenshot = iframe.locator("canvas").screenshot()
            allure.attach(
                body=screenshot,
                name=f"vnc截图_{name}",
                attachment_type=allure.attachment_type.PNG
            )
            logger.info(f"USM 实例 {name}：VNC 登录成功")
            return new_page

    def usm_hot_migration(self, name: str, target_host: str = None, m_type: str = "手动指定", bandwidth: str = "全速") -> str | None:
        """USM 实例热迁移。

        通过"更多操作"-"热迁移"打开热迁移弹窗，选择调度方式和目标物理机后确认。

        Args:
            name: USM 实例名称
            target_host: 目标物理机名称（如 master01），手动指定时有效
            m_type: 调度方式，"手动指定"或"系统分配"
            bandwidth: 迁移速率，"25%" / "50%" / "75%" / "全速"

        Returns:
            str | None: 实际选择的目标物理机名称，系统分配时返回 None
        """
        self.goto_list_page()
        self._dismiss_visible_dialogs()

        # 点击更多操作 - 热迁移
        self.click_action(name, "热迁移")
        self.page.wait_for_timeout(1500)

        # 等待热迁移弹窗
        dialog = self.page.locator(".el-dialog__wrapper:visible, .sugon-dialog:visible").filter(has_text="热迁移").first
        if dialog.count() == 0 or not dialog.is_visible():
            raise Exception("未找到热迁移弹窗")
        logger.info("USM 热迁移弹窗已打开")

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
            available_hosts = self._get_available_usm_migration_hosts(drawer, exclude_host=None)

            if not available_hosts:
                # 取消并跳过
                drawer.get_by_text("取消").click()
                self.page.wait_for_timeout(800)
                dialog.get_by_text("取消").click()
                pytest.skip("没有可用的物理机可供选择")

            # 选择目标物理机
            if target_host:
                target_host_full = f"{target_host}.cloud.local" if ".cloud.local" not in target_host else target_host
                matched = [h for h in available_hosts if target_host in h or target_host_full in h]
                if matched:
                    drawer.get_by_role("radio", name=matched[0]).click()
                    checked_host = matched[0]
                    logger.info(f"已选择指定的目标物理机: {checked_host}")
                else:
                    logger.warning(f"指定的目标物理机 {target_host} 不可用，选择第一个可用物理机")
                    drawer.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")
            else:
                drawer.get_by_role("radio", name=available_hosts[0]).click()
                checked_host = available_hosts[0]
                logger.info(f"已选择第一个可用的物理机: {checked_host}")

            # 点击确定关闭 drawer（cl-button 组件可能没有 role="button"）
            confirm_btn = drawer.locator(".cloud-button-btn, button").filter(has_text="确定").first
            if confirm_btn.count() == 0 or not confirm_btn.is_visible():
                confirm_btn = self.page.get_by_text("确定").filter(has_text="确定").first
            confirm_btn.click()
            self.page.wait_for_timeout(1000)

        # 选择迁移速率
        if bandwidth != "全速":
            dialog.get_by_placeholder("请选择迁移速率").click()
            self.page.wait_for_timeout(500)
            self.page.locator("li").filter(has_text=bandwidth).click()
            self.page.wait_for_timeout(500)

        # 确认热迁移（cl-button 组件可能没有 role="button"）
        confirm_btn = dialog.locator(".cloud-button-btn, button").filter(has_text="确定").first
        if confirm_btn.count() == 0 or not confirm_btn.is_visible():
            confirm_btn = dialog.get_by_role("button", name="确定")
        confirm_btn.click()
        logger.info(
            f"USM 实例 {name} 热迁移命令已下发: 调度方式={m_type}, "
            f"目标主机={checked_host}, 迁移速率={bandwidth}"
        )
        return checked_host

    def _get_available_usm_migration_hosts(self, drawer, exclude_host: str | None = None) -> list[str]:
        """从物理机选择 drawer 中获取可用的迁移目标物理机列表。

        Args:
            drawer: 物理机选择 drawer 的定位器
            exclude_host: 需要排除的物理机名称（当前实例所在节点）

        Returns:
            list[str]: 可用物理机名称列表
        """
        available_hosts = []
        # 等待表格加载
        self.page.wait_for_timeout(2000)

        # 获取所有行
        all_rows = drawer.locator("tbody tr, .el-table__body-wrapper tr").all()
        logger.info(f"物理机选择弹窗中找到 {len(all_rows)} 个行")

        for row in all_rows:
            try:
                # 获取第一个 td 中的物理机名称
                first_td = row.locator("td").first
                host_name = first_td.inner_text().strip()
                if not host_name:
                    continue

                # 检查是否 disabled（通过 radio 的 disabled 属性或行样式）
                radio = row.locator("input[type='radio']").first
                is_disabled = False
                if radio.count() > 0:
                    is_disabled = radio.is_disabled()

                # 检查行是否有 is-disabled 类
                row_classes = row.evaluate("el => el.className") or ""
                if "is-disabled" in row_classes:
                    is_disabled = True

                if not is_disabled and host_name:
                    if exclude_host and exclude_host in host_name:
                        logger.info(f"排除当前实例所在物理机: {host_name}")
                        continue
                    available_hosts.append(host_name)
            except Exception as e:
                logger.debug(f"解析物理机行失败: {e}")
                continue

        logger.info(f"可用物理机列表: {available_hosts}")
        return available_hosts
