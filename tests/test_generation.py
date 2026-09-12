"""M3 生成层单测：引用解析 / 上下文组装（纯函数，不调用 API）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation.prompt import build_context, linkify_citations, parse_citations


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


class TestLinkifyCitations:
    def test_plain_numbers_become_links(self):
        cards = {"1": {"source": {"url": "https://pokeapi.co/api/v2/pokemon-species/149/"}}}
        out = linkify_citations("快龙是龙+飞行型[1]。", cards)
        assert "[[1]](https://pokeapi.co" in out

    def test_missing_source_kept_plain(self):
        out = linkify_citations("规则结果[1]。", {"1": {"source": {}}})
        assert out == "规则结果[1]。"

    def test_unknown_number_kept(self):
        assert linkify_citations("答案[9]", {}) == "答案[9]"


def test_normalize_sections_splits_scenarios():
    """伤害计算极端情形必须各自成段（LLM 单换行输出会被 Markdown 合并成一大段）。"""
    from src.generation.prompt import normalize_sections

    # 模拟模型照抄上下文的单换行输出
    bad = "判定：一定打不死 [1]\n情形 2｜中间情形\n条件：252 努力值\n判定：一定打不死 [1]\n情形 3｜最有利\n判定：一定打得死\n★ 总体结论：看配置。"
    out = normalize_sections(bad)
    parts = out.split("\n\n")
    assert any(p.startswith("情形 2") for p in parts), out
    assert any(p.startswith("情形 3") for p in parts), out
    assert any(p.startswith("★ 总体结论") for p in parts), out

    # 模型连换行都没有（句号后直接跟"情形 2"）也要分段
    worse = "判定：一定打不死 [1] 情形 2｜中间情形 条件：x"
    out2 = normalize_sections(worse)
    assert "\n\n情形 2" in out2, out2

    # 正常列表输出不应被破坏
    good = "- **情形 1｜最不利**：x\n\n- **情形 2｜中间**：y"
    assert normalize_sections(good) == good


def test_normalize_sections_no_false_positive():
    """「情形」出现在普通句子里（非编号标记）不应被切断。"""
    from src.generation.prompt import normalize_sections

    s = "这个情形描述的是特殊情况。"
    assert normalize_sections(s) == s


def test_retrieval_whitelist_covered_by_assembly():
    """检索白名单必须被上下文组装白名单完全覆盖——form 卡漏接导致
    线上 None.get() 崩溃（「快龙怕什么属性」命中 form:dragonitemega，
    2026-09-12）。本测试把两份白名单永久锁成一致。"""
    from src.retrieval.index import _load_cards
    from src.generation.prompt import load_cards

    assembly = load_cards()
    missing = [c["card_id"] for c in _load_cards() if c["card_id"] not in assembly]
    assert not missing, f"组装层白名单缺少（会被静默丢弃并产生 None 引用）: {missing[:5]}"


def test_form_card_reachable_in_context():
    """Mega 形态卡命中后必须真实进入知识片段（当年被组装层静默丢弃）。"""
    from src.generation.prompt import build_context

    context, mapping = build_context(["form:dragonitemega"])
    assert context, "form:dragonitemega 组装为空"
    assert list(mapping.values()) == ["form:dragonitemega"]
