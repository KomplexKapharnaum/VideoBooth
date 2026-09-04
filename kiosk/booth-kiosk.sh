#!/usr/bin/env bash
# booth-kiosk.sh — configure the HDMI output (portrait) and run Chromium (or Chrome) in kiosk mode
# on the engine's output page, forever (restarts the browser if it exits).
# Runs inside the kxkm graphical session (systemd user unit booth-kiosk.service).
set -uo pipefail
. "$(dirname "$0")/../setup/env.sh"
export DISPLAY=${DISPLAY:-:0}
CHROME=$(command -v chromium || command -v chromium-browser || command -v google-chrome-stable || command -v google-chrome || true)
[ -n "$CHROME" ] || { echo "no Chromium/Chrome (setup/02_root_prereqs.sh)"; exit 1; }
# The Chromium snap can only write inside $HOME/snap/chromium/… (and non-hidden $HOME paths),
# so the kiosk profile lives there; Chrome (deb) can use the repo's .state dir.
case "$CHROME" in
  */chromium*) PROFILE=$HOME/snap/chromium/common/booth-kiosk ;;
  *)           PROFILE=$BOOTH_STATE/chrome-kiosk ;;
esac
mkdir -p "$PROFILE"

# Display: no blanking, native mode (or KIOSK_MODE), portrait rotation.
xset s off; xset s noblank; xset -dpms 2>/dev/null || true
command -v gsettings >/dev/null && { gsettings set org.gnome.desktop.session idle-delay 0; gsettings set org.gnome.desktop.screensaver lock-enabled false; } 2>/dev/null || true
OUT=${KIOSK_OUTPUT:-$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')}
if [ -n "$OUT" ]; then
  if [ -n "$KIOSK_MODE" ]; then xrandr --output "$OUT" --mode "$KIOSK_MODE" --rotate "$KIOSK_ROTATE"; else xrandr --output "$OUT" --auto --rotate "$KIOSK_ROTATE"; fi
  echo "display $OUT: $(xrandr | awk -v o="$OUT" '$1==o{print $3, $4, $5}') rotate=$KIOSK_ROTATE"
fi
command -v unclutter >/dev/null && pgrep -x unclutter >/dev/null || unclutter --timeout 1 --fork 2>/dev/null || true

# Serve kiosk/www (the output-only page) on 127.0.0.1:$KIOSK_HTTP_PORT — the snap-confined
# browser cannot open files under /ai, and http://127.0.0.1 is a secure context for the camera.
if ! curl -fs -m 1 "http://127.0.0.1:$KIOSK_HTTP_PORT/" >/dev/null 2>&1; then
  python3 -m http.server "$KIOSK_HTTP_PORT" --bind 127.0.0.1 --directory "$BOOTH_HOME/kiosk/www" >> "$BOOTH_LOGS/kiosk-www.log" 2>&1 &
  WWW_PID=$!; trap 'kill $WWW_PID 2>/dev/null' EXIT
fi

# Chromium flags: kiosk + camera auto-grant (verified on Chrome 149, HNdi 2026-09-04) +
# DevTools port for tools/fps_probe.py. 127.0.0.1 is a secure context, getUserMedia works.
# --incognito: no session restore — a restart must not bring back the previous page as a
# second tab (a stale demo tab keeps its own stream and starves the engine's event loop).
while true; do
  rm -f "$PROFILE/SingletonLock" 2>/dev/null
  "$CHROME" --kiosk --incognito --start-fullscreen --window-position=0,0 --no-first-run --noerrdialogs \
    --disable-infobars --disable-session-crashed-bubble --disable-features=TranslateUI \
    --autoplay-policy=no-user-gesture-required --auto-accept-camera-and-microphone-capture \
    --overscroll-history-navigation=0 --check-for-update-interval=31536000 \
    --remote-debugging-port="$CDP_PORT" --user-data-dir="$PROFILE" "$KIOSK_URL" \
    >> "$BOOTH_LOGS/kiosk.log" 2>&1
  echo "browser exited ($?), restarting in 2 s" >> "$BOOTH_LOGS/kiosk.log"; sleep 2
done
