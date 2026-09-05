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
    content = (
        f"道具「{item.name_zh}」（{item.name_en}）：{effect[:200]}"
    )
    from .i18n_patch import patch_title

    title_zh = item.name_zh if _has_cjk(item.name_zh) else patch_title("item", item.name_en)
    return {
        "card_id": f"item:{item.id}",
        "type": "item",
        "title_zh": title_zh or item.name_zh,
        "title_en": item.name_en,
        "aliases": [item.name_zh, item.name_en],
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



