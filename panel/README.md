# panel/ — the technician's control room

`http://<kxkm-ai>:7870` from any laptop or tablet on the LAN / tailnet. No login (decision
2026-09-04: no security layer yet — never expose the port beyond the LAN).

What it shows: the **render preview** (what the visitor sees — 2 fps snapshots, or the
kiosk browser's own screencast relayed at full rate), the **prompt (+)** and **negative (−)**
fields, the **presets**, the **knobs** of the running engine, the **engine switch**
(STOP / B / A) and **show mode**. `server.py` is stdlib Python; it talks to Engine B's demo
API, Scope's API, the kiosk Chromium's DevTools port, `tools/showmode.sh` and tmux.

**Live view for any device**: `http://<box>:7870/view.html` (link + QR code in the panel,
LAN and tailscale addresses) shows the visitor screen full-screen — no camera, no controls —
relayed from the kiosk browser's screencast (`/api/preview.mjpg`, ~30 fps, ~30 KB/frame).

**STOP** shuts both engines down and blanks the visitor screen (GPU free for the other
tenants); B and A load their engine and page. The screen is black during a switch.

**Presets** live in `.state/presets.json` on the box (seeded from `presets/heroes.json`, the
committed defaults — copy back and commit when a set is worth keeping). Clicking a preset
applies it AND fills the boxes and knobs. "Save as NEW" refuses an existing name; "Update"
and "Remove" act only on the preset last loaded and ask for a confirm; every write keeps a
dated backup next to the file (last 10).

Engine B knobs: depth control scale (ControlNet strength, live), steps 1–4 and strength
0–1 (mapped to the demo's `t_index_list`, live), guidance and delta (live), seed (live) and
a **flicker** toggle (the panel re-seeds every 150 ms = "seed unlocked"). The negative
prompt is live too, through the booth's two-line patch on the demo
(`engines/b-streamdiffusion/patches/`); on an unpatched demo the panel falls back to a config
re-upload (pipeline rebuild, ~20 s black) and re-applies the live values afterwards. The
safety terms are always kept in the negative.

Engine A knobs: prompt, noise scale (v2v strength), VACE scale, VACE on/off, per-visitor
reset (cache), all live through Scope's session parameters.

**Engine switch**: one segmented control, STOP, B or A. The backend runs the whole sequence in
the background and the page shows the step: to A — kiosk → `scope.html`, stop Engine B,
ensure Scope, load LongLive (480x832, tiny VAE, VACE weights), wait for the WebRTC session;
to B — kiosk → `output.html`, stop the Scope session and restart Scope idle (frees its
VRAM), start Engine B, wait for its pipeline. Presets (`presets/heroes.json`) apply to the
engine shown on the kiosk. Ops: show mode
on/off, Engine B / A start/stop, "free GPU" (restart Scope, which keeps ~22 GB loaded after a
session), kiosk restart, and switching the kiosk between the Engine B output page and Scope's
own page. Unit: `booth-panel.service` (see the file for install lines).

**Do not** start engines from inside another service's cgroup: the panel and show mode start
the tmux server in its own transient scope (`systemd-run --user --scope tmux start-server`)
because a tmux server born inside `booth-panel.service` died with every panel restart, taking
the engines and VoiceClone with it (2026-09-04).
