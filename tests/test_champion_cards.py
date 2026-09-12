"""冠军训练家卡片：数据契约 + 检索/上下文链路回归。

背景：数据库此前没有联盟冠军（竹兰/大吾/赤红等）与队伍数据，
本次从 Bulbapedia 整理入卡（data/cards/champion.jsonl）。冠军卡要
走通全链路必须接入三处白名单：索引加载、上下文组装、jieba 词典——
meta/typechart 卡当年漏接的教训（llm-eval 发现）由本文件锁定。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.retrieval import index as index_mod  # noqa: E402
from src.generation.prompt import build_context, load_cards  # noqa: E402

CHAMPION_PATH = os.path.join(ROOT, "data", "cards", "champion.jsonl")
BM25_PATH = os.path.join(ROOT, "data", "index", "bm25.json")


def _load_champion_cards() -> list[dict]:
    with open(CHAMPION_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestChampionCards:
    def test_data_contract(self):
        cards = _load_champion_cards()
        assert len(cards) >= 14
        ids = [c["card_id"] for c in cards]
        assert len(ids) == len(set(ids)), "card_id 重复"
        for card in cards:
            assert card["card_id"].startswith("champion:")
            assert card["type"] == "champion"
            # 必须过索引质量过滤（≥40 字、标题无"？"），否则会被静默丢弃
            assert len(card["content_zh"]) >= 40
            assert "？" not in card["title_zh"]
            assert card["aliases"], "别名承担口语命中（竹兰/希罗娜等），不能为空"
            assert card["source"]["provider"] == "bulbapedia"
            assert card["source"]["url"].startswith("https://bulbapedia.bulbagarden.net/")

    def test_core_champions_covered(self):
        ids = {c["card_id"] for c in _load_champion_cards()}
        for cid in ("champion:index", "champion:cynthia", "champion:red",
                    "champion:steven", "champion:leon", "champion:blue",
                    "champion:lance", "champion:diantha", "champion:geeta"):
            assert cid in ids

    def test_bm25_alignment(self):
        """bm25.json 的 id 序必须与当前卡片集一致——新增卡片后必须重建索引，
        否则 save 的 id 列表与新语料错位，检索会返回错卡甚至越界。"""
        cards = index_mod._load_cards()
        with open(BM25_PATH, encoding="utf-8") as f:
            saved_ids = json.load(f)["ids"]
        assert len(saved_ids) == len(cards)
        assert set(saved_ids) == {c["card_id"] for c in cards}

    def test_context_includes_champion_cards(self):
        """上下文组装白名单必须含 champion，否则检索命中后组装时被静默丢弃。"""
        cards = load_cards()
        assert "champion:cynthia" in cards
        context, mapping = build_context(["champion:cynthia"])
        # content_zh 不重复人名（在标题里），断言正文关键事实
        assert "神奥联盟冠军" in context and "烈咬陆鲨" in context
        assert mapping["1"] == "champion:cynthia"

    def test_retrieval_hits_champion(self, monkeypatch):
        """冠军问法应命中冠军卡（BM25-only，离线确定性）。"""
        monkeypatch.setattr(index_mod, "_use_dense", lambda: False)
        for query, expected in [
            ("竹兰用什么队伍", "champion:cynthia"),
            ("白金山最强训练家", "champion:red"),
            ("丰缘冠军", "champion:steven"),
        ]:
            hits = [cid for cid, _ in index_mod.search(query, top_k=5)]
            assert expected in hits, f"{query} 未命中 {expected}，实际：{hits}"
