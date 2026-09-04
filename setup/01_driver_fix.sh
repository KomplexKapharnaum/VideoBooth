#!/usr/bin/env bash
# 01_driver_fix.sh — ROOT. Put the NVIDIA driver of kxkm-ai in a known-good, reboot-safe state.
#
# Root cause found 2026-09-04: Ubuntu's signed NVIDIA module packages (linux-modules-nvidia-*)
# LINK the .ko files at install time on this box (/etc/default/linux-modules-nvidia:
# latelink=true), which needs the matching linux-headers-<kver>. Headers were never
# installed for the newest OEM kernel (grub default), so its module package sits
# "half-configured" with no nvidia.ko on disk, while unattended-upgrades already moved the
# userspace to a newer 580 build than the loaded module → NVML mismatch. A plain reboot
# would boot a kernel without any NVIDIA module.
#
# Secure Boot is ON: only Canonical-signed modules load. Never install nvidia-driver-<N>
# meta-packages here — they pull nvidia-dkms-<N>, whose unsigned module would shadow the
# signed one (/lib/modules/*/updates/dkms wins in depmod). This script installs the explicit
# package set instead.
#
# Modes:
#   sudo setup/01_driver_fix.sh                 keep the 580 branch: headers + finish configure
#   sudo setup/01_driver_fix.sh --driver 595-open   switch to the current NVIDIA production
#                                               branch (595, open kernel modules — Ubuntu's
#                                               `ubuntu-drivers` recommendation for RTX 40)
#   options: --kernel <kver> (default: newest installed)  --reboot (reboot when verified)
# Idempotent. Verifies module-on-disk == userspace version before printing the reboot hint.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
DRIVER=keep; DO_REBOOT=0; KVER=""
while [ $# -gt 0 ]; do case "$1" in
  --driver) DRIVER=$2; shift;; --reboot) DO_REBOOT=1;; --kernel) KVER=$2; shift;;
  *) echo "unknown arg $1"; exit 2;; esac; shift; done
[ -n "$KVER" ] || KVER=$(ls /boot/vmlinuz-* | sed 's#.*/vmlinuz-##' | sort -V | tail -1)
export DEBIAN_FRONTEND=noninteractive
echo "target kernel : $KVER   (running: $(uname -r), loaded module: $(cat /sys/module/nvidia/version 2>/dev/null || echo none))"

# 1. Let dpkg settle what it can (the nvidia module configure still fails here — expected),
#    install the headers for the target kernel, then finish the pending configures.
dpkg --configure -a || true
apt-get update -qq
apt-get install -y "linux-headers-$KVER"
dpkg --configure -a || true

# 2. Branch.
case "$DRIVER" in
  keep)
    BRANCH=$(ls /lib/modules/"$KVER"/kernel 2>/dev/null | grep -oE 'nvidia-[0-9]+(-open)?' | head -1)
    BRANCH=${BRANCH#nvidia-}; [ -n "$BRANCH" ] || BRANCH=580
    echo "keeping branch $BRANCH"
    apt-get install --reinstall -y "linux-modules-nvidia-$BRANCH-$KVER" || dpkg-reconfigure "linux-modules-nvidia-$BRANCH-$KVER"
    ;;
  *-open|[0-9]*)
    BRANCH=$DRIVER; N=${BRANCH%-open}
    echo "switching to branch $BRANCH (userspace nvidia-utils-$N + signed modules for $KVER)"
    apt-get install -y \
      "nvidia-utils-$N" "libnvidia-gl-$N" "libnvidia-compute-$N" "libnvidia-decode-$N" "libnvidia-encode-$N" \
      "libnvidia-extra-$N" "libnvidia-cfg1-$N" "libnvidia-fbc1-$N" "nvidia-compute-utils-$N" \
      "nvidia-kernel-common-$N" "nvidia-kernel-source-$BRANCH" "xserver-xorg-video-nvidia-$N" \
      "linux-modules-nvidia-$BRANCH-$KVER" "linux-modules-nvidia-$BRANCH-oem-24.04"
    apt-get autoremove -y --purge >/dev/null || true
    ;;
esac
N=${BRANCH%-open}
depmod -a "$KVER"

# 3. Verify: signed module on disk for $KVER, same version as userspace, no DKMS shadow.
USER_VER=$(dpkg-query -W -f='${Version}' "nvidia-utils-$N" | cut -d- -f1)
MOD_VER=$(modinfo -k "$KVER" nvidia 2>/dev/null | awk '/^version/{print $2}')
SIGNER=$(modinfo -k "$KVER" nvidia 2>/dev/null | awk -F': *' '/^signer/{print $2}')
MOD_FILE=$(modinfo -k "$KVER" -F filename nvidia 2>/dev/null || true)
echo "userspace     : $USER_VER (nvidia-utils-$N)"
echo "module on disk: ${MOD_VER:-missing} ${MOD_FILE:+at $MOD_FILE} signer: ${SIGNER:-none}"
FAIL=0
[ -n "$MOD_VER" ] && [ "$MOD_VER" = "$USER_VER" ] || FAIL=1
case "$MOD_FILE" in */updates/dkms/*) echo "FAIL: an unsigned DKMS module shadows the signed one — remove nvidia-dkms-*"; FAIL=1;; esac
[ -n "$SIGNER" ] || { echo "FAIL: module is unsigned and Secure Boot is $(mokutil --sb-state 2>/dev/null)"; FAIL=1; }
if [ "$FAIL" = 1 ]; then
  echo "FAIL: do NOT reboot. Diagnose: ls /lib/modules/$KVER/kernel/nvidia-$BRANCH ; tail -60 /var/log/apt/term.log ; dpkg -l | grep nvidia"
  exit 3
fi
update-initramfs -u -k "$KVER" >/dev/null 2>&1 || true
echo "OK: $KVER will load nvidia $MOD_VER (signed) matching userspace $USER_VER"

# 4. Never again by unattended-upgrades.
BL=/etc/apt/apt.conf.d/51videobooth-nvidia-hold
cat > "$BL" <<'CONF'
// VideoBooth (KXKM): unattended-upgrades must not touch the GPU driver or the kernel.
// A 580.159 → 580.173 userspace auto-upgrade broke the driver on 2026-08-16.
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
echo "OK: unattended-upgrades blacklist at $BL"
echo
echo "Reboot into $KVER:   sudo reboot"
echo "After reboot:        nvidia-smi ; mount | grep /mnt/models ; docker ps --format '{{.Names}} {{.Status}}'"
[ "$DO_REBOOT" = 1 ] && { echo "rebooting now"; sleep 2; reboot; }
exit 0
