from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import allure
import pytest

from sugon_web.pages.cms import CmsPage
from sugon_web.tools.preflight.health import evaluate_health_env, load_health_rules
from sugon_web.tools.preflight.suites import filter_health_rules


@pytest.fixture(scope="function")
def cms_page(page):
    """初始化运维页面对象。"""
    return CmsPage(page)


@pytest.fixture(scope="session")
def preflight_health_file(config):
    """当前环境健康快照输出文件。"""
    host = config.get("host") or "default"
    env_name = os.environ.get("PREFLIGHT_ENV_NAME", "").strip() or str(host)
    safe_env_name = _safe_name(env_name)
    output = Path("preflight-results") / f"health_{safe_env_name}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    return output


@pytest.mark.preflight
@pytest.mark.preflight_health
@allure.feature("环境前置检查")
@allure.story("完整前置检查")
def test_preflight_selected_suite(config, preflight_health_file):
    """占位展示当前执行的前置检查关键词。"""
    suite_name = os.environ.get("PREFLIGHT_SUITE", "preflight-all").strip() or "preflight-all"
    env_name = os.environ.get("PREFLIGHT_ENV_NAME", "").strip() or str(config.get("host") or "default")
    snapshot = _update_snapshot(preflight_health_file, {
        "suite": suite_name,
        "env_name": env_name,
        "host": config.get("host"),
    })
    _attach_snapshot("前置检查关键词", snapshot)
    assert suite_name


@pytest.mark.preflight
@pytest.mark.preflight_health
@pytest.mark.preflight_frontend
@allure.feature("环境前置检查")
@allure.story("前端可用性")
def test_frontend_health(cms_page, config, preflight_health_file):
    """检查前端登录态和运维入口是否可访问。"""
    frontend = _collect_frontend_health(cms_page)
    snapshot = _update_snapshot(preflight_health_file, {"frontend": frontend})
    _attach_snapshot("前端健康检查结果", snapshot)
    _assert_section_health(
        config,
        snapshot,
        ["frontend_reachable", "login_ok", "ops_page_ok"],
        page=cms_page.page,
    )


@pytest.mark.preflight
@pytest.mark.preflight_health
@pytest.mark.preflight_backend
@allure.feature("环境前置检查")
@allure.story("后台健康")
def test_backend_health(config, ssh_host, preflight_health_file):
    """检查后台系统盘和 Pod 状态。"""
    backend = _collect_backend_health(ssh_host)
    snapshot = _update_snapshot(preflight_health_file, {"backend": backend})
    _attach_snapshot("后台健康检查结果", snapshot)
    _assert_section_health(config, snapshot, ["system_disk_usage_pct", "pods_abnormal"])


@pytest.mark.preflight
@pytest.mark.preflight_health
@pytest.mark.preflight_inspection
@allure.feature("环境前置检查")
@allure.story("运维一键巡检")
def test_ops_one_click_inspection(cms_page, config, preflight_health_file):
    """运行运维一键巡检并保存结果。"""
    inspection = cms_page.run_one_click_inspection()
    snapshot = _update_snapshot(preflight_health_file, {"inspection": inspection})
    _attach_snapshot("运维一键巡检结果", snapshot)
    _assert_section_health(
        config,
        snapshot,
        ["inspection_status", "inspection_failed", "inspection_warnings"],
        page=cms_page.page,
    )


@pytest.mark.preflight
@pytest.mark.preflight_health
@pytest.mark.preflight_storage
@allure.feature("环境前置检查")
@allure.story("存储池健康")
def test_storage_pool_health(cms_page, config, preflight_health_file):
    """检查存储池运行状态和剩余容量。"""
    storage_pools = cms_page.collect_storage_pools()
    snapshot = _update_snapshot(preflight_health_file, {"storage_pools": storage_pools})
    _attach_snapshot("存储池健康检查结果", snapshot)
    _assert_section_health(
        config,
        snapshot,
        [
            "storage_pool_usable_count",
            "storage_pool_abnormal_count",
            "storage_pool_max_available_gib",
        ],
        page=cms_page.page,
    )


def _collect_frontend_health(cms_page: CmsPage) -> dict[str, Any]:
    """采集前端登录和运维入口可用性。"""
    result = {
        "reachable": False,
        "login": False,
        "ops_page": False,
    }
    try:
        result["reachable"] = True
        result["login"] = "login" not in (cms_page.page.url or "")
        cms_page.goto_service("运维", force=True)
        cms_page.wait_for_page_ready()
        result["ops_page"] = "/cms" in cms_page.page.url
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _assert_section_health(
    config,
    snapshot: dict[str, Any],
    check_names: list[str],
    page=None,
) -> None:
    rules = filter_health_rules(load_health_rules(), check_names)
    host = config.get("host") or "default"
    health_result = evaluate_health_env(str(host), snapshot, rules)
    failures = health_result.failed + health_result.unknown
    if failures and page is not None:
        _attach_page_screenshot(page, "前置检查失败截图")
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


def _update_snapshot(path: Path, partial: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    else:
        snapshot = {}
    snapshot.update(partial)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def _attach_snapshot(name: str, snapshot: dict[str, Any]) -> None:
    allure.attach(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def _attach_page_screenshot(page, name: str) -> None:
    try:
        screenshot = page.screenshot(full_page=True)
        allure.attach(
            screenshot,
            name=name,
            attachment_type=allure.attachment_type.PNG,
        )
        allure.attach(
            page.url or "",
            name="失败时页面 URL",
            attachment_type=allure.attachment_type.TEXT,
        )
    except Exception as exc:
        allure.attach(
            f"截图失败: {exc}",
            name="截图失败信息",
            attachment_type=allure.attachment_type.TEXT,
        )


def _to_int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text.splitlines()[-1].strip()))
    except ValueError:
        return None


def _safe_name(value: str) -> str:
    safe_chars = []
    for char in value:
        if char.isalnum() or char in {"_", "-", "."}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    return "".join(safe_chars).strip("_") or "default"
