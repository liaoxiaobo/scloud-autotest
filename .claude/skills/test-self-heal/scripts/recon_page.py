#!/usr/bin/env python3
"""recon_page.py — test-self-heal 运行时侦察对齐黑盒脚本。

用途：当静态前端工程代码无法确定唯一、稳定的定位时，实际登录被测环境、导航到目标
服务页面，从**真实渲染态**枚举页面上的可定位元素（按钮/链接/输入框/标签页/表格列
等），并整页截图，输出「候选定位清单」，供据此写出/对齐 Page Object 的稳定定位。

在 test-self-heal 中的用途：阶段二「写定位前」按需侦察（无法仅凭前端代码确定
唯一定位时）、阶段三「诊断定位类失败」时枚举真实元素取证。

设计原则（黑盒 utility 脚本最佳实践）：
- **黑盒调用**：直接 `python recon_page.py --help` 看用法后执行，**不必读源码**，
  以免污染上下文。
- **只读不改**：本脚本只发现定位、绝不修改任何测试代码；真正修复写回 Page Object。
- **复用项目登录态/导航**：复用 sugon_web 的 Config 登录与 goto_service 导航，
  不另起裸浏览器、不写死 URL。
- **solve, don't punt**：对可预见错误显式处理并给出可操作提示，不把异常甩给调用者。

借鉴 anthropics/skills 的 webapp-testing：先 `wait_for_load_state('networkidle')`
再 inspect DOM。元素枚举采用浏览器端单次 `page.evaluate`，与 `sugon_web/utils/hooks.py`
失败现场 domsnap 同一套增强启发式（借鉴 browser-use 的 is_interactive 思路 + 项目自研
组件 cl-*/cloud-*），额外给出弹窗/抽屉状态、radio/checkbox、运行态 DISABLED、class，
使阶段二"写定位前"侦察与阶段三失败现场拿到同等丰富的元素清单。

用法示例：
    python recon_page.py --service "云服务器"          # 不带 --host：默认用 sugon_web/config/base.yaml 配置的当前测试环境（推荐）
    python recon_page.py --service "负载均衡" --submenu "监听器" --grep "创建"
    python recon_page.py --url-hash "#/vpc/slb" --headless
输出：
    控制台打印候选定位清单；整页截图存到 skill_runs/recon/ 下（本 skill 的运行时侦察产物目录）。
"""
import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

# Windows 控制台默认 GBK，本脚本会打印大量含中文文案/特殊符号（如 ⚠️、→、\xa0 不间断空格、
# 前端 class 名）的真实渲染态元素清单；不强制 UTF-8 输出会直接 `UnicodeEncodeError: 'gbk'
# codec can't encode` 崩溃——实测曾导致阶段二侦察跑不起来、被迫凭源码猜定位、阶段三反复返工。
# 与 run_guard.py / precheck.py / report_check.py / loop_gate.py 同款保护：统一把 stdout/stderr 切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

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


# 浏览器端【单次 page.evaluate】枚举"可定位/可交互元素"的 JS。
# 与 sugon_web/utils/hooks.py 失败现场 domsnap 的 `_DOM_SNAPSHOT_JS` 同一套启发式（借鉴 browser-use 的
# is_interactive 思路 + 项目自研组件 cl-*/cloud-*），目的：让阶段二"写定位前"的主动侦察，拿到与阶段三失败
# 现场同等丰富的元素清单（含弹窗/抽屉状态、radio/checkbox、自研组件、DISABLED、class），从源头一次写对定位、
# 减少进入阶段三的失败与修复轮次。单次 evaluate 在浏览器内采集，比逐元素 is_visible 往返更快、更不易漏。
_RECON_DOM_JS = r"""
(MAX) => {
  const txt = (e) => ((e.innerText || e.textContent || '').trim().replace(/\s+/g, ' ')).slice(0, 60);
  const vis = (e) => { try { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; } catch (_) { return false; } };
  const attrs = (e) => {
    const out = [];
    for (const k of ['id','name','placeholder','aria-label','type','role','href']) {
      const v = e.getAttribute && e.getAttribute(k); if (v) out.push(k + '=' + String(v).slice(0,40));
    }
    const cls = ((e.getAttribute && e.getAttribute('class')) || '').trim(); if (cls) out.push('class=' + cls.slice(0,70));
    const dis = (e.disabled === true) || (e.getAttribute && (e.getAttribute('aria-disabled') === 'true' || ((e.getAttribute('class')||'').includes('is-disabled'))));
    if (dis) out.push('【DISABLED】');
    return out.join(' ');
  };
  // 全局导航 chrome（左侧菜单树 / 顶部菜单），每页都一样、极少是定位目标，排除以免挤占名额、淹没页面内容
  const isChrome = (e) => { try { const c = (e.getAttribute && e.getAttribute('class')) || '';
      return /cloud-left-menu|app-mainframe|one-tree-/.test(c); } catch (_) { return false; } };
  const collect = (sel, skipChrome) => {
    const out = []; const seen = new Set();
    let nodes; try { nodes = document.querySelectorAll(sel); } catch (_) { return out; }
    nodes.forEach((e) => {
      if (out.length >= MAX) return;
      if (!vis(e)) return;
      if (skipChrome && isChrome(e)) return;
      const t = txt(e), a = attrs(e);
      const key = (e.tagName || '') + '|' + t + '|' + a; if (seen.has(key)) return; seen.add(key);
      out.push({ tag: (e.tagName || '').toLowerCase(), text: t, attrs: a });
    });
    return out;
  };
  // 表格数据行（列表页核心交互：点实体名进详情 / 点行内"操作"项——云控制台最高频、也最常超时失败的一步）
  const rows = [];
  try {
    const seenRow = new Set();
    document.querySelectorAll(".el-table__body-wrapper tbody tr, .cl-table tbody tr, table tbody tr").forEach((tr) => {
      if (rows.length >= MAX) return;
      if (!vis(tr)) return;
      const rowText = txt(tr); if (!rowText) return;
      if (seenRow.has(rowText)) return; seenRow.add(rowText);
      const links = [];
      try {
        tr.querySelectorAll("a, .el-link, [role=button], .cl-button, .cloud-button-btn, .cloud-table-dropdown-item, [class*='btn'], [class*='link']").forEach((a) => {
          if (links.length >= 10) return;
          if (!vis(a)) return;
          const t = txt(a); if (t) links.push(t);
        });
      } catch (_) {}
      rows.push({ text: rowText.slice(0, 120), links: links });
    });
  } catch (_) {}
  const dialogs = [];
  try {
    document.querySelectorAll("[role=dialog],.el-dialog,.el-drawer,.el-message-box,.cl-dialog,.cloud-dialog").forEach((d) => {
      if (!vis(d)) return;
      const tEl = d.querySelector('.el-dialog__title,.el-drawer__title,.cl-dialog-title,.cloud-dialog-title,header,h1,h2,h3');
      dialogs.push(((tEl ? (tEl.innerText || '') : '').trim().slice(0, 60)) || '(无标题)');
    });
  } catch (_) {}
  return {
    url: location.href,
    title: document.title,
    dialogs: dialogs,
    buttons: collect("button,[role=button],a,.el-link,.cl-button,.cloud-button-btn,.cloud-table-dropdown-item,[class*='btn']", true),
    inputs: collect("input,textarea,select,[contenteditable='true']", false),
    radios: collect("[role=radio],[role=checkbox],input[type=radio],input[type=checkbox],.el-radio,.el-checkbox", false),
    tabs: collect("[role=tab],.el-tabs__item", false),
    headers: collect("th,.el-table__header-wrapper th,.cl-table-header", false),
    rows: rows,
  };
}
"""


def _enumerate(page, grep):
    """从真实渲染态枚举候选可定位元素（浏览器端单次 evaluate，与 hooks.py domsnap 同套增强启发式）。只读。

    相比旧版仅枚举 button/a/input/tab/th，本版额外给出：**表格数据行 + 行内可点击项**（列表页点实体名
    进详情/点行操作最高频）、弹窗/抽屉状态（治"内联误判为弹窗"高频根因）、radio/checkbox、自研组件
    cl-*/cloud-*、运行态 DISABLED、class 属性，并滤除每页都一样的左侧导航菜单 chrome——让阶段二一次写对定位。
    """

    def _match(row):
        if grep is None:
            return True
        hay = ((row.get("text") or "") + " " + (row.get("attrs") or "")).lower()
        return grep.lower() in hay

    print("\n========== 候选新定位清单（真实渲染态·增强枚举） ==========")
    try:
        data = page.evaluate(_RECON_DOM_JS, MAX_ITEMS_PER_KIND)
    except Exception as e:
        print(f"元素枚举失败（页面可能未就绪，可稍后重试或换 --url-hash/--service）：{e}")
        print("==================================================\n")
        return

    print(f"当前 URL: {data.get('url', '')}")
    print(f"页面标题: {data.get('title', '')}")

    dialogs = data.get("dialogs") or []
    if dialogs:
        print("\n[⚠️ 弹窗/抽屉状态] 检测到打开的弹窗/抽屉：" + "；".join(dialogs))
        print("  → 目标元素很可能在该弹窗/抽屉作用域内（注意可能 teleport 到 body 下），定位应在其内查找。")
    else:
        print("\n[⚠️ 弹窗/抽屉状态] 未检测到打开的弹窗/抽屉 → 当前应为页面/内联表单，勿误判为弹窗（弹窗 vs 内联误判是高频定位根因）。")

    # 表格数据行（列表页核心：点实体名进详情 / 点行内"操作"项——最高频也最常超时失败的一步）
    def _row_match(r):
        if grep is None:
            return True
        hay = ((r.get("text") or "") + " " + " ".join(r.get("links") or [])).lower()
        return grep.lower() in hay
    trows = [r for r in (data.get("rows") or []) if _row_match(r)]
    print(f"\n[表格数据行] 命中 {len(trows)} 行（列表页“点实体名进详情 / 点行内操作”就到这里找目标行的可点击项）：")
    if not trows:
        print("  - （未捕获到表格数据行：当前页可能不是列表页，或数据行尚未渲染）")
    for _r in trows:
        _links = _r.get("links") or []
        _ls = ("　可点击项：" + " | ".join(_links)) if _links else "　（行内未发现可点击链接/按钮）"
        print(f"  - 行：{_r.get('text', '')}{_ls}")

    sections = [
        ("可点击元素（按钮/链接/role=button/cl-button 等·已滤除左侧导航菜单）", data.get("buttons")),
        ("输入/选择（input/textarea/select）", data.get("inputs")),
        ("单选/多选（radio/checkbox）", data.get("radios")),
        ("标签页 tab", data.get("tabs")),
        ("表格列头/表头（th / cl-table-header）", data.get("headers")),
    ]
    for title, rows in sections:
        rows = [r for r in (rows or []) if _match(r)]
        print(f"\n[{title}] 命中 {len(rows)} 条（每类最多 {MAX_ITEMS_PER_KIND}）：")
        if not rows:
            print("  - （无）")
        for r in rows:
            text = r.get("text") or ""
            desc = f'text="{text}"' if text else "[无文本]"
            print(f"  - {desc} | tag={r.get('tag', '')} | {r.get('attrs', '')}".rstrip(" |"))

    print("\n建议：优先用 get_by_role(role, name=真实文案) / get_by_text(exact=True) / get_by_placeholder() / get_by_label() 选定定位，禁用 XPath。")
    print("列表页进详情 / 点行操作：到【表格数据行】找目标行的可点击项点击；禁止自己拼 URL 用 page.goto，也禁止 evaluate 读 __vue__ 内部数据 / 合成 click。")
    print("标了【DISABLED】的元素当前不可点，应先满足其启用前置条件，勿强点。")
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
