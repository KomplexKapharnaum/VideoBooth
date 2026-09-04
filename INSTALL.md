# Install on kxkm-ai (Ubuntu 24.04, RTX 4090)

Two hands: **root steps are Thomas's** (sudo needs a password on this shared box), the
rest runs as `kxkm`. Every script is idempotent; re-run after a change. Paths and ports:
`setup/env.sh` (override in `booth.conf`).

## 0. Clone (kxkm)
```bash
git clone https://github.com/KomplexKapharnaum/VideoBooth.git /ai/VideoBooth
cd /ai/VideoBooth && setup/00_audit.sh          # read-only report, paste into BENCHMARKS.md
```

## 1. Driver repair + reboot (root) — REQUIRED before anything touches the GPU
State on 2026-09-04: userspace 580.173 vs loaded module 580.159, and no NVIDIA module on
disk for the kernel grub boots by default. Do not reboot without this.
```bash
sudo /ai/VideoBooth/setup/01_driver_fix.sh      # verifies module == userspace, blacklists auto-upgrades
sudo reboot                                     # or: sudo …/01_driver_fix.sh --reboot
# after reboot
nvidia-smi && mount | grep /mnt/models && docker ps --format '{{.Names}} {{.Status}}'
```
Side effects of the reboot: Clément's Clown stack restarts by docker policy, VoiceClone and
gpu-swap by cron @reboot, NFS hard mounts come back by themselves (July precedent).

## 2. System prerequisites (root)
```bash
sudo /ai/VideoBooth/setup/02_root_prereqs.sh    # Chrome (Google apt), build deps, v4l-utils, video group, GDM autologin kxkm
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
| 9222 | kiosk Chrome DevTools (localhost, for the probes) |

Never expose 7860/8000 beyond the LAN / tailnet.
