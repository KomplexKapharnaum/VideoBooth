# Decision — Engine A (Scope) vs Engine B (StreamDiffusion)

_Taken 2026-09-21, on the 2026-09-04 bench alone — the Phase 2 A/B session (Brio, real
people, three lighting setups) was cancelled, not run. Score order: latency constancy, then
fps, then look._

| Criterion | Engine A (Scope, LongLive + VACE) | Engine B (StreamDiffusion, SD1.5-LCM + depth CN) |
|---|---|---|
| Frame-interval p95 / max (ms) | 1943 / 2031 (VACE), 1577 / 1612 (bare) — 12-frame bursts | 28 / 103 (engine), 45 / 50 (presented on the kiosk) |
| Stalls > 250 ms per 2 min | ~70 (one per block) | 0 |
| fps at baseline | 5.7 (VACE), 7.0 (bare) | 33–37 engine, 33 presented |
| Glass-to-glass mean ± spread (s) | not measured; ≥ 1.6–2 s by construction (block cadence) | not measured; engine-side 0.13 s ± 0.04 |
| Pose legibility (3 lightings) | not tested (clip only) | not tested (clip / desk webcam only) |
| Look: clean end / freaky end | bare v2v stylises strongly (chrome hero painted over the test pattern); VACE from the raw video returns the input — depth-node graph untested; temporal coherence is its strength | per-frame chrome-armour look following the input structures, flicker as texture |
| Dials available live | noise_scale, steps, VACE scale, cache reset, kv bias, LoRA (API/OSC/UI) | strength (t_index), steps, CN scale, seed, similarity filter (UI/API) |
| Operational risk (alpha, restarts, VRAM) | alpha; ~22 GB VRAM, exclusive GPU; block cadence | 4 upstream traps fixed; ~5 GB VRAM; single-threaded server (one stream) |

## Result

**Engine B — StreamDiffusion, SD1.5-LCM + depth ControlNet + TensorRT.** Engine A (Scope) is
dropped for the show (brief §4).

_On the 2026-09-04 bench, engine-side numbers only:_ **Engine B leads on the two criteria
that come first** (latency constancy, fps) by a wide margin — 33–37 fps, 28 ms p95 frame
interval, 0 stalls per 2 min, against Engine A's 5.7–7.0 fps delivered in ~12-frame bursts,
1.6–1.9 s p95 interval and ~70 stalls per 2 min. Engine A's block-wise generation makes a
constant ~1 s delay impossible at 480x832 on one 4090. Re-measured at 37.2 fps on the
production box (kxkm-ai2) on 2026-09-11, once the CPU caps were lifted.

**What this decision does NOT rest on.** The A/B session was the method for the two remaining
criteria, and it was cancelled on 2026-09-20 rather than run:

- **Pose legibility under three lightings — never measured**, on either engine. Nobody has
  seen a real face go through either pipeline on the 55" panel.
- **Glass-to-glass latency — never measured**, on either engine. The 0.13 s ± 0.04 above is
  engine-side only: camera, display and compositing are not in it.
- **The hero presets ship untuned** — `presets/heroes.json` is still the 2026-09-04 scaffold.

Those three stay open by choice, not by oversight: the show is 2026-09-24 and the remaining
days went to the physical setup instead. Read the "not measured" / "not tested" rows above as
final for this show, not as pending work.

_engine: **B** · date: **2026-09-21** · reasoning: **latency constancy, then fps, on the
2026-09-04 bench; the A/B session that would have added look and pose legibility was
cancelled**_
