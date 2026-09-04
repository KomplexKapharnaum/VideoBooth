#!/usr/bin/env python3
"""engine_b_probe.py — drive the StreamDiffusion realtime-img2img server the way its web page
does (websocket in, MJPEG out) and measure what the ENGINE delivers: output fps, frame-interval
jitter, stalls, and — with a flashing source — end-to-end latency mean AND spread (brief
rule 2.2). No browser involved; the kiosk adds a constant on top of these numbers.

Frames come from ffmpeg (already on the box): the real camera, a synthetic test pattern that
flashes white every N seconds, or a video file.

  # synthetic pattern with a flash every 5 s → fps + jitter + latency, 90 s
  .engines/StreamDiffusion/.venv/bin/python tools/engine_b_probe.py --source lavfi --seconds 90 --label "B baseline 512x768 1step"
  # the real camera (flash a torch at the lens for latency samples)
  .engines/StreamDiffusion/.venv/bin/python tools/engine_b_probe.py --source v4l2:/dev/video0 --seconds 120

Run it with the Engine B venv python (Pillow is used for the flash detector; without it the
probe still reports fps/jitter). Paste the last line into BENCHMARKS.md.
"""
import argparse, base64, io, json, os, socket, statistics, struct, subprocess, sys, threading, time, urllib.request, uuid

try:
    from PIL import Image
except ImportError:  # fps/jitter still work
    Image = None


# ---------------------------------------------------------------- minimal websocket client
class WS:
    def __init__(self, url):
        assert url.startswith('ws://')
        hostport, path = url[5:].split('/', 1)
        host, _, port = hostport.partition(':')
        self.s = socket.create_connection((host, int(port or 80)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        resp = b''
        while b'\r\n\r\n' not in resp:
            c = self.s.recv(4096)
            if not c:
                raise ConnectionError('websocket handshake failed')
            resp += c
        if b' 101 ' not in resp.split(b'\r\n', 1)[0]:
            raise ConnectionError(resp.split(b'\r\n', 1)[0].decode(errors='replace'))
        self.s.settimeout(5)  # short timeout so the main loop can notice a dead MJPEG stream while waiting

    def _rd(self, n):
        b = b''
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise EOFError('websocket closed')
            b += c
        return b

    def _send(self, op, data):
        n = len(data)
        hdr = bytes([0x80 | op])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack('>H', n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack('>Q', n)
        mask = os.urandom(4)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i & 3] for i, b in enumerate(data)))

    def send_json(self, obj):
        self._send(0x1, json.dumps(obj).encode())

    def send_bytes(self, data):
        self._send(0x2, data)

    def recv_json(self):
        """Next text frame, or None on a read timeout (the caller re-checks the sink and loops)."""
        while True:
            try:
                b1, b2 = self._rd(2)
            except socket.timeout:
                return None
            n = b2 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._rd(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._rd(8))[0]
            if b2 & 0x80:
                self._rd(4)
            payload = self._rd(n)
            op = b1 & 0x0f
            if op == 0x8:
                raise EOFError('close')
            if op == 0x9:  # ping → pong
                self._send(0xA, payload)
                continue
            if op == 0x1:
                return json.loads(payload)


# ---------------------------------------------------------------- frame source (ffmpeg → JPEGs)
def ffmpeg_cmd(source, w, h, fps, flash_period, flash_len):
    base = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin']
    if source == 'lavfi':
        vf = (f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='lt(mod(t\\,{flash_period})\\,{flash_len})'")
        inp = ['-f', 'lavfi', '-i', f'testsrc2=size={w}x{h}:rate={fps}']
    elif source.startswith('v4l2:'):
        inp = ['-f', 'v4l2', '-input_format', 'mjpeg', '-framerate', str(fps), '-i', source[5:]]
        vf = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
    else:
        inp = ['-re', '-stream_loop', '-1', '-i', source]
        vf = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
    return base + inp + ['-vf', vf, '-r', str(fps), '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '4', '-']


class Source(threading.Thread):
    """Keeps the newest JPEG from ffmpeg. JPEG scan data never contains FF D9, so splitting on
    the EOI marker is safe."""
    def __init__(self, cmd):
        super().__init__(daemon=True)
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.latest = None; self.count = 0; self.lock = threading.Lock()

    def run(self):
        buf = b''
        while True:
            c = self.p.stdout.read(65536)
            if not c:
                break
            buf += c
            while True:
                e = buf.find(b'\xff\xd9')
                if e < 0:
                    break
                s = buf.find(b'\xff\xd8')
                frame, buf = buf[s:e + 2], buf[e + 2:]
                with self.lock:
                    self.latest = frame; self.count += 1

    def get(self):
        with self.lock:
            return self.latest


def brightness(jpeg):
    if Image is None:
        return None
    im = Image.open(io.BytesIO(jpeg)).convert('L').resize((32, 32))
    px = list(im.getdata())
    return sum(px) / len(px)


# ---------------------------------------------------------------- MJPEG output reader
class Sink(threading.Thread):
    def __init__(self, url):
        super().__init__(daemon=True)
        self.url = url; self.t = []; self.bright = []; self.sizes = []; self.err = None; self.first_at = None

    def run(self):
        try:
            resp = urllib.request.urlopen(self.url, timeout=3600)
            buf = b''
            while True:
                c = resp.read(65536)
                if not c:
                    break
                buf += c
                while True:
                    s = buf.find(b'\xff\xd8')
                    if s < 0:
                        break
                    e = buf.find(b'\xff\xd9', s)
                    if e < 0:
                        break
                    jpeg, buf = buf[s:e + 2], buf[e + 2:]
                    now = time.perf_counter()
                    if self.first_at is None:
                        self.first_at = now
                    self.t.append(now); self.sizes.append(len(jpeg))
                    self.bright.append(brightness(jpeg))
        except Exception as ex:  # noqa: BLE001
            self.err = repr(ex)


def pct(sorted_vals, q):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', default='http://127.0.0.1:7860')
    ap.add_argument('--source', default='lavfi', help='lavfi | v4l2:/dev/videoN | path/to/video')
    ap.add_argument('--size', default='512x768')
    ap.add_argument('--fps', type=int, default=30, help='source frame rate')
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--warmup', type=float, default=10, help='seconds ignored at the start (engine warm-up)')
    ap.add_argument('--flash-period', type=float, default=5.0)
    ap.add_argument('--flash-len', type=float, default=0.25)
    ap.add_argument('--flash-threshold', type=float, default=60.0, help='brightness jump (0-255) that counts as a flash')
    ap.add_argument('--stall-ms', type=float, default=250)
    ap.add_argument('--build-timeout', type=float, default=2400, help='seconds to wait for the first output frame (engine build)')
    ap.add_argument('--label', default='')
    ap.add_argument('--json', help='write raw samples + stats here')
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.split('x'))
    host = a.server.split('//', 1)[1]
    uid = str(uuid.uuid4())

    # default params from the server's own schema, then our resolution
    schema = json.load(urllib.request.urlopen(f'{a.server}/api/settings', timeout=30))
    props = schema.get('input_params', {}).get('properties', {})
    params = {k: v['default'] for k, v in props.items() if 'default' in v}
    params.update(width=w, height=h)
    res_label = next((r for r in props.get('resolution', {}).get('values', []) if r.startswith(f'{w}x{h}')), None)
    if res_label:
        params['resolution'] = res_label
    print(f'params: {len(params)} fields, resolution {params.get("resolution")} {w}x{h}', file=sys.stderr)

    src = Source(ffmpeg_cmd(a.source, w, h, a.fps, a.flash_period, a.flash_len)); src.start()
    t0 = time.time()
    while src.get() is None:
        if time.time() - t0 > 15 or src.p.poll() is not None:
            sys.exit('no frames from ffmpeg: ' + src.p.stderr.read().decode(errors='replace')[-800:])
        time.sleep(0.05)

    ws = WS(f'ws://{host}/api/ws/{uid}')
    msg = ws.recv_json()
    if msg.get('status') != 'connected':
        sys.exit(f'unexpected first message: {msg}')
    sink = Sink(f'{a.server}/api/stream/{uid}'); sink.start()
    print('connected; first /api/stream call builds the pipeline (TensorRT engines: minutes) …', file=sys.stderr)

    sent_t, sent_b = [], []          # send time + brightness of each frame we pushed
    start = time.perf_counter(); last_report = start
    while True:
        try:
            msg = ws.recv_json()
        except EOFError:
            print('websocket closed by server', file=sys.stderr); break
        if msg is None:
            if sink.err:
                break
            if not sink.first_at and time.perf_counter() - start > a.build_timeout:
                print(f'no output frame after {a.build_timeout:.0f}s', file=sys.stderr); break
            continue
        st = msg.get('status')
        if st == 'send_frame':
            jpeg = src.get()
            ws.send_json({'status': 'next_frame'}); ws.send_json(params); ws.send_bytes(jpeg)
            sent_t.append(time.perf_counter()); sent_b.append(brightness(jpeg))
        elif st in ('timeout', 'error'):
            print(f'server says {st}: {msg.get("message")}', file=sys.stderr); break
        now = time.perf_counter()
        if sink.first_at and now - sink.first_at > a.seconds + a.warmup:
            break
        if now - last_report > 10:
            last_report = now
            print(f'  sent {len(sent_t)} · received {len(sink.t)} · source frames {src.count}' + (f' · sink error {sink.err}' if sink.err else ''), file=sys.stderr)
        if sink.err:
            break
    try:
        ws.s.close()
    except Exception:
        pass
    src.p.kill()

    if not sink.first_at or len(sink.t) < 3:
        sys.exit(f'too few output frames ({len(sink.t)}); sink error: {sink.err}')
    cut = sink.first_at + a.warmup
    t = [x for x in sink.t if x >= cut]
    d = [b - x for x, b in zip(t, t[1:])]
    if len(d) < 2:
        sys.exit('not enough frames after warm-up')
    ds = sorted(d); span = t[-1] - t[0]
    sec = lambda v: round(v, 3)
    stats = dict(label=a.label, source=a.source, size=a.size, frames=len(t), seconds=round(span, 1),
                 fps=round((len(t) - 1) / span, 2), mean_ms=round(statistics.fmean(d) * 1000, 1),
                 p50_ms=round(pct(ds, .5) * 1000, 1), p95_ms=round(pct(ds, .95) * 1000, 1),
                 max_ms=round(max(d) * 1000, 1), stdev_ms=round(statistics.pstdev(d) * 1000, 1),
                 stalls=sum(1 for x in d if x * 1000 > a.stall_ms), stall_ms=a.stall_ms,
                 sent=len(sent_t), warmup_s=a.warmup)
    # latency: rising edges of brightness in what we sent vs what came back
    lat = []
    if Image is not None and sent_b and all(b is not None for b in sent_b[:5]):
        def edges(ts, bs):
            out, prev = [], bs[0]
            for ti, bi in zip(ts, bs):
                if bi is not None and prev is not None and bi - prev > a.flash_threshold:
                    out.append(ti)
                prev = bi
            return out
        ein, eout = edges(sent_t, sent_b), edges(sink.t, sink.bright)
        for ti in ein:
            cands = [to - ti for to in eout if 0 < to - ti < a.flash_period * 0.9]
            if cands:
                lat.append(min(cands))
        if lat:
            stats.update(latency_n=len(lat), latency_mean_s=sec(statistics.fmean(lat)), latency_min_s=sec(min(lat)),
                         latency_max_s=sec(max(lat)), latency_stdev_s=sec(statistics.pstdev(lat)))
        else:
            stats.update(latency_n=0, flashes_sent=len(ein), flashes_seen=len(eout))
    try:
        stats['server_fps'] = json.load(urllib.request.urlopen(f'{a.server}/api/fps', timeout=5)).get('fps')
    except Exception:
        pass
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(dict(stats=stats, out_t=sink.t, out_bright=sink.bright, sent_t=sent_t, sent_bright=sent_b), f)
    print(json.dumps(stats))
    lat_s = (f"{stats['latency_mean_s']} s (min {stats['latency_min_s']} / max {stats['latency_max_s']} / sd {stats['latency_stdev_s']}, n={stats['latency_n']})"
             if lat else 'n/a')
    print(f"| {time.strftime('%Y-%m-%d %H:%M')} | {a.label or '-'} | {a.source} {a.size} | {stats['fps']} fps | "
          f"{stats['mean_ms']} / {stats['p95_ms']} / {stats['max_ms']} ms (mean/p95/max) | sd {stats['stdev_ms']} ms | "
          f"stalls>{int(a.stall_ms)}ms: {stats['stalls']} | latency {lat_s} |")


if __name__ == '__main__':
    main()
