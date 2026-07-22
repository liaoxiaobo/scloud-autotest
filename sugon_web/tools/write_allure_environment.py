#!/usr/bin/env python3
"""
生成 Allure 汇总 environment.properties。

职责：
- 读取 dispatch-jobs.json，汇总本次构建涉及的所有环境
- 写入 allure-result/environment.properties
- 让 Allure 总览页 Environment 小部件展示所有参与环境，而不是只有一个
"""
import argparse
import json
import re
import sys
from pathlib import Path


def _summarize_mark(job):
    """根据 modules/services 或 marker 表达式生成简明的执行范围描述。"""
    label = job.get("label", "")
    if label == "env-default":
        return "其他未分配用例"

    modules = job.get("modules") or []
    services = job.get("services") or []
    if modules or services:
        parts = []
        if modules:
            parts.append(f"模块: {', '.join(modules)}")
        if services:
            parts.append(f"服务: {', '.join(services)}")
        return " / ".join(parts)

    mark_expr = job.get("markExpr", "")
    if not mark_expr:
        return ""

    tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", mark_expr)
    keywords = {"and", "or", "not", "true", "false"}
    markers = sorted({t for t in tokens if t.lower() not in keywords})
    return ", ".join(markers) if markers else ""


def _escape_props(text):
    """把非 ASCII 字符转成 Java Properties 支持的 \\uXXXX 转义，避免中文乱码。"""
    return "".join(f"\\u{ord(c):04x}" if ord(c) > 127 else c for c in text)


def _parse_run_env(allure_root, env_label):
    """从 pytest 为单环境生成的 environment.properties 中解析补充信息。"""
    props_path = Path(allure_root) / env_label / "environment.properties"
    if not props_path.exists():
        return {}

    data = {}
    with open(props_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()

    return {
        "user": data.get("USER", ""),
        "arch": data.get("Arch", ""),
        "version": data.get("VERSION", ""),
        "build_time": data.get("BUILD_TIME", ""),
    }


def write_environment_properties(dispatch_json_path, output_path):
    """根据 dispatch-jobs.json 生成汇总 environment.properties。"""
    dispatch_path = Path(dispatch_json_path)
    if not dispatch_path.exists():
        print(f"dispatch 文件不存在: {dispatch_json_path}", file=sys.stderr)
        return

    with open(dispatch_path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    lines = [
        f"ENV_COUNT={len(jobs)}",
    ]

    allure_root = Path(output_path).parent
    extra_keys = [
        ("user", "USER"),
        ("arch", "Arch"),
        ("version", "VERSION"),
        ("build_time", "BUILD_TIME"),
    ]

    for idx, job in enumerate(jobs, start=1):
        host = job.get("host", "")
        stor = job.get("stor", "")
        env_line = f"{host} / {stor}"
        mark_summary = _summarize_mark(job)
        if mark_summary:
            env_line += f"  |  {mark_summary}"
        lines.append(f"ENV_{idx}={env_line}")

        # 补充该环境独有的 USER / Arch / VERSION / BUILD_TIME
        run_env = _parse_run_env(allure_root, job.get("label", ""))
        for internal_key, display_key in extra_keys:
            value = run_env.get(internal_key, "")
            if value:
                lines.append(f"ENV_{idx}_{display_key}={value}")

    # Allure / Java Properties 默认按 ISO-8859-1 读取 .properties，
    # 直接写 UTF-8 中文会乱码；转义为 \\uXXXX 后任何编码都能正确显示。
    escaped_lines = [_escape_props(line) for line in lines]

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="ascii") as f:
        f.write("\n".join(escaped_lines))
        f.write("\n")

    print(f"已生成汇总 environment.properties: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="根据 dispatch-jobs.json 生成 Allure 汇总 environment.properties"
    )
    parser.add_argument("--dispatch-json", required=True, help="dispatch-jobs.json 路径")
    parser.add_argument("--output", default="allure-result/environment.properties", help="输出文件路径")
    args = parser.parse_args()

    write_environment_properties(
        args.dispatch_json,
        args.output,
    )


if __name__ == "__main__":
    main()
