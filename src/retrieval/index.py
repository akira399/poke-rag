"""M2 · 索引构建与检索：卡片集合 -> Chroma 向量库 + BM25 语料。

索引文档文本 = 「title_zh title_en content_zh」（检索主用中文正文）。
"""
from __future__ import annotations

import json
import os

from src.retrieval.bm25 import Bm25Index
from src.retrieval.embed import embed_query, embed_texts
from src.retrieval.hybrid import rrf_fuse
from src.retrieval.query_expand import expand

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX_DIR = os.path.join(_ROOT, "data", "index")
CARDS_DIR = os.path.join(_ROOT, "data", "cards")
COLLECTION = "cards"


def _load_cards(quality_filter: bool = True) -> list[dict]:
    """加载全部卡片；quality_filter 丢弃无实质内容的占位卡。

    占位卡（PokeAPI 部分条目缺中文效果，title 为 ??? 等）内容空泛，
    检索时会因命中泛词而霸榜，污染召回（实测教训）。
    """
    cards: list[dict] = []
    for name in ["pokemon", "form", "move", "ability", "item", "meta", "typechart"]:
        with open(os.path.join(CARDS_DIR, f"{name}.jsonl"), encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                # 占位卡：无实质内容（<40字）或标题含"？"（官方未命名条目）
                if quality_filter and (
                    len(card.get("content_zh", "")) < 40 or "？" in card.get("title_zh", "")
                ):
                    continue
                cards.append(card)
    return cards


def doc_text(card: dict) -> str:
    return f"{card['title_zh']} {card['title_en']} {card['content_zh']}"


def _collection():
    import chromadb

    client = chromadb.PersistentClient(path=os.path.join(INDEX_DIR, "chroma"))
    # cosine 空间：距离 [0,2]，可直接用作检索置信度（M3 拒答闸）
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def build_index() -> None:
    from src.retrieval import embed as embed_mod

    cards = _load_cards()
    ids = [c["card_id"] for c in cards]
    docs = [doc_text(c) for c in cards]

    aliases = [c.get("aliases", []) for c in cards]
    os.makedirs(INDEX_DIR, exist_ok=True)
    if embed_mod.embedding_available():
        alias_texts = [" ".join(c.get("aliases", [])) for c in cards]
        _collection().upsert(
            ids=ids,
            embeddings=embed_texts([f"{d} {a}" for d, a in zip(docs, alias_texts)]),
            documents=docs,
            metadatas=[{"card_id": cid, "title_zh": c["title_zh"], "type": c["type"]}
                       for c, cid in zip(cards, ids)],
        )
        print(f"向量+关键词索引完成: {len(cards)} 张卡片")
    else:
        print(f"⚠️ 本地 embedding 不可用（内存/页面文件受限），仅构建 BM25 索引")
    Bm25Index().build(ids, docs, aliases).save(os.path.join(INDEX_DIR, "bm25.json"))


_BM25_CACHE: "Bm25Index | None" = None
_BM25_KEY: tuple | None = None
_DENSE_CACHE: tuple | None = None   # (key, ids, 归一化向量矩阵)


def _get_bm25(docs: list[str], aliases: list[list[str]]) -> Bm25Index:
    """BM25 索引模块级缓存：按文档数+内容指纹判断是否需要重建。"""
    global _BM25_CACHE, _BM25_KEY
    key = (len(docs), sum(len(d) for d in docs))
    if _BM25_CACHE is None or _BM25_KEY != key:
        _BM25_CACHE = Bm25Index().load(os.path.join(INDEX_DIR, "bm25.json"), docs, aliases)
        _BM25_KEY = key
    return _BM25_CACHE


def _dense_rank(ids: list[str], docs: list[str], query: str, top_k: int) -> list[str]:
    """远程向量召回的余弦排序（内存计算，无需 chromadb / torch）。

    卡片向量按内容指纹缓存，首次调用建立（约 4.5k 条，几十秒内）。
    """
    global _DENSE_CACHE
    import numpy as np

    from src.retrieval.embed import embed_query, embed_texts

    key = (len(docs), sum(len(d) for d in docs))
    if _DENSE_CACHE is None or _DENSE_CACHE[0] != key:
        mat = np.asarray(embed_texts(docs), dtype="float32")
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        mat = mat / np.clip(norms, 1e-8, None)
        _DENSE_CACHE = (key, ids, mat)

    _, cached_ids, mat = _DENSE_CACHE
    q = np.asarray(embed_query(query), dtype="float32")
    q = q / max(float(np.linalg.norm(q)), 1e-8)
    scores = mat @ q
    order = np.argsort(-scores)[:top_k]
    return [cached_ids[i] for i in order]


def search(query: str, top_k: int = 20) -> list[tuple[str, float]]:
    """双路召回 + RRF 融合；向量不可用时降级为 BM25-only。

    返回 [(card_id, 融合分)]。降级模式分数为 BM25 原始分（>-1 视为命中）。
    """
    from src.retrieval import embed

    cards = _load_cards()
    docs = [doc_text(c) for c in cards]
    ids = [c["card_id"] for c in cards]

    query_enriched = expand(query)
    aliases = [c.get("aliases", []) for c in cards]
    bm25 = _get_bm25(docs, aliases)   # 模块级缓存：避免每次查询重建（内存与延迟）
    bm25_hits = bm25.search(query_enriched, top_k)
    bm25_rank = [cid for cid, _ in bm25_hits]

    if not _use_dense() or not embed.embedding_available():  # 按配置/优雅降级
        return bm25_hits
    try:
        if embed.is_remote():
            dense_rank = _dense_rank(ids, docs, query_enriched, top_k)
        else:
            res = _collection().query(
                query_embeddings=[embed.embed_query(query_enriched)],
                n_results=top_k,
            )
            dense_rank = list(res["ids"][0])
    except Exception:
        return bm25_hits   # 远程接口异常时不影响主流程（BM25 兜底）
    return rrf_fuse(dense_rank, bm25_rank, top_k=top_k)


def _use_dense() -> bool:
    from src.config import load

    return load()["rag"].get("use_dense", False)
