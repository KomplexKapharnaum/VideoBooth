# Engine B — StreamDiffusion (Daydream fork) + depth ControlNet + TensorRT

Repo https://github.com/daydreamlive/StreamDiffusion (Apache-2.0; the livepeer fork
named in the first brief is archived since 2025-12). Installed by
`setup/10_engine_b.sh` into `.engines/StreamDiffusion` with a Python 3.10 venv. The
technician UI is the fork's `demo/realtime-img2img` (browser, `:7860`, WebRTC/WebSocket
streaming; the page captures the camera and shows the output).

## Run
`engines/b-streamdiffusion/run.sh` → `python main.py --acceleration tensorrt
--controlnet-config booth_sd15_depth.yaml --host 0.0.0.0 --port 7860 --engine-dir
.engines/trt` (flags per the demo README). The first start builds the TensorRT engines
for the sizes in the config (minutes). Kiosk: `KIOSK_URL=http://127.0.0.1:7860`.

## Config — `booth_sd15_depth.yaml` (baseline, CLAUDE.md §5)
Keys follow `configs/sd15_multicontrol.yaml.example` in the fork. Starting points:
- `model_id` SD1.5-LCM (`SimianLuo/LCM_Dreamshaper_v7`; the same checkpoint exists locally
  at `/ai/data/models/checkpoints/LCM_Dreamshaper_v7_4k.safetensors`), `scheduler: lcm`.
- 512×768 portrait, `use_tiny_vae: true`, `acceleration: tensorrt`.
- `t_index_list` sets steps AND strength: one entry = 1 step; a LOWER index = more noise
  = stronger stylization. `[24]` ≈ denoise 0.5 one step, `[18, 32]` two steps. Tune by
  eye, log in BENCHMARKS.md.
- ControlNet `lllyasviel/control_v11f1p_sd15_depth` (local copy in
  `/ai/data/models/controlnet/`), `conditioning_scale` 0.8–1.0, preprocessor `depth`
  first (HF model, `model_name` per `configs/_preprocessor_reference.yaml.example`), then
  `depth_tensorrt` with an `engine_path` once the fps baseline exists.
- Fixed `seed`; `guidance_scale: 1.0` (LCM, no CFG).
- SD-Turbo is SD2.1-based: it needs an SD2.1 depth ControlNet, not the SD1.5 one. Try only
  if the LCM look disappoints (see `configs/sdturbo_multicontrol.yaml.example`).

## Dial mapping (brief rule 2.4) — to fill during Phase 1
| dial | demo control / config key | live without restart? |
|---|---|---|
| steps | `t_index_list` length | |
| strength / denoise | `t_index_list` values | |
| control (depth) scale | `conditioning_scale` | |
| negative prompt on/off | `negative_prompt` | |
| seed lock | `seed` | |
| similarity filter | `similar_image_filter_*` (verify names) | |
