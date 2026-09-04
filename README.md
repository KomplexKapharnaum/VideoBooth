# VideoBooth

Real-time "superhero twin" booth for a KXKM festival. A visitor stands in front of a
fixed camera; a 55" portrait screen shows a generated superhero that copies their pose
with a short, constant delay. One machine (RTX 4090), one camera (Logitech Brio 4K), a
browser in kiosk mode, and a diffusion engine picked by measurement.

```
Brio 4K ─USB─▶ kiosk Chromium (camera + display, --kiosk, portrait 55")
                  │ WebRTC                       ▲ WebRTC
                  ▼                              │
        engine server on the same 4090: Scope (:8000)  or  StreamDiffusion (:7860)
        depth preprocessor → 1–2 step diffusion → video
        technician: engine web UI from a laptop on the LAN — dials, presets, reset
```

> **Status (2026-09-04):** repo and plan; nothing measured yet. Blocker: the GPU driver
> on the machine needs a repair + reboot (root). See [ROADMAP.md](ROADMAP.md).

- **Brief and rules** (read first): [CLAUDE.md](CLAUDE.md)
- **Plan, decisions, deviations, risks**: [ROADMAP.md](ROADMAP.md)
- **Install on kxkm-ai**: [INSTALL.md](INSTALL.md) · Windows emergency notes: [WINDOWS.md](WINDOWS.md)
- **Measurements**: [BENCHMARKS.md](BENCHMARKS.md) · **engine choice**: [DECISION.md](DECISION.md)
- **Presets**: [presets/heroes.json](presets/heroes.json)

## Operating a show (to be completed after Phase 2)

| | |
|---|---|
| Free the GPU | `tools/showmode.sh on` (stops ComfyUI, the whisper worker, VoiceClone, TTS, LLM launchers) |
| Start the engine | `engines/b-streamdiffusion/run.sh` or `engines/a-scope/run.sh` |
| Screen | kiosk starts with the session (`systemctl --user status booth-kiosk`); URL in `booth.conf` |
| Dials | the engine UI from your laptop: steps, strength, depth control scale, negatives, seed lock, interpolation |
| Presets | `presets/heroes.json` — "Chrome Sentinel" is the clean reference, "Neon Wraith" the freaky end |
| Per-visitor reset | engine reset button (Scope: stream restart) |
| Stall | engine restart; the kiosk reconnects by itself |
| After the show | `tools/showmode.sh off` restores the other services |

## Repo map
`setup/` install scripts (00 audit · 01 driver fix · 02 prereqs · 10 engine B · 20 engine A · 99 verify) ·
`tools/` show mode, camera check, fps/jitter probe, latency protocol ·
`kiosk/` Chromium kiosk + systemd user unit · `engines/` per-engine config, run script and dial map.

License: GPL-3.0. Engines keep their own licenses (Scope CC BY-NC-SA 4.0, StreamDiffusion Apache-2.0).
