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

# 常见问题实例（聊天页左侧一键提问；覆盖各条功能路径，便于快速验证）
EXAMPLES = {
    "伤害计算": [
        "化石翼龙一发岩崩打喷火龙多少血",
        "快龙用龙爪打喷火龙多少血",
        "喷火龙用十万伏特打快龙多少血",
    ],
    "属性克制": [
        "快龙怕什么属性？",
        "皮卡丘怕什么？",
    ],
    "图鉴与招式": [
        "啪嚓海胆的种族值是多少？",
        "岩崩是什么属性的招式？威力多少？",
    ],
    "特性与道具": [
        "硬壳盔甲有什么效果？",
        "生命宝珠有什么效果？",
    ],
    "招式列表（规则查询）": [
        "快龙会哪些变化招式？",
        "皮卡丘能学所有什么招式？",
    ],
    "对战环境": [
        "现在 Gen9 OU 环境使用率最高的宝可梦是谁？",
    ],
    "拒答演示（知识库外）": [
        "今天上海的天气怎么样？",
    ],
}

st.set_page_config(page_title="Poke-RAG · 宝可梦对战知识库", page_icon="🧭",
                   layout="wide")

from src.ui import theme  # noqa: E402

theme.inject(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".streamlit"))

tabs = st.tabs(["💬 问答", "🔍 检索调试", "🧮 伤害计算器", "⚙️ 模型设置"])


@st.cache_data
def load_damage_data() -> dict:
    """伤害计算器数据：直接复用公共数据层 src/rules/pokedata（单一数据来源）。

    返回结构与原实现保持一致：pokemon/moves/learnsets。
    """
    from src.rules import pokedata

    data = pokedata.load()
    pokemon = {
        slug: {"zh": info["_zh"], "types": [t.lower() for t in info["types"]],
               "stats": info["baseStats"]}
        for slug, info in data["pokedex"].items() if info.get("_zh")
    }
    moves = {
        slug: {"zh": info["_zh"], "power": info.get("basePower"),
               "type": str(info.get("type", "")).lower(),
               "category": str(info.get("category", "")).lower()}
        for slug, info in data["moves"].items() if info.get("_zh")
    }
    learnsets = {k: set(v.get("learnset", {}).keys())
                 for k, v in data["learnsets"].items() if "learnset" in v}
    return {"pokemon": pokemon, "moves": moves, "learnsets": learnsets}


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


def render_answer(prompt: str) -> tuple[str, dict]:
    """单次消费事件流：过程（路由/检索/思考）实时展示，答案流式输出。

    返回 (答案文本, {引用编号: 卡片})。
    """
    from src.generation import prompt as prompt_mod

    answer_parts: list[str] = []
    citations: dict[str, dict] = {}
    with st.chat_message("assistant"):
        status = st.status("🧠 正在处理…", expanded=True)
        thinking_ph = status.empty()
        answer_ph = st.empty()
        rejected = False
        thinking_len = 0
        for event in fetch_events(prompt):
            etype = event.get("type")
            if etype == "route":
                icon = "🔀"
                status.write(f"{icon} 路由：{event['detail']}")
            elif etype == "retrieval":
                names = "、".join(h["title_zh"] for h in event["hits"])
                status.write(f"🔍 检索命中 {len(event['hits'])} 张卡片：{names}")
            elif etype == "citations":
                for n, card in zip(event["mapping"].keys(), event["cards"]):
                    citations[n] = card
                titles = "、".join(
                    f"[{n}] {c.get('title_zh', '')}" for n, c in citations.items()
                )
                status.write(f"📚 知识片段：{titles}")
            elif etype == "reasoning":
                thinking_len += len(event["text"])
                if thinking_len % 60 < len(event["text"]):  # 节流更新
                    thinking_ph.caption("💭 模型思考：" + event["text"][-300:])
            elif etype == "delta":
                answer_parts.append(event["text"])
                answer_ph.markdown("".join(answer_parts) + "▌")
            elif etype == "reject":
                rejected = True
                status.write("🚫 置信度不足，拒绝作答")
        status.update(
            label="✅ 完成" if not rejected else "⚠️ 已拒答",
            state="complete" if not rejected else "error",
            expanded=False,
        )
        answer = "".join(answer_parts) or "知识库中未找到相关信息。"
        answer = prompt_mod.normalize_sections(answer)
        answer_ph.markdown(prompt_mod.linkify_citations(answer, citations))
        for n, card in citations.items():
            url = (card.get("source") or {}).get("url") or ""
            with st.expander(f"[{n}] {card.get('title_zh', '')}　"
                             + (f"（来源 ↗）" if url else "")):
                st.markdown(card.get("content_zh", "") or card.get("content_en", "")[:400])
                if url:
                    st.markdown(f"来源：{url}")
    return answer, citations


with tabs[0]:
    st.subheader("宝可梦对战知识库问答")
    st.caption("回答带引用编号，点击 [n] 可跳转来源页面查证；处理过程（路由/检索/思考）默认展开")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending" not in st.session_state:
        st.session_state.pending = None
    from src.generation import prompt as _prompt_mod

    # 左侧常见问题实例，右侧对话区
    col_demo, col_chat = st.columns([1, 2.6], gap="medium")

    with col_demo:
        st.markdown("##### 💡 常见问题实例")
        st.caption("点击任意一条即可提问")
        for group, items in EXAMPLES.items():
            st.markdown(f"**{group}**")
            for i, q in enumerate(items):
                if st.button(q, key=f"ex_{group}_{i}", use_container_width=True):
                    st.session_state.pending = q

    with col_chat:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                content = msg["content"]
                if msg["role"] == "assistant":
                    content = _prompt_mod.linkify_citations(content, msg.get("citations") or {})
                st.markdown(content)
                for n, card in (msg.get("citations") or {}).items():
                    url = (card.get("source") or {}).get("url") or ""
                    with st.expander(f"[{n}] {card.get('title_zh', '')}"
                                     + ("　（来源 ↗）" if url else "")):
                        st.markdown(card.get("content_zh", "") or card.get("content_en", "")[:400])
                        if url:
                            st.markdown(f"来源：{url}")

        prompt = st.chat_input("问点什么？例如：快龙怕什么？")
        if st.session_state.pending:          # 点击左侧示例触发的提问
            prompt = st.session_state.pending
            st.session_state.pending = None
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            answer, citations = render_answer(prompt)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "citations": citations}
            )
            st.rerun()

with tabs[1]:
    st.subheader("检索调试")
    q = st.text_input("检索问题", "快龙怕什么？")
    if st.button("检索"):
        hits = requests.get(f"{API}/api/search", params={"q": q, "top_k": 5}, timeout=60).json()
        for hit in hits["hits"]:
            st.markdown(f"**{hit['card_id']}** · {hit['title_zh']} · 得分 {hit['score']}")
            st.caption(hit["content_zh"][:120])

with tabs[3]:
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
