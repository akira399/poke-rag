"""M5 · 招式查询工具：宝可梦 -> 可学习招式（全部/按类别/按威力）。

集合型查询（"所有招式""变化招式"）不能靠卡片内容穷举——卡片只是摘要；
正确做法是规则引擎直接查 learnsets + moves（确定性数据，非 LLM 生成），
结果作为事实上下文注入生成层（Agentic RAG 的工具调用形态）。
"""
from __future__ import annotations

import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RAW = os.path.join(_ROOT, "data", "raw", "showdown", "json")
_CARDS = os.path.join(_ROOT, "data", "cards")

_CACHE: dict = {}

_TYPE_ZH = {
    "normal": "一般", "fire": "火", "water": "水", "electric": "电", "grass": "草",
    "ice": "冰", "fighting": "格斗", "poison": "毒", "ground": "地面", "flying": "飞行",
    "psychic": "超能力", "bug": "虫", "rock": "岩石", "ghost": "幽灵", "dragon": "龙",
    "dark": "恶", "steel": "钢", "fairy": "妖精", "stellar": "星晶",
}

# 招式集合查询的意图关键词（与宝可梦名同时命中才路由）
_QUERY_KEYWORDS = ["所有招式", "全部招式", "招式有哪些", "会什么招式", "会哪些招式",
                   "招式列表", "变化招式", "辅助招式", "非攻击招式", "威力0", "威力为零",
                   "什么招式", "哪些招式", "能学什么", "能学哪些", "技能有哪些"]


def _load() -> dict:
    if _CACHE:
        return _CACHE
    with open(os.path.join(_RAW, "moves.json"), encoding="utf-8") as f:
        moves = json.load(f)["Moves"]
    with open(os.path.join(_RAW, "learnsets.json"), encoding="utf-8") as f:
        learnsets = json.load(f)["Learnsets"]
    moves_zh: dict[str, str] = {}
    path = os.path.join(_CARDS, "move.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                toid = card["title_en"].lower().replace(" ", "").replace("-", "")
                moves_zh[toid] = card["title_zh"]
    _CACHE.update({"moves": moves, "learnsets": learnsets, "moves_zh": moves_zh})
    return _CACHE


def list_moves(species_en: str) -> dict | None:
    """按类别返回可学习招式：{damaging:[...], status:[...]}，未知宝可梦返回 None。"""
    data = _load()
    toid = species_en.lower().replace(" ", "").replace("-", "")
    learn = data["learnsets"].get(toid, {}).get("learnset", {})
    if not learn:
        return None
    damaging, status = [], []
    for mid in learn:
        info = data["moves"].get(mid)
        if not info:
            continue
        name = data["moves_zh"].get(mid, mid)
        power = info.get("basePower") or 0
        mtype = _TYPE_ZH.get(str(info.get("type", "")).lower(), info.get("type", ""))
        category = str(info.get("category", "")).lower()
        entry = {"name": name, "power": power, "type": mtype, "category": category}
        if category == "status":
            status.append(entry)
        else:
            damaging.append(entry)
    damaging.sort(key=lambda e: -e["power"])
    status.sort(key=lambda e: e["name"])
    return {"damaging": damaging, "status": status}


def format_moves(species_zh: str, result: dict, limit_all: int = 40) -> str:
    """规则查询结果 -> 中文文本（攻击招式按威力降序；变化招式按名称序）。

    limit_all <= 0 表示不截断（用户明确要「所有招式」时全列）。
    """
    lines = [f"【{species_zh} 可学习招式（规则查询结果）】"]
    dmg = result["damaging"]
    st = result["status"]
    if dmg:
        lines.append(f"攻击招式 {len(dmg)} 个（按威力排序）：")
        for e in dmg[:limit_all] if limit_all > 0 else dmg:
            lines.append(f"· {e['name']}（{e['type']}系，威力{e['power']}）")
        if limit_all > 0 and len(dmg) > limit_all:
            lines.append(f"…… 其余 {len(dmg) - limit_all} 个略")
    if st:
        lines.append(f"变化招式 {len(st)} 个：")
        for e in st[:limit_all] if limit_all > 0 else st:
            lines.append(f"· {e['name']}（{e['type']}系）")
        if limit_all > 0 and len(st) > limit_all:
            lines.append(f"…… 其余 {len(st) - limit_all} 个略")
    return "\n".join(lines)


def detect_move_query(query: str, aliases: dict[str, str]) -> tuple[str | None, bool]:
    """意图检测：query 是否命中「宝可梦 + 招式集合」模式。

    返回 (species_en 或 None, 是否命中)。宝可梦名来自别名表（中文名/俗称）。
    """
    if not any(kw in query for kw in _QUERY_KEYWORDS):
        return None, False
    # 找 query 中的物种名：取最长匹配（别名表 value 为规范英文名）
    best_en, best_len = None, 0
    for alias, en in aliases.items():
        if len(alias) >= 2 and alias in query and len(alias) > best_len:
            # 只要 pokemon 类别名（move/item 名也可能命中，如「十万伏特」）
            if _is_pokemon_alias(en):
                best_en, best_len = en, len(alias)
    if not best_en:
        return None, False
    return best_en, True


_POKEMON_IDS: set[str] | None = None


def _is_pokemon_alias(en: str) -> bool:
    global _POKEMON_IDS
    if _POKEMON_IDS is None:
        _POKEMON_IDS = set()
        path = os.path.join(_CARDS, "pokemon.jsonl")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    card = json.loads(line)
                    _POKEMON_IDS.add(card["title_en"].lower())
    return en.lower() in _POKEMON_IDS
