"""M3 · LLM 客户端（OpenAI 兼容协议，模型/地址/密钥可配置）。

统一处理：流式输出、思维链字段（deepseek-v4 的 reasoning_content 作为
独立事件下发，UI 可展示思考过程、不混入答案正文）。换模型只改
config.local.json（OpenAI 兼容协议是事实标准，一份客户端跑遍主流推理服务）。
"""
from __future__ import annotations

from collections.abc import Iterator

from src.config import load


def _client(llm_cfg: dict | None = None):
    from openai import OpenAI

    cfg = llm_cfg or load()["llm"]
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])


def llm_config() -> dict:
    return load()["llm"]


def stream_chat(messages: list[dict]) -> Iterator[str]:
    """流式生成，只产生内容文本（reasoning 内部消耗，不下发）。"""
    for event in stream_chat_events(messages):
        if event["type"] == "content":
            yield event["text"]


def stream_chat_events(messages: list[dict], llm_cfg: dict | None = None) -> Iterator[dict]:
    """流式生成的事件流：{"type": "reasoning"|"content", "text": ...}。

    reasoning 为模型的思考过程（deepseek-v4 系列返回 reasoning_content），
    单独作为事件下发——UI 可像思维链一样展示，不混入答案正文。
    """
    cfg_all = load()
    llm = llm_cfg or cfg_all["llm"]
    resp = _client(llm).chat.completions.create(
        model=llm.get("model") or cfg_all["llm"]["model"],
        messages=messages,
        temperature=llm.get("temperature", cfg_all["llm"].get("temperature", 0.2)),
        stream=True,
    )
    for chunk in resp:
        if not (chunk.choices and chunk.choices[0].delta):
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield {"type": "reasoning", "text": reasoning}
        if delta.content:
            yield {"type": "content", "text": delta.content}
