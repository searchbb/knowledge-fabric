#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/mac/Downloads/code/knowledge-fabric/backend/scripts/wiki_intake"
PYTHON="${PYTHON:-python3}"
INTAKE_DIR="${INTAKE_DIR:-/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake}"
CLIPPINGS_ROOT="${CLIPPINGS_ROOT:-/Users/mac/Downloads/OB笔记/Clippings}"
WIKI_HUB="${WIKI_HUB:-/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub}"
AUTO_INTAKE_ADAPTER="${AUTO_INTAKE_ADAPTER:-chatgpt_app_attachment}"
export PATH="/Users/mac/.nvm/versions/node/v22.17.0/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOCK_DIR="$INTAKE_DIR/.auto_intake_tick.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "{\"ok\":true,\"status\":\"tick_already_running\",\"lock_dir\":\"$LOCK_DIR\"}"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$ROOT"

"$PYTHON" "$ROOT/scan_clippings.py" \
  --clippings-root "$CLIPPINGS_ROOT" \
  --intake-dir "$INTAKE_DIR"

"$PYTHON" "$ROOT/auto_intake_enqueue.py" \
  --intake-dir "$INTAKE_DIR"

"$PYTHON" "$ROOT/auto_intake_job_store.py" recover-stuck \
  --intake-dir "$INTAKE_DIR" \
  --stale-seconds "${AUTO_INTAKE_STALE_SECONDS:-1800}"

"$PYTHON" "$ROOT/auto_intake_fresh_runner.py" \
  --intake-dir "$INTAKE_DIR" \
  --wiki-hub "$WIKI_HUB" \
  --clippings-root "$CLIPPINGS_ROOT" \
  --adapter "$AUTO_INTAKE_ADAPTER"
