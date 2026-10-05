#!/usr/bin/env bash
# 11_depth_engine.sh [--force] — the depth TensorRT engine ($DEPTH_ENGINE) that the yaml's
# depth_tensorrt preprocessor loads. User-level, idempotent; run by setup/10_engine_b.sh.
# Fetches the pinned Depth-Anything-V2-small ONNX into $DEPTH_ONNX (sha256-checked), then builds
# the engine with engines/b-streamdiffusion/build_depth_engine.py in the engine B venv.
# Skips when the engine already loads with this TensorRT + GPU, rebuilds when it does not (a
# TensorRT upgrade). --force rebuilds anyway; a failed build never replaces the old engine.
# Offline box: copy the .onnx to $DEPTH_ONNX (same sha256), or the .engine itself from a box
# with the same GPU + TensorRT version.
set -euo pipefail
. "$(dirname "$0")/env.sh"
FORCE=0; [ "${1:-}" = --force ] && FORCE=1
PY=$SD_DIR/.venv/bin/python
BUILD=$BOOTH_HOME/engines/b-streamdiffusion/build_depth_engine.py
[ -x "$PY" ] || { echo "engine B not installed: setup/10_engine_b.sh first"; exit 1; }
# the same CUDA runtime path run.sh gives the engine
CUDART_DIR=$(ls -d "$SD_DIR"/.venv/lib/python*/site-packages/nvidia/cuda_runtime/lib 2>/dev/null | head -1 || true)
if [ -n "$CUDART_DIR" ]; then export LD_LIBRARY_PATH="$CUDART_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; fi

if [ "$FORCE" = 0 ] && "$PY" "$BUILD" --check --out "$DEPTH_ENGINE"; then exit 0; fi

if [ -f "$DEPTH_ONNX" ]; then
  echo "$DEPTH_ONNX_SHA256  $DEPTH_ONNX" | sha256sum -c --status \
    || echo "WARN: $DEPTH_ONNX is not the pinned export (sha256 $DEPTH_ONNX_SHA256) — building from it anyway"
else
  mkdir -p "$(dirname "$DEPTH_ONNX")"
  echo "fetching $DEPTH_ONNX_URL"
  curl -fL --retry 3 -o "$DEPTH_ONNX.part" "$DEPTH_ONNX_URL" \
    || { echo "download failed (offline?) — copy the .onnx to $DEPTH_ONNX, sha256 $DEPTH_ONNX_SHA256"; exit 1; }
  echo "$DEPTH_ONNX_SHA256  $DEPTH_ONNX.part" | sha256sum -c --status \
    || { rm -f "$DEPTH_ONNX.part"; echo "sha256 mismatch on the download — not the pinned export"; exit 1; }
  mv "$DEPTH_ONNX.part" "$DEPTH_ONNX"
  echo "ok: $DEPTH_ONNX (sha256 checked)"
fi
"$PY" "$BUILD" --onnx "$DEPTH_ONNX" --out "$DEPTH_ENGINE"
"$PY" "$BUILD" --check --out "$DEPTH_ENGINE"
