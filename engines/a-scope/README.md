# Engine A — Daydream Scope

Source install on Linux (`setup/20_engine_a.sh`), browser UI on `:8000`, WebRTC in/out,
NDI out, OSC + HTTP API. Docs: https://docs.daydream.live/scope · repo
https://github.com/daydreamlive/scope (alpha, CC BY-NC-SA 4.0 — fine for this
non-commercial booth). Read the docs again before each install: they change weekly.

## Run
`engines/a-scope/run.sh` → `uv run daydream-scope` in the checkout. First run downloads
the pipeline weights into `~/.daydream-scope/models` (> 10 GB: ask first). Point the
kiosk at the output page (`KIOSK_URL=http://127.0.0.1:8000`, exact path to be confirmed
in the UI) and the technician's laptop at the same UI over the LAN / tailnet.

## Settings to use (baseline, CLAUDE.md §5)
- Pipeline **LongLive** (Wan 2.1 1.3B, ~20 GB VRAM). VACE **On** in Settings, control
  video = live camera through the built-in **`video-depth-anything`** preprocessor
  (~1 GB VRAM). VACE scale 0.8–0.9. Resolution 480×832 portrait (the model is trained at
  832×480; portrait orientation to be confirmed in the UI). 1 denoising step.
- Also measure: StreamDiffusionV2 bare (no VACE — the docs say VACE quality on SDV2 is
  poor), RewardForcing and MemFlow with VACE as alternates on the same weights.
- Frame interpolation and tiny VAE as the UI exposes them; note the exact names.

## Dial mapping (brief rule 2.4) — to fill during Phase 1
| dial | Scope setting | live without restart? |
|---|---|---|
| steps | | |
| v2v strength / denoise | | |
| control (depth) scale | VACE scale | |
| negative prompt on/off | | |
| seed lock | | |
| interpolation on/off | | |
| coherence / drift reset | per-visitor stream restart | |

## Remote control
OSC is native (prompt, intensity, pipeline settings); the auto-generated docs page in the
UI has API starter code. This is how the technician drives the kiosk's session from a
laptop if two browser pages cannot share one stream (ROADMAP risk).
