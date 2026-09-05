"""属性克制卡片与全类型加载测试（llm-eval 评测发现的缺口修复，M2 回归防護）。

背景：克制知识此前只在规则引擎、未入检索语料；meta 卡片在上下文组装时
被 load_cards 白名单静默丢弃。这两处修复由本文件锁定。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.pipeline.build_cards import build_typechart_cards  # noqa: E402
from src.pipeline.typechart import defense_matrix, load_typechart  # noqa: E402

HAS_CHART = os.path.exists(
    os.path.join(ROOT, "data", "raw", "showdown", "json", "typechart.json")
)
pytestmark = pytest.mark.skipif(not HAS_CHART, reason="Showdown typechart 数据未落地")


class TestTypechartCards:
    def test_dragon_weaknesses(self):
        """龙属性被冰/龙/妖精克制——Gen9 标准克制表的核心事实。"""
        chart = load_typechart()
        mult = defense_matrix(["dragon"], chart)
        weak = sorted(t for t, m in mult.items() if m > 1)
        assert weak == ["dragon", "fairy", "ice"]

    def test_card_count_and_schema(self):
        cards = build_typechart_cards()
        # 18 个常规防守属性（stellar 是攻击方机制，不建卡）
        assert len(cards) == 18
        for card in cards:
            assert card["card_id"].startswith("type:")
            assert card["type"] == "typechart"
            # 内容必须过质量过滤（≥40 字），否则会被索引丢弃
            assert len(card["content_zh"]) >= 40

    def test_dragon_card_content_hits_queries(self):
        card = next(c for c in build_typechart_cards() if c["card_id"] == "type:dragon")
        for term in ("克制", "弱点", "冰", "妖精"):
            assert term in card["content_zh"]


class TestFullCardLoading:
    def test_prompt_load_cards_covers_meta_and_typechart(self):
        """组装层白名单必须覆盖全部卡片类型（漏掉=静默丢弃→空上下文拒答）。"""
        from src.generation.prompt import load_cards

        cards = load_cards()
        assert any(cid.startswith("meta:") for cid in cards), "meta 卡片未进组装层"
        assert any(cid.startswith("type:") for cid in cards), "typechart 卡片未进组装层"

    def test_index_load_cards_includes_typechart(self):
        from src.retrieval.index import _load_cards

        cards = _load_cards()
        assert any(c["card_id"] == "type:dragon" for c in cards)

    def test_typechart_jsonl_on_disk_matches_builder(self):
        """语料文件与生成函数一致（防止手改漂移）。"""
        path = os.path.join(ROOT, "data", "cards", "typechart.jsonl")
        if not os.path.exists(path):
            pytest.skip("typechart.jsonl 未生成，先运行 build_cards")
        on_disk = [json.loads(line) for line in open(path, encoding="utf-8")]
        assert {c["card_id"] for c in on_disk} == {c["card_id"] for c in build_typechart_cards()}
