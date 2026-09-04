#!/usr/bin/env bash
# 01_driver_fix.sh — ROOT. Repairs the NVIDIA driver state of kxkm-ai before a reboot.
#
# Situation found 2026-09-04: userspace auto-upgraded to 580.173.02, running module
# 580.159.03 (NVML "Driver/library version mismatch"), and the newest installed OEM
# kernel — the one grub boots by default — has NO nvidia module on disk although its
# module package is marked installed. This script:
#   1. (re)installs the signed module trio for the newest kernel and verifies that the
#      module version on disk == the userspace version,
#   2. blacklists nvidia/kernel packages from unattended-upgrades so it cannot recur,
#   3. prints the reboot command (adds --reboot to do it now).
# Idempotent. Aborts (no reboot hint) if the verification fails.
#
# Run:  sudo /ai/VideoBooth/setup/01_driver_fix.sh [--reboot] [--kernel <kver>]
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
FLAVOR=580; DO_REBOOT=0; KVER=""
while [ $# -gt 0 ]; do case "$1" in --reboot) DO_REBOOT=1;; --kernel) KVER=$2; shift;; *) echo "unknown arg $1"; exit 2;; esac; shift; done
[ -n "$KVER" ] || KVER=$(ls /boot/vmlinuz-* | sed 's#.*/vmlinuz-##' | sort -V | tail -1)
USER_VER=$(dpkg-query -W -f='${Version}' nvidia-kernel-common-$FLAVOR | cut -d- -f1)
mod_ver() { modinfo -k "$KVER" nvidia 2>/dev/null | awk '/^version/{print $2}'; }
echo "target kernel : $KVER"
echo "userspace     : $USER_VER"
echo "module on disk: ${MODV:-$(mod_ver)}"
if [ "$(mod_ver)" != "$USER_VER" ]; then
  echo "→ reinstalling signed module packages for $KVER"
  apt-get update -qq
  apt-get install --reinstall -y "linux-signatures-nvidia-$KVER" "linux-objects-nvidia-$FLAVOR-$KVER" "linux-modules-nvidia-$FLAVOR-$KVER"
  depmod -a "$KVER"
  [ "$(mod_ver)" = "$USER_VER" ] || dpkg-reconfigure "linux-modules-nvidia-$FLAVOR-$KVER" || true
  depmod -a "$KVER"
fi
NOW=$(mod_ver)
if [ "$NOW" != "$USER_VER" ]; then
  echo "FAIL: module for $KVER is '${NOW:-missing}', userspace is $USER_VER. Do NOT reboot."
  echo "Diagnose: ls /lib/modules/$KVER/kernel/nvidia-$FLAVOR ; apt-cache policy linux-modules-nvidia-$FLAVOR-$KVER nvidia-kernel-common-$FLAVOR"
  exit 3
fi
SIGNER=$(modinfo -k "$KVER" nvidia | awk -F': *' '/^signer/{print $2}')
echo "OK: $KVER has nvidia $NOW (signer: ${SIGNER:-none})"
[ -n "$SIGNER" ] || echo "WARN: module is unsigned and Secure Boot is $(mokutil --sb-state 2>/dev/null)"
update-initramfs -u -k "$KVER" >/dev/null 2>&1 || true

BL=/etc/apt/apt.conf.d/51videobooth-nvidia-hold
cat > "$BL" <<'CONF'
// VideoBooth (KXKM): never let unattended-upgrades touch the GPU driver or the kernel.
// An automatic 580.159 → 580.173 userspace upgrade broke the driver on 2026-08-16.
Unattended-Upgrade::Package-Blacklist {
    "nvidia-";
    "libnvidia-";
    "linux-image";
    "linux-modules";
    "linux-objects";
    "linux-signatures";
    "linux-headers";
    "linux-oem";
    "linux-generic";
};
CONF
echo "OK: unattended-upgrades blacklist written to $BL"
echo
echo "Reboot to load $KVER + nvidia $NOW:   sudo reboot"
echo "After reboot check:  nvidia-smi ; mount | grep /mnt/models ; docker ps"
[ "$DO_REBOOT" = 1 ] && { echo "rebooting now"; sleep 2; reboot; }
exit 0
