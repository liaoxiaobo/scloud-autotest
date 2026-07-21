#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loop_gate.py —— 阶段三/五 回退派发硬闸门（中方案·架构新增）

定位：与 report_check.py / precheck.py 同类的"确定性小校验器"。本脚本不含任何业务判断，
也不发明任何新规则，只做一件客观的事——
    读运行报告里的「循环计数区」 → 比对阈值 → 输出"还能不能再派发一轮"。

为什么需要它（中方案动机）：
    原本各类"停止条件"（次数上限、状态冻结）写在 phase3 正文里，靠子智能体自觉遵守（软约束），
    弱模型长跑时会无视上限继续试错（实测出现过阶段三十几轮失控）。本闸门把"要不要再来一轮"
    的决定权从子智能体收回到编排层：编排层每次回退派发 phase3 前先跑本脚本，退出码非 0 就
    强制停止、不再派发。刹车从"软约束"升级为"硬控制"，且不依赖模型当天是否听话。

为什么读文件而不读对话（抗上下文压缩）：
    阶段三多轮修复时，即便在子智能体的 fresh context 内也可能触发上下文压缩导致"忘记第几轮"。
    本脚本只读运行报告磁盘文件中的「循环计数区」，不依赖任何对话记忆——只要计数"每轮就落盘"，
    压缩遗忘也不影响裁决结果。

阈值来源（统一以 run_guard.py 常量与 SKILL.md「循环计数器持久化」表为准，本脚本不改判定逻辑，
只读运行报告「循环计数区」里"当前值/上限"做机器比对；2026-06-16 团队决策值）：
    - 单用例次数上限 40                          见 phase3-self-heal-repair 正文「三、3.1」
    - 全局次数上限 max(60, 失败用例数×10)            见 phase3-self-heal-repair 正文「三、3.5」
    - 状态冻结：连续 15 次相同失败                 见 phase3-self-heal-repair 正文「三、3.3」
    - 阶段五回退同一根因修复次数上限 8           见 phase5-stability-heal 正文回退约束
    - 全局端到端总时长上限 GLOBAL_DEADLINE_HOURS（默认 12h，2026-06-29 新增·机械兜底）
                                                 见 SKILL.md「全局端到端总时长闸」
  注：本脚本按运行报告计数区"上限"列的实际数值比对，故上述数字变化时改 run_guard 与计数区即可，
      无需改本脚本逻辑；口径为"1 次 pytest = 1 次"。（2026-06-17 团队决策：30/失败用例数×30/10/10 → 20/失败用例数×8/5/5；2026-06-18 阶段五同根因 5 → 8；2026-06-19 冻结 5→10、单用例 20→30、全局下限 20→40；2026-06-21 单用例 30→40、冻结 10→15、全局下限 40→60、每场景 8→10）

运行报告中须存在「循环计数区」结构化块（由编排层 SKILL.md 维护），格式（标记之间为一张表）：
    <!-- LOOP_COUNTER_BLOCK_START -->
    | 计数项 | 标识 | 当前值 | 上限 |
    |---|---|---|---|
    | global_fix_rounds |  | 3 | 80 |
    | case_fix_rounds | test_xxx | 2 | 40 |
    | freeze_same_rounds | test_xxx | 1 | 15 |
    | heal_same_rootcause | <根因标识> | 0 | 8 |
    <!-- LOOP_COUNTER_BLOCK_END -->
  说明：字段名沿用历史命名（global_fix_rounds/case_fix_rounds 等），含义即"次数"；"上限"列由编排层
        按生效阈值写入（单用例 40、全局 max(60,失败用例数×10)、冻结 15、同根因 8），脚本只比对当前值 >= 上限。

退出码：
    0  允许再派发一轮（所有相关计数均未达上限、且未超全局总时长）
    1  已达上限，禁止再派发（编排层须按正文规则标记"遗留问题"并停止回退）；stdout 打印命中原因
       —— 命中项含：全局/单用例次数上限、状态冻结、同根因修复上限、**全局端到端总时长上限**
    2  计数区缺失 / 无法解析 / 缺必需行（**不放行**：宁可暴露问题，也绝不在缺数据时假装通过）

用法：
    python loop_gate.py <运行报告 md 路径> [--case <用例名>] [--rootcause <根因标识>] [--deadline-hours <小时>]
        不带 --case/--rootcause：只校验全局轮次（global_fix_rounds）与全局总时长。
        带 --case：额外校验该用例的 case_fix_rounds 与 freeze_same_rounds。
        带 --rootcause：额外校验阶段五回退的 heal_same_rootcause。
        --deadline-hours：全局端到端总时长上限(小时)，默认 12；自运行报告头「运行开始时间」按真实墙钟计。
        （全局总时长闸始终校验；若运行报告头解析不到「运行开始时间」则自动跳过该闸、不阻断。）
"""

import argparse
import re
import sys
from datetime import datetime

# Windows 控制台默认 GBK，脚本含大量中文；不强制 UTF-8 会出现 `���` 乱码。
# 统一把 stdout/stderr 切到 UTF-8，保证闸门命中原因可读。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

BLOCK_START = "<!-- LOOP_COUNTER_BLOCK_START -->"
BLOCK_END = "<!-- LOOP_COUNTER_BLOCK_END -->"

# 全局端到端总时长上限(小时)：自运行报告头「运行开始时间」按真实墙钟计（含跨夜/空闲）。
# 用于兜住 run_guard 10h 活跃墙钟"只覆盖阶段三、且对阶段五裸跑那几小时不可见"的盲区
# （2026-06-29 新增·实测整套曾连续跑约 12h/跨度近 15h 仍未收尾）。超限即按退出码 1 禁止再派发。
GLOBAL_DEADLINE_HOURS = 12


def _check_global_deadline(text, deadline_hours):
    """读运行报告头「运行开始时间」，按真实墙钟算端到端已耗时；>= deadline_hours 返回命中原因串，否则 None。

    设计取舍：解析不到「运行开始时间」（旧报告/格式异常）时**跳过本闸、返回 None、不阻断**——
    时长闸是兜底而非主闸，缺数据宁可不拦也不误杀（次数/冻结闸仍照常生效）。
    """
    m = re.search(r"运行开始时间[：:]\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", text)
    if not m:
        return None
    try:
        start = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    elapsed_h = (datetime.now() - start).total_seconds() / 3600.0
    if elapsed_h >= deadline_hours:
        return ("全局端到端总时长已达上限（≈%.1fh ≥ %gh，自运行开始时间 %s 起按真实墙钟计，"
                "独立于 run_guard 阶段三活跃墙钟）" % (elapsed_h, deadline_hours, m.group(1) + " " + m.group(2)))
    return None


def _fail_parse(msg):
    """计数区问题 → 退出码 2，不放行。"""
    print("[loop_gate] 计数区校验失败（不放行，退出码 2）：%s" % msg)
    sys.exit(2)


def parse_counter_block(text):
    """从运行报告全文中抽出「循环计数区」表格，解析为 {(计数项, 标识): (当前值, 上限)}。"""
    if BLOCK_START not in text or BLOCK_END not in text:
        _fail_parse("运行报告中未找到「循环计数区」标记（%s ... %s）。"
                    "编排层必须先写入计数区再调用本闸门。" % (BLOCK_START, BLOCK_END))
    block = text.split(BLOCK_START, 1)[1].split(BLOCK_END, 1)[0]

    counters = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        # 跳过表头行与分隔行
        if cells[0] in ("计数项", "") or set(cells[0]) <= set("-: "):
            continue
        if len(cells) < 4:
            _fail_parse("计数区存在列数不足的行：%r（需要：计数项|标识|当前值|上限）。" % line)
        name, ident, cur_s, limit_s = cells[0], cells[1], cells[2], cells[3]
        cur = _to_int(cur_s, line)
        limit = _to_int(limit_s, line)
        counters[(name, ident)] = (cur, limit)
    if not counters:
        _fail_parse("计数区为空，未解析到任何计数行。")
    return counters


def _to_int(s, line):
    m = re.search(r"-?\d+", s or "")
    if not m:
        _fail_parse("计数区数值无法解析：%r（来自行：%r）。" % (s, line))
    return int(m.group(0))


def _require(counters, name, ident):
    if (name, ident) not in counters:
        label = name if not ident else "%s[%s]" % (name, ident)
        _fail_parse("计数区缺少必需计数行：%s。" % label)
    return counters[(name, ident)]


def main():
    ap = argparse.ArgumentParser(description="阶段三/五 回退派发硬闸门")
    ap.add_argument("report", help="本次运行报告 md 路径")
    ap.add_argument("--case", default=None, help="本轮要回退/重派的用例名（校验单用例轮次与状态冻结）")
    ap.add_argument("--rootcause", default=None, help="阶段五回退的同一根因标识（校验同根因修复次数）")
    ap.add_argument("--deadline-hours", type=float, default=GLOBAL_DEADLINE_HOURS,
                    help="全局端到端总时长上限(小时)，默认 %g；自运行报告头「运行开始时间」按真实墙钟计，"
                         "兜住 run_guard 阶段三活跃墙钟对阶段五裸跑不可见的盲区" % GLOBAL_DEADLINE_HOURS)
    args = ap.parse_args()

    try:
        with open(args.report, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        _fail_parse("无法读取运行报告文件 %s：%s" % (args.report, e))

    counters = parse_counter_block(text)
    blocked = []

    # 1) 全局轮次（始终校验）
    cur, limit = _require(counters, "global_fix_rounds", "")
    if cur >= limit:
        blocked.append("全局修复轮次已达上限（%d/%d，phase3 正文 3.5）" % (cur, limit))

    # 2) 单用例轮次 + 状态冻结（指定 --case 时校验）
    if args.case:
        cur, limit = _require(counters, "case_fix_rounds", args.case)
        if cur >= limit:
            blocked.append("用例 %s 修复轮次已达上限（%d/%d，phase3 正文 3.1/3.2）" % (args.case, cur, limit))
        cur, limit = _require(counters, "freeze_same_rounds", args.case)
        if cur >= limit:
            blocked.append("用例 %s 触发状态冻结（连续 %d 轮无变化 >= %d，phase3 正文 3.3）" % (args.case, cur, limit))

    # 3) 阶段五回退同一根因修复次数（指定 --rootcause 时校验）
    if args.rootcause:
        cur, limit = _require(counters, "heal_same_rootcause", args.rootcause)
        if cur >= limit:
            blocked.append("根因 %s 阶段五回退修复次数已达上限（%d/%d，phase5 正文回退约束）"
                           % (args.rootcause, cur, limit))

    # 4) 全局端到端总时长闸（机械兜底·2026-06-29 新增）：始终校验，独立于次数/冻结闸
    dl = _check_global_deadline(text, args.deadline_hours)
    if dl:
        blocked.append(dl)

    if blocked:
        print("[loop_gate] 禁止再派发（退出码 1）。命中以下停止条件：")
        for b in blocked:
            print("  - " + b)
        print("编排层须按正文规则标记『遗留问题』并停止该回退分支，不得再派发子智能体。")
        sys.exit(1)

    print("[loop_gate] 允许再派发一轮（退出码 0）：所有相关计数均未达上限、且未超全局总时长。")
    sys.exit(0)


if __name__ == "__main__":
    main()
