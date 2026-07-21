"""对象存储 OSS 对象 ACL 管理页面对象。"""

from sugon_web.common.base import BasePage
from sugon_web.pages.storage.oss import OssPage
from sugon_web.utils.logger import logger


class OssObjectAclPage(BasePage):
    """对象存储 OSS 对象 ACL 管理页面对象。

    负责对象详情页中"对象 ACL" tab 的导航、新增/编辑/删除账号权限
    以及相关断言封装。
    """

    service_name = "对象存储"

    def goto_service(self, service: str, force: bool = False):
        """重写服务导航，OSS 微前端通过 OssPage 落到桶列表页。

        Args:
            service: 服务名称。
            force: 是否强制重新导航。

        Returns:
            OssObjectAclPage: 当前页面对象实例。
        """
        if service == self.service_name:
            OssPage(self.page).goto_service(service, force=force)
            return self
        return super().goto_service(service, force=force)

    # ── 导航 ──

    def oss_object_acl_goto_page(self, bucket_name: str, object_name: str):
        """导航到指定桶/对象的对象 ACL 管理页面。

        导航链：OSS 桶列表 -> 点击桶名进入详情 -> 切换到"对象" tab ->
        点击对象名进入对象详情页（默认展示"对象 ACL" tab）。

        Args:
            bucket_name: 桶名称。
            object_name: 对象名称。
        """
        oss_page = OssPage(self.page)
        oss_page.oss_bucket_goto_object_tab_via_ui(bucket_name)
        self._click_object_name(object_name)
        self._wait_for_acl_container()

    def _click_object_name(self, object_name: str):
        """在对象列表中点击指定对象名称进入对象详情页。

        Args:
            object_name: 对象名称。
        """
        object_list = self.page.locator(".object-list-page-container").first
        link = object_list.get_by_text(object_name, exact=True).first
        link.wait_for(state="visible", timeout=15000)
        link.click(timeout=10000)
        self.wait_for_page_ready()

    def _wait_for_acl_container(self):
        """等待对象 ACL 容器渲染完成。"""
        container = self.page.locator(".object-ACL-container").first
        container.wait_for(state="visible", timeout=15000)
        # 等待列表加载动画消失（如有）
        loading = container.locator(".el-loading-mask").first
        if loading.count() > 0:
            loading.wait_for(state="hidden", timeout=15000)

    def _acl_container(self):
        """返回对象 ACL 容器定位器。"""
        return self.page.locator(".object-ACL-container").first

    # ── 对象 ACL 列表操作 ──

    def oss_object_acl_click_new(self):
        """点击对象 ACL 列表的"新建"按钮。"""
        btn = self._acl_container().get_by_text("新建", exact=True).first
        btn.click(timeout=10000)

    def _find_acl_row(self, account_id: str):
        """在对象 ACL 列表（普通账号权限表）中查找指定账号 ID 所在行。

        使用 Playwright 自动轮询等待行渲染，避免列表异步刷新时断言过早执行。

        Args:
            account_id: 账号 ID。

        Returns:
            Locator: 匹配到的表格行定位器。
        """
        self._wait_for_acl_container()
        container = self._acl_container()
        table = container.locator(".el-table").first
        row = table.locator(".el-table__body-wrapper .el-table__row").filter(
            has_text=account_id
        ).first
        row.wait_for(state="visible", timeout=15000)
        return row

    def _get_acl_rows(self):
        """获取对象 ACL 列表（tableData1）中所有数据行。

        Returns:
            list[Locator]: 表格行定位器列表。
        """
        container = self._acl_container()
        # 对象 ACL 容器内第一个 el-table 为普通账号权限表
        table = container.locator(".el-table").first
        return table.locator(".el-table__body-wrapper .el-table__row").all()

    def oss_object_acl_click_row_edit(self, account_id: str):
        """点击指定账号 ACL 行的"编辑"操作。

        Args:
            account_id: 账号 ID。
        """
        self._click_row_action(account_id, "编辑")

    def oss_object_acl_click_row_delete(self, account_id: str):
        """点击指定账号 ACL 行的"删除"操作。

        Args:
            account_id: 账号 ID。
        """
        self._click_row_action(account_id, "删除")

    def _click_row_action(self, account_id: str, action_name: str):
        """点击指定账号 ACL 行的操作项（编辑/删除）。

        对象 ACL 表格的行操作在真实渲染态下为可直接点击的按钮/链接，
        优先在行作用域内按文案点击；若未命中再回退到下拉菜单展开方式。

        Args:
            account_id: 账号 ID。
            action_name: 操作名称，如"编辑"、"删除"。
        """
        row = self._find_acl_row(account_id)
        action = row.get_by_text(action_name, exact=True).first
        if action.count() > 0:
            action.click(timeout=10000)
            return

        # 回退：下拉菜单触发方式
        operation_btn = row.locator(".cl-table-dropdown, .el-dropdown, .cloud-table-dropdown").first
        operation_btn.click(timeout=10000)
        menu = self.page.locator(
            ".el-dropdown-menu:visible, .cloud-table-dropdown-menu:visible, .cl-table-dropdown-menu:visible"
        ).first
        if menu.count() == 0:
            menu = self.page.locator(
                ".el-dropdown-menu, .cloud-table-dropdown-menu, .cl-table-dropdown-menu"
            ).filter(has=self.page.get_by_text(action_name, exact=True)).first
        menu_item = menu.get_by_text(action_name, exact=True).first
        menu_item.click(timeout=10000)

    # ── 新增/编辑弹窗 ──

    def _acl_dialog(self, title: str | None = None):
        """定位对象 ACL 新增/编辑弹窗。

        Args:
            title: 弹窗标题，如"新增账号权限"、"编辑账号权限"。

        Returns:
            Locator: 弹窗定位器。
        """
        if title:
            return self.page.locator(".el-dialog").filter(
                has=self.page.get_by_text(title, exact=True)
            ).first
        return self.page.locator(".el-dialog").filter(
            has=self.page.locator(".el-dialog__title")
        ).first

    def oss_object_acl_dialog_fill_account(self, account_id: str):
        """在新增/编辑账号权限弹窗中填写账号 ID。

        Args:
            account_id: 账号 ID。
        """
        dialog = self._acl_dialog()
        input_el = dialog.locator("input.el-input__inner").first
        input_el.fill(account_id)

    def oss_object_acl_dialog_check_permission(self, section: str, name: str):
        """在弹窗中勾选指定权限。

        Args:
            section: 权限分组，"对象访问权限" 或 "ACL访问权限"。
            name: 权限名称，"读取权限" 或 "写入权限"。
        """
        self._toggle_permission(section, name, check=True)

    def oss_object_acl_dialog_uncheck_permission(self, section: str, name: str):
        """在弹窗中取消勾选指定权限。

        Args:
            section: 权限分组，"对象访问权限" 或 "ACL访问权限"。
            name: 权限名称，"读取权限" 或 "写入权限"。
        """
        self._toggle_permission(section, name, check=False)

    def _toggle_permission(self, section: str, name: str, check: bool):
        """切换弹窗中指定权限的勾选状态。

        Args:
            section: 权限分组。
            name: 权限名称。
            check: True 为勾选，False 为取消勾选。
        """
        dialog = self._acl_dialog()
        section_item = dialog.locator(".el-form-item").filter(
            has=self.page.get_by_text(section, exact=True)
        ).first
        checkbox = section_item.locator(".el-checkbox").filter(
            has=self.page.get_by_text(name, exact=True)
        ).first

        checkbox_input = checkbox.locator(".el-checkbox__input").first
        is_checked = "is-checked" in (checkbox_input.get_attribute("class") or "")

        if check and not is_checked:
            checkbox.click(timeout=10000)
        elif not check and is_checked:
            checkbox.click(timeout=10000)

    def oss_object_acl_dialog_click_confirm(self):
        """点击弹窗"确定"按钮并等待弹窗关闭。"""
        dialog = self._acl_dialog()
        confirm_btn = dialog.get_by_text("确定", exact=True).first
        confirm_btn.click(timeout=10000)
        dialog.wait_for(state="hidden", timeout=15000)

    def oss_object_acl_dialog_is_visible(self, title: str | None = None) -> bool:
        """判断对象 ACL 弹窗是否可见。

        Args:
            title: 弹窗标题，可选。

        Returns:
            bool: 可见返回 True，否则 False。
        """
        try:
            dialog = self._acl_dialog(title)
            dialog.wait_for(state="visible", timeout=5000)
            return dialog.is_visible()
        except Exception:
            return False

    # ── 删除确认弹窗 ──

    def oss_object_acl_click_delete_confirm(self):
        """在删除确认弹窗中点击"确定"并等待弹窗关闭。

        兼容 el-dialog / cv-dialog / el-message-box / SugonDeleteDialog 等多种确认弹窗形态。
        """
        dialog_selectors = [
            ".cv-dialog:visible",
            ".el-dialog:visible",
            ".el-message-box:visible",
            ".sugon-dialog:visible",
            ".cl-dialog:visible",
            "[role='dialog']:visible",
        ]
        dialog = None
        for selector in dialog_selectors:
            candidate = self.page.locator(selector).filter(
                has=self.page.get_by_text("确定", exact=True)
            ).first
            try:
                candidate.wait_for(state="visible", timeout=3000)
                dialog = candidate
                break
            except Exception:
                continue

        if dialog is None:
            # 兜底：任意包含"确定"+"取消"的可见弹窗/面板
            dialog = self.page.locator("*").filter(
                has=self.page.get_by_text("确定", exact=True)
            ).filter(
                has=self.page.get_by_text("取消", exact=True)
            ).filter(visible=True).first
            dialog.wait_for(state="visible", timeout=10000)

        confirm_btn = dialog.get_by_text("确定", exact=True).first
        confirm_btn.click(timeout=10000)
        dialog.wait_for(state="hidden", timeout=15000)

    # ── 断言 ──

    def oss_object_acl_assert_account_permissions(
        self,
        account_id: str,
        object_permission: list[str],
        acl_permission: list[str],
    ):
        """断言指定账号的对象访问权限和 ACL 访问权限。

        Args:
            account_id: 账号 ID。
            object_permission: 期望的对象访问权限列表，如 ["读取权限"]。
            acl_permission: 期望的 ACL 访问权限列表，如 ["读取权限"]。
        """
        row = self._find_acl_row(account_id)
        cells = row.locator("td").all()
        if len(cells) < 3:
            raise AssertionError(f"账号 {account_id} 的 ACL 行缺少权限列")

        actual_object = self._read_permission_tags(cells[1])
        actual_acl = self._read_permission_tags(cells[2])

        expected_object = [self._normalize_permission_name(p) for p in object_permission]
        expected_acl = [self._normalize_permission_name(p) for p in acl_permission]

        assert actual_object == expected_object, (
            f"账号 {account_id} 对象访问权限不一致: 期望 {expected_object}, 实际 {actual_object}"
        )
        assert actual_acl == expected_acl, (
            f"账号 {account_id} ACL 访问权限不一致: 期望 {expected_acl}, 实际 {actual_acl}"
        )

    def oss_object_acl_assert_account_not_exists(self, account_id: str):
        """断言指定账号的 ACL 记录已不在列表中。

        Args:
            account_id: 账号 ID。
        """
        rows = self._get_acl_rows()
        for row in rows:
            text = (row.locator("td").first.inner_text() or "").strip()
            if text == account_id:
                raise AssertionError(f"账号 {account_id} 的 ACL 记录仍存在列表中")

    def _read_permission_tags(self, cell) -> list[str]:
        """读取权限单元格中所有 el-tag 文本。

        Args:
            cell: 单元格定位器。

        Returns:
            list[str]: 权限文本列表（已标准化）。
        """
        tags = cell.locator(".el-tag").filter(visible=True).all_inner_texts()
        result = []
        for tag in tags:
            text = tag.strip()
            if text and text != "--":
                result.append(self._normalize_permission_name(text))
        return result

    @staticmethod
    def _normalize_permission_name(name: str) -> str:
        """标准化权限显示名称。

        前端过滤器将 READ/READ_ACP 显示为"读权限"，WRITE/WRITE_ACP 显示为"写权限"；
        同时兼容传入的"读取权限"/"写入权限"。

        Args:
            name: 原始权限名称。

        Returns:
            str: 标准化后的权限名称。
        """
        mapping = {
            "读取权限": "读权限",
            "写入权限": "写权限",
            "读权限": "读权限",
            "写权限": "写权限",
            "完全控制": "完全控制",
        }
        return mapping.get(name.strip(), name.strip())

    # ── 清理 ──

    def oss_object_acl_delete_all(self, bucket_name: str, object_name: str):
        """删除指定对象下所有普通账号 ACL 记录（用于 teardown 兜底清理）。

        Args:
            bucket_name: 桶名称。
            object_name: 对象名称。
        """
        try:
            self.oss_object_acl_goto_page(bucket_name, object_name)
        except Exception as e:
            logger.warning(f"导航到对象 ACL 页面失败，跳过 ACL 清理: {e}")
            return

        for _ in range(20):
            rows = self._get_acl_rows()
            if not rows:
                break
            account_id = (rows[0].locator("td").first.inner_text() or "").strip()
            if not account_id:
                break
            try:
                self.oss_object_acl_click_row_delete(account_id)
                self.oss_object_acl_click_delete_confirm()
                self.wait_for_operation_complete(timeout=30)
            except Exception as e:
                logger.warning(f"删除账号 {account_id} 的 ACL 失败: {e}")
                break
