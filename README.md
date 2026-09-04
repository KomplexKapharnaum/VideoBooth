# VideoBooth

Real-time "superhero twin" booth for KXKM at **IMA-Niort 2026** (Niort, 24 September). A visitor
stands in front of a fixed camera; a 55" portrait screen shows a generated superhero copying
their pose with a short, constant delay. One machine (RTX 4090), one camera (Logitech Brio 4K),
a browser in kiosk mode, and a diffusion engine picked by measurement. Non-commercial demo.

```
Brio 4K ─USB─▶ kiosk Chromium (camera + display, --kiosk, portrait 55")
                  │ websocket / WebRTC                 ▲ MJPEG / WebRTC
                  ▼                                    │
        engine server on the same 4090:  StreamDiffusion (:7860)  or  Scope (:8000)
        depth map of the visitor → 1–2 step diffusion → video, ~10–20 fps, ~0.3–1 s behind
        technician: the engine's web UI from a laptop on the LAN — dials, presets, reset
```

> **Status (2026-09-04):** machine prepared (driver 595 open, Chromium, autologin), Engine B
> installed with its TensorRT depth preprocessor, first baseline being measured. Engine A not
> installed yet. Camera arrives the week of 7 September. Details: [ROADMAP.md](ROADMAP.md).

## Start here

| You are… | Read |
|---|---|
| **new on the project** | [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) — access, day-1 checklist, how to work on the box |
| **wondering how it works** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — the whole chain, ports, paths, constraints |
| **running a show or rehearsal** | [docs/OPERATIONS.md](docs/OPERATIONS.md) — show day, during, after, troubleshooting |
| **changing the look** | [docs/TUNING.md](docs/TUNING.md) — dials, presets, config keys, the measure-after-every-change rule |
| **installing from scratch** | [INSTALL.md](INSTALL.md) — root steps (Thomas) and user steps, in order |
| **deciding / arguing** | [CLAUDE.md](CLAUDE.md) the brief and its rules · [ROADMAP.md](ROADMAP.md) decisions, deviations, risks · [DECISION.md](DECISION.md) engine choice · [BENCHMARKS.md](BENCHMARKS.md) every number |

## Technician panel

`http://<box>:7870` from a laptop or tablet on the LAN (`panel/`, no login): live preview of
the visitor screen, prompt and negative, presets, knobs of the running engine, show mode,
engine start/stop and the kiosk target.

## Quick commands (on the box, as `kxkm`, in `/ai/VideoBooth`)

```bash
setup/99_verify.sh                              # is the machine ready? PASS/FAIL list
tools/showmode.sh on|off|status                 # free the GPU for a show / give it back
tmux new -d -s booth-b engines/b-streamdiffusion/run.sh    # Engine B → http://<box>:7860
engines/a-scope/run.sh                          # Engine A → http://<box>:8000 (once installed)
systemctl --user status booth-kiosk             # the visitor screen; tools/cdp.py --screenshot /tmp/k.png
.engines/StreamDiffusion/.venv/bin/python tools/engine_b_probe.py --source lavfi --seconds 60 --label "…"   # fps / jitter / latency
```

## Repo map

```
CLAUDE.md  ROADMAP.md  INSTALL.md  BENCHMARKS.md  DECISION.md  WINDOWS.md   the documents
docs/            ARCHITECTURE · GETTING-STARTED · OPERATIONS · TUNING
setup/           00 audit · 01 driver fix (root) · 02 prereqs (root) · 10 engine B · 20 engine A · 99 verify · env.sh
tools/           showmode · camera_check · engine_b_probe · fps_probe + cdp (DevTools) · bench_browser · LATENCY.md
kiosk/           Chromium kiosk launcher + systemd user unit (portrait, camera auto-granted)
engines/         a-scope/ (notes, run.sh) · b-streamdiffusion/ (config yaml, run.sh, depth engine builder)
presets/         heroes.json — technician presets, safety negatives always on
booth.conf       (gitignored) per-machine overrides of setup/env.sh
.engines/ .hf/ .state/   (gitignored, on the box) upstream checkouts + venvs, model cache, logs + state
```

License: GPL-3.0. Engines keep their own licenses (Scope CC BY-NC-SA 4.0, StreamDiffusion Apache-2.0).
