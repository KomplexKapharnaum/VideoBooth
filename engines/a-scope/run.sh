#!/usr/bin/env bash
# run.sh — start Scope (Engine A). UI on http://<host>:8000. Ctrl-C stops.
set -euo pipefail
. "$(dirname "$0")/../../setup/env.sh"
[ -d "$SCOPE_DIR" ] || { echo "not installed: setup/20_engine_a.sh"; exit 1; }
cd "$SCOPE_DIR"
echo "scope @ $(git rev-parse --short HEAD) — first run downloads > 10 GB of weights (ask first)"
# --host 0.0.0.0: default binds 127.0.0.1 only (technician laptop could not reach it);
# -N: never pop a browser window in the kiosk session. Other flags: uv run daydream-scope --help
exec uv run daydream-scope --host 0.0.0.0 --port "$SCOPE_PORT" -N "$@"
