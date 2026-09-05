"""招式查询工具单测：意图检测 / 分组与排序（不依赖 LLM）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules.move_query import detect_move_query, format_moves, list_moves

_HAS_DATA = os.path.exists(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "showdown", "json", "learnsets.json"))


class TestListMoves:
    def test_dragonite_damaging_sorted(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("showdown 数据未生成")
        result = list_moves("dragonite")
        assert result is not None
        powers = [e["power"] for e in result["damaging"]]
        assert powers == sorted(powers, reverse=True)
        assert all(e["category"] == "physical" or e["category"] == "special"
                   for e in result["damaging"])
        assert all(e["category"] == "status" for e in result["status"])

    def test_unknown_species_returns_none(self):
        assert list_moves("no-such-pokemon") is None


class TestDetect:
    def test_all_moves_query(self):
        aliases = {"快龙": "dragonite", "dragonite": "dragonite"}
        en, hit = detect_move_query("快龙会哪些招式？", aliases)
        assert hit and en == "dragonite"

    def test_status_moves_query(self):
        aliases = {"皮卡丘": "pikachu"}
        en, hit = detect_move_query("皮卡丘的变化招式有哪些？", aliases)
        assert hit and en == "pikachu"

    def test_no_keyword(self):
        en, hit = detect_move_query("快龙怕什么？", {"快龙": "dragonite"})
        assert not hit and en is None

    def test_no_pokemon(self):
        en, hit = detect_move_query("所有招式都有什么效果？", {})
        assert not hit and en is None


class TestFormat:
    def test_format_contains_groups(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("showdown 数据未生成")
        result = list_moves("dragonite")
        text = format_moves("快龙", result, limit_all=10)
        assert "攻击招式" in text and "变化招式" in text
        assert "威力" in text
