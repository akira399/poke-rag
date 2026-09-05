"""M3 · LLM 客户端（OpenAI 兼容协议，模型/地址/密钥可配置）。

统一处理：流式输出、思维链字段（deepseek-v4 的 reasoning_content 不
作为答案内容输出）、超时。换模型只改 config.local.json（
OpenAI 兼容协议是事实标准，一份客户端跑遍主流推理服务）。
"""
from __future__ import annotations

from collections.abc import Iterator

from src.config import load


def _client():
    from openai import OpenAI

    cfg = load()["llm"]
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])


def llm_config() -> dict:
    return load()["llm"]


def stream_chat(messages: list[dict]) -> Iterator[str]:
    """流式生成，只产生内容文本（reasoning 内部消耗，不下发）。"""
    cfg = _client()
    resp = cfg.chat.completions.create(
        model=load()["llm"]["model"],
        messages=messages,
        temperature=load()["llm"]["temperature"],
        stream=True,
    )
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta:
            content = chunk.choices[0].delta.content
            if content:
                yield content
