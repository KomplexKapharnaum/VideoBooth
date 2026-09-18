#!/usr/bin/env bash
# 25_hndi.sh — HNdi input node on the booth box: an NDI stream becomes a camera called "NDI"
# (/dev/video10, v4l2loopback) that the kiosk Chromium can open like a webcam. Run as root once:
#   sudo setup/25_hndi.sh
# Then the panel's "Video source" section switches the kiosk between the USB webcam and NDI and
# picks the NDI stream; HNdi's own page (http://<box>:8791/) does the same without the panel.
# Env: HNDI_HOME (default /opt/HNdi) · HNDI_REPO (default https://github.com/Hemisphere-Project/HNdi.git)
#      GST_NDI_SO=/path/libgstndi.so (a prebuilt plugin for this GStreamer, skips the rust build)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root: sudo $0"; exit 1; }
. "$(dirname "$0")/env.sh"
HNDI_HOME="${HNDI_HOME:-/opt/HNdi}"; HNDI_REPO="${HNDI_REPO:-https://github.com/Hemisphere-Project/HNdi.git}"
OWNER="${SUDO_USER:-kxkm}"
if [ -d "$HNDI_HOME/.git" ]; then
  git -C "$HNDI_HOME" fetch -q origin main && git -C "$HNDI_HOME" merge -q --ff-only origin/main || echo "WARN: $HNDI_HOME not fast-forwarded — left as is"
else
  git clone -q "$HNDI_REPO" "$HNDI_HOME"
fi
echo "HNdi $(git -C "$HNDI_HOME" log --oneline -1)"
# HNdi's installer: NDI runtime, GStreamer NDI plugin, v4l2loopback (dkms) as /dev/video10 "NDI", service unit
DEV=10 "$HNDI_HOME/install.sh"
# the booth's hndi.conf: fixed 1080p caps (Chrome holds the device — the caps must not move), no
# auto-pick (the operator chooses), slate instead of black, API on the LAN for the panel/laptop
CONF=/boot/hndi.conf; [ -d /boot/firmware ] && CONF=/boot/firmware/hndi.conf
python3 - "$CONF" "$(hostname)" <<'PY'
import re, sys
p, host = sys.argv[1], sys.argv[2]
s = open(p).read()
def setk(section, key, val):
    global s
    if re.search(rf'^\s*{key}\s*=', s, re.M):
        s = re.sub(rf'^\s*{key}\s*=.*$', f'{key} = {val}', s, count=1, flags=re.M)
    else:
        s = re.sub(rf'^\[{section}\]\s*$', f'[{section}]\n{key} = {val}', s, count=1, flags=re.M)
for k, v in (('width', 1920), ('height', 1080), ('format', 'YUY2'), ('size', 'fixed'), ('autopick', 'false'),
             ('nosignal', 'slate'), ('api_bind', '0.0.0.0'), ('receiver_name', f'{host} (VideoBooth)'), ('profile', 'lowlatency')):
    setk('input', k, v)
open(p, 'w').write(s)
print('hndi.conf:', ', '.join(l.strip() for l in s.splitlines() if re.match(r'^(width|height|size|autopick|nosignal|api_bind|receiver_name)\s*=', l)))
PY
# The kiosk page picks its camera by label (cam=NDI). Chromium exposes camera labels and ids only
# to an origin whose camera permission is GRANTED; the kiosk's --auto-accept-camera-and-microphone-capture
# answers prompts but leaves the permission at 'prompt', so enumerateDevices() stays collapsed to
# one nameless placeholder and cam= can never match (kxkm-ai2 2026-09-18). A managed policy grants
# the kiosk origin for real. The Chromium snap reads /etc/chromium/policies/managed (and the deb
# /etc/chromium/policies/managed too); the JSON is harmless where nothing reads it.
KIOSK_ORIGIN="http://127.0.0.1:${KIOSK_HTTP_PORT:-7861}"
for d in /etc/chromium/policies/managed /etc/chromium-browser/policies/managed; do
  mkdir -p "$d"
  printf '{\n  "VideoCaptureAllowedUrls": ["%s"],\n  "AudioCaptureAllowedUrls": ["%s"]\n}\n' "$KIOSK_ORIGIN" "$KIOSK_ORIGIN" > "$d/videobooth-kiosk.json"
done
echo "kiosk camera policy: $KIOSK_ORIGIN granted (restart the kiosk to apply)"
# the kiosk user must read the loopback (Chrome opens it like a webcam)
id -nG "$OWNER" | grep -qw video || { usermod -aG video "$OWNER"; echo "added $OWNER to video (re-login / kiosk restart)"; }
systemctl daemon-reload; systemctl enable -q hndi-in; systemctl restart hndi-in; sleep 4
systemctl is-active hndi-in && v4l2-ctl -d /dev/video10 --info | grep -E "Card type|Driver name" || { echo "hndi-in did not come up: journalctl -u hndi-in"; exit 1; }
echo "done — panel: Video source → NDI · HNdi page: http://$(hostname -I | awk '{print $1}'):8791/"
