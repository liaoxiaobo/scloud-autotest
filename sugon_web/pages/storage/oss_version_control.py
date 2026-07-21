"""OSS 多版本控制场景专用的 Page Object 扩展。

继承自 ``OssPage``，补充对象详情页及版本标签页相关操作。
"""

import re

from sugon_web.pages.storage.oss import OssPage
from sugon_web.utils.logger import logger


class OssVersionControlPage(OssPage):
    """OSS 多版本控制场景页面对象。"""

    def _goto_bucket_detail(self, name):
        """进入桶详情页（使用基类 UI 导航）。"""
        self._enter_bucket_detail_via_ui(name)

    def _is_on_object_detail_page(self):
        """检查当前页面是否在对象详情页。"""
        try:
            return self.page.locator(".objectDetail-container").count() > 0
        except Exception:
            return False

    def oss_bucket_enter_object_detail(self, bucket_name, object_name):
        """在对象列表页点击对象名称进入对象详情页。

        Args:
            bucket_name: 桶名称。
            object_name: 对象名称。
        """
        # 确保在对象列表页
        self.oss_bucket_object_tab_click()
        self.page.wait_for_timeout(3000)

        # 关闭可能打开的任务列表面板（避免遮挡行定位）
        self._close_task_list_panel_if_exists()

        # 原生点击对象名称
        object_link = self.page.locator(
            ".el-table__body-wrapper tr, .table-main tr"
        ).filter(
            has_text=re.compile(rf"\b{re.escape(object_name)}\b")
        ).first.locator(
            "span"
        ).filter(
            has_text=re.compile(rf"\b{re.escape(object_name)}\b")
        ).first

        if object_link.count() > 0:
            object_link.click()
            self.page.wait_for_timeout(5000)
            if self._is_on_object_detail_page():
                logger.info(
                    f"[EnterObjectDetail] 原生点击进入对象详情页成功，当前URL: {self.page.url}"
                )
                return

        # 兜底：在表格行内查找对象名并点击
        row = self.page.locator(".el-table__row").filter(has_text=object_name).first
        if row.count() > 0:
            link = row.locator("span").filter(has_text=object_name).first
            if link.count() > 0:
                link.click()
                self.page.wait_for_timeout(5000)
                if self._is_on_object_detail_page():
                    return

        raise AssertionError(
            f"对象 {object_name} 未找到或无法进入详情页 | 当前URL: {self.page.url}"
        )

    def _close_task_list_panel_if_exists(self):
        """关闭任务列表面板（如果存在）。"""
        try:
            panel = self.page.locator(".el-drawer__wrapper, .task-list-panel").first
            if panel.count() > 0 and panel.is_visible():
                close = panel.locator(".el-drawer__close-btn, .el-drawer__headerbtn, .close-btn").first
                if close.count() > 0:
                    close.click()
                    self.page.wait_for_timeout(1000)
        except Exception:
            pass

    def oss_bucket_object_detail_click_version_tab(self):
        """在对象详情页点击"版本"标签页。"""
        version_tab = self.page.locator(".el-tabs__nav").get_by_text("版本").first
        if version_tab.count() == 0:
            version_tab = self.page.get_by_text("版本", exact=True).first
        version_tab.click()
        # 等待版本列表组件渲染及数据加载
        self.page.wait_for_timeout(3000)
        try:
            self.page.wait_for_selector(
                ".objectVersion-container", timeout=10000
            )
        except Exception:
            logger.warning(
                f"[ClickVersionTab] 未检测到版本列表容器，当前URL: {self.page.url}"
            )

    def oss_bucket_object_detail_get_version_count(self):
        """获取对象详情页"版本"标签页中展示的对象版本数量。

        Returns:
            int: 版本数量（仅统计有效数据行，不含表头和空数据占位）。
        """
        # 等待版本列表加载完成（含 loading 消失）
        try:
            self.page.wait_for_selector(
                ".objectVersion-container .el-table__body-wrapper .el-table__row",
                timeout=15000,
            )
        except Exception:
            logger.warning("[VersionCount] 未检测到版本表格行")
            return 0

        try:
            self.page.wait_for_selector(
                ".objectVersion-container .el-loading-mask",
                state="hidden",
                timeout=15000,
            )
        except Exception:
            pass

        self.page.wait_for_timeout(2000)

        rows = self.page.locator(
            ".objectVersion-container .el-table__body-wrapper .el-table__row"
        ).all()
        valid_rows = [row for row in rows if row.locator("td").count() > 0]
        logger.info(f"[VersionCount] 检测到 {len(valid_rows)} 个版本")
        return len(valid_rows)
