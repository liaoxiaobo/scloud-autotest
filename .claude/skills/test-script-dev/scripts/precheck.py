#!/usr/bin/env python3
"""precheck.py — test-script-dev 阶段二/三「静态门禁」黑盒脚本。

用途：在「阶段二编码完成、首次执行 pytest 之前」对测试脚本做一次**纯静态**校验，
把可被正则/AST 客观判定的规范违规，在「零执行成本」的最便宜时刻拦下，形成
validator → fix → repeat 反馈环，避免这些违规被带到阶段三的长时执行里才暴露。

设计原则（对应优化方案 §6.2.2 / 第七章官方最佳实践）：
- **黑盒调用**：直接 `python precheck.py --help` 看用法后执行，**不必读源码**。
- **只做客观机械校验**：本脚本只兜底「可机器判定」的违规；断言分层是否合理、是否
  对齐需求语义，仍由 AI 按阶段二对齐检查完成——门禁是兜底，不是替代。
- **solve, don't punt**：对每条违规显式输出「文件:行:原因」，不把判断甩给调用者；
  文件读取等可预见错误显式处理。
- **退出码**：无违规返回 0；有违规返回 1；用法/环境错误返回 2。

校验项（1~6 对 test_*.py「测试层」生效；7 对该测试 import 的 pages/ 页面对象层生效）：
  1. 测试层底层 API：出现 .locator( / playwright import expect / xpath=
  2. 固定等待：出现 wait_for_timeout( / time.sleep(
  3. 测试方法体 try/except|try/finally 包裹（AST 精确判定，仅 test_ 方法）
  4. SSH 掩盖错误：命令串内出现 || true
  5. 新增 marker 未登记：用到的 @pytest.mark.X 未在 pytest.ini 的 markers 声明
  6. 数量对齐（可选）：展开 @pytest.mark.parametrize 后的「用例数」≠ --expected-tests 指定值
     （计数口径：1 个无参方法记 1 个用例；带 N 组 parametrize 的方法记 N 个用例。
      这样 5 个独立方法、或 1 个 5 组参数化方法都算 5；而把 5 个场景塞进同一个不参数化
      的方法只算 1，会被拦下——正是要堵的「多需求合并进一个方法」。
      不传 --expected-tests 时本项静默跳过，故脚本会显式告警提醒开启。）
  7. Page Object 导航/定位 + JS 填表反模式（通用·跨模块，扫描该测试 import 的 pages/ 文件，按 --since 限定本轮改动的）：
     硬违规 = 读取 Vue 内部状态 __vue__、用 evaluate 合成 .click()、用 evaluate 合成 input/change 填表、
              JS 点 .el-select-dropdown__item 选下拉、evaluate 内 setTimeout 竞态；
     告警 = 手动拼接 #/ 前端路由、page.goto(f"...") 跳转构造 URL。
     —— 列表→详情应点真实行内实体名链接、表单应原生 fill/点选项触发真实事件链，而非拼 URL/读 Vue 内部状态/JS 合成事件
     （前者是"反复超时卡列表页"、后者是"创建表单提交不了、按钮一直 disabled"的高发根因）。

用法示例：
    python precheck.py sugon_web/testcase/network/test_lb_v2_http_forward.py
    python precheck.py sugon_web/testcase/network/        # 递归扫描目录下 test_*.py
    python precheck.py <文件> --expected-tests 2          # 同时校验测试方法数
    python precheck.py <文件> --pytest-ini sugon_web/pytest.ini

注：运行报告（skill_runs 下的 md）的章节锚点完整性校验是另一职责，见同目录 report_check.py。
"""
import argparse
import ast
import re
import subprocess
import sys
import time
from pathlib import Path

# Windows 控制台默认 GBK，脚本含大量中文；不强制 UTF-8 会出现 `���` 乱码，
# 让"按门禁提示修复"的反馈环失效。统一把 stdout/stderr 切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

# 仅扫描「测试层」文件：文件名形如 test_*.py。pages/ 页面对象层允许底层 API，故不纳入。
TEST_FILE_GLOB = "test_*.py"

# 运行时侦察产物目录（recon_page.py 截图落盘处），用于「新建 Page Object 必须先侦察」的机械门禁。
RECON_DIR_DEFAULT = "skill_runs/recon"

# 测试层禁止的底层 Playwright API（必须经 Page Object 封装调用）。
# 说明：.locator( 与 expect 仅在测试层禁止；XPath 任何层都脆弱，统一标记。
LOW_LEVEL_API_PATTERNS = [
    (re.compile(r"\.locator\("), "测试层直接使用 .locator()（应通过 Page Object 封装方法）"),
    (re.compile(r"from\s+playwright.*import\s+.*\bexpect\b"), "测试层引入 playwright expect（应通过 Page Object/断言方法）"),
    (re.compile(r"\bexpect\("), "测试层直接调用 expect()（应通过 Page Object/断言方法）"),
    (re.compile(r"xpath\s*=|//\w+\[|\.xpath\("), "使用 XPath 定位（脆弱，禁用；改 get_by_role/get_by_text(exact=True)）"),
]

# 固定等待：项目红线禁止，应改用 wait_for_page_ready/wait_for_operation_complete/wait_for_source_complete 收敛点。
FIXED_WAIT_PATTERNS = [
    (re.compile(r"wait_for_timeout\("), "固定等待 wait_for_timeout()（改用收敛点等待）"),
    (re.compile(r"\btime\.sleep\("), "固定等待 time.sleep()（轮询间隔除外；断言前的固定等待一律禁止）"),
]

# SSH 命令掩盖错误：必须断言 rc/stdout，禁止 `|| true` 吞错。
SSH_MASK_PATTERN = (re.compile(r"\|\|\s*true\b"), "SSH/命令用 `|| true` 掩盖失败（必须断言 rc 和 stdout）")

# 收集测试代码中使用到的 pytest marker。
MARK_USAGE_PATTERN = re.compile(r"@pytest\.mark\.([A-Za-z_]\w*)")
# pytest 内置/参数化类 marker，不需要在 markers 列表登记，避免误报。
BUILTIN_MARKERS = {
    "parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings", "tryfirst", "trylast",
}

# Page Object 导航/定位反模式（通用·跨模块）：靠框架内部状态或拼 URL 导航，而非点击真实渲染元素。
# 硬违规——这两类在 Page Object 里几乎无正当用途，且是"反复超时卡在列表页"的高发根因：
PAGE_NAV_VIOLATION_PATTERNS = [
    (re.compile(r"__vue__"),
     "Page Object 读取 Vue 内部状态 __vue__（构建/版本相关、极脆弱、常返回 None）：禁止靠它取数据再拼 URL 导航；列表→详情应点击该行真实渲染的实体名链接 / 行内操作进入"),
    (re.compile(r"\.evaluate\([^\n]*\.click\(\)"),
     "用 evaluate 合成 .click()（合成事件触发不了 Vue 的 @click、常静默失败、还易引发 dialog 异常）：改用 Playwright 原生定位后 .click()"),
]
# 告警——多数情况是反模式，但保留少量正当导航的可能，故只提示、不阻断：
PAGE_NAV_WARN_PATTERNS = [
    (re.compile(r"=\s*f?[\"'][^\"'\n]*#/"),
     "疑似手动拼接前端路由（#/...）用于导航：列表→详情应点击行内实体名链接，不要自己拼 URL 再 page.goto（拼 URL 脆弱、易因缺参/重定向停在列表页）"),
    (re.compile(r"\.goto\(\s*f[\"']"),
     "page.goto() 跳转 f-string 构造的 URL：导航应走 goto_service/goto_submenu 或点击真实元素，避免写死/拼接 URL"),
]

# JS 填表反模式（通用·跨模块）：用 page.evaluate 里的合成事件/JS 直接填表，骗不过 Vue/Element UI 的
# 响应式校验（v-model 不更新、必填项被判空、提交按钮一直 disabled），是"创建表单提交不了、反复超时"的高发根因。
# 这些 token 只会出现在 evaluate 的 JS 串里，扫页面对象 .py 即可命中，正当 Playwright 代码不会误伤。
PAGE_JSFILL_VIOLATION_PATTERNS = [
    (re.compile(r"dispatchEvent\(\s*new\s+Event\(\s*['\"](input|change)"),
     "用 evaluate 合成 input/change 事件填表（dispatchEvent(new Event('input'/'change'))）：合成事件常骗不过 Element UI 校验，v-model 不更新、必填项被判空、提交按钮保持 disabled。改用原生 fill()/点选项触发真实事件链"),
    (re.compile(r"\.el-select-dropdown__item"),
     "用 JS 直接点 .el-select-dropdown__item 选下拉项：易选错/未触发 @change，子网等必填项实际没赋值。改用原生：点 el-select → 等选项可见 → 按文案 .click() 选项"),
    (re.compile(r"setTimeout\s*\("),
     "页面对象里出现 setTimeout（必在 evaluate 的 JS 串内）：page.evaluate 一返回就不等这个异步回调，是典型竞态 bug（如『盲选下拉』）。改用 Playwright 原生等待（expect/wait_for_selector），不要在 JS 里 setTimeout"),
]


def _iter_test_files(paths):
    """把入参（文件或目录）展开为 test_*.py 文件列表。目录递归。"""
    files = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            print(f"错误：路径不存在：{p}", file=sys.stderr)
            continue
        if p.is_dir():
            files.extend(sorted(p.rglob(TEST_FILE_GLOB)))
        elif p.name.startswith("test_") and p.suffix == ".py":
            files.append(p)
        else:
            # 显式提示：传入了非 test_*.py 文件（如 page object），本门禁不扫描它
            print(f"提示：跳过非测试层文件（门禁只扫描 test_*.py）：{p}")
    return files


def _read(path):
    """读文件文本；失败显式处理并返回 None（不把异常甩给调用者）。

    用 utf-8-sig 兼容带 BOM 的源文件（否则 ast.parse 会把 BOM 误判为语法错误）。
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        print(f"提示：读取失败，跳过 {path}：{e}")
        return None


def _scan_line_patterns(path, source, patterns):
    """逐行匹配正则模式，命中即记 文件:行:原因。"""
    violations = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pat, reason in patterns:
            if pat.search(line):
                violations.append(f"{path}:{lineno}: {reason}")
    return violations


def _scan_try_in_test_methods(path, source):
    """用 AST 精确判定：test_ 开头的测试方法体内是否出现 try/except 或 try/finally。

    仅命中「测试主流程包裹」，不误伤页面对象层或 fixture（本脚本只扫 test_*.py，
    且只看名字以 test_ 开头的函数）。
    """
    violations = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        violations.append(f"{path}:{e.lineno or 0}: 语法错误，无法解析（先修复语法）：{e.msg}")
        return violations
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Try):
                    violations.append(
                        f"{path}:{sub.lineno}: 测试方法 {node.name} 体内出现 try/except|finally 包裹核心步骤"
                        f"（清理用 fixture 的 yield 管理，异常应真实抛出）"
                    )
    return violations


def _load_declared_markers(pytest_ini):
    """从 pytest.ini 的 [pytest] markers = 段读取已声明 marker 名。读不到返回 None。"""
    ini = Path(pytest_ini)
    text = _read(ini) if ini.exists() else None
    if text is None:
        return None
    declared = set()
    in_markers = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^markers\s*=", stripped):
            in_markers = True
            stripped = re.sub(r"^markers\s*=", "", stripped).strip()
            if stripped:
                declared.add(stripped.split(":", 1)[0].strip())
            continue
        if in_markers:
            # markers 是缩进续行；遇到下一个顶格 key 或空行结束
            if not line.startswith((" ", "\t")) or "=" in stripped and ":" not in stripped:
                in_markers = False
            elif stripped:
                declared.add(stripped.split(":", 1)[0].strip())
    return {m for m in declared if m}


def _scan_unregistered_markers(path, source, declared_markers):
    """命中使用了但未在 pytest.ini 登记的自定义 marker。declared_markers 为 None 时跳过本检查。"""
    if declared_markers is None:
        return []
    violations = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for m in MARK_USAGE_PATTERN.findall(line):
            if m in BUILTIN_MARKERS or m in declared_markers:
                continue
            violations.append(f"{path}:{lineno}: 使用了未在 pytest.ini 登记的 marker @pytest.mark.{m}（新增 marker 必须同步 pytest.ini）")
    return violations


def _dotted_name(node):
    """把 a.b.c 形式的属性/名字节点还原成点号字符串；非此类返回 None。"""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    if not parts:
        return None
    return ".".join(reversed(parts))


def _parametrize_multiplier(decorator):
    """若 decorator 是 @pytest.mark.parametrize(...)，返回 (该装饰器贡献的用例倍数, 是否无法静态判定)；
    否则返回 None。多个 parametrize 叠加时为笛卡尔积（由调用方连乘）。"""
    if not isinstance(decorator, ast.Call):
        return None
    name = _dotted_name(decorator.func)
    if name is None or not name.endswith("parametrize"):
        return None
    # parametrize(argnames, argvalues, ...)：argvalues 为第 2 个位置参或关键字参 argvalues
    argvalues = decorator.args[1] if len(decorator.args) >= 2 else None
    for kw in decorator.keywords:
        if kw.arg == "argvalues":
            argvalues = kw.value
    if isinstance(argvalues, (ast.List, ast.Tuple, ast.Set)):
        return (max(len(argvalues.elts), 1), False)
    # argvalues 非字面量（变量/推导式等）→ 无法静态计数，记 1 并标记不确定
    return (1, True)


def _count_tests(source, path):
    """返回 (def test_ 方法数, 展开 parametrize 后的用例数, 是否存在无法静态计数的 parametrize)。"""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        # 语法错误时退化为正则数方法数（用例数同方法数，语法问题另有专门校验报出）
        m = len(re.findall(r"^\s*(?:async\s+)?def\s+test_\w+", source, flags=re.MULTILINE))
        return m, m, False
    methods = 0
    cases = 0
    indeterminate = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            methods += 1
            mult = 1
            for dec in node.decorator_list:
                res = _parametrize_multiplier(dec)
                if res is not None:
                    mult *= res[0]
                    indeterminate = indeterminate or res[1]
            cases += mult
    return methods, cases, indeterminate


def _project_root():
    """向上回溯定位含 sugon_web 包的仓库根；找不到回退当前目录。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "sugon_web").is_dir():
            return parent
    return Path.cwd()


def _resolve_page_object_files(source, root):
    """从测试文件源码里解析出它引用的 Page Object 文件路径（sugon_web/pages/ 下）。

    扫描 `from sugon_web.pages... import` 与 `import sugon_web.pages...`，把模块点路径
    映射为仓库内 .py 文件。仅返回真实存在的文件。
    """
    pages_files = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return pages_files
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("sugon_web.pages"):
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("sugon_web.pages"):
                    mods.append(a.name)
    for m in mods:
        rel = Path(*m.split("."))
        cand = root / rel.with_suffix(".py")
        if cand.is_file():
            pages_files.add(cand)
        pkg_init = root / rel / "__init__.py"
        if pkg_init.is_file():
            pages_files.add(pkg_init)
    return pages_files


def _parse_since(s):
    """把 --since 解析为 epoch 秒。支持纯 epoch、'YYYY-MM-DD HH:MM[:SS]'。失败返回 None。"""
    if not s:
        return None
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return time.mktime(time.strptime(s, fmt))
        except ValueError:
            continue
    return None


def _check_recon_gate(test_files, explicit_page_files, recon_dir, since_epoch):
    """新建/本轮改动了 Page Object，却没有对应运行时侦察产物 → 违规。

    机械依据：recon_page.py 会把整页截图落盘到 skill_runs/recon/（recon_*.png / probe_after_*.png）。
    若本次涉及 Page Object（新建或本轮 mtime 晚于 --since），而 recon 目录里没有本次产生的
    侦察产物（同样按 --since 过滤），即判定"凭空猜了页面结构、未先侦察"——这正是本次 lbv2
    把内联表单误判成弹窗、耗尽阶段三额度的根因。返回违规列表（0 或 1 条）。
    """
    root = _project_root()
    # 1) 收集本次涉及的 Page Object 文件
    page_files = set(Path(p) for p in (explicit_page_files or []))
    if not page_files:
        for tf in test_files:
            src = _read(tf)
            if src is not None:
                page_files |= _resolve_page_object_files(src, root)
    # 2) 若指定 --since，只考虑本轮新建/改动的 Page Object
    in_scope = []
    for pf in sorted(page_files):
        if not pf.exists():
            continue
        if since_epoch is not None:
            try:
                if pf.stat().st_mtime < (since_epoch - 2):
                    continue
            except OSError:
                continue
        in_scope.append(pf)
    if not in_scope:
        print("[recon 门禁] 本次未检测到新建/本轮改动的 Page Object，跳过侦察门禁。")
        return []
    # 3) 统计本次产生的侦察产物
    rdir = Path(recon_dir)
    if not rdir.is_absolute():
        rdir = root / recon_dir
    artifacts = []
    if rdir.is_dir():
        for pat in ("recon_*.png", "probe_after_*.png"):
            for a in rdir.glob(pat):
                if since_epoch is not None:
                    try:
                        if a.stat().st_mtime < (since_epoch - 2):
                            continue
                    except OSError:
                        continue
                artifacts.append(a)
    if artifacts:
        print(f"[recon 门禁] 通过：检测到 {len(artifacts)} 个本次侦察产物，覆盖 {len(in_scope)} 个 Page Object。")
        return []
    files_str = "、".join(str(p.relative_to(root)) if str(p).startswith(str(root)) else str(p) for p in in_scope)
    return [
        f"[recon 门禁]: 本次新建/改动了 Page Object（{files_str}），但 {recon_dir} 下无对应运行时侦察产物。"
        f"编写/修改 Page Object 前【必须先跑 recon_page.py 侦察真实渲染态】，严禁凭需求文案猜页面结构"
        f"（如弹窗 vs 内联表单）。请执行："
        f"python .claude/skills/test-script-dev/scripts/recon_page.py --service \"<服务>\" [--submenu \"<子菜单>\"] "
        f"[--probe-click \"<按钮文案>\"]，再重跑本门禁。"
    ]


def _conftest_chain(test_file, root):
    """返回该测试文件所在目录到仓库根之间所有存在的 conftest.py。

    测试常通过 conftest 里的 fixture（如 slb_page）间接使用 Page Object，
    Page Object 不在测试文件的 import 里，故需顺路扫 conftest 的 pages 导入，避免漏检。
    """
    out = []
    try:
        d = test_file.resolve().parent
        root = root.resolve()
    except OSError:
        return out
    while True:
        cf = d / "conftest.py"
        if cf.is_file():
            out.append(cf)
        if d == root or d.parent == d:
            break
        d = d.parent
    return out


def _resolve_page_files_in_scope(test_files, explicit_page_files, since_epoch):
    """解析本次该检查的 Page Object 文件，按精准度从高到低：
      1) 显式 --page-files；
      2) 有 --since（阶段二/三 workflow 一定带）：直接扫 sugon_web/pages 下【本轮 mtime 改动过】的文件
         —— 精准命中"本次任务新建/改动的 Page Object"，不依赖脆弱的 import 解析，也不误伤未改动的历史文件；
      3) 无 --since（手动跑兜底）：从测试文件 + 其路径上的 conftest（fixture 常在此引入 Page Object）解析导入。
    """
    root = _project_root()
    if explicit_page_files:
        cand = set(Path(p) for p in explicit_page_files)
    elif since_epoch is not None:
        cand = set()
        pages_dir = root / "sugon_web" / "pages"
        if pages_dir.is_dir():
            for p in pages_dir.rglob("*.py"):
                if p.name != "__init__.py":
                    cand.add(p)
    else:
        cand = set()
        for tf in test_files:
            src = _read(tf)
            if src is not None:
                cand |= _resolve_page_object_files(src, root)
            for cf in _conftest_chain(Path(tf), root):
                csrc = _read(cf)
                if csrc is not None:
                    cand |= _resolve_page_object_files(csrc, root)
    in_scope = []
    for pf in sorted(cand):
        if not pf.exists():
            continue
        if since_epoch is not None:
            try:
                if pf.stat().st_mtime < (since_epoch - 2):
                    continue
            except OSError:
                continue
        in_scope.append(pf)
    return in_scope


def _check_page_object_nav_antipattern(test_files, explicit_page_files, since_epoch):
    """机检 Page Object 层「靠框架内部状态/拼 URL 导航，而非点击真实渲染元素」这一类通用反模式。

    跨模块通用（不针对任何具体页面）：
      硬违规：读取 __vue__ 内部数据、用 evaluate 合成 .click()（Vue @click 触发不了、常静默失败）。
      告警：手动拼接 #/ 前端路由、page.goto(f"...") 跳转构造的 URL。
    实测教训：列表→详情若靠 el.__vue__ 取 id 拼 URL 再 page.goto，会因缺参/重定向停在列表页、
    反复 30+ 轮超时仍卡同一页。正确做法是点击该行真实渲染的实体名链接 / 行内操作。
    返回 (violations, warnings)。仅扫描 pages/ 下解析到的（按 --since 过滤的）文件；未涉及/未改动一律不误伤。
    """
    in_scope = _resolve_page_files_in_scope(test_files, explicit_page_files, since_epoch)
    violations, warnings = [], []
    for pf in in_scope:
        src = _read(pf)
        if src is None:
            continue
        violations += _scan_line_patterns(pf, src, PAGE_NAV_VIOLATION_PATTERNS)
        violations += _scan_line_patterns(pf, src, PAGE_JSFILL_VIOLATION_PATTERNS)
        warnings += _scan_line_patterns(pf, src, PAGE_NAV_WARN_PATTERNS)
    return violations, warnings


def _git_repo_root(start):
    """返回包含 start 的 git 仓库根（`git rev-parse --show-toplevel`）；
    不在 git 仓库 / 无 git 命令时返回 None。

    用真实仓库根（而非"含 sugon_web 的目录"）作为 `git show HEAD:<path>` 的相对基准，
    避免 sugon_web 不在仓库根时（如 submodule / .git 在更上层）相对路径错配导致保护静默失效。
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, OSError):
        return None  # 无 git 命令
    if proc.returncode != 0:
        return None  # 不在 git 仓库
    top = proc.stdout.strip()
    return Path(top) if top else None


def _git_head_content(path, repo_root):
    """返回该文件在 git HEAD 的内容；不在 git 仓库 / 未跟踪 / 无 git 命令时返回 None（静默跳过）。

    repo_root 须为 git 真实仓库根（见 _git_repo_root）；path 不在该仓库根下则返回 None。
    """
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None  # 文件不在该仓库根下
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"HEAD:{rel.as_posix()}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, OSError):
        return None  # 无 git 命令
    if proc.returncode != 0:
        return None  # 不是 git 仓库 / 文件未被跟踪 / 无 HEAD
    return proc.stdout


def _check_no_test_deletion(test_files):
    """机械兜底『已有用例只增不减』：与 git HEAD 比对，若某 test_*.py 的 def test_ 方法数变少 → 违规。

    这是为彻底堵死『因 CSV/MD 与既有文件同名 → 整文件覆盖 → 删掉已有用例』的严重事故而加的硬门禁。
    仅在『文件被 git 跟踪且当前方法数 < HEAD 方法数』时报违规；新建文件 / 未跟踪 / 无 git 一律静默跳过，
    不会误伤。本工作流的阶段二/三只应『新增/修改本次相关用例』，绝不应让已有用例总数下降。
    """
    root = _project_root()
    repo_root = _git_repo_root(root) or root
    violations = []
    for path in test_files:
        head_src = _git_head_content(path, repo_root)
        if head_src is None:
            continue
        cur_src = _read(path)
        if cur_src is None:
            continue
        head_methods, _, _ = _count_tests(head_src, path)
        cur_methods, _, _ = _count_tests(cur_src, path)
        if cur_methods < head_methods:
            violations.append(
                f"[已有用例保护]: {path} 的 def test_ 方法数从 git HEAD 的 {head_methods} 个减少到 {cur_methods} 个，"
                f"疑似误删/整文件覆盖了已有用例（严重事故）。【立即停止当前任务】：严禁用 git 或任何其它方式自行补救/恢复，"
                f"在对话框醒目提示用户『测试文件 {path} 的已有用例被误删/覆盖（{head_methods} → {cur_methods} 个），"
                f"需人工从版本库/备份恢复后再继续』，等待用户处理，不要继续往下执行。"
            )
    return violations


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="test-script-dev 静态门禁：首次执行 pytest 前对 test_*.py 做客观机械校验。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("paths", nargs="+", help="一个或多个 test_*.py 文件或包含它们的目录（目录递归）")
    parser.add_argument("--expected-tests", type=int, default=None,
                        help="可选：期望的 def test_ 方法总数（应等于 CSV/MD 场景数）；不一致则报错")
    parser.add_argument("--pytest-ini", default="pytest.ini",
                        help="pytest.ini 路径，用于校验 marker 是否已登记（缺省仓库根目录 pytest.ini）")
    parser.add_argument("--require-recon", action="store_true",
                        help="开启『新建/改动 Page Object 必须先侦察』门禁：本次涉及的 Page Object 若在 recon 目录无侦察产物则报错。"
                             "阶段二新建 Page Object、或遇自定义组件/多步向导时必须带此开关。")
    parser.add_argument("--recon-dir", default=RECON_DIR_DEFAULT,
                        help=f"运行时侦察产物目录（recon_page.py 截图落盘处），默认 {RECON_DIR_DEFAULT}")
    parser.add_argument("--since", default=None,
                        help="可选：只把 mtime 晚于该时刻的 Page Object 视为『本轮改动』、只认该时刻之后的侦察产物。"
                             "建议传本次运行报告头『运行开始时间』（'YYYY-MM-DD HH:MM' 或 epoch 秒）。")
    parser.add_argument("--page-files", nargs="*", default=None,
                        help="可选：显式指定本次涉及的 Page Object 文件（不传则从测试文件 import 自动解析）。")
    return parser.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    files = _iter_test_files(args.paths)
    if not files:
        print("错误：未找到任何 test_*.py 文件可校验。用 --help 查看用法。", file=sys.stderr)
        return 2

    declared_markers = _load_declared_markers(args.pytest_ini)
    if declared_markers is None:
        print(f"提示：未读到 {args.pytest_ini} 的 markers 声明，跳过 marker 登记校验。")

    all_violations = []
    total_methods = 0
    total_cases = 0
    indeterminate = False
    for path in files:
        source = _read(path)
        if source is None:
            continue
        m, c, ind = _count_tests(source, path)
        total_methods += m
        total_cases += c
        indeterminate = indeterminate or ind
        all_violations += _scan_line_patterns(path, source, LOW_LEVEL_API_PATTERNS)
        all_violations += _scan_line_patterns(path, source, FIXED_WAIT_PATTERNS)
        all_violations += _scan_line_patterns(path, source, [SSH_MASK_PATTERN])
        all_violations += _scan_try_in_test_methods(path, source)
        all_violations += _scan_unregistered_markers(path, source, declared_markers)

    count_skipped = False
    if args.expected_tests is not None:
        if total_cases != args.expected_tests:
            all_violations.append(
                f"[数量对齐]: 展开 parametrize 后共 {total_cases} 个测试用例"
                f"（{total_methods} 个 def test_ 方法），期望 {args.expected_tests} 个"
                f"（= CSV 场景数 / MD 场景数）。严禁把多个场景塞进同一个测试方法；"
                f"仅『参数不同的高重复场景』才用 @pytest.mark.parametrize 实现"
            )
    else:
        count_skipped = True

    # 解析 --since（recon 门禁与 Page Object 反模式门禁共用）
    since_epoch = _parse_since(args.since)
    if args.since and since_epoch is None:
        print(f"[WARN] --since 无法解析：{args.since!r}（应为 'YYYY-MM-DD HH:MM' 或 epoch 秒），本次按『不限时间』判定。")

    # 新建/改动 Page Object 必须先侦察（仅 --require-recon 开启时生效）
    recon_skipped = not args.require_recon
    if args.require_recon:
        all_violations += _check_recon_gate(files, args.page_files, args.recon_dir, since_epoch)

    # Page Object 导航/定位反模式（通用·始终执行，跨模块；__vue__/合成 click 为硬违规，拼 URL 为告警）
    nav_violations, nav_warnings = _check_page_object_nav_antipattern(files, args.page_files, since_epoch)
    all_violations += nav_violations

    # 已有用例只增不减（机械兜底·始终执行，防 CSV/MD 同名导致整文件覆盖删除已有用例的严重事故）
    all_violations += _check_no_test_deletion(files)

    # 注：输出统一用 ASCII 标记（[PASS]/[FAIL]），不用 emoji——
    # Windows 控制台默认 GBK，emoji 会触发 UnicodeEncodeError（solve, don't punt）。
    print("\n========== 静态门禁结果 ==========")
    print(f"扫描文件 {len(files)} 个，def test_ 方法 {total_methods} 个，展开 parametrize 后用例 {total_cases} 个。")
    if count_skipped:
        print("[WARN] 未提供 --expected-tests，已【静默跳过】数量对齐门禁。"
              "强烈建议传入 CSV 场景数以启用：--expected-tests <场景数>")
    elif indeterminate:
        print("[WARN] 存在 argvalues 非字面量列表的 parametrize，用例数可能统计不准，请人工复核数量对齐。")
    if recon_skipped:
        print("[WARN] 未提供 --require-recon，已【跳过】『新建 Page Object 必须先侦察』门禁。"
              "本次若新建/改动了 Page Object（或遇自定义组件/多步向导），强烈建议加 --require-recon。")
    if nav_warnings:
        print(f"[WARN] Page Object 导航疑似反模式 {len(nav_warnings)} 处（不阻断，但强烈建议改为点击真实元素导航）：")
        for w in nav_warnings:
            print(f"  - {w}")
    if not all_violations:
        print("[PASS] 门禁通过：未发现可机器判定的规范违规。")
        print("（注意：门禁只兜底机械项，断言分层/需求语义对齐仍须按阶段二对齐检查完成。）")
        print("==================================\n")
        return 0
    print(f"[FAIL] 门禁未通过：发现 {len(all_violations)} 处违规，须修复后重跑门禁：")
    for v in all_violations:
        print(f"  - {v}")
    print("==================================\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
