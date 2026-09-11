"""M3 · 配置加载：config.local.json（gitignore，含 API key 不入库）。

支持环境变量覆盖（LLM_BASE_URL / LLM_API_KEY / LLM_MODEL），
演示与生产统一走这一层（配置与代码分离、密钥不进仓库）。
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_ROOT, "config.local.json")

_DEFAULTS = {
    "llm": {
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-v4-flash",
        "temperature": 0.2,
    },
    "rag": {
        "top_k_retrieve": 20,
        "top_k_answer": 5,
        "reject_distance_threshold": 0.9,
        # 消融结论（docs/08 §4b）：轻量向量模型（mE5-small）混合后反降
        # top-3 3%（96% vs BM25-only 99%），默认关闭双路、保留架构
        "use_dense": False,
    },
}


def load(overrides: dict | None = None) -> dict:
    """加载配置；overrides 为运行时覆盖（如用户在界面填的 API Key），
    优先级最高：overrides > 环境变量 > config.local.json > 默认值。"""
    cfg = json.loads(json.dumps(_DEFAULTS))
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user_cfg = json.load(f)
        for section in ("llm", "rag"):
            cfg[section].update(user_cfg.get(section, {}))
    # 环境变量覆盖（密钥走环境变量是更规范的生产姿势）
    cfg["llm"]["base_url"] = os.environ.get("LLM_BASE_URL", cfg["llm"]["base_url"])
    cfg["llm"]["api_key"] = os.environ.get("LLM_API_KEY", cfg["llm"]["api_key"])
    cfg["llm"]["model"] = os.environ.get("LLM_MODEL", cfg["llm"]["model"])
    if overrides:
        for section in ("llm", "rag"):
            cfg[section].update(
                {k: v for k, v in (overrides.get(section) or {}).items() if v}
            )
    return cfg


def save(section: str, values: dict) -> None:
    """把（llm|rag）节的配置合并写回 config.local.json（key 从环境变量覆盖时跳过写入）。"""
    cfg: dict = {"llm": {}, "rag": {}}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.setdefault(section, {}).update(values)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def masked_key(api_key: str) -> str:
    """脱敏展示：sk-****1a2b。"""
    if not api_key:
        return ""
    if len(api_key) <= 6:
        return "****"
    return api_key[:3] + "****" + api_key[-4:]
