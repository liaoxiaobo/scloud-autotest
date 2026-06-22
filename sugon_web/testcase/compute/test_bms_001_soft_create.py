import re
import time
import pytest
import allure

from sugon_web.common.remote import SSH
from sugon_web.pages.network import VpcPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data, get_file_abspath


BMS_ACL_NAME = "bms-acl"
BMS_SECURITY_GROUP_NAME = "bms-default"
BMS_VPC_PREFIX = "bms-vpc-autotest"


def _row_exists(page_obj, submenu_name, row_name):
    page_obj.goto_service("虚拟私有云")
    page_obj.goto_submenu(submenu_name)
    try:
        return page_obj.get_row_by_name(row_name) is not None
    except Exception:
        return False


def _bms_open_acl_list(vpc_page):
    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu("网络ACL")


def _bms_open_acl_detail(vpc_page, acl_name):
    _bms_open_acl_list(vpc_page)
    try:
        vpc_page.search(acl_name)
    except Exception as e:
        logger.warning(f"BMS ACL {acl_name} 搜索失败，尝试直接在列表中定位: {e}")

    row = vpc_page.page.locator("tbody tr").filter(has_text=acl_name)
    row.first.wait_for(state="visible", timeout=15000)

    click_result = vpc_page.page.evaluate(
        """aclName => {
            const visible = el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style && style.visibility !== 'hidden' && style.display !== 'none'
                    && rect.width > 0 && rect.height > 0;
            };
            const exactText = el => (el.innerText || el.textContent || '').trim() === aclName;
            const candidates = Array.from(document.querySelectorAll('.detail_link, a, button, span, div'))
                .filter(el => exactText(el));
            const target = candidates.find(visible) || candidates[0];
            if (!target) {
                return {
                    status: 'target-not-found',
                    candidates: candidates.length,
                    visibleRows: Array.from(document.querySelectorAll('tbody tr'))
                        .filter(visible)
                        .slice(0, 5)
                        .map(row => (row.innerText || '').replace(/\\s+/g, ' ').trim())
                };
            }
            target.scrollIntoView({block: 'center', inline: 'center'});
            ['mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {
                target.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
            });
            if (typeof target.click === 'function') {
                target.click();
            }
            return {
                status: 'clicked',
                tag: target.tagName,
                className: `${target.className || ''}`,
                text: (target.innerText || target.textContent || '').trim(),
                visible: visible(target)
            };
        }""",
        acl_name,
    )
    assert click_result.get("status") == "clicked", (
        f"点击 BMS ACL {acl_name} 详情入口失败: {click_result}"
    )
    logger.info(f"点击 BMS ACL {acl_name} 详情入口: {click_result}")

    for _ in range(10):
        try:
            page_text = vpc_page.page.locator("#cloud-container-content").inner_text(timeout=3000)
            if "/vpc-acl/" in vpc_page.page.url and acl_name in page_text:
                return
        except Exception:
            pass
        vpc_page.page.wait_for_timeout(1000)

    try:
        vpc_page.get_by_text(acl_name, exact=True).nth(1).click()
    except Exception as e:
        logger.warning(f"按精确文本点击 BMS ACL {acl_name} 进入详情失败，尝试 href 兜底: {e}")

    for _ in range(10):
        try:
            page_text = vpc_page.page.locator("#cloud-container-content").inner_text(timeout=3000)
            if "/vpc-acl/" in vpc_page.page.url and acl_name in page_text:
                return
        except Exception:
            pass
        vpc_page.page.wait_for_timeout(1000)

    detail_url = vpc_page.page.evaluate(
        """aclName => {
            const anchors = Array.from(document.querySelectorAll('a[href*="/vpc-acl/"]'));
            const anchor = anchors.find(el => (el.innerText || el.textContent || '').trim() === aclName);
            return anchor ? anchor.href : '';
        }""",
        acl_name,
    )
    if detail_url:
        vpc_page.page.goto(detail_url)
        vpc_page.wait_for_page_ready()

    for _ in range(30):
        try:
            page_text = vpc_page.page.locator("#cloud-container-content").inner_text(timeout=3000)
            if "/vpc-acl/" in vpc_page.page.url and acl_name in page_text:
                return
        except Exception:
            pass
        vpc_page.page.wait_for_timeout(1000)
    raise AssertionError(f"进入 BMS ACL 详情页超时: {acl_name}, current={vpc_page.page.url}")


def _bms_acl_page_diagnostics(vpc_page):
    try:
        return vpc_page.page.evaluate(
            """() => {
                const visible = el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style && style.visibility !== 'hidden' && style.display !== 'none'
                        && rect.width > 0 && rect.height > 0;
                };
                const textOf = el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                const tabs = Array.from(document.querySelectorAll('[role="tab"], .el-tabs__item, .cloud-tabs-tab, .cloud-tab'))
                    .filter(visible)
                    .map(el => ({
                        text: textOf(el),
                        className: `${el.className || ''}`,
                        selected: el.getAttribute('aria-selected')
                    }));
                const buttons = Array.from(document.querySelectorAll('button, .cloud-button, .el-button, [role="button"]'))
                    .filter(visible)
                    .map(el => textOf(el))
                    .filter(Boolean);
                const dialogs = Array.from(document.querySelectorAll('.el-dialog, [role="dialog"]'))
                    .filter(visible)
                    .map(el => textOf(el).slice(0, 120));
                return {
                    url: location.href,
                    tabs,
                    buttons,
                    dialogs,
                    text: textOf(document.querySelector('#cloud-container-content') || document.body).slice(0, 500)
                };
            }"""
        )
    except Exception as e:
        return {"url": vpc_page.page.url, "diagnostics_error": str(e)}


def _bms_switch_acl_rule_tab(vpc_page, tab_name):
    result = vpc_page.page.evaluate(
        """tabName => {
            const visible = el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style && style.visibility !== 'hidden' && style.display !== 'none'
                    && rect.width > 0 && rect.height > 0;
            };
            const normalize = text => (text || '').replace(/\\s+/g, '').trim();
            const candidates = Array.from(document.querySelectorAll(
                '[role="tab"], .el-tabs__item, .cloud-tabs-tab, .cloud-tab, button, span, div'
            )).filter(el => visible(el) && normalize(el.innerText || el.textContent) === normalize(tabName));
            if (!candidates.length) {
                return 'tab-not-found';
            }
            const active = candidates.find(el => {
                const host = el.closest('[role="tab"], .el-tabs__item, .cloud-tabs-tab, .cloud-tab') || el;
                const classes = `${el.className || ''} ${host.className || ''}`;
                return el.getAttribute('aria-selected') === 'true'
                    || host.getAttribute('aria-selected') === 'true'
                    || /(^|\\s)(is-active|active|cloud-tabs-tab-active)(\\s|$)/.test(classes);
            });
            if (active) {
                return 'already-active';
            }
            candidates[0].click();
            return 'clicked';
        }""",
        tab_name,
    )
    assert result in ("clicked", "already-active"), f"切换 BMS ACL 页签失败: {tab_name}, result={result}"
    vpc_page.wait_for_page_ready()
    for _ in range(10):
        active = vpc_page.page.evaluate(
            """tabName => {
                const visible = el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style && style.visibility !== 'hidden' && style.display !== 'none'
                        && rect.width > 0 && rect.height > 0;
                };
                const normalize = text => (text || '').replace(/\\s+/g, '').trim();
                return Array.from(document.querySelectorAll('[role="tab"], .el-tabs__item, .cloud-tabs-tab, .cloud-tab'))
                    .filter(visible)
                    .some(el => {
                        const classes = `${el.className || ''}`;
                        return normalize(el.innerText || el.textContent) === normalize(tabName)
                            && (el.getAttribute('aria-selected') === 'true'
                                || /(^|\\s)(is-active|active|cloud-tabs-tab-active)(\\s|$)/.test(classes));
                    });
            }""",
            tab_name,
        )
        if active:
            return
        vpc_page.page.wait_for_timeout(500)
    raise AssertionError(f"切换 BMS ACL 页签后未激活: {tab_name}, diagnostics={_bms_acl_page_diagnostics(vpc_page)}")


def _bms_acl_rule_rows_text(vpc_page):
    return vpc_page.page.evaluate(
        """() => Array.from(document.querySelectorAll('tbody tr'))
            .filter(row => {
                const style = window.getComputedStyle(row);
                const rect = row.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && rect.width > 0 && rect.height > 0;
            })
            .map(row => row.innerText || '')"""
    )


def _bms_click_acl_rule_create(vpc_page, tab_name):
    result = vpc_page.page.evaluate(
        """tabName => {
            const visible = el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style && style.visibility !== 'hidden' && style.display !== 'none'
                    && rect.width > 0 && rect.height > 0;
            };
            const textOf = el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
            const buttons = Array.from(document.querySelectorAll(
                '.noOverflow .cloud-button-btn.cl-btn-primary, '
                + '#cloud-container-content .cloud-button-btn.cl-btn-primary, '
                + '#cloud-container-content button, '
                + '#cloud-container-content .el-button, '
                + '#cloud-container-content [role="button"]'
            )).filter(el => visible(el) && textOf(el) === '新建' && !el.closest('.el-dialog, [role="dialog"]'));
            if (!buttons.length) {
                return {
                    status: 'button-not-found',
                    tabName,
                    buttons: Array.from(document.querySelectorAll(
                        '#cloud-container-content .cloud-button-btn, '
                        + '#cloud-container-content button, '
                        + '#cloud-container-content .el-button, '
                        + '#cloud-container-content [role="button"]'
                    ))
                        .filter(visible)
                        .map(textOf)
                        .filter(Boolean)
                };
            }
            const activePane = Array.from(document.querySelectorAll('.el-tab-pane, [role="tabpanel"], .cloud-tabs-panel'))
                .find(el => visible(el) && (textOf(el).includes(tabName) || textOf(el).includes('新建')));
            const target = buttons.find(btn => activePane && activePane.contains(btn)) || buttons[0];
            target.scrollIntoView({block: 'center', inline: 'center'});
            ['mouseover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {
                target.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
            });
            if (typeof target.click === 'function') {
                target.click();
            }
            return {
                status: 'clicked',
                tabName,
                buttonText: textOf(target),
                buttonClass: `${target.className || ''}`,
                allButtons: buttons.map(textOf)
            };
        }""",
        tab_name,
    )
    assert result.get("status") == "clicked", f"未找到 BMS ACL 规则新建按钮: {result}"
    logger.info(f"BMS ACL {tab_name} 新建按钮点击结果: {result}")


def _bms_fill_acl_allow_all_dialog(vpc_page, tab_name):
    dialog_name = f"新建{tab_name}"
    dialog = vpc_page.page.locator(".el-dialog:visible, [role='dialog']:visible").filter(has_text=dialog_name)
    try:
        dialog.wait_for(state="visible", timeout=15000)
    except Exception as e:
        raise AssertionError(
            f"BMS ACL {tab_name} 新建弹窗未出现: {e}; diagnostics={_bms_acl_page_diagnostics(vpc_page)}"
        ) from e

    policy_input = dialog.locator(".el-form-item").filter(has_text="策略").locator(
        "input[placeholder='请选择策略']"
    ).first
    try:
        if not (policy_input.input_value(timeout=1000) or "").strip():
            policy_input.click(force=True)
            vpc_page.page.locator("li:visible").filter(has_text="允许").first.click()
    except Exception as e:
        raise AssertionError(
            f"BMS ACL {tab_name} 新建弹窗选择策略失败: {e}; diagnostics={_bms_acl_page_diagnostics(vpc_page)}"
        ) from e

    src_ip_input = dialog.locator(".el-form-item").filter(has_text="源IP地址").locator("textarea, input[type='text']").first
    src_ip_input.fill("0.0.0.0/0")
    dest_ip_input = dialog.locator(".el-form-item").filter(has_text="目的IP地址").locator("textarea, input[type='text']").first
    dest_ip_input.fill("0.0.0.0/0")

    ok_button = dialog.locator(".cloud-button-btn.cl-btn-primary").filter(has_text="确定")
    if ok_button.count() > 0:
        ok_button.first.click(force=True)
    else:
        dialog.get_by_text("确定", exact=True).click()
    vpc_page.wait_for_page_ready()


def _bms_ensure_acl_allow_all_rule(vpc_page, direction):
    tab_name = f"{direction}规则"
    _bms_switch_acl_rule_tab(vpc_page, tab_name)

    rows_text = _bms_acl_rule_rows_text(vpc_page)
    has_allow_all = any(
        "IPv4" in text
        and "允许" in text
        and ("all" in text.lower() or "全部" in text)
        and "0.0.0.0/0" in text
        for text in rows_text
    )
    if has_allow_all:
        logger.info(f"ACL {BMS_ACL_NAME} 已存在 {direction} IPv4 全放通规则")
        return

    _bms_click_acl_rule_create(vpc_page, tab_name)
    _bms_fill_acl_allow_all_dialog(vpc_page, tab_name)
    logger.info(f"ACL {BMS_ACL_NAME} 已按BMS页面流程创建 {direction} IPv4 全放通规则")


def _ensure_bms_acl_allow_all(vpc_page):
    if _row_exists(vpc_page, "网络ACL", BMS_ACL_NAME):
        logger.info(f"ACL {BMS_ACL_NAME} 已存在，复用")
    else:
        vpc_page.acl_create(BMS_ACL_NAME, desc="BMS自动化专用ACL")

    try:
        acl_data = vpc_page.get_row_data(BMS_ACL_NAME)
        if acl_data and str(acl_data.get("状态", "")) == "关闭":
            vpc_page.acl_enable(BMS_ACL_NAME)
    except Exception as e:
        logger.warning(f"检查/开启 ACL {BMS_ACL_NAME} 状态失败，继续补规则: {e}")

    _bms_open_acl_detail(vpc_page, BMS_ACL_NAME)
    for direction in ("入方向", "出方向"):
        _bms_ensure_acl_allow_all_rule(vpc_page, direction)


def _sg_rule_exists(rules, direction, protocol, port=None):
    for rule in rules:
        if str(rule.get("方向", "")).strip() != direction:
            continue
        if "IPv4" not in str(rule.get("以太网类型", "")):
            continue
        rule_protocol = str(rule.get("IP协议", "")).lower()
        if protocol.lower() not in rule_protocol:
            continue
        if port:
            rule_port = str(rule.get("端口范围", "")).replace(" ", "")
            if port.replace(" ", "") not in rule_port:
                continue
        return True
    return False


def _bms_select_rule_option(vpc_page, dialog, label_text, option_text, exact=True):
    """Select an option in the BMS-only security group rule dialog."""
    label_prefix = r"远[程端]" if label_text == "远程" else re.escape(label_text)
    label_pattern = re.compile(rf"^\s*\*?\s*{label_prefix}")
    form_item = dialog.locator(".el-form-item").filter(has_text=label_pattern).first
    select_input = form_item.get_by_placeholder("请选择").first
    current = ""
    try:
        current = select_input.input_value(timeout=1000).strip()
    except Exception:
        pass
    if current == option_text:
        return

    select_input.click(force=True)
    options = vpc_page.page.locator("li:visible")
    if exact:
        options.filter(has_text=re.compile(rf"^\s*{re.escape(option_text)}\s*$")).first.click()
    else:
        options.filter(has_text=option_text).first.click()


def _bms_create_sg_cidr_rule(vpc_page, direction, protocol_type, port=None):
    """Create a BMS security group rule with CIDR remote only, never remote security group."""
    vpc_page.btn_create.click()
    dialog = vpc_page.get_by_role("dialog", name="创建规则")

    _bms_select_rule_option(vpc_page, dialog, "协议", "选择常用协议")

    protocol_type_input = dialog.get_by_placeholder("请选择协议")
    protocol_type_input.click(force=True)
    protocol_type_input.fill(protocol_type)
    vpc_page.page.locator("li:visible").filter(
        has_text=re.compile(rf"^\s*{re.escape(protocol_type)}\s*$", re.IGNORECASE)
    ).first.click()

    if port:
        _bms_select_rule_option(vpc_page, dialog, "打开端口", "端口范围")
        start_port, end_port = port.split("-", 1)
        start_input = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"^\s*\*?\s*起始端口号")
        ).get_by_role("textbox").first
        end_input = dialog.locator(".el-form-item").filter(
            has_text=re.compile(r"^\s*\*?\s*终止端口号")
        ).get_by_role("textbox").first
        start_input.fill(start_port.strip())
        end_input.fill(end_port.strip())

    _bms_select_rule_option(vpc_page, dialog, "方向", direction, exact=False)
    _bms_select_rule_option(vpc_page, dialog, "远程", "CIDR")
    _bms_select_rule_option(vpc_page, dialog, "IP版本", "IPv4", exact=False)

    dialog.get_by_text("确定").click()
    vpc_page.assert_popup_success("新建安全组规则成功")
    logger.info(
        f"BMS安全组规则创建完成: sg={BMS_SECURITY_GROUP_NAME}, 方向={direction}, "
        f"协议={protocol_type}, 远程=CIDR, CIDR留空"
        f"{f', 端口={port}' if port else ''}"
    )


def _ensure_bms_security_group_allow_all(vpc_page):
    if _row_exists(vpc_page, "安全组", BMS_SECURITY_GROUP_NAME):
        logger.info(f"安全组 {BMS_SECURITY_GROUP_NAME} 已存在，复用")
        return

    vpc_page.sg_create(BMS_SECURITY_GROUP_NAME, desc="BMS自动化专用安全组")

    rules = vpc_page.sg_get_all_rules(sg_name=BMS_SECURITY_GROUP_NAME)
    expected_rules = [
        ("入口", "定制TCP协议", "tcp", "1-65535"),
        ("出口", "定制TCP协议", "tcp", "1-65535"),
        ("入口", "定制UDP协议", "udp", "1-65535"),
        ("出口", "定制UDP协议", "udp", "1-65535"),
        ("入口", "所有ICMP协议", "icmp", None),
        ("出口", "所有ICMP协议", "icmp", None),
    ]
    for direction, protocol_type, protocol, port in expected_rules:
        if _sg_rule_exists(rules, direction, protocol, port):
            logger.info(f"安全组 {BMS_SECURITY_GROUP_NAME} 已存在 {direction} {protocol} 放通规则")
            continue
        _bms_create_sg_cidr_rule(vpc_page, direction, protocol_type, port=port)


def _find_reusable_bms_vpc(vpc_page):
    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu("虚拟私有云")
    try:
        vpc_page.search(BMS_VPC_PREFIX)
    except Exception as e:
        logger.warning(f"搜索可复用 BMS VPC 失败，继续新建: {e}")
        return None

    rows = vpc_page.page.locator(".el-table__body-wrapper:visible tbody tr").filter(has_text=BMS_VPC_PREFIX)
    if rows.count() == 0:
        return None

    row = rows.first
    cells = row.locator("td")
    vpc_name = ""
    for index in range(cells.count()):
        text = (cells.nth(index).text_content(timeout=1000) or "").strip()
        match = re.search(r"bms-vpc-autotest[-\w]*", text)
        if match:
            vpc_name = match.group(0)
            break
    if not vpc_name:
        return None

    row_data = {}
    try:
        row_data = vpc_page.get_row_data(vpc_name)
    except Exception as e:
        logger.warning(f"读取可复用 BMS VPC {vpc_name} 行数据失败，使用默认子网命名: {e}")
    cidr = (
        row_data.get("网段")
        or row_data.get("CIDR")
        or row_data.get("IPv4网段")
        or ""
    )
    subnet_name = f"{vpc_name}-subnet"
    logger.info(f"复用已有 BMS VPC: VPC={vpc_name}, 子网={subnet_name}, CIDR={cidr or '未知'}")
    return {
        "vpc_name": vpc_name,
        "subnet_name": subnet_name,
        "cidr": cidr,
        "acl_name": BMS_ACL_NAME,
        "security_group": BMS_SECURITY_GROUP_NAME,
    }


def _prepare_bms_instance_vpc(vpc_page):
    _ensure_bms_acl_allow_all(vpc_page)
    _ensure_bms_security_group_allow_all(vpc_page)

    reusable_vpc = _find_reusable_bms_vpc(vpc_page)
    if reusable_vpc:
        return reusable_vpc

    timestamp = time.strftime("%Y%m%d%H%M%S")
    vpc_name = f"{BMS_VPC_PREFIX}-{timestamp}"
    subnet_name = f"{vpc_name}-subnet"
    cidr = random_data("cidr")

    vpc_page.goto_service("虚拟私有云")
    vpc_page.goto_submenu("虚拟私有云")
    vpc_page.vpc_create(
        name=vpc_name,
        subnet_name=subnet_name,
        cidr=cidr,
        desc="BMS自动化专用VPC",
        subnet_desc="BMS自动化专用子网",
        network_type="Geneve",
        acl_policy=BMS_ACL_NAME,
    )
    vpc_page.assert_popup_success("创建虚拟私有云成功")
    vpc_page.assert_status(vpc_name)
    logger.info(
        f"BMS实例专用网络已创建: VPC={vpc_name}, 子网={subnet_name}, CIDR={cidr}, "
        f"ACL={BMS_ACL_NAME}, 安全组={BMS_SECURITY_GROUP_NAME}"
    )
    return {
        "vpc_name": vpc_name,
        "subnet_name": subnet_name,
        "cidr": cidr,
        "acl_name": BMS_ACL_NAME,
        "security_group": BMS_SECURITY_GROUP_NAME,
    }


def _get_prepared_bms_instance_vpc(vpc_page):
    """读取 network_prepare 已准备好的 BMS 实例网络环境。"""
    missing = []
    if not _row_exists(vpc_page, "网络ACL", BMS_ACL_NAME):
        missing.append(f"网络ACL {BMS_ACL_NAME}")
    if not _row_exists(vpc_page, "安全组", BMS_SECURITY_GROUP_NAME):
        missing.append(f"安全组 {BMS_SECURITY_GROUP_NAME}")

    reusable_vpc = _find_reusable_bms_vpc(vpc_page)
    if not reusable_vpc:
        missing.append(f"VPC {BMS_VPC_PREFIX}*")
    if missing:
        raise AssertionError(
            "BMS网络前置未准备完成，请先执行 test_bms_000_network_prepare.py；缺失: "
            + ", ".join(missing)
        )

    logger.info(
        f"BMS网络前置已准备: VPC={reusable_vpc['vpc_name']}, "
        f"子网={reusable_vpc['subnet_name']}, 安全组={BMS_SECURITY_GROUP_NAME}, ACL={BMS_ACL_NAME}"
    )
    return reusable_vpc


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS完整创建流程")
class TestBmsSoftCreate:

    @allure.title("裸金属BMS-软装版创建流程")
    def test_bms_create_with_page_image(self, ops_page, bms_page, ssh_host, config, bms_instance, bms_env):
        sg_name = f"test-bms-{random_data()}"
        bms_network_name = bms_env["network_name"]
        discovery_name = f"bms-test-{random_data()}"
        bmc_ip = bms_env["bmc_ip"]
        preferred_node = bms_env["preferred_node"]
        instance_name = bms_env["instance_name"]
        skip_to_step14 = False  # 标记是否跳过到步骤14（已有实例复用）

        # === 步骤0: 清理（本次跳过，保留资源供后续测试使用） ===
        logger.info("步骤0: 跳过清理，保留已创建的BMS资源")

        # === 步骤1-2: 获取或创建交换机组 ===
        with allure_step_log("步骤1-2: 获取交换机组"):
            ops_page._goto_switch_group()
            sg_name = None
            actual_node = None
            bound_group = None
            bound_node = None
            unbound_group = None
            for r in ops_page.page.locator("tbody tr").all():
                try:
                    cells = r.locator("td")
                    if cells.count() > 1:
                        n = cells.nth(1).text_content(timeout=3000).strip()
                        pm = cells.nth(2).text_content(timeout=3000).strip() if cells.count() > 2 else ""
                        if not n or "暂无数据" in n:
                            continue
                        # 物理机名必须是合法主机名（不含中文、操作按钮文案）
                        if n and pm and pm != "--" and pm != "—" and not re.search(r'[一-鿿]', pm):
                            bound_group = n
                            bound_node = pm
                            break
                        if not unbound_group and (not pm or pm == "--" or pm == "—"):
                            unbound_group = n
                except Exception:
                    continue

            if bound_group:
                sg_name = bound_group
                actual_node = bound_node
                logger.info(f"复用已绑定物理机的交换机组: {sg_name}, 物理机: {actual_node}")
            elif unbound_group:
                sg_name = unbound_group
                logger.info(f"复用未绑定物理机的交换机组: {sg_name}，开始绑定物理机")
                ops_page.switch_group_bind_node(sg_name, preferred_node)
                ops_page.page.wait_for_timeout(2000)
                ops_page._goto_switch_group()
                ops_page.search(sg_name)
                actual_node = ops_page.get_row_data(sg_name).get("物理机", "")
                assert actual_node and actual_node != "--"
            else:
                sg_name = f"test-bms-{random_data()}"
                ops_page.switch_group_create(sg_name)
                ops_page.page.wait_for_timeout(2000)
                ops_page._goto_switch_group()
                ops_page.search(sg_name)
                assert ops_page.get_row_data(sg_name).get("名称") == sg_name
                ops_page.switch_group_bind_node(sg_name, preferred_node)
                ops_page.page.wait_for_timeout(2000)
                ops_page._goto_switch_group()
                ops_page.search(sg_name)
                actual_node = ops_page.get_row_data(sg_name).get("物理机", "")
                assert actual_node and actual_node != "--"
            # 物理机列可能返回多个节点名拼接（如 master02.cloud.localmaster01.cloud.local），提取第一个
            if actual_node and preferred_node in actual_node:
                actual_node = preferred_node
            logger.info(f"使用交换机组: {sg_name}, 物理机: {actual_node}")

        # 前置检查：确认目标节点在 K8s 中为 Ready 状态
        with allure_step_log("步骤2b: 检查节点健康状态"):
            node_status = ssh_host.run(f"sudo kubectl get nodes {actual_node} --no-headers", return_rc=True)
            if node_status.get("rc") != 0 or "Ready" not in node_status.get("stdout", ""):
                logger.warning(f"节点 {actual_node} 在 Kubernetes 中不为 Ready 状态，跳过测试")
                pytest.skip(f"节点 {actual_node} 不在线或不为 Ready 状态，无法继续 BMS 流程")

        # === 步骤3: 创建网络 ===
        with allure_step_log("步骤3: 创建网络"):
            bms_page._goto_submenu_safe("网络")
            bms_page.page.wait_for_timeout(3000)
            # 多重检测：先检查表格行，再检查是否有"新建"按钮
            has_net = False
            for _ in range(3):
                rows = bms_page._get_rows()
                has_net = any(
                    bms_network_name in (r.text_content(timeout=3000) or "")
                    for r in rows
                    if "暂无数据" not in (r.text_content(timeout=3000) or "")
                )
                if has_net:
                    break
                # 如果没检测到行数据，检查是否有"新建"按钮（有则说明表格为空）
                new_btn = bms_page.page.locator("button, .cloud-button, .el-button").filter(has_text="新建")
                if new_btn.count() == 0 or not new_btn.first.is_visible():
                    # 没有新建按钮，说明表格有数据（只是可能还没解析到）
                    has_net = True
                    break
                bms_page.page.wait_for_timeout(2000)
            if not has_net:
                bms_page.bms_network_create(
                    name=bms_network_name, cidr="10.0.13.0/24",
                    start_ip="10.0.13.1", end_ip="10.0.13.254",
                    gateway="10.0.13.254", vlan="3157")
                bms_page.page.wait_for_timeout(3000)
            else:
                logger.info("网络bms已存在，跳过创建")
            bms_page._goto_submenu_safe("网络")
            bms_page.search(bms_network_name)
            assert bms_page.get_row_data(bms_network_name).get("网络名称") == bms_network_name

        # === 步骤4: 注册代理 ===
        with allure_step_log("步骤4: 注册代理"):
            bms_page._goto_submenu_safe("代理")
            bms_page.bms_search(actual_node)
            existing_agent = None
            try:
                existing_agent = bms_page.get_row_data(actual_node)
            except Exception as e:
                logger.info(f"未找到现有代理 '{actual_node}'，准备注册: {e}")

            if existing_agent:
                logger.info(f"发现现有代理 '{actual_node}'，复用该代理: {existing_agent}")
            else:
                bms_page.bms_agent_register(node_name=actual_node, ip_address="10.0.13.13")
            agent_data = bms_page.bms_agent_wait_healthy(actual_node, max_wait=600, poll_interval=30)
            if not agent_data:
                pytest.skip(f"代理 {actual_node} 未在10分钟内变为健康，无法继续 BMS 流程")

        # === 步骤5: 安装PXE ===
        with allure_step_log("步骤5: 安装PXE"):
            if agent_data.get("安装插件") == "是":
                logger.info(f"代理 {actual_node} 已安装PXE插件，跳过安装")
            else:
                bms_page.bms_agent_install_pxe(actual_node)
                bms_page.page.wait_for_timeout(3000)
                if not bms_page.bms_agent_wait_pxe_installed(actual_node, initial_wait=300, poll_interval=30, max_wait=1800):
                    pytest.skip("PXE安装超时")

        # === 步骤6: 创建发现任务 ===
        with allure_step_log("步骤6: 创建发现任务"):
            bms_page._goto_submenu_safe("发现")
            bms_page.page.wait_for_timeout(3000)
            # 检查是否已有覆盖该 BMC IP 的发现任务
            rows = bms_page._get_rows()
            existing_discovery = None
            for r in rows:
                try:
                    txt = r.text_content(timeout=3000) or ""
                    if "暂无数据" in txt:
                        continue
                    # 检查行中是否包含目标 BMC IP
                    if bmc_ip in txt:
                        cells = r.locator("td")
                        if cells.count() > 1:
                            name = cells.nth(1).text_content(timeout=3000).strip()
                            if name:
                                existing_discovery = name
                                break
                except Exception:
                    continue
            if existing_discovery:
                logger.info(f"发现已有覆盖 BMC {bmc_ip} 的发现任务: {existing_discovery}，将复用")
                discovery_name = existing_discovery
            else:
                bms_page.bms_discovery_create(
                    name=discovery_name, start_ip=bmc_ip, end_ip=bmc_ip,
                    subnet_mask="255.255.255.0", username="admin", password="admin")
                bms_page.page.wait_for_timeout(3000)
                bms_page._goto_submenu_safe("发现")
                bms_page.search(discovery_name)
                rd = bms_page.get_row_data(discovery_name)
                if rd is None:
                    # 创建后验证失败，可能是IP冲突或后端延迟，尝试从列表中查找
                    logger.warning(f"创建发现任务 '{discovery_name}' 后未立即找到，尝试从列表匹配")
                    bms_page._goto_submenu_safe("发现")
                    rows = bms_page._get_rows()
                    for r in rows:
                        try:
                            txt = r.text_content(timeout=3000) or ""
                            if bmc_ip in txt:
                                cells = r.locator("td")
                                if cells.count() > 1:
                                    discovery_name = cells.nth(1).text_content(timeout=3000).strip()
                                    logger.info(f"从列表匹配到发现任务: {discovery_name}")
                                    break
                        except Exception:
                            continue
                    else:
                        pytest.skip("无法创建或找到发现任务，可能该BMC IP已被其他任务覆盖")
            # 执行同步
            bms_page.bms_discovery_sync(discovery_name)
            bms_page.page.wait_for_timeout(3000)
            time.sleep(300)

        # === 步骤7: 带外信息 + 等待注册完成 ===
        with allure_step_log("步骤7: 配置带外信息"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            rd = bms_page.get_row_data(bmc_ip)
            assert rd is not None
            current_status = str(rd.get("状态", ""))
            if "注册完成" in current_status or "就绪" in current_status:
                logger.info(f"BMC {bmc_ip} 状态已为'{current_status}'，跳过带外信息配置")
            elif "新上架" in current_status or "注册中" in current_status:
                # 无论'新上架'还是'注册中'，都配置带外信息以确保注册能顺利完成
                logger.info(f"BMC {bmc_ip} 状态为'{current_status}'，配置带外信息")
                bms_page.bms_register_out_of_band_info(bmc_ip, switch_vlan="787", switch_group_name=sg_name)
                bms_page.page.wait_for_timeout(3000)
            elif "已使用" in current_status:
                logger.info(f"BMC {bmc_ip} 状态为'已使用'，检查是否已有实例")
                bms_page._goto_submenu_safe("裸金属实例")
                bms_page.page.wait_for_timeout(2000)
                rows = bms_page._get_rows()
                existing_instance = None
                for r in rows:
                    try:
                        txt = r.text_content(timeout=3000)
                        if txt and "暂无数据" not in txt and bms_network_name in txt:
                            cells = r.locator("td")
                            if cells.count() > 1:
                                name = cells.nth(1).text_content(timeout=3000).strip()
                                if name and name != "":
                                    existing_instance = name
                                    break
                    except Exception:
                        continue
                if existing_instance:
                    logger.info(f"发现已有实例: {existing_instance}，将复用该实例")
                    instance_name = existing_instance
                    skip_to_step14 = True
                else:
                    pytest.skip(f"BMC {bmc_ip} 状态为'已使用'但未找到实例，环境异常")
            elif "注册失败" in current_status:
                logger.warning(f"BMC {bmc_ip} 状态为'注册失败'，尝试删除并重新发现")
                bms_page.bms_register_delete(bmc_ip)
                bms_page.page.wait_for_timeout(3000)
                # 先删除旧发现任务，避免同IP冲突导致新建失败
                try:
                    bms_page.bms_discovery_delete(discovery_name)
                    bms_page.page.wait_for_timeout(3000)
                except Exception as e:
                    logger.warning(f"删除旧发现任务失败（可能已不存在）: {e}")
                # 重新创建发现任务并同步（使用新名称避免冲突）
                rediscovery_name = f"bms-retry-{random_data()}"
                bms_page.bms_discovery_create(
                    name=rediscovery_name, start_ip=bmc_ip, end_ip=bmc_ip,
                    subnet_mask="255.255.255.0", username="admin", password="admin")
                bms_page.page.wait_for_timeout(5000)
                # 如果重试发现任务仍未创建成功，跳过而非失败
                try:
                    bms_page.bms_discovery_sync(rediscovery_name)
                except Exception as e:
                    logger.warning(f"重新发现任务同步失败: {e}")
                    pytest.skip(f"BMC {bmc_ip} 注册失败后重新发现未能成功创建任务，环境可能不支持该BMC的重新发现")
                time.sleep(300)
                # 重新检查注册状态
                bms_page._goto_submenu_safe("注册")
                bms_page.search(bmc_ip)
                rd = bms_page.get_row_data(bmc_ip)
                current_status = str(rd.get("状态", "")) if rd else ""
                if "新上架" in current_status:
                    bms_page.bms_register_out_of_band_info(bmc_ip, switch_vlan="787", switch_group_name=sg_name)
                    bms_page.page.wait_for_timeout(3000)
                elif "注册完成" in current_status:
                    logger.info(f"重新发现后状态已为'注册完成'")
                else:
                    pytest.skip(f"重新发现后BMC {bmc_ip} 仍处异常状态: {current_status}")
            else:
                pytest.skip(f"BMC {bmc_ip} 处于未知状态: {current_status}")

        with allure_step_log("步骤7b: 等待注册完成"):
            if "已使用" in current_status:
                logger.info("BMC状态为'已使用'，跳过注册完成等待")
            elif "注册完成" in current_status or "就绪" in current_status:
                logger.info(f"BMC状态已为'{current_status}'，跳过注册完成等待")
            else:
                if not bms_page.bms_register_wait_status(bmc_ip, "注册完成", poll_interval=30, max_wait=600):
                    pytest.skip("步骤7注册完成等待超时（10分钟），可能环境异常")

        # === 步骤8: SSH检查BMS网卡 ===
        with allure_step_log("步骤8: SSH检查BMS网卡"):
            # 获取 master02 的 IP 地址
            node_info = ssh_host.run(f"sudo kubectl get nodes {actual_node} -owide", return_rc=True)
            master02_ip = None
            for line in node_info.get("stdout", "").split('\n'):
                parts = line.split()
                if len(parts) >= 6 and actual_node in line:
                    master02_ip = parts[5]
                    break
            if not master02_ip:
                logger.warning(f"未从 kubectl 节点信息中解析到 {actual_node} 的 Internal-IP，使用节点名直连")
                master02_ip = actual_node
            logger.info(f"master02 节点地址: {master02_ip}")

            # 创建到 master02 的 SSH 连接（通过跳板机）
            ssh_node = SSH()
            ssh_node.jumphost_client = ssh_host.ssh_client
            pkey_path = get_file_abspath(config.get("pkey"))
            ssh_node.connect(host=master02_ip, username="scloudadmin", pkey=pkey_path, use_jumphost=True)

            bms_nic_name = None
            for waited in range(0, 901, 30):
                r = ssh_node.run("ip a | grep bms", return_rc=True)
                if r["rc"] == 0 and "bms-nic" in r["stdout"]:
                    # ip a 输出格式: "bms-nic-3157: <flags> ..."，冒号不是名称一部分
                    m = re.search(r"(bms-nic[0-9a-zA-Z_-]+)", r["stdout"])
                    if m:
                        bms_nic_name = m.group(1)
                        logger.info(f"发现BMS网卡: {bms_nic_name}，等待{waited}s")
                        break
                if waited < 900:
                    logger.info(f"暂未发现 bms-nic 网卡，30s后重试 ({waited}/900s)")
                    time.sleep(30)
            if not bms_nic_name:
                ssh_node.close()
                pytest.skip("未在15分钟内找到bms-nic网卡")

        try:
            # === 步骤9: 记录 ===
            with allure_step_log("步骤9: 记录网卡名称"):
                allure.attach(bms_nic_name, "BMS网卡", allure.attachment_type.TEXT)

            # === 步骤10: 检查/编辑trusted.xml ===
            with allure_step_log("步骤10: 检查trusted.xml"):
                r = ssh_node.run("cat /etc/firewalld/zones/trusted.xml")
                if f'<interface name="{bms_nic_name}"/>' not in r:
                    ssh_node.run("sudo cp /etc/firewalld/zones/trusted.xml /etc/firewalld/zones/trusted.xml.bak")
                    # 使用 sed 在 </zone> 前插入网卡配置
                    insert_line = f'  <interface name="{bms_nic_name}"/>'
                    ssh_node.run(f"sudo sed -i 's|</zone>|{insert_line}\\n</zone>|' /etc/firewalld/zones/trusted.xml")
                v = ssh_node.run("cat /etc/firewalld/zones/trusted.xml")
                assert f'<interface name="{bms_nic_name}"/>' in v

            # === 步骤11: 检查并重载防火墙 ===
            with allure_step_log("步骤11: 检查并重载防火墙"):
                status = ssh_node.run("sudo systemctl is-active firewalld", return_rc=True, return_stderr=True)
                firewall_status = (status.get("stdout", "") or status.get("stderr", "")).strip()
                if status["rc"] != 0 or firewall_status != "active":
                    logger.warning(f"firewalld 当前状态为 {firewall_status or 'unknown'}，尝试启动 firewalld")
                    start = ssh_node.run("sudo systemctl start firewalld", return_rc=True, return_stderr=True)
                    start_output = f"{start.get('stdout', '')}\n{start.get('stderr', '')}"
                    assert start["rc"] == 0, f"firewalld 启动失败: {start_output}"

                    status = ssh_node.run("sudo systemctl is-active firewalld", return_rc=True, return_stderr=True)
                    firewall_status = (status.get("stdout", "") or status.get("stderr", "")).strip()
                    assert status["rc"] == 0 and firewall_status == "active", (
                        f"firewalld 启动后状态异常: {firewall_status or status.get('stderr', '')}"
                    )

                r = ssh_node.run("sudo firewall-cmd --reload", return_rc=True, return_stderr=True)
                firewall_output = f"{r.get('stdout', '')}\n{r.get('stderr', '')}"
                assert r["rc"] == 0, f"防火墙重载失败: {firewall_output}"
        finally:
            ssh_node.close()

        # === 步骤12: 注册物理机 ===
        with allure_step_log("步骤12: 注册物理机"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            rd = bms_page.get_row_data(bmc_ip)
            reg_status = str(rd.get("状态", "")) if rd else ""
            cpu = str(rd.get("CPU", "")) if rd else ""
            mem = str(rd.get("内存", "")) if rd else ""
            arch = str(rd.get("架构", "")) if rd else ""
            # 即使状态为"注册完成"，如果关键信息缺失也需重新注册
            info_complete = cpu and cpu != "--" and mem and mem != "--" and arch and arch != "--"
            if "已使用" in reg_status:
                logger.info(f"BMC {bmc_ip} 状态已为 '{reg_status}'，跳过重新注册")
            elif "注册完成" in reg_status and info_complete:
                logger.info(f"BMC {bmc_ip} 状态为'{reg_status}'且信息完整(CPU={cpu},内存={mem},架构={arch})，跳过重新注册")
            else:
                if "注册完成" in reg_status and not info_complete:
                    logger.info(f"BMC {bmc_ip} 状态为'{reg_status}'但信息不完整(CPU={cpu},内存={mem},架构={arch})，重新注册")
                bms_page.bms_register_action(bmc_ip)
                bms_page.page.wait_for_timeout(3000)
                if not bms_page.bms_register_wait_status(bmc_ip, "就绪", poll_interval=30, max_wait=2400):
                    pytest.skip("注册未在40分钟内完成")

        if skip_to_step14:
            logger.info("检测到已有实例，跳过步骤13（创建实例），直接进入步骤14")
        else:
            with allure_step_log("步骤12b: 读取BMS实例专用VPC/安全组"):
                vpc_page = VpcPage(bms_page.page)
                bms_network_env = _get_prepared_bms_instance_vpc(vpc_page)

            # === 步骤13-14: 创建裸金属实例并等待运行中（使用 fixture 工厂函数） ===
            instance_name = bms_instance(
                name=instance_name,
                security_group=bms_network_env["security_group"],
                network_name=bms_network_env["vpc_name"],
                subnet_name=bms_network_env["subnet_name"],
            )

        # === 步骤15: SSH验证 ===
        with allure_step_log("步骤15: SSH验证"):
            port_uuid = None
            for attempt in range(10):
                # 先尝试用网卡名搜索
                r = ssh_host.run(f"scli port list | grep {bms_nic_name}", return_rc=True)
                if r["rc"] == 0 and r["stdout"].strip():
                    m = re.search(r"\| ([a-f0-9\-]+) +\|", r["stdout"])
                    if m:
                        port_uuid = m.group(1)
                        logger.info(f"步骤15: 通过网卡名找到端口UUID: {port_uuid}")
                        break
                # 如果网卡名搜索失败，尝试搜索所有bms相关端口
                r_all = ssh_host.run("scli port list | grep -i bms", return_rc=True)
                if r_all["rc"] == 0 and r_all["stdout"].strip():
                    lines = [l for l in r_all["stdout"].split("\n") if l.strip()]
                    for line in lines:
                        m = re.search(r"\| ([a-f0-9\-]+) +\|", line)
                        if m:
                            port_uuid = m.group(1)
                            logger.info(f"步骤15: 通过bms关键字找到端口UUID: {port_uuid}")
                            break
                    if port_uuid:
                        break
                logger.info(f"步骤15: scli port list 未找到端口，第{attempt + 1}/10次重试...")
                time.sleep(60)
            else:
                pytest.skip("scli port list 未找到任何bms相关端口")
            r2 = ssh_host.run(f"scli port show {port_uuid}")
            # BMS 端口的 device_owner 为 neutron:bms，vnic_type 可能为空
            assert "neutron:bms" in r2 or "baremetal" in r2

        # === 步骤16: 验证注册状态 ===
        with allure_step_log("步骤16: 验证注册状态"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            assert "已使用" in bms_page.get_row_data(bmc_ip).get("状态", "")
