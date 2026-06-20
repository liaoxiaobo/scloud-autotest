from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from sugon_web.common.base import BasePage
from sugon_web.config.config import Config


class InspectionMixin(BasePage):
    """运维一键巡检页面能力。

    正常路径为：登录后进入“运维”服务，点击左侧“一键巡检”，再点击
    “重新执行巡检”。这里避免使用“巡检”这类宽泛文本，防止误入巡检大盘。
    """

    inspection_menu_keywords = ("一键巡检",)
    inspection_start_keywords = ("开始巡检", "重新执行巡检", "重新巡检", "立即巡检", "执行巡检")
    critical_inspection_keywords = (
        "管理节点系统盘已用容量检查",
        "管理节点缓存盘已用容量检查",
        "核心Pod检查",
        "AnhanDB检查",
        "ETCD检查",
        "HAProxy状态检查",
        "kubelet状态检查",
        "ipmitool检查",
        "防火墙状态检查",
        "物理机管理网丢包检查",
        "物理机业务网丢包检查",
        "管理网VIP检查",
        "存储池容量检查",
    )

    def goto_one_click_inspection(self) -> None:
        """进入运维一键巡检页面。"""
        self.goto_service("运维", force=True)
        self.close_dialog_if_exists()
        self.wait_for_page_ready()

        if self._click_one_click_inspection_menu():
            return

        base_url = Config.get("base_url").rstrip("/")
        candidates = (
            f"{base_url}/cms/#/inspection",
            f"{base_url}/cms/#/inspection/index",
            f"{base_url}/cms/#/health-inspection",
            f"{base_url}/cms/#/one-click-inspection",
        )
        for url in candidates:
            self.page.goto(url)
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            self.page.wait_for_timeout(2000)
            if self._is_one_click_inspection_page():
                return

        raise AssertionError(f"未找到运维一键巡检入口，当前URL: {self.page.url}")

    def run_one_click_inspection(self, timeout: int = 600_000) -> dict[str, Any]:
        """触发一键巡检并返回页面结果摘要。"""
        self.goto_one_click_inspection()
        before_url = self.page.url

        clicked = self._click_inspection_start_button()

        if not clicked:
            raise AssertionError(f"未找到一键巡检启动按钮，当前URL: {self.page.url}")

        self._wait_inspection_finished(timeout=timeout)
        result = self.collect_inspection_result()
        result["url"] = self.page.url
        result["started"] = clicked
        result["source_url"] = before_url
        return result

    def collect_inspection_result(self) -> dict[str, Any]:
        """从当前巡检页面提取结果表格和状态统计。"""
        rows = self.page.evaluate(
            """
            () => {
                const tables = Array.from(document.querySelectorAll('table'));
                const output = [];
                for (const table of tables) {
                    const headers = Array.from(table.querySelectorAll('thead th'))
                        .map(th => th.innerText.trim()).filter(Boolean);
                    for (const tr of table.querySelectorAll('tbody tr')) {
                        const cells = Array.from(tr.querySelectorAll('td'))
                            .map(td => td.innerText.trim());
                        if (!cells.some(Boolean)) continue;
                        const row = {};
                        cells.forEach((value, index) => {
                            row[headers[index] || `col_${index + 1}`] = value;
                        });
                        output.push(row);
                    }
                }
                return output;
            }
            """
        )

        abnormal_items = self._collect_abnormal_inspection_items()
        critical_failed_items = [
            item for item in abnormal_items
            if self._is_critical_inspection_item(item)
        ]
        ignored_failed_items = [
            item for item in abnormal_items
            if not self._is_critical_inspection_item(item)
        ]

        raw_failed = self._count_rows_by_keywords(rows, ("失败", "异常", "不通过", "Fail", "ERROR"))
        row_warnings = self._count_rows_by_keywords(rows, ("告警", "警告", "Warning", "WARN"))
        passed = self._count_rows_by_keywords(rows, ("成功", "正常", "通过", "Pass", "OK"))
        failed = len(critical_failed_items)
        warnings = len(ignored_failed_items) + row_warnings

        if critical_failed_items:
            status = "failed"
        elif ignored_failed_items or warnings > 0:
            status = "warning"
        elif passed > 0 or raw_failed == 0:
            status = "passed"
        else:
            status = "unknown"

        return {
            "status": status,
            "total": len(rows),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "raw_failed": raw_failed,
            "critical_failed_items": critical_failed_items,
            "ignored_failed_items": ignored_failed_items,
            "abnormal_items": abnormal_items,
            "critical_items": list(self.critical_inspection_keywords),
            "items": rows,
        }

    def write_inspection_result(self, path: str | Path, result: dict[str, Any]) -> Path:
        """保存巡检结果 JSON，供 preflight 健康统计脚本消费。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def _click_one_click_inspection_menu(self) -> bool:
        """点击左侧菜单中的“一键巡检”。"""
        try:
            self.goto_submenu("一键巡检")
            if self._is_one_click_inspection_page():
                return True
        except Exception as exc:
            self.logger.warning(f"通过标准子菜单进入一键巡检失败: {exc}")

        try:
            menu_left = self.page.locator("#cloud-menu-left")
            if menu_left.count() > 0:
                # 展开所有可展开父节点，确保“一键巡检”不被折叠隐藏。
                parents = menu_left.locator(".one-tree-parent-node")
                for index in range(parents.count()):
                    parent = parents.nth(index)
                    try:
                        if not parent.evaluate("el => el.classList.contains('one-tree-expand')"):
                            parent.click()
                            self.page.wait_for_timeout(300)
                    except Exception:
                        continue

                item = menu_left.get_by_text("一键巡检", exact=True).first
                if item.count() > 0 and item.is_visible(timeout=5000):
                    item.click()
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    self.page.wait_for_timeout(2000)
                    return self._is_one_click_inspection_page()
        except Exception as exc:
            self.logger.warning(f"点击左侧一键巡检菜单失败: {exc}")

        return False

    def _is_one_click_inspection_page(self) -> bool:
        try:
            text = self.page.locator("body").inner_text(timeout=3000)
        except Exception:
            return False
        return "一键巡检" in text and (
            "开始巡检" in text
            or "重新执行巡检" in text
            or "执行巡检" in text
            or "巡检结果" in text
            or "巡检项" in text
        )

    def _click_inspection_start_button(self) -> bool:
        """点击“开始巡检”或“重新执行巡检”按钮。"""
        for keyword in self.inspection_start_keywords:
            candidates = (
                self.page.get_by_role("button", name=re.compile(keyword)).first,
                self.page.locator("button, .cloud-button-btn").filter(has_text=re.compile(keyword)).first,
                self.page.get_by_text(keyword, exact=True).first,
            )
            for candidate in candidates:
                try:
                    if candidate.count() > 0 and candidate.is_visible(timeout=3000):
                        candidate.click()
                        self._confirm_inspection_dialog_if_exists()
                        self.logger.info(f"已点击一键巡检启动按钮: {keyword}")
                        return True
                except Exception:
                    continue

        clicked = self.page.evaluate(
            """(keywords) => {
                const selectors = ['button', '.cloud-button-btn', 'a', 'span'];
                for (const keyword of keywords) {
                    for (const selector of selectors) {
                        for (const el of document.querySelectorAll(selector)) {
                            const text = (el.innerText || el.textContent || '').trim();
                            if (text === keyword || text.includes(keyword)) {
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                if (
                                    style.display !== 'none' &&
                                    style.visibility !== 'hidden' &&
                                    rect.width > 0 &&
                                    rect.height > 0
                                ) {
                                    el.click();
                                    return keyword;
                                }
                            }
                        }
                    }
                }
                return null;
            }""",
            list(self.inspection_start_keywords),
        )
        if clicked:
            self._confirm_inspection_dialog_if_exists()
            self.logger.info(f"已通过 DOM 兜底点击一键巡检启动按钮: {clicked}")
            return True
        return False

    def _confirm_inspection_dialog_if_exists(self) -> None:
        """确认重新执行巡检弹窗。"""
        dialog = self.page.locator(".el-message-box:visible, .el-dialog:visible, [role='dialog']:visible").last
        try:
            if dialog.count() == 0 or not dialog.is_visible(timeout=2000):
                return
            confirm = dialog.locator("button, .cloud-button-btn").filter(
                has_text=re.compile(r"确定|确认|执行|重新执行")
            ).last
            if confirm.count() > 0 and confirm.is_visible(timeout=2000):
                confirm.click()
                self.page.wait_for_timeout(1000)
        except Exception as exc:
            self.logger.warning(f"确认重新执行巡检弹窗失败，继续等待巡检结果: {exc}")

    def _wait_inspection_finished(self, timeout: int) -> None:
        deadline = time.time() + timeout / 1000
        running_pattern = re.compile(r"巡检中|执行中|检查中|运行中|loading", re.I)
        finished_pattern = re.compile(r"巡检完成|检查完成|执行完成|重新执行巡检|导出巡检报告", re.I)

        while time.time() < deadline:
            try:
                text = self.page.locator("body").inner_text(timeout=3000)
            except PlaywrightTimeoutError:
                text = ""

            if finished_pattern.search(text) and not running_pattern.search(text):
                self.page.wait_for_timeout(1500)
                return
            self.page.wait_for_timeout(3000)

        raise TimeoutError(f"等待一键巡检完成超时: {timeout}ms")

    @staticmethod
    def _count_rows_by_keywords(rows: list[dict[str, Any]], keywords: tuple[str, ...]) -> int:
        pattern = re.compile("|".join(re.escape(keyword) for keyword in keywords), re.I)
        count = 0
        for row in rows:
            if pattern.search(" ".join(str(value) for value in row.values())):
                count += 1
        return count

    def _collect_abnormal_inspection_items(self) -> list[str]:
        """采集异常项页签下的巡检项名称。"""
        try:
            abnormal_tab = self.page.get_by_text(re.compile(r"异常项\s*\(\d+\)|异常项")).first
            if abnormal_tab.count() > 0 and abnormal_tab.is_visible():
                abnormal_tab.click()
                self.page.wait_for_timeout(800)
        except Exception as exc:
            self.logger.warning(f"切换一键巡检异常项页签失败，继续从当前页面采集: {exc}")

        items = self.page.evaluate(
            """
            () => {
                const names = new Set();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && rect.width > 0
                        && rect.height > 0;
                };
                const pattern = /[\\u4e00-\\u9fa5A-Za-z0-9（）()\\-]+?检查/g;
                for (const el of document.querySelectorAll('span, div, li, td, label, p')) {
                    if (!visible(el)) continue;
                    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, '');
                    if (!text || text.length > 120 || !text.includes('检查')) continue;
                    const matches = text.match(pattern) || [];
                    for (const name of matches) {
                        if (name.length >= 4 && name.length <= 40) {
                            names.add(name);
                        }
                    }
                }
                return Array.from(names);
            }
            """
        )
        return sorted(set(str(item).strip() for item in items if str(item).strip()))

    def _is_critical_inspection_item(self, item_name: str) -> bool:
        return any(keyword in item_name for keyword in self.critical_inspection_keywords)
