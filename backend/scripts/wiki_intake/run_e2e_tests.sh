#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/mac/Downloads/code/knowledge-fabric/backend/scripts/wiki_intake"
NODE_BIN="${NODE_BIN:-/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
NODE_MODULES="${NODE_PATH:-/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules}"

cd "$ROOT"
NODE_PATH="$NODE_MODULES" "$NODE_BIN" "$ROOT/tests/e2e_clippings_intake.mjs"
