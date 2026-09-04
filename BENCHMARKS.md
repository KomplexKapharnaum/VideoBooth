# Benchmarks

Every performance measurement, dated, with the exact config. Never overwrite an entry;
add a new one. Frame-time variance matters more than mean fps (brief rule 2.2).

Protocol for an fps/jitter entry: `tools/fps_probe.py --seconds 120` against the kiosk
Chrome showing the engine output, a person moving continuously in frame. Report fps,
mean / p95 / max frame interval, stalls > 250 ms, and the engine settings verbatim.

Protocol for latency: `tools/LATENCY.md`.

## Machine (setup/00_audit.sh)

_pending — run after the driver fix and reboot_

## Camera (tools/camera_check.sh)

_pending_

## Engine B — StreamDiffusion (SD1.5-LCM + depth ControlNet + TensorRT)

_pending_

## Engine A — Scope (LongLive / SDV2, VACE depth)

_pending_

## Glass-to-glass latency

_pending_
