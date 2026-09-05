"""M3 生成层单测：引用解析 / 上下文组装（纯函数，不调用 API）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation.prompt import build_context, parse_citations


class TestParseCitations:
    def test_extract_numbers(self):
        ans = "快龙是龙+飞行系[1]，威吓特性[2]。"
        assert parse_citations(ans) == ["1", "2"]

    def test_no_citations(self):
        assert parse_citations("知识库中未找到相关信息") == []


class TestBuildContext:
    def test_numbering_and_mapping(self):
        # 用构造的最小卡片目录不可行（读 data/cards），此测试验证编号逻辑：
        # 用真实卡片存在时的行为（无卡片则跳过）
        import json

        cards_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "cards",
        )
        if not os.path.exists(os.path.join(cards_dir, "pokemon.jsonl")):
            import pytest
            pytest.skip("cards 未构建")
        ctx, mapping = build_context(["poke:149"])
        assert mapping["1"] == "poke:149"
        assert "[1]" in ctx
        assert "快龙" in ctx
