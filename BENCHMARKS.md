# Benchmarks

Every performance measurement, dated, with the exact config. Never overwrite an entry;
add a new one. Frame-time variance matters more than mean fps (brief rule 2.2).

Protocol for an fps/jitter entry: `tools/fps_probe.py --seconds 120` against the kiosk
Chrome showing the engine output, a person moving continuously in frame. Report fps,
mean / p95 / max frame interval, stalls > 250 ms, and the engine settings verbatim.

Protocol for latency: `tools/LATENCY.md`.

## Machine (setup/00_audit.sh)

## Machine audit — kxkm-ai — 2026-09-04T13:21:59+02:00

### Host
```
 13:21:59 up 19 min,  4 users,  load average: 0,20, 0,23, 0,25
PRETTY_NAME="Ubuntu 24.04.4 LTS"
VERSION_ID="24.04"
kernel: 6.17.0-1032-oem
```

### NVIDIA
```
name, driver_version, memory.used [MiB], memory.total [MiB]
NVIDIA GeForce RTX 4090, 595.84, 2648 MiB, 24564 MiB
kernel module: 595.84
userspace    : nvidia-utils-595 595.84-0ubuntu0.24.04.1
module on disk for 6.17.0-1032-oem: 595.84
newest kernel (grub default 0): 6.17.0-1032-oem
secure boot: SecureBoot enabled
```

### GPU processes
```
pid, process_name, used_gpu_memory [MiB]
3406, python3, 2466 MiB
```

### CPU / RAM / disk
```
Model name:                              Intel(R) Core(TM) i7-14700KF
28
               total        used        free      shared  buff/cache   available
Mem:            62Gi        12Gi        24Gi        35Mi        25Gi        49Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p3  1,8T  765G  919G  46% /
/dev/nvme0n1p3  1,8T  765G  919G  46% /
```

### Python / tooling
```
Python 3.12.3
uv: /home/kxkm/.local/bin/uv
node: v22.23.2
chrome: /snap/bin/chromium
ffmpeg: /usr/bin/ffmpeg
v4l2-ctl: /usr/bin/v4l2-ctl
docker: /usr/bin/docker
```

### User / groups
```
uid=1000(kxkm) gid=1000(kxkm) groups=1000(kxkm),4(adm),24(cdrom),27(sudo),30(dip),44(video),46(plugdev),122(lpadmin),135(lxd),136(sambashare),141(docker),995(ollama),1001(ai)
video group: yes
Linger=yes
```

### Display
```
card1-HDMI-A-2: connected, modes: 3840x2160
AutomaticLoginEnable=True
AutomaticLogin=kxkm
WaylandEnable=false
15 1000 kxkm     -     -    closing no  -
37 1000 kxkm     -     -    active  no  -
 5 6000 electron -     -    active  no  -
c1  128 gdm      seat0 tty1 active  yes 14min ago
```

### Cameras
```
aGent V5 full HD: aGent V5 full (usb-0000:00:14.0-11):
	/dev/video0
	/dev/video1
	/dev/media0

crw-rw----+ 1 root video 81, 0 sept.  4 13:11 /dev/video0
crw-rw----+ 1 root video 81, 1 sept.  4 13:11 /dev/video1
```

### Listening ports (booth-relevant)
```
0.0.0.0:18890
0.0.0.0:7865
*:9211
```

## Camera (tools/camera_check.sh)

### 2026-09-04 — interim USB webcam on the box (not the show camera)
`/dev/video0` = "aGent V5 full HD" (USB2, Z-Star). Every listed mode is 15 fps max (7.5 fps
alternate); 1920x1080 MJPEG through ffmpeg decode ran at ~9 fps. Usable to plumb the engines,
useless for fps or latency baselines — those wait for the Brio 4K (week of 2026-09-07).

## Engine B — StreamDiffusion (SD1.5-LCM + depth ControlNet + TensorRT)

### 2026-09-04 14:02 — first baseline, synthetic source (engine-side, no browser)
Config `engines/b-streamdiffusion/booth_sd15_depth.yaml` @ `bb1c821`: `SimianLuo/LCM_Dreamshaper_v7`,
512x768, `t_index_list: [24]` (1 step), `guidance_scale 1.0`, `delta 0.7`, `seed 42`, tiny VAE,
TensorRT (torch 2.8.0+cu128, TensorRT 10.12.0.36, fork `4c90d9e` with its custom diffusers),
depth ControlNet `control_v11f1p_sd15_depth` scale 0.9 via `depth_tensorrt` (Depth Anything V2
small, 518², fp16). Driver 595.84, kernel 6.17.0-1032-oem. Source: `tools/engine_b_probe.py
--source lavfi` (testsrc2 pattern, white flash every 5 s), 90 s after a 15 s warm-up. Other GPU
tenants NOT stopped (whisper worker idle at 2.4 GB) — a show-mode run will follow.

| date | label | source | fps | frame interval mean / p95 / max | stdev | stalls | latency (engine-side, flash) |
|---|---|---|---|---|---|---|---|
| 2026-09-04 14:02 | B baseline SD1.5-LCM 512x768 1step depthTRT 0.9 | lavfi 512x768 | **28.4 fps** | 35.2 / 65.2 / 112.3 ms | 14.9 ms | 0 > 250 ms (2557 frames) | **0.105 s** (min 0.031 / max 0.161 / sd 0.023, n=27) |

| 2026-09-04 14:04 | B lavfi **paced at 30 fps** (`-re`), same config | lavfi 512x768 | **37.5 fps** (server 38.0) | 26.7 / 27.9 / 103.1 ms | 6.8 ms | 0 (937 frames, 25 s) | 0.128 s (min 0.081 / max 0.189 / sd 0.039, n=5) |
| 2026-09-04 14:05 | B **real webcam** (aGent V5, 15 fps device), same config | v4l2 /dev/video0 512x768 | 36.9 fps (server 35.6) | 27.1 / 53.8 / 79.1 ms | 14.2 ms | 0 (1658 frames, 45 s) | n/a (no flash) |

Output fps above the input rate (37 fps from a 30 fps or 15 fps source) means the demo
re-renders the latest frame whenever no new one arrived — the per-frame cost is what the
numbers show: **~27 ms per frame at 512x768, 1 step, depth ControlNet** on the 4090. The first
run's 28 fps / 15 ms stdev was with the synthetic source running unpaced (ffmpeg flat out on the
CPU next to the server); paced, the interval stdev falls to 7 ms.

Reading: fps is 2.8× the ≥10 fps target and the latency spread is 23 ms — both far inside the
brief's constraints. The p95 at 65 ms vs p50 at 30 ms hints at a bimodal frame time (TensorRT
depth preprocessor on the default CUDA stream: the runtime warns about extra
`cudaStreamSynchronize`); to look at when tuning. Not yet measured: the browser path (kiosk
Chromium on the same GPU) and glass-to-glass; the synthetic source is not a person.
First-run build times: UNet+ControlNet TensorRT engine 203 s, VAE encoder/decoder ~20 s each,
ControlNet engine ~1 min; cached under `.engines/trt/`.

## Engine A — Scope (LongLive / SDV2, VACE depth)

_pending_

## Glass-to-glass latency

_pending_
