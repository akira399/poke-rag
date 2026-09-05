"""M2 · 查询改写：术语表翻译 + 实体别名扩展（检索前调用）。

两类映射补充双路召回：
1. 术语表：中文对战术语 -> 英文术语（"会心一击" -> "critical hit"），
   解决查询与文档无词重叠（BM25 打不到）与向量对齐不足的问题；
2. 别名扩展：query 中出现的实体中文名/俗称 -> 追加规范英文名
   （"快龙" -> "Dragonite"），专名两路都能命中。
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 中文对战术语 -> 英文术语（卡片效果文本为英文，术语不翻译就无词重叠）
TERMS: dict[str, str] = {
    "会心一击": "critical hit",
    "会心": "critical hit",
    "必杀一击": "critical hit",
    "本系": "STAB",
    "本属性加成": "STAB",
    "雨天": "rain",
    "天晴": "sun",
    "大晴天": "sun",
    "沙暴": "sandstorm",
    "冰雹": "hail",
    "雪天": "snow",
    "下雨": "rain",
    "场地": "terrain",
    "秒杀": "OHKO",
    "一击": "OHKO",
    "中毒": "poison",
    "灼伤": "burn",
    "麻痹": "paralysis",
    "睡眠": "sleep",
    "冰冻": "freeze",
    "挑衅": "Taunt",
    "道具": "item",
    "特性": "ability",
    "招式": "move",
    "技能": "move",
}

_aliases: dict[str, str] | None = None


def _load_aliases() -> dict[str, str]:
    global _aliases
    if _aliases is None:
        path = os.path.join(_ROOT, "data", "cards", "aliases.json")
        with open(path, encoding="utf-8") as f:
            _aliases = json.load(f)
    return _aliases


def expand(query: str) -> str:
    """返回完成术语翻译 + 别名扩展的查询文本（保持原始 query 在前）。

    EXPAND_DISABLED=1 可关闭（消融实验用：评估查询改写层的真实增益）。
    """
    import os

    if os.environ.get("EXPAND_DISABLED") == "1":
        return query
    parts = []
    seen = set()

    def add(token: str) -> None:
        if token and token.lower() not in seen:
            seen.add(token.lower())
            parts.append(token)

    for zh, en in TERMS.items():
        if zh in query:
            add(en)
    for alias, canonical in _load_aliases().items():
        if len(alias) >= 2 and alias in query and canonical != alias and canonical not in query:
            add(canonical)
    return " ".join([query] + parts)
