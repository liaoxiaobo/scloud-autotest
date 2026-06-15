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

    该页面在不同版本中的路由和按钮文案可能略有差异，因此这里优先走菜单文本，
    再用常见 hash 路由兜底。
    """

    inspection_menu_keywords = ("一键巡检", "健康巡检", "巡检中心", "巡检")
    inspection_start_keywords = ("一键巡检", "开始巡检", "立即巡检", "执行巡检", "重新巡检")

    def goto_one_click_inspection(self) -> None:
        """进入运维巡检页面。"""
        self.goto_service("运维")
        self.close_dialog_if_exists()
        self.wait_for_page_ready()

        for keyword in self.inspection_menu_keywords:
            locator = self.page.get_by_text(keyword, exact=False).first
            try:
                if locator.count() > 0 and locator.is_visible(timeout=3000):
                    locator.click()
                    self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    self.page.wait_for_timeout(2000)
                    return
            except Exception:
                continue

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
            if self._has_inspection_signals():
                return

        raise AssertionError(f"未找到运维一键巡检入口，当前URL: {self.page.url}")

    def run_one_click_inspection(self, timeout: int = 600_000) -> dict[str, Any]:
        """触发一键巡检并返回页面结果摘要。"""
        self.goto_one_click_inspection()
        before_url = self.page.url

        clicked = False
        for keyword in self.inspection_start_keywords:
            button = self.page.locator("button, .cloud-button-btn, a, span").filter(
                has_text=re.compile(keyword)
            ).first
            try:
                if button.count() > 0 and button.is_visible(timeout=3000):
                    button.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            self.logger.warning("未找到巡检启动按钮，将尝试直接读取当前页面已有巡检结果")

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

        page_text = self.page.locator("body").inner_text(timeout=10_000)
        failed = self._count_rows_by_keywords(rows, ("失败", "异常", "不通过", "Fail", "ERROR"))
        warnings = self._count_rows_by_keywords(rows, ("告警", "警告", "Warning", "WARN"))
        passed = self._count_rows_by_keywords(rows, ("成功", "正常", "通过", "Pass", "OK"))

        if failed > 0 or re.search(r"失败|异常|不通过|ERROR", page_text, re.I):
            status = "failed"
        elif warnings > 0 or re.search(r"告警|警告|WARN", page_text, re.I):
            status = "warning"
        elif passed > 0 or re.search(r"成功|正常|通过|OK", page_text, re.I):
            status = "passed"
        else:
            status = "unknown"

        return {
            "status": status,
            "total": len(rows),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "items": rows,
        }

    def write_inspection_result(self, path: str | Path, result: dict[str, Any]) -> Path:
        """保存巡检结果 JSON，供 preflight 健康统计脚本消费。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def _has_inspection_signals(self) -> bool:
        try:
            text = self.page.locator("body").inner_text(timeout=3000)
        except Exception:
            return False
        return any(keyword in text for keyword in self.inspection_menu_keywords)

    def _wait_inspection_finished(self, timeout: int) -> None:
        deadline = time.time() + timeout / 1000
        running_pattern = re.compile(r"巡检中|执行中|检查中|运行中|loading", re.I)
        finished_pattern = re.compile(r"完成|成功|正常|异常|失败|告警|通过|不通过|OK|WARN|ERROR", re.I)

        while time.time() < deadline:
            try:
                text = self.page.locator("body").inner_text(timeout=3000)
            except PlaywrightTimeoutError:
                text = ""

            if finished_pattern.search(text) and not running_pattern.search(text):
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
