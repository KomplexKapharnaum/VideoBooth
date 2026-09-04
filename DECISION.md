# Decision — Engine A (Scope) vs Engine B (StreamDiffusion)

_Not taken yet. Filled after the Phase 2 A/B session (Brio, real people, three lighting
setups). Score order: latency constancy, then fps, then look._

| Criterion | Engine A (Scope, LongLive + VACE) | Engine B (StreamDiffusion, SD1.5-LCM + depth CN) |
|---|---|---|
| Frame-interval p95 / max (ms) | 1943 / 2031 (VACE), 1577 / 1612 (bare) — 12-frame bursts | 28 / 103 (engine), 45 / 50 (presented on the kiosk) |
| Stalls > 250 ms per 2 min | ~70 (one per block) | 0 |
| fps at baseline | 5.7 (VACE), 7.0 (bare) | 33–37 engine, 33 presented |
| Glass-to-glass mean ± spread (s) | not measured; ≥ 1.6–2 s by construction (block cadence) | not measured; engine-side 0.13 s ± 0.04 |
| Pose legibility (3 lightings) | not tested (clip only) | not tested (clip / desk webcam only) |
| Look: clean end / freaky end | coherent stylised figure (one frame seen); temporal coherence is its strength | per-frame chrome-armour look, flicker as texture |
| Dials available live | noise_scale, steps, VACE scale, cache reset, kv bias, LoRA (API/OSC/UI) | strength (t_index), steps, CN scale, seed, similarity filter (UI/API) |
| Operational risk (alpha, restarts, VRAM) | alpha; ~22 GB VRAM, exclusive GPU; block cadence | 4 upstream traps fixed; ~5 GB VRAM; single-threaded server (one stream) |

## Result

_Preliminary, 2026-09-04, engine-side numbers only:_ **Engine B leads on the two criteria
that come first** (latency constancy, fps) by a wide margin; Engine A's block-wise
generation makes a constant ~1 s delay impossible at 480x832 on one 4090. The look
criterion and pose legibility on real people under three lightings (t-009, with the Brio)
are still open — that session decides. If it confirms B, Scope is dropped (brief §4); if
A's coherence is judged essential, the price is a delay that wanders by up to two seconds.

_engine: ___ · date: ___ · reasoning:_
