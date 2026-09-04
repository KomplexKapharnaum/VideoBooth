# VideoBooth — real-time pose-driven "superhero twin" booth

Project brief and working instructions. Read fully before doing anything.
Decisions below were made deliberately (claude.chat brief 2026-09-03, then
reviewed against the real machine and the hub on 2026-09-04); do not
re-litigate them unless a hard blocker appears. Report blockers, do not
silently work around them. Plan, status and deviations: `ROADMAP.md`.

## 1. What we are building

A physical booth at a festival (non-commercial demo, KXKM). A visitor steps
in front of a fixed camera and sees, on a 55" portrait screen 2–3 m away, a
continuously generated video of a "superhero twin" that copies their pose
with a short, CONSTANT delay. The delay is part of the experience: people
learn to time their moves against it.

The aesthetic is "superhero but borderline freaky", not a clean idealized
Hollywood render. Uncanny anatomy, invented volume, flicker, drift and
low-res softness are acceptable and often desirable — but the technician
must be able to dial between "clean" and "freaky" live.

The user interface is for the technician, not the visitor. The visitor
only sees the screen.

## 2. Design rules, in priority order

1. Pose legibility above everything. The output must always read as
   "that is my pose, a moment later". Anything that breaks the pose link
   is a bug, however good it looks.
2. Constant latency. The absolute value is negotiable against other
   constraints (target ~1 s, lower is welcome); what is not negotiable is
   that it does not wander. Measure frame-time variance, not just fps.
   Treat stalls and spikes as bugs.
3. Frame rate: ≥ 10 fps is the target at the baseline config. Dropping
   below it under heavier settings (more denoising steps, extra control)
   is tolerable as long as the pose stays readable. Establish the
   readability floor by test (expect it around 6 fps), record it.
4. Style dials exposed to the technician in the running UI, no restart:
   denoising steps, v2v strength/denoise, control (depth) scale, negative
   prompt on/off, seed lock on/off, frame interpolation on/off, and any
   engine-specific coherence/similarity setting. "Clean" and "freaky" are
   two ends of these dials, not two configs.
5. Temporal coherence is nice-to-have, not required. Frame-to-frame
   flicker is acceptable and can be a style. Engines are chosen on speed,
   latency constancy and look — not on coherence alone.
6. Subject identity is not required. Skin tone, gender presentation and
   body shape should mostly survive; that is achieved by the image/video
   pipeline carrying the input pixels, never by classifying the visitor.
   NO automatic gender / skin-tone / age detection of any kind.
7. Public booth, families present: safety negatives (nudity, gore,
   sexual content) stay in every preset even when aesthetic negatives
   ("ugly, deformed") are removed on purpose.

## 3. Hardware and OS (verified on the machine, 2026-09-04)

- Machine: **kxkm-ai** — i7-14700KF, 62 GB RAM, single RTX 4090 24 GB,
  1.8 TB NVMe (≈ 940 GB free). Ubuntu 24.04 LTS, OEM kernel 6.17, NVIDIA
  580 (Ubuntu signed modules, Secure Boot ON — no DKMS drivers). Reached
  over tailscale (`ssh kxkm-ai`, user `kxkm`) or LAN `10.2.0.237`.
  Linux only. Do not propose Windows paths (`WINDOWS.md` = emergency
  fallback, unmaintained).
- The machine is SHARED: ComfyUI, a whisper worker for the hub, VoiceClone,
  a TTS server and other people's LLM launchers live on it. The booth
  cohabits under the `kxkm` account in `/ai/VideoBooth` and never touches
  those installs. `tools/showmode.sh on` stops the GPU tenants for a show
  and `off` restores them. The GPU runs nothing else DURING a show.
- Root is Thomas's: scripts in `setup/` that need sudo are run by him
  (`! ssh -t kxkm-ai sudo …`); everything else runs as `kxkm`.
- Display: 55" TV on the 4090's HDMI, mounted PORTRAIT (native resolution
  to be confirmed; generation resolution does not change). Today a 27" 4K
  desk monitor is on HDMI-A-2 and serves for the bench. GDM + Xorg,
  autologin `kxkm`, Google Chrome kiosk (systemd user unit).
- Camera, primary: Logitech Brio 4K (new generation, UVC) on USB, arriving
  week of 2026-09-07. 30 fps, fixed position, fixed framing, person fills
  the portrait frame. Until it arrives the cheap USB webcam already on
  `/dev/video0` serves for the pipeline bench. Fallbacks (Panasonic / Sony
  a7 over an HDMI capture card) only if the Brio fails on look or fps.
- Camera, secondary (later): phone browser → WebRTC into the same server.
- Network: machine on Ethernet + tailscale. Only the technician UI is
  reached over the network; the display is local for phase 1. Because both
  engines render through a browser page, a second LAN machine can show the
  output as a bonus, never as the primary display.

## 4. Stack — two candidate engines, decided by measurement in Phase 1

Both engines share: the same camera, a depth preprocessor (Depth Anything
family, run INSIDE each engine — never two depth models on the GPU at
once), the same kiosk output on HDMI, the same preset JSON format. Only the
generation core differs.

### Engine A — temporally coherent (video model)
- Daydream Scope (github.com/daydreamlive/scope, docs.daydream.live/scope):
  pipeline server + browser UI on :8000, WebRTC in/out, NDI out, OSC and
  HTTP control. Linux = source install (`uv run build`, `uv run
  daydream-scope`); the desktop app is Windows/macOS only. Alpha, license
  CC BY-NC-SA 4.0 (fine: non-commercial booth).
- Pipeline baseline: **LongLive** (Wan 2.1 1.3B, ~20 GB VRAM) with
  **VACE depth control** via the built-in `video-depth-anything`
  preprocessor. StreamDiffusionV2 is kept for the bare speed test only:
  the Scope docs state VACE quality on SDV2 is poor. RewardForcing / MemFlow
  are alternates on the same weights. Never Krea Realtime (≥ 32 GB VRAM).
- Tiny VAE / frame interpolation as the UI exposes them.
- Expected: ~10–13 fps at 480×832, 1 step, ~0.7–1.2 s latency, coherent
  motion, autoregressive drift usable as a dial (reset button required).

### Engine B — per-image (image model, fastest, lowest latency)
- StreamDiffusion, the maintained Daydream fork
  (github.com/daydreamlive/StreamDiffusion — the livepeer fork is archived
  since 2025-12): multi-ControlNet, IP-Adapter, LoRA, TensorRT, built-in
  `depth` / `depth_tensorrt` preprocessors, `demo/realtime-img2img`
  browser UI on :7860 as the base technician UI. Apache-2.0.
- Model: SD1.5 + LCM (1–2 steps) as first candidate — the SD1.5 depth
  ControlNet, LCM Dreamshaper and SD-Turbo / SDXL-Lightning checkpoints are
  ALREADY on the machine (`/ai/data/models`). SD-Turbo is SD2.1-based and
  needs its own ControlNet; SDXL-Turbo second if the look justifies the fps.
- Control: depth ControlNet, fixed seed by default, denoise 0.5–0.7,
  stochastic similarity filter exposed as a dial.
- Expected: 20+ fps at 512×768 with depth ControlNet after the TensorRT
  engine build, ~0.3 s latency, frame-to-frame flicker.

### Decision rule
Run both on the same camera, same depth input, same three lighting setups,
real people moving. Score: latency constancy first, fps second, look
third. Record the decision and the numbers in `DECISION.md`. If B wins,
drop Scope entirely. If A wins, keep B's TensorRT engines around only if
they cost nothing to maintain.

## 5. Baseline configs (starting points, all dials live)

Engine A: 480×832 portrait · LongLive · VACE depth scale 0.8–0.9 · 1 step ·
v2v strength high · tiny VAE on · per-visitor stream restart button.

Engine B: 512×768 portrait (576×1024 if fps allows) · 1 step (2 as a
dial) · depth ControlNet scale 0.8–1.0 · denoise 0.5–0.7 · seed locked ·
similarity filter off · TensorRT engines built for exactly these sizes.
Config: `engines/b-streamdiffusion/booth_sd15_depth.yaml`.

Display upscale from generation size to the panel is done by the browser
(GPU-side). Do not add an AI upscaler in phase 1.

## 6. Aesthetic direction — where "freaky" comes from, in order

1. Control (depth) scale below 1.0: pose still locked, anatomy free to
   go wrong. The single best "borderline" dial.
2. Fewer steps, higher strength/denoise.
3. Engine B only: seed unlocked → per-frame flicker as a texture.
   Engine A only: accumulated drift before a reset.
4. The input feed: hard side light, colored gels, low-key booth, optional
   slow strobe. Depth estimation stays robust; appearance mutates.
   Lighting is a primary creative control, owned by the technician.
5. Prompts — least reliable. Generic "grotesque/uncanny" prompts give
   cliché AI-horror. A house style comes from a LoRA (later phase).

"Clean" is the same dials the other way: 2–4 steps, control scale 1.0,
seed locked, aesthetic negatives on, interpolation on (Engine A).

Prompt presets live in `presets/heroes.json`: name, prompt, negative
(safety terms always present), control_scale, strength, steps, seed_lock,
notes. Presets must be switchable from the UI without restart.

## 7. Explicitly rejected — do not propose

- ComfyUI / ComfyStream (previous prototype; replaced). ComfyUI stays
  installed on the machine for other work — it is simply stopped for shows.
- FLUX or any model that cannot reach ≥ 10 fps on a 4090 at ~512p.
- Native generation above ~576p on one 4090.
- Krea Realtime (VRAM).
- Any visitor-facing UI, tablet, or automatic attribute detection.
- Cloud / RunPod. Everything runs on the local machine.
- Windows install scripts (see §3).

## 8. Use context

Non-commercial: festival demo booth by a non-commercial entity (KXKM).
Model or LoRA licenses are not a selection constraint. Public audience
including children: rule 2.7 applies regardless.

## 9. Repo layout

```
VideoBooth/
  CLAUDE.md               this brief
  ROADMAP.md              status, decisions, phases, deviations, risks
  README.md               operator-facing: start a show, dials, presets, resets
  INSTALL.md              step-by-step install on kxkm-ai (root part / user part)
  WINDOWS.md              emergency fallback pointers only
  BENCHMARKS.md           every perf measurement, dated, exact config
  DECISION.md             A vs B result and reasoning
  setup/                  idempotent scripts: 00 audit · 01 driver fix (root) ·
                          02 prereqs (root) · 10 engine B · 20 engine A · 99 verify
  tools/                  showmode.sh · camera_check.sh · fps_probe.py (DevTools) ·
                          cdp.py · latency test protocol
  kiosk/                  Chrome kiosk launcher + systemd user unit + portrait setup
  engines/a-scope/        Scope notes, settings to use, dial mapping
  engines/b-streamdiffusion/  StreamDiffusion config (depth ControlNet), dial mapping
  presets/heroes.json     technician prompt presets
  .engines/ .hf/          (gitignored) upstream checkouts, venvs, model caches
```

On the machine the clone lives at `/ai/VideoBooth`; `setup/env.sh` is the
single place for paths.

## 10. Phase 1 — kickoff tasks, in this order, stop after each

0. Driver repair + reboot (Thomas, root): `setup/01_driver_fix.sh`. The
   userspace driver was auto-upgraded to 580.173 while the running kernel
   module is 580.159 and the newest installed kernel has NO NVIDIA module
   on disk. Nothing GPU-related starts before this is green.
1. Machine audit: `setup/00_audit.sh`. Report; install nothing yet.
2. Prereqs (Thomas, root): `setup/02_root_prereqs.sh` — Chrome, build
   deps, `video` group, GDM autologin, unattended-upgrade blacklist.
3. Camera audit: `tools/camera_check.sh`, first with the USB webcam
   already on the box, again with the Brio when it arrives (30 fps
   confirmed, MJPEG vs YUY2 noted).
4. Engine B install: `setup/10_engine_b.sh` (uv venv Python 3.10, torch
   cu128, the Daydream fork with tensorrt+controlnet extras, TensorRT,
   engines built for 512×768). No new checkpoints needed. Then baseline:
   camera in, depth ControlNet, 1 step, seed locked, ≥ 2 min with a moving
   person → `BENCHMARKS.md` (fps + frame-time variance via
   `tools/fps_probe.py`).
5. Engine A install: `setup/20_engine_a.sh` per CURRENT Scope docs (read
   them first; versions change weekly). Ask before any download > 10 GB.
   Baseline: LongLive, camera in, no VACE, 480×832, 1 step. Measure. Then
   VACE depth on, re-measure. SDV2 bare once, for the number.
6. Glass-to-glass latency test for both (`tools/LATENCY.md` protocol).
   Latency mean AND spread → `BENCHMARKS.md`.
7. Kiosk: `kiosk/` — Chrome `--kiosk` on the HDMI output, portrait, pointed
   at whichever engine's output page; systemd user unit; auto-start on
   login; survives an engine restart.
8. A/B session on real people under three lighting setups (Brio). Write
   `DECISION.md`. Everything after this targets one engine.
9. Dials (rule 2.4) verified live in the chosen UI; extend the UI where a
   dial is missing. `presets/heroes.json` with 5 starter heroes.
10. Operator `README.md`: start, stop, per-visitor reset, switch preset,
    clean↔freaky quick guide, what to do when it stalls.

Later phases (not now): style LoRA on house references; hero-shot
high-res still on a button; NDI / WebRTC output to a remote display (Scope
has NDI out; Hemisphere's HNdi can receive it on a mini-PC kiosk);
phone-as-camera via WebRTC; a second 4090 only if measured fps demands it.

## 11. Working rules

- Verify against current upstream docs before writing install commands
  or config keys. Do not invent flags, parameter names or pipeline IDs.
  If a feature described here does not exist in the installed version,
  say so and propose the closest real thing.
- Measure before and after every performance-relevant change; log both
  in `BENCHMARKS.md` with the exact config.
- One change at a time. Keep the baseline configs (section 5) unless a
  measurement forces a change, and then say why.
- Everything reproducible: scripts in the repo, `setup/` re-runnable on a
  fresh Ubuntu 24.04 install.
- Never expose the technician UI beyond the LAN / tailnet.
- Never stop, edit or "clean up" other tenants' services on kxkm-ai except
  through `tools/showmode.sh`, which records what it stopped and restores
  exactly that.
- Remote work: feed scripts as `ssh kxkm-ai 'bash -s' <<'EOF' … EOF`; never
  put a `pkill -f <pattern>` inline in an ssh argv (it kills the ssh shell).
- Keep replies short and concrete: what was done, what was measured,
  what is blocked. No optimism about untested steps.
- Hub: this project is `videobooth` in 37Projects (org KXKM). Commits that
  close a task carry `Refs-37: videobooth#t-NNN [done]`.

## 12. Numbers in this brief that are estimates, to be replaced by measurements

- Engine A: ~16 fps bare SDV2 at 480p on a 4090 (paper, bf16); VACE adds
  ~20–30 % latency (VACE-streaming paper); LongLive similar class.
- Engine B: ~90 fps single-step SD-Turbo at 512² raw (StreamDiffusion
  paper); ~14–15 fps SD1.5-LCM + depth ControlNet at higher res on a 4090
  (community workflow). Our 512×768 + depth is expected 20+ fps.
- Depth preprocessing ~5–10 ms/frame. Interpolation ~+100 ms latency.
- Glass-to-glass: A ~0.7–1.2 s, B ~0.3 s. Measure both (step 6).

## 13. Operator facts

- Camera model: Logitech Brio 4K new gen (ordered, due week of 2026-09-07).
  Capture card: none in phase 1.
- Display: 55" TV portrait, model / native resolution: ______ (bench today
  on a Samsung LS27D80xE 27" 4K).
- Machine: kxkm-ai, Ubuntu 24.04.4, tailscale `100.87.54.119`, LAN
  `10.2.0.237`, technician UI ports :7860 (B) / :8000 (A).
- Festival / date: ______
