#!/usr/bin/env bash
# apply_config.sh [config.yaml] — (re)load the booth config into the RUNNING Engine B server.
# The demo applies a config only through POST /api/controlnet/upload-config (its
# --controlnet-config argument is just a base path for relative files): this uploads the
# yaml, which resets the app state from it and rebuilds the pipeline on the next stream
# request. Use it after editing the yaml — no server restart needed (TensorRT engines are
# rebuilt only if model/resolution changed).
set -euo pipefail
. "$(dirname "$0")/../../setup/env.sh"
CFG=${1:-$SD_CONFIG}
[ -f "$CFG" ] || { echo "no such config: $CFG"; exit 1; }
curl -fsS -m 30 -F "file=@$CFG" "http://127.0.0.1:$SD_PORT/api/controlnet/upload-config" \
  && echo && echo "applied: $CFG (pipeline rebuilds on the next stream)"
