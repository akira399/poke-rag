"""一键更新数据与索引（知识库随时更新）。

用法：
    python scripts/update_data.py              # 增量更新（约 2-5 分钟）
    python scripts/update_data.py --full       # 全量（含 PokeAPI 全量拉取，约 30 分钟）
    python scripts/update_data.py --index-only # 只重建索引（改代码后用，约 2 分钟）
    python scripts/update_data.py --only showdown,smogon   # 只更新指定数据源

更新内容：
  1. Showdown 规则数据（图鉴/招式/特性/道具/克制表/学习表）——官方数据，每周有调整
  2. Smogon 月度使用率（环境榜，每月更新）——自动取最新月份
  3. 重建知识卡片（data/cards/*.jsonl）
  4. 重建检索索引（数据更新后必须重建，否则检索仍用旧数据）

PokeAPI 默认不重拉（图鉴中文名/描述极少变动），需要时用 --full。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
NODE = "node"


def _run(cmd: list[str], desc: str) -> bool:
    print(f"\n{'=' * 60}\n▶ {desc}\n{'=' * 60}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT)
    ok = proc.returncode == 0
    print(f"{'✅' if ok else '❌'} {desc}（{time.time() - t0:.0f}s）")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="包含 PokeAPI 全量拉取（慢）")
    ap.add_argument("--index-only", action="store_true", help="只重建检索索引")
    ap.add_argument("--only", default="", help="只更新指定数据源，逗号分隔：pokeapi,showdown,smogon")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    steps: list[tuple[list[str], str]] = []

    if args.index_only:
        steps = [([PY, "scripts/build_index.py"], "重建检索索引")]
    else:
        if args.full or (only and "pokeapi" in only):
            steps.append(([PY, "scripts/fetch_pokeapi.py"], "PokeAPI 全量数据"))
        if not only or "showdown" in only:
            steps.append(([NODE, "scripts/fetch_showdown.mjs"], "Showdown 规则数据"))
        if not only or "smogon" in only:
            steps.append(([PY, "scripts/fetch_smogon.py"], "Smogon 月度使用率"))
        steps.append(([PY, "scripts/build_cards.py"], "重建知识卡片"))
        steps.append(([PY, "scripts/build_index.py"], "重建检索索引"))

    failed = []
    for cmd, desc in steps:
        if not _run(cmd, desc):
            failed.append(desc)
            print(f"⚠️ 「{desc}」失败，继续执行后续步骤（可单独重跑该脚本续传）")

    print(f"\n{'=' * 60}\n更新完成：{len(steps) - len(failed)}/{len(steps)} 步成功")
    if failed:
        print("失败步骤：" + "、".join(failed))
        print("提示：数据拉取均支持断点续传，重跑本脚本即可补齐。")
        return 1
    print("提示：运行中的服务（serve.py / streamlit）需重启才能加载新数据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
