# Install on kxkm-ai (Ubuntu 24.04, RTX 4090)

> Already done on kxkm-ai (2026-09-04) up to step 5 for Engine B. New here? Start with
> [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md); this page is the from-scratch procedure.

Two hands: **root steps are Thomas's** (sudo needs a password on this shared box), the
rest runs as `kxkm`. Every script is idempotent; re-run after a change. Paths and ports:
`setup/env.sh` (override in `booth.conf`).

## 0. Clone (kxkm)
```bash
git clone https://github.com/KomplexKapharnaum/VideoBooth.git /ai/VideoBooth
cd /ai/VideoBooth && setup/00_audit.sh          # read-only report, paste into BENCHMARKS.md
```

## 1. Driver repair + reboot (root) — REQUIRED before anything touches the GPU
Root cause (2026-09-04): the signed NVIDIA module packages link their `.ko` at install
time (`latelink=true`) and need `linux-headers-<kver>`; the newest OEM kernel (grub
default) had none, so it has no NVIDIA module, and unattended-upgrades moved the userspace
ahead of the loaded module. Do not reboot without this. Secure Boot is on: the script
installs explicit signed packages, never `nvidia-driver-*` (that pulls DKMS).
```bash
# recommended: NVIDIA production branch 595, open kernel modules (ubuntu-drivers' pick for RTX 40)
sudo /ai/VideoBooth/setup/01_driver_fix.sh --driver 595-open
sudo reboot                                     # reboot right away: the loaded 580 module no longer matches the new userspace
# alternative: stay on 580.173 (headers + finish configure only)
sudo /ai/VideoBooth/setup/01_driver_fix.sh
sudo reboot
# after reboot
nvidia-smi && mount | grep /mnt/models && docker ps --format '{{.Names}} {{.Status}}'
```
Fallback if 595 misbehaves: `sudo setup/01_driver_fix.sh --driver 580` reinstalls the 580 set.
Side effects of the reboot: Clément's Clown stack restarts by docker policy, VoiceClone and
gpu-swap by cron @reboot, NFS hard mounts come back by themselves (July precedent).

## 2. System prerequisites (root)
```bash
sudo /ai/VideoBooth/setup/02_root_prereqs.sh    # Chromium snap (refresh held, camera plug), build deps, v4l-utils, video group, GDM autologin kxkm; --chrome for Google Chrome instead
```
`--no-autologin` keeps the login screen (then start the kiosk by hand from the desktop).
Log out / in once for the `video` group.

## 3. Camera (kxkm)
```bash
tools/camera_check.sh /dev/video0               # formats + real fps; Brio: expect MJPG 1080p30
```
Set `CAMERA_DEV` in `booth.conf` if the Brio is not video0 (`v4l2-ctl --list-devices`).

## 4. Engine B — StreamDiffusion (kxkm, no big download)
```bash
setup/10_engine_b.sh                            # Python 3.10 venv, torch cu128, fork + TensorRT, demo build
engines/b-streamdiffusion/run.sh                # first run builds the TensorRT engines (minutes) → http://kxkm-ai:7860
```

## 5. Engine A — Scope (kxkm, > 10 GB of weights on first run: ask first)
```bash
setup/20_engine_a.sh                            # git clone + uv run build
engines/a-scope/run.sh                          # first run downloads the pipeline weights → http://kxkm-ai:8000
```

## 6. Kiosk (kxkm, inside the graphical session)
```bash
mkdir -p ~/.config/systemd/user && ln -sf /ai/VideoBooth/kiosk/booth-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now booth-kiosk.service
```
`KIOSK_URL` / `KIOSK_ROTATE` / `KIOSK_MODE` in `booth.conf`. Screenshot of what the TV
shows: `tools/cdp.py --screenshot /tmp/k.png`.

## 6b. Panel + boot state (kxkm)
```bash
ln -sf /ai/VideoBooth/panel/booth-panel.service ~/.config/systemd/user/ && ln -sf /ai/VideoBooth/panel/booth-boot.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable booth-boot.service && systemctl --user enable --now booth-panel.service
```
At boot the booth comes up idle (engines stopped, show mode off, blank screen); the panel at
`http://<box>:7870` starts everything.

## 7. Verify + show mode
```bash
setup/99_verify.sh                              # PASS/FAIL list
tools/showmode.sh on                            # stops ComfyUI, whisper worker, VoiceClone, TTS, LLM launchers
tools/showmode.sh status
tools/showmode.sh off                           # restores exactly what "on" stopped
```

## Ports
| 7860 | Engine B UI (StreamDiffusion demo) |
|---|---|
| 8000 | Engine A UI (Scope) |
| 9222 | kiosk Chromium DevTools (localhost, for the probes) |

Never expose 7860/8000 beyond the LAN / tailnet.
