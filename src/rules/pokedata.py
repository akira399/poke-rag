"""公共数据层：宝可梦/招式/学习表 + 中文名映射 + 名称解析。

UI（伤害计算器页面）与规则工具（伤害查询）共用同一层，
避免两处各自加载导致不一致（曾因键名格式不同出现 535 处中文名丢失）。

数据来源：Pokémon Showdown（权威数值）+ data/cards（中文名）。
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RAW = os.path.join(_ROOT, "data", "raw", "showdown", "json")
_CARDS = os.path.join(_ROOT, "data", "cards")

_CACHE: dict | None = None

# 形态后缀 -> 中文（无独立卡片时用「本体（形态）」拼出）
FORM_SUFFIX = {
    "mega": "Mega进化", "megax": "Mega进化X", "megay": "Mega进化Y", "megaz": "Mega进化Z",
    "gmax": "超极巨化", "alola": "阿罗拉形态", "galar": "伽勒尔形态",
    "hisui": "洗翠形态", "paldea": "帕底亚形态", "therian": "灵兽形态",
    "incarnate": "化身形", "origin": "起源形态", "attack": "攻击形态",
    "defense": "防御形态", "speed": "速度形态", "primal": "原始回归",
    "eternamax": "永恒极巨", "totem": "霸主形态", "battlebond": "羁绊变身",
    "ash": "小智版", "cap": "帽子皮卡丘", "cosplay": "换装形态",
    "rockstar": "摇滚明星", "belle": "贵妇", "popstar": "偶像", "phd": "博士",
    "libre": "摔角手", "starter": "搭档", "original": "原始", "hoenn": "丰缘",
    "sinnoh": "神奥", "unova": "合众", "kalos": "卡洛斯", "partner": "搭档",
    "world": "世界", "alolancap": "阿罗拉", "sinnohcap": "神奥",
    "paldeacombat": "帕底亚·斗战形态", "paldeablaze": "帕底亚·火舞形态",
    "paldeaaqua": "帕底亚·水澜形态",
    "blade": "刀剑形态", "shield": "盾牌形态", "zen": "达摩模式",
    "busted": "现形形态", "complete": "完全体形态", "school": "群聚形态",
    "core": "核心形态", "meteor": "流星形态", "gulping": "吞下形态",
    "gorging": "大口吞下", "crowned": "王者形态",
    "sunny": "晴天形态", "rainy": "雨天形态", "snowy": "雪天形态",
    "sandy": "沙地形态", "trash": "垃圾形态", "plant": "植物形态",
}
_FORM_ORDERED = sorted(FORM_SUFFIX.items(), key=lambda kv: -len(kv[0]))

# 能力值字段 -> 中文
STAT_ZH = {"hp": "HP", "atk": "攻击", "def": "防御", "spa": "特攻",
           "spd": "特防", "spe": "速度"}

TYPE_ZH = {
    "normal": "一般", "fire": "火", "water": "水", "electric": "电", "grass": "草",
    "ice": "冰", "fighting": "格斗", "poison": "毒", "ground": "地面", "flying": "飞行",
    "psychic": "超能力", "bug": "虫", "rock": "岩石", "ghost": "幽灵", "dragon": "龙",
    "dark": "恶", "steel": "钢", "fairy": "妖精", "stellar": "星晶", "unknown": "未知",
}
CATEGORY_ZH = {"physical": "物理", "special": "特殊", "status": "变化"}


def toid(name: str) -> str:
    """Showdown 紧凑命名：小写、去空格/连字符/点/引号，性别符号转 f/m。"""
    name = name.replace("♀", "f").replace("♂", "m")
    return (name.lower().replace(" ", "").replace("-", "").replace(".", "")
            .replace("'", "").replace("\u2019", "").replace("é", "e").replace(":", ""))


def _zh_name(slug: str, zh_pokemon: dict[str, str]) -> str:
    """slug -> 中文名（无独立卡片时按形态后缀拼出）。"""
    if slug in zh_pokemon:
        return zh_pokemon[slug]
    parts, cur = [], slug
    while True:
        if cur in zh_pokemon:
            base = zh_pokemon[cur]
            return f"{base}（{'·'.join(parts)}）" if parts else base
        for suff, suff_zh in _FORM_ORDERED:
            if cur.endswith(suff) and len(cur) > len(suff):
                parts.insert(0, suff_zh)
                cur = cur[: -len(suff)]
                break
        else:
            return slug


def load() -> dict:
    """加载并缓存全部数据（首次调用约 1-2 秒）。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with open(os.path.join(_RAW, "pokedex.json"), encoding="utf-8") as f:
        pokedex = json.load(f)["Pokedex"]
    with open(os.path.join(_RAW, "moves.json"), encoding="utf-8") as f:
        moves = json.load(f)["Moves"]
    with open(os.path.join(_RAW, "learnsets.json"), encoding="utf-8") as f:
        learnsets = json.load(f)["Learnsets"]

    zh_pokemon, zh_moves = {}, {}
    for fname, target in (("pokemon.jsonl", zh_pokemon), ("move.jsonl", zh_moves)):
        path = os.path.join(_CARDS, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                target[toid(card["title_en"])] = card["title_zh"]

    # 中文名 -> slug（供问题解析）；只保留已汉化、数据齐备的条目
    zh_to_slug: dict[str, str] = {}
    for slug, info in pokedex.items():
        if "baseStats" not in info or "types" not in info:
            continue
        zh = _zh_name(slug, zh_pokemon)
        if zh != slug:
            zh_to_slug.setdefault(zh, slug)
            info["_zh"] = zh
    zh_move_to_slug: dict[str, str] = {}
    for slug, info in moves.items():
        zh = zh_moves.get(toid(slug))
        if zh:
            zh_move_to_slug.setdefault(zh, slug)
            info["_zh"] = zh

    _CACHE = {
        "pokedex": pokedex, "moves": moves, "learnsets": learnsets,
        "zh_pokemon": zh_pokemon, "zh_moves": zh_moves,
        "zh_to_slug": zh_to_slug, "zh_move_to_slug": zh_move_to_slug,
    }
    return _CACHE


def resolve_pokemon(text: str) -> str | None:
    """从自然语言片段中找宝可梦（最长匹配中文名），返回 slug。"""
    data = load()
    best, best_len = None, 0
    for zh, slug in data["zh_to_slug"].items():
        if len(zh) >= 2 and zh in text and len(zh) > best_len:
            best, best_len = slug, len(zh)
    return best


def resolve_move(text: str) -> str | None:
    """从自然语言片段中找招式（最长匹配中文名），返回 slug。"""
    data = load()
    best, best_len = None, 0
    for zh, slug in data["zh_move_to_slug"].items():
        if len(zh) >= 2 and zh in text and len(zh) > best_len:
            best, best_len = slug, len(zh)
    return best


def pokemon(slug: str) -> dict | None:
    return load()["pokedex"].get(slug)


def move(slug: str) -> dict | None:
    return load()["moves"].get(slug)


def can_learn(pokemon_slug: str, move_slug: str) -> bool:
    """该宝可梦是否能学会该招式（用于校验问题里的组合是否合法）。"""
    learnset = load()["learnsets"].get(toid(pokemon_slug), {}).get("learnset", {})
    return toid(move_slug) in learnset
