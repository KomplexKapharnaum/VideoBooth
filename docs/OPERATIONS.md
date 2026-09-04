# Operations run-book

Show day, rehearsals, and what to do when something is wrong. Everything here runs as `kxkm`
on the box unless marked **root**.

## Show day — from cold

```bash
ssh kxkm-ai && cd /ai/VideoBooth
setup/99_verify.sh                 # all PASS (engine A WARN is fine if B is the chosen engine)
tools/showmode.sh on               # stops ComfyUI, whisper worker, VoiceClone, TTS, LLM launchers; GPU must read "free"
tmux new -d -s booth-b engines/b-streamdiffusion/run.sh     # Engine B (or engines/a-scope/run.sh for A)
tail -f .state/logs/engine_b_server.log                      # wait for "Uvicorn running" / first frames
systemctl --user status booth-kiosk                          # kiosk up? else: systemctl --user restart booth-kiosk
tools/cdp.py --screenshot /tmp/k.png                         # what the TV shows (copy it to your laptop to look)
```

Then from the technician laptop: open the **panel `http://<box>:7870`** — preview of the
visitor screen, presets, prompt, knobs, show mode and engine buttons in one page (the
engines' own UIs stay available at `:7860` for B and `:8000` for A for anything the panel
does not expose). Pick the preset, check the pose link with someone moving in front of the
camera. **Engine B:
never press "Start Stream" on the laptop** — the kiosk page already streams; the sliders on
the laptop act on the shared pipeline. A second stream would interleave with the kiosk's
frames and halve the frame rate.

Before doors: run one probe and keep the row —
`.engines/StreamDiffusion/.venv/bin/python tools/engine_b_probe.py --source lavfi --seconds 60 --label "show-day check"`.
Numbers far from `BENCHMARKS.md` = something is wrong (another process on the GPU, thermal,
wrong resolution). Fix before doors, not after.

## During the show

**Switching engines** is one control in the panel ("Engine on the visitor screen": B or A).
It stops the other engine (GPU memory), loads the pipeline, points the screen at the right
page and reports progress; B → A takes 1–3 min, A → B about 1 min, the screen is black
meanwhile. Never click the raw start/stop buttons for a switch.

| Situation | Do |
|---|---|
| New visitor, twin still shows the previous one's "memory" (Engine A drift) | engine reset / stream restart in the UI (Engine A); Engine B has no memory |
| Picture frozen, page alive | the engine stalled: `tmux attach -t booth-b`, Ctrl-C, re-run `run.sh` — the kiosk page reconnects by itself |
| Black screen / browser gone | `systemctl --user restart booth-kiosk` |
| Camera lost (USB hiccup) | `tools/camera_check.sh`; replug; restart the kiosk (it re-opens the camera) |
| Latency wandering, fps down | `tools/showmode.sh status` → something else took the GPU → stop it; check `nvidia-smi` temperature/throttle |
| Look too clean / too freaky | the dials, see [TUNING.md](TUNING.md); never restart for a style change |

Logs: `.state/logs/engine_b_server.log`, `.state/logs/kiosk.log`, `journalctl --user -u booth-kiosk`.

## After the show

```bash
tools/showmode.sh off              # restores exactly the services "on" stopped
tmux kill-session -t booth-b       # optional; the engine idles at ~0 % GPU
```

The box goes back to being the research machine. Leave the kiosk unit enabled or disable it
(`systemctl --user disable --now booth-kiosk`) if the desk monitor is needed.

## Rehearsal checklist (once, before the festival week)

- [ ] Cold boot → GDM autologin → kiosk on the TV in portrait → engine page loads → picture
      within 2 min, no hands.
- [ ] `showmode on/off` round trip leaves every other service as it was (`status` before and
      after).
- [ ] 2-hour soak with a moving person; probe every 30 min; no stall > 250 ms, fps flat.
- [ ] Engine restart while the kiosk runs: picture back without touching the kiosk.
- [ ] Preset switch and every dial live, no restart.
- [ ] Glass-to-glass measured on the real TV (`tools/LATENCY.md`).

## Updating things

- **Repo**: `cd /ai/VideoBooth && git pull`. Safe while the engine runs (it read its config at
  start). Restart the engine to apply a config change.
- **Engines** (`.engines/`): pinned by `SD_REF` / `SCOPE_REF`. To bump: change the pin in
  `booth.conf`, re-run `setup/10_engine_b.sh` (or `20_engine_a.sh`), rebuild TensorRT engines
  on the first start, **measure**, record in `BENCHMARKS.md`. Not in show week.
- **System packages, driver, kernel**: **root**, Thomas. Unattended upgrades are blacklisted
  for nvidia/kernel on purpose. The only sanctioned driver path is
  `sudo setup/01_driver_fix.sh` (see its header); a reboot without it can leave the box
  without a GPU driver.
- **Chromium snap**: refresh is held. To update deliberately: `sudo snap refresh chromium`
  (root), then re-test camera and kiosk.

## Reboot procedure

1. `tools/showmode.sh status` — note what runs (other people's services restart on their
   own: docker restart policies, cron @reboot).
2. `setup/99_verify.sh` must PASS the two driver lines *before* rebooting. If not, stop and
   read `setup/01_driver_fix.sh`.
3. `sudo reboot` (**root**). Back in ~2 min. GDM autologin brings the kiosk up.
4. After: `nvidia-smi`, `mount | grep /mnt/models`, `docker ps`, `setup/99_verify.sh`.

## Never

- Never install `nvidia-driver-*` meta-packages or any DKMS NVIDIA driver (Secure Boot).
- Never remove `/etc/apt/apt.conf.d/51videobooth-nvidia-hold`.
- Never `pkill` other people's processes; never edit their units or crontabs.
- Never expose ports 7860 / 8000 beyond the LAN / tailnet.
- Never drop the safety negatives from a preset, whatever the artistic argument.
- Never change resolution, engine pin or driver in show week without a measured A/B.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `nvidia-smi`: "Driver/library version mismatch" | userspace and kernel module differ → `setup/01_driver_fix.sh` (root) + reboot. Do not reboot first. |
| `99_verify` FAIL "kernel module vs userspace" | same |
| Camera "Permission denied" for a script | `kxkm` not in `video` group / not re-logged in (`id -nG`) |
| Page shows no camera | Chromium camera plug (`snap connections chromium`), another process holds `/dev/video0` (`fuser /dev/video0`) |
| Engine start very slow the first time | TensorRT engine build for the configured resolution — normal (minutes); cached under `.engines/trt/` afterwards |
| Engine rebuilds engines at every start | `engine_dir` in the yaml differs from `SD_TRT_ENGINES`, or resolution changed |
| Python import errors in the venv (xformers, torch CUDA 13) | the demo's requirements pulled an unpinned xformers → re-run `setup/10_engine_b.sh` (it filters it and re-pins torch cu128) |
| Every session drops after N seconds | demo `--timeout` bug → `run.sh` passes `--timeout 0`; keep it |
| Port 7860 in use | old server: `tmux ls`, `ss -tlnp \| grep 7860` |
| Kiosk restart piles up tabs / an old page keeps streaming | the snap browser escapes the unit's cgroup; `booth-kiosk.sh` now kills the previous instance by profile path before launching (and the unit's `ExecStopPost` on stop). If it happens anyway: `pkill -f -- "--user-data-dir=.*booth-kiosk"` then restart the unit |
| Output page black, engine fine | it reconnects every 2 s and after an 8 s stall by itself; check `tools/cdp.py 'window.__booth.ws.readyState'` (1 = open), `.state/logs/kiosk.log`, and that no other page streams from the same server (one stream at a time) |
| fps fine, latency wanders | another GPU tenant (`showmode status`), or the camera dropping frames (`camera_check`) |
| HF download fails at start | no internet on the box? `HF_HOME=/ai/VideoBooth/.hf`; local copies of the checkpoints exist in `/ai/data/models` — point `model_id` at them |
