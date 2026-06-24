"""pytest 钩子辅助函数。

与 pytest 生命周期（setup/call/teardown）交互的纯工具函数，
用于失败现场保留、报告附加等。
"""

from datetime import datetime
from pathlib import Path

import allure

from sugon_web.utils.logger import logger


def capture_failure_screenshot(page, item, failure_stage):
    """捕获失败截图并添加到 Allure 报告。

    Args:
        page: Playwright 页面对象
        item: pytest 测试项对象
        failure_stage: 失败阶段 (setup/call/teardown)
    """
    try:
        logger.info(f"开始生成失败截图")
        project_root = Path(__file__).resolve().parents[2]
        screenshot_dir = project_root / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"{item.name}_{timestamp}.png"

        page.screenshot(path=str(screenshot_path))
        logger.info(f"截图保存成功: {screenshot_path}")

        failure_info = (
            f"测试失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"测试用例名称: {item.name}\n"
            f"失败阶段: {failure_stage}\n"
            f"当前页面URL: {page.url}\n"
        )
        logger.error(f"测试失败详情:\n{failure_info}")

        with allure.step(f"用例信息收集 -> {failure_stage}阶段"):
            with open(screenshot_path, "rb") as f:
                allure.attach(
                    body=f.read(),
                    name=f"失败截图",
                    attachment_type=allure.attachment_type.PNG
                )
            allure.attach(
                body=failure_info,
                name="失败信息",
                attachment_type=allure.attachment_type.TEXT
            )

        logger.info(f"失败截图已保存并添加到 Allure 报告: {screenshot_path}")

    except Exception as e:
        logger.error(f"截图保存失败: {e}")

    # 【路线A·2026-06-19】失败那一刻顺带采集"真实渲染态可定位元素摘要"，供阶段三按真实 DOM 改定位。
    # 独立 try，与截图解耦：无论上面截图成功与否都尝试；任何异常都吞掉，绝不影响用例。
    try:
        capture_failure_dom_summary(page, item, failure_stage)
    except Exception as e:
        logger.error(f"失败现场 DOM 摘要采集失败（已忽略，不影响用例）: {e}")


def get_page_from_item(item):
    """从测试用例的 fixture 中获取 page 对象。

    Args:
        item: pytest 测试项对象

    Returns:
        Page 对象或 None
    """
    page = item.funcargs.get("page", None)
    if page:
        return page

    for fixture_name, fixture_obj in item.funcargs.items():
        if hasattr(fixture_obj, 'page'):
            page = getattr(fixture_obj, 'page')
            logger.info(f"从 {fixture_name} 中获取到page对象")
            return page

    logger.warning("无法获取page对象")
    return None


# ===== 失败现场 DOM 元素摘要（路线A·2026-06-19 新增，提升阶段三按真实渲染态修定位的准确度）=====
# 每类可定位元素最多保留条数：摘要化、防上下文爆炸——【绝不 dump 整页 raw HTML】（重前端整页 HTML 几百 KB~MB，会撑爆 AI 上下文）。
_DOM_SNAPSHOT_MAX_PER_KIND = 40

# 在浏览器端【单次 page.evaluate】枚举"可定位/可交互元素"的 JS：
# - 吸收 browser-use 的可交互判定思路（交互标签 + role + 自研组件 class），并补项目自研组件 cl-*/cloud-*；
# - 在浏览器内一次性采集，避免逐元素 is_visible 往返拖慢失败钩子；
# - 【通用增强·2026-06-20】额外采集"表格数据行 + 行内可点击项"（列表页点实体名进详情/点行操作最高频），
#   并滤除每页都一样的左侧导航菜单 chrome（避免淹没页面内容、挤占名额）；
# - 只取可见元素、文案/属性截断，输出结构化摘要（不是整页 HTML）。
_DOM_SNAPSHOT_JS = r"""
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


def capture_failure_dom_summary(page, item, failure_stage):
    """失败那一刻自动采集"真实渲染态的可定位元素摘要"，落盘为文本 + 附加到 Allure，供阶段三按真实 DOM 改定位。

    为什么需要（解决阶段三反复盲改 locator、修复准确度不高的根因）：
    - 阶段二靠"读前端工程源码"写定位，源码 ≠ 运行态，常对不上；修复时 AI 手里只有报错日志(单个失败 locator)
      + 一张截图(图片，难精确提取 class/role)，于是只能猜→反复改→原地打转。
    - 本函数把"失败那一刻真实渲染态的可定位元素清单"以【文本】落盘，AI 读文本即可拿到真实 class/role/文案，
      据此一次改对，大幅减少盲改轮次与阶段三耗时。
    设计约束：
    - 【摘要化、绝不 dump 整页 raw HTML】，每类限量；
    - 现场真实：直接对失败那一刻的 page 取（含 teleport 到 body 的弹窗/下拉、当前 tab/向导步等中间状态）；
    - 独立容错：任何异常都吞掉，绝不影响用例与截图。
    """
    if page is None:
        return
    try:
        data = page.evaluate(_DOM_SNAPSHOT_JS, _DOM_SNAPSHOT_MAX_PER_KIND)
    except Exception as e:
        logger.error(f"失败现场 DOM 枚举失败（已忽略）: {e}")
        return

    def _section(title, rows):
        rows = rows or []
        lines = [f"\n## {title}（{len(rows)} 条，最多显示 {_DOM_SNAPSHOT_MAX_PER_KIND}）"]
        if not rows:
            lines.append("- （无）")
        for r in rows:
            text = r.get("text", "")
            attrs = r.get("attrs", "")
            desc = f'text="{text}"' if text else "[无文本]"
            lines.append(f"- {desc} | tag={r.get('tag', '')} | {attrs}".rstrip(" |"))
        return "\n".join(lines)

    def _rows_section(rows):
        rows = rows or []
        lines = [f"\n## 表格数据行（{len(rows)} 行，最多 {_DOM_SNAPSHOT_MAX_PER_KIND}；**列表页“点实体名进详情 / 点行内‘操作’项”就到这里找目标行的可点击项**）"]
        if not rows:
            lines.append("- （未捕获到表格数据行：当前页可能不是列表页，或数据行尚未渲染。若你正卡在“进详情页”，先确认目标行是否已加载出来）")
        for r in rows:
            links = r.get("links") or []
            link_str = ("　可点击项：" + " | ".join(links)) if links else "　（行内未发现可点击链接/按钮：实体名可能是纯文本，需点整行或确认真实可点元素）"
            lines.append(f"- 行：{r.get('text', '')}{link_str}")
        return "\n".join(lines)

    dialogs = data.get("dialogs") or []
    if dialogs:
        dialog_block = ("## ⚠️ 弹窗/抽屉状态\n"
                        "- 当前检测到打开的弹窗/抽屉：" + "；".join(dialogs) + "\n"
                        "- 含义：你的目标元素很可能在该弹窗/抽屉内，定位应在其作用域内查找（注意它可能 teleport 到 body 下）。")
    else:
        dialog_block = ("## ⚠️ 弹窗/抽屉状态\n"
                        "- 未检测到打开的弹窗/抽屉 → 当前应为页面/内联表单，**不要假设是弹窗**（弹窗 vs 内联误判是高频根因）。")

    md = [
        "# 失败现场 DOM 元素摘要（自动捕获·真实渲染态）",
        f"- 用例：{item.name}　|　失败阶段：{failure_stage}　|　时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 当前 URL：{data.get('url', '')}",
        f"- 页面标题：{data.get('title', '')}",
        "",
        dialog_block,
        _section("可点击元素（按钮/链接/role=button/cl-button 等·已滤除左侧导航菜单）", data.get("buttons")),
        _rows_section(data.get("rows")),
        _section("输入/选择元素（input/textarea/select）", data.get("inputs")),
        _section("单选/多选（radio/checkbox）", data.get("radios")),
        _section("标签页 tab", data.get("tabs")),
        _section("表格列头/表头（th / cl-table-header）", data.get("headers")),
        ("\n## 修复提示（按真实渲染态改定位）\n"
         "- 优先 `get_by_role(role, name=真实文案)` / `get_by_text(真实文案, exact=True)` / `get_by_label` / `get_by_placeholder`，禁用 XPath。\n"
         "- **列表页要进详情 / 点行内操作**：到上面【表格数据行】找目标行的「可点击项」，用 `get_by_role(\"link\"/\"button\", name=...)` 或在该行作用域内 `get_by_text` 点击进入；**严禁自己拼前端路由 URL 用 `page.goto`、或用 `evaluate` 读 `__vue__` 内部数据 / 合成 `click`**——拼 URL 易因缺参/重定向而停在列表页，合成 click 触发不了 Vue 事件（这是“反复超时卡在列表页”的典型根因）。\n"
         "- **若你上一次失败用的定位/文案在上面清单里【找不到对应元素】**：多半是「元素还没渲染好」(应补等待收敛点) 或「选错了容器/层级」(如把内联表单当弹窗)，**不要只反复微调 selector**。\n"
         "- 若某元素标了【DISABLED】：它当前不可点，应先满足其启用前置条件，而非强点。\n"
         "- 本摘要是「失败那一刻」的真实现场，**优先以它为准，胜过前端源码印象/记忆中的结构**。"),
    ]
    content = "\n".join(md)

    try:
        project_root = Path(__file__).resolve().parents[2]
        out_dir = project_root / "screenshots"
        out_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{item.name}_{timestamp}_domsnap.md"
        out_path.write_text(content, encoding="utf-8")
        logger.info(f"失败现场 DOM 摘要已保存: {out_path}")
        with allure.step(f"失败现场 DOM 元素摘要 -> {failure_stage}阶段"):
            allure.attach(body=content, name="失败现场DOM元素摘要", attachment_type=allure.attachment_type.TEXT)
    except Exception as e:
        logger.error(f"失败现场 DOM 摘要写盘失败（已忽略）: {e}")
