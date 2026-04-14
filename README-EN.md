<div align="center">

# Knowledge Fabric

**A Knowledge Workspace for Research and Insight**

<em>Turn articles, research notes, and Markdown into reusable knowledge assets.</em>

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## ⚡ Overview

**Knowledge Fabric** is currently being open-sourced primarily as an **article -> graph -> knowledge workspace** system rather than as a simulation-first product.

The core idea is to turn long-form articles, notes, and Markdown files into reusable knowledge assets instead of one-off summaries.

Current goals:

- turn a single article into a readable project graph
- gradually promote project-level concepts, themes, and relations into cross-project knowledge assets
- provide a stable workspace for review, governance, evolution tracking, and automation

Recommended usage today:

- input an article URL or a Markdown file
- build a project and graph
- inspect the Phase 2 workspace for article graph, concept/theme candidates, cross-article relations, and auto-pipeline status

## ✨ Core Capabilities

- **Article ingestion**: import Markdown directly or enqueue URLs
- **Graph building**: create project graphs, reading structure, and workspace state
- **Project workspace**: inspect article graph, project concepts, theme signals, evolution, and review
- **Cross-project knowledge layer**: browse the registry, theme hub, and cross-article relations
- **Auto pipeline queue**: manually drive URL fetching, graph building, and follow-up knowledge processing

## 🚧 Current Open-Source Status (Phase 2 Preview)

This repository currently contains two product surfaces:

- **Phase 2 Knowledge Workspace**: the recommended open-source entry point today. It focuses on article ingestion, graph building, the new workspace, concept/theme candidates, cross-article relations, and the auto pipeline queue.
- **Legacy prediction/simulation flow**: the older simulation / report / interaction routes are still present for compatibility and comparison, but they are not the primary path for this preview release.

What is already usable:

- Import an article or Markdown and generate a project + graph
- Open the Phase 2 workspace and inspect article graph / reading output
- Use the auto pipeline queue as a manual entry point for URL ingestion
- Explore the global registry, theme hub, and cross-article relation views

What is still preview / prototype:

- `review` is still a prototype flow, not a full review/approval loop
- `evolution` is currently a per-project snapshot, not a full historical timeline
- project-level `concept/theme` views are still mostly candidate/read-only aggregations, not a finished governance system

## 🔄 Recommended Preview Flow (Phase 2)

1. **Import content**: upload Markdown or add a URL into the auto pipeline queue
2. **Build the graph**: create a project, graph, reading structure, and Phase 2 workspace entry
3. **Use the project workspace**: switch between article graph, project concepts, theme signals, evolution, and review
4. **Move into cross-project governance**: inspect the registry, theme hub, cross-article relations, and auto pipeline
5. **Iterate on governance**: review and refine candidate concepts, themes, and relations

> Note: the older prediction / simulation / reporting surfaces are still included in the repo, but the recommended open-source preview path starts from the Phase 2 workspace.

## 🚀 Quick Start

### Option 1: Source Code Deployment (Recommended)

#### Prerequisites

| Tool | Version | Description | Check Installation |
|------|---------|-------------|-------------------|
| **Node.js** | 18+ | Frontend runtime, includes npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | Backend runtime | `python --version` |
| **uv** | Latest | Python package manager | `uv --version` |
| **Neo4j** | 5+ | Local database for Graphiti | `neo4j --version` or verify a reachable local instance |

#### 1. Configure Environment Variables

```bash
# Copy the example configuration file
cp .env.example .env

# Edit the .env file and fill in the required API keys
```

**Required Environment Variables:**

```env
# Core LLM (OpenAI-compatible)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Neo4j / Graphiti
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

`ZEP_API_KEY`, `DEEPSEEK_API_KEY`, `OBSIDIAN_VAULT_PATH`, and `OPENCLAW_FETCH_SCRIPT_PATH` are optional. See [`.env.example`](./.env.example) for the current template.

#### 2. Install Dependencies

```bash
# One-click installation of all dependencies (root + frontend + backend)
npm run setup:all
```

Or install step by step:

```bash
# Install Node dependencies (root + frontend)
npm run setup

# Install Python dependencies (backend, auto-creates virtual environment)
npm run setup:backend
```

#### 3. Start Services

```bash
# Start both frontend and backend (run from project root)
npm run dev
```

**Service URLs:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

**Recommended entry points:**
- Phase 2 workspace overview: `http://localhost:3000/workspace/overview`
- Legacy home / compatibility entry: `http://localhost:3000/`

**Start Individually:**

```bash
npm run backend   # Start backend only
npm run frontend  # Start frontend only
```

### Option 2: Docker Deployment

```bash
# 1. Configure environment variables (same as source deployment)
cp .env.example .env

# 2. Pull image and start
docker compose up -d
```

Reads `.env` from root directory by default and maps ports `3000 (frontend) / 5001 (backend)`.

The current `docker-compose.yml` starts the app container only; **you still need to provide a reachable Neo4j instance via environment variables**.

> Mirror address for faster pulling is provided as comments in `docker-compose.yml`, replace if needed.

## ⚠️ Known Limitations

- `review` is still a prototype and should not be treated as a finished governance workflow
- `evolution` currently shows project-level readiness snapshots rather than a full historical timeline
- the home/history entry still carries legacy flow assumptions; Phase 2 has not fully replaced every primary entry yet
- some backend tests require optional local services or extra dependencies; for public release, prioritize the minimal runnable path first

## 📬 Community and Feedback

- Feedback via GitHub Issues / PRs is welcome

## 📄 Acknowledgments

Knowledge Fabric carries forward some legacy simulation capabilities powered by **[OASIS](https://github.com/camel-ai/oasis)**. The current Phase 2 workspace continues to evolve around local graph building, knowledge governance, and workspace UX.
