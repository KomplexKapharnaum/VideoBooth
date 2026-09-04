#!/usr/bin/env python3
"""engine_a_probe.py — bench Daydream Scope (Engine A) engine-side, without a browser.

Starts a HEADLESS Scope session (Scope's own API: no WebRTC) fed by a video file from Scope's
assets directory, reads the MPEG-TS output through ffmpeg and times every output frame:
fps, frame-interval mean/p95/max/stdev, stalls; a flashing clip also proves the input→output
link (flash count seen). Scope's own frame stats (/api/v1/session/metrics) are reported too.

  # LongLive, bare (no VACE), the flashing synthetic clip, 90 s
  .engines/scope/.venv/bin/python tools/engine_a_probe.py --pipeline longlive --clip booth_flash_480x832 --seconds 90 --label "A longlive bare"
  # LongLive + VACE depth control from the input video
  .engines/scope/.venv/bin/python tools/engine_a_probe.py --pipeline longlive --clip booth_cam_480x832 --vace --vace-scale 0.85 --seconds 90 --label "A longlive vace0.85"

Clips: any video in ~/.daydream-scope/assets (name without extension). Pillow is optional
(flash detection). The GPU must be free of Engine B (tools/showmode.sh on; tmux kill-session
-t booth-b): LongLive needs ~20 GB. Paste the last line into BENCHMARKS.md.
"""
import argparse, io, json, statistics, subprocess, sys, threading, time, urllib.request

try:
    from PIL import Image
except ImportError:
    Image = None


def api(base, path, method='GET', body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode(errors='replace')


def brightness(jpeg):
    if Image is None:
        return None
    im = Image.open(io.BytesIO(jpeg)).convert('L').resize((32, 32))
    px = list(im.getdata()); return sum(px) / len(px)


class TsReader(threading.Thread):
    """ffmpeg decodes the MPEG-TS output stream into JPEGs; we timestamp each one on arrival."""
    def __init__(self, url):
        super().__init__(daemon=True)
        self.p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-fflags', 'nobuffer', '-flags', 'low_delay',
                                   '-i', url, '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '5', '-'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.t, self.bright, self.last = [], [], None

    def run(self):
        buf = b''
        while True:
            c = self.p.stdout.read(65536)
            if not c:
                break
            buf += c
            while True:
                s = buf.find(b'\xff\xd8'); e = buf.find(b'\xff\xd9', s) if s >= 0 else -1
                if s < 0 or e < 0:
                    break
                jpeg, buf = buf[s:e + 2], buf[e + 2:]
                self.t.append(time.perf_counter()); self.bright.append(brightness(jpeg)); self.last = jpeg


def pct(v, q):
    return v[min(len(v) - 1, int(q * len(v)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', default='http://127.0.0.1:8000')
    ap.add_argument('--pipeline', default='longlive')
    ap.add_argument('--clip', default='booth_flash_480x832', help='video in Scope assets (name without extension) or a path')
    ap.add_argument('--prompt', default='a superhero in a sleek chrome armored suit, glowing blue chest emblem, dramatic rim light, cinematic')
    ap.add_argument('--vace', action='store_true', help='enable VACE with the input video as control')
    ap.add_argument('--vace-scale', type=float, default=0.85)
    ap.add_argument('--width', type=int, default=480)
    ap.add_argument('--height', type=int, default=832)
    ap.add_argument('--vae', default='tae', help='vae_type load param: wan | lightvae | tae | lighttae (tae = tiny VAE)')
    ap.add_argument('--quant', default=None, help='quantization load param, e.g. fp8_e4m3fn')
    ap.add_argument('--load-steps', default=None, help='denoising_steps load param, comma-separated timesteps (pipeline default [1000,750,500,250])')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--load-timeout', type=float, default=1800)
    ap.add_argument('--noise-scale', type=float, default=None)
    ap.add_argument('--steps', default=None, help='denoising_step_list, comma-separated (pipeline default if omitted)')
    ap.add_argument('--param', action='append', default=[], metavar='KEY=JSON', help='extra session parameter, e.g. --param kv_cache_attention_bias=0.5')
    ap.add_argument('--seconds', type=float, default=90)
    ap.add_argument('--warmup', type=float, default=15)
    ap.add_argument('--stall-ms', type=float, default=250)
    ap.add_argument('--flash-threshold', type=float, default=60.0)
    ap.add_argument('--label', default='')
    ap.add_argument('--json')
    ap.add_argument('--save-frame', metavar='PATH', help='save the last output JPEG here')
    ap.add_argument('--keep', action='store_true', help='leave the session running at the end')
    a = ap.parse_args()
    B = a.server.rstrip('/')

    # 1. load the pipeline (single-pipeline sessions do NOT load it themselves), then wait
    load = {'height': a.height, 'width': a.width, 'vae_type': a.vae, 'base_seed': a.seed}
    if a.quant: load['quantization'] = a.quant
    if a.load_steps: load['denoising_steps'] = [int(x) for x in a.load_steps.split(',')]
    if a.vace: load.update(vace_enabled=True, vace_context_scale=a.vace_scale)
    st = api(B, '/api/v1/pipeline/status')
    if not (st.get('status') == 'loaded' and st.get('pipeline_id') == a.pipeline and (st.get('load_params') or {}).items() >= load.items()):
        print(f'loading {a.pipeline} {json.dumps(load)}', file=sys.stderr)
        t0 = time.time(); api(B, '/api/v1/pipeline/load', 'POST', {'pipeline_ids': [a.pipeline], 'load_params': load})
        while True:
            st = api(B, '/api/v1/pipeline/status')
            if st.get('status') == 'loaded': break
            if st.get('status') == 'error' or st.get('error'): sys.exit(f'pipeline load failed: {json.dumps(st)[:400]}')
            if time.time() - t0 > a.load_timeout: sys.exit('pipeline load timed out')
            time.sleep(3)
        print(f'loaded in {time.time() - t0:.0f}s (stage {st.get("loading_stage")})', file=sys.stderr)
    else:
        print('pipeline already loaded with these params', file=sys.stderr)

    params = {}
    if a.vace:
        params.update(vace_enabled=True, vace_use_input_video=True, vace_context_scale=a.vace_scale)
    if a.noise_scale is not None:
        params['noise_scale'] = a.noise_scale
    if a.steps:
        params['denoising_step_list'] = [int(x) for x in a.steps.split(',')]
    for kv in a.param:
        k, v = kv.split('=', 1); params[k] = json.loads(v)
    body = {'pipeline_id': a.pipeline, 'input_mode': 'video',
            'prompts': [{'text': a.prompt, 'weight': 1.0}],
            'input_source': {'enabled': True, 'source_type': 'video_file', 'source_name': a.clip},
            'parameters': params or None}
    print(f'starting headless session: {json.dumps(body)[:300]}', file=sys.stderr)
    t0 = time.time()
    try:
        r = api(B, '/api/v1/session/start', 'POST', body, timeout=3600)   # loads the pipeline (minutes the first time)
    except urllib.error.HTTPError as e:
        sys.exit(f'session start failed: HTTP {e.code}: {e.read().decode(errors="replace")[:600]}')
    print(f'session started in {time.time() - t0:.0f}s: {json.dumps(r)[:300]}', file=sys.stderr)

    rd = TsReader(B + '/api/v1/session/output.ts'); rd.start()
    start = time.perf_counter(); last = start
    while rd.p.poll() is None:
        now = time.perf_counter()
        if rd.t and now - rd.t[0] > a.seconds + a.warmup:
            break
        if now - start > a.warmup + 300 and not rd.t:
            print('no output frame after 5 min', file=sys.stderr); break
        if now - last > 10:
            last = now; print(f'  frames {len(rd.t)} · {json.dumps(api(B, "/api/v1/session/metrics").get("sessions", {}))[:200]}', file=sys.stderr)
        time.sleep(0.5)
    metrics = api(B, '/api/v1/session/metrics')
    rd.p.kill()
    if not a.keep:
        try: api(B, '/api/v1/session/stop', 'POST', {})
        except Exception as e: print('stop:', e, file=sys.stderr)
    if len(rd.t) < 3:
        err = rd.p.stderr.read().decode(errors='replace')[-600:]
        sys.exit(f'too few output frames ({len(rd.t)}); ffmpeg: {err}')
    cut = rd.t[0] + a.warmup
    t = [x for x in rd.t if x >= cut]
    d = sorted(b - x for x, b in zip(t, t[1:])); span = t[-1] - t[0]
    dd = [b - x for x, b in zip(t, t[1:])]
    stats = dict(label=a.label, pipeline=a.pipeline, clip=a.clip, load=load, params=params, frames=len(t), seconds=round(span, 1),
                 fps=round((len(t) - 1) / span, 2), mean_ms=round(statistics.fmean(dd) * 1000, 1), p50_ms=round(pct(d, .5) * 1000, 1),
                 p95_ms=round(pct(d, .95) * 1000, 1), max_ms=round(max(dd) * 1000, 1), stdev_ms=round(statistics.pstdev(dd) * 1000, 1),
                 stalls=sum(1 for x in dd if x * 1000 > a.stall_ms), stall_ms=a.stall_ms, warmup_s=a.warmup)
    if Image is not None and any(b is not None for b in rd.bright):
        flashes, prev = 0, rd.bright[0]
        for b in rd.bright:
            if b is not None and prev is not None and b - prev > a.flash_threshold: flashes += 1
            prev = b
        stats['flashes_seen'] = flashes
    sess = metrics.get('sessions', {}); fp = next(iter(sess.values()), {}) if isinstance(sess, dict) else {}
    stats['scope_metrics'] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in fp.items() if k in ('fps_in', 'fps_out', 'pipeline_fps', 'frames_in', 'frames_out')}
    stats['gpu'] = metrics.get('gpu', {})
    if a.json:
        with open(a.json, 'w') as f: json.dump(dict(stats=stats, t=rd.t, bright=rd.bright), f)
    if a.save_frame and rd.last:
        with open(a.save_frame, 'wb') as f: f.write(rd.last)
    print(json.dumps(stats))
    print(f"| {time.strftime('%Y-%m-%d %H:%M')} | {a.label or '-'} | {a.pipeline} {a.width}x{a.height} vae={a.vae} steps={load.get('denoising_steps', 'default')} {'+VACE ' + str(a.vace_scale) if a.vace else 'bare'} · {a.clip} | {stats['fps']} fps | "
          f"{stats['mean_ms']} / {stats['p95_ms']} / {stats['max_ms']} ms (mean/p95/max) | sd {stats['stdev_ms']} ms | stalls>{int(a.stall_ms)}ms: {stats['stalls']} | "
          f"scope pipeline_fps {stats['scope_metrics'].get('pipeline_fps')} | flashes seen {stats.get('flashes_seen', 'n/a')} |")


if __name__ == '__main__':
    main()
