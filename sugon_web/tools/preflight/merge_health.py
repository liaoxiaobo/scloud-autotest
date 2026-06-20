from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="合并多个环境的健康巡检 JSON")
    parser.add_argument("files", nargs="+", help="单环境健康 JSON 文件列表")
    parser.add_argument("--output", required=True, help="合并后的多环境健康 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    merged: dict[str, dict[str, Any]] = {}

    for raw_file in args.files:
        path = Path(raw_file)
        env_name = _env_name_from_path(path)
        if not path.exists():
            merged[env_name] = {
                "env_name": env_name,
                "inspection": {
                    "status": "failed",
                    "failed": 1,
                    "warnings": 0,
                    "error": f"健康结果文件不存在: {path}",
                },
            }
            continue

        with path.open("r", encoding="utf-8-sig") as file_obj:
            snapshot = json.load(file_obj)
        env_name = str(snapshot.get("env_name") or env_name)
        merged[env_name] = snapshot

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已合并 {len(merged)} 个环境健康结果: {output}")
    return 0


def _env_name_from_path(path: Path) -> str:
    name = path.stem
    if name.startswith("health_"):
        return name[len("health_"):]
    return name


if __name__ == "__main__":
    raise SystemExit(main())
