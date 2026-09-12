"""《宝可梦冠军》（Pokémon Champions）游戏卡：数据契约 + 检索/上下文链路回归。

背景：用户指出「宝可梦冠军」是官方 2026 年推出的对战游戏（Switch 2026-04-08、
移动端 2026-06-17 发售），不是联盟冠军训练家——同名歧义已用两张总览卡互相
交叉说明化解。游戏数据（机制改动/规则集/名单/道具池）整理自官方站、Serebii、
Victory Road、IGN wiki、PokemonDB，入 data/cards/game.jsonl（type=game）。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.retrieval import index as index_mod  # noqa: E402
from src.generation.prompt import build_context, load_cards  # noqa: E402

GAME_PATH = os.path.join(ROOT, "data", "cards", "game.jsonl")


def _load_game_cards() -> list[dict]:
    with open(GAME_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestGameCards:
    def test_data_contract(self):
        cards = _load_game_cards()
        assert len(cards) >= 13
        ids = [c["card_id"] for c in cards]
        assert len(ids) == len(set(ids)), "card_id 重复"
        for card in cards:
            assert card["card_id"].startswith("game:")
            assert card["type"] == "game"
            assert len(card["content_zh"]) >= 40
            assert "？" not in card["title_zh"]
            assert card["aliases"], "别名承担口语命中（排位/66点/Mega石等），不能为空"
            assert card["source"]["url"].startswith("https://")

    def test_core_cards_covered(self):
        ids = {c["card_id"] for c in _load_game_cards()}
        for cid in ("game:index", "game:modes", "game:regulations", "game:mc",
                    "game:stats", "game:mega", "game:items", "game:roster"):
            assert cid in ids

    def test_context_includes_game_cards(self):
        """上下文组装白名单必须含 game；关键事实（66 点制、个体值取消）在正文。"""
        cards = load_cards()
        assert "game:stats" in cards
        context, mapping = build_context(["game:stats"])
        assert "个体值" in context and "66" in context
        assert mapping["1"] == "game:stats"

    def test_retrieval_hits_game_cards(self, monkeypatch):
        """游戏相关问法应命中游戏卡（BM25-only，离线确定性）。"""
        monkeypatch.setattr(index_mod, "_use_dense", lambda: False)
        for query, expected in [
            ("宝可梦冠军是什么游戏", "game:index"),
            ("宝可梦冠军个体值还存在吗", "game:stats"),
            ("冠军 排位 双打 规则", "game:modes"),
            ("冠军游戏现在什么规则集", "game:mc"),
        ]:
            hits = [cid for cid, _ in index_mod.search(query, top_k=4)]
            assert expected in hits, f"{query} 未命中 {expected}，实际：{hits}"

    def test_disambiguation_note(self):
        """「宝可梦冠军」与联盟冠军训练家同名歧义——总览卡正文须有交叉说明。"""
        cards = {c["card_id"]: c for c in _load_game_cards()}
        assert "联盟冠军训练家" in cards["game:index"]["content_zh"]
