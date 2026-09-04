# Booth patches on the StreamDiffusion demo

Applied by `setup/10_engine_b.sh` to `.engines/StreamDiffusion` with `git apply` (idempotent:
already-applied patches are skipped). Keep them tiny and explain each one here.

- **0001-live-negative-prompt.patch** — `POST /api/params` accepts `negative_prompt`. The
  library's `update_stream_params()` already takes it (re-encodes the prompt embeddings, no
  rebuild) and the demo's `AppState.update_parameter('negative_prompt')` exists, but no route
  forwarded it: changing the negative meant re-uploading the config, which destroys and
  rebuilds the pipeline (~20 s black) — this is why switching presets stalled Engine B. Two
  lines. The panel uses the live route and falls back to the re-upload only on an unpatched demo.

Regenerate after editing the checkout: `git diff -- <file> > patches/NNNN-name.patch`.
