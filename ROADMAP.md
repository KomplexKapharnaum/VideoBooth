# VideoBooth — roadmap

Real-time "superhero twin" booth for a KXKM festival: a fixed camera, one RTX 4090,
a 55" portrait screen showing a generated twin that copies the visitor's pose with a
short constant delay. Brief and rules: [CLAUDE.md](CLAUDE.md). Install:
[INSTALL.md](INSTALL.md). Measurements: [BENCHMARKS.md](BENCHMARKS.md).

```
Brio 4K ─USB─▶ kiosk Chromium (getUserMedia) ─WebRTC─▶ engine server (Scope :8000 | StreamDiffusion :7860)
                     ▲                                        │ depth preprocessor + diffusion, 1–2 steps
                     └────────── WebRTC output ◀──────────────┘
              same Chromium, --kiosk, portrait 55" on the 4090's HDMI
   technician: the engine's own web UI from a laptop on the LAN / tailnet (dials, presets, reset)
```

Origin: a first brief written with claude.chat (2026-09-03), reviewed against the real
machine (kxkm-ai) and the hub on 2026-09-04; the decisions below supersede it where
they differ (see "Deviations").

---

## Status (2026-09-04)

- **Repo created**, brief reviewed, scripts and configs drafted — **nothing run on the
  GPU yet**.
- **Blocker 0 — driver (root cause found 2026-09-04 pm)**: Ubuntu's signed NVIDIA
  module packages link their `.ko` at install time on this box (`latelink=true`) and
  need `linux-headers-<kver>`; the headers were never installed for the newest OEM
  kernel (6.17.0-1032, grub default), so its module package is stuck half-configured
  with no `nvidia.ko`, while unattended-upgrades moved the userspace to 580.173.02
  against a loaded 580.159.03 → `nvidia-smi` mismatch, and a plain reboot = dead GPU.
  The first `01_driver_fix.sh` failed on exactly that missing header. Fix =
  `setup/01_driver_fix.sh` (headers + configure), recommended with `--driver 595-open`
  (NVIDIA production branch 595, Ubuntu-recommended open modules for RTX 40, signed
  LRM packages, no DKMS), then reboot. Thomas runs it (root).
- **Show = IMA-Niort, 2026-09-24, Niort** (Thomas, 2026-09-04): non-commercial demo.
  Three weeks. Hub project [[ima-niort-2026]] carries the date.
- Camera: Brio 4K ordered, due week of 2026-09-07. A cheap USB webcam is already on
  `/dev/video0` for the pipeline bench.
- Display: 27" 4K desk monitor on HDMI-A-2 today; the 55" TV is not attached yet.

## Decisions locked (2026-09-04, Thomas)

1. **Machine = kxkm-ai, shared.** The booth cohabits under the `kxkm` account in
   `/ai/VideoBooth`. Other tenants (ComfyUI, hub whisper worker, VoiceClone, kokoro
   TTS, LLM launchers) stay installed; `tools/showmode.sh on|off` stops them for a show
   and restores exactly what it stopped. Kiosk = GDM autologin of `kxkm` + a systemd
   user unit running Chromium (snap) `--kiosk`.
2. **Root work is Thomas's.** `setup/01_driver_fix.sh` and `setup/02_root_prereqs.sh`
   are run by him with sudo; everything else runs as `kxkm`.
3. **Repo** `KomplexKapharnaum/VideoBooth`, public, GPL-3. Hub project `videobooth`
   (org KXKM, kind installation).
4. **Linux only.** Ubuntu 24.04 scripts. `WINDOWS.md` is a pointer list for an
   emergency machine swap, untested and unmaintained.
5. **Two engines, decided by measurement** (brief §4): Scope (LongLive + VACE depth)
   vs the Daydream StreamDiffusion fork (SD1.5-LCM + depth ControlNet + TensorRT).
   Score latency constancy > fps > look. One engine after `DECISION.md`.
6. **Browser = Chromium** (Canonical snap, refresh held, camera plug) — Thomas
   2026-09-04; Google Chrome stays a `--chrome` fallback in the prereqs script if the
   snap's confinement bites in Phase 1 (HKiosk's experience).
7. **Browser-centric I/O.** Both engines take the camera from the browser page and
   return video over WebRTC. The kiosk Chromium on kxkm-ai is both camera source and
   display; the technician drives the engine UI from another machine. A remote LAN
   display is a bonus (Scope: NDI out; either: a second browser), never the primary.

## Target machine facts (verified 2026-09-04 over ssh, read-only)

| | |
|---|---|
| Host | kxkm-ai · i7-14700KF 28 threads · 62 GB RAM · RTX 4090 24 GB · NVMe 1.8 TB, 937 GB free |
| OS | Ubuntu 24.04.4 · kernel 6.17.0-1028-oem running, 6.17.0-1032-oem installed (grub default) · Secure Boot ON (Ubuntu-signed NVIDIA modules, no DKMS) |
| NVIDIA | module 580.159.03 loaded · userspace 580.173.02 · signed LRM packages with `latelink=true` (headers required per kernel; never `nvidia-driver-*` meta = DKMS) · apt offers 580 / 595 / 610, `ubuntu-drivers` recommends 595-open · CUDA toolkit apt 12.0 (unused) |
| Access | `ssh kxkm-ai` = kxkm@100.87.54.119 (tailscale, Thomas's tailnet) · LAN 10.2.0.237 · sudo needs a password |
| Desktop | GDM + Xorg (Wayland disabled), `AutomaticLogin=kxkm` present but disabled · nobody logged in · gnome-remote-desktop service present, RDP disabled |
| Display | HDMI-A-2 connected: Samsung LS27D80xE, 3840×2160 · four other outputs free |
| Tooling | Python 3.12, uv (`~/.local/bin`), Node 22 (nvm + apt), Docker + nvidia runtime, ffmpeg, v4l-utils, Firefox snap only (no Chromium yet) |
| Camera now | Z-Star "Venus USB2.0 Camera" on `/dev/video0` (+ video1 metadata node); `kxkm` is NOT in the `video` group |
| GPU tenants | ComfyUI2 :8188 (user unit `kxkm-comfyui`, VRAM unload cron every 5 min) · docker `gpu-worker` (whisper for hub37, polls every 3 s) · VoiceClone :7865 (tmux `voiceclone`, cron @reboot) · `kokoro-tts` user unit :9211 · gpu-swap uvicorn :18890 (LLM launcher, cron @reboot) · many inactive LLM user units |
| Models on disk | `/ai/data/models`: SD1.5 depth ControlNet, OpenPose CN, LCM Dreamshaper v7, SD-Turbo, SDXL-Lightning 1/2/4-step, DreamshaperXL turbo; TensorRT Depth-Anything engines (ComfyUI's) |
| Ports free | 7860, 8000, 9222 |
| Upgrades | unattended-upgrades ON (this is what broke the driver) |

## Phases

### Phase 0 — machine ready (this week, Thomas + dev37)
- [ ] `setup/01_driver_fix.sh --driver 595-open` run as root → headers installed, signed
      595.84 module for 6.17.0-1032, 580 removed → reboot → `nvidia-smi` green, NFS
      mounts back, Clown stack up.
- [ ] `setup/02_root_prereqs.sh` → Chromium snap (refresh held), build deps, `video` group, GDM autologin,
      unattended-upgrades blacklist for nvidia/kernel.
- [ ] `setup/00_audit.sh` report filed in BENCHMARKS.md (header block).

### Phase 1 — engines and baselines (this week with the USB webcam, redo with the Brio)
- [ ] `tools/camera_check.sh` (formats, real fps).
- [ ] Engine B: `setup/10_engine_b.sh`, TensorRT engines 512×768, baseline run,
      `tools/fps_probe.py` 2 min moving person → BENCHMARKS.md.
- [ ] Engine A: `setup/20_engine_a.sh` (ask before the ~20 GB Wan download), LongLive
      bare, then VACE depth; SDV2 bare once → BENCHMARKS.md.
- [ ] Glass-to-glass for both (`tools/LATENCY.md`).
- [ ] Kiosk unit live on the desk monitor, portrait.

### Phase 2 — decision (week of 2026-09-07, Brio + real people + 3 lightings)
- [ ] A/B session → `DECISION.md`. One engine from here.
- [ ] Dials verified live; `presets/heroes.json` 5 heroes tuned.
- [ ] Operator README.

### Phase 3 — show hardening (before the festival)
- [ ] 55" TV attached, portrait, native mode, overscan checked.
- [ ] `showmode on` rehearsal: cold boot → kiosk up → engine up → picture, no hands.
- [ ] Stall watchdog: engine restart without touching the kiosk.
- [ ] Two-hour soak with a moving person; jitter logged.

### Later (not now)
Style LoRA on house references · hero-shot high-res still on a button · NDI / WebRTC
output to a remote display (Scope NDI → HNdi on an N150 kiosk) · phone-as-camera ·
second GPU only if measured fps demands it.

## Deviations from the claude.chat brief (and why)

- **Engine A baseline = LongLive + VACE, not StreamDiffusionV2 + VACE.** Scope's own
  VACE doc (read 2026-09-04) lists `longlive`, `reward-forcing`, `memflow` as the VACE
  pipelines and says SDV2 "supports VACE but with poor quality". SDV2 stays for the
  bare-speed number.
- **No shared `common/depth.py` runtime.** Each engine ships a depth preprocessor
  (Scope `video-depth-anything`, StreamDiffusion `depth` / `depth_tensorrt`); a
  separate process would put a second depth model on the GPU and add a hop. The
  camera goes to the engine through the browser page, as both demos are built.
- **Engine B installs before Engine A.** B needs no download (checkpoints on disk),
  A pulls ~20 GB of Wan weights; the order minimizes time-to-first-picture.
- **StreamDiffusion fork = daydreamlive/StreamDiffusion.** The livepeer repo named in
  the brief is archived (read-only since 2025-12-26).
- **The machine is not exclusive.** Brief §3 said "no ComfyUI, no second Python
  process" — kept as a SHOW-TIME rule (show-mode), not an install rule.
- **Windows** exists as `WINDOWS.md` because the production machine may be swapped;
  the brief's "Linux only" still governs everything that is scripted.

## Risks

- **Driver drift** on a shared box with unattended-upgrades — mitigated by the
  blacklist in `02_root_prereqs.sh`; a show-week freeze is still Thomas's call.
- **Scope is alpha**, weekly changes; pin the commit that passes the bench in
  `setup/env.sh` (`SCOPE_REF`) and never update during show week.
- **VRAM**: LongLive ~20 GB + depth preprocessor ~1 GB + Chromium on the same GPU. Show
  mode must leave the GPU empty; `nvidia-smi` is checked by `showmode status`.
- **Brio at 1080p30**: MJPEG or YUY2 — the browser decodes; if CPU decode jitters,
  drop the capture to 720p (generation input is ≤ 576p anyway).
- **Two browsers on one stream**: whether a technician page and the kiosk page can
  share one session is engine-specific; if not, the technician uses OSC/API (Scope) or
  the demo's controls over the kiosk page via DevTools (B). Verified in Phase 1.
- **Reboot side effects**: Clément's Clown stack (docker restart policies), VoiceClone
  and gpu-swap (cron @reboot) come back by themselves; NFS hard mounts recovered on
  their own after the July outage.

## Open items

- 55" TV model / native resolution / HDMI cable length (4K60 over a long run?).
- Reboot window for the driver fix (Clément's bot restarts, whisper worker idle).
- Whether `kxkm-comfyui` should be re-enabled after each show automatically
  (`showmode off` does) or left down during the festival week.
