from __future__ import annotations

import re
import time
from typing import Any

from sugon_web.common.base import BasePage
from sugon_web.config.config import Config


class StoragePoolMixin(BasePage):
    """基础设施存储池页面采集能力。"""

    healthy_storage_keywords = ("正常", "已同步", "运行中", "可用")
    abnormal_storage_keywords = ("异常", "失败", "离线", "未同步", "不可用", "错误")

    def goto_storage_pool_list(self) -> None:
        """进入基础设施 -> 存储池页面。"""
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/ops/#/ecs-storage-list")
        self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        self.wait_for_page_ready()
        self.close_dialog_if_exists()
        if not self._wait_storage_pool_page_ready(timeout=20):
            self.logger.warning("存储池页面首次加载未完成，刷新后重试")
            self.page.reload()
            self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
            self.wait_for_page_ready()
            self._wait_storage_pool_page_ready(timeout=20)

    def collect_storage_pools(self) -> dict[str, Any]:
        """采集存储池运行状态和容量摘要。"""
        self.goto_storage_pool_list()
        items = self._collect_all_storage_pool_rows()
        normalized_items = [self._normalize_storage_pool_row(row) for row in items]
        usable_items = [item for item in normalized_items if item["usable"]]
        abnormal_items = [item for item in normalized_items if item["abnormal"]]
        available_values = [
            item["available_gib"]
            for item in usable_items
            if item["available_gib"] is not None
        ]

        return {
            "status": "passed" if usable_items else "failed",
            "total": len(normalized_items),
            "running": len(usable_items),
            "usable": len(usable_items),
            "abnormal": len(abnormal_items),
            "max_available_gib": max(available_values) if available_values else 0,
            "min_available_gib": min(available_values) if available_values else 0,
            "running_names": [item["name"] for item in usable_items],
            "abnormal_names": [item["name"] for item in abnormal_items],
            "items": normalized_items,
            "url": self.page.url,
        }

    def _collect_all_storage_pool_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen_pages: set[str] = set()

        for _ in range(30):
            self.page.wait_for_timeout(500)
            page_rows = self._collect_current_storage_pool_rows()
            page_key = repr(page_rows)
            if page_key in seen_pages:
                break
            seen_pages.add(page_key)
            rows.extend(page_rows)

            if not self._click_next_storage_pool_page():
                break

        deduped: list[dict[str, str]] = []
        seen_names: set[str] = set()
        for row in rows:
            name = row.get("名称") or row.get("name") or repr(row)
            if name in seen_names:
                continue
            seen_names.add(name)
            deduped.append(row)
        return deduped

    def _collect_current_storage_pool_rows(self) -> list[dict[str, str]]:
        return self.page.evaluate(
            """
            () => {
                const tables = Array.from(document.querySelectorAll('table'));
                const target = tables.find(table => {
                    const text = table.innerText || '';
                    return text.includes('可用量') && text.includes('总量') && text.includes('连接状态');
                }) || tables[0];
                if (!target) return [];

                const headers = Array.from(target.querySelectorAll('thead th'))
                    .map(th => th.innerText.trim().replace(/\\s+/g, ' '))
                    .filter(Boolean);
                const rows = [];
                for (const tr of target.querySelectorAll('tbody tr')) {
                    const cells = Array.from(tr.querySelectorAll('td'))
                        .map(td => td.innerText.trim().replace(/\\s+/g, ' '));
                    if (!cells.some(Boolean)) continue;
                    const row = {};
                    cells.forEach((value, index) => {
                        row[headers[index] || `col_${index + 1}`] = value;
                    });
                    rows.push(row);
                }
                return rows;
            }
            """
        )

    def _wait_storage_pool_page_ready(self, timeout: int = 20) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready = self.page.evaluate(
                """
                () => {
                    const text = document.body ? document.body.innerText : '';
                    if (!text || text.includes('加载中')) return false;
                    const hasHeader = text.includes('存储池') && text.includes('可用量') && text.includes('连接状态');
                    const hasRows = Array.from(document.querySelectorAll('tbody tr'))
                        .some(tr => (tr.innerText || '').trim());
                    const hasEmpty = text.includes('暂无数据') || text.includes('没有查询到');
                    return Boolean(hasHeader && (hasRows || hasEmpty));
                }
                """
            )
            if ready:
                return True
            self.page.wait_for_timeout(1000)
        return False

    def _click_next_storage_pool_page(self) -> bool:
        next_button = self.page.locator(".el-pagination .btn-next, button.btn-next").last
        try:
            if next_button.count() == 0 or not next_button.is_visible():
                return False
            class_name = next_button.get_attribute("class") or ""
            disabled = next_button.get_attribute("disabled")
            if "disabled" in class_name or disabled is not None:
                return False
            next_button.click()
            self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
            self.page.wait_for_timeout(1000)
            return True
        except Exception as exc:
            self.logger.warning(f"翻页采集存储池失败: {exc}")
            return False

    def _normalize_storage_pool_row(self, row: dict[str, str]) -> dict[str, Any]:
        name = row.get("名称") or row.get("name") or ""
        storage_type = row.get("类型") or row.get("type") or ""
        protocol = row.get("协议") or row.get("protocol") or ""
        available_text = row.get("可用量") or row.get("available") or ""
        total_text = row.get("总量") or row.get("total") or ""
        config_status = row.get("配置状态") or ""
        connection_status = row.get("连接状态") or ""
        status_text = " ".join([config_status, connection_status])
        abnormal = self._has_any_keyword(status_text, self.abnormal_storage_keywords)
        connected = self._has_any_keyword(connection_status, self.healthy_storage_keywords)
        synced = "已同步" in config_status or not config_status
        available_gib = self._parse_capacity_gib(available_text)

        return {
            "name": name,
            "alias": row.get("别名") or "",
            "type": storage_type,
            "protocol": protocol,
            "available": available_text,
            "available_gib": available_gib,
            "total": total_text,
            "total_gib": self._parse_capacity_gib(total_text),
            "usage": row.get("用途") or "",
            "config_status": config_status,
            "connection_status": connection_status,
            "usable": bool(connected and synced and not abnormal and (available_gib or 0) > 0),
            "abnormal": abnormal,
            "raw": row,
        }

    @staticmethod
    def _has_any_keyword(value: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in value for keyword in keywords)

    @staticmethod
    def _parse_capacity_gib(value: str) -> float | None:
        text = str(value or "").strip()
        if not text or text in {"-", "--"}:
            return None
        match = re.search(r"([\d.]+)\s*([KMGTPE]?i?B|[KMGTPE]?B)", text, re.I)
        if not match:
            return None
        number = float(match.group(1))
        unit = match.group(2).lower()
        factors = {
            "kb": 1 / 1024 / 1024,
            "kib": 1 / 1024 / 1024,
            "mb": 1 / 1024,
            "mib": 1 / 1024,
            "gb": 1,
            "gib": 1,
            "tb": 1024,
            "tib": 1024,
            "pb": 1024 * 1024,
            "pib": 1024 * 1024,
        }
        return round(number * factors.get(unit, 1), 2)
