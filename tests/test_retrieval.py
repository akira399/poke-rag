"""M2 检索层单测：bm25 分词 / RRF 融合（不依赖模型与索引）。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.bm25 import tokenize_hybrid
from src.retrieval.hybrid import rrf_fuse
from src.retrieval.query_expand import TERMS, expand


class TestTokenize:
    def test_chinese_only(self):
        tokens = tokenize_hybrid("快龙怕什么")
        assert "快龙" in tokens or "龙" in tokens  # jieba 粒度可能不同，保证有切分
        assert all(isinstance(t, str) and t for t in tokens)

    def test_latin_kept_as_word(self):
        tokens = tokenize_hybrid("Dragonite 的属性")
        assert "dragonite" in tokens
        assert "属性" in tokens

    def test_mixed_alias(self):
        tokens = tokenize_hybrid("十万伏特 thunderbolt")
        assert "thunderbolt" in tokens


class TestQueryExpand:
    def test_term_translation(self):
        q = expand("什么特性让宝可梦不会受到会心一击？")
        assert "critical hit" in q  # 术语表中英翻译追加

    def test_alias_expansion_requires_cards(self):
        # aliases.json 由 build_cards 产生；未生成时跳过（用术语表功能兜底）
        import os

        if not os.path.exists(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "cards", "aliases.json")):
            import pytest
            pytest.skip("cards 未构建")
        q = expand("快龙怕什么")
        assert "dragonite" in q or "Dragonite" in q or "dragonite" in q.lower()


class TestRrfFuse:
    def test_fuse_ranks(self):
        dense = ["a", "b", "c", "d"]
        bm25 = ["b", "a", "e", "d"]
        result = rrf_fuse(dense, bm25, top_k=10)
        scores = dict(result)
        # a 与 b 排名互换：得分相等（1/61 + 1/62），且都高于单路出现的 c/e
        assert scores["a"] == scores["b"] >= max(scores["c"], scores["e"])
        assert scores["a"] > scores["d"]  # d 两路皆第 4
        assert len(result) <= 10

    def test_rrf_is_rank_based_not_score_based(self):
        # 融合分只由名次决定；k 平滑参数默认 60
        result = rrf_fuse(["x", "y"], ["y"], k=1, top_k=5)
        scores = dict(result)
        assert scores["x"] == 1 / 2          # dense 第 1
        assert scores["y"] == 1 / 3 + 1 / 2   # dense 第 2 + bm25 第 1
        assert scores["y"] > scores["x"]
