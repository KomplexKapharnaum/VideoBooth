#!/usr/bin/env bash
# boot_state.sh — the state the booth must be in after a boot: SHOW MODE OFF (the box's other
# services start by themselves at boot, so a leftover state file would lie), engines STOPPED
# (no tmux server survives a reboot; make sure), visitor screen BLANK (the kiosk unit reads
# KIOSK_URL from booth.conf when the autologin session starts). The technician then chooses
# the engine and turns show mode on from the panel. Runs from booth-boot.service before the
# panel; safe to run by hand.
set -uo pipefail
. "$(dirname "$0")/../setup/env.sh"
CONF=$BOOTH_HOME/booth.conf; BLANK="http://127.0.0.1:$KIOSK_HTTP_PORT/blank.html"
mkdir -p "$BOOTH_LOGS"
if [ -f "$BOOTH_STATE/showmode.stopped" ]; then
  echo "$(date -Is) boot: stale show-mode state removed (tenants restart on their own at boot)" | tee -a "$BOOTH_LOGS/boot.log"
  rm -f "$BOOTH_STATE/showmode.stopped"
fi
tmux kill-session -t booth-a 2>/dev/null; tmux kill-session -t booth-b 2>/dev/null
touch "$CONF"; grep -v '^KIOSK_URL=' "$CONF" > "$CONF.tmp"; printf 'KIOSK_URL="%s"\n' "$BLANK" >> "$CONF.tmp"; mv "$CONF.tmp" "$CONF"
echo "$(date -Is) boot: engines stopped, show mode off, visitor screen → blank ($BLANK)" | tee -a "$BOOTH_LOGS/boot.log"
