#!/usr/bin/env bash
# bench_browser.sh start|stop|status [url] — a HEADLESS Chromium that opens the camera and the
# engine page exactly like the kiosk does, but without a desk session (no X, no GDM login).
# Use it for the Phase 1 baselines when nobody is logged in on the box: tools/fps_probe.py and
# tools/cdp.py talk to it on the same DevTools port as the kiosk.
#   tools/bench_browser.sh start http://127.0.0.1:7860
#   tools/cdp.py --screenshot /tmp/bench.png     # what the page shows
#   tools/fps_probe.py --seconds 120 --label "B baseline"
#   tools/bench_browser.sh stop
# Not for shows: the kiosk unit (kiosk/) is the real display path.
set -uo pipefail
. "$(dirname "$0")/../setup/env.sh"
CHROME=$(command -v chromium || command -v chromium-browser || command -v google-chrome-stable || command -v google-chrome || true)
case "$CHROME" in */chromium*) PROFILE=$HOME/snap/chromium/common/booth-bench ;; *) PROFILE=$BOOTH_STATE/chrome-bench ;; esac
PIDF=$BOOTH_STATE/bench_browser.pid; LOG=$BOOTH_LOGS/bench_browser.log
W=${BENCH_W:-1080}; H=${BENCH_H:-1920}
case "${1:-status}" in
  start)
    URL=${2:-$KIOSK_URL}; [ -n "$CHROME" ] || { echo "no Chromium/Chrome"; exit 1; }
    [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null && { echo "already running (pid $(cat "$PIDF"))"; exit 0; }
    mkdir -p "$PROFILE"; rm -f "$PROFILE/SingletonLock"
    # classic --headless: the snap's --headless=new crashes at startup (crashpad ptrace errors)
    setsid nohup "$CHROME" --headless --disable-gpu --window-size="$W,$H" --no-first-run --noerrdialogs \
      --autoplay-policy=no-user-gesture-required --auto-accept-camera-and-microphone-capture \
      --use-fake-ui-for-media-stream --remote-debugging-port="$CDP_PORT" --user-data-dir="$PROFILE" \
      --disable-features=TranslateUI "$URL" > "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDF"; sleep 3
    if curl -fs "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null; then echo "headless browser up on DevTools :$CDP_PORT → $URL (pid $(cat "$PIDF"))"; else echo "browser did not expose DevTools — see $LOG"; tail -5 "$LOG"; exit 1; fi ;;
  stop)
    [ -f "$PIDF" ] && { pkill -TERM -P "$(cat "$PIDF")" 2>/dev/null; kill -TERM "$(cat "$PIDF")" 2>/dev/null; rm -f "$PIDF"; echo "stopped"; } || echo "not running" ;;
  status)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "running (pid $(cat "$PIDF"))"; curl -fs "http://127.0.0.1:$CDP_PORT/json" | python3 -c 'import sys,json; [print(" ", t.get("type"), t.get("url")) for t in json.load(sys.stdin)]' 2>/dev/null; else echo "not running"; fi ;;
  *) echo "usage: $0 start [url] | stop | status"; exit 2 ;;
esac
