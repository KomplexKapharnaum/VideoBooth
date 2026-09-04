#!/usr/bin/env bash
# 99_verify.sh — is this machine ready for a show? PASS/FAIL per check, exit 1 on any FAIL.
set -uo pipefail
. "$(dirname "$0")/env.sh"
rc=0; ok() { echo "PASS  $1"; }; ko() { echo "FAIL  $1"; rc=1; }; warn() { echo "WARN  $1"; }
if nvidia-smi >/dev/null 2>&1; then ok "nvidia-smi ($(nvidia-smi --query-gpu=driver_version --format=csv,noheader))"; else ko "nvidia-smi (driver mismatch? setup/01_driver_fix.sh + reboot)"; fi
M=$(cat /sys/module/nvidia/version 2>/dev/null); U=$(dpkg-query -W -f='${Version}' nvidia-kernel-common-580 2>/dev/null | cut -d- -f1)
[ -n "$M" ] && [ "$M" = "$U" ] && ok "kernel module $M == userspace $U" || ko "kernel module '${M:-none}' vs userspace '$U'"
[ -f /var/run/reboot-required ] && warn "reboot-required flag is set" || ok "no reboot pending"
id -nG | grep -qw video && ok "user in video group" || ko "user not in video group (setup/02_root_prereqs.sh)"
C=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium); [ -n "$C" ] && ok "browser: $C" || ko "no Chrome/Chromium"
command -v uv >/dev/null && ok "uv" || ko "uv"
[ -c "$CAMERA_DEV" ] && [ -r "$CAMERA_DEV" ] && ok "camera $CAMERA_DEV readable" || ko "camera $CAMERA_DEV missing or not readable"
[ -x "$SD_DIR/.venv/bin/python" ] && "$SD_DIR/.venv/bin/python" -c "import streamdiffusion, tensorrt" 2>/dev/null && ok "engine B venv imports streamdiffusion+tensorrt" || warn "engine B not installed (setup/10_engine_b.sh)"
[ -d "$SCOPE_DIR/.venv" ] && ok "engine A built ($SCOPE_DIR)" || warn "engine A not installed (setup/20_engine_a.sh)"
for p in $SD_PORT $SCOPE_PORT; do ss -tln | grep -q ":$p " && warn "port $p in use (engine running?)" || ok "port $p free"; done
grep -qs "AutomaticLoginEnable=True" /etc/gdm3/custom.conf && ok "GDM autologin" || warn "GDM autologin off (kiosk needs a logged-in session)"
systemctl --user is-enabled booth-kiosk.service >/dev/null 2>&1 && ok "booth-kiosk.service enabled" || warn "booth-kiosk.service not enabled (kiosk/README)"
[ -f /etc/apt/apt.conf.d/51videobooth-nvidia-hold ] && ok "unattended-upgrades blacklist" || warn "no unattended-upgrades blacklist"
"$BOOTH_HOME/tools/showmode.sh" status | sed 's/^/      /'
exit $rc
