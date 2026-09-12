"""M1 · 知识卡片生成：规范实体 -> 自然语言「知识卡片」

卡片是检索/引用/评测的最小单元（方案 §3）：每张卡片 = 一段中文知识文本
+ 双语标题 + 标签 + 权威来源。纯函数实现，便于单测与重跑。
"""
from __future__ import annotations

import json
import os

from .normalize import Ability, Item, Move, Pokemon, Species

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TYPE_MAP = {
    "normal": "一般", "fire": "火", "water": "水", "electric": "电", "grass": "草",
    "ice": "冰", "fighting": "格斗", "poison": "毒", "ground": "地面", "flying": "飞行",
    "psychic": "超能力", "bug": "虫", "rock": "岩石", "ghost": "幽灵", "dragon": "龙",
    "dark": "恶", "steel": "钢", "fairy": "妖精", "stellar": "星晶",
}

_FALLBACK_FLAVOR = "（暂无官方简体中文图鉴描述）"

_TEXT_CACHE: dict = {}


def _text_desc(kind: str, en_id: str) -> str:
    """Showdown data/text 英文 shortDesc（PokeAPI 效果缺失时的兜底）。kind: items/moves/abilities"""
    global _TEXT_CACHE
    if kind not in _TEXT_CACHE:
        path = os.path.join(ROOT, "data", "raw", "showdown", "json", f"text-{kind}.json")
        if not os.path.exists(path):
            _TEXT_CACHE[kind] = {}
            return ""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        table = next((v for v in data.values() if isinstance(v, dict) and v), {})
        _TEXT_CACHE[kind] = {k.lower().replace(" ", "").replace("-", ""): v for k, v in table.items()}
    entry = _TEXT_CACHE[kind].get(en_id.lower().replace(" ", "").replace("-", ""))
    return (entry or {}).get("shortDesc", "") or (entry or {}).get("desc", "")


def _types_zh(types: list[str]) -> str:
    return "+".join(TYPE_MAP.get(t, t) for t in types)


def stats_line(pokemon: Pokemon) -> str:
    s = pokemon.base_stats
    return (f"生命 {s.get('hp', '-')}、攻击 {s.get('attack', '-')}、防御 {s.get('defense', '-')}、"
            f"特攻 {s.get('special-attack', '-')}、特防 {s.get('special-defense', '-')}、"
            f"速度 {s.get('speed', '-')}，种族值合计 {sum(v for v in s.values() if isinstance(v, int))}")


def top_moves_text(species_en: str, moves_zh: dict) -> str:
    """该宝可梦可学习招式按威力 Top15 的中文列表。

    learnsets（可学招式）+ moves（威力）两个数据源融合——「宝可梦→招式」
    关联是单张招式卡给不了的知识（规则查询，非 LLM 生成）。
    """
    toid = species_en.lower().replace(" ", "").replace("-", "")
    ls_path = os.path.join(ROOT, "data", "raw", "showdown", "json", "learnsets.json")
    mv_path = os.path.join(ROOT, "data", "raw", "showdown", "json", "moves.json")
    if not os.path.exists(ls_path) or not os.path.exists(mv_path):
        return ""
    with open(ls_path, encoding="utf-8") as f:
        learn = json.load(f)["Learnsets"].get(toid, {}).get("learnset", {})
    with open(mv_path, encoding="utf-8") as f:
        moves = json.load(f)["Moves"]
    entries = []
    for mid in learn:
        info = moves.get(mid)
        if not info or not info.get("basePower"):
            continue
        entries.append((info["basePower"], mid))
    entries.sort(key=lambda e: -e[0])
    top = entries[:15]
    if not top:
        return ""
    return "、".join(f"{moves_zh.get(mid, mid)}（威力{p}）" for p, mid in top)


def _has_cjk(text: str) -> bool:
    import re

    return bool(re.search(r"[一-鿿]", text))


_ABILITY_ZH: dict | None = None


def _ability_zh_map() -> dict[str, str]:
    """ability slug -> 中文名（来自 ability 卡 + 补丁表，模块级缓存）。"""
    global _ABILITY_ZH
    if _ABILITY_ZH is not None:
        return _ABILITY_ZH
    m: dict[str, str] = {}
    path = os.path.join(ROOT, "data", "cards", "ability.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                m[card["title_en"].lower()] = card["title_zh"]
    _ABILITY_ZH = m
    return m


def _abilities_zh(slugs: list[str]) -> str:
    from .i18n_patch import patch_title

    zh_map = _ability_zh_map()
    names = [zh_map.get(s.lower()) or patch_title("ability", s) or s for s in slugs]
    return "、".join(names)


def render_pokemon_card(species: Species, pokemon: Pokemon, moves_text: str = "") -> dict:
    from .typechart import load_typechart, weakness_text

    # 中文名以 species 为准（唯一带官方多语言名的资源），属性/种族值/特性来自 pokemon
    flaw = weakness_text(pokemon.types, load_typechart())
    flavor = species.flavor_zh or _FALLBACK_FLAVOR
    content = (
        f"{species.name_zh}（{species.name_en}）是{pokemon.types and _types_zh(pokemon.types)+'型'}宝可梦，"
        f"身高 {pokemon.heightm} 米，体重 {pokemon.weightkg} 千克。"
        f"种族值：{stats_line(pokemon)}。"
        f"特性：{_abilities_zh(pokemon.abilities) or '未知'}。"
        + (f"属性克制：{flaw}。" if flaw else "")
        + (f"可学习招式（按威力排序）：{moves_text}。" if moves_text else "")
        + f"图鉴描述：{flavor}。"
    )
    return {
        "card_id": f"poke:{pokemon.id}",
        "type": "pokemon",
        "title_zh": species.name_zh,
        "title_en": species.name_en,
        "aliases": [species.name_zh, species.name_en],
        "content_zh": content,
        "content_en": f"{species.name_en} is a {_types_zh(pokemon.types)} type Pokemon. {flavor}",
        "tags": pokemon.types + [f"种族值{sum(v for v in pokemon.base_stats.values() if isinstance(v, int))}"],
        "stats": pokemon.base_stats,
        "source": {"provider": "pokeapi", "id": pokemon.id,
                   "url": species.source_url or f"https://pokeapi.co/api/v2/pokemon-species/{pokemon.id}/"},
    }


def render_move_card(move: Move) -> dict:
    effect = move.effect_zh or move.effect_en or _text_desc("moves", move.name_en) or "（暂无中文效果描述）"
    content = (
        f"招式「{move.name_zh}」（{move.name_en}，{TYPE_MAP.get(move.move_type, move.move_type)}系）："
        f"威力 {move.power if move.power else '—'}、命中 {move.accuracy if move.accuracy else '—'}、PP {move.pp if move.pp else '—'}。"
        f"效果：{effect[:200]}"
    )
    from .i18n_patch import patch_title

    title_zh = move.name_zh if _has_cjk(move.name_zh) else patch_title("move", move.name_en)
    return {
        "card_id": f"move:{move.id}",
        "type": "move",
        "title_zh": title_zh or move.name_zh,
        "title_en": move.name_en,
        "aliases": [move.name_zh, move.name_en],
        "content_zh": content,
        "content_en": f"{move.name_en} ({move.move_type}) power {move.power} acc {move.accuracy}. {move.effect_en[:200]}",
        "tags": [move.move_type],
        "stats": {"power": move.power, "accuracy": move.accuracy, "pp": move.pp},
        "source": {"provider": "pokeapi", "id": move.id,
                   "url": f"https://pokeapi.co/api/v2/move/{move.id}/"},
    }


def render_ability_card(ability: Ability) -> dict:
    effect = ability.effect_zh or ability.effect_en or _text_desc("abilities", ability.name_en) or "（暂无效果描述）"
    content = (
        f"特性「{ability.name_zh}」（{ability.name_en}）：{effect[:200]}"
    )
    from .i18n_patch import patch_title

    title_zh = ability.name_zh if _has_cjk(ability.name_zh) else patch_title("ability", ability.name_en)
    return {
        "card_id": f"ability:{ability.id}",
        "type": "ability",
        "title_zh": title_zh or ability.name_zh,
        "title_en": ability.name_en,
        "aliases": [ability.name_zh, ability.name_en],
        "content_zh": content,
        "content_en": f"{ability.name_en}: {ability.effect_en[:200]}",
        "tags": ["特性"],
        "stats": {},
        "source": {"provider": "pokeapi", "id": ability.id,
                   "url": f"https://pokeapi.co/api/v2/ability/{ability.id}/"},
    }


def render_item_card(item: Item) -> dict:
    effect = item.effect_en or _text_desc("items", item.name_en) or "（暂无效果描述）"
    from .i18n_patch import patch_title

    title_zh = item.name_zh if _has_cjk(item.name_zh) else patch_title("item", item.name_en)
    content = f"道具「{title_zh or item.name_zh}」（{item.name_en}）：{effect[:200]}"
    # Mega 石在 PokeAPI 尚无中文效果的（传说 Z-A 系列），按石名补一句中文效果，
    # 否则检索命中的是整段英文、模型也只能照抄英文
    if (title_zh or "").endswith("进化石") and "Mega" in effect:
        holder = title_zh[:-3]
        content += f"由 {holder} 携带后可超级进化为超级 {holder}。"
    return {
        "card_id": f"item:{item.id}",
        "type": "item",
        "title_zh": title_zh or item.name_zh,
        "title_en": item.name_en,
        "aliases": list(dict.fromkeys(
            [title_zh, item.name_zh, item.name_en] if title_zh != item.name_zh
            else [item.name_zh, item.name_en])),
        "content_zh": content,
        "content_en": f"{item.name_en}: {effect[:200]}",
        "tags": ["道具"],
        "stats": {},
        "source": {"provider": "pokeapi", "id": item.id,
                   "url": f"https://pokeapi.co/api/v2/item/{item.id}/"},
    }


TIER_ZH = {"gen9ou": "Gen9 OU", "gen9uu": "Gen9 UU", "gen9ru": "Gen9 RU",
           "gen9nu": "Gen9 NU", "gen9pu": "Gen9 PU", "gen9ubers": "Gen9 Ubers",
           "gen8ou": "Gen8 OU", "gen8ubers": "Gen8 Ubers"}


def build_meta_cards() -> list[dict]:
    """Smogon 月度使用率 -> Meta 卡片（每分级一张：Top15 榜单 + 概括）。"""
    import json

    def load_pokemon_title_map() -> dict[str, str]:
        m = {}
        with open(os.path.join(ROOT, "data", "cards", "pokemon.jsonl"),
                encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                # Smogon 统计 key 是显示名（"Great Tusk"），兼容 toID/小写三种形态
                m[card["title_en"]] = card["title_zh"]
                m[card["title_en"].lower()] = card["title_zh"]
                m[card["title_en"].lower().replace(" ", "")] = card["title_zh"]
        return m

    name_map = load_pokemon_title_map()
    stats_dir = os.path.join(ROOT, "data", "raw", "smogon", "stats")
    cards = []
    for tier, tier_zh in TIER_ZH.items():
        path = os.path.join(stats_dir, f"{tier}-1500.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        mg = data.get("info", {}).get("metagame", {})
        month = mg.get("month", "2026-08") if isinstance(mg, dict) else "2026-08"
        ranked = sorted(data["data"].items(), key=lambda kv: kv[1]["usage"], reverse=True)
        top = ranked[:15]
        lines = [f"{tier_zh} 环境（{month} 月度数据）使用率最高的宝可梦："]
        for i, (sid, v) in enumerate(top, 1):
            zh = name_map.get(sid, sid)
            lines.append(f"{i}. {zh} —— 使用率 {v['usage']*100:.1f}%")
        content = "\n".join(lines)
        cards.append({
            "card_id": f"meta:{tier}",
            "type": "meta",
            "title_zh": f"{tier_zh} 环境使用率榜",
            "title_en": tier,
            "aliases": [tier_zh, tier, f"{tier_zh}环境", "使用率"],
            "content_zh": content,
            "content_en": f"{tier_zh} ({month}) usage: " + ", ".join(
                f"{sid} {v['usage']*100:.1f}%" for sid, v in top[:10]),
            "tags": ["meta", tier],
            "stats": {"month": month},
            "source": {"provider": "smogon",
                       "url": f"https://www.smogon.com/stats/{month}/"},
        })
    return cards





def build_typechart_cards() -> list[dict]:
    """Showdown typechart -> 属性克制卡片（每防守属性一张）。

    克制关系是确定性知识（查表），写进卡片内容让检索直接命中、
    回答可溯源，不依赖 LLM 记忆（确定性知识的正确归属）。
    查询词「克制/弱点」在标题与正文自然出现即可保证召回；正文必须精炼——
    堆砌查询词会造成词频饱和、污染无关查询的排序（实测：正文重复「属性」
    十余次后，78 问检索评测 top-3 从 99% 跌到 94%）。
    """
    from .typechart import defense_matrix, load_typechart

    chart = load_typechart()
    cards = []
    for def_type in sorted(chart.keys()):
        # stellar 是攻击方机制（第九世代太晶爆发），不作防守属性建卡
        if def_type == "stellar":
            continue
        zh = TYPE_MAP.get(def_type, def_type)
        mult = defense_matrix([def_type], chart)
        weak = [TYPE_MAP.get(t, t) for t, m in mult.items() if m > 1]
        resist = [TYPE_MAP.get(t, t) for t, m in mult.items() if 0 < m < 1]
        immune = [TYPE_MAP.get(t, t) for t, m in mult.items() if m == 0]
        content = f"{zh}属性宝可梦的防守克制关系。弱点（被克制，受到双倍伤害）：{'、'.join(weak) if weak else '无'}。"
        if resist:
            content += f"抵抗（受到一半伤害）：{'、'.join(resist)}。"
        if immune:
            content += f"免疫（不受伤害）：{'、'.join(immune)}。"
        # 攻击视角：{zh}系招式克制谁，由防守方矩阵反推（评测发现仅防守视角
        # 答不了「火属性招式克制哪些属性」这类攻击方问题）
        atk_weak = [TYPE_MAP.get(d, d) for d, entry in chart.items()
                    if (entry.get("damageTaken", {}).get(def_type)
                        or entry.get("damageTaken", {}).get(def_type.capitalize())) == 1]
        atk_resist = [TYPE_MAP.get(d, d) for d, entry in chart.items()
                      if (entry.get("damageTaken", {}).get(def_type)
                          or entry.get("damageTaken", {}).get(def_type.capitalize())) == 2]
        atk_immune = [TYPE_MAP.get(d, d) for d, entry in chart.items()
                      if (entry.get("damageTaken", {}).get(def_type)
                          or entry.get("damageTaken", {}).get(def_type.capitalize())) == 3]
        content += f"作为攻击方，{zh}属性招式克制{'、'.join(atk_weak) if atk_weak else '无'}属性（效果绝佳）"
        if atk_resist:
            content += f"，被{'、'.join(atk_resist)}属性抵抗"
        if atk_immune:
            content += f"，被{'、'.join(atk_immune)}属性免疫（无效）"
        content += "。"
        cards.append({
            "card_id": f"type:{def_type}",
            "type": "typechart",
            "title_zh": f"{zh}属性克制表",
            "title_en": f"{def_type}-type matchups",
            "aliases": [zh, f"{zh}属性", f"{zh}系", "克制", "弱点"],
            "content_zh": content,
            "content_en": f"{def_type} takes 2x from: {', '.join(weak) if weak else 'none'}; "
                          f"0.5x from: {', '.join(resist) if resist else 'none'}; "
                          f"immune: {', '.join(immune) if immune else 'none'}.",
            "tags": ["typechart", def_type],
            "source": {"provider": "showdown",
                       "url": "https://github.com/smogon/pokemon-showdown/blob/master/data/typechart.ts"},
        })
    return cards

# 形态关键词 -> 中文说明（用于卡片正文，让检索也能命中「超级进化」等说法）
FORM_KEYWORDS = {
    "mega": "超级进化形态（Mega进化），需携带对应超级石",
    "gmax": "超极巨化形态",
    "alola": "阿罗拉地区形态",
    "galar": "伽勒尔地区形态",
    "hisui": "洗翠地区形态",
    "paldea": "帕底亚地区形态",
    "therian": "灵兽形态",
    "origin": "起源形态",
}


def _form_kind(slug: str) -> tuple[str, str]:
    """返回 (形态后缀, 中文说明)。"""
    for suff in ("megax", "megay", "megaz", "mega", "gmax"):
        if slug.endswith(suff):
            base = suff[:-1] if suff.endswith("x") or suff.endswith("y") or suff.endswith("z") else suff
            return suff, FORM_KEYWORDS.get(base, "特殊形态")
    for suff in ("alola", "galar", "hisui", "paldea", "therian", "origin"):
        if slug.endswith(suff):
            return suff, FORM_KEYWORDS[suff]
    return "", "特殊形态"


def build_form_cards(existing_slugs: set[str]) -> list[dict]:
    """用 Showdown 数据为「形态」生成知识卡片（超级进化/超极巨化/地区形态等）。

    PokeAPI 不含这些形态，而它们在官方对战中大量使用（如超级进化喷火龙），
    没有卡片就会导导致检索不到、回答「知识库中没有数据」。
    """
    from src.rules.pokedata import load as load_pokedata

    data = load_pokedata()
    pokedex = data["pokedex"]
    zh_pokemon = data["zh_pokemon"]
    cards = []
    for slug, info in pokedex.items():
        if slug in existing_slugs or "baseStats" not in info or "types" not in info:
            continue
        suff, kind_zh = _form_kind(slug)
        if not suff:
            continue  # 只处理明确形态，跳过其它非常规条目
        from src.rules.pokedata import zh_form_name

        title_zh = zh_form_name(slug, zh_pokemon)
        base_slug = slug[: -len(suff)]
        base_zh = zh_pokemon.get(base_slug, base_slug)
        stats = info["baseStats"]
        total = sum(v for v in stats.values() if isinstance(v, int))
        types_zh = "、".join(TYPE_MAP.get(str(t).lower(), t) for t in info["types"])
        from .typechart import load_typechart, weakness_text

        flaw = weakness_text([str(t).lower() for t in info["types"]], load_typechart())
        item = info.get("requiredItem") or ""
        english_name = info.get("name", slug)
        content = (
            f"{title_zh}（{english_name}）是{base_zh}的{kind_zh}"
            f"{('，需要携带道具「' + item + '」') if item else ''}。"
            f"这是{types_zh}属性宝可梦，与普通形态的能力值不同。"
            f"种族值：生命 {stats.get('hp')}、攻击 {stats.get('atk')}、防御 {stats.get('def')}、"
            f"特攻 {stats.get('spa')}、特防 {stats.get('spd')}、速度 {stats.get('spe')}，"
            f"种族值合计 {total}。"
            + (f"属性克制：{flaw}。" if flaw else "")
        )
        cards.append({
            "card_id": f"form:{slug}",
            "type": "pokemon",
            "title_zh": title_zh,
            "title_en": english_name,
            "aliases": _form_aliases(title_zh, english_name, base_zh, suff),
            "content_zh": content,
            "content_en": f"{english_name} ({kind_zh}) base stats total {total}.",
            "tags": [str(t).lower() for t in info["types"]] + [kind_zh],
            "stats": stats,
            "source": {"provider": "showdown",
                       "url": "https://github.com/smogon/pokemon-showdown"},
        })
    return cards

def _form_aliases(title_zh: str, english_name: str, base_zh: str, suff: str) -> list[str]:
    """形态卡的检索别名：把用户可能的口语说法都列进去。"""
    aliases = [title_zh, english_name]
    if "mega" in suff:
        aliases += [f"超级进化{base_zh}", f"超进化{base_zh}", f"超级{base_zh}",
                    f"Mega{base_zh}", f"{base_zh}Mega", f"{base_zh}超级进化"]
        if suff.endswith("x"):
            aliases += [f"超级进化{base_zh}X", f"{base_zh}X"]
        elif suff.endswith("y"):
            aliases += [f"超级进化{base_zh}Y", f"{base_zh}Y"]
    elif suff == "gmax":
        aliases += [f"超极巨化{base_zh}", f"极巨化{base_zh}"]
    elif suff in ("alola", "galar", "hisui", "paldea"):
        region = {"alola": "阿罗拉", "galar": "伽勒尔", "hisui": "洗翠", "paldea": "帕底亚"}[suff]
        aliases += [f"{region}形态{base_zh}", f"{region}{base_zh}", f"{base_zh}{region}形态"]
    return [a for a in dict.fromkeys(aliases) if a]
