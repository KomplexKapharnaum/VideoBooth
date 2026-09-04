#!/usr/bin/env bash
# 00_audit.sh — read-only machine audit. Installs nothing, needs no root.
# Usage: setup/00_audit.sh | tee -a BENCHMARKS.md   (paste under "## Machine")
set -uo pipefail
. "$(dirname "$0")/env.sh"
h() { printf '\n### %s\n```\n' "$1"; }
e() { printf '```\n'; }
echo "## Machine audit — $(hostname) — $(date -Is)"
h "Host"; uptime; grep -E "PRETTY|VERSION_ID" /etc/os-release; echo "kernel: $(uname -r)"; [ -f /var/run/reboot-required ] && echo "REBOOT REQUIRED"; e
h "NVIDIA"; nvidia-smi --query-gpu=name,driver_version,memory.used,memory.total --format=csv 2>&1 | head -3
echo "kernel module: $(cat /sys/module/nvidia/version 2>/dev/null || echo none loaded)"
echo "userspace    : $(dpkg-query -W -f='${db:Status-Abbrev}\t${Package} ${Version}\n' 'nvidia-utils-*' 2>/dev/null | awk '$1=="ii"{print $2, $3}' | head -1)"
for k in $(ls /lib/modules); do v=$(modinfo -k "$k" nvidia 2>/dev/null | awk '/^version/{print $2}'); [ -n "$v" ] && echo "module on disk for $k: $v"; done
echo "newest kernel (grub default 0): $(ls /boot/vmlinuz-* | sed 's#.*/vmlinuz-##' | sort -V | tail -1)"
echo "secure boot: $(mokutil --sb-state 2>/dev/null | tr -d '\n')"; e
h "GPU processes"; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>&1 | head; e
h "CPU / RAM / disk"; lscpu | grep "Model name"; nproc; free -h | head -2; df -h / "$BOOTH_HOME" 2>/dev/null | awk 'NR==1||/\//'; e
h "Python / tooling"; python3 --version; echo "uv: $(command -v uv || echo missing)"; echo "node: $(node --version 2>/dev/null || echo missing)"; echo "chrome: $(command -v google-chrome-stable || command -v google-chrome || command -v chromium || echo missing)"; echo "ffmpeg: $(command -v ffmpeg || echo missing)"; echo "v4l2-ctl: $(command -v v4l2-ctl || echo missing)"; echo "docker: $(command -v docker || echo missing)"; e
h "User / groups"; id; echo "video group: $(id -nG | grep -qw video && echo yes || echo NO)"; loginctl show-user "$USER" -p Linger 2>/dev/null; e
h "Display"; for p in /sys/class/drm/card*-*; do s=$(cat "$p/status" 2>/dev/null); [ "$s" = connected ] && echo "$(basename "$p"): connected, modes: $(head -1 "$p/modes" 2>/dev/null)"; done
grep -E "^(AutomaticLogin|WaylandEnable)" /etc/gdm3/custom.conf 2>/dev/null; loginctl list-sessions --no-legend 2>/dev/null | head -5; e
h "Cameras"; v4l2-ctl --list-devices 2>&1 | head -12; ls -l /dev/video* 2>/dev/null; e
h "Listening ports (booth-relevant)"; ss -tln 2>/dev/null | awk 'NR>1{print $4}' | grep -E ":(7860|8000|8188|7865|9222|18890|9211)$" || echo "none of 7860 8000 8188 7865 9222 18890 9211"; e
h "Show-mode tenants"; "$BOOTH_HOME/tools/showmode.sh" status 2>/dev/null || echo "(tools/showmode.sh not runnable from here)"; e
