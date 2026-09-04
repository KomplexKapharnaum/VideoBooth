# panel/ — the technician's control room

`http://<kxkm-ai>:7870` from any laptop or tablet on the LAN / tailnet. No login (decision
2026-09-04: no security layer yet — never expose the port beyond the LAN).

What it shows: the **render preview** (a live screenshot of the kiosk browser, i.e. exactly
what the visitor sees), the **prompt (+)** and **negative (−)** fields, the **presets**, the
**knobs** of the running engine, and the **show operations** (show mode, engine start/stop,
kiosk target). `server.py` is stdlib Python; it talks to Engine B's demo API, Scope's API,
the kiosk Chromium's DevTools port, `tools/showmode.sh` and tmux.

Engine B knobs: depth control scale (ControlNet strength, live), steps 1–4 and strength
0–1 (mapped to the demo's `t_index_list`, live), guidance and delta (live), seed (live) and
a **flicker** toggle (the panel re-seeds every 150 ms = "seed unlocked"). The negative
prompt has no live route in the demo: applying it re-uploads the config and the pipeline
rebuilds in ~20 s (TensorRT engines stay cached); the panel re-applies the live values
afterwards. The safety terms are always kept in the negative.

Engine A knobs: prompt, noise scale (v2v strength), VACE scale, VACE on/off, per-visitor
reset (cache), all live through Scope's session parameters.

**Engine switch**: one segmented control, B or A. The backend runs the whole sequence in
the background and the page shows the step: to A — kiosk → `scope.html`, stop Engine B,
ensure Scope, load LongLive (480x832, tiny VAE, VACE weights), wait for the WebRTC session;
to B — kiosk → `output.html`, stop the Scope session and restart Scope idle (frees its
VRAM), start Engine B, wait for its pipeline. Presets (`presets/heroes.json`) apply to the
engine shown on the kiosk. Ops: show mode
on/off, Engine B / A start/stop, "free GPU" (restart Scope, which keeps ~22 GB loaded after a
session), kiosk restart, and switching the kiosk between the Engine B output page and Scope's
own page. Unit: `booth-panel.service` (see the file for install lines).
