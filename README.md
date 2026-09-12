# Poke-RAG · 宝可梦对战知识库问答系统

基于 RAG 的宝可梦对战知识库问答系统：覆盖图鉴、招式、特性、道具、属性克制、
对战环境（Meta）与伤害计算。数据来自权威开源数据源（PokeAPI / Pokémon
Showdown / Smogon），回答可溯源、效果可量化评测。

## 🌐 在线演示

**http://139.155.157.248:8501**

> 部署在腾讯云轻量应用服务器（免费试用）。首次使用请展开页面顶部
> **「⚙️ 模型配置」** 填入你自己的模型 API Key（推荐 DeepSeek，注册即送额度；
> 也支持通义 / Kimi / OpenAI 等任何 OpenAI 兼容服务）。Key 仅保存在你的浏览器
> 会话中，服务器不存储、不共享。
>
> 若演示地址过期（试用到期），可按下方「快速开始」或「云端部署」自行部署，
> 全程约 10 分钟。

### 🔒 隐私保护

本项目**不收集、不存储、不共享**任何用户数据：

- **API Key**：仅在服务器**内存**中用于本次会话调用你指定的模型——不写入磁盘、
  不记录日志、不上传任何第三方；会话结束（关闭页面后约 10 分钟）即从内存销毁；
- **对话内容**：同样只存在于服务器内存会话与你的浏览器中，刷新页面即清空；
- **可审计**：项目完全开源，数据流向见 `src/config.py`（配置加载）与
  `src/generation/llm.py`（模型调用），不含任何上报/遥测代码。

## ✨ 功能与特性

### 知识库问答
- **4,559+ 知识卡片**：宝可梦 1,025 / 招式 937 / 特性 374 / 道具 2,223，
  另含 194 张 Mega/地区形态卡片
- **12,000+ 别名表**：官方中英名、Showdown 民间译名（冷冻光线 = 冰冻光束、
  多鳞 = 多重鳞片），口语化提问也能命中
- **引用溯源**：回答中的 `[n]` 标记可点击展开对应知识片段并跳转来源页面查证
- **低置信度拒答**：检索结果置信度不足时明确拒答，不编造
- **过程透明**：路由 → 检索命中 → 模型思考链全程实时展示

### 规则引擎（确定性知识不走大模型）
- **伤害计算**：精确复刻 Gen9 官方公式（pokeRound / 定点 STAB / 16 档随机数），
  与官方 @smogon/calc **86/86 对拍完全一致（Δ=0）**
- **伤害问答**：直接问「快龙用龙爪打喷火龙多少血」——自动解析实体，输出伤害
  范围、占血比例、一击击杀概率，并给出**极端情况分析**（我方零投入 vs 满配置
  等三种情形下的"必杀/必不杀/看概率"判定）；信息不足时逐项列出缺失参数追问
- **属性克制**：攻防双向查表，防御矩阵与弱点文本
- **招式集合查询**：某宝可梦能学的所有招式 / 变化招式（learnsets 数据）

### 中文本地化
- 官方 zh-hans 名称对齐 + 规则化补丁表（形态后缀：超级进化X / 阿罗拉形态 /
  超极巨化…）+ 民间译名兜底，界面与回答全中文

### 检索架构（自研，非 LangChain 直拼）
```
查询 → 查询改写（术语表 + 别名扩展）
     → 混合召回：BM25（jieba 自定义词典）+ 稠密向量（可选，mE5-small）
     → RRF 融合排序 → Top-K 知识卡片 → 提示词组装 → 流式生成
```
- **78 问检索评测 top-3 99%**；消融实验：查询改写 +8%，稠密向量在小语料上
  收益为负（-3%），故生产默认 BM25-only——**每个开关都有评测数字支撑**
- 反幻觉四道闸：提示词约束 → 引用编号校验 → 检索置信度阈值 → 拒答兜底

## 🚀 快速开始（本地）

```bash
# 1. 依赖（Python 3.12+）
pip install -r requirements.txt

# 2. 数据（可一键重建，原始数据不入 git）
python scripts/fetch_pokeapi.py
node scripts/fetch_showdown.mjs
python scripts/fetch_smogon.py
python scripts/build_cards.py
python scripts/build_index.py

# 3. 启动（后端 8765 + 界面 8501）
python scripts/serve.py
python -m streamlit run scripts/serve_ui.py --server.port=8501
```

配置模型两种方式（二选一）：
- 界面「模型设置」页填 base_url / API Key / 模型名，保存即生效；
- 编辑 `config.local.json`（已 gitignore，格式见 `config.example.json`）。

### 低内存环境 / 单进程精简版

512MB~2GB 内存的服务器上，用单进程版（RAG 引擎内嵌，无 FastAPI 中转，
默认 BM25 检索）：

```bash
pip install -r requirements-render.txt
EMBED_DISABLED=1 LLM_MODEL=deepseek-flash \
  streamlit run app_render.py --server.port 8501 --server.address 0.0.0.0
```

## ☁️ 云端部署

### 方案 A：腾讯云轻量应用服务器（本项目的线上环境）

一台 Ubuntu 22.04 机器 + 一条命令完成部署（上传代码 → swap → venv →
systemd 服务 → 健康检查）：

```bash
python scripts/deploy_tencent.py --host <服务器IP> --password <密码>
```

服务由 systemd 守护：崩溃自动重启（Restart=always）、开机自启。需要：防火墙
放行 22 与 8501，用户名 `ubuntu`（轻量默认）。

### 方案 B：PaaS 容器平台（Render 等）

仓库已按容器化规范整理（依赖锁定、入口单文件、配置全走环境变量），
`render.yaml` 提供蓝图：构建 `pip install -r requirements-render.txt`，
启动 `streamlit run app_render.py --server.port $PORT --server.address 0.0.0.0`。

### 方案 C：HuggingFace Space

`app.py`（Gradio 版）+ `scripts/deploy_space.py` 一键创建并上传 Space。

## 🔄 更新数据

数据是可重建资产，随时可更新（官方规则数据每周有调整、环境榜每月更新）：

```bash
python scripts/update_data.py              # 增量更新（约 2-5 分钟）
python scripts/update_data.py --index-only # 只重建索引（改代码后用）
python scripts/update_data.py --full       # 含 PokeAPI 全量重拉（约 30 分钟）
python scripts/update_data.py --only smogon  # 只更新指定数据源
```

更新后需重启运行中的服务以加载新数据。

## 📊 评测

```bash
python scripts/eval_retrieval.py     # 78 问检索评测
python scripts/ablation.py           # 消融实验（查询改写/稠密向量开关）
python scripts/verify_damage.py      # 伤害引擎对拍（官方 @smogon/calc，86/86）
python -m pytest tests/              # 单元测试（96 项，含 UI 冒烟）
```

## 📁 目录结构

```
app.py                  Gradio 版（HF Space）
app_render.py           单进程 Streamlit 版（低内存服务器）
scripts/serve.py        本地完整版后端（FastAPI :8765）
scripts/serve_ui.py     本地完整版界面（Streamlit :8501）
src/pipeline/           数据流水线：抓取→清洗→知识卡片→别名→索引
src/retrieval/          BM25 / 稠密向量 / RRF 融合 / 查询改写
src/generation/         RAG 引擎 / 提示词 / 引用校验 / 流式输出
src/rules/              规则引擎：伤害计算 / 克制查表 / 招式查询
src/api/                FastAPI（SSE 流式）
src/ui/                 深色主题与样式注入
data/cards/             知识卡片（入 git，可直接用）
data/index/             BM25 索引（入 git）
data/raw/               原始数据（脚本重建，不入 git）
tests/                  96 项单元测试 + UI 冒烟（AppTest 真实渲染）
docs/                   技术方案 / 数据清单 / 使用说明
```

## 📄 文档

[技术方案](docs/00-技术方案.md) · [数据源与调研](docs/01-数据源与开源借鉴调研.md) ·
[数据清单](docs/03-M0-数据清单报告.md) · [使用说明](docs/09-使用说明.md)

## 🙏 数据来源与许可

- PokeAPI（BSD-3-Clause）
- Pokémon Showdown（MIT）
- Smogon（公开统计，www.smogon.com）

本项目为学习与演示用途，与任天堂（Nintendo）及宝可梦公司无关联。
