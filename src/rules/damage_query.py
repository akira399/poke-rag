"""伤害计算问答工具：把「A 用 B 打 C 多少血」解析成一次规则计算。

设计原则（确定性知识不走 LLM 算术）：
- 实体解析、数值计算全部由规则引擎完成，LLM 只负责把结果组织成自然语言；
- 信息不足时不猜：逐项列出「缺失/可提升精度」的参数，交给 LLM 追问用户；
- 有概率的地方必须给出概率（16 档随机、命中率、会心一击）。
"""
from __future__ import annotations

import math
import re

from src.rules import pokedata
from src.rules.damage import (DamageInput, damage_rolls, gen_stat, get_base_damage,
                                type_effectiveness)

# 意图关键词（检测"伤害计算"类问题）
_DAMAGE_KEYWORDS = ["多少血", "多少伤害", "打多少", "能打", "伤害是多少", "几发",
                    "能秒", "秒杀", "击杀", "能不能秒", "够不够", "伤害范围", "打掉",
                    "一下能打", "一发"]
_ATTACKERSHIP_WORDS = ["用", "使用", "一发", "一招", "打出", "使出", "放"]
_SPLIT_VERBS = ["打", "攻击", "揍", "轰", "撞", "秒"]
_LEVEL_RE = re.compile(r"(?:lv|Lv|LV|等级)\s*(\d{1,3})")

# 默认假设（用户未提供时使用，并明确告知）。全部用中文表述，避免英文缩写。
DEFAULT_LEVEL = 50
DEFAULT_IV = 31
DEFAULT_EV = 0

OPTIONAL_PARAMS = [
    "双方等级（默认按 50 级计算）",
    "个体值与努力值（默认个体值满分、努力值未投入）",
    "性格（默认无能力加成，性格最多可再提高约一成关键能力）",
    "持有道具（如讲究头带增加一半攻击力、生命宝珠增加三成伤害）",
    "特性（如威吓降低对方攻击、厚脂肪让火冰伤害减半）",
    "天气与场地（雨天水系招式威力涨一半、晴天火系招式涨一半）",
]
# 对结果影响最大的补充项（回答里应提醒用户）
KEY_SUPPLEMENTS = ["努力值投入", "性格", "持有道具", "特性"]


def is_damage_query(query: str) -> bool:
    """是否为伤害计算类问题。"""
    return any(kw in query for kw in _DAMAGE_KEYWORDS)


def parse(query: str) -> dict:
    """解析伤害问题：攻击方 / 招式 / 防御方 / 等级；缺失项写入 missing。

    语序策略：按动词（打/攻击…）切分——左侧找攻击方与招式，右侧找防御方。
    """
    text = query
    level_match = _LEVEL_RE.search(text)
    level = int(level_match.group(1)) if level_match else None

    split_pos, verb_used = None, None
    for verb in _SPLIT_VERBS:
        idx = text.find(verb)
        if idx > 0 and (split_pos is None or idx < split_pos):
            split_pos, verb_used = idx, verb

    if split_pos is None:
        left, right = text, ""
    else:
        left, right = text[:split_pos], text[split_pos + len(verb_used):]

    attacker = pokedata.resolve_pokemon(left)
    move_slug = pokedata.resolve_move(left)
    # 若左侧没找到招式，尝试全文（如"岩崩 化石翼龙打喷火龙"）
    if move_slug is None:
        move_slug = pokedata.resolve_move(query)
    defender = pokedata.resolve_pokemon(right) if right else None

    missing = []
    if attacker is None:
        missing.append("攻击方宝可梦")
    if move_slug is None:
        missing.append("使用的招式")
    if defender is None:
        missing.append("防御方宝可梦")
    if level is None:
        missing.append("双方等级（或说明使用默认 Lv50）")

    return {
        "attacker": attacker, "move": move_slug, "defender": defender,
        "level": level or DEFAULT_LEVEL,
        "level_provided": level is not None,
        "missing": missing,
    }


def _zh(slug: str | None, kind: str) -> str:
    if slug is None:
        return "（未识别）"
    info = pokedata.pokemon(slug) if kind == "pokemon" else pokedata.move(slug)
    return (info or {}).get("_zh") or slug


def format_missing(parsed: dict) -> str:
    """缺信息时的事实文本：逐项列出需要用户补充的内容。"""
    lines = ["【伤害计算：信息不足，无法计算】",
             "缺少以下必要信息："]
    for i, item in enumerate(parsed["missing"], 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    lines.append("若用户只想知道粗略结果，可说明将采用这些默认假设：")
    for item in OPTIONAL_PARAMS[:2]:
        lines.append(f"· {item}")
    lines.append("请向用户逐项追问缺失信息（不要自行假设数值）。")
    return "\n".join(lines)


def format_result(parsed: dict) -> str:
    """完整计算：返回可交给 LLM 组织语言的事实文本（含概率与假设）。"""
    attacker_slug, move_slug, defender_slug = parsed["attacker"], parsed["move"], parsed["defender"]
    atk_info, mv_info, df_info = (pokedata.pokemon(attacker_slug),
                                  pokedata.move(move_slug),
                                  pokedata.pokemon(defender_slug))
    if not (atk_info and mv_info and df_info):
        return format_missing(parsed)

    level = parsed["level"]
    power = mv_info.get("basePower") or 0
    if power == 0:
        return (f"【伤害计算】招式「{_zh(move_slug, 'move')}」是变化招式（威力 0），"
                f"不造成直接伤害，无法计算打掉多少 HP。")

    category = str(mv_info.get("category", "")).lower()
    physical = category == "physical"
    atk_stat = "atk" if physical else "spa"
    def_stat = "def" if physical else "spd"

    atk_value = gen_stat(atk_info["baseStats"][atk_stat], level)
    def_value = gen_stat(df_info["baseStats"][def_stat], level)
    defender_hp = gen_stat(df_info["baseStats"]["hp"], level, hp=True)

    move_type = str(mv_info.get("type", "")).lower()
    atk_types = [t.lower() for t in atk_info["types"]]
    def_types = [t.lower() for t in df_info["types"]]
    stab = move_type in atk_types
    eff = type_effectiveness(move_type, def_types, __import__(
        "src.pipeline.typechart", fromlist=["load_typechart"]).load_typechart())

    rolls = damage_rolls(DamageInput(
        level=level, power=power, atk=atk_value, defense=def_value,
        stab=stab, move_type=move_type, defender_types=def_types,
    ))
    dmg_min, dmg_max = min(rolls), max(rolls)
    hp_pct_min = dmg_min / defender_hp * 100 if defender_hp else 0
    hp_pct_max = dmg_max / defender_hp * 100 if defender_hp else 0
    ko_count = sum(1 for d in rolls if d >= defender_hp)
    ko_pct = ko_count / len(rolls) * 100
    accuracy = mv_info.get("accuracy")
    n_hits = math.ceil(defender_hp / dmg_min) if dmg_min > 0 else 99

    base_before_mod = get_base_damage(level, power, atk_value, def_value)
    # Showdown 的类型是首字母大写（Rock），查表用小写
    atk_types_zh = "、".join(pokedata.TYPE_ZH.get(str(t).lower(), t) for t in atk_info["types"])
    def_types_zh = "、".join(pokedata.TYPE_ZH.get(str(t).lower(), t) for t in df_info["types"])
    eff_desc = ("（免疫，伤害为 0）" if eff == 0 else
                "（四倍弱点，伤害非常高）" if eff >= 4 else
                "（弱点，效果拔群）" if eff > 1 else
                "（抗性，效果不佳）" if 0 < eff < 1 else "（无克制关系）")
    lines = [
        "【伤害计算结果（规则引擎计算，非模型推测）】",
        f"场景：{_zh(attacker_slug, 'pokemon')} {level} 级 使用"
        f"「{_zh(move_slug, 'move')}」攻击 {_zh(defender_slug, 'pokemon')} {level} 级",
        "",
        "【本次计算用的参数（未提到的都是默认值）】",
        f"· 等级：{level} 级"
        f"（{'由用户提供' if parsed.get('level_provided') else '用户未提供，按默认 50 级'}）",
        f"· 个体值：满分 {DEFAULT_IV}（默认，相当于天赋拉满）",
        f"· 努力值：{DEFAULT_EV}（默认，相当于完全没有投入努力值）",
        "· 性格：默认无能力加成",
        "· 持有道具、特性、天气：默认均无影响",
        "⚠️ 请务必提醒用户：以上未提到的项都用了默认值，会明显影响结果；",
        f"   补充 " + "、".join(KEY_SUPPLEMENTS) + " 可得到更准确的结果。",
        "",
        "【计算过程（可逐步核对）】",
        f"第 1 步 · 算实际能力值（由种族值、个体值、努力值、等级共同决定）",
        f"   攻击方 {_zh(attacker_slug, 'pokemon')}"
        f"（种族值 {atk_info['baseStats'][atk_stat]}）→ "
        f"{pokedata.STAT_ZH[atk_stat]}能力值 = {atk_value}",
        f"   防御方 {_zh(defender_slug, 'pokemon')}"
        f"（种族值 {df_info['baseStats'][def_stat]}）→ "
        f"{pokedata.STAT_ZH[def_stat]}能力值 = {def_value}",
        f"   防御方满血血量 = {defender_hp}"
        f"（由血量种族值 {df_info['baseStats']['hp']} 决定）",
        f"第 2 步 · 招式基础伤害 = （2×{level}÷5+2）× 威力{power} × {atk_value} ÷ {def_value}"
        f" ÷ 50 + 2，向下取整 = {base_before_mod}",
        f"第 3 步 · 本系加成（招式属性与自身属性相同时加成）："
        f"{'有，伤害 ×1.5' if stab else '无'}",
        f"第 4 步 · 属性相克倍率：{eff:g} 倍{eff_desc}",
        "第 5 步 · 随机浮动：实际伤害在计算值的 85%~100% 之间随机（共 16 档）",
        "",
        "【数值明细】",
        f"· 招式「{_zh(move_slug, 'move')}」：{pokedata.TYPE_ZH.get(move_type, move_type)}系，"
        f"威力 {power}，{pokedata.CATEGORY_ZH.get(category, category)}招式"
        f"，命中率 {accuracy if accuracy is not None else '必中'}",
        f"· 攻击方属性：{atk_types_zh}系",
        f"· 防御方属性：{def_types_zh}系",
        "",
        "【伤害结果】",
        f"· 伤害范围：{dmg_min} ~ {dmg_max} 点血量（对应随机浮动的最差档与最好档）",
        f"· 占对方满血比例：{hp_pct_min:.1f}% ~ {hp_pct_max:.1f}%",
        f"· 一击击杀概率：{ko_pct:.1f}%（16 档随机值中有 {ko_count} 档可一击击杀）"
        if eff > 0 else "· 属性免疫，无伤害",
    ]
    if eff > 0:
        if ko_count == len(rolls):
            lines.append("· 结论：必定一击击杀")
        elif ko_count == 0:
            lines.append(f"· 结论：无法一击击杀；按最低伤害计算需 {n_hits} 次攻击才能击倒")
        else:
            lines.append(f"· 结论：有概率一击击杀（{ko_pct:.1f}%），"
                         f"未能击杀时按最低伤害需 {n_hits} 次")
        lines.append(f"· 命中率：{accuracy if accuracy is not None else 100}%"
                     + ("" if accuracy is None else f"（有 {100 - accuracy:.0f}% 概率打空）"))
        lines.append("· 会心一击（暴击）：伤害 ×1.5，第九世代基础概率约 1/24（约 4.2%）")
    if move_slug and attacker_slug and not pokedata.can_learn(attacker_slug, move_slug):
        lines.append(f"⚠️ 注意：{_zh(attacker_slug, 'pokemon')} 在数据中不能学会"
                     f"「{_zh(move_slug, 'move')}」，该组合可能不合法")
    lines.append("")
    lines.append("请基于以上数据用中文回答，要求：")
    lines.append("1. 给出伤害范围、占满血比例、能否一击击杀以及对应概率；")
    lines.append("2. 用一两句话说明结果是怎么来的（属性相克倍率、本系加成的影响）；")
    lines.append("3. 必须提醒用户：本次用的是默认假设（等级 50、个体值满分、努力值未投入、"
                 "无性格与道具加成），补充这些信息能让结果更准确；")
    lines.append("4. 不要使用英文缩写（如 HP、EV、IV、OHKO、STAB），全部用中文表达"
                 "（血量、努力值、个体值、一击击杀、本系加成）。")
    return "\n".join(lines)


def try_build_context(query: str) -> str | None:
    """伤害问题入口：非伤害问题返回 None；伤害问题返回事实文本。"""
    if not is_damage_query(query):
        return None
    parsed = parse(query)
    if parsed["missing"]:
        # 缺宝可梦/招式等硬信息 → 让 LLM 追问；仅缺等级则按默认继续算
        hard_missing = [m for m in parsed["missing"] if "等级" not in m]
        if hard_missing:
            return format_missing(parsed)
    if parsed["attacker"] and parsed["move"] and parsed["defender"]:
        return format_result(parsed)
    return format_missing(parsed)
