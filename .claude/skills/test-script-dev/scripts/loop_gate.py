#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
loop_gate.py —— 阶段三/五 回退派发硬闸门（中方案·架构新增）

定位：与 report_check.py / precheck.py 同类的"确定性小校验器"。本脚本不含任何业务判断，
也不发明任何新规则，只做一件客观的事——
    读运行报告里的「循环计数区」 → 比对阈值 → 输出"还能不能再派发一轮"。

为什么需要它（中方案动机）：
    原本 5/7/15 轮、状态冻结这些"停止条件"写在 phase3 正文里，靠子智能体自觉遵守（软约束），
    弱模型长跑时会无视上限继续试错（实测出现过阶段三十几轮失控）。本闸门把"要不要再来一轮"
    的决定权从子智能体收回到编排层：编排层每次回退派发 phase3 前先跑本脚本，退出码非 0 就
    强制停止、不再派发。刹车从"软约束"升级为"硬控制"，且不依赖模型当天是否听话。

为什么读文件而不读对话（抗上下文压缩）：
    阶段三多轮修复时，即便在子智能体的 fresh context 内也可能触发上下文压缩导致"忘记第几轮"。
    本脚本只读运行报告磁盘文件中的「循环计数区」，不依赖任何对话记忆——只要计数"每轮就落盘"，
    压缩遗忘也不影响裁决结果。

阈值来源（全部来自子智能体内联正文，本脚本不改判定逻辑，仅做机器比对）：
    - 单用例修复轮次上限 5（触发进展奖励 → 7）  见 phase3-execution 正文「三、3.1 / 3.2」
    - 全局修复轮次上限 15                        见 phase3-execution 正文「三、3.5」
    - 状态冻结：连续 2 轮无变化                   见 phase3-execution 正文「三、3.3」
    - 阶段五回退同一根因修复次数上限 2           见 phase5-stability 正文回退约束
  注：以上数字若与正文不一致，一律以正文为准并同步修正本脚本，严禁出现"第二套阈值"。

运行报告中须存在「循环计数区」结构化块（由编排层 SKILL.md 维护），格式（标记之间为一张表）：
    <!-- LOOP_COUNTER_BLOCK_START -->
    | 计数项 | 标识 | 当前值 | 上限 |
    |---|---|---|---|
    | global_fix_rounds |  | 3 | 15 |
    | case_fix_rounds | test_xxx | 2 | 5 |
    | freeze_same_rounds | test_xxx | 1 | 2 |
    | heal_same_rootcause | <根因标识> | 0 | 2 |
    <!-- LOOP_COUNTER_BLOCK_END -->
  说明：单用例上限是否被进展奖励抬到 7，由编排层在"上限"列写入生效值（5 或 7），脚本只比对。

退出码：
    0  允许再派发一轮（所有相关计数均未达上限）
    1  已达上限，禁止再派发（编排层须按正文规则标记"遗留问题"并停止回退）；stdout 打印命中原因
    2  计数区缺失 / 无法解析 / 缺必需行（**不放行**：宁可暴露问题，也绝不在缺数据时假装通过）

用法：
    python loop_gate.py <运行报告 md 路径> [--case <用例名>] [--rootcause <根因标识>]
        不带 --case/--rootcause：只校验全局轮次（global_fix_rounds）。
        带 --case：额外校验该用例的 case_fix_rounds 与 freeze_same_rounds。
        带 --rootcause：额外校验阶段五回退的 heal_same_rootcause。
"""

import argparse
import re
import sys

BLOCK_START = "<!-- LOOP_COUNTER_BLOCK_START -->"
BLOCK_END = "<!-- LOOP_COUNTER_BLOCK_END -->"


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

    if blocked:
        print("[loop_gate] 禁止再派发（退出码 1）。命中以下停止条件：")
        for b in blocked:
            print("  - " + b)
        print("编排层须按正文规则标记『遗留问题』并停止该回退分支，不得再派发子智能体。")
        sys.exit(1)

    print("[loop_gate] 允许再派发一轮（退出码 0）：所有相关计数均未达上限。")
    sys.exit(0)


if __name__ == "__main__":
    main()
