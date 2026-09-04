#!/usr/bin/env bash
# run.sh — start Scope (Engine A). UI on http://<host>:8000. Ctrl-C stops.
set -euo pipefail
. "$(dirname "$0")/../../setup/env.sh"
[ -d "$SCOPE_DIR" ] || { echo "not installed: setup/20_engine_a.sh"; exit 1; }
cd "$SCOPE_DIR"
echo "scope @ $(git rev-parse --short HEAD) — first run downloads > 10 GB of weights (ask first)"
exec uv run daydream-scope "$@"   # flags: uv run daydream-scope --help
