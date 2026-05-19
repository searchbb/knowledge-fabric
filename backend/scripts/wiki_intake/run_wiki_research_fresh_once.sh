#!/bin/zsh
set -euo pipefail

ROOT="/Users/mac/Downloads/code/knowledge-fabric/backend/scripts/wiki_intake"
LOG_DIR="/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake/research_runner_logs"
mkdir -p "$LOG_DIR"

export CODEX_BIN="${CODEX_BIN:-/opt/homebrew/bin/codex}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

exec /usr/bin/python3 "$ROOT/wiki_research_fresh_codex_runner.py" \
  --hub /Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub \
  --timeout-seconds "${WIKI_RESEARCH_TIMEOUT_SECONDS:-1800}" \
  >>"$LOG_DIR/fresh-runner.log" 2>>"$LOG_DIR/fresh-runner.err"
