# Windows — emergency fallback only

The booth is built and tested on Ubuntu 24.04 (kxkm-ai). If the production machine has
to become a Windows box with an RTX 4090, this is the untested, unmaintained path.
Nothing in `setup/`, `tools/` or `kiosk/` runs on Windows.

- **Engine A (Scope)**: Daydream ships a Windows desktop app (installer on
  github.com/daydreamlive/scope releases / docs.daydream.live/scope). Same pipelines,
  same browser UI on :8000, Spout output available on Windows. Copy the settings noted
  in `engines/a-scope/README.md` by hand.
- **Engine B (StreamDiffusion)**: the Daydream fork documents a Windows install
  (Python 3.10, CUDA 12.8 torch wheels, TensorRT via the same installer module). Use
  `engines/b-streamdiffusion/booth_sd15_depth.yaml` unchanged; rebuild the TensorRT
  engines on the new GPU.
- **Kiosk**: Chrome `--kiosk --auto-accept-camera-and-microphone-capture` from a
  shortcut in the Startup folder; portrait rotation in Windows display settings.
- **Presets**: `presets/heroes.json` is engine- and OS-independent.

Expect a full day to bring a Windows box to the state `setup/99_verify.sh` checks on
Linux. Re-run the benchmarks; the numbers in `BENCHMARKS.md` do not carry over.
