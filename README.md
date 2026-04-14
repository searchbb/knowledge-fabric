<div align="center">

# Knowledge Fabric

**A Knowledge Workspace for Research and Insight**

<em>面向研究与洞察的 AI 原生知识工作台</em>

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## ⚡ 项目概述

**Knowledge Fabric** 当前公开主线不是“仿真预测引擎”，而是一个 **文章 -> 图谱 -> 知识工作台** 的 AI 原生知识系统。

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

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|---------|------|---------|
| **Node.js** | 18+ | 前端运行环境，包含 npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | 后端运行环境 | `python --version` |
| **uv** | 最新版 | Python 包管理器 | `uv --version` |
| **Neo4j** | 5+ | Graphiti 本地图数据库 | `neo4j --version` 或确认本地实例可连接 |

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入必要的 API 密钥
```

**必需的环境变量：**

```env
# 基础 LLM（OpenAI 兼容）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Neo4j / Graphiti
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

`ZEP_API_KEY`、`DEEPSEEK_API_KEY`、`OBSIDIAN_VAULT_PATH`、`OPENCLAW_FETCH_SCRIPT_PATH` 等配置都属于可选项；具体见 [`.env.example`](./.env.example)。

#### 2. 安装依赖

```bash
# 一键安装所有依赖（根目录 + 前端 + 后端）
npm run setup:all
```

或者分步安装：

```bash
# 安装 Node 依赖（根目录 + 前端）
npm run setup

# 安装 Python 依赖（后端，自动创建虚拟环境）
npm run setup:backend
```

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
- 旧版首页/legacy 入口：`http://localhost:3000/`

**单独启动：**

```bash
npm run backend   # 仅启动后端
npm run frontend  # 仅启动前端
```

### 二、Docker 部署

```bash
# 1. 配置环境变量（同源码部署）
cp .env.example .env

# 2. 拉取镜像并启动
docker compose up -d
```

默认会读取根目录下的 `.env`，并映射端口 `3000（前端）/5001（后端）`。

当前 `docker-compose.yml` 只负责启动应用容器；**Neo4j 仍需你自行准备并通过环境变量连接**。

> 在 `docker-compose.yml` 中已通过注释提供加速镜像地址，可按需替换

## ⚠️ 已知限制

- `review` 页面当前仍是 prototype，主要用于验证审核主链路
- `evolution` 页面当前展示的是项目内演化快照，不是完整历史时间轴
- 首页与历史入口仍带有 legacy 流程痕迹，Phase 2 尚未完全接管所有主入口
- 部分后端测试依赖额外本地服务或可选依赖；对外发布时建议优先以最小可运行路径为准

## 📬 社区与反馈

- 欢迎直接通过 GitHub Issues / PR 反馈问题与改进建议

## 📄 致谢

Knowledge Fabric 的部分 legacy 仿真能力由 **[OASIS](https://github.com/camel-ai/oasis)** 驱动；当前 Phase 2 工作台能力继续围绕本地图谱、知识治理与工作台体验演进。
