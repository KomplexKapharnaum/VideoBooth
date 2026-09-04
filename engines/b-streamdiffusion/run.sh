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
