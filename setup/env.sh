# VideoBooth — single place for paths, ports and knobs. Sourced by every script.
# Override anything in $BOOTH_HOME/booth.conf (gitignored; see booth.conf.example).

BOOTH_HOME=${BOOTH_HOME:-/ai/VideoBooth}      # the repo clone on the booth machine
BOOTH_ENGINES=$BOOTH_HOME/.engines             # upstream checkouts + venvs (gitignored)
BOOTH_HF=$BOOTH_HOME/.hf                       # HuggingFace cache for the booth only
BOOTH_STATE=$BOOTH_HOME/.state                 # showmode state, chrome profile, logs
BOOTH_LOGS=$BOOTH_STATE/logs

# Engine B — StreamDiffusion (Daydream fork)
SD_REPO=https://github.com/daydreamlive/StreamDiffusion.git
SD_REF=${SD_REF:-main}                         # pin to the commit that passes the bench
SD_DIR=$BOOTH_ENGINES/StreamDiffusion
SD_PY=3.10                                     # the fork's demo requires 3.10
SD_TRT_ENGINES=$BOOTH_ENGINES/trt              # built TensorRT engines (size-specific)
SD_CONFIG=$BOOTH_HOME/engines/b-streamdiffusion/booth_sd15_depth.yaml
SD_PORT=7860

# Engine A — Daydream Scope
SCOPE_REPO=https://github.com/daydreamlive/scope.git
SCOPE_REF=${SCOPE_REF:-main}                   # pin to the commit that passes the bench
SCOPE_DIR=$BOOTH_ENGINES/scope
SCOPE_PORT=8000

# Camera / kiosk
CAMERA_DEV=${CAMERA_DEV:-/dev/video0}
KIOSK_HTTP_PORT=7861                           # kiosk/www served on 127.0.0.1 by booth-kiosk.sh (the snap browser cannot read /ai)
KIOSK_URL=${KIOSK_URL:-http://127.0.0.1:$KIOSK_HTTP_PORT/output.html?server=http://127.0.0.1:$SD_PORT}   # output-only page for Engine B; the panel rewrites it in booth.conf
# VIDEO SOURCE of the kiosk page: webcam (default, every boot) | ndi (HNdi's /dev/video10, a camera
# called "NDI" for Chrome). The panel switches it (booth.conf SOURCE=) and reloads the kiosk.
SOURCE=${SOURCE:-webcam}
WEBCAM_LABEL=${WEBCAM_LABEL:-}                 # substring of the USB camera's label for the kiosk's cam= (empty = first camera)
NDI_API=${NDI_API:-http://127.0.0.1:8791}      # HNdi input node on this box (setup/25_hndi.sh)
KIOSK_ROTATE=${KIOSK_ROTATE:-left}             # normal | left | right | inverted (xrandr)
KIOSK_MODE=${KIOSK_MODE:-}                     # e.g. 3840x2160 ; empty = panel native (--auto)
KIOSK_OUTPUT=${KIOSK_OUTPUT:-}                 # xrandr output name; empty = the connected output with the largest physical width (the TV)
KIOSK_TV_MIN_MM=${KIOSK_TV_MIN_MM:-900}        # rotate only a panel at least this wide (mm) — a control monitor stays landscape
KIOSK_ROTATE_ALWAYS=${KIOSK_ROTATE_ALWAYS:-0}  # 1 = rotate whatever output is picked (old behaviour)
KIOSK_LOCKED=${KIOSK_LOCKED:-0}                # 1 = Chromium --kiosk (locked); 0 = fullscreen at start, F11 toggles
CDP_PORT=${CDP_PORT:-9222}                        # Chrome DevTools port used by tools/fps_probe.py and the panel preview
PANEL_PORT=7870                                # technician panel (panel/server.py), LAN, no auth

export HF_HOME=$BOOTH_HF
export PATH="$HOME/.local/bin:$PATH"           # uv lives there on kxkm-ai

[ -f "$BOOTH_HOME/booth.conf" ] && . "$BOOTH_HOME/booth.conf"
mkdir -p "$BOOTH_ENGINES" "$BOOTH_HF" "$BOOTH_STATE" "$BOOTH_LOGS" 2>/dev/null || true
