#!/usr/bin/env python3
"""precheck.py — test-script-workflow 阶段二/三「静态门禁」黑盒脚本。

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

校验项（全部对 test_*.py「测试层」生效，pages/ 页面对象层不在此列）：
  1. 测试层底层 API：出现 .locator( / playwright import expect / xpath=
  2. 固定等待：出现 wait_for_timeout( / time.sleep(
  3. 测试方法体 try/except|try/finally 包裹（AST 精确判定，仅 test_ 方法）
  4. SSH 掩盖错误：命令串内出现 || true
  5. 新增 marker 未登记：用到的 @pytest.mark.X 未在 pytest.ini 的 markers 声明
  6. 数量对齐（可选）：def test_ 数 ≠ --expected-tests 指定值

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
import sys
from pathlib import Path

# 仅扫描「测试层」文件：文件名形如 test_*.py。pages/ 页面对象层允许底层 API，故不纳入。
TEST_FILE_GLOB = "test_*.py"

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


def _count_test_methods(source):
    return len(re.findall(r"^\s*(?:async\s+)?def\s+test_\w+", source, flags=re.MULTILINE))


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="test-script-workflow 静态门禁：首次执行 pytest 前对 test_*.py 做客观机械校验。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("paths", nargs="+", help="一个或多个 test_*.py 文件或包含它们的目录（目录递归）")
    parser.add_argument("--expected-tests", type=int, default=None,
                        help="可选：期望的 def test_ 方法总数（应等于 CSV/MD 场景数）；不一致则报错")
    parser.add_argument("--pytest-ini", default="pytest.ini",
                        help="pytest.ini 路径，用于校验 marker 是否已登记（缺省仓库根目录 pytest.ini）")
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
    total_tests = 0
    for path in files:
        source = _read(path)
        if source is None:
            continue
        total_tests += _count_test_methods(source)
        all_violations += _scan_line_patterns(path, source, LOW_LEVEL_API_PATTERNS)
        all_violations += _scan_line_patterns(path, source, FIXED_WAIT_PATTERNS)
        all_violations += _scan_line_patterns(path, source, [SSH_MASK_PATTERN])
        all_violations += _scan_try_in_test_methods(path, source)
        all_violations += _scan_unregistered_markers(path, source, declared_markers)

    if args.expected_tests is not None and total_tests != args.expected_tests:
        all_violations.append(
            f"[数量对齐]: 扫描到 def test_ 方法 {total_tests} 个，期望 {args.expected_tests} 个"
            f"（CSV 场景数 / MD 场景数 / 测试方法数三者须一致）"
        )

    # 注：输出统一用 ASCII 标记（[PASS]/[FAIL]），不用 emoji——
    # Windows 控制台默认 GBK，emoji 会触发 UnicodeEncodeError（solve, don't punt）。
    print("\n========== 静态门禁结果 ==========")
    print(f"扫描文件 {len(files)} 个，测试方法 {total_tests} 个。")
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
