"""模型链与降级：主模型遇限流/故障时自动切换到备用模型。

为什么需要：免费模型（智谱 Flash 等）在访问高峰会返回 429「访问量过大」，
公开站点上这会直接变成用户看到的报错。策略是把候选模型排成链，逐个尝试，
只有全部失败才向用户报错。

关键设计：OpenAI SDK 的流式请求在 `create()` 阶段就会抛错（尚未产出任何
内容），因此切换备用模型不会出现"前半段一个模型、后半段另一个模型"的
半截答案——只要在收到第一个 chunk 之前换，输出就是干净的。

用户在界面填了自己的 Key 时不参与降级（否则可借降级绕过站点限流）。
"""
from __future__ import annotations

from collections.abc import Iterator


def _is_retryable(err: Exception) -> bool:
    """判断错误是否值得切到下一个模型。

    值得重试：限流(429)、超时、连接错误、5xx 服务端错误。
    不值得：鉴权失败(401)、参数错误(400)、模型不存在(404)——换模型也没用，
    反而会掩盖真实配置问题。
    """
    name = type(err).__name__
    if name in ("RateLimitError", "APITimeoutError", "APIConnectionError",
                "InternalServerError"):
        return True
    status = getattr(err, "status_code", None)
    if status in (408, 409, 429, 500, 502, 503, 504):
        return True
    if name == "APIStatusError" and status and status >= 500:
        return True
    return False


def candidate_chain(cfg: dict, user_llm: bool = False) -> list[dict]:
    """构造候选模型链。

    user_llm=True（用户在界面填了自己的 Key）时不降级：否则访客可以借降级
    绕过站点限流，用站点额度跑本应计费的请求。
    """
    if user_llm:
        return [cfg["llm"]]
    chain = [cfg["llm"]]
    for fb in cfg.get("llm_fallbacks") or []:
        if fb.get("base_url") and fb.get("model"):
            chain.append(fb)
    return chain


def stream_with_fallback(cfg: dict, messages: list[dict],
                         user_llm: bool = False) -> Iterator[dict]:
    """按候选链尝试流式生成，遇到可重试错误自动切下一个。

    产生的事件：
      {"type": "reasoning"|"content", "text": ...}  正常内容
      {"type": "fallback", "detail": ...}           已切换到备用模型
      {"type": "all_failed", "detail": ...}         全部失败（上层转友好提示）

    切换到下一个模型仅在「尚未产出任何内容」时进行。若某模型已开始输出却在
    中途失败，不再切换——否则会拼接出半截来自不同模型的答案；此时直接抛出，
    由上层如实报错。
    """
    from src.generation.llm import stream_chat_events

    chain = candidate_chain(cfg, user_llm)
    for idx, model_cfg in enumerate(chain):
        produced = False
        try:
            for event in stream_chat_events(messages, model_cfg):
                produced = True
                yield event
            return
        except Exception as e:
            if produced or not _is_retryable(e):
                raise           # 已产出内容 / 不可重试：交给上层，不掩盖问题
            if idx + 1 < len(chain):
                yield {"type": "fallback",
                       "detail": f"主模型繁忙，已自动切换备用模型"
                                 f"（{chain[idx + 1].get('model', '?')}）"}
    yield {"type": "all_failed",
           "detail": "所有模型当前都繁忙，请稍后重试；"
                     "也可以在「模型配置」中填入自己的 Key 立即使用。"}
