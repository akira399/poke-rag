"""免费 API 预设与远程向量配置的单元测试。

覆盖 config.LLM_PRESETS / EMBED_PRESETS 的结构契约，以及 embed 后端的
选择逻辑（远程配置齐全 -> is_remote；本地 -> 走 sentence-transformers）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import EMBED_PRESETS, LLM_PRESETS, load  # noqa: E402


def test_llm_presets_are_openai_compatible():
    """每个预设都必须有 https 的 base_url、模型名、注册链接与说明。"""
    assert LLM_PRESETS, "预设不能为空"
    for name, p in LLM_PRESETS.items():
        assert p["base_url"].startswith("https://"), name
        assert p["model"], name
        assert p["signup"].startswith("https://"), name
        assert p["note"], name


def test_free_presets_present():
    """至少包含智谱免费模型（当前主流免费方案）。"""
    joined = " ".join(LLM_PRESETS.keys())
    assert "智谱" in joined


def test_embed_presets_structure():
    for name, p in EMBED_PRESETS.items():
        assert p["backend"] in ("local", "remote"), name
        if p["backend"] == "remote":
            assert p["base_url"].startswith("https://"), name
            assert p["model"], name
            assert p["dim"] > 0, name


def test_config_has_embed_section():
    """config.load() 必须包含 embed 节（含 backend 与远程字段）。"""
    cfg = load()
    assert "embed" in cfg
    for key in ("backend", "base_url", "model", "api_key", "dim"):
        assert key in cfg["embed"], key


def test_embed_env_override(monkeypatch):
    """环境变量应能覆盖向量后端配置（服务器级部署用）。"""
    monkeypatch.setenv("EMBED_BACKEND", "remote")
    monkeypatch.setenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("EMBED_MODEL_NAME", "BAAI/bge-m3")
    cfg = load()
    assert cfg["embed"]["backend"] == "remote"
    assert cfg["embed"]["model"] == "BAAI/bge-m3"


def test_is_remote_detection(monkeypatch):
    """backend=remote 且地址/模型齐全才算远程；缺一不可。"""
    from src.retrieval import embed

    monkeypatch.setenv("EMBED_BACKEND", "remote")
    monkeypatch.setenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("EMBED_MODEL_NAME", "BAAI/bge-m3")
    assert embed.is_remote() is True
    # 清掉模型名 -> 判定为非远程（回退本地）
    monkeypatch.setenv("EMBED_MODEL_NAME", "")
    monkeypatch.delenv("EMBED_MODEL_NAME")
    cfg = load()
    cfg_embed = cfg["embed"]
    cfg_embed["model"] = ""
    monkeypatch.setattr(embed, "_embed_cfg", lambda: {"backend": "remote",
                                                      "base_url": "https://x/v1",
                                                      "model": ""})
    assert embed.is_remote() is False


def test_remote_backend_available_without_torch(monkeypatch):
    """远程后端不依赖 torch：配置齐全即视为可用（低配服务器关键路径）。"""
    from src.retrieval import embed

    monkeypatch.setattr(embed, "_embed_cfg", lambda: {
        "backend": "remote", "base_url": "https://api.siliconflow.cn/v1",
        "model": "BAAI/bge-m3", "dim": 1024,
    })
    assert embed.embedding_available() is True


@pytest.mark.parametrize("backend", ["local", "remote"])
def test_no_secrets_in_presets(backend):
    """预设里不能出现任何密钥字段（防止误把 Key 写进仓库）。"""
    presets = LLM_PRESETS if backend == "local" else EMBED_PRESETS
    for p in presets.values():
        assert "api_key" not in p or not p["api_key"]
