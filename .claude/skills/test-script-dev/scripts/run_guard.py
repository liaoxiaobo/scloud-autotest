#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_guard.py —— 阶段三 pytest 执行守卫（机械硬熔断·针对 kimi 的"自律失效"而设）。

为什么需要本脚本（根因）：
    阶段三的修复循环跑在【一次 phase3 子智能体派发内部】，编排层看不到"两轮之间"，
    所以 loop_gate.py（设计给编排层在两轮间调用）根本没机会触发；而轮次上限、状态冻结
    等又都是写在 agent 体内、靠模型【自觉执行】的软约束——实测 kimi 在长循环里 0 执行
    （运行报告里轮次一直是 0，却跑了 40+ 次 pytest、耗时 10+ 小时）。
    结论：失控的 agent 不会自己停。刹车必须放在【绕不开的咽喉点】——每一次 pytest 调用。

本脚本把"计数 / 熔断 / 冻结检测"从"模型的责任"变成"跑 pytest 这个动作的不可避免副作用"：
    无论模型是否自觉，只要它经本脚本跑测试，计数就被机械记录、超限就被机械拒绝。
    本脚本【不改变任何编码/定位/规范能力】，只拦"还能不能再跑一轮"。

=== 计数单位的明确定义（务必读懂，避免理解错）===
    本脚本的计数键 = 你传给 pytest 的"测试目标"：
      · `pytest 文件.py -k test_xxx`  → 键 = 该【测试方法 test_xxx】（推荐：阶段三调试单个需求就这么跑）
      · `pytest 文件.py`（不带 -k）   → 键 = 【整个 .py 文件】（首次整文件跑 / 最后整文件验证）
    而"一个测试方法 def test_xxx"在本项目里就对应"测试需求 CSV 文件里的一行（一个测试需求/场景）"
    （阶段二硬规则：一个 CSV 场景 = 一个独立 def test_ 方法）。
    所以："单个用例最多跑 N 次" = "CSV 里的每一个测试需求（= 一个 def test_ 方法，用 -k 单独跑时）
    最多跑 N 次 pytest"。它【不是】指整个 .py 脚本（一个 .py 往往含一个 CSV 文件的多个需求/多个
    def test_ 方法），也【不是】指一次 pytest 命令。

机械控制（全部确定性，不含 LLM 判断，口径极简：1 次 pytest = 1 次）：
    1) 计数：每经本脚本跑一次 pytest，该测试目标计数 +1、全局计数 +1，落盘 state 文件。
    2) 硬熔断（满足任一即退出码 3 拒绝执行）：
         - 单测试目标累计 >= --cap-file（默认 30）
         - 全局累计 >= --cap-global（默认随场景数缩放 = 场景数 × 30）
         - 连续 FREEZE_LIMIT 次"相同失败指纹"（默认 10）→ 原地打转，停。
    3) 冻结检测：连续 N 次失败摘要完全相同 → 判定无进展、拒绝下一轮；只要失败现象变化（有进展）
       或某轮通过，冻结计数立即清零。

退出码：
    0   pytest 通过（透传 pytest 退出码 0）
    1   pytest 失败（透传 pytest 非 0 退出码；未达熔断上限，可在修对根因后再跑）
    3   被守卫拒绝（已达次数上限 或 触发状态冻结）→ 必须停止该测试目标，标记"遗留问题·转人工"，
        严禁绕过本脚本裸跑 pytest 继续试。
    2   用法/环境错误。

用法（阶段三所有 pytest 必须经本脚本跑，禁止裸跑 pytest）：
    # 阶段三开始（首次执行该文件前）先重置本次任务的守卫状态（必须传 --cases 缩放全局上限）：
    python .claude/skills/test-script-dev/scripts/run_guard.py --reset --task <任务标识> --cases <场景数>
    # 之后每次跑 pytest 都经本脚本（-- 之后原样就是平时的 pytest 命令与参数）：
    python .claude/skills/test-script-dev/scripts/run_guard.py --task <任务标识> -- \
        pytest sugon_web/testcase/network/test_xxx.py -k test_xxx --log-file=logs/xxx.log --log-file-level=DEBUG
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Windows 控制台默认 GBK，脚本含大量中文；不强制 UTF-8 会出现 `???` 乱码，
# 让"按提示修复/补写"的反馈环失效。统一把 stdout/stderr 切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

DEFAULT_CAP_FILE = 30          # 单测试目标（= 一个 CSV 需求 / def test_ 方法）次数上限
GLOBAL_PER_CASE = 30           # 全局上限按"每个场景 30 次"加总缩放：场景数 × 该值
DEFAULT_CAP_GLOBAL = 30        # 全局上限下限（1 个场景时）
FREEZE_LIMIT = 10              # 连续相同失败达到该值 → 下一轮拒绝（原地打转、无进展）


def _project_root() -> Path:
    """从脚本位置向上找含 sugon_web 的仓库根；找不到则回退当前目录。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "sugon_web").is_dir():
            return parent
    return Path.cwd()


def _state_path(task, explicit):
    if explicit:
        return Path(explicit)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", task or "default")
    return _project_root() / "skill_runs" / "test-script-dev" / f"_runguard_{safe}.json"


def _load(p):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"global_runs": 0, "files": {}}


def _save(p, state):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _target_key(pytest_args):
    """从 pytest 参数里提取"测试目标"作为计数键：优先 .py 路径（含 ::node），并附带 -k 表达式。"""
    target = None
    kexpr = None
    for i in range(len(pytest_args)):
        a = pytest_args[i]
        if a == "-k" and i + 1 < len(pytest_args):
            kexpr = pytest_args[i + 1]
        elif a.startswith("-k="):
            kexpr = a[3:]
        elif ".py" in a and not a.startswith("-"):
            target = a
    key = target or "<whole-suite>"
    if kexpr:
        key += f"  -k {kexpr}"
    return key


def _log_dir_from_args(pytest_args):
    """从 pytest 参数里提取 --log-file 的所在目录，用于统计该目标的真实运行日志数。"""
    for i, a in enumerate(pytest_args):
        if a.startswith("--log-file="):
            return Path(a.split("=", 1)[1]).parent
        if a == "--log-file" and i + 1 < len(pytest_args):
            return Path(pytest_args[i + 1]).parent
    return None


def _count_real_logs(log_dir, started_at=0):
    """统计日志目录下（含子目录）本次 reset 之后产生的 *.log 数 = 真实 pytest 运行次数。

    只数 mtime >= started_at 的日志：阶段三 --reset 之前就存在的旧日志（阶段二试跑、
    上一次任务残留、同名带时间戳永不覆盖的累积日志）一律不计入本次额度，避免额度被陈旧
    日志提前耗尽。started_at 落空（旧状态/未 reset）时退化为"全部计入"，宁紧勿松。
    """
    if not log_dir or not log_dir.exists():
        return None
    n = 0
    for p in log_dir.rglob("*.log"):
        if not p.is_file():
            continue
        if started_at:
            try:
                # 留 2s 容差，避开 reset 与首个日志落盘之间的时钟抖动
                if p.stat().st_mtime < (started_at - 2):
                    continue
            except OSError:
                continue
        n += 1
    return n


def _failure_fingerprint(output):
    """从 pytest 输出提取失败指纹：取 FAILED/ERROR 短摘要行集合做哈希；无则取末尾非空行。"""
    lines = [l.strip() for l in output.splitlines()]
    sig_lines = [l for l in lines if l.startswith("FAILED ") or l.startswith("ERROR ")]
    if not sig_lines:
        tail = [l for l in lines if l][-6:]
        sig_lines = tail
    blob = "\n".join(sig_lines)
    return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:16]


def _refuse(reason):
    print("\n========== run_guard 拒绝执行（退出码 3）==========")
    print(reason)
    print("→ 必须停止该测试目标的修复循环，按正文规则标记『遗留问题/转人工』。")
    print("→ 严禁绕过本脚本裸跑 pytest 继续试错（裸跑即视为违规）。")
    print("===================================================\n")
    sys.exit(3)


def _ensure_file_entry(state, key):
    """取/建某测试目标的计数项，并补齐字段（兼容旧 state 文件）。"""
    f = state["files"].setdefault(key, {})
    f.setdefault("runs", 0)
    f.setdefault("freeze", 0)
    f.setdefault("last_fp", None)
    return f


def main(argv):
    ap = argparse.ArgumentParser(description="阶段三 pytest 执行守卫（机械硬熔断）", add_help=True)
    ap.add_argument("--task", default="default", help="本次任务标识（= 需求 MD 英文名去 .md）")
    ap.add_argument("--state", default=None, help="守卫状态文件路径（默认按 task 生成）")
    ap.add_argument("--cap-file", type=int, default=DEFAULT_CAP_FILE,
                    help=f"单测试目标(= 一个 CSV 需求/def test_ 方法)次数上限（默认 {DEFAULT_CAP_FILE}）")
    ap.add_argument("--cap-global", type=int, default=DEFAULT_CAP_GLOBAL,
                    help=f"全局次数上限下限（默认 {DEFAULT_CAP_GLOBAL}）；实际取 max(该值, 场景数×{GLOBAL_PER_CASE})")
    ap.add_argument("--reset", action="store_true", help="重置本任务守卫状态（阶段三开始时调一次）")
    ap.add_argument("--cases", type=int, default=None,
                    help=f"本次测试场景数（def test_ 方法数）；用于把全局上限缩放为 max(cap-global, 场景数×{GLOBAL_PER_CASE})，--reset 时传一次")
    ap.add_argument("--pytest-cmd", default="pytest", help="pytest 可执行命令（默认 pytest）")
    if "--" in argv:
        sep = argv.index("--")
        guard_argv, pytest_args = argv[:sep], argv[sep + 1:]
    else:
        guard_argv, pytest_args = argv, []
    args, extra = ap.parse_known_args(guard_argv)
    pytest_args = extra + pytest_args
    # 去掉用户可能误带的开头 "pytest"
    if pytest_args and pytest_args[0] == "pytest":
        pytest_args = pytest_args[1:]

    sp = _state_path(args.task, args.state)

    if args.reset:
        # 全局上限随场景数缩放 = max(下限, 场景数 × 每个场景 30 次)
        eff_global = max(args.cap_global, (args.cases or 0) * GLOBAL_PER_CASE)
        _save(sp, {"global_runs": 0, "files": {}, "started_at": time.time(), "cap_global": eff_global})
        print(f"[run_guard] 已重置守卫状态：{sp}")
        print(f"[run_guard] 次数上限：单用例(= 一个 CSV 需求/def test_ 方法)={args.cap_file} 次、"
              f"全局={eff_global} 次（场景数={args.cases or '未提供'}，公式 max({args.cap_global}, 场景数×{GLOBAL_PER_CASE})）；"
              f"连续相同失败冻结={FREEZE_LIMIT} 次。")
        print(f"[run_guard] 口径：1 次 pytest = 1 次；审计只数本次 reset 之后产生的日志，旧日志不污染额度。")
        if not pytest_args:
            return 0

    if not pytest_args:
        print("[run_guard] 未提供 pytest 命令（-- 之后为空）。用法见 --help。", file=sys.stderr)
        return 2

    state = _load(sp)
    state.setdefault("global_runs", 0)
    cap_global = state.get("cap_global", args.cap_global)
    cap_file = args.cap_file
    key = _target_key(pytest_args)
    f = _ensure_file_entry(state, key)

    # ---- 绕过审计：按日志目录真实 .log 数补算（裸跑绕过也逃不过上限）----
    # 只数 reset 之后的日志，旧日志不再污染额度。
    started_at = state.get("started_at", 0)
    log_dir = _log_dir_from_args(pytest_args)
    real = _count_real_logs(log_dir, started_at)
    if real is not None and real > f["runs"]:
        bypass = real - f["runs"]
        print(f"[run_guard] [!] 绕过审计：日志目录（本次 reset 后）实际有 {real} 次 pytest 运行，"
              f"本守卫该目标仅计 {f['runs']} 次——检测到约 {bypass} 次【未经 run_guard 的裸跑】。")
        print("[run_guard] 已按实际运行数补算：裸跑绕过不会逃过上限。此后所有 pytest 必须经 run_guard 跑。")
        f["runs"] = real
        state["global_runs"] = state["global_runs"] + bypass

    # ---- 执行前硬熔断检查 ----
    if state["global_runs"] >= cap_global:
        _refuse(f"全局次数已达上限（{state['global_runs']}/{cap_global}）。")
    if f["runs"] >= cap_file:
        _refuse(f"测试目标【{key}】次数已达上限（{f['runs']}/{cap_file}）。")
    if f["freeze"] >= FREEZE_LIMIT:
        _refuse(f"测试目标【{key}】触发状态冻结（连续 {f['freeze']} 次相同失败 >= {FREEZE_LIMIT}）——"
                f"同一处反复试错无进展，按正文 3.3 停止。")

    # ---- 计数 +1 并落盘（跑之前就记，确保即使 pytest 崩溃也已计数）----
    state["global_runs"] += 1
    f["runs"] += 1
    _save(sp, state)
    print(f"[run_guard] 第 {f['runs']}/{cap_file} 次（全局 {state['global_runs']}/{cap_global}）"
          f"｜目标：{key}")

    # ---- 跑 pytest，实时打印同时捕获用于指纹 ----
    try:
        proc = subprocess.run([args.pytest_cmd] + pytest_args,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print(f"[run_guard] 找不到 pytest 命令：{args.pytest_cmd}", file=sys.stderr)
        return 2
    output = proc.stdout or ""
    print(output)

    rc = proc.returncode
    if rc == 0:
        f["freeze"] = 0
        f["last_fp"] = None
        _save(sp, state)
        print(f"[run_guard] 本轮通过。目标【{key}】冻结计数已清零。")
        return 0

    # 失败：更新冻结计数（连续相同失败才累加，现象一变即清零）
    fp = _failure_fingerprint(output)
    if fp == f["last_fp"]:
        f["freeze"] += 1
    else:
        f["freeze"] = 1
    f["last_fp"] = fp
    _save(sp, state)
    print(f"[run_guard] 本轮失败（失败指纹 {fp}，连续相同 {f['freeze']}/{FREEZE_LIMIT} 次）。"
          f"该目标剩余 {cap_file - f['runs']} 次、全局剩余 {cap_global - state['global_runs']} 次。")
    if f["freeze"] >= FREEZE_LIMIT:
        print("[run_guard] [!] 已连续相同失败达冻结线——下一轮将被拒绝。"
              "请勿再重复同一修复，改为零基复盘根因或标记遗留问题。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
