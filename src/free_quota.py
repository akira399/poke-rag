"""免费模式配额：内存滑动窗口限流。

站点侧持有一个共享的免费模型 Key（见 config 的 free 节 + LLM_API_KEY 环境
变量），访客无需配置即可使用。公开地址下这个 Key 会被所有人消耗，因此必须
限流：按客户端（IP 优先，取不到则退化为会话 ID）做小时/天双窗口计数，再加
一道全局日上限兜底。超限时引导用户改用自备 Key。

单进程部署（app_render.py）用进程内字典即可；多副本部署需换 Redis 等共享
存储，否则各处计数独立、限额会被放大 N 倍。
"""
from __future__ import annotations

import time

_HOUR = 3600
_DAY = 86400

# client_id -> {"hour": [ts, ...], "day": [ts, ...]}
_BUCKETS: dict[str, dict[str, list[float]]] = {}
# 全站当天消耗时间戳（防单个 IP 换 IP 绕过后的总量失控）
_GLOBAL_DAY: list[float] = []


def _prune(stamps: list[float], window: int, now: float) -> list[float]:
    """丢弃窗口外的旧时间戳（列表按时间递增，从头裁剪即可）。"""
    if not stamps:
        return []
    cutoff = now - window
    i = 0
    for i, ts in enumerate(stamps):
        if ts >= cutoff:
            return stamps[i:]
    return []


def _limits(cfg: dict | None = None) -> dict:
    from src.config import load

    free = (cfg or load()).get("free", {})
    return {
        "enabled": bool(free.get("enabled", True)),
        "per_hour": int(free.get("per_hour", 10)),
        "per_day": int(free.get("per_day", 30)),
        "global_per_day": int(free.get("global_per_day", 500)),
    }


def free_mode_available() -> bool:
    """站点侧是否配好了免费 Key（没配则免费模式不可用，只能自备 Key）。"""
    from src.config import load

    cfg = load()
    return bool(cfg.get("free", {}).get("enabled", True)) and bool(
        cfg["llm"].get("api_key")
    )


def peek(client_id: str, cfg: dict | None = None) -> dict:
    """查看剩余额度，不消耗。供界面展示。"""
    lim = _limits(cfg)
    now = time.time()
    bucket = _BUCKETS.setdefault(client_id, {"hour": [], "day": []})
    bucket["hour"] = _prune(bucket["hour"], _HOUR, now)
    bucket["day"] = _prune(bucket["day"], _DAY, now)
    return {
        "allowed": (len(bucket["hour"]) < lim["per_hour"]
                    and len(bucket["day"]) < lim["per_day"]
                    and len(_prune(_GLOBAL_DAY, _DAY, now)) < lim["global_per_day"]),
        "hour_used": len(bucket["hour"]),
        "hour_limit": lim["per_hour"],
        "day_used": len(bucket["day"]),
        "day_limit": lim["per_day"],
        "hour_left": max(0, lim["per_hour"] - len(bucket["hour"])),
        "day_left": max(0, lim["per_day"] - len(bucket["day"])),
    }


def take(client_id: str, cfg: dict | None = None) -> dict:
    """检查并消耗一次配额；返回含 allowed/剩余/原因的字典。

    只在 allowed=True 时计数，避免超限请求继续累加时间戳。
    """
    lim = _limits(cfg)
    now = time.time()
    bucket = _BUCKETS.setdefault(client_id, {"hour": [], "day": []})
    bucket["hour"] = _prune(bucket["hour"], _HOUR, now)
    bucket["day"] = _prune(bucket["day"], _DAY, now)

    global_used = _prune(_GLOBAL_DAY, _DAY, now)
    _GLOBAL_DAY[:] = global_used

    if len(global_used) >= lim["global_per_day"]:
        return {"allowed": False, "reason": "global",
                "message": "今日全站免费额度已用完，请改用「自备 API Key」模式继续使用。"}
    if len(bucket["hour"]) >= lim["per_hour"]:
        return {"allowed": False, "reason": "hour",
                "message": f"免费模式每小时限 {lim['per_hour']} 次，已用完。"
                           "可稍后再试，或在「模型配置」里填入自己的 Key 继续使用。"}
    if len(bucket["day"]) >= lim["per_day"]:
        return {"allowed": False, "reason": "day",
                "message": f"免费模式每天限 {lim['per_day']} 次，今天已用完。"
                           "请明天再来，或填入自己的 Key 继续使用。"}

    bucket["hour"].append(now)
    bucket["day"].append(now)
    _GLOBAL_DAY.append(now)
    return {
        "allowed": True,
        "hour_used": len(bucket["hour"]), "hour_limit": lim["per_hour"],
        "day_used": len(bucket["day"]), "day_limit": lim["per_day"],
        "hour_left": lim["per_hour"] - len(bucket["hour"]),
        "day_left": lim["per_day"] - len(bucket["day"]),
    }


def reset() -> None:
    """清空计数（测试用）。"""
    _BUCKETS.clear()
    _GLOBAL_DAY.clear()
