"""M1 · 别名映射：中文名 / 英文名 / Showdown 别名 / 玩家俗称 -> 规范英文名

核心作用：中文问答的检索命中。query「快龙怕什么」先经别名表换出
Dragonite，再拼入英文关键词做 BM25 兜底，双语两路都吃得到。
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS_DIR = os.path.join(ROOT, "data", "cards")

# 玩家俗称/民间译名（官方简体名与民间常用叫法的对照）——手工维护，量小，价值高
_NICKNAMES = {
    "肥大": "dragonite",
    "老翁龙": "drampa",
    "咆哮虎": "incineroar",
    "土地云": "landorus-therian",
    "mega差不多娃娃": "audino-mega",
    "暴鲤龙": "gyarados",
    "耿鬼": "gengar",
    "卡比兽": "snorlax",
    "火神蛾": "volcarona",
    "钢嘴鸟": "corviknight",
    "虾仁": "clauncher",
    # 招式译名对照：民间叫法 -> 官方英文名（官方简体名以 PokeAPI 为准）
    "冷冻光线": "ice-beam",
    "破坏死光": "hyper-beam",
    "急冻光线": "ice-beam",
    "破坏光线": "hyper-beam",
    "十万伏特": "thunderbolt",
    "电光一闪": "quick-attack",
    # 特性简称
    "多鳞": "multiscale",
    "鳞翅": "multiscale",
    "威吓": "intimidate",
    # 道具别名
    "剩饭": "leftovers",
    "剩菜剩饭": "leftovers",
    "生命玉": "life-orb",
    "气腰": "focus-sash",
    "气势头带": "focus-band",
    # 其它民间/简称（官方名以 PokeAPI 为准）
    "暴露菇": "amoonguss",
    "凹凸头盔": "rocky-helmet",
    "凸凸头盔": "rocky-helmet",
    "头盔": "rocky-helmet",
}


def load_showdown_aliases() -> dict[str, str]:
    """Showdown aliases.ts 转译产物：英文别名（如 dnite -> dragonite）。"""
    path = os.path.join(ROOT, "data", "raw", "showdown", "json", "aliases.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    aliases = data.get("Aliases", {})
    return {str(k).lower(): v.lower() for k, v in aliases.items()}


def build_aliases(species_dir: str = None) -> dict[str, str]:
    """全量别名表：中文名/官方英文名/俗称/Showdown 别名 -> 规范英文名。

    覆盖 pokemon-species 官方中英名 + 卡片层全部实体的中文标题
    （招式/特性/道具/图鉴，由 cards/*.jsonl 提供）。
    返回 dict：别名(小写) -> 规范英文名(小写)。
    """
    import glob

    alias_map: dict[str, str] = {}
    species_dir = species_dir or os.path.join(ROOT, "data", "raw", "pokeapi", "pokemon-species")
    for path in glob.glob(os.path.join(species_dir, "*.json")):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        en = d.get("name", "").lower()
        if not en:
            continue
        for n in d.get("names", []):
            if n["language"]["name"] in ("zh-hans", "zh-hant"):
                alias_map[n["name"].lower()] = en
        alias_map[en] = en
    # 卡片层全部实体：标题中英互查（含招式/特性/道具/Meta 的中文名）
    for fname in ("pokemon.jsonl", "move.jsonl", "ability.jsonl", "item.jsonl", "meta.jsonl"):
        path = os.path.join(CARDS_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                alias_map.setdefault(card.get("title_zh", "").lower(),
                                     card.get("title_en", "").lower())
                alias_map.setdefault(card.get("title_en", "").lower(),
                                     card.get("title_en", "").lower())
    # 玩家俗称
    for alias, en in _NICKNAMES.items():
        alias_map.setdefault(alias.lower(), en)
    # Showdown 英文别名（覆盖已有则跳过，避免覆盖官方名）
    for alias, en in load_showdown_aliases().items():
        alias_map.setdefault(alias.lower(), en)
    return alias_map


def resolve(aliases: dict[str, str], token: str) -> str | None:
    """把 token（可能是中文名/俗名/英文名）解析成规范英文名。"""
    return aliases.get(token.strip().lower())
