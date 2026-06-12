#!/usr/bin/env python3
"""
给 allure-result 下的测试用例结果注入 host/stor 环境 Tag。

职责：
- 多环境分发执行后，按环境标识找到该环境对应的 allure-result 用例结果
- 兼容 conftest.py 中按测试路径创建子目录的情况（如 allure-result/<run_id>/<env-label>/）
- 以 name="tag" 的 Label 形式注入 host/stor，确保在 Allure 2.29.0 测试详情页可见
- 直接修改 *-result.json，确保 Allure 报告能按环境维度展示和筛选

使用时机：pytest 执行完毕后、Allure 报告生成之前。
"""
import argparse
import json
import sys
from pathlib import Path


def _find_allure_root(result_path):
    """从给定的 alluredir 向上回溯，找到 allure-result 根目录。"""
    current = result_path.resolve()
    while current.name != "allure-result" and current.parent != current:
        current = current.parent
    return current if current.name == "allure-result" else None


def _find_result_files(alluredir, env_label):
    """
    查找需要注入标签的 *-result.json 文件。

    查找策略：
    1. 优先直接在 --alluredir 下查找
    2. 如果未找到且指定了 env-label，则回到 allure-result 根目录，
       按路径中是否包含 env-label 目录名进行匹配
    """
    result_path = Path(alluredir)
    files = []

    # 1. 直接在 alluredir 下查找
    if result_path.exists():
        files = list(result_path.glob("*-result.json"))

    # 2. 如果没找到且指定了 env-label，则在整个 allure-result 树中按 env-label 回溯查找
    if not files and env_label:
        allure_root = _find_allure_root(result_path)
        if allure_root:
            for json_file in allure_root.rglob("*-result.json"):
                try:
                    rel_parts = json_file.relative_to(allure_root).parts
                except ValueError:
                    continue
                # env-label 必须是路径中的一个目录名，避免子串误判
                if env_label in rel_parts:
                    files.append(json_file)

    return files


def inject_environment_tags(alluredir, host, stor, env_label):
    """找到 alluredir 对应的测试用例结果，注入 host/stor 环境 Tag。"""
    tags_to_add = []
    if host:
        tags_to_add.append({"name": "tag", "value": f"host:{host}"})
    if stor:
        tags_to_add.append({"name": "tag", "value": f"stor:{stor}"})

    if not tags_to_add:
        print("没有需要注入的 Tag")
        return

    json_files = _find_result_files(alluredir, env_label)
    if not json_files:
        print(f"未找到需要注入 Tag 的结果文件: alluredir={alluredir}, env-label={env_label}", file=sys.stderr)
        return

    count = 0
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                print(f"跳过损坏的 JSON 文件 {json_file}: {exc}", file=sys.stderr)
                continue

        existing_tag_values = {
            label.get("value")
            for label in data.get("labels", [])
            if label.get("name") == "tag"
        }

        for tag in tags_to_add:
            if tag["value"] not in existing_tag_values:
                data.setdefault("labels", []).append(tag)
                existing_tag_values.add(tag["value"])

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        count += 1

    print(f"已为 {count} 个用例结果注入环境 Tag: host={host}, stor={stor}")


def main():
    parser = argparse.ArgumentParser(
        description="向 allure-result 测试用例结果注入 host/stor 环境 Tag"
    )
    parser.add_argument("--alluredir", required=True, help="allure-result 子目录路径")
    parser.add_argument("--host", default="", help="测试环境 host")
    parser.add_argument("--stor", default="", help="存储类型")
    parser.add_argument("--env-label", default="", help="环境标识，用于定位结果文件，对应 Jenkins 中的 env-label")
    args = parser.parse_args()

    inject_environment_tags(args.alluredir, args.host, args.stor, args.env_label)


if __name__ == "__main__":
    main()
