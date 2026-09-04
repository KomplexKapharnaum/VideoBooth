#!/usr/bin/env bash
# 10_engine_b.sh — Engine B: StreamDiffusion (Daydream fork) + TensorRT + realtime-img2img demo.
# User-level, idempotent. Commands follow the fork's README as read 2026-09-04:
#   python 3.10 · torch 2.8.0+cu128 · pip extras [tensorrt,controlnet,ipadapter]
#   · python -m streamdiffusion.tools.install-tensorrt · demo frontend npm build.
# Checkpoints download from HuggingFace on first run (SD1.5-LCM ≈ 2 GB, depth CN ≈ 1.4 GB)
# into $HF_HOME — well under the 10 GB ask-first threshold.
set -euo pipefail
. "$(dirname "$0")/env.sh"
command -v uv >/dev/null || { echo "uv missing (expected in ~/.local/bin)"; exit 1; }
command -v npm >/dev/null || { echo "npm missing"; exit 1; }

if [ ! -d "$SD_DIR/.git" ]; then git clone "$SD_REPO" "$SD_DIR"; fi
git -C "$SD_DIR" fetch -q origin
git -C "$SD_DIR" checkout -q "$SD_REF"
[ "$SD_REF" = main ] && git -C "$SD_DIR" pull -q --ff-only origin main || true
echo "StreamDiffusion @ $(git -C "$SD_DIR" rev-parse --short HEAD)"

cd "$SD_DIR"
[ -x .venv/bin/python ] || uv venv --python "$SD_PY" .venv
# shellcheck disable=SC1091
. .venv/bin/activate
uv pip install "torch==2.8.0" "torchvision==0.23.0" --index-url https://download.pytorch.org/whl/cu128
uv pip install -e ".[tensorrt,controlnet,ipadapter]"
python -m streamdiffusion.tools.install-tensorrt
python - <<'PY'
import torch, streamdiffusion
print("torch", torch.__version__, "cuda", torch.version.cuda, "gpu", torch.cuda.get_device_name(0))
import tensorrt; print("tensorrt", tensorrt.__version__)
PY

cd demo/realtime-img2img
uv pip install -r requirements.txt
( cd frontend && npm i --silent && npm run build --silent )
mkdir -p "$SD_TRT_ENGINES"
echo "OK. Start with: $BOOTH_HOME/engines/b-streamdiffusion/run.sh   (UI http://<host>:$SD_PORT)"
echo "First start builds the TensorRT engines for the sizes in $SD_CONFIG (several minutes)."
