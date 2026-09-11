"""Poke-RAG · HuggingFace Space 版（Gradio，免费账号 ZeroGPU 兼容）。

与本地 Streamlit 版功能一致：问答（含处理过程/引用）/ 伤害计算问答 /
检索调试 / 模型设置。差异：
- 单进程：规则引擎与 RAG 直接嵌入，无 FastAPI 中转；
- API Key 按浏览器会话保存在 gr.State（不落盘、不共享）；
- ZeroGPU 兼容：@spaces.GPU 装饰 no-op（纯 CPU 任务，不消耗 GPU 配额）；
- 首次访问需在「模型设置」页填入自己的 DeepSeek API Key（仅会话内使用）。
"""
from __future__ import annotations

import os
import sys

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import load  # noqa: E402
from src.generation import prompt as prompt_mod  # noqa: E402
from src.generation.rag import RAGEngine  # noqa: E402
from src.retrieval.index import search  # noqa: E402
from src.rules import damage_query, pokedata  # noqa: E402

# ZeroGPU 兼容：Space 上由 spaces 包提供装饰器；本地无 spaces 包时用 no-op。
# 我们的应用是纯 CPU 任务，不会真正请求 GPU，因此不消耗访客配额。
try:
    import spaces  # type: ignore

    gpu_gate = spaces.GPU
except Exception:  # 本地开发
    def gpu_gate(fn):
        return fn


# 默认回答（未配置 Key 时的引导文案）
_NO_KEY_HINT = (
    "⚠️ 尚未配置模型 API Key。请切到「⚙️ 模型设置」页签，填入你自己的"
    " DeepSeek API Key（[免费注册获取](https://platform.deepseek.com/)）。\n\n"
    "Key 只保存在你当前浏览器的会话中，不会上传存储、不会与其他用户共享。"
)


def _engine(llm_cfg: dict | None) -> RAGEngine:
    return RAGEngine(llm_cfg=llm_cfg)


# ---------------------------------------------------------------- 聊天
def chat_fn(message: str, history: list, session_key: str, session_url: str,
            session_model: str):
    """处理一轮问答；返回（流式聚合的答案, 更新后的会话状态）。"""
    if not session_key:
        yield _NO_KEY_HINT, gr.update(), gr.update(), gr.update()
        return

    llm_cfg = {"api_key": session_key}
    if session_url:
        llm_cfg["base_url"] = session_url
    if session_model:
        llm_cfg["model"] = session_model

    steps, answer = [], ""
    process_md = ""
    citations: dict[str, dict] = {}

    for event in _engine(llm_cfg).answer(message):
        etype = event.get("type")
        if etype == "route":
            steps.append(f"🔀 **路由**：{event['detail']}")
        elif etype == "retrieval":
            names = "、".join(h["title_zh"] for h in event["hits"])
            steps.append(f"🔍 **检索命中 {len(event['hits'])} 张卡片**：{names}")
        elif etype == "citations":
            for n, card in zip(event["mapping"].keys(), event["cards"]):
                citations[n] = card
        elif etype == "reasoning":
            # 思维链展示最新片段（不落盘）
            steps.append(f"💭 {event['text'][-160:]}")
        elif etype == "delta":
            answer += event["text"]
        elif etype == "reject":
            answer = "知识库中未找到相关信息。"
        # 过程面板：最新 6 步 + 正在生成提示
        process_md = "\n\n".join(steps[-6:])
        yield (f"{_process_block(process_md)}\n\n{answer or '⏳ 生成中…'}",
               gr.update(), gr.update(), gr.update())

    answer = prompt_mod.linkify_citations(answer, citations)
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": f"{_process_block(process_md)}\n\n{answer}"},
    ]
    yield answer, history, gr.update(), gr.update()


def _process_block(steps_md: str) -> str:
    if not steps_md:
        return ""
    return f"<details open><summary>⚙️ 处理过程</summary>\n\n{steps_md}\n\n</details>"


# ---------------------------------------------------------------- 伤害计算器
def damage_calc(atk_zh: str, def_zh: str, move_zh: str, level: int) -> str:
    """调用规则引擎直接计算（不经 LLM，结果即精确值）。"""
    ctx = damage_query.try_build_context(f"{atk_zh}使用{move_zh}打{def_zh}多少血")
    if ctx is None:
        return "无法识别该组合，请从下拉框选择。"
    # 表单直算：截掉「回答格式要求」等给 LLM 的指令段，只展示计算事实
    cut = ctx.find("【回答格式要求")
    return ctx[:cut].rstrip() if cut > 0 else ctx


# ---------------------------------------------------------------- 检索调试
def search_fn(q: str) -> str:
    hits = search(q, top_k=5)
    lines = []
    for cid, score in hits:
        info = next((c for c in _CARDS_CACHE if c["card_id"] == cid), None)
        title = info["title_zh"] if info else cid
        lines.append(f"**{title}**（{cid}）· 得分 {score:.3f}")
    return "\n\n".join(lines) or "无结果"


_CARDS_CACHE: list[dict] = []


def _preload() -> None:
    """启动时预热：加载卡片缓存（索引已随仓库提供）。"""
    global _CARDS_CACHE
    from src.retrieval.index import _load_cards

    _CARDS_CACHE = _load_cards()


# ---------------------------------------------------------------- 界面
def build_ui() -> gr.Blocks:
    cfg = load()
    theme = gr.themes.Soft(primary_hue="blue", neutral_hue="slate")

    with gr.Blocks(title="Poke-RAG · 宝可梦对战知识库", theme=theme) as demo:
        gr.Markdown(
            "# 🧭 Poke-RAG · 宝可梦对战知识库问答\n"
            "回答带引用可查证 · 伤害计算与官方计算器一致 · 处理过程透明可见\n\n"
            "⚠️ **首次使用请到「⚙️ 模型设置」填入你自己的 DeepSeek API Key**"
            "（[点此免费注册获取](https://platform.deepseek.com/)）。"
            "Key 仅保存在当前浏览器会话，不落盘、不共享。"
        )
        with gr.Tabs():
            with gr.Tab("💬 问答"):
                chat = gr.Chatbot(type="messages", height=440,
                                  label="对话", show_copy_button=True)
                msg = gr.Textbox(placeholder="问点什么？例如：化石翼龙一发岩崩打喷火龙多少血",
                                 show_label=False)
                state_key = gr.State("")
                state_url = gr.State("")
                state_model = gr.State("")
                clear = gr.Button("清空对话", variant="secondary")

                msg.submit(chat_fn,
                           [msg, chat, state_key, state_url, state_model],
                           [msg, chat, state_key, state_url, state_model])
                clear.click(lambda: [], None, chat)

            with gr.Tab("🧮 伤害计算器"):
                gr.Markdown("引擎与官方 @smogon/calc 对拍一致；"
                            "默认 50 级、个体值满分、努力值未投入、无性格/道具/天气。")
                data = pokedata.load()
                pk_choices = sorted(data["zh_to_slug"].keys())
                with gr.Row():
                    atk = gr.Dropdown(pk_choices, label="攻击方", filterable=True)
                    dfn = gr.Dropdown(pk_choices, label="防御方", filterable=True)
                with gr.Row():
                    lvl = gr.Slider(1, 100, value=50, step=1, label="等级")
                move = gr.Dropdown(sorted(data["zh_move_to_slug"].keys()),
                                   label="招式", filterable=True)
                btn = gr.Button("计算", variant="primary")
                out = gr.Markdown()
                btn.click(damage_calc, [atk, dfn, move, lvl], out)

            with gr.Tab("🔍 检索调试"):
                q = gr.Textbox(label="检索问题", value="快龙怕什么？")
                sbtn = gr.Button("检索")
                sout = gr.Markdown()
                sbtn.click(search_fn, q, sout)

            with gr.Tab("⚙️ 模型设置"):
                gr.Markdown("填写你自己的 API Key（仅保存在当前浏览器会话，"
                            "刷新页面后需重新填写；服务器不存储）。")
                k = gr.Textbox(label="DeepSeek API Key", type="password")
                u = gr.Textbox(label="接口地址（默认 DeepSeek 官方）",
                               value=cfg["llm"]["base_url"])
                m = gr.Textbox(label="模型名", value=cfg["llm"]["model"])
                save = gr.Button("保存到本会话", variant="primary")
                hint = gr.Markdown()
                save.click(_save_settings, [k, u, m], [state_key, state_url, state_model, hint])

    return demo


def _save_settings(key, url, model):
    if not key:
        return "", "", "", gr.Markdown.update("⚠️ 请填入 API Key")
    return key, url, model, "✅ 已保存到当前会话，可以去「💬 问答」提问了。"


_preload()

if __name__ == "__main__":
    demo = build_ui()
    demo.queue().launch(server_name="0.0.0.0",
                        server_port=int(os.environ.get("PORT", 7860)))
