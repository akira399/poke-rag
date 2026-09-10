"""M2 · BM25 关键词检索（jieba 中文分词 + rank_bm25）。

与稠密检索互补：专名（快龙/十万伏特）向量可能漂移，关键词不会漏。
"""
from __future__ import annotations

import json
import os
import re

import jieba
from rank_bm25 import BM25Okapi

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS_DIR = os.path.join(root, "data", "cards")
BM25_DATA = os.path.join(root, "data", "index", "bm25.json")

_LATIN_RE = re.compile(r"[a-zA-Z0-9\-]+")
_dict_loaded = False


def _ensure_card_dict() -> None:
    """把知识卡片的中文标题注册进 jieba 自定义词典（只执行一次）。

    jieba 默认词典不含专名（如「十万伏特」会被切成「十万/伏特」），
    专名破碎会让 BM25 检索命中率显著下降；卡片标题即主数据，
    主数据回灌词典是标准解法。
    """
    global _dict_loaded
    if _dict_loaded:
        return
    for fname in ("pokemon.jsonl", "move.jsonl", "ability.jsonl", "item.jsonl"):
        path = os.path.join(CARDS_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                title = card.get("title_zh", "")
                if title and len(title) >= 2:
                    jieba.add_word(title)
    _dict_loaded = True


def tokenize(text: str) -> list[str]:
    tokens = jieba.lcut(text.lower())
    return [t for t in tokens if t.strip()]


def _latin_terms(text: str) -> list[str]:
    """英文/数字专名按原词保留（BM25 对复合词按空格切分）。"""
    return _LATIN_RE.findall(text.lower())


def tokenize_hybrid(text: str) -> list[str]:
    """中英混合分词：中文走 jieba（含卡片专名词典），英文词保留为整词。"""
    _ensure_card_dict()
    result: list[str] = []
    for part in _LATIN_RE.split(text):
        if part.strip():
            result.extend(tokenize(part))
    result.extend(_latin_terms(text))
    return result


class Bm25Index:
    def __init__(self):
        self.doc_ids: list[str] = []
        self._bm25: BM25Okapi | None = None

    def build(self, ids: list[str], docs: list[str],
              aliases: list[list[str]] | None = None) -> "Bm25Index":
        # 别名拼进文档：用户用口语（"超级进化喷火龙"）也能命中该卡
        corpus = []
        for i, d in enumerate(docs):
            extra = " ".join(aliases[i]) if aliases and i < len(aliases) else ""
            corpus.append(tokenize_hybrid(f"{d} {extra}"))
        self.doc_ids = ids
        self._bm25 = BM25Okapi(corpus)
        return self

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        scores = self._bm25.get_scores(tokenize_hybrid(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(self.doc_ids[i], scores[i]) for i in order]

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ids": self.doc_ids}, f, ensure_ascii=False)

    def load(self, path: str, docs: list[str],
             aliases: list[list[str]] | None = None) -> "Bm25Index":
        with open(path, encoding="utf-8") as f:
            self.doc_ids = json.load(f)["ids"]
        return self.build(self.doc_ids, docs, aliases)
