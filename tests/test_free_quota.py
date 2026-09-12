"""免费模式配额限流测试：滑动窗口、双窗口、全局兜底、边界行为。

这是公开部署下保护站点免费 Key 的关键防线，必须有测试兜住。
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import free_quota  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    free_quota.reset()
    yield
    free_quota.reset()


CFG = {"free": {"enabled": True, "per_hour": 3, "per_day": 5, "global_per_day": 8}}


def test_allow_then_block_on_hour_limit():
    """每小时上限：前 N 次放行，第 N+1 次被拦并给出提示。"""
    for i in range(3):
        r = free_quota.take("ip:1.1.1.1", CFG)
        assert r["allowed"] is True, f"第 {i+1} 次应放行"
        assert r["hour_left"] == 3 - (i + 1)
    blocked = free_quota.take("ip:1.1.1.1", CFG)
    assert blocked["allowed"] is False
    assert blocked["reason"] == "hour"
    assert "小时" in blocked["message"]


def test_different_clients_are_isolated():
    """不同客户端各自计数，互不影响。"""
    for _ in range(3):
        free_quota.take("ip:1.1.1.1", CFG)
    assert free_quota.take("ip:1.1.1.1", CFG)["allowed"] is False
    assert free_quota.take("ip:2.2.2.2", CFG)["allowed"] is True


def test_blocked_requests_do_not_consume_quota():
    """被拦的请求不应继续累加时间戳（否则窗口永远不释放）。"""
    for _ in range(3):
        free_quota.take("ip:1.1.1.1", CFG)
    for _ in range(5):
        free_quota.take("ip:1.1.1.1", CFG)
    st = free_quota.peek("ip:1.1.1.1", CFG)
    assert st["hour_used"] == 3          # 没有被超限请求撑大


def test_day_limit_applies_across_hours(monkeypatch):
    """跨小时累计到当日上限后应被拦（用 monkeypatch 推进时间）。"""
    cfg = {"free": {"enabled": True, "per_hour": 10, "per_day": 4,
                    "global_per_day": 100}}
    t = [1000.0]
    monkeypatch.setattr(free_quota.time, "time", lambda: t[0])
    # 每轮跨过一小时窗口，逐次消耗当日额度
    used = 0
    for _ in range(4):
        assert free_quota.take("ip:9.9.9.9", cfg)["allowed"] is True
        used += 1
        t[0] += 3700                      # 跳过 1 小时
    blocked = free_quota.take("ip:9.9.9.9", cfg)
    assert blocked["allowed"] is False
    assert blocked["reason"] == "day"
    assert "天" in blocked["message"]
    assert used == 4


def test_global_daily_cap_protects_site_key():
    """全站兜底：多个不同客户端累计到全局上限后一律拒绝。"""
    for i in range(8):
        r = free_quota.take(f"ip:10.0.0.{i}", CFG)
        assert r["allowed"] is True
    blocked = free_quota.take("ip:10.0.0.99", CFG)
    assert blocked["allowed"] is False
    assert blocked["reason"] == "global"
    assert "全站" in blocked["message"]


def test_peek_does_not_consume():
    free_quota.take("ip:1.1.1.1", CFG)
    a = free_quota.peek("ip:1.1.1.1", CFG)
    b = free_quota.peek("ip:1.1.1.1", CFG)
    assert a["hour_used"] == b["hour_used"] == 1


def test_window_expiry_restores_quota(monkeypatch):
    """窗口滑过后额度自动恢复。"""
    cfg = {"free": {"enabled": True, "per_hour": 1, "per_day": 10,
                    "global_per_day": 100}}
    t = [5000.0]
    monkeypatch.setattr(free_quota.time, "time", lambda: t[0])
    assert free_quota.take("ip:3.3.3.3", cfg)["allowed"] is True
    assert free_quota.take("ip:3.3.3.3", cfg)["allowed"] is False
    t[0] += 3601                          # 超过一小时窗口
    assert free_quota.take("ip:3.3.3.3", cfg)["allowed"] is True


def test_free_limits_env_override(monkeypatch):
    """站点部署通过环境变量调额度（README 承诺的 FREE_* 变量必须生效）。"""
    from src.config import load

    monkeypatch.setenv("FREE_PER_HOUR", "7")
    monkeypatch.setenv("FREE_PER_DAY", "22")
    monkeypatch.setenv("FREE_GLOBAL_PER_DAY", "333")
    free = load()["free"]
    assert free["per_hour"] == 7
    assert free["per_day"] == 22
    assert free["global_per_day"] == 333

    monkeypatch.setenv("FREE_ENABLED", "0")
    assert load()["free"]["enabled"] is False


def test_free_mode_unavailable_without_site_key(monkeypatch):
    """站点未配共享 Key 时，免费模式应报告不可用（UI 据此引导自备 Key）。"""
    import src.config as config

    monkeypatch.setattr(config, "load", lambda *a, **k: {
        "llm": {"api_key": "", "base_url": "", "model": ""},
        "free": {"enabled": True},
        "embed": {}, "rag": {},
    })
    assert free_quota.free_mode_available() is False

    monkeypatch.setattr(config, "load", lambda *a, **k: {
        "llm": {"api_key": "sk-site"},
        "free": {"enabled": True},
        "embed": {}, "rag": {},
    })
    assert free_quota.free_mode_available() is True

    # 显式关闭免费模式时，即便有 Key 也不可用
    monkeypatch.setattr(config, "load", lambda *a, **k: {
        "llm": {"api_key": "sk-site"},
        "free": {"enabled": False},
        "embed": {}, "rag": {},
    })
    assert free_quota.free_mode_available() is False
