#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/mac/Downloads/code/knowledge-fabric/backend/scripts/wiki_intake"
LABEL="com.codex.kfc-wiki-intake"
HOST="${CLIPPINGS_INTAKE_HOST:-127.0.0.1}"
PORT="${CLIPPINGS_INTAKE_PORT:-8765}"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
CLIPPINGS_ROOT="${CLIPPINGS_ROOT:-/Users/mac/Downloads/OB笔记/Clippings}"
INTAKE_DIR="${INTAKE_DIR:-/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_intake}"
WIKI_HUB="${WIKI_HUB:-/Users/mac/Downloads/code/knowledge-fabric/backend/data/wiki_hub}"
SOURCE_DIGEST_MODE="${SOURCE_DIGEST_MODE:-auto}"
DECISION_DIGEST_MODE="${DECISION_DIGEST_MODE:-auto}"
CODEX_BIN="${CODEX_BIN:-/opt/homebrew/bin/codex}"
STDOUT_LOG="${CLIPPINGS_INTAKE_STDOUT:-/tmp/clippings-intake.out}"
STDERR_LOG="${CLIPPINGS_INTAKE_STDERR:-/tmp/clippings-intake.err}"

launchctl remove "$LABEL" >/dev/null 2>&1 || true
: > "$STDOUT_LOG"
: > "$STDERR_LOG"

launchctl submit \
  -l "$LABEL" \
  -o "$STDOUT_LOG" \
  -e "$STDERR_LOG" \
  -- /usr/bin/env "PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" "SOURCE_DIGEST_MODE=$SOURCE_DIGEST_MODE" "DECISION_DIGEST_MODE=$DECISION_DIGEST_MODE" "CODEX_BIN=$CODEX_BIN" "$PYTHON" -u "$ROOT/server.py" \
    --host "$HOST" \
    --port "$PORT" \
    --clippings-root "$CLIPPINGS_ROOT" \
    --intake-dir "$INTAKE_DIR" \
    --wiki-hub "$WIKI_HUB"

health_url="http://$HOST:$PORT/api/health"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 "$health_url" >/tmp/clippings-intake-health.json 2>/dev/null; then
    pid="$(launchctl list | awk -v label="$LABEL" '$3 == label { print $1 }')"
    {
      echo "ok: true"
      echo "url: http://$HOST:$PORT/index.html"
      echo "label: $LABEL"
      echo "pid: ${pid:-unknown}"
      echo "source_digest_mode: $SOURCE_DIGEST_MODE"
      echo "decision_digest_mode: $DECISION_DIGEST_MODE"
      echo "codex_bin: $CODEX_BIN"
      echo "stdout_log: $STDOUT_LOG"
      echo "stderr_log: $STDERR_LOG"
      echo "health:"
      cat /tmp/clippings-intake-health.json
      echo
    }
    exit 0
  fi
  sleep 0.5
done

echo "ok: false" >&2
echo "health check failed: $health_url" >&2
echo "stdout log:" >&2
cat "$STDOUT_LOG" >&2 || true
echo "stderr log:" >&2
cat "$STDERR_LOG" >&2 || true
exit 1
