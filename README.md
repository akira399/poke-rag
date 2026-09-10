# Poke-RAG · 宝可梦对战知识库问答系统

基于 RAG 的宝可梦对战知识库问答系统：覆盖图鉴、招式、特性、道具、属性克制、
对战环境（Meta）与伤害计算。数据来自权威开源数据源（PokeAPI / Pokémon
Showdown / Smogon），回答可溯源、效果可量化评测。

## 功能

- **知识库问答**：图鉴 / 招式 / 特性 / 道具 / 属性克制 / 对战环境，回答带引用溯源，低置信度拒答
- **规则引擎**：属性克制查表、伤害计算（与官方 @smogon/calc 对拍一致）、招式集合查询（所有/变化招式）
- **伤害问答**：直接问「A 用 B 打 C 多少血」——自动解析实体、计算伤害范围与击杀概率；信息不足时逐项追问缺失参数
- **评测闭环**：78 问检索评测 top-3 99%、消融实验、官方对拍 86/86
- **模型可配置**：OpenAI 兼容协议，界面填 base_url / api_key / model
- **本地化**：官方简体中文名 + 补丁表

## 架构

```
Streamlit（问答 / 检索调试 / 伤害计算器 / 模型设置）
   ↓ HTTP + SSE
FastAPI（/api/chat /api/search /api/settings /api/health）
   ↓
Router（意图路由：工具路径[规则引擎] / 知识路径[检索→生成]）
   ↓
知识卡片（Chroma 向量库[可选] + BM25 索引 + 查询改写）
```

## 快速开始

```bash
# 依赖（Python 3.12+）
pip install -r requirements.txt

# 数据（脚本可一键重建 data/，不入 git）
python scripts/fetch_pokeapi.py
node scripts/fetch_showdown.mjs
python scripts/fetch_smogon.py
python scripts/build_cards.py
python scripts/build_index.py

# 启动（后端 8765 + 界面 8501）
python scripts/serve.py
python -m streamlit run scripts/serve_ui.py --server.port=8501
```

配置模型：编辑 `config.local.json`（gitignore）或在界面「模型设置」页填写。

## 更新数据

数据是可重建资产，随时可更新（官方规则数据每周有调整、环境榜每月更新）：

```bash
python scripts/update_data.py              # 增量更新（约 2-5 分钟）
python scripts/update_data.py --index-only # 只重建索引（改代码后用）
python scripts/update_data.py --full       # 含 PokeAPI 全量重拉（约 30 分钟）
python scripts/update_data.py --only smogon  # 只更新指定数据源
```

更新后需重启运行中的服务（serve.py / streamlit）以加载新数据。

## 评测

```bash
python scripts/eval_retrieval.py     # 78 问检索评测
python scripts/ablation.py           # 消融实验（查询改写开关）
python scripts/verify_damage.py      # 伤害引擎对拍（官方 @smogon/calc）
python -m pytest tests/              # 单元测试
```

## 文档

[技术方案](docs/00-技术方案.md) · [数据源与调研](docs/01-数据源与开源借鉴调研.md) ·
[数据清单](docs/03-M0-数据清单报告.md) · [使用说明](docs/09-使用说明.md)

## 数据来源与许可

- PokeAPI（BSD-3-Clause）
- Pokémon Showdown（MIT）
- Smogon（公开统计，www.smogon.com）

本项目为教学与演示用途，与任天堂（Nintendo）及宝可梦公司无关联。
