# Tuning — the dials, presets and configs

The technician owns the look. "Clean" and "freaky" are two ends of the same dials (brief §5–6),
not two configs. This page says what each dial does, where it lives, and what to measure after
touching it.

The **technician panel** (`http://<box>:7870`, `panel/`) exposes the dials below for the
engine shown on the kiosk, applies presets, and previews the visitor screen. Every dial is
live, the negative prompt included (a two-line booth patch on the demo,
`engines/b-streamdiffusion/patches/`); without that patch a negative change rebuilds the
pipeline (~20 s black).

## 1. The dials (brief rule 2.4)

| Dial | Effect | Engine B (StreamDiffusion) | Engine A (Scope) |
|---|---|---|---|
| **Depth control scale** | how hard the pose is locked. 1.0 = anatomy follows the depth map; < 1.0 = pose still readable, anatomy free to go wrong — **the best "borderline" dial** | UI ControlNet strength; yaml `controlnets[0].conditioning_scale` (0.8–1.0 baseline) | VACE scale (0.8–0.9 baseline) |
| **Steps** | more steps = cleaner, slower | number of entries in `t_index_list` (1 = one step); UI where exposed | steps setting |
| **Strength / denoise** | how far from the camera pixels | the *values* in `t_index_list`: lower index = more noise = stronger change (`[24]` ≈ 0.5 one-step, `[18, 32]` two-step) | v2v strength |
| **Seed lock** | fixed seed = calm; per-frame seed = flicker as texture | `seed` fixed / UI seed | seed |
| **Negative prompt** | safety terms ALWAYS stay; aesthetic terms ("ugly, deformed") on = clean, off = freaky | `negative_prompt` (live with the booth patch) | negative prompt |
| **Similarity filter** | freezes output while the input is static (saves GPU, can look dead) | `enable_similar_image_filter` + threshold (off at baseline) | — |
| **Interpolation** | smoother motion, +latency | — | frame interpolation toggle |
| **Reset** | per-visitor: forget the previous person | none needed (no memory) | stream restart button |
| **Resolution** | fps vs detail; TensorRT rebuild | `width` / `height` (512x768 baseline, 576x1024 if fps allows) | 480x832 |

Aesthetic direction, in order of reliability: depth scale < 1.0 → fewer steps / more strength
→ seed unlock (B) or drift (A) → **lighting of the input feed** (hard side light, gels, low key:
depth stays robust, appearance mutates) → prompts, last. Generic "grotesque" prompts give
cliché AI-horror; a house style will come from a LoRA later.

All Engine B dials are **global**: the demo's sliders call `POST /api/params` on the server
and change the one pipeline that serves every page, so a laptop page controls what the kiosk
shows (without starting its own stream). Scope has one session: its UI, OSC, or
`POST /api/v1/session/parameters` (`noise_scale`, `denoising_step_list`, `vace_enabled`,
`vace_context_scale`, `reset_cache`, `output_sinks` for NDI).

## 2. Presets — `presets/heroes.json`

One JSON, engine-independent. Fields: `name`, `prompt`, `negative` (must contain the safety
terms), `control_scale`, `strength`, `steps`, `seed_lock`, `notes`. Five starters ship;
"Chrome Sentinel (clean)" is the reference for pose-legibility checks, "Neon Wraith" the
freaky end.

Adding a hero from the panel: set the prompt, negative and knobs, try it on a moving person,
type a name and a note, "Save as NEW". Refine a loaded one and "Update" (confirm). The live
file is `.state/presets.json` on the box; `presets/heroes.json` in the repo is the committed
set of defaults — copy the live file back into the repo and commit when a set is worth
keeping for the next install. Keep `control_scale` 0.75–1.0, `strength` 0.5–0.7, `steps` 1–3.

## 3. Engine B config — `engines/b-streamdiffusion/booth_sd15_depth.yaml`

Keys follow the fork's `configs/sd15_multicontrol.yaml.example` and `src/streamdiffusion/config.py`.
`run.sh` uploads it to the server after start (the demo applies configs only through its
upload endpoint); after editing it, `engines/b-streamdiffusion/apply_config.sh` reloads it
live — the pipeline rebuilds on the next stream, TensorRT engines only if model or
resolution changed. Dials changed in the UI do not write back to the file.

| Key | Baseline | Notes |
|---|---|---|
| `model_id` | `SimianLuo/LCM_Dreamshaper_v7` | SD1.5 + LCM, 1–2 steps. Local copy: `/ai/data/models/checkpoints/LCM_Dreamshaper_v7_4k.safetensors`. Any SD1.5 checkpoint works with the same ControlNet; **SD-Turbo is SD2.1-based** and needs `thibaud/controlnet-sd21-depth-diffusers`; SDXL-Turbo needs the SDXL depth ControlNet and a TensorRT rebuild |
| `t_index_list` | `[24]` | steps + strength, see §1. Indices run 0 (pure noise) → 49 (almost the input) |
| `width`, `height` | 512, 768 | portrait 2:3. Change → TensorRT rebuild at next start (minutes). The UI resolution menu must match |
| `guidance_scale` | 1.0 | LCM: no CFG. `cfg_type: "self"` |
| `seed` | 42 | fixed = seed lock |
| `delta` | 0.7 | StreamDiffusion's residual-noise knob (temporal "stickiness"); 1.0 = none |
| `use_tiny_vae` | true | TAESD decode; off = slower, cleaner |
| `acceleration` | `tensorrt` | the only real-time option here; `engine_dir` must equal `SD_TRT_ENGINES` |
| `enable_similar_image_filter` | false | dial; threshold 0.98, `max_skip_frame` 10 |
| `controlnets[0]` | depth CN, scale 0.9, `depth_tensorrt` | engine built by `engines/b-streamdiffusion/build_depth_engine.py` (Depth Anything V2 small, 518²). The plain `depth` preprocessor is a CPU DPT model — not real-time |
| `use_ipadapter` | false | style transfer from an image; later, costs fps |
| `lora_dict` | — | `{"path/or/hf-id": weight}` for a house-style LoRA (later phase) |

Adding a second ControlNet (e.g. OpenPose, weights already in `/ai/data/models/controlnet/`)
is another `controlnets:` entry — expect fps to drop; measure.

## 4. Engine A settings — Scope (v0.2.5, verified names)

Pipeline **longlive**. **Load params** (`POST /api/v1/pipeline/load`, a reload each time they
change): `height`/`width` (480x832 for the booth; the model is trained at 832x480),
`vae_type` (`wan` full, `lightvae`, `tae` tiny, `lighttae`), `denoising_steps` (timestep
schedule, default `[1000, 750, 500, 250]`; `[1000]` = one step — measured: no rate change),
`base_seed`, `quantization` (`fp8_e4m3fn` or none), `vace_enabled` + `vace_context_scale`.
**Session params** (`POST /api/v1/session/parameters`, live): `noise_scale` (v2v strength,
default 0.7), `noise_controller` (auto by motion), `denoising_step_list`, `vace_enabled`,
`vace_use_input_video` (raw video as control — reproduces the input; use a depth node in a
graph for pose control), `vace_context_scale`, `reset_cache` (per-visitor reset),
`kv_cache_attention_bias` (pipelines that support it), `lora_scales`, `output_sinks` (`ndi`).
The UI exposes the same; OSC too. `tools/engine_a_probe.py` sets them from the command
line for a bench. Measured 2026-09-04: LongLive delivers ~12 frames per block every
1.6–1.9 s — read BENCHMARKS.md before spending time on Engine A dials.

## 5. The rule after every change

1. Change **one** thing.
2. Run the probe (B: `tools/engine_b_probe.py`; A: `tools/fps_probe.py` on the kiosk) for at
   least 60 s with a moving person or the flashing synthetic source.
3. Paste the row into `BENCHMARKS.md` with the setting, before and after.
4. If latency **spread** or stalls got worse, the change loses — however good it looks
   (brief rule 2.2).

## 6. Safety and taste boundaries

- The safety negatives (`nudity, naked, nsfw, sexual, explicit, gore, blood, wounds,
  mutilation`) stay in every preset and every live edit. Families are in front of the screen.
- No prompts or models that classify the visitor (gender, age, skin tone). The pipeline carries
  the camera pixels; that is how identity survives, by construction.
- "Freaky" is anatomy, texture and light — never violence.
