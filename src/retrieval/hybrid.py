"""M2 · RRF 融合：两路排名（dense / bm25）-> 融合分排序。

RRF（Reciprocal Rank Fusion）：对每个候选按「名次倒数」求和，
k 为平滑常数（RRF 论文推荐 60）。好处：不依赖两路分数刻度可比。
"""
from __future__ import annotations


def rrf_fuse(
    dense_rank: list[str],
    bm25_rank: list[str],
    k: int = 60,
    top_k: int = 20,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for rank, ids in enumerate((dense_rank, bm25_rank)):
        for i, cid in enumerate(ids):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
