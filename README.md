# Poke-RAG · 宝可梦对战知识库问答

基于 RAG 的宝可梦对战问答系统。覆盖图鉴、招式、特性、道具、属性克制、对战环境、
伤害计算，以及官方对战游戏《宝可梦冠军》（Pokémon Champions）的机制与规则集；
用户未指明游戏时，默认按《宝可梦冠军》环境回答。数据来自 PokeAPI、
Pokémon Showdown、Smogon 与官方公开资料，回答带引用、可溯源。

## 在线演示

**http://139.155.157.248:8501**

打开即可提问，站点提供免费模型额度，无需注册。API Key 只在服务器内存中用于本次
会话调用，不写盘、不入日志、不下发浏览器。主模型繁忙时自动切换备用模型。
演示服务器为免费试用，过期后可按下文自行部署。

## 功能

- 知识库问答：4,500+ 知识卡片（宝可梦 / 招式 / 特性 / 道具 / Mega 与地区形态 /
  对战环境 / 《宝可梦冠军》机制），12,000+ 中英别名，口语化提问可命中
- 《宝可梦冠军》环境：个体值取消、努力值 66 点制、规则集时间线
  （M-A / M-B / M-C）、可用名单、道具池、Mega 进化与赛事规则
- 伤害问答：直接问「快龙用龙爪打喷火龙多少血」——规则引擎按主线公式计算
  （与 @smogon/calc 对拍 86/86 一致），输出伤害范围、一击击杀概率与极端情况分析
- 确定性查询走规则引擎：属性克制攻防双向查表、可学招式列表，不经过大模型
- 回答可信：引用编号可点击跳转来源页面；检索置信度不足时明确拒答

## 检索与生成

```
查询 → 查询改写（术语表 + 别名扩展）
     → BM25（jieba 自定义词典）+ 稠密向量（可选，远程 embedding）
     → RRF 融合 → Top-K 卡片 → 流式生成 → 引用校验 / 拒答兜底
```

78 问检索评测 top-3 命中 99%；低配服务器可只跑 BM25，零外部依赖。

## 快速开始

```bash
pip install -r requirements.txt

# 数据（原始数据不入 git，可一键重建）
python scripts/fetch_pokeapi.py
node scripts/fetch_showdown.mjs
python scripts/fetch_smogon.py
python scripts/build_cards.py
python scripts/build_index.py

# 启动（后端 8765 + 界面 8501）
python scripts/serve.py
python -m streamlit run scripts/serve_ui.py --server.port=8501
```

模型配置二选一：界面「模型设置」页填入 base_url / API Key / 模型名；或编辑
`config.local.json`（格式见 `config.example.json`）。支持智谱、DeepSeek、百炼、
混元、硅基流动等 OpenAI 兼容接口，内置免费方案预设。

低内存服务器（512MB~2GB）用单进程版，默认 BM25 检索：

```bash
pip install -r requirements-render.txt
EMBED_DISABLED=1 streamlit run app_render.py --server.port 8501 --server.address 0.0.0.0
```

## 云端部署

```bash
python scripts/deploy_tencent.py --host <服务器IP> --password <密码>
```

一条命令完成代码上传、依赖安装与 systemd 服务注册（崩溃自动重启、开机自启）。
模型 Key 经参数写入服务器 systemd（权限 600），不进仓库。仓库同时提供
Render 蓝图（`render.yaml`）与 HuggingFace Space 版（`app.py`）。

## 数据更新

```bash
python scripts/update_data.py              # 增量更新（约 2-5 分钟）
python scripts/update_data.py --full       # 全量重拉（约 30 分钟）
python scripts/update_data.py --index-only # 只重建索引
```

## 测试

```bash
python -m pytest tests/                    # 单元测试（含 UI 冒烟）
python scripts/verify_damage.py            # 伤害引擎对拍（@smogon/calc，86/86）
python scripts/eval_retrieval.py           # 检索评测（78 问）
```

## 目录结构

```
app.py                  Gradio 版（HF Space）
app_render.py           单进程 Streamlit 版（低内存服务器）
scripts/serve.py        本地完整版后端（FastAPI :8765）
scripts/serve_ui.py     本地完整版界面（Streamlit :8501）
src/pipeline/           数据流水线：抓取 → 清洗 → 知识卡片 → 别名 → 索引
src/retrieval/          BM25 / 稠密向量 / RRF 融合 / 查询改写
src/generation/         RAG 引擎 / 提示词 / 引用校验 / 流式输出
src/rules/              规则引擎：伤害计算 / 克制查表 / 招式查询
src/api/                FastAPI（SSE 流式）
src/ui/                 深色主题与样式注入
data/cards/             知识卡片（入 git，可直接用）
data/index/             BM25 索引（入 git）
tests/                  单元测试 + UI 冒烟
```

## 文档

[技术方案](docs/00-技术方案.md) · [数据源与调研](docs/01-数据源与开源借鉴调研.md) ·
[数据清单](docs/03-M0-数据清单报告.md) · [使用说明](docs/09-使用说明.md)

## 数据来源与许可

- PokeAPI（BSD-3-Clause）
- Pokémon Showdown（MIT）
- Smogon（公开统计，www.smogon.com）
- 《宝可梦冠军》资料整理自官方公开页面（champions.pokemon.com）及
  Serebii、Victory Road、IGN 等社区资料

本项目用于学习与演示，与 Nintendo / The Pokémon Company 无关联。
