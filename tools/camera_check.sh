#!/usr/bin/env bash
# camera_check.sh [/dev/videoN] [WxH] — formats, controls and REAL fps of the booth camera.
# Paste the output under "## Camera" in BENCHMARKS.md.
set -uo pipefail
. "$(dirname "$0")/../setup/env.sh"
DEV=${1:-$CAMERA_DEV}; SIZE=${2:-1920x1080}
echo "## Camera check — $DEV — $(date -Is)"; echo '```'
v4l2-ctl --list-devices 2>&1
echo "--- $DEV"; v4l2-ctl -d "$DEV" --info 2>&1 | grep -E "Driver name|Card type|Bus info"
v4l2-ctl -d "$DEV" --list-formats-ext 2>&1 | grep -E "^\s*\[|Size|Interval" | head -60
echo "--- controls of interest"; v4l2-ctl -d "$DEV" --list-ctrls 2>&1 | grep -E -i "exposure|focus|gain|white|power_line|zoom|brightness" 
W=${SIZE%x*}; H=${SIZE#*x}
for fmt in MJPG YUYV; do
  echo "--- real fps: $fmt $SIZE, 150 frames via v4l2-ctl"
  v4l2-ctl -d "$DEV" --set-fmt-video=width=$W,height=$H,pixelformat=$fmt --set-parm=30 >/dev/null 2>&1
  timeout -s INT 20 v4l2-ctl -d "$DEV" --stream-mmap=3 --stream-count=150 --stream-to=/dev/null 2>&1 | tail -1
done
if command -v ffmpeg >/dev/null; then
  echo "--- ffmpeg 10 s MJPEG $SIZE @30 (decode included)"
  timeout -s INT 25 ffmpeg -hide_banner -loglevel info -f v4l2 -input_format mjpeg -video_size "$SIZE" -framerate 30 -i "$DEV" -t 10 -f null - 2>&1 | grep -E "Stream #0:0|fps=" | tail -2
fi
echo '```'
