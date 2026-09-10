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


class TestExtremeScenarios:
    """默认假设影响结果时，必须给出两端情形（什么情况死 / 什么情况不死）。"""

    def test_all_scenarios_ohko_for_4x_weakness(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("化石翼龙一发岩崩打喷火龙多少血")
        assert "极端情况分析" in ctx
        # 四倍弱点且双方满投入时必死；最不利情形仍可能差一点 →
        # 结论应说明"取决于配置"，并把两端都讲清楚
        assert "最有利情形" in ctx and "无论随机浮动如何都能一击击杀" in ctx

    def test_uncertain_case_shows_both_ends(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("快龙用龙爪打喷火龙多少血")
        assert "极端情况分析" in ctx
        assert "结果取决于配置" in ctx
        assert "最不利情形" in ctx and "最有利情形" in ctx

    def test_scenarios_cover_ev_nature_item_weather(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("快龙用龙爪打喷火龙多少血")
        for kw in ("努力值", "性格", "道具", "天气", "随机浮动"):
            assert kw in ctx, f"极端情形未覆盖 {kw}"

    def test_no_english_jargon_in_context(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("化石翼龙一发岩崩打喷火龙多少血")
        for bad in ("OHKO", "STAB"):
            assert bad not in ctx, f"事实文本不应出现英文缩写 {bad}"


class TestMegaForms:
    """Mega 等形态数据必须可检索、可计算（曾缺失导致回答"知识库无数据"）。"""

    def test_form_cards_exist(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        import json
        import os

        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "cards", "form.jsonl")
        assert os.path.exists(path), "form.jsonl 未生成"
        cards = [json.loads(l) for l in open(path, encoding="utf-8")]
        assert len(cards) > 100, f"形态卡数量过少: {len(cards)}"
        assert any("charizardmegax" in c["card_id"] for c in cards)
        mega = next(c for c in cards if c["card_id"] == "form:charizardmegax")
        assert "超级进化" in mega["content_zh"] and "634" in mega["content_zh"]

    def test_form_resolution(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        # 明确形态：直接解析
        assert pokedata.resolve_pokemon_smart("超级进化喷火龙X")[0] == "charizardmegax"
        # 歧义形态：要求澄清而非瞎猜
        slug, note = pokedata.resolve_pokemon_smart("超级进化喷火龙")
        assert slug is None and "多个进化形态" in note

    def test_mega_damage_calc(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        ctx = try_build_context("化石翼龙一发岩崩打超级进化喷火龙X多少血")
        assert "Mega进化X" in ctx
        assert "伤害范围" in ctx
        # Mega X 是火+龙：岩石打火 2 倍、打龙 1 倍 → 合计 2 倍
        assert "2 倍" in ctx
        # 与普通喷火龙（火+飞，岩石 4 倍）对比，形态确实改变了克制关系
        normal = try_build_context("化石翼龙一发岩崩打喷火龙多少血")
        assert "4 倍" in normal

    def test_mega_retrieval_hits_form_card(self):
        if not _HAS_DATA:
            import pytest
            pytest.skip("数据未生成")
        import os

        if not os.path.exists(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "index", "bm25.json")):
            import pytest
            pytest.skip("索引未构建")
        from src.retrieval.index import search

        hits = [cid for cid, _ in search("超级进化喷火龙的种族值", top_k=3)]
        assert any(h.startswith("form:charizard") for h in hits), f"未命中形态卡: {hits}"
