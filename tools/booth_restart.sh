#!/usr/bin/env bash
# booth_restart.sh — the panel's RESTART button: VideoBooth back to the state it has after a boot,
# without rebooting the box. Runs DETACHED (systemd-run --user) because it restarts the panel that
# called it. Order matters: engines first (they hold the GPU), then the NDI node (drops the pick:
# nothing persists), then the visitor screen, the panel last.
#   1. tools/boot_state.sh   engines stopped, show mode off, KIOSK_URL blank
#   2. SOURCE=webcam         every start begins on the USB camera (the kiosk unit's cold-boot rule)
#   3. hndi-in restarted     (root via sudo -n; skipped if HNdi is not installed)
#   4. booth-kiosk restarted (screen black meanwhile, ~15 s)
#   5. booth-panel restarted (the page reconnects by itself)
# The technician then picks the engine, as after a boot.
set -uo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
. "$ROOT/setup/env.sh"
LOG="${BOOTH_STATE:-$ROOT/.state}/logs/booth_restart.log"; mkdir -p "$(dirname "$LOG")"
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
sleep 1                                     # let the panel answer the click first
say "RESTART requested"
"$ROOT/tools/boot_state.sh" >>"$LOG" 2>&1 && say "boot state: engines stopped, show mode off, screen blank" || say "boot_state.sh failed (continuing)"
sed -i -E 's/^SOURCE=.*$/SOURCE="webcam"/; s/&cam=NDI"/"/; s/\?cam=NDI&/?/; s/\?cam=NDI"/"/' "$ROOT/booth.conf" 2>/dev/null
rm -f "/run/user/$(id -u)/booth-kiosk.booted"; say "video source: webcam"
if systemctl is-enabled hndi-in >/dev/null 2>&1; then sudo -n systemctl restart hndi-in && say "hndi-in restarted (no source until a pick)" || say "hndi-in restart refused (sudo)"; fi
systemctl --user restart booth-kiosk.service && say "kiosk restarted"
say "panel restarting"; systemctl --user restart booth-panel.service
