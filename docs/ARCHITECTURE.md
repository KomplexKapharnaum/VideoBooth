# Architecture

How the VideoBooth is put together, from the camera to the 55" screen, and where every
piece lives. Read this once; the other docs assume it.

## 1. The experience, in one paragraph

A visitor stands in front of a fixed camera. Two to three metres away, a 55" TV in portrait
shows a **generated "superhero twin"** that copies their pose with a short, **constant** delay
(target about one second, lower is welcome). The twin is re-generated continuously by a
diffusion model that is steered by a **depth map** of the visitor, so the pose is always
theirs while the look is whatever the technician dials in, from clean comic-book hero to
borderline freaky. Nobody touches a screen; the technician drives everything from a laptop.
Full brief and the design rules in priority order: [../CLAUDE.md](../CLAUDE.md).

## 2. Physical setup

```
                 ┌──────────────────────────── kxkm-ai (Ubuntu 24.04, RTX 4090) ─────────────────────────────┐
 Logitech Brio   │                                                                                          │   55" TV, portrait
 4K (USB, UVC) ──┤ USB                                                                             HDMI ──┼──▶ (1080x1920 or
 fixed framing   │                                                                                          │   2160x3840)
                 └──────────────────────────────────────────────────────────────────────────────────────────┘
                                                        │ Ethernet + tailscale
                                        technician laptop: engine web UI (dials, presets, reset)
```

- **Machine**: `kxkm-ai`, i7-14700KF, 62 GB RAM, one RTX 4090 24 GB, 1.8 TB NVMe. It is a
  **shared** research box (ComfyUI, a whisper worker, TTS, LLM launchers). The booth cohabits;
  see §7.
- **Camera**: Logitech Brio 4K new gen, 1080p30 (MJPEG), person fills the portrait frame. A
  cheap 15 fps USB webcam sits on the box for plumbing tests until the Brio arrives.
- **Display**: the TV on the 4090's HDMI output, rotated to portrait by `xrandr`. The
  generation resolution never changes with the panel; the browser upscales.
- **Network**: technician UI on the LAN / tailnet only. Nothing is exposed to the internet.

## 3. Software layers

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ kiosk  (kiosk/booth-kiosk.sh + booth-kiosk.service, systemd --user, GDM autologin kxkm)   │
│   Chromium --kiosk on the HDMI output: opens the camera (getUserMedia, auto-granted)      │
│   and shows the engine's output page full-screen. DevTools on :9222 for the probes.      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ engine server (one of two, decided by measurement — DECISION.md)                         │
│   B  StreamDiffusion (Daydream fork) realtime-img2img demo   :7860   engines/b-…/run.sh   │
│      SD1.5-LCM · depth ControlNet · Depth Anything V2 on TensorRT · 1–2 steps · TensorRT  │
│   A  Daydream Scope                                            :8000   engines/a-scope/run.sh │
│      LongLive (Wan 2.1 1.3B) · VACE depth control · video-depth-anything · WebRTC/NDI out  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ show mode  (tools/showmode.sh on|off|status)                                             │
│   stops / restores the OTHER GPU tenants of the box so the engine has the whole 4090       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ OS  Ubuntu 24.04.4 · OEM kernel 6.17 · NVIDIA 595 open (Ubuntu-signed modules, Secure    │
│     Boot ON) · Chromium snap (refresh held) · uv-managed Python 3.10 venv for Engine B    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## 4. Data flow (Engine B, the one currently installed)

```
camera ──▶ kiosk Chromium page ──(websocket: "next_frame" + params JSON + JPEG)──▶ demo server
                    ▲                                                               │
                    │                                              depth_tensorrt preprocessor
                    │                                              (Depth Anything V2 small, 518²)
                    │                                                               ▼
                    │                                        StreamDiffusion: SD1.5-LCM + depth ControlNet
                    │                                        TensorRT engines, 1 step at 512x768, tiny VAE
                    │                                                               │
                    └──────────────(HTTP multipart MJPEG  /api/stream/<uuid>)◀───────┘
```

The page **pulls** work: the server sends `{"status":"send_frame"}` after each generated frame,
the page answers with the next camera frame. So the engine never queues up stale frames and
the delay stays constant — that is the property brief rule 2.2 asks for, and what
`tools/engine_b_probe.py` measures.

Engine A (Scope) works the same way from the outside — camera from the browser page, video
back over WebRTC — with its own UI, pipelines and control (OSC + HTTP API, NDI output).

## 5. Processes, ports, files on the box

| What | Where / how |
|---|---|
| Repo checkout | `/ai/VideoBooth` (clone of `KomplexKapharnaum/VideoBooth`, branch `main`), owned by `kxkm` |
| Upstream engines, venvs | `/ai/VideoBooth/.engines/StreamDiffusion` (+ `.venv`), `/ai/VideoBooth/.engines/scope` — gitignored |
| TensorRT engines | `/ai/VideoBooth/.engines/trt/` — SD unet/vae/controlnet per resolution + `depth_anything_v2_vits-fp16.engine` |
| Model cache | `/ai/VideoBooth/.hf` (`HF_HOME`); the box also has `/ai/data/models` (ComfyUI's checkpoints, local copies) |
| State, logs | `/ai/VideoBooth/.state/` — `logs/*.log`, `showmode.stopped`, Chrome profiles |
| Engine B server | tmux session `booth-b`, `engines/b-streamdiffusion/run.sh`, port **7860** |
| Engine A server | `engines/a-scope/run.sh`, port **8000** |
| Kiosk | `systemctl --user status booth-kiosk`, Chromium DevTools **9222** (localhost) |
| Config | `setup/env.sh` (paths, ports, defaults) overridden by `booth.conf` (gitignored, per machine) |

Pinned versions (2026-09-04): Python 3.10.20 · torch 2.8.0+cu128 · TensorRT 10.12.0.36 ·
diffusers 0.35.0 · StreamDiffusion fork `4c90d9e` · Node 22 / npm 10 · Chromium 152 (snap,
held) · NVIDIA 595.84. `SD_REF` / `SCOPE_REF` in `setup/env.sh` pin the upstream commits once a
bench passes.

## 6. Measuring (what the tools tell you)

| Tool | Measures | Use |
|---|---|---|
| `tools/engine_b_probe.py` | engine-side output fps, frame-interval mean/p95/max/stdev, stalls, and **latency mean + spread** from a flashing source | the number that decides A vs B; run after every change |
| `tools/fps_probe.py` | frames actually **presented** by the browser `<video>` (Engine A / any WebRTC page), via DevTools | display-side jitter |
| `tools/LATENCY.md` | glass-to-glass with a phone at 240 fps | the truth the visitor feels; once per engine + after display changes |
| `tools/camera_check.sh` | camera formats and real fps | on every new camera |
| `setup/00_audit.sh`, `setup/99_verify.sh` | machine state | before a bench, on show day |

Every number goes to [../BENCHMARKS.md](../BENCHMARKS.md) with the exact config, dated, never
overwritten.

## 7. Constraints you must know

- **Shared box.** Other people's services live here. Only `tools/showmode.sh` may stop them,
  and it restores exactly what it stopped. Never `pkill` around.
- **No sudo for the booth.** Root steps are scripts Thomas runs (`setup/01_*`, `setup/02_*`).
- **Secure Boot is on.** Only Ubuntu-signed NVIDIA modules load; they are linked at install
  time and need the kernel headers. `nvidia-driver-*` meta-packages (DKMS) must never be
  installed. `setup/01_driver_fix.sh` is the only sanctioned way to touch the driver.
- **Unattended upgrades** are blacklisted for nvidia and kernel packages. Do not remove
  `/etc/apt/apt.conf.d/51videobooth-nvidia-hold`.
- **Chromium is a snap**: refresh held (no mid-show update), profile under
  `~/snap/chromium/common`, camera plug connected. Google Chrome remains a fallback
  (`setup/02_root_prereqs.sh --chrome`).
- **TensorRT engines are bound** to resolution, TensorRT version and GPU: a resolution change
  means a rebuild (minutes), a TensorRT upgrade means rebuilding everything.
- **Public booth, families present**: the safety negatives in every preset are not optional
  (brief rule 2.7). No visitor-facing UI, no attribute detection of any kind.

## 8. Decisions and open questions

Decisions, deviations from the original brief and the risk list live in
[../ROADMAP.md](../ROADMAP.md). The engine choice will be recorded in
[../DECISION.md](../DECISION.md). Open at the time of writing: how the technician controls the
kiosk's session from another machine (the demo page owns the camera; Scope has OSC/API),
and an output-only page for the visitor screen.
