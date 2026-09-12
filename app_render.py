"""Poke-RAG · Render 单进程版（免费档 512MB 内存适配）。

与 Streamlit 版功能一致，但**去掉 FastAPI 中转**：规则引擎与 RAG 直接嵌入
本进程，数据只加载一份——这是免费容器内存下的正确架构（双进程会 OOM）。

Render 配置（render.yaml）：
    build: pip install -r requirements.txt
    start : streamlit run app_render.py --server.port $PORT
环境变量：
    EMBED_DISABLED=1   精简检索（BM25+查询改写，免费档推荐）
    LLM_BASE_URL / LLM_MODEL   生成层默认（用户在界面填自己的 Key，会话级保存）
"""
from __future__ import annotations

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load  # noqa: E402
from src.generation import prompt as prompt_mod  # noqa: E402
from src.generation.rag import RAGEngine  # noqa: E402
from src.retrieval.index import search  # noqa: E402
from src.rules import damage_query, pokedata  # noqa: E402
from src.ui import theme  # noqa: E402

st.set_page_config(page_title="Poke-RAG · 宝可梦对战知识库", page_icon="🧭",
                   layout="wide")
theme.inject(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".streamlit"))

API = ""  # 单进程模式：不经过任何 HTTP 中转

# 常见问题实例（左侧一键提问）
EXAMPLES = {
    "伤害计算": [
        "化石翼龙一发岩崩打喷火龙多少血",
        "快龙用龙爪打喷火龙多少血",
        "喷火龙用十万伏特打快龙多少血",
    ],
    "属性克制": ["快龙怕什么属性？", "皮卡丘怕什么？"],
    "图鉴与招式": [
        "啪嚓海胆的种族值是多少？",
        "岩崩是什么属性的招式？威力多少？",
    ],
    "特性与道具": ["硬壳盔甲有什么效果？", "生命宝珠有什么效果？"],
    "招式列表（规则查询）": ["快龙会哪些变化招式？", "皮卡丘能学所有什么招式？"],
    "对战环境": ["现在 Gen9 OU 环境使用率最高的宝可梦是谁？"],
    "拒答演示（知识库外）": ["今天上海的天气怎么样？"],
}


def _engine(llm_cfg: dict | None) -> RAGEngine:
    return RAGEngine(llm_cfg=llm_cfg)


def render_answer(prompt: str) -> tuple[str, dict]:
    """本地引擎直连：过程（路由/检索/思考）实时展示，答案流式输出。"""
    skey = st.session_state
    if not skey.get("key"):
        return ("⚠️ 尚未配置模型 API Key。请展开页面顶部「⚙️ 模型配置」填入你的"
                " DeepSeek Key（[免费注册](https://platform.deepseek.com/)），"
                "仅保存在当前会话。"), {}
    llm_cfg = {"api_key": skey["key"], "base_url": skey.get("url"),
               "model": skey.get("model")}

    answer_parts: list[str] = []
    citations: dict[str, dict] = {}
    status = st.status("🧠 正在处理…", expanded=True)
    thinking_ph = status.empty()
    answer_ph = st.empty()
    rejected, thinking_len = False, 0

    for event in _engine(llm_cfg).answer(prompt):
        etype = event.get("type")
        if etype == "route":
            status.write(f"🔀 路由：{event['detail']}")
        elif etype == "retrieval":
            names = "、".join(h["title_zh"] for h in event["hits"])
            status.write(f"🔍 检索命中 {len(event['hits'])} 张卡片：{names}")
        elif etype == "citations":
            for n, card in zip(event["mapping"].keys(), event["cards"]):
                citations[n] = card
            titles = "、".join(f"[{n}] {c.get('title_zh', '')}"
                               for n, c in citations.items())
            status.write(f"📚 知识片段：{titles}")
        elif etype == "reasoning":
            thinking_len += len(event["text"])
            if thinking_len % 60 < len(event["text"]):
                thinking_ph.caption("💭 模型思考：" + event["text"][-300:])
        elif etype == "delta":
            answer_parts.append(event["text"])
            answer_ph.markdown("".join(answer_parts) + "▌")
        elif etype == "reject":
            rejected = True
            status.write("🚫 置信度不足，拒绝作答")
    status.update(label="✅ 完成" if not rejected else "⚠️ 已拒答",
                  state="complete" if not rejected else "error",
                  expanded=False)
    answer = "".join(answer_parts) or "知识库中未找到相关信息。"
    answer_ph.markdown(prompt_mod.linkify_citations(answer, citations))
    for n, card in citations.items():
        url = (card.get("source") or {}).get("url") or ""
        with st.expander(f"[{n}] {card.get('title_zh', '')}"
                         + ("　（来源 ↗）" if url else "")):
            st.markdown(card.get("content_zh", "") or card.get("content_en", "")[:400])
            if url:
                st.markdown(f"来源：{url}")
    return answer, citations


st.markdown("## 🧭 宝可梦对战知识库问答")
st.caption("回答带引用可点击查证；处理过程实时展开；伤害计算与官方计算器一致")

if "key" not in st.session_state:
    cfg = load()
    st.session_state.key = ""
    st.session_state.url = cfg["llm"]["base_url"]
    st.session_state.model = cfg["llm"]["model"]
configured = bool(st.session_state.key)

# 配置区放主页面顶部：手机端侧边栏是折叠的，塞在里面等于找不到。
if not configured:
    st.warning("首次使用请先展开「⚙️ 模型配置」填入 API Key（DeepSeek/通义/Kimi 均可）")
with st.expander(
    "⚙️ 模型配置 · 已配置 ✓（点此修改）" if configured
    else "⚙️ 模型配置 · 点此展开填入 API Key",
    expanded=False,
):
    st.caption("支持任何 OpenAI 兼容服务；推荐 DeepSeek"
               "（[注册](https://platform.deepseek.com/)）。")
    st.info(
        "🔒 **隐私承诺：本项目不收集、不存储、不共享你的任何数据。**\n\n"
        "- API Key 只在服务器**内存**中用于本次会话调用你指定的模型："
        "**不写入磁盘、不记录日志、不上传任何第三方**，会话结束（关闭页面后约"
        " 10 分钟）即从内存销毁；\n"
        "- 对话内容同样只在内存会话中，刷新页面即清空；\n"
        "- 本项目完全开源，数据流向可在 "
        "`src/config.py` 与 `src/generation/llm.py` 中自行审计。"
    )
    k = st.text_input("API Key", value=st.session_state.key, type="password")
    u = st.text_input("接口地址", value=st.session_state.url)
    m = st.text_input("模型名", value=st.session_state.model)
    if st.button("保存到本会话", type="primary", use_container_width=True):
        st.session_state.key, st.session_state.url, st.session_state.model = k, u, m
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None

with st.expander("💡 常见问题实例（点击展开）", expanded=False):
    for group, items in EXAMPLES.items():
        st.markdown(f"**{group}**")
        for i, q in enumerate(items):
            if st.button(q, key=f"ex_{group}_{i}", use_container_width=True):
                st.session_state.pending = q

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        content = msg["content"]
        if msg["role"] == "assistant":
            content = prompt_mod.linkify_citations(content,
                                                   msg.get("citations") or {})
        st.markdown(content)
        for n, card in (msg.get("citations") or {}).items():
            url = (card.get("source") or {}).get("url") or ""
            with st.expander(f"[{n}] {card.get('title_zh', '')}"
                             + ("　（来源 ↗）" if url else "")):
                st.markdown(card.get("content_zh", "")
                            or card.get("content_en", "")[:400])
                if url:
                    st.markdown(f"来源：{url}")

prompt = st.chat_input("问点什么？例如：快龙怕什么？")
if st.session_state.pending:
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

with st.expander("🔍 检索调试"):
    q2 = st.text_input("检索问题", "快龙怕什么？")
    if st.button("运行检索"):
        hits = search(q2, top_k=5)
        for cid, score in hits:
            st.markdown(f"**{cid}** · 得分 {score:.3f}")
