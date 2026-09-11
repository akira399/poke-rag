"""M2 · 多语言稠密嵌入（query 与文档共用一个编码器）。

模型按资源可切换（按需选型）：
- data/models/multilingual-e5-small （约 110MB，384 维，默认：低配机器）
- data/models/bge-m3 （约 2.2GB，1024 维，满配时切换，需 ~4GB 内存）
e5 系列需要指令前缀（query:/passage:），bge 系列无需——embed.py 内部处理。
"""
from __future__ import annotations

import os
import ssl

_MODELS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "models",
)

# 模型候选：本地目录优先；云端/无本地目录时按完整 HF repo id 自动下载。
# (本地目录名或 HF repo id, 是否 e5 系需前缀)
_MODEL_CANDIDATES = [
    ("intfloat/multilingual-e5-small", True),   # 轻量默认（384 维）
    ("BAAI/bge-m3", False),                     # 满配选项（1024 维，需大内存）
]
_MODEL_DIR = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
_IS_E5 = True
if not (os.path.isdir(os.path.join(_MODELS_ROOT, _MODEL_DIR.replace("/", os.sep)))
        or os.path.isdir(os.path.join(_MODELS_ROOT, os.path.basename(_MODEL_DIR)))):
    # 本地无缓存目录：逐个候选找本地，找不到则保持完整 repo id（SentenceTransformer 会从 Hub 下载）
    for name, is_e5 in _MODEL_CANDIDATES:
        if os.path.isdir(os.path.join(_MODELS_ROOT, name.split("/")[-1])):
            _MODEL_DIR, _IS_E5 = name, is_e5
            break

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# 本机 CA 证书链被代理中断（与采集脚本同因），HF Hub 下载走
# requests/httpx 两条路径，统一全局关闭校验；生产环境必须恢复。
ssl._create_default_https_context = ssl._create_unverified_context

try:  # huggingface_hub 底层使用 httpx，其 Client 构造函数接受 verify 参数
    import httpx

    _orig_init = httpx.Client.__init__

    def _insecure_client_init(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        _orig_init(self, *args, **kwargs)

    httpx.Client.__init__ = _insecure_client_init
except ImportError:
    pass

_model = None  # 惰性加载：BM25-only 部署无需安装/导入 torch（省 ~200MB 内存）
_LOAD_ERROR: str | None = None


def get_model() -> SentenceTransformer:
    global _model, _LOAD_ERROR
    if _model is None:
        if _LOAD_ERROR:
            raise RuntimeError(_LOAD_ERROR)  # 会话内失败过一次不再重试
        try:
            from sentence_transformers import SentenceTransformer

            # 本地目录（data/models/<名>）存在则离线加载；
            # 否则 _MODEL_DIR 是完整 HF repo id，SentenceTransformer 自动从 Hub 下载
            local_dir = os.path.join(_MODELS_ROOT, _MODEL_DIR.split("/")[-1])
            model_path = local_dir if os.path.isdir(local_dir) else _MODEL_DIR
            _model = SentenceTransformer(
                model_path,
                model_kwargs={"low_cpu_mem_usage": True},
            )
        except Exception as e:
            _LOAD_ERROR = f"{type(e).__name__}: {e}"
            raise
    return _model


def embedding_available() -> bool:
    """本地 embedding 是否可用（不可用时检索层降级为 BM25-only）。

    EMBED_DISABLED=1 显式禁用（低内存/页面文件受限机器）。
    """
    global _LOAD_ERROR
    if os.environ.get("EMBED_DISABLED") == "1":
        return False
    try:
        get_model()
        return True
    except Exception:
        return False


def _prefix(text: str, role: str) -> str:
    if not _IS_E5:
        return text
    return f"{role}: {text}"


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    docs = [_prefix(t, "passage") for t in texts]
    return get_model().encode(docs, batch_size=batch_size, show_progress_bar=False).tolist()


def embed_query(text: str) -> list[float]:
    return get_model().encode(
        [_prefix(text, "query")], show_progress_bar=False
    ).tolist()[0]
