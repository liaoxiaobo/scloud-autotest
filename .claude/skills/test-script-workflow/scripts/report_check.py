#!/usr/bin/env python3
"""report_check.py — test-script-workflow 运行报告「锚点完整性」校验黑盒脚本。

用途：各 phase 文件末尾「阶段完成时立即输出」要求把规定内容**双写**到运行报告
`skill_runs/test-script-workflow/test-script-workflow_{任务标识}_*.md`。但该输出发生在
每个阶段的「末尾」，距离 phase 文件被读取已隔了大量执行 token，叠加 Claude Code 的
上下文压缩，模型可能凭记忆把规定区块写漏或写简（尤以阶段五 4.4 最重、最易被简化）。
本脚本不执行任何阶段逻辑，只对「已写好的运行报告」做客观的「锚点是否齐全」校验，
把「自证式完成」升级为「机器可判定的闸门」——缺锚点即退出码 1，提示补写后重跑。

与 `precheck.py` 的分工（两者职责不同，故分文件）：
- `precheck.py`：校验**测试代码** `test_*.py` 的静态编码违规（阶段二/三跑 pytest 前）。
- `report_check.py`（本文件）：校验**运行报告 md** 的章节区块是否齐全（各阶段末尾 + 总收尾）。

设计原则：
- **黑盒调用**：直接 `python report_check.py --help` 看用法后执行，不必读源码。
- **只判结构、不判质量**：本脚本只判定「规定章节/表/字段是否出现」；内容是否详实、
  数据是否正确，仍由各阶段自检负责。
- **退出码**：锚点齐全返回 0；有缺失返回 1；用法/环境错误返回 2。

用法示例：
    # 校验阶段五结束时报告是否含 4.4 等全部必出锚点
    python report_check.py skill_runs/test-script-workflow/test-script-workflow_xxx_YYYYMMDD_HHMM.md --phase 5
    # 总收尾前校验全部阶段 + 总收尾锚点齐全
    python report_check.py skill_runs/test-script-workflow/test-script-workflow_xxx_YYYYMMDD_HHMM.md --phase final
    # 也可只校验到某个中间阶段
    python report_check.py <报告md> --phase 3
"""
import argparse
import sys
from pathlib import Path

# 锚点 = 各 phase 文件末尾要求必须出现在报告里的章节标题/表名/字段名的字面字符串。
# 只校验「结构是否齐全」，不校验内容质量（质量仍由阶段自检负责）。
REPORT_ANCHORS = {
    "1": [
        ("## 阶段一：需求转换与校验", "阶段一完成块标题（含完成时间）"),
        ("### 完成清单", "阶段一完成清单表"),
    ],
    "2": [
        ("## 阶段二：脚本编写与对齐", "阶段二完成块标题（含完成时间）"),
        ("### 完成清单", "阶段二完成清单表"),
    ],
    "3": [
        ("## 阶段三：执行用例与修复", "阶段三完成块标题（含完成时间）"),
        ("### 完成清单", "阶段三完成清单表"),
        ("问题清单", "阶段三 5.2 修复循环问题清单"),
    ],
    "4": [
        ("## 阶段四：日志分析与核查", "阶段四完成块标题（含完成时间）"),
        ("### 完成清单", "阶段四完成清单表"),
    ],
    "5": [
        ("## 阶段五：稳定性验证", "阶段五完成块标题（含完成时间）"),
        ("### 完成清单", "4.2 完成清单表"),
        ("问题总结", "4.3 问题总结（阶段一~五全部问题汇总）"),
        ("项目能力复用与经验沉淀", "4.4 独立大章节标题"),
        ("第一部分：项目已有能力复用情况", "4.4 第一部分标题"),
        ("Fixture 复用清单", "4.4 ① Fixture 复用清单表"),
        ("Page Object 公共方法复用清单", "4.4 ② Page Object 公共方法复用清单表"),
        ("辅助函数（Helper）复用清单", "4.4 ③ 辅助函数（Helper）复用清单表"),
        ("断言复用/新增清单", "4.4 ④ 断言复用/新增清单表"),
        ("第二部分：修复经验沉淀总结", "4.4 第二部分 10 列经验沉淀表标题"),
    ],
    "final": [
        ("## 完成后输出", "全局总结标题"),
        ("总体结论", "总结 1. 总体结论"),
        ("执行概览", "总结 2. 执行概览表"),
        ("风险与后续待办", "总结 3. 风险与后续待办"),
        ("产物位置索引", "总结 4. 产物位置索引"),
    ],
}
# 校验某阶段时，其前序阶段块也必须已在报告中（一次运行一个文件、按阶段追加）。
PHASE_ORDER = ["1", "2", "3", "4", "5", "final"]


def _read(path):
    """读文件文本；失败显式处理并返回 None（不把异常甩给调用者）。

    用 utf-8-sig 兼容带 BOM 的文件。
    """
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        print(f"提示：读取失败 {path}：{e}", file=sys.stderr)
        return None


def _validate_report(report_path, phase):
    """校验运行报告是否含「截至 phase（含）所有阶段」要求的锚点。返回违规列表。"""
    p = Path(report_path)
    if not p.exists():
        return [f"运行报告文件不存在：{p}（各阶段须双写到 skill_runs/test-script-workflow/ 下的同一文件）"]
    text = _read(p)
    if text is None:
        return [f"运行报告文件读取失败：{p}"]
    if phase not in PHASE_ORDER:
        return [f"未知阶段 --phase {phase}（可选：1/2/3/4/5/final）"]
    violations = []
    # 校验本阶段及其所有前序阶段的锚点（确保前序阶段块未被覆盖/丢失）
    for ph in PHASE_ORDER[: PHASE_ORDER.index(phase) + 1]:
        for anchor, desc in REPORT_ANCHORS[ph]:
            if anchor not in text:
                violations.append(f"[阶段{ph}] 缺锚点「{anchor}」——{desc}")
    return violations


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="test-script-workflow 运行报告锚点校验：校验各阶段「立即输出」要求的章节是否齐全（对抗上下文压缩导致的漏写/写简）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("report", help="本次运行报告 md 路径（skill_runs/test-script-workflow/ 下）")
    parser.add_argument("--phase", default="final",
                        help="校验到哪个阶段（1/2/3/4/5/final）。默认 final（全部阶段+总收尾）")
    return parser.parse_args(argv)


def main(argv):
    args = _parse_args(argv)
    violations = _validate_report(args.report, str(args.phase))
    print("\n========== 运行报告锚点校验 ==========")
    print(f"报告文件：{args.report}")
    print(f"校验范围：截至阶段 {args.phase}（含前序阶段）")
    if not violations:
        print("[PASS] 报告锚点齐全：各阶段「立即输出」要求的章节/表/字段均已写入报告。")
        print("（注意：本校验只判定结构是否齐全，不判定内容质量；内容详实度仍由各阶段自检负责。）")
        print("======================================\n")
        return 0
    print(f"[FAIL] 报告锚点缺失：发现 {len(violations)} 处，须按对应 phase 文件「阶段完成时立即输出」要求补写后重跑：")
    for v in violations:
        print(f"  - {v}")
    print("提示：补写前请重新 Read 对应 phase 文件末尾的「立即输出」整节，按其确切表头逐表补全，禁止凭记忆精简。")
    print("======================================\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
