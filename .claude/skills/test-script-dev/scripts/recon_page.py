#!/usr/bin/env python3
"""recon_page.py — 运行时侦察对齐黑盒脚本（test-script-dev / test-self-heal 共用）。

用途：当静态前端工程代码无法确定唯一、稳定的定位时，实际登录被测环境、导航到目标
服务页面，从**真实渲染态**枚举页面上的可定位元素（按钮/链接/输入框/标签页/表格列
等），并整页截图，输出「候选定位清单」，供据此写出/对齐 Page Object 的稳定定位。

在 test-script-dev 中的用途：阶段二「写定位前」按需侦察（无法仅凭前端代码确定
唯一定位时）、阶段三「诊断定位类失败」时枚举真实元素取证。

设计原则（黑盒 utility 脚本最佳实践）：
- **黑盒调用**：直接 `python recon_page.py --help` 看用法后执行，**不必读源码**，
  以免污染上下文。
- **只读不改**：本脚本只发现定位、绝不修改任何测试代码；真正修复写回 Page Object。
- **复用项目登录态/导航**：复用 sugon_web 的 Config 登录与 goto_service 导航，
  不另起裸浏览器、不写死 URL。
- **solve, don't punt**：对可预见错误显式处理并给出可操作提示，不把异常甩给调用者。

借鉴 anthropics/skills 的 webapp-testing：先 `wait_for_load_state('networkidle')`
再 inspect DOM；元素枚举范式参考其 examples/element_discovery.py。

用法示例：
    python recon_page.py --service "云服务器"          # 不带 --host：默认用 sugon_web/config/base.yaml 配置的当前测试环境（推荐）
    python recon_page.py --service "负载均衡" --submenu "监听器" --grep "创建"
    python recon_page.py --url-hash "#/vpc/slb" --headless
输出：
    控制台打印候选定位清单；整页截图存到 skill_runs/recon/ 下（与 test-self-heal 共用侦察产物目录）。
"""
import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

# 侦察的可见性判定超时（毫秒）。3000ms 兼顾慢环境渲染与脚本不长时间挂起；
# 与项目登录流程中对弹窗可见性的等待量级一致。
VISIBLE_TIMEOUT_MS = 3000
# networkidle 等待上限（毫秒）。15000ms 覆盖 SugonCloud 重前端页面的首屏异步加载。
NETWORKIDLE_TIMEOUT_MS = 15000
# 每类元素最多打印条数，避免输出爆炸污染上下文。
MAX_ITEMS_PER_KIND = 40


def _project_root() -> Path:
    """向上回溯定位仓库根目录（含 sugon_web 包的目录）。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "sugon_web").is_dir():
            return parent
    # 兜底：脚本位于 .claude/skills/<skill-name>/scripts/，根目录为上溯 4 层
    return here.parents[4]


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="运行时侦察脚本：登录被测环境、导航目标页、枚举真实渲染态可定位元素（只读）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--service", help="goto_service 的服务名（如 '云服务器'/'负载均衡'），与项目导航一致")
    parser.add_argument("--submenu", default=None, help="可选：进入服务后要点击的子菜单名")
    parser.add_argument("--url-hash", default=None, help="可选：直接导航到 base_url + 该 hash（如 '#/vpc/slb'），优先级低于 --service")
    parser.add_argument("--grep", default=None, help="可选：只打印文本/属性包含该关键词的候选元素")
    parser.add_argument("--probe-click", default=None, metavar="文案",
                        help="交互探针：导航到目标页后，对该文案的元素做【原生 .click()】，报命中数 + 点击前后 URL/DOM 是否变化（用于秒级验证'这个点击到底跳不跳转/有无效果'，替代靠全量 pytest 反复猜）")
    parser.add_argument("--host", default=None, help="被测环境管理 VIP，缺省用项目配置默认值")
    parser.add_argument("--username", default=None, help="登录用户名，缺省用项目配置")
    parser.add_argument("--password", default=None, help="登录密码，缺省用项目配置")
    parser.add_argument("--headless", action="store_true", help="无头模式运行（默认有头，便于观察）")
    return parser.parse_args(argv)


def _bootstrap_config(args):
    """复用项目 Config 完成配置加载与命令行覆盖（与 conftest 一致）。"""
    from sugon_web.config.config import Config

    Config.load(host=args.host)
    Config.override(
        username=args.username,
        password=args.password,
        headless="true" if args.headless else None,
    )
    return Config


def _enumerate(page, grep):
    """从真实渲染态枚举候选可定位元素（借鉴 element_discovery.py）。只读。"""

    def _match(text):
        return grep is None or (text and grep.lower() in text.lower())

    print("\n========== 候选新定位清单（真实渲染态） ==========")
    print(f"当前 URL: {page.url}")

    kinds = [
        ("按钮 button", "button"),
        ("链接 a[href]", "a[href]"),
        ("输入/选择 input,textarea,select", "input, textarea, select"),
        ("标签页 [role=tab]", "[role='tab']"),
        ("表格列头 th", "th"),
    ]
    for title, selector in kinds:
        try:
            elements = page.locator(selector).all()
        except Exception as e:
            print(f"\n[{title}] 枚举失败（跳过）: {e}")
            continue
        rows = []
        for el in elements:
            try:
                if not el.is_visible(timeout=VISIBLE_TIMEOUT_MS):
                    continue
                text = (el.inner_text() or "").strip().replace("\n", " ")
                role = el.get_attribute("role")
                name = el.get_attribute("name") or el.get_attribute("id") or el.get_attribute("placeholder")
                etype = el.get_attribute("type")
                desc = f"text='{text[:40]}'" if text else ""
                attrs = " ".join(filter(None, [
                    f"role={role}" if role else "",
                    f"name/id/ph={name}" if name else "",
                    f"type={etype}" if etype else "",
                ]))
                line = " | ".join(filter(None, [desc, attrs])) or "[无文本/无显著属性]"
                if _match(text) or _match(name):
                    rows.append(line)
            except Exception:
                continue  # 单个元素读取失败不影响整体枚举
            if len(rows) >= MAX_ITEMS_PER_KIND:
                rows.append(f"... （已截断，仅显示前 {MAX_ITEMS_PER_KIND} 条）")
                break
        print(f"\n[{title}] 命中 {len(rows)} 条：")
        for r in rows:
            print(f"  - {r}")

    print("\n建议：优先用 get_by_role(role, name=...) / get_by_text(exact=True) / get_by_placeholder() 选定新定位，禁用 XPath。")
    print("==================================================\n")


def _dom_signature(page):
    """轻量 DOM 指纹：(HTML 长度, 短哈希)，用于点击前后对比是否发生状态变化。"""
    try:
        html = page.content()
    except Exception:
        return (0, "")
    return (len(html), hashlib.sha256(html.encode("utf-8", "replace")).hexdigest()[:12])


def _probe_click(page, text, recon_dir):
    """交互探针：对目标文案元素做原生 .click()，报命中数 + 点击前后 URL/DOM 变化。

    目的：把"猜定位→7 分钟全量 pytest 验证→再猜"压成"秒级验证点击到底有无效果"。
    只做一次点击验证，不修改任何测试代码。
    """
    print("\n========== 交互探针（点击效果验证） ==========")
    print(f"目标文案: {text!r}")
    loc = page.get_by_text(text, exact=False)
    try:
        n = loc.count()
    except Exception as e:
        print(f"[命中] get_by_text 统计失败: {e}")
        print("=============================================\n")
        return
    note = "（>1：需在 dialog/行/tab 内 scope 限定，勿直接点 first）" if n > 1 else ""
    print(f"[命中] get_by_text({text!r}) 命中 {n} 个 {note}")
    if n == 0:
        print("结论：当前页未命中该文案——文案/页面不对。先核对真实渲染文案（去掉 --probe-click 改用 --grep 侦察枚举）。")
        print("=============================================\n")
        return

    url_before = page.url
    sig_before = _dom_signature(page)
    try:
        loc.first.click(timeout=VISIBLE_TIMEOUT_MS * 2)
        print("[点击] 已对 .first 执行【原生 Playwright .click()】（正确方式，勿用 evaluate 合成事件）")
    except Exception as e:
        print(f"[点击] 原生 .click() 失败：{e}")
        print("结论：原生点击点不动——多为元素不可见/被遮挡/未就绪。先解决可见性与等待时机，"
              "**切勿改用 evaluate 合成 MouseEvent 绕过**（合成事件触发不了 Vue onClick）。")
        print("=============================================\n")
        return

    try:
        page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT_MS)
    except Exception:
        pass
    url_after = page.url
    sig_after = _dom_signature(page)
    url_changed = url_after != url_before
    dom_changed = sig_after != sig_before

    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot = recon_dir / f"probe_after_{ts}.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"点击后整页截图：{shot}")
    except Exception:
        pass

    print(f"[URL] 前: {url_before}")
    print(f"[URL] 后: {url_after}")
    print(f"[结果] URL 变化: {'是' if url_changed else '否'} | DOM 变化: {'是' if dom_changed else '否'}"
          f"（HTML 长度 {sig_before[0]}→{sig_after[0]}）")
    if url_changed:
        print("结论：原生 .click() 触发了路由跳转 → 该交互用 `get_by_text(...).click()` 即可，"
              "**以 URL 变化判定成功**，不要等猜的返回按钮。")
    elif dom_changed:
        print("结论：原生 .click() 触发了页面状态变化（DOM 变、未跳路由）→ 多为弹窗/抽屉/展开，"
              "按目标等其可见元素判定，仍用原生点击。")
    else:
        print("结论：点击后 URL 与 DOM 均无变化 → 多半点到了错元素或目标非真正可点击。"
              "**先在 dialog/行/tab 内 scope 精确定位目标再验**，切勿改用 evaluate 合成事件反复试错。")
    print("=============================================\n")


def main(argv):
    args = _parse_args(argv)
    if not args.service and not args.url_hash:
        print("错误：必须提供 --service 或 --url-hash 之一。用 --help 查看用法。", file=sys.stderr)
        return 2

    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：未安装 playwright。请先 `pip install -r requirements.txt && playwright install`。", file=sys.stderr)
        return 3

    try:
        config = _bootstrap_config(args)
        from sugon_web.conftest import _create_logged_in_page  # 复用项目登录态
        from sugon_web.common.base import BasePage
    except Exception as e:
        print(f"错误：加载项目登录/导航基建失败：{e}", file=sys.stderr)
        return 3

    recon_dir = root / "skill_runs" / "recon"
    recon_dir.mkdir(parents=True, exist_ok=True)

    browser_type = config.get("browser") or "chromium"
    headless = bool(config.get("headless"))
    with sync_playwright() as p:
        browser = getattr(p, browser_type).launch(
            headless=headless,
            args=["--ignore-certificate-errors", "--ignore-certificate-errors-spki-list"],
        )
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = _create_logged_in_page(context, config)
            base = BasePage(page)
            if args.service:
                base.goto_service(args.service)
                if args.submenu:
                    # 复用项目导航能力进入子菜单，避免写死页面结构
                    try:
                        base.goto_submenu(args.submenu)
                    except Exception as e:
                        print(f"提示：进入子菜单 '{args.submenu}' 未成功（继续侦察当前页）：{e}")
            else:
                base_url = config.get("base_url")
                page.goto(f"{base_url}{args.url_hash}", wait_until="domcontentloaded")

            # 关键：inspect DOM 前必须等 networkidle（webapp-testing 反模式规避）
            try:
                page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT_MS)
            except Exception:
                print("提示：networkidle 等待超时，按当前渲染态继续侦察。")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = recon_dir / f"recon_{ts}.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"整页截图已保存：{shot}")
            except Exception as e:
                print(f"提示：截图失败（继续枚举）：{e}")

            if args.probe_click:
                _probe_click(page, args.probe_click, recon_dir)
            else:
                _enumerate(page, args.grep)
            return 0
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
