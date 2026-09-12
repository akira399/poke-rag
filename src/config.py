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
        "model": "deepseek-flash",
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
    # 向量后端：local=本地 sentence-transformers；remote=OpenAI 兼容的
    # /embeddings 接口（可用免费的 bge-m3，低配机器无需装 torch）。
    "embed": {
        "backend": "local",
        "base_url": "",
        "model": "",
        "api_key": "",
        "dim": 0,
    },
    # 免费模式：站点侧持有一个共享 Key，访客无需配置即可使用。
    # 公开地址下该 Key 会被所有访客消耗，因此按客户端限流（见 free_quota.py）。
    "free": {
        "enabled": True,
        "per_hour": 10,        # 单客户端每小时上限
        "per_day": 30,         # 单客户端每天上限
        "global_per_day": 500, # 全站每天总量兜底
    },
}

# 服务商预设：界面「快速配置」一键填充 base_url 与模型名，用户只需填自己的
# Key（本文件不含任何密钥）。全部为 OpenAI 兼容接口，可直接接入。
LLM_PRESETS: dict[str, dict] = {
    "智谱 GLM-4.7-Flash（免费）": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.7-flash",
        "note": "完全免费文本模型 · 200K 上下文 · 无需信用卡",
        "signup": "https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
    },
    "阿里云百炼（每模型 100 万 tokens）": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "note": "新用户每个模型 100 万 tokens · 有效期 90 天 · 免实名",
        "signup": "https://bailian.console.aliyun.com/",
    },
    "腾讯混元（100 万 tokens / 1 年）": {
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-turbos-latest",
        "note": "新用户 100 万 tokens 共享额度 · 有效期 1 年",
        "signup": "https://console.cloud.tencent.com/hunyuan/api-key",
    },
    "硅基流动 SiliconFlow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen3-8B",
        "note": "免费额度 + 免费向量模型（见下方向量检索预设）",
        "signup": "https://cloud.siliconflow.cn/account/ak",
    },
    "DeepSeek（便宜稳定，非免费）": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
        "note": "价格极低、中文效果好；新用户偶有赠额",
        "signup": "https://platform.deepseek.com/",
    },
}

# 远程向量检索预设：借用免费 embedding API 恢复混合检索，
# 低配服务器无需装 torch（本地小模型消融为负收益，见 docs/08）。
EMBED_PRESETS: dict[str, dict] = {
    "关闭（仅关键词 BM25）": {
        "backend": "local",
        "base_url": "",
        "model": "",
        "dim": 0,
        "note": "默认。零依赖、零成本，检索 top-3 仍有 99%",
    },
    "硅基流动 · BAAI/bge-m3（免费）": {
        "backend": "remote",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "BAAI/bge-m3",
        "dim": 1024,
        "note": "本项目原设计向量模型 · 免费 · 与 BM25 混合可提召回",
    },
    "腾讯混元 · Hunyuan-embedding": {
        "backend": "remote",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-embedding",
        "dim": 1024,
        "note": "免费额度 100 万 tokens · 与混元大模型同一 Key",
    },
}


def load(overrides: dict | None = None) -> dict:
    """加载配置；overrides 为运行时覆盖（如用户在界面填的 API Key），
    优先级最高：overrides > 环境变量 > config.local.json > 默认值。"""
    cfg = json.loads(json.dumps(_DEFAULTS))
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user_cfg = json.load(f)
        for section in ("llm", "rag", "embed", "free"):
            cfg[section].update(user_cfg.get(section, {}))
    # 环境变量覆盖（密钥走环境变量是更规范的生产姿势）
    cfg["llm"]["base_url"] = os.environ.get("LLM_BASE_URL", cfg["llm"]["base_url"])
    cfg["llm"]["api_key"] = os.environ.get("LLM_API_KEY", cfg["llm"]["api_key"])
    cfg["llm"]["model"] = os.environ.get("LLM_MODEL", cfg["llm"]["model"])
    cfg["embed"]["backend"] = os.environ.get("EMBED_BACKEND", cfg["embed"]["backend"])
    cfg["embed"]["base_url"] = os.environ.get("EMBED_BASE_URL", cfg["embed"]["base_url"])
    cfg["embed"]["model"] = os.environ.get("EMBED_MODEL_NAME", cfg["embed"]["model"])
    cfg["embed"]["api_key"] = os.environ.get("EMBED_API_KEY", cfg["embed"]["api_key"])
    for env_key, field, cast in (
        ("FREE_PER_HOUR", "per_hour", int),
        ("FREE_PER_DAY", "per_day", int),
        ("FREE_GLOBAL_PER_DAY", "global_per_day", int),
    ):
        if os.environ.get(env_key):
            cfg["free"][field] = cast(os.environ[env_key])
    if os.environ.get("FREE_ENABLED"):
        cfg["free"]["enabled"] = os.environ["FREE_ENABLED"] not in ("0", "false", "False")
    if overrides:
        for section in ("llm", "rag", "embed", "free"):
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
