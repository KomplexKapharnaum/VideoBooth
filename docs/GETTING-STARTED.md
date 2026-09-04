# Getting started

For someone joining the project today. Half a day from zero to a running engine and a first
measurement, assuming the box is already prepared (it is, since 2026-09-04).

## 1. Read, in this order (30 min)

1. [../CLAUDE.md](../CLAUDE.md) — the brief: what we build, the design rules **in priority
   order**, what is rejected. Everything else follows from it.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — how the pieces fit, ports, paths, constraints.
3. [../ROADMAP.md](../ROADMAP.md) — where we are, what is decided, what is open.
4. [../BENCHMARKS.md](../BENCHMARKS.md) — the numbers so far.

## 2. Access

- **Machine**: `kxkm-ai`, user `kxkm`. From a machine on the KXKM LAN: `ssh kxkm@10.2.0.237`.
  From outside: over Thomas's tailscale (`100.87.54.119`). Ask Thomas for an SSH key on the
  box; the shared password is not the way.
- **You do not have sudo** as `kxkm` (it asks for a password nobody should type in a script).
  Everything the booth needs runs as `kxkm`; the two root scripts have already been run.
- **Repo**: https://github.com/KomplexKapharnaum/VideoBooth (public). Clone it on your laptop
  for editing; the box has its own clone at `/ai/VideoBooth` that you update with `git pull`.
- **Hub**: Thomas tracks tasks in his 37Projects hub (project `videobooth`). Commits that
  close a task carry a `Refs-37: videobooth#t-NNN [done]` trailer; if you do not know what
  that is, ignore it.

## 3. Day-1 checklist (60 min)

```bash
ssh kxkm-ai
cd /ai/VideoBooth && git pull
setup/99_verify.sh                      # everything PASS except "engine A not installed" is fine today
tools/showmode.sh status                # who is on the GPU right now
tools/camera_check.sh /dev/video0       # which camera, which formats, real fps
```

Start Engine B and look at it:

```bash
tools/showmode.sh on                    # free the GPU (restores later with "off")
tmux new -s booth-b engines/b-streamdiffusion/run.sh      # first start: builds TensorRT engines, minutes
# detach with Ctrl-b d ; watch with: tmux attach -t booth-b ; log: .state/logs/engine_b_server.log
```

Then from your laptop's browser: `http://kxkm-ai:7860` (or the LAN IP). Allow the camera, press
start, move. That page is what the visitor screen shows; the controls on it are the dials
([TUNING.md](TUNING.md)).

Measure (this is the reflex the project runs on):

```bash
.engines/StreamDiffusion/.venv/bin/python tools/engine_b_probe.py --source lavfi --seconds 60 --label "my first run"
```

It prints one JSON line and one Markdown table row. Paste the row into
`BENCHMARKS.md` under the engine's section with the settings you used.

When you are done: `tools/showmode.sh off` gives the GPU back to the other tenants.

## 4. Working on the box, safely

- Long jobs go in **tmux** (`tmux ls`, `tmux attach -t <name>`), logs under
  `/ai/VideoBooth/.state/logs/`. The Engine B server session is `booth-b`.
- Prefer scripts from the repo over ad-hoc commands: if you had to type it twice, put it in
  `setup/` or `tools/` and commit.
- Never `pkill -f <pattern>` inside an `ssh host '<cmd>'` argument — the pattern matches the
  ssh shell itself and kills it. Feed scripts with `ssh kxkm-ai 'bash -s' <<'EOF' … EOF`, and in
  such scripts always run `ffmpeg -nostdin …`: otherwise ffmpeg eats the rest of the script from
  stdin (the remaining lines never run).
- The kiosk page holds `/dev/video0`; to record from the camera, `systemctl --user stop
  booth-kiosk` first and start it again after.
- Don't stop, edit or "clean up" services that are not the booth's. `tools/showmode.sh`
  is the only sanctioned way to pause them.
- Changing the repo on your laptop → `git push` → on the box `git pull`. Don't edit files in
  `/ai/VideoBooth` directly unless you commit from there too.
- The engines' upstream checkouts under `.engines/` are pinned (`SD_REF`, `SCOPE_REF` in
  `setup/env.sh`). Bumping them is a decision, measured before and after, never in show week.

## 5. The kiosk (visitor screen)

`kiosk/booth-kiosk.sh` puts the HDMI output in portrait and runs Chromium `--kiosk` on
`KIOSK_URL` (default Engine B). It runs as a **systemd user unit** inside the `kxkm` graphical
session — GDM autologin is configured, so after a reboot (or `sudo systemctl restart gdm`) the
screen shows the engine page by itself. Install / control:

```bash
mkdir -p ~/.config/systemd/user && ln -sf /ai/VideoBooth/kiosk/booth-kiosk.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now booth-kiosk
systemctl --user status booth-kiosk ; tools/cdp.py --screenshot /tmp/k.png   # see what the TV sees
```

No desk session yet? `tools/bench_browser.sh start` runs the same page headless with the
camera, so the probes work anyway.

## 6. Where to change what

| I want to… | Go to |
|---|---|
| change the look (prompt, steps, strength, depth scale, seed) | the engine UI live; defaults in `engines/b-streamdiffusion/booth_sd15_depth.yaml`; presets in `presets/heroes.json` — see [TUNING.md](TUNING.md) |
| change resolution | the yaml (`width`/`height`) → TensorRT rebuild on next start |
| change camera / kiosk URL / rotation | `booth.conf` (`CAMERA_DEV`, `KIOSK_URL`, `KIOSK_ROTATE`, `KIOSK_MODE`) |
| add a tool or script | `tools/` (measurement, ops) or `setup/` (install, idempotent) |
| record a number | `BENCHMARKS.md` |
| record a decision | `ROADMAP.md` (decisions / deviations), `DECISION.md` (engine choice) |
| run a show | [OPERATIONS.md](OPERATIONS.md) |
