# kiosk/

Google Chrome `--kiosk` on the 4090's HDMI output, portrait, pointed at the running
engine's output page (`KIOSK_URL` in `setup/env.sh` / `booth.conf`). The same Chrome page
holds the camera (`getUserMedia`, auto-granted) and displays the WebRTC output.

- `booth-kiosk.sh` — xrandr (native mode or `KIOSK_MODE`, `KIOSK_ROTATE`), no blanking,
  cursor hidden, Chrome loop. Logs: `.state/logs/kiosk.log`. DevTools on `:9222` for
  `tools/fps_probe.py` (`tools/cdp.py --screenshot /tmp/k.png` to see what the TV sees).
- `booth-kiosk.service` — systemd user unit bound to the GNOME session (install lines in
  the file). Needs GDM autologin (`setup/02_root_prereqs.sh`).

Manual test without the unit, from the desktop session: `kiosk/booth-kiosk.sh`.
Stop the unit: `systemctl --user stop booth-kiosk`. Change URL: edit `booth.conf`, restart.

Open (Phase 1): each engine demo page shows its controls next to the video; the visitor
screen wants the output only. Either the demo's own fullscreen/output view, or a small
wrapper page in this folder that opens the camera, connects to the engine and shows only
the output — written against the engine's real API once measured.
