#!/usr/bin/env python3
"""
多环境调度配置生成器。

职责：
- 读取 env.yaml 或 ENV_DISPATCH 输入（YAML/JSON 格式）
- 计算 marker 表达式、合并相同 host+stor 任务、生成默认兜底任务
- ENV_DISPATCH 中无 modules/services/mark 的条目会被识别为默认执行环境
- 输出 dispatch-jobs.txt（Jenkins 用字符串 split 即可解析）
- 同时输出 dispatch-jobs.json（便于人工查看调试）

设计原因：
Jenkins Script Security 沙箱禁用了 groovy.json.JsonSlurper / JsonSlurperClassic /
JsonOutput 等 JSON 处理类。把所有解析与调度计算放到 Docker 镜像中的 Python
脚本执行，可彻底避开 Jenkins 沙箱与 CPS 序列化限制。
"""
import argparse
import json
import sys

import yaml


def normalize_dispatch(dispatch):
    """把 dispatch 规范化为列表（支持单个对象或对象列表）。"""
    if not dispatch:
        return []
    if isinstance(dispatch, list):
        return dispatch
    return [dispatch]


def build_mark_expr(job):
    """构造单个 dispatch job 的 marker 表达式（modules/services/mark）。"""
    expr = (job.get("mark") or "").strip()
    if not expr and job.get("modules"):
        expr = " or ".join(job["modules"])
    if not expr and job.get("services"):
        expr = " or ".join(job["services"])
    return expr


def is_bms_only_job(job):
    """BMS lifecycle cases must be dispatched as an isolated serial pytest job."""
    modules = set(job.get("modules") or [])
    services = set(job.get("services") or [])
    return modules == {"bms"} and not services and not (job.get("mark") or "").strip()


def combine_with_global_mark(global_mark, dispatch_expr):
    """把全局 MARK 和 dispatch 表达式组合起来。"""
    gm = (global_mark or "").strip()
    if dispatch_expr == "bms":
        return "bms"
    if not gm and not dispatch_expr:
        return ""
    if not gm:
        return dispatch_expr
    if not dispatch_expr:
        return gm
    return f"({gm}) and ({dispatch_expr})"


def validate_jobs(data):
    """校验调度任务列表格式，支持默认环境条目。

    无 modules/services/mark 的条目被视为默认环境配置，用于兜底任务。
    返回 (default_config, dispatch_jobs)。
    """
    if data is None:
        raise ValueError("调度配置不能为空")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError(f"调度配置必须是数组或单个对象，当前类型: {type(data)}")

    default_config = None
    dispatch_jobs = []

    for idx, job in enumerate(data):
        if not isinstance(job, dict):
            raise ValueError(f"调度配置第 {idx + 1} 项必须是对象，当前: {job}")
        if not job.get("host"):
            raise ValueError(f"调度配置第 {idx + 1} 项缺少必填字段 host: {job}")

        normalized = {
            "host": str(job["host"]),
            "modules": job.get("modules") or [],
            "services": job.get("services") or [],
            "mark": job.get("mark") or "",
            "stor": job.get("stor") or "xstor",
            "parallel_count": str(job.get("parallel_count") or ""),
            "bms": job.get("bms") or {},
        }

        # 无 modules/services/mark 的条目视为默认执行环境
        is_default = not (normalized["modules"] or normalized["services"] or normalized["mark"])
        if is_default:
            if default_config is not None:
                raise ValueError("调度配置中只能有一个默认环境条目（无 modules/services/mark）")
            default_config = normalized
        else:
            dispatch_jobs.append(normalized)

    return default_config, dispatch_jobs


def load_from_env_yaml(path, target_hosts=None):
    """从 env.yaml 加载 dispatch 配置。"""
    with open(path, "r", encoding="utf-8") as f:
        env_cfg = yaml.safe_load(f)

    dispatch_jobs = []
    target_hosts = {h.strip() for h in (target_hosts or "").split(",") if h.strip()}

    for env_item in env_cfg.get("env", []):
        stors = env_item.get("stors") or []
        if not stors:
            print(f"跳过 host {env_item['host']}：未配置 stors", file=sys.stderr)
            continue

        dispatches = normalize_dispatch(env_item.get("dispatch"))
        if not dispatches:
            continue

        if target_hosts and env_item["host"] not in target_hosts:
            continue

        for dispatch in dispatches:
            stor = dispatch.get("stor") or stors[0]
            if stor not in stors:
                raise ValueError(
                    f"host {env_item['host']} 的 dispatch 配置了不支持的 stor: {stor}，"
                    f"该环境支持的 stor: {stors}"
                )

            dispatch_jobs.append(
                {
                    "host": env_item["host"],
                    "modules": dispatch.get("modules") or [],
                    "services": dispatch.get("services") or [],
                    "mark": dispatch.get("mark") or "",
                    "stor": stor,
                    "parallel_count": dispatch.get("parallel_count") or "",
                    "bms": dispatch.get("bms") or {},
                }
            )

    return dispatch_jobs


def build_run_jobs(dispatch_jobs, global_mark, default_host, default_stor, default_parallel_count="2"):
    """构建最终执行任务列表（含默认兜底任务）。"""
    # 合并相同 host+stor 的调度任务，避免 label 冲突并减少容器数
    merged = {}
    for job in dispatch_jobs:
        job_kind = "bms" if is_bms_only_job(job) else "normal"
        key = (job["host"], job["stor"], job_kind)
        expr = build_mark_expr(job)
        if key not in merged:
            merged[key] = {
                "host": job["host"],
                "stor": job["stor"],
                "kind": job_kind,
                "expr": expr,
                "modules": set(job.get("modules") or []),
                "services": set(job.get("services") or []),
                "parallel_count": job.get("parallel_count") or "",
                "bms": job.get("bms") or {},
            }
        else:
            merged[key]["modules"].update(job.get("modules") or [])
            merged[key]["services"].update(job.get("services") or [])
            if expr:
                existing = merged[key]["expr"]
                merged[key]["expr"] = f"({existing}) or ({expr})" if existing else expr
            if job.get("parallel_count"):
                merged[key]["parallel_count"] = job["parallel_count"]
            if job.get("bms"):
                merged[key]["bms"].update(job["bms"])

    # 构建 runJobs
    run_jobs = []
    for job in merged.values():
        label = f"env-{job['host'].replace('.', '-')}-{job['stor']}"
        if job.get("kind") == "bms":
            label = f"{label}-bms"
        run_jobs.append(
            {
                "host": job["host"],
                "stor": job["stor"],
                "markExpr": combine_with_global_mark(global_mark, job["expr"]),
                "label": label,
                "modules": sorted(job["modules"]),
                "services": sorted(job["services"]),
                "parallel_count": job.get("parallel_count") or "",
                "bms": job.get("bms") or {},
            }
        )

    # 默认兜底任务：全局 MARK 且不在任何已分配 marker 中
    assigned_exprs = [f"({job['expr']})" for job in merged.values() if job["expr"]]
    assigned_marks = " or ".join(assigned_exprs)
    default_expr = f"not ({assigned_marks})" if assigned_marks else ""
    run_jobs.append(
        {
            "host": default_host,
            "stor": default_stor,
            "markExpr": combine_with_global_mark(global_mark, default_expr),
            "label": "env-default",
            "modules": [],
            "services": [],
            "parallel_count": default_parallel_count,
            "bms": {},
        }
    )

    return run_jobs


def write_text_output(run_jobs, path):
    """
    写入供 Jenkins 直接读取的简单文本文件。

    格式：
    第一行为任务数量 N
    接下来 N 行，每行 6 个字段，用制表符 \t 分隔：
        host\tstor\tmarkExpr\tlabel\tparallel_count\tbms

    使用 \t 作为分隔符，因为 host 是 IP、stor 是标识、label 是 env-...，
    marker 表达式中通常不会包含制表符。
    """
    lines = [str(len(run_jobs))]
    for job in run_jobs:
        host = job["host"]
        stor = job["stor"]
        mark_expr = job["markExpr"]
        label = job["label"]
        parallel_count = job.get("parallel_count") or ""
        bms = json.dumps(job.get("bms") or {}, ensure_ascii=False)
        # 制表符和换行是 marker 表达式中不可能出现的字符，安全作为分隔符
        lines.append(f"{host}\t{stor}\t{mark_expr}\t{label}\t{parallel_count}\t{bms}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="输入文件：env.yaml 或 env-dispatch-input.yaml")
    parser.add_argument(
        "--use-env-dispatch", action="store_true", help="输入是 ENV_DISPATCH 格式"
    )
    parser.add_argument("--mark", default="", help="全局 MARK")
    parser.add_argument("--host", default="172.22.1.190", help="默认环境 HOST")
    parser.add_argument("--stor", default="xstor", help="默认环境 STOR")
    parser.add_argument("--parallel", default="2", help="默认并行数")
    parser.add_argument("--hosts", default="", help="逗号分隔的目标 host 列表")
    parser.add_argument(
        "--output-json", default="dispatch-jobs.json", help="JSON 输出文件"
    )
    parser.add_argument(
        "--output-txt", default="dispatch-jobs.txt", help="文本输出文件"
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if args.use_env_dispatch:
        default_config, dispatch_jobs = validate_jobs(data)
        if default_config:
            args.host = default_config["host"] or args.host
            args.stor = default_config["stor"] or args.stor
            args.parallel = default_config["parallel_count"] or args.parallel
    else:
        dispatch_jobs = load_from_env_yaml(args.input, args.hosts)

    run_jobs = build_run_jobs(dispatch_jobs, args.mark, args.host, args.stor, args.parallel)

    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(run_jobs, f, ensure_ascii=False, indent=2)

    write_text_output(run_jobs, args.output_txt)

    print(f"生成 {len(run_jobs)} 个调度任务（含默认兜底）", file=sys.stderr)


if __name__ == "__main__":
    main()
