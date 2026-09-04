#!/usr/bin/env bash
# 20_engine_a.sh — Engine A: Daydream Scope, Linux source install.
# User-level, idempotent. Follows docs.daydream.live/scope quickstart as read 2026-09-04:
#   requirements: NVIDIA ≥ 24 GB, CUDA 12.8+ driver, uv, Node.js + npm
#   git clone … && uv run build && uv run daydream-scope   → UI http://localhost:8000
# Model weights (Wan 2.1 1.3B pipelines, ~20 GB class) download on FIRST RUN into
# ~/.daydream-scope/models — that first run is the > 10 GB step: ask Thomas before it.
set -euo pipefail
. "$(dirname "$0")/env.sh"
command -v uv >/dev/null || { echo "uv missing"; exit 1; }
command -v npm >/dev/null || { echo "npm missing"; exit 1; }
nvidia-smi >/dev/null 2>&1 || { echo "nvidia-smi fails — run setup/01_driver_fix.sh + reboot first"; exit 1; }

if [ ! -d "$SCOPE_DIR/.git" ]; then git clone "$SCOPE_REPO" "$SCOPE_DIR"; fi
git -C "$SCOPE_DIR" fetch -q origin
git -C "$SCOPE_DIR" checkout -q "$SCOPE_REF"
[ "$SCOPE_REF" = main ] && git -C "$SCOPE_DIR" pull -q --ff-only origin main || true
echo "scope @ $(git -C "$SCOPE_DIR" rev-parse --short HEAD)"

cd "$SCOPE_DIR"
uv run build
echo "OK. Start with: $BOOTH_HOME/engines/a-scope/run.sh   (UI http://<host>:$SCOPE_PORT)"
echo "First start downloads the pipeline weights (> 10 GB) — confirm with Thomas first."
