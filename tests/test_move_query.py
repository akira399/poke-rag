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
        en, kind = detect_move_query("快龙会哪些招式？", aliases)
        assert kind == "all" and en == "dragonite"

    def test_status_moves_query(self):
        aliases = {"皮卡丘": "pikachu"}
        en, kind = detect_move_query("皮卡丘的变化招式有哪些？", aliases)
        assert kind == "status" and en == "pikachu"

    def test_no_keyword(self):
        en, kind = detect_move_query("快龙怕什么？", {"快龙": "dragonite"})
        assert not kind and en is None

    def test_no_pokemon(self):
        en, kind = detect_move_query("所有招式都有什么效果？", {})
        assert not kind and en is None


class TestFormat:
    def test_format_contains_groups(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("showdown 数据未生成")
        result = list_moves("dragonite")
        text = format_moves("快龙", result, limit_all=10)
        assert "攻击招式" in text and "变化招式" in text
        assert "威力" in text

    def test_status_only_renders_subset(self):
        """子集查询只渲染变化招式段——全量 139 条列表 + 严格反幻觉提示词
        会让免费小模型对「答案就在片段里」的问题拒答（线上实测）。"""
        if not _HAS_DATA:
            import pytest
            pytest.skip("showdown 数据未生成")
        result = list_moves("dragonite")
        text = format_moves("快龙", result, status_only=True)
        assert "变化招式 40 个" in text
        assert "龙之舞" in text
        assert "攻击招式" not in text
        assert len(text) < 800
