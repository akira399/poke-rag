"""模型降级链测试：限流自动切备用、不掩盖真实错误、不拼接半截答案。

免费模型高峰期会 429，公开站点必须能自动降级；同时不能因为降级把
「Key 无效」这类配置错误也吞掉。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation import fallback  # noqa: E402


class FakeRateLimit(Exception):
    type_name = "RateLimitError"

    def __init__(self):
        super().__init__("429 too many requests")
        self.status_code = 429


# 让异常类名与真实 SDK 对齐（_is_retryable 按类名/状态码判断）
FakeRateLimit.__name__ = "RateLimitError"


class FakeAuthError(Exception):
    def __init__(self):
        super().__init__("401 unauthorized")
        self.status_code = 401


FakeAuthError.__name__ = "AuthenticationError"


CFG = {
    "llm": {"base_url": "https://main/v1", "model": "main-model", "api_key": "k1",
            "temperature": 0.2},
    "llm_fallbacks": [
        {"base_url": "https://backup/v1", "model": "backup-model", "api_key": "k2"},
    ],
}


def _fake_stream(behavior: dict):
    """behavior: {model_name: 'ok' | Exception 实例 | [异常, 然后 ok]}"""
    def _f(messages, llm_cfg):
        name = llm_cfg["model"]
        b = behavior.get(name, "ok")
        if isinstance(b, list):
            if b and isinstance(b[0], Exception):
                raise b.pop(0)
            b = "ok"
        if isinstance(b, Exception):
            raise b
        yield {"type": "content", "text": f"[{name}]答案"}
    return _f


def test_retryable_classification():
    assert fallback._is_retryable(FakeRateLimit()) is True
    assert fallback._is_retryable(FakeAuthError()) is False
    assert fallback._is_retryable(TimeoutError()) is False   # 无状态码、类名不匹配


def test_chain_excludes_fallback_when_user_key():
    """用户自带 Key 不参与降级（否则可借降级绕过站点限流）。"""
    chain = fallback.candidate_chain(CFG, user_llm=True)
    assert len(chain) == 1
    assert chain[0]["model"] == "main-model"


def test_chain_includes_fallback_for_site_mode():
    chain = fallback.candidate_chain(CFG, user_llm=False)
    assert [c["model"] for c in chain] == ["main-model", "backup-model"]


def test_fallback_on_rate_limit(monkeypatch):
    """主模型 429 -> 自动切换备用，并发出 fallback 事件。"""
    import src.generation.llm as llm

    monkeypatch.setattr(llm, "stream_chat_events", _fake_stream(
        {"main-model": FakeRateLimit(), "backup-model": "ok"}))

    events = list(fallback.stream_with_fallback(CFG, []))
    types = [e["type"] for e in events]
    assert "fallback" in types
    assert any(e["type"] == "content" and "backup-model" in e["text"] for e in events)
    assert not any(e["type"] == "all_failed" for e in events)


def test_no_fallback_on_auth_error(monkeypatch):
    """Key 无效(401) 不可重试：应直接抛出，不被降级掩盖。"""
    import src.generation.llm as llm

    monkeypatch.setattr(llm, "stream_chat_events", _fake_stream(
        {"main-model": FakeAuthError(), "backup-model": "ok"}))

    with pytest.raises(FakeAuthError):
        list(fallback.stream_with_fallback(CFG, []))


def test_all_failed_gives_friendly_message(monkeypatch):
    """所有模型都限流 -> 给出友好提示而非抛异常。"""
    import src.generation.llm as llm

    monkeypatch.setattr(llm, "stream_chat_events", _fake_stream(
        {"main-model": FakeRateLimit(), "backup-model": FakeRateLimit()}))

    events = list(fallback.stream_with_fallback(CFG, []))
    assert events[-1]["type"] == "all_failed"
    assert "稍后重试" in events[-1]["detail"]


def test_no_partial_answer_when_stream_breaks_midway(monkeypatch):
    """已产出内容后中断：不再切换（避免拼接半截答案），直接抛出。"""
    import src.generation.llm as llm

    def broken(messages, llm_cfg):
        yield {"type": "content", "text": "前半段"}
        raise FakeRateLimit()

    monkeypatch.setattr(llm, "stream_chat_events", broken)

    with pytest.raises(FakeRateLimit):
        list(fallback.stream_with_fallback(CFG, []))


def test_config_env_fallback_single(monkeypatch):
    """离散环境变量可配单个备用模型（部署脚本传参更简单）。"""
    from src.config import load

    monkeypatch.setenv("FALLBACK_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("FALLBACK_MODEL", "Qwen/Qwen3-8B")
    monkeypatch.setenv("FALLBACK_API_KEY", "sk-backup")
    fbs = load()["llm_fallbacks"]
    assert len(fbs) == 1
    assert fbs[0]["model"] == "Qwen/Qwen3-8B"
    assert fbs[0]["api_key"] == "sk-backup"


def test_config_env_fallback_json(monkeypatch):
    """LLM_FALLBACKS 支持 JSON 配多个备用；坏 JSON 不影响主模型。"""
    from src.config import load

    monkeypatch.setenv("LLM_FALLBACKS", '[{"base_url":"https://a/v1","model":"m1","api_key":"k"}]')
    fbs = load()["llm_fallbacks"]
    assert fbs[0]["model"] == "m1"

    monkeypatch.setenv("LLM_FALLBACKS", "{bad json")
    cfg = load()
    assert cfg["llm"]["base_url"]          # 主配置仍正常
