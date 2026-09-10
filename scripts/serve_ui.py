"""M4 · Streamlit 前端：聊天（流式+引用展开）/ 检索调试 / 模型设置。

启动：python scripts/serve_ui.py  （http://localhost:8501）
"""
import json
import os
import sys

import requests
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("POKE_RAG_API", "http://127.0.0.1:8765")

st.set_page_config(page_title="Poke-RAG · 宝可梦对战知识库", page_icon="🧭")

tabs = st.tabs(["💬 问答", "🔍 检索调试", "🧮 伤害计算器", "⚙️ 模型设置"])


@st.cache_data
def load_damage_data() -> dict:
    """伤害计算所需数据：宝可梦（中文名/类型/种族值）、招式（中文/威力/属性/类别）、学习表。

    数值与属性以 Showdown 官方数据为准；中文名来自知识卡片。
    """
    import json

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw = os.path.join(root, "data", "raw", "showdown", "json")
    cards_dir = os.path.join(root, "data", "cards")

    with open(os.path.join(raw, "pokedex.json"), encoding="utf-8") as f:
        pokedex = json.load(f)["Pokedex"]
    with open(os.path.join(raw, "moves.json"), encoding="utf-8") as f:
        raw_moves = json.load(f)["Moves"]
    with open(os.path.join(raw, "learnsets.json"), encoding="utf-8") as f:
        learnsets = json.load(f)["Learnsets"]

    def toid(name: str) -> str:
        """Showdown 紧凑命名：小写、去空格/连字符/点、性别符号转 f/m。
        例：Great Tusk -> greattusk；Nidoran♀ -> nidoranf。"""
        name = name.replace("♀", "f").replace("♂", "m")
        return (name.lower().replace(" ", "").replace("-", "").replace(".", "")
                .replace("'", "").replace("’", "")  # 直/弯引号（Farfetch'd）
                .replace("é", "e").replace(":", ""))

    zh_pokemon = {}
    with open(os.path.join(cards_dir, "pokemon.jsonl"), encoding="utf-8") as f:
        for line in f:
            card = json.loads(line)
            zh_pokemon[toid(card["title_en"])] = card["title_zh"]   # 键与 Showdown 对齐
    zh_moves = {}
    with open(os.path.join(cards_dir, "move.jsonl"), encoding="utf-8") as f:
        for line in f:
            card = json.loads(line)
            zh_moves[toid(card["title_en"])] = card["title_zh"]

    # 形态中文名规则：无独立卡片时用「本体中文名（形态·形态…）」拼出。
    # 支持多重后缀迭代剥离（如 raticatealolatotem = 拉达 + 阿罗拉 + 霸主）
    FORM_SUFFIX = {
        "mega": "Mega进化", "megax": "Mega进化X", "megay": "Mega进化Y",
        "gmax": "超极巨化", "alola": "阿罗拉形态", "galar": "伽勒尔形态",
        "hisui": "洗翠形态", "paldea": "帕底亚形态", "therian": "灵兽形态",
        "incarnate": "化身形", "origin": "起源形态", "attack": "攻击形态",
        "defense": "防御形态", "speed": "速度形态", "primal": "原始回归",
        "eternamax": "永恒极巨", "totem": "霸主形态", "battlebond": "羁绊变身",
        "ash": "小智版", "cap": "帽子皮卡丘", "cosplay": "换装形态",
        "rockstar": "摇滚明星", "belle": "贵妇", "popstar": "偶像",
        "phd": "博士", "libre": "摔角手", "starter": "搭档",
        "original": "原始", "hoenn": "丰缘", "sinnoh": "神奥",
        "unova": "合众", "kalos": "卡洛斯", "partner": "搭档",
        "world": "世界", "alolancap": "阿罗拉", "sinnohcap": "神奥",
        # 帕底亚三牛（Showdown 命名无 -breed 后缀，单独补）
        "paldeacombat": "帕底亚·斗战形态", "paldeablaze": "帕底亚·火舞形态",
        "paldeaaqua": "帕底亚·水澜形态",
        # 天气/外衣形态
        "sunny": "晴天形态", "rainy": "雨天形态", "snowy": "雪天形态",
        "sandy": "沙地形态", "trash": "垃圾形态", "plant": "植物形态",
        "megaz": "Mega进化Z", "spikyeared": "刺刺耳", "noice": "无冰",
        # 对战常见形态（剑盾怪、达摩、谜拟丘、基格尔德、弱丁鱼…）
        "blade": "刀剑形态", "shield": "盾牌形态", "zen": "达摩模式",
        "busted": "现形形态", "complete": "完全体形态", "school": "群聚形态",
        "core": "核心形态", "meteor": "流星形态", "gulping": "吞下形态",
        "gorging": "大口吞下", "crowned": "王者形态", "noices": "无冰",
    }
    # 长后缀优先，避免 "ash"（小智版）误吃 "sandslash"（穿山王）的尾部
    FORM_ORDERED = sorted(FORM_SUFFIX.items(), key=lambda kv: -len(kv[0]))

    def zh_name(slug: str) -> str:
        if slug in zh_pokemon:
            return zh_pokemon[slug]
        parts, cur = [], slug
        while True:
            if cur in zh_pokemon:  # 剥到本体立即停（防后缀误吃）
                base = zh_pokemon[cur]
                return f"{base}（{'·'.join(parts)}）" if parts else base
            for suff, suff_zh in FORM_ORDERED:
                if cur.endswith(suff) and len(cur) > len(suff):
                    parts.insert(0, suff_zh)
                    cur = cur[: -len(suff)]
                    break
            else:
                return slug  # 无后缀可剥且非本体：兜底原名

    pokemon = {
        slug: {
            "zh": zh_name(slug),
            "types": [t.lower() for t in info["types"]],
            "stats": info["baseStats"],
        }
        for slug, info in pokedex.items()
        if "types" in info and "baseStats" in info
    }
    moves = {
        slug: {
            "zh": zh_moves.get(slug, ""),
            "power": info.get("basePower"),
            "type": str(info.get("type", "")).lower(),
            "category": str(info.get("category", "")).lower(),
        }
        for slug, info in raw_moves.items()
    }
    # 只保留下拉可读的条目：有中文名（避免英文/占位名混入选择器）
    pokemon = {k: v for k, v in pokemon.items() if v["zh"] != k}
    moves = {k: v for k, v in moves.items() if v["zh"]}
    learn = {k.lower(): set(v.get("learnset", {}).keys())
             for k, v in learnsets.items() if "learnset" in v}
    return {"pokemon": pokemon, "moves": moves, "learnsets": learn}


with tabs[2]:
    st.subheader("伤害计算器")
    st.caption("引擎与官方 @smogon/calc 对拍 86/86 精确一致（Δ=0）；能力值按 IV31/EV0 计算")
    data = load_damage_data()
    pk_list = sorted(data["pokemon"], key=lambda k: data["pokemon"][k]["zh"])
    c1, c2 = st.columns(2)
    with c1:
        atk_key = st.selectbox("攻击方", pk_list, format_func=lambda k: data["pokemon"][k]["zh"])
        level = st.radio("等级", [50, 100], horizontal=True)
    with c2:
        def_key = st.selectbox("防御方", pk_list, format_func=lambda k: data["pokemon"][k]["zh"])
    # 招式 = 该宝可梦学习表 ∩ 有威力的招式
    toid = atk_key.replace(" ", "").replace("-", "")
    learn = data["learnsets"].get(toid, set())
    avail = [m for m in data["moves"]
             if m.replace("-", "") in learn and (data["moves"][m]["power"] or 0) > 0]
    move_key = st.selectbox("招式", avail, format_func=lambda k: data["moves"][k]["zh"])
    c3, c4, c5 = st.columns(3)
    weather = c3.selectbox("天气", ["无", "雨天", "晴天"])
    burn = c4.checkbox("攻击方灼伤（仅物理招式生效）")
    calc = c5.button("计算", type="primary", use_container_width=True)

    if calc and move_key:
        from src.rules.damage import DamageInput, damage_rolls, gen_stat, ko_probability, type_effectiveness
        from src.rules.damage import _load_typechart

        move = data["moves"][move_key]
        atk_pk = data["pokemon"][atk_key]
        def_pk = data["pokemon"][def_key]
        physical = move["category"] == "physical"
        stat = "atk" if physical else "spa"
        stat_def = "def" if physical else "spd"
        atk_val = gen_stat(atk_pk["stats"][stat], level)
        def_val = gen_stat(def_pk["stats"][stat_def], level)
        hp = gen_stat(def_pk["stats"]["hp"], level, hp=True)
        ci = DamageInput(
            level=level, power=move["power"], atk=atk_val, defense=def_val,
            stab=move["type"] in atk_pk["types"], move_type=move["type"],
            defender_types=def_pk["types"],
            weather={"雨天": "rain", "晴天": "sun"}.get(weather),
            burn=burn and physical,
        )
        rolls = damage_rolls(ci)
        eff = type_effectiveness(move["type"], def_pk["types"], _load_typechart())
        m1, m2, m3 = st.columns(3)
        m1.metric("伤害范围", f"{min(rolls)} ~ {max(rolls)}")
        m2.metric("一击击杀", f"{ko_probability(rolls, hp):.0%}")
        m3.metric("属性倍率", f"{eff:g}x" if eff != 1 else "1x（普通）")
        st.caption(f"{data['pokemon'][atk_key]['zh']} Lv{level} 的 "
                   f"{('物攻' if physical else '特攻')} {atk_val} → "
                   f"{data['pokemon'][def_key]['zh']} 的 "
                   f"{('物防' if physical else '特防')} {def_val}；对方满血 {hp}")


def fetch_events(query: str):
    """SSE 事件流 -> yield event dict（流只能消费一次）。"""
    resp = requests.post(f"{API}/api/chat", json={"query": query}, stream=True, timeout=120)
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            yield json.loads(line[len("data: "):])


def stream_answer(prompt: str) -> tuple[str, dict]:
    """单次消费事件流：返回 (答案文本, {引用编号: 卡片})。"""
    answer_parts = []
    citations: dict[str, dict] = {}

    def gen():
        answered = False
        for event in fetch_events(prompt):
            etype = event.get("type")
            if etype == "delta":
                answered = True
                answer_parts.append(event["text"])
                yield event["text"]
            elif etype == "citations":
                for n, card in zip(event["mapping"].keys(), event["cards"]):
                    citations[n] = card
            elif etype == "reject":
                yield "知识库中未找到相关信息。"
                answered = True
        return answered

    with st.chat_message("assistant"):
        displayed = list(st.write_stream(gen()))
    answer = "".join(answer_parts) or "知识库中未找到相关信息。"
    return answer, citations


with tabs[0]:
    st.subheader("宝可梦对战知识库问答")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for n, card in (msg.get("citations") or {}).items():
                with st.expander(f"[{n}] {card.get('title_zh', '')}"):
                    st.markdown(card.get("content_zh", "") or "")

    if prompt := st.chat_input("问点什么？例如：快龙怕什么？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        answer, citations = stream_answer(prompt)
        st.session_state.messages.append(
            {"role": "assistant", "content": answer, "citations": citations}
        )

with tabs[1]:
    st.subheader("检索调试")
    q = st.text_input("检索问题", "快龙怕什么？")
    if st.button("检索"):
        hits = requests.get(f"{API}/api/search", params={"q": q, "top_k": 5}, timeout=60).json()
        for hit in hits["hits"]:
            st.markdown(f"**{hit['card_id']}** · {hit['title_zh']} · 得分 {hit['score']}")
            st.caption(hit["content_zh"][:120])

with tabs[2]:
    st.subheader("模型设置（OpenAI 兼容协议）")
    s = requests.get(f"{API}/api/settings", timeout=10).json()
    base_url = st.text_input("Base URL", value=s["base_url"])
    model = st.text_input("模型名", value=s["model"])
    api_key = st.text_input("API Key", value="", type="password",
                            help=f"当前已配置: {s['api_key_masked'] or '未配置'}")
    temperature = st.number_input("Temperature", value=0.2, step=0.05, min_value=0.0, max_value=1.0)
    if st.button("保存配置", type="primary"):
        payload = {"base_url": base_url, "model": model, "temperature": float(temperature)}
        if api_key:
            payload["api_key"] = api_key
        requests.post(f"{API}/api/settings", json=payload, timeout=10)
        st.success("已保存（不填 API Key 则保留现有）")
