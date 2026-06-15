from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import allure
import pytest

from sugon_web.pages.cms import CmsPage
from sugon_web.tools.preflight.health import evaluate_health_env, load_health_rules
from sugon_web.tools.preflight.suites import filter_health_rules, load_suites, resolve_suite


@pytest.fixture(scope="function")
def cms_page(page):
    """初始化运维页面对象。"""
    return CmsPage(page)


@pytest.mark.preflight
@pytest.mark.preflight_health
@pytest.mark.preflight_frontend
@pytest.mark.preflight_backend
@pytest.mark.preflight_inspection
@allure.feature("环境前置检查")
@allure.story("运维一键巡检")
def test_ops_one_click_inspection(cms_page, config, ssh_host):
    """运行运维一键巡检，采集后台健康项，并保存统一结果。"""
    inspection = cms_page.run_one_click_inspection()
    backend = _collect_backend_health(ssh_host)
    snapshot = {
        "frontend": {
            "reachable": True,
            "login": True,
            "ops_page": inspection.get("status") != "unknown",
        },
        "backend": backend,
        "inspection": inspection,
    }

    host = config.get("host") or "default"
    safe_host = str(host).replace(":", "_").replace("/", "_").replace("\\", "_")
    output = Path("preflight-results") / f"health_{safe_host}.json"
    cms_page.write_inspection_result(output, snapshot)

    allure.attach(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        name="环境健康巡检结果",
        attachment_type=allure.attachment_type.JSON,
    )

    rules = _resolve_rules_for_suite()
    health_result = evaluate_health_env(str(host), snapshot, rules)
    failures = health_result.failed + health_result.unknown
    assert not failures, "环境健康检查不通过: " + "; ".join(
        f"{finding.check}={finding.actual}, 期望 {finding.expected}, {finding.detail}"
        for finding in failures
    )


def _collect_backend_health(ssh_host) -> dict[str, Any]:
    """通过后台 SSH 采集基础健康项。"""
    disk_output = ssh_host.run(
        "df -P / | awk 'NR==2 {gsub(\"%\",\"\",$5); print $5}'",
        timeout=30,
    )
    pods_output = ssh_host.run(
        "kubectl get pods -A --no-headers 2>/dev/null | "
        "awk '$4!=\"Running\" && $4!=\"Completed\" {count++} END {print count+0}'",
        timeout=60,
    )
    return {
        "system_disk_usage_pct": _to_int_or_none(disk_output),
        "pods_abnormal": _to_int_or_none(pods_output),
    }


def _resolve_rules_for_suite() -> dict[str, Any]:
    rules = load_health_rules()
    suite_name = os.environ.get("PREFLIGHT_SUITE", "").strip()
    if not suite_name:
        return rules

    expanded = resolve_suite(
        suite_name,
        load_suites(),
        available_modules=[],
        available_checks=list(rules.get("checks", {})),
    )
    if not expanded["health_checks"]:
        return rules
    return filter_health_rules(rules, expanded["health_checks"])


def _to_int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text.splitlines()[-1].strip()))
    except ValueError:
        return None
