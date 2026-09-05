"""M2 · 索引构建入口：卡片 -> Chroma 向量库 + BM25 语料。

运行：python scripts/build_index.py [--rebuild]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.index import build_index  # noqa: E402

if __name__ == "__main__":
    build_index()
