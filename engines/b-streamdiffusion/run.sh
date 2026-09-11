#!/usr/bin/env bash
# run.sh — start the StreamDiffusion realtime-img2img demo (Engine B) with the booth config.
# UI on http://<host>:7860. Extra args are passed to main.py (see --help). Ctrl-C stops.
#
# The demo does NOT load --controlnet-config into its state at startup (that flag is only a
# base path for relative files); it applies a config through POST /api/controlnet/upload-config.
# So: start the server, wait for HTTP, upload $SD_CONFIG, then keep the server in the foreground.
# --timeout 0: the demo's websocket loop never refreshes its last_time, so any positive
# timeout ends every session after that many seconds — fatal for a show.
set -uo pipefail
. "$(dirname "$0")/../../setup/env.sh"
[ -x "$SD_DIR/.venv/bin/python" ] || { echo "not installed: setup/10_engine_b.sh"; exit 1; }
cd "$SD_DIR/demo/realtime-img2img"
# polygraphy (TensorRT path) dlopens the UNVERSIONED libcudart.so. kxkm-ai had it from the
# Ubuntu nvidia-cuda-toolkit package (CUDA 12.0) — an undeclared dependency found on kxkm-ai2
# 2026-09-11 ("Acceleration has failed" / OSError: libcudart.so). The venv already ships
# libcudart.so.12 with torch cu128: expose it under the bare name and put it on the path.
CUDART_DIR=$(ls -d "$SD_DIR"/.venv/lib/python*/site-packages/nvidia/cuda_runtime/lib 2>/dev/null | head -1)
if [ -n "$CUDART_DIR" ]; then
  [ -e "$CUDART_DIR/libcudart.so" ] || ln -s libcudart.so.12 "$CUDART_DIR/libcudart.so"
  export LD_LIBRARY_PATH="$CUDART_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
echo "StreamDiffusion @ $(git -C "$SD_DIR" rev-parse --short HEAD) — config $SD_CONFIG"
"$SD_DIR/.venv/bin/python" main.py --acceleration tensorrt --controlnet-config "$SD_CONFIG" \
  --host 0.0.0.0 --port "$SD_PORT" --engine-dir "$SD_TRT_ENGINES" --timeout 0 "$@" &
PID=$!
trap 'kill -TERM $PID 2>/dev/null' INT TERM
for _ in $(seq 90); do
  curl -fs -m 3 "http://127.0.0.1:$SD_PORT/api/settings" >/dev/null 2>&1 && break
  kill -0 $PID 2>/dev/null || { echo "server exited during startup"; exit 1; }
  sleep 2
done
"$BOOTH_HOME/engines/b-streamdiffusion/apply_config.sh" "$SD_CONFIG" || echo "WARN: config upload failed — the server runs with the demo defaults (sd-turbo, no ControlNet)"
wait $PID
