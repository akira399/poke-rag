"""伤害计算问答工具单测：解析 / 计算 / 信息不足追问（纯规则，不调 LLM）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules import pokedata
from src.rules.damage_query import format_missing, is_damage_query, parse, try_build_context

_HAS_DATA = os.path.exists(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "showdown", "json", "pokedex.json"))


class TestDetect:
    def test_damage_queries(self):
        for q in ["化石翼龙一发岩崩打喷火龙多少血", "快龙用地震能打多少伤害",
                  "这个招能不能秒它"]:
            assert is_damage_query(q), q

    def test_non_damage(self):
        assert not is_damage_query("快龙怕什么属性？")


class TestParse:
    def test_full_question(self):
        p = parse("化石翼龙一发岩崩打喷火龙多少血")
        assert p["attacker"] == "aerodactyl"
        assert p["move"] == "rockslide"
        assert p["defender"] == "charizard"
        # 等级未提供时会被记录（用于提示用户），但不算硬缺失——仍会按默认 Lv50 计算
        assert p["missing"] == ["双方等级（或说明使用默认 Lv50）"]
        assert p["level"] == 50 and p["level_provided"] is False

    def test_respects_verb_over_pokemon_name(self):
        # 「怪力」是宝可梦名，不能把它当动词切分
        p = parse("怪力用岩崩打喷火龙多少血")
        assert p["attacker"] == "machamp"
        assert p["move"] == "rockslide"
        assert p["defender"] == "charizard"

    def test_level_parsed(self):
        assert parse("快龙用地震打喷火龙Lv100多少血")["level"] == 100
        assert parse("快龙用地震打喷火龙等级75多少血")["level"] == 75

    def test_missing_attacker(self):
        p = parse("岩崩打喷火龙多少血")
        assert "攻击方宝可梦" in p["missing"]

    def test_move_not_taken_as_defender(self):
        p = parse("喷火龙用十万伏特打快龙多少血")
        assert p["defender"] == "dragonite"
        assert p["move"] == "thunderbolt"


class TestCalculate:
    def test_super_effective_ohko(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("化石翼龙一发岩崩打喷火龙多少血")
        assert "伤害范围" in ctx
        assert "100.0%" in ctx          # 4 倍弱点，必定秒杀
        assert "命中率" in ctx          # 岩崩 90% 命中，必须给出
        assert "会心一击" in ctx        # 概率也要给

    def test_probability_reported_when_not_guaranteed(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("快龙用龙爪打喷火龙多少血")
        assert "一击击杀概率" in ctx

    def test_missing_info_asks_user(self):
        ctx = try_build_context("岩崩打喷火龙多少血")
        assert "信息不足" in ctx
        assert "攻击方宝可梦" in ctx

    def test_status_move_no_damage(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("快龙用龙之舞打喷火龙多少血")
        assert ctx is not None and "变化招式" in ctx


class TestPokedata:
    def test_resolve(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        assert pokedata.resolve_pokemon("化石翼龙") == "aerodactyl"
        assert pokedata.resolve_move("岩崩") == "rockslide"

    def test_can_learn(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        assert pokedata.can_learn("aerodactyl", "rockslide")
        assert not pokedata.can_learn("magikarp", "flamethrower")

    def test_toid(self):
        assert pokedata.toid("Great Tusk") == "greattusk"
        assert pokedata.toid("Nidoran♀") == "nidoranf"
