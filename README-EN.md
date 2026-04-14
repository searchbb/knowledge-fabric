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

| Tool | Version | Install / Check |
|------|---------|-----------------|
| **Node.js** | 18+ | `node -v` / [download](https://nodejs.org/) |
| **Python** | ≥3.11, ≤3.12 | `python3 --version` |
| **uv** | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` / `uv --version` |
| **Neo4j** | 5.26+ | Docker one-liner below, or [Neo4j Desktop](https://neo4j.com/download/) |

**Run a local Neo4j via Docker (easiest):**

```bash
docker run -d \
  --name knowledge-fabric-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/graphiti123 \
  -v $HOME/neo4j-data:/data \
  neo4j:5.26
```

- Visit `http://localhost:7474/` once to confirm the password
- Keep `.env` aligned: `NEO4J_URI=bolt://localhost:7687 / NEO4J_USER=neo4j / NEO4J_PASSWORD=graphiti123`

#### 1. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env, at minimum set LLM_API_KEY
```

**Minimum viable `.env`:**

```env
# Core LLM (OpenAI-compatible — any compatible gateway works)
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Neo4j / Graphiti
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphiti123
```

`ZEP_API_KEY`, `DEEPSEEK_API_KEY`, `OBSIDIAN_VAULT_PATH`, and `OPENCLAW_FETCH_SCRIPT_PATH` are optional. See [`.env.example`](./.env.example) for the full template.

#### 2. Install Dependencies

```bash
# One-click install for root + frontend + backend
npm run setup:all
```

Or install step by step:

```bash
npm run setup          # Node deps (root + frontend)
npm run setup:backend  # Python deps (uv sync, creates .venv)
```

> If you plan to use the reading-view screenshot feature (the `article_workspace_pipeline` calls `playwright` to render the reading view to PNG), also run:
>
> ```bash
> cd backend && uv run playwright install chromium
> ```

#### 3. Start the Services

```bash
# Start both frontend and backend (from the project root)
npm run dev
```

**Service URLs:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

**Recommended entry points:**
- Phase 2 workspace overview: `http://localhost:3000/workspace/overview`
- Legacy home / compatibility entry: `http://localhost:3000/`

**Run individually:**

```bash
npm run backend   # backend only
npm run frontend  # frontend only
```

#### 4. First-Run Verification Path

1. Open `http://localhost:3000/workspace/overview` — if the page loads, the frontend + the `/api/*` proxy are wired.
2. If you see a "Neo4j not connected" warning, check `docker ps` for the Neo4j container and confirm the password in `.env`.
3. Try the "auto pipeline queue" or "article import" page: paste a WeChat / blog URL, or upload a Markdown file, and watch the graph build.
4. LLM returning 401 / 404? Double-check `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` against your gateway's docs.

### Option 2: Docker Deployment

```bash
# 1. Configure environment variables (same as source deployment)
cp .env.example .env

# 2. Local build + launch
docker compose up -d --build
```

Reads `.env` from the root directory by default and maps ports `3000 (frontend) / 5001 (backend)`.

The current `docker-compose.yml` only launches the app container — **you still need to provide a reachable Neo4j instance**. Use the `docker run` command above, then set `NEO4J_URI` to `host.docker.internal:7687` (macOS / Windows) or the host IP (Linux).

> Once a GHCR image is published by CI, you can swap the `build:` in `docker-compose.yml` for `image: ghcr.io/searchbb/knowledge-fabric:latest` to skip the local build.

## 🧪 Running Tests

The backend ships a pytest suite. Default run:

```bash
cd backend
uv run pytest -q
```

Some tests require a real Neo4j + live LLM (mostly in `test_graph_builder_normalization.py`, `test_theme_attach_detach_audit.py`, `test_e2e_registry_flows.py`, and parts of `test_evolution_log_api.py`). To run only the **pure unit tests**:

```bash
uv run pytest -q --ignore=tests/test_graph_builder_normalization.py \
                 --ignore=tests/test_theme_attach_detach_audit.py \
                 --ignore=tests/test_e2e_registry_flows.py \
                 --ignore=tests/test_evolution_log_api.py
```

## 🛠 Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `npm run dev` fails: `port 3000 is already in use` | Port 3000 taken (another dev server / Docker) | Change `server.port` in `frontend/vite.config.js` and set `KNOWLEDGE_WORKSPACE_FRONTEND=http://localhost:<new>` in `.env` |
| Backend `ModuleNotFoundError: graphiti_core` | Python deps missing | Make sure `uv sync` ran; start the backend with `uv run python run.py` (or activate `backend/.venv`) — do not use the system `python3` |
| Backend Neo4j `ServiceUnavailable` | Neo4j not running or password mismatch | `docker ps \| grep neo4j`; if needed `docker logs knowledge-fabric-neo4j` |
| Reading-view screenshot `ERR_CONNECTION_REFUSED` | Frontend not on 3000, or playwright browser not installed | Make sure `npm run frontend` is up; run `cd backend && uv run playwright install chromium` |
| LLM 401 / 404 | `LLM_BASE_URL` / `LLM_MODEL_NAME` mismatched with your key | Reconcile with your gateway's docs; OpenAI official is `https://api.openai.com/v1` + `gpt-4o-mini` |

## 🔁 Enabling Legacy Simulation (optional)

`camel-oasis` / `camel-ai` pin a Neo4j version that conflicts with the main pipeline, so they are **not** in the main dependencies.

Only if you need the legacy simulation / report capability (and set `ENABLE_LEGACY_ZEP_SIMULATION=true` in `.env`), install them in a **separate virtual environment**:

```bash
python -m venv .venv-legacy
source .venv-legacy/bin/activate
pip install -r backend/requirements-legacy.txt
```

## ⚠️ Known Limitations

- `review` is still a prototype and should not be treated as a finished governance workflow
- `evolution` currently shows project-level readiness snapshots rather than a full historical timeline
- the home / history entry still carries legacy flow assumptions; Phase 2 has not fully replaced every primary entry yet
- some backend tests expect a live Neo4j + live LLM; under a plain `uv run pytest` a dozen or so tests in `test_graph_builder_normalization.py` / `test_theme_attach_detach_audit.py` are expected to fail — this is the "requires external environment" contract

## 📬 Community & Feedback

- Feedback via GitHub Issues / PRs is welcome

## 📄 Acknowledgments

Knowledge Fabric carries forward some legacy simulation capabilities powered by **[OASIS](https://github.com/camel-ai/oasis)**. The current Phase 2 workspace continues to evolve around local graph building (Graphiti + Neo4j), knowledge governance, and workspace UX.
