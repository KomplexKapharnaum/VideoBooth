#!/usr/bin/env bash
# 02_root_prereqs.sh — ROOT, idempotent. System packages, Chromium (snap), video group, GDM autologin.
# Run:  sudo /ai/VideoBooth/setup/02_root_prereqs.sh [--user kxkm] [--no-autologin] [--chrome]
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
BOOTH_USER=${SUDO_USER:-kxkm}; AUTOLOGIN=1; BROWSER=chromium
while [ $# -gt 0 ]; do case "$1" in --user) BOOTH_USER=$2; shift;; --no-autologin) AUTOLOGIN=0;; --chrome) BROWSER=chrome;; *) echo "unknown arg $1"; exit 2;; esac; shift; done
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y git curl jq tmux build-essential ninja-build python3-dev \
  v4l-utils ffmpeg x11-xserver-utils xdotool unclutter-xfixes edid-decode
echo "OK: packages"

# Browser. Default: Chromium — on Ubuntu 24.04 that is the Canonical snap (no deb exists).
# Kiosk needs: refresh held (no mid-show auto-update), camera plug connected, profile inside
# the snap's writable area (kiosk/booth-kiosk.sh handles the path). --chrome installs Google
# Chrome from Google's apt repo instead (HKiosk's choice; fallback if the snap misbehaves).
if [ "$BROWSER" = chromium ]; then
  snap list chromium >/dev/null 2>&1 || snap install chromium
  snap refresh --hold chromium >/dev/null 2>&1 && echo "OK: chromium snap, refresh held" || echo "WARN: could not hold chromium refresh (old snapd?)"
  snap connect chromium:camera 2>/dev/null || true
  snap connections chromium 2>/dev/null | grep -E "^(camera|removable-media|home) " | sed 's/^/      /'
else
  if ! command -v google-chrome-stable >/dev/null; then
    install -d /etc/apt/keyrings
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
    apt-get update -qq
  fi
  apt-get install -y google-chrome-stable && echo "OK: google-chrome-stable"
fi

# Camera access for services started outside a seat session (systemd --user, ssh).
id -nG "$BOOTH_USER" | grep -qw video || usermod -aG video "$BOOTH_USER"
echo "OK: $BOOTH_USER in video group (re-login to apply)"

# GDM autologin → the kiosk user unit starts with the graphical session.
if [ "$AUTOLOGIN" = 1 ] && [ -f /etc/gdm3/custom.conf ]; then
  sed -i -E "s/^#?\s*AutomaticLoginEnable\s*=.*/AutomaticLoginEnable=True/; s/^#?\s*AutomaticLogin\s*=.*/AutomaticLogin=$BOOTH_USER/" /etc/gdm3/custom.conf
  grep -q "^AutomaticLoginEnable=True" /etc/gdm3/custom.conf || sed -i "/^\[daemon\]/a AutomaticLoginEnable=True\nAutomaticLogin=$BOOTH_USER" /etc/gdm3/custom.conf
  grep -q "^WaylandEnable=false" /etc/gdm3/custom.conf || sed -i "/^\[daemon\]/a WaylandEnable=false" /etc/gdm3/custom.conf
  echo "OK: GDM autologin $BOOTH_USER (Xorg). Effective at next boot."
fi

# Never let unattended-upgrades touch the driver or kernel (also written by 01).
BL=/etc/apt/apt.conf.d/51videobooth-nvidia-hold
[ -f "$BL" ] || cat > "$BL" <<'CONF'
Unattended-Upgrade::Package-Blacklist { "nvidia-"; "libnvidia-"; "linux-image"; "linux-modules"; "linux-objects"; "linux-signatures"; "linux-headers"; "linux-oem"; "linux-generic"; };
CONF
echo "OK: unattended-upgrades blacklist ($BL)"
echo "Done. Next (as $BOOTH_USER): setup/10_engine_b.sh, setup/20_engine_a.sh, setup/99_verify.sh"
