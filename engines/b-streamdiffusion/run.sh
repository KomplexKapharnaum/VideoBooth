#!/usr/bin/env bash
# run.sh — start the StreamDiffusion realtime-img2img demo with the booth config (Engine B).
# UI on http://<host>:7860. Extra args are passed to main.py (see --help).
set -euo pipefail
. "$(dirname "$0")/../../setup/env.sh"
[ -x "$SD_DIR/.venv/bin/python" ] || { echo "not installed: setup/10_engine_b.sh"; exit 1; }
cd "$SD_DIR/demo/realtime-img2img"
echo "StreamDiffusion @ $(git -C "$SD_DIR" rev-parse --short HEAD) — config $SD_CONFIG"
exec "$SD_DIR/.venv/bin/python" main.py --acceleration tensorrt --controlnet-config "$SD_CONFIG" \
  --host 0.0.0.0 --port "$SD_PORT" --engine-dir "$SD_TRT_ENGINES" "$@"
