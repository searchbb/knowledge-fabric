<div align="center">

# Knowledge Fabric

**A Knowledge Workspace for Research and Insight**

<em>面向研究与洞察的 AI 原生知识工作台</em>

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## ⚡ 项目概述

**Knowledge Fabric** 当前公开主线不是"仿真预测引擎"，而是一个 **文章 -> 图谱 -> 知识工作台** 的 AI 原生知识系统。

它关注的是：把长文、研究笔记、网页文章和 Markdown，整理成一个可持续治理的知识工作台，而不是一次性摘要。

核心目标：

- 把单篇文章变成可读、可检视的项目图谱
- 把项目内概念、主题、关系逐步沉淀成跨项目知识资产
- 给后续审核、主题治理、演化跟踪和自动处理留出稳定工作台

适合当前阶段的使用方式：

- 输入一篇文章或一份 Markdown
- 生成项目与图谱
- 在 Phase 2 工作台里查看文章图谱、候选概念、主题线索、跨文关系和自动处理状态

## ✨ 核心能力

- **文章导入**：支持 Markdown 和 URL 入队处理
- **图谱构建**：将文章整理成图谱、阅读骨架和项目状态
- **项目工作台**：围绕单个项目查看文章图谱、项目概念、主题线索、项目演化、项目审核
- **跨项目知识层**：查看概念注册表、主题枢纽、跨文关系
- **自动处理队列**：手动驱动 URL 抓取、构图和后续知识整理入口

## 🚧 当前开源状态（Phase 2 Preview）

当前仓库同时包含两套体验面：

- **Phase 2 知识工作台**：这是当前推荐的开源体验主线。重点在文章导入、图谱构建、知识工作台、概念/主题候选、跨文关系与自动处理队列。
- **Legacy 预测/仿真链路**：旧的 simulation / report / interaction 路径仍保留，用于兼容和对照，但不是本次开源预览版的主入口。

当前已可体验的内容：

- 导入文章或 Markdown，生成项目与图谱
- 进入 Phase 2 工作台查看文章图谱与阅读结果
- 通过自动处理队列手动驱动 URL 入队、抓取和构图
- 查看全局概念注册表、主题枢纽、跨文关系等新界面

当前仍属于 Preview / Prototype 的内容：

- `review` 仍是原型流程，不是完整审核闭环
- `evolution` 目前是项目内快照，不是完整历史时间轴
- 项目内 `concept/theme` 视图仍以候选和只读聚合为主，不应视为最终治理系统

## 🔄 当前推荐体验路径（Phase 2）

1. **导入文章**：上传 Markdown，或将 URL 加入自动处理队列
2. **图谱构建**：生成项目、图谱、阅读骨架与 Phase 2 工作台入口
3. **项目工作台**：在文章图谱、项目概念、主题线索、项目演化、项目审核之间切换
4. **跨项目治理**：查看概念注册表、主题枢纽、跨文关系与自动处理队列
5. **逐步治理**：对候选概念、主题和关系进行后续确认与整理

> 说明：旧的预测/仿真/报告路径仍在仓库中保留，但当前开源预览版更推荐从 Phase 2 工作台开始体验。

## 🚀 快速开始

### 一、源码部署（推荐）

#### 前置要求

| 工具 | 版本要求 | 安装命令 / 安装检查 |
|------|---------|---------------------|
| **Node.js** | 18+ | `node -v` ／ [下载](https://nodejs.org/) |
| **Python** | ≥3.11, ≤3.12 | `python3 --version` |
| **uv** | 最新版 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` ／ `uv --version` |
| **Neo4j** | 5.26+ | Docker 一键启动见下方；或用 [Neo4j Desktop](https://neo4j.com/download/) |

**启动一个本地 Neo4j（Docker 方式，最省事）：**

```bash
docker run -d \
  --name knowledge-fabric-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/graphiti123 \
  -v $HOME/neo4j-data:/data \
  neo4j:5.26
```

- 浏览器访问 `http://localhost:7474/` 做一次口令确认
- 配合 `.env` 里 `NEO4J_URI=bolt://localhost:7687 / NEO4J_USER=neo4j / NEO4J_PASSWORD=graphiti123`

#### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填入 LLM_API_KEY
```

**最小可运行 `.env` 示例：**

```env
# 核心 LLM（OpenAI 兼容；不想用 OpenAI 可换成任意兼容网关）
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Neo4j / Graphiti
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphiti123
```

其它如 `ZEP_API_KEY`、`DEEPSEEK_API_KEY`、`OBSIDIAN_VAULT_PATH`、`OPENCLAW_FETCH_SCRIPT_PATH` 均为可选项，完整说明见 [`.env.example`](./.env.example)。

#### 2. 安装依赖

```bash
# 一键安装所有依赖（根目录 + 前端 + 后端）
npm run setup:all
```

或者分步安装：

```bash
npm run setup          # Node 依赖（根目录 + 前端）
npm run setup:backend  # Python 依赖（uv sync，自动创建 .venv）
```

> 如果要使用"阅读视图截图"功能（`article_workspace_pipeline` 会调用 playwright 生成阅读视图 png），额外执行一次：
>
> ```bash
> cd backend && uv run playwright install chromium
> ```

#### 3. 启动服务

```bash
# 同时启动前后端（在项目根目录执行）
npm run dev
```

**服务地址：**
- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`

**推荐入口：**
- Phase 2 工作台总览：`http://localhost:3000/workspace/overview`
- 旧版首页 / legacy 入口：`http://localhost:3000/`

**单独启动：**

```bash
npm run backend   # 仅启动后端
npm run frontend  # 仅启动前端
```

#### 4. 首次启动验证路径

1. 访问 `http://localhost:3000/workspace/overview`，页面能加载说明前端 + `/api/*` 代理就绪
2. 如顶部出现 "Neo4j 未连接" 类提示，检查 `docker ps` 里 neo4j 容器是否在跑、`.env` 里的口令是否和容器一致
3. 打开"自动处理队列"或"文章导入"页面，粘贴一个微信 / 博客 URL 或上传一份 Markdown，观察图谱是否成功生成
4. 如 LLM 报 401 或 404，优先检查 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` 三个字段是否和你接入的网关匹配

### 二、Docker 部署

```bash
# 1. 配置环境变量（同源码部署）
cp .env.example .env

# 2. 本地 build + 启动
docker compose up -d --build
```

默认会读取根目录下的 `.env`，并映射端口 `3000（前端）/ 5001（后端）`。

当前 `docker-compose.yml` 只负责启动应用容器；**Neo4j 仍需你自行准备并通过环境变量连接**，可以照上面的 `docker run` 命令在宿主机起一个实例，再把 `NEO4J_URI` 指到 `host.docker.internal:7687`（macOS / Windows）或宿主机 IP（Linux）。

> 后续在 CI 发布 GHCR 镜像后，可以把 compose 里的 `build:` 换成 `image: ghcr.io/searchbb/knowledge-fabric:latest` 直接拉镜像。

## 🧪 运行测试

后端有一套 pytest 测试套件。默认运行：

```bash
cd backend
uv run pytest -q
```

部分测试需要真实的 Neo4j 与 LLM 在线调用（主要是 `test_graph_builder_normalization.py`、`test_theme_attach_detach_audit.py`、`test_e2e_registry_flows.py`、`test_evolution_log_api.py` 的一部分）。只跑**纯单测闭环**：

```bash
# 只跑不依赖外部服务的快速子集
uv run pytest -q --ignore=tests/test_graph_builder_normalization.py \
                 --ignore=tests/test_theme_attach_detach_audit.py \
                 --ignore=tests/test_e2e_registry_flows.py \
                 --ignore=tests/test_evolution_log_api.py
```

## 🛠 常见启动问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `npm run dev` 前端报 `port 3000 is already in use` | 3000 端口被占（别的 dev server / Docker） | 改 `frontend/vite.config.js` 的 `server.port`，同时在 `.env` 里设 `KNOWLEDGE_WORKSPACE_FRONTEND=http://localhost:<新端口>` |
| 后端报 `ModuleNotFoundError: graphiti_core` | Python 依赖没装 | 确认 `uv sync` 跑过；后端启动必须用 `uv run python run.py` 或激活 `backend/.venv`，不要用系统 `python3` |
| 后端连 Neo4j 报 `ServiceUnavailable` | Neo4j 没起 / 口令不匹配 | `docker ps \| grep neo4j`；必要时 `docker logs knowledge-fabric-neo4j` 看详情 |
| 阅读视图截图失败 `ERR_CONNECTION_REFUSED` | 前端没起在 3000，或 playwright 浏览器没装 | 确认 `npm run frontend` 已启；执行 `cd backend && uv run playwright install chromium` |
| LLM 调用 401 / 404 | `LLM_BASE_URL` / `LLM_MODEL_NAME` 与 key 不匹配 | 按你用的网关文档核对；OpenAI 官方就是 `https://api.openai.com/v1` + `gpt-4o-mini` |

## 🔁 启用 Legacy 仿真链路（可选）

`camel-oasis` / `camel-ai` 硬 pin 了一个与主链路冲突的 Neo4j 版本，所以它们**不在**主依赖里。

只有当你需要 legacy 仿真 / 报告能力（并且在 `.env` 里打开 `ENABLE_LEGACY_ZEP_SIMULATION=true`）时，才推荐在**独立虚拟环境**里单独安装：

```bash
python -m venv .venv-legacy
source .venv-legacy/bin/activate
pip install -r backend/requirements-legacy.txt
```

## ⚠️ 已知限制

- `review` 页面当前仍是 prototype，主要用于验证审核主链路
- `evolution` 页面当前展示的是项目内演化快照，不是完整历史时间轴
- 首页与历史入口仍带有 legacy 流程痕迹，Phase 2 尚未完全接管所有主入口
- 部分后端测试依赖真实 Neo4j / 真实 LLM；默认 `uv run pytest` 会有 10+ 个 test（集中在 `test_graph_builder_normalization.py` / `test_theme_attach_detach_audit.py` 等）标红，是预期内的"需要外部环境"行为

## 📬 社区与反馈

- 欢迎直接通过 GitHub Issues / PR 反馈问题与改进建议

## 📄 致谢

Knowledge Fabric 的部分 legacy 仿真能力由 **[OASIS](https://github.com/camel-ai/oasis)** 驱动；当前 Phase 2 工作台能力继续围绕本地图谱（Graphiti + Neo4j）、知识治理与工作台体验演进。
