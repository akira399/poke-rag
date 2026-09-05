"""M5 · 消融实验：查询改写层的真实增益（同一评测集开关对比）。

运行：EMBED_DISABLED=1 python scripts/ablation.py
输出两组指标并打印对比表（后续可加 dense/rerank 组）。
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_eval(env_extra: dict) -> dict:
    env = os.environ.copy()
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "scripts/eval_retrieval.py"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
    )
    for line in proc.stdout.splitlines():
        if "样本" in line:
            import re

            nums = re.search(r"top-1 (\d+)% · top-3 (\d+)% · top-10 (\d+)%", line)
            if nums:
                return {"top1": int(nums.group(1)), "top3": int(nums.group(2)), "top10": int(nums.group(3))}
    return {"top1": None, "top3": None, "top10": None, "err": proc.stdout[-200:]}


def main() -> None:
    base = run_eval({})                                # 查询改写开启
    no_expand = run_eval({"EXPAND_DISABLED": "1"})     # 查询改写关闭
    print(f"{'配置':<18}{'top-1':>8}{'top-3':>8}{'top-10':>8}")
    print(f"{'BM25-only（有改写）':<18}{base['top1'] or '-':>8}{base['top3'] or '-':>8}{base['top10'] or '-':>8}")
    print(f"{'BM25-only（无改写）':<18}{no_expand['top1'] or '-':>8}{no_expand['top3'] or '-':>8}{no_expand['top10'] or '-':>8}")
    print(f"{'改写层增益':<18}{'+%d' % (base['top1'] - no_expand['top1']):>8}"
          f"{'+%d' % (base['top3'] - no_expand['top3']):>8}"
          f"{'+%d' % (base['top10'] - no_expand['top10']):>8}")


if __name__ == "__main__":
    main()
