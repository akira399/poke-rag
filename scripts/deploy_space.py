"""一键部署到 HuggingFace Space（Gradio SDK，免费账号可用）。

用法：
    python scripts/deploy_space.py --token hf_xxx [--repo siyixly/poke-rag] [--private]

流程：
  1. 组装 Space 内容到临时 staging 目录（app.py + src/ + 数据/索引 + Space README）；
  2. 用 HfApi 创建 Space（gradio SDK）并上传全部文件；
  3. 等待构建完成后访问 https://<repo 替换 / 为 />.hf.space

Space 内容说明：
  - app.py：Gradio 应用（会话级 API Key，用户自配）
  - data/cards + data/index：知识卡片与检索索引（本地预构建，含向量）
  - data/raw/showdown/json：规则数据（pokedata / typechart 运行时需要）
  - 模型（mE5-small）不进仓库：Space 首次启动自动从 HF Hub 下载（约 2 分钟）
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Space 版 requirements（锁兼容组合：gradio 5.x + hub 0.36 与 transformers 4.57 匹配；
# torch 走 CPU 源避免拉 CUDA 大包）
SPACE_REQUIREMENTS = """--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.6.0
gradio==5.49.1
huggingface_hub==0.36.2
sentence-transformers==5.7.0
transformers==4.57.6
accelerate==1.14.0
chromadb==1.5.9
rank-bm25==0.2.2
jieba==0.42.1
requests==2.34.2
numpy<3
"""

SPACE_README = """---
title: Poke-RAG 宝可梦对战知识库
emoji: 🧭
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.49.1"
app_file: app.py
pinned: false
license: mit
short_description: RAG 宝可梦对战问答：伤害计算/克制/Meta，引用可查证
---

{body}

> 本 Space 是 [Poke-RAG](https://github.com/akira399/poke-rag) 的在线演示。
> 首次使用请在「⚙️ 模型设置」填入你自己的 DeepSeek API Key（服务器不存储）。
> 数据来自 PokeAPI（BSD-3）、Pokémon Showdown（MIT）、Smogon，仅教学演示用途。
"""

COPY_DIRS = [
    "src",
    os.path.join("data", "cards"),
    os.path.join("data", "raw", "showdown", "json"),
    os.path.join("data", "index", "chroma"),   # 预构建向量索引（满血检索）
]
COPY_FILES = [
    "app.py",
    os.path.join("data", "index", "bm25.json"),
]
SKIP_TOP = {".venv", "node_modules", "__pycache__", ".git", "config.local.json"}


def assemble(staging: str) -> None:
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    for d in COPY_DIRS:
        src = os.path.join(ROOT, d)
        if not os.path.exists(src):
            print(f"⚠️ 跳过不存在的目录: {d}")
            continue
        dst = os.path.join(staging, d)
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_raw"))

    for f in COPY_FILES:
        src = os.path.join(ROOT, f)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(os.path.join(staging, f)), exist_ok=True)
            shutil.copy2(src, os.path.join(staging, f))

    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        body = fh.read()
    with open(os.path.join(staging, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(SPACE_README.format(body=body))
    with open(os.path.join(staging, "requirements.txt"), "w", encoding="utf-8") as fh:
        fh.write(SPACE_REQUIREMENTS)

    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(staging) for f in fs)
    print(f"staging 组装完成: {staging}（{total / 1024 / 1024:.1f} MB）")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--token", required=True, help="HF write token（hf_...）")
    ap.add_argument("--repo", default="siyixly/poke-rag", help="Space 仓库名")
    ap.add_argument("--private", action="store_true", help="私有 Space")
    ap.add_argument("--staging", default=os.path.join(tempfile.gettempdir(), "poke-rag-space"))
    args = ap.parse_args()

    assemble(args.staging)

    from huggingface_hub import HfApi

    api = HfApi(token=args.token)
    space_id = args.repo
    print(f"创建 Space: {space_id}（sdk=gradio, {'private' if args.private else 'public'}）")
    url = api.create_repo(
        repo_id=space_id, repo_type="space", space_sdk="gradio",
        private=args.private, exist_ok=True,
    )
    print("Space 地址:", getattr(url, "raw_url", url) if not isinstance(url, str) else url)

    print("上传文件（首次约 1-3 分钟，取决于网络）…")
    api.upload_folder(
        repo_id=space_id, repo_type="space",
        folder_path=args.staging, commit_message="Deploy Poke-RAG to Space",
    )
    print("✅ 上传完成，HF 正在自动构建。几分钟后访问：")
    print(f"   https://{space_id.replace('/', '-')}.hf.space")
    print("构建日志: https://huggingface.co/spaces/" + space_id + "/logs/build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
