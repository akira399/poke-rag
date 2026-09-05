"""M1 · 属性克制计算：Showdown typechart -> 弱点/抗性/免疫文本。

Showdown damageTaken 约定（实测反推）：0=正常 1=弱点(2×) 2=抗性(0.5×) 3=免疫。
克制关系是确定性知识（查表），因此写进卡片内容让检索直接命中，
不依赖 LLM 记忆（确定性知识的正确归属）。
"""
from __future__ import annotations

import json
import os

from .build_cards import TYPE_MAP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_typechart() -> dict:
    path = os.path.join(ROOT, "data", "raw", "showdown", "json", "typechart.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("TypeChart", {})


def defense_matrix(types_: list[str], chart: dict) -> dict[str, float]:
    """给定宝可梦属性组 -> {攻击属性: 综合倍率}（多属性相乘，免疫后为 0）。

    注意 Showdown 的 damageTaken 键为首字母大写（'Bug'），统一小写处理。
    """
    mult: dict[str, float] = {}
    for atk_type in chart.keys():
        rate = 1.0
        for own_type in types_:
            entry = chart.get(own_type, {}).get("damageTaken", {})
            v = entry.get(atk_type) or entry.get(atk_type.capitalize()) or 0
            # Showdown 约定（实测反推）：0=正常 1=弱点(2×) 2=抗性(0.5×) 3=免疫(0×)
            rate *= {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}.get(v, 1.0)
        mult[atk_type] = rate
    return mult


def weakness_text(types_: list[str], chart: dict) -> str:
    """生成「弱点/抗性/免疫」中文描述，返回空串表示无料可写。"""
    if not types_:
        return ""
    mult = defense_matrix(types_, chart)
    weak = [TYPE_MAP.get(t, t) for t, m in mult.items() if m > 1]
    resist = [TYPE_MAP.get(t, t) for t, m in mult.items() if 0 < m < 1]
    immune = [TYPE_MAP.get(t, t) for t, m in mult.items() if m == 0]
    parts = []
    if weak:
        parts.append(f"弱点（会受到双倍伤害）：{'、'.join(weak)}")
    if resist:
        parts.append(f"抗性（受到一半伤害）：{'、'.join(resist)}")
    if immune:
        parts.append(f"免疫：{'、'.join(immune)}")
    return "。".join(parts) if parts else ""
