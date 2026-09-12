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

    # 形态感知解析（识别「超级进化喷火龙X / 阿罗拉形态」等说法）
    attacker, atk_note = pokedata.resolve_pokemon_smart(left)
    move_slug = pokedata.resolve_move(left)
    # 若左侧没找到招式，尝试全文（如"岩崩 化石翼龙打喷火龙"）
    if move_slug is None:
        move_slug = pokedata.resolve_move(query)
    defender, def_note = (pokedata.resolve_pokemon_smart(right) if right else (None, ""))
    if defender is None and def_note == "" and right:
        defender, def_note = (None, "")

    missing = []
    if attacker is None:
        missing.append(atk_note or "攻击方宝可梦")
    if move_slug is None:
        missing.append("使用的招式")
    if defender is None:
        missing.append(def_note or "防御方宝可梦")
    if level is None:
        missing.append("双方等级（或说明使用默认 Lv50）")

    return {
        "attacker": attacker, "move": move_slug, "defender": defender,
        "level": level or DEFAULT_LEVEL,
        "level_provided": level is not None,
        "missing": missing,
        "form_hint": atk_note or def_note or "",
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


def _stat_with_ev(base: int, level: int, ev: int, nature: float = 1.0) -> int:
    """能力值（含努力值与性格加成；性格在 +5 之后相乘再向下取整）。"""
    val = (2 * base + DEFAULT_IV + ev // 4) * level // 100 + 5
    return math.floor(val * nature)


def _hp_with_ev(base: int, level: int, ev: int) -> int:
    return (2 * base + DEFAULT_IV + ev // 4) * level // 100 + level + 10


def extreme_scenarios(parsed: dict, atk_info: dict, mv_info: dict, df_info: dict,
                      level: int, power: int, move_type: str, physical: bool,
                      stab: bool, def_types: list[str]) -> list[dict]:
    """极端情况分析：默认假设对结果的影响有多大。

    因为用户没给努力值/性格/道具/天气，真实结果是一个区间。这里算出两端：
    · 最不利情形：我方零投入、无道具天气；对方血量与防御都拉满且有性格加成
    · 最有利情形：我方努力值拉满 + 性格加成 + 道具 + 有利天气；对方零投入
    两端的击杀结论决定了「什么情况下必死 / 一定不死 / 看概率」。
    """
    atk_stat = "atk" if physical else "spa"
    def_stat = "def" if physical else "spd"
    atk_base = atk_info["baseStats"][atk_stat]
    def_base = df_info["baseStats"][def_stat]
    hp_base = df_info["baseStats"]["hp"]

    # 有利天气只在招式属性匹配时生效
    weather = None
    if move_type == "water":
        weather = "rain"
    elif move_type == "fire":
        weather = "sun"

    def run(atk_ev, atk_nature, item_mult, weather_on, def_ev, def_nature, hp_ev):
        atk_v = _stat_with_ev(atk_base, level, atk_ev, atk_nature)
        def_v = _stat_with_ev(def_base, level, def_ev, def_nature)
        hp_v = _hp_with_ev(hp_base, level, hp_ev)
        rolls = damage_rolls(DamageInput(
            level=level, power=power, atk=atk_v, defense=def_v, stab=stab,
            move_type=move_type, defender_types=def_types,
            weather=weather if weather_on else None, item_mult=item_mult,
        ))
        ko = sum(1 for d in rolls if d >= hp_v) / len(rolls) * 100 if hp_v else 0
        return {"rolls": rolls, "hp": hp_v, "ko_pct": ko,
                "dmg_min": min(rolls), "dmg_max": max(rolls),
                "atk_v": atk_v, "def_v": def_v}

    return [
        {"name": "最不利情形（我方零投入，对方满血量满防御并有性格加成）",
         "detail": "我方努力值 0、无性格加成、无道具无天气；对方血量与防御努力值拉满",
         "result": run(0, 1.0, 1.0, False, 252, 1.1, 252)},
        {"name": "中间情形（双方常规投入，各拉满努力值 252 并有性格加成）",
         "detail": "我方进攻努力值 252 + 性格加成；对方血量与防御努力值 252 + 性格加成",
         "result": run(252, 1.1, 1.0, False, 252, 1.1, 252)},
        {"name": "最有利情形（我方全加成，对方零投入）",
         "detail": "我方进攻努力值 252 + 性格加成 + 道具加成 + 有利天气；对方努力值 0",
         "result": run(252, 1.1, 1.5, True, 0, 1.0, 0)},
    ]


def format_result(parsed: dict) -> str:
    """完整计算：返回可交给 LLM 组织语言的事实文本（默认假设前置、分节清晰）。"""
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
                f"不造成直接伤害，无法计算打掉多少血量。")

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
    from src.pipeline.typechart import load_typechart

    eff = type_effectiveness(move_type, def_types, load_typechart())

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

    atk_types_zh = "、".join(pokedata.TYPE_ZH.get(str(t).lower(), t) for t in atk_info["types"])
    def_types_zh = "、".join(pokedata.TYPE_ZH.get(str(t).lower(), t) for t in df_info["types"])
    move_type_zh = pokedata.TYPE_ZH.get(move_type, move_type)
    eff_desc = ("（免疫，伤害为 0）" if eff == 0 else
                "（四倍弱点，伤害非常高）" if eff >= 4 else
                "（弱点，效果拔群）" if eff > 1 else
                "（抗性，效果不佳）" if 0 < eff < 1 else "（无克制关系）")

    # 参数来源：区分用户提供 / 采用默认值
    provided, defaulted = [], []
    if parsed.get("level_provided"):
        provided.append(f"等级 {level} 级")
    else:
        defaulted.append("等级（按默认 50 级）")
    defaulted += ["个体值（按满分 31）", "努力值（按未投入 0）", "性格（按无加成）",
                  "持有道具（按无）", "特性（按无影响）", "天气场地（按无影响）"]

    lines = [
        "【第 0 节 · 计算前提（必须最先讲给用户）】",
        f"对战场景：{_zh(attacker_slug, 'pokemon')} {level} 级 使用"
        f"「{_zh(move_slug, 'move')}」攻击 {_zh(defender_slug, 'pokemon')} {level} 级",
        f"用户已提供的信息：{'、'.join(provided) if provided else '无（全部按默认值）'}",
        f"本次采用默认值的参数：{'、'.join(defaulted)}",
        "默认值的大白话解释：个体值满分 = 天赋拉满；努力值 0 = 完全没有培养投入；"
        "性格无加成 = 中性性格。",
        f"⚠️ 必须提醒用户：这些默认值会明显影响结果，补充 "
        f"{'、'.join(KEY_SUPPLEMENTS)} 后才能得到更准确的答案。",
        "",
        "【第 1 节 · 结论（先说结果）】",
    ]

    if eff == 0:
        lines.append(f"· 属性免疫：{def_types_zh}系对{move_type_zh}系招式免疫，伤害为 0。")
    else:
        if ko_count == len(rolls):
            ko_txt = "必定一击击杀"
        elif ko_count == 0:
            ko_txt = f"无法一击击杀，按最低伤害需 {n_hits} 次攻击才能击倒"
        else:
            ko_txt = f"有 {ko_pct:.1f}% 概率一击击杀，未击杀时需 {n_hits} 次攻击"
        lines += [
            f"· 伤害范围：{dmg_min} ~ {dmg_max} 点血量"
            f"（占对方满血 {hp_pct_min:.1f}% ~ {hp_pct_max:.1f}%）",
            f"· 一击击杀：{ko_txt}",
            f"· 招式命中率：{accuracy if accuracy is not None else 100}%"
            + ("" if accuracy is None else f"（{100 - accuracy:.0f}% 概率打空）"),
            "· 会心一击（暴击）：伤害 ×1.5，第九世代基础概率约 1/24（约 4.2%）",
        ]
    if not pokedata.can_learn(attacker_slug, move_slug):
        lines.append(f"· 数据校验：{_zh(attacker_slug, 'pokemon')} 在官方数据中无法学会"
                     f"「{_zh(move_slug, 'move')}」，该组合可能不合法，需告知用户。")

    lines += [
        "",
        "【第 2 节 · 计算过程（讲清楚结果怎么来的）】",
        "1. 算双方实际能力值（由种族值、等级、个体值、努力值共同决定）：",
        f"   攻击方 {_zh(attacker_slug, 'pokemon')}："
        f"{pokedata.STAT_ZH[atk_stat]}种族值 {atk_info['baseStats'][atk_stat]}"
        f" → 实际能力值 {atk_value}",
        f"   防御方 {_zh(defender_slug, 'pokemon')}："
        f"{pokedata.STAT_ZH[def_stat]}种族值 {df_info['baseStats'][def_stat]}"
        f" → 实际能力值 {def_value}",
        f"   防御方满血血量 {defender_hp}（血量种族值 {df_info['baseStats']['hp']}）",
        f"2. 招式基础伤害 =（2×等级÷5+2）× 威力 × 攻击 ÷ 防御 ÷ 50 + 2"
        f" =（2×{level}÷5+2）×{power}×{atk_value}÷{def_value}÷50+2 = {base_before_mod}",
        f"3. 本系加成（招式属性与自身属性相同时）：{'有，×1.5' if stab else '无'}",
        f"4. 属性相克：{move_type_zh}系招式打{def_types_zh}系 = {eff:g} 倍{eff_desc}",
        "5. 随机浮动：同一配置下伤害在计算值的 85%~100% 之间随机（共 16 档），"
        "这是结果呈范围而非单一数字的原因",
        "",
        "【第 3 节 · 数值明细】",
        f"· 招式「{_zh(move_slug, 'move')}」：{move_type_zh}系，威力 {power}，"
        f"{pokedata.CATEGORY_ZH.get(category, category)}招式，"
        f"命中率 {accuracy if accuracy is not None else '必中'}",
        f"· 攻击方属性：{atk_types_zh}系（{'有' if stab else '无'}本系加成）",
        f"· 防御方属性：{def_types_zh}系",
    ]

    if eff > 0:
        lines += [
            "",
            "【第 4 节 · 极端情况分析（回答「什么情况打得死 / 什么情况打不死」）】",
            "因为缺少培养参数，真实结果落在下面这个区间里。请用这几种情形回答用户，"
            "不要只给一个数字。",
        ]
        scenarios = extreme_scenarios(parsed, atk_info, mv_info, df_info,
                                      level, power, move_type, physical, stab, def_types)
        for idx, sc in enumerate(scenarios, 1):
            r = sc["result"]
            pct_min = r["dmg_min"] / r["hp"] * 100 if r["hp"] else 0
            pct_max = r["dmg_max"] / r["hp"] * 100 if r["hp"] else 0
            if r["ko_pct"] >= 100:
                verdict = "一定打得死（无论随机浮动如何都能一击击杀）"
            elif r["ko_pct"] <= 0:
                verdict = "一定打不死（任何随机浮动都无法一击击杀）"
            else:
                verdict = f"看概率（{r['ko_pct']:.0f}% 概率一击击杀，取决于随机浮动）"
            lines += [
                f"情形 {idx}｜{sc['name']}",
                f"   条件：{sc['detail']}",
                f"   伤害 {r['dmg_min']} ~ {r['dmg_max']}，占对方血量 "
                f"{pct_min:.0f}% ~ {pct_max:.0f}%（对方血量 {r['hp']}）；"
                f"我方{'物攻' if physical else '特攻'} {r['atk_v']}、"
                f"对方{'物防' if physical else '特防'} {r['def_v']}",
                f"   判定：{verdict}",
            ]
        worst = scenarios[0]["result"]["ko_pct"]
        best = scenarios[-1]["result"]["ko_pct"]
        lines.append("")
        if worst >= 100:
            lines.append("★ 总体结论：在所有合理配置下都必定一击击杀。")
        elif best <= 0:
            lines.append("★ 总体结论：在所有合理配置下都无法一击击杀。")
        else:
            lines.append("★ 总体结论：结果取决于培养配置——最不利配置下一击击杀概率 "
                         f"{worst:.0f}%（基本打不死），最有利配置下 {best:.0f}%（大概率打得死）。")
            lines.append("   把结果从「打不死」推到「打得死」的关键因素："
                         + "、".join(KEY_SUPPLEMENTS)
                         + "，以及同一配置下的随机浮动（伤害有 85%~100% 的波动）。")

    lines += [
        "",
        "【回答格式要求（严格遵守，保证排版整洁）】",
        "1. 用 Markdown 输出，按四块顺序组织，每块用 ### 三级标题；",
        "2. 顺序固定为：计算前提 → 结论 → 计算过程 → 极端情况分析；",
        "3. 「计算前提」必须放在最前面，用列表逐条列出默认值，"
        "并用一句话说明这些默认值会影响结果、补充哪些信息更准确；",
        "4. 「结论」用列表给出：伤害范围、占满血比例、能否一击击杀及概率、命中率、暴击；",
        "5. 「计算过程」用有序列表逐步说明（能力值 → 基础伤害 → 本系 → 克制 → 随机浮动），"
        "每步一行，不要写成大段文字；",
        "6. 「极端情况分析」必须分段，禁止把多个情形写进同一段：每个情形用"
        "列表项呈现，格式严格如下（顺序为 情形1、情形2、情形3）：\n"
        "   - **情形 1｜最不利情形（…）**：条件 …；伤害 …；判定 …\n"
        "   - **情形 2｜中间情形（…）**：…\n"
        "   - **情形 3｜最有利情形（…）**：…\n"
        "   列表项之后另起一段写「★ 总体结论」；",
        "7. 全文只用中文术语（血量、努力值、个体值、一击击杀、本系加成），禁止英文缩写；",
        "8. 引用知识片段时在句末标注 [1]，同一编号不要重复标注。",
    ]
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
