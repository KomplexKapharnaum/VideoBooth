# kiosk/

Chromium `--kiosk` (Canonical snap; Google Chrome as fallback) on the 4090's HDMI output, portrait, pointed at the running
engine's output page (`KIOSK_URL` in `setup/env.sh` / `booth.conf`). The same Chromium page
holds the camera (`getUserMedia`, auto-granted) and displays the WebRTC output.

- `booth-kiosk.sh` — xrandr (native mode or `KIOSK_MODE`, `KIOSK_ROTATE`), no blanking,
  cursor hidden, browser loop. Logs: `.state/logs/kiosk.log`. DevTools on `:9222` for
  `tools/fps_probe.py` (`tools/cdp.py --screenshot /tmp/k.png` to see what the TV sees).
- `booth-kiosk.service` — systemd user unit bound to the GNOME session (install lines in
  the file). Needs GDM autologin (`setup/02_root_prereqs.sh`).

Manual test without the unit, from the desktop session: `kiosk/booth-kiosk.sh`.
Stop the unit: `systemctl --user stop booth-kiosk`. Change URL: edit `booth.conf`, restart.

**`www/output.html`** — the visitor page for Engine B: black page, output full-screen,
nothing else. It opens the camera, feeds the demo's websocket exactly like the demo UI does
and shows `/api/stream/<uuid>`; reconnects by itself when the engine restarts (stall watchdog
at 8 s). Served by `booth-kiosk.sh` on `127.0.0.1:7861` (the snap browser cannot read `/ai`).
URL options: `server=`, `w=`/`h=` (must match the yaml), `cam=<label>`, `fit=cover|contain`,
`mirror=1|0` (default mirrored, like a mirror). The technician's laptop uses the panel
(`http://<box>:7870`) or the demo UI (`:7860`) for the dials — they act on the shared
pipeline — and must not press "Start Stream" on the demo page.

**`www/scope.html`** — the visitor page for Engine A (Scope): same idea over WebRTC — the
cover-cropped camera is sent as a video track, the offer carries the initial parameters
(video mode, pipeline, prompt), the remote track is shown full-screen; it waits until the
pipeline is loaded and reconnects by itself. The panel's engine switch loads the pipeline
and points the kiosk at this page (`server=`, `pipeline=`, `w=`/`h=`, `prompt=`, `noise=`).
