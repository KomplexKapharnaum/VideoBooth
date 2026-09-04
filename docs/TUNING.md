# Tuning — the dials, presets and configs

The technician owns the look. "Clean" and "freaky" are two ends of the same dials (brief §5–6),
not two configs. This page says what each dial does, where it lives, and what to measure after
touching it.

## 1. The dials (brief rule 2.4)

| Dial | Effect | Engine B (StreamDiffusion) | Engine A (Scope) |
|---|---|---|---|
| **Depth control scale** | how hard the pose is locked. 1.0 = anatomy follows the depth map; < 1.0 = pose still readable, anatomy free to go wrong — **the best "borderline" dial** | UI ControlNet strength; yaml `controlnets[0].conditioning_scale` (0.8–1.0 baseline) | VACE scale (0.8–0.9 baseline) |
| **Steps** | more steps = cleaner, slower | number of entries in `t_index_list` (1 = one step); UI where exposed | steps setting |
| **Strength / denoise** | how far from the camera pixels | the *values* in `t_index_list`: lower index = more noise = stronger change (`[24]` ≈ 0.5 one-step, `[18, 32]` two-step) | v2v strength |
| **Seed lock** | fixed seed = calm; per-frame seed = flicker as texture | `seed` fixed / UI seed | seed |
| **Negative prompt** | safety terms ALWAYS stay; aesthetic terms ("ugly, deformed") on = clean, off = freaky | `negative_prompt` | negative prompt |
| **Similarity filter** | freezes output while the input is static (saves GPU, can look dead) | `enable_similar_image_filter` + threshold (off at baseline) | — |
| **Interpolation** | smoother motion, +latency | — | frame interpolation toggle |
| **Reset** | per-visitor: forget the previous person | none needed (no memory) | stream restart button |
| **Resolution** | fps vs detail; TensorRT rebuild | `width` / `height` (512x768 baseline, 576x1024 if fps allows) | 480x832 |

Aesthetic direction, in order of reliability: depth scale < 1.0 → fewer steps / more strength
→ seed unlock (B) or drift (A) → **lighting of the input feed** (hard side light, gels, low key:
depth stays robust, appearance mutates) → prompts, last. Generic "grotesque" prompts give
cliché AI-horror; a house style will come from a LoRA later.

## 2. Presets — `presets/heroes.json`

One JSON, engine-independent. Fields: `name`, `prompt`, `negative` (must contain the safety
terms), `control_scale`, `strength`, `steps`, `seed_lock`, `notes`. Five starters ship;
"Chrome Sentinel (clean)" is the reference for pose-legibility checks, "Neon Wraith" the
freaky end.

Adding a hero: copy a block, keep `_safety_negative` in `negative`, pick `control_scale`
0.75–1.0, `strength` 0.5–0.7, `steps` 1–3, then **try it on a moving person** and write one
line of `notes` (what it is for, which lighting). Until the engine UI loads presets directly
(Phase 2 work), presets are applied by hand in the UI: prompt, negative, ControlNet strength,
steps, seed.

## 3. Engine B config — `engines/b-streamdiffusion/booth_sd15_depth.yaml`

Keys follow the fork's `configs/sd15_multicontrol.yaml.example` and `src/streamdiffusion/config.py`.
The server reads it **at start** (`run.sh --controlnet-config`); dials changed in the UI do not
write back to it — edit the file for new defaults.

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

## 4. Engine A settings — Scope UI

Pipeline **LongLive**, VACE **On**, control video = camera through the built-in
`video-depth-anything` preprocessor, resolution 480x832, 1 step, tiny VAE on. StreamDiffusionV2
only for the bare-speed number (its docs say VACE quality on it is poor). Exact setting names
are filled into `engines/a-scope/README.md` during Phase 1. Scope accepts OSC and an HTTP API
for live parameter control — the way a laptop drives the kiosk's session.

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
