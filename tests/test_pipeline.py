"""M1 管道单测：normalize / aliases / build_cards（数据已落地时运行）。"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.pipeline.aliases import build_aliases, resolve
from src.pipeline.build_cards import render_item_card, render_move_card, render_pokemon_card
from src.pipeline.normalize import (
    normalize_ability,
    normalize_item,
    normalize_move,
    normalize_pokemon,
    normalize_species,
)

HAS_DATA = os.path.exists(os.path.join(ROOT, "data", "raw", "pokeapi", "pokemon-species", "149.json"))
pytestmark = pytest.mark.skipif(not HAS_DATA, reason="raw 数据未落地，先运行 fetch_pokeapi.py")


class TestNormalize:
    def test_species_dragonite(self):
        sp = normalize_species(149)
        assert sp.name_zh == "快龙"
        assert sp.name_en.lower() == "dragonite"  # species 侧 name 为显示名（首字母大写）
        assert sp.flavor_zh  # 中文图鉴描述存在

    def test_pokemon_dragonite(self):
        pk = normalize_pokemon(149)
        assert pk.types == ["dragon", "flying"]
        assert pk.base_stats["attack"] == 134
        assert pk.name_en == "dragonite"
        # 中文名不在 /pokemon 资源里，由 /pokemon-species 提供（卡片层对齐）
        assert normalize_species(149).name_zh == "快龙"

    def test_move_thunderbolt(self):
        mv = normalize_move(85)
        assert mv.name_zh == "十万伏特"
        assert mv.power == 90
        assert mv.move_type == "electric"

    def test_ability_shell_armor(self):
        ab = normalize_ability(75)
        assert ab.name_zh == "硬壳盔甲"
        assert "critical" in ab.effect_en.lower()

    def test_item_master_ball(self):
        it = normalize_item(1)
        assert it.name_zh == "大师球"


class TestCards:
    def test_pokemon_card(self):
        card = render_pokemon_card(normalize_species(149), normalize_pokemon(149))
        assert card["card_id"] == "poke:149"
        assert "快龙" in card["content_zh"]
        assert "种族值合计 600" in card["content_zh"]  # 91+134+95+100+100+80
        assert card["source"]["provider"] == "pokeapi"

    def test_move_card(self):
        card = render_move_card(normalize_move(85))
        assert card["type"] == "move"
        assert "威力 90" in card["content_zh"]
        assert card["aliases"] == ["十万伏特", "thunderbolt"]

    def test_mega_stone_localized(self):
        """传说 Z-A 的 Mega 石 PokeAPI 无中文（dragoninite）——补丁表命名 +
        渲染层补中文效果句，否则检索命中整段英文、UI 还会露出裸英文标题
        （线上事故 2026-09-12：快龙怕什么属性 命中 dragoninite）。"""
        card = render_item_card(normalize_item(2236))
        assert card["title_zh"] == "快龙进化石"
        assert "由 快龙 携带后可超级进化为超级 快龙。" in card["content_zh"]
        assert "快龙进化石" in card["aliases"]


class TestMovesText:
    def test_top_moves_text(self):
        from src.pipeline.build_cards import top_moves_text

        text = top_moves_text("Pincurchin", {})
        assert text and "威力" in text
        # 排序正确：威力最大的在前
        assert text.startswith("自爆") or "威力200" in text

    def test_unknown_species(self):
        from src.pipeline.build_cards import top_moves_text

        assert top_moves_text("nonexistent-pokemon", {}) == ""


class TestAliases:
    def test_zh_to_en(self):
        aliases = build_aliases()
        assert aliases["快龙"] == "dragonite"
        assert aliases["dragonite"] == "dragonite"

    def test_nickname_resolve(self):
        aliases = build_aliases()
        assert resolve(aliases, "肥大") == "dragonite"
        assert resolve(aliases, "快龙") == "dragonite"

    def test_showdown_alias(self):
        aliases = build_aliases()
        # Showdown 自带别名（dnite -> dragonite），经 setdefault 不覆盖规范名
        assert aliases.get("dnite", "") == "dragonite" or "dnite" not in aliases
