#!/usr/bin/env python3
"""fps_probe.py — measure the PRESENTED frame rate and frame-time jitter of the engine
output as the kiosk Chrome actually displays it (brief rule 2.2: variance, not just fps).

Talks to the kiosk Chrome over DevTools (kiosk/booth-kiosk.sh starts it with
--remote-debugging-port), hooks `requestVideoFrameCallback` on the output <video>, samples
for N seconds, then reports fps, mean / p50 / p95 / max frame interval, stalls and skipped
frames. Stdlib only (uses cdp.py next to it).

  tools/fps_probe.py --seconds 120                # default: first <video> on the page
  tools/fps_probe.py --seconds 120 --select 'video#output' --stall-ms 250 --json out.json
Paste the last line into BENCHMARKS.md with the exact engine settings.
"""
import argparse, json, os, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402

HOOK = """(() => {
  const v = document.querySelector(%s);
  if (!v) return 'NOVIDEO';
  if (!('requestVideoFrameCallback' in v)) return 'NORVFC';
  window.__fp = {t: [], pf: [], stop: false};
  const cb = (now, meta) => {
    window.__fp.t.push(now); window.__fp.pf.push(meta.presentedFrames || 0);
    if (!window.__fp.stop) v.requestVideoFrameCallback(cb);
  };
  v.requestVideoFrameCallback(cb);
  return 'OK:' + v.videoWidth + 'x' + v.videoHeight;
})()"""
READ = "(() => { window.__fp.stop = true; return JSON.stringify([window.__fp.t, window.__fp.pf]); })()"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--select', default='video')
    ap.add_argument('--stall-ms', type=float, default=250)
    ap.add_argument('--json', help='write raw samples + stats here')
    ap.add_argument('--label', default='', help='free text (engine + settings) echoed in the summary line')
    a = ap.parse_args()
    ws = cdp.WS(cdp.page()['webSocketDebuggerUrl'])
    r = ws.call('Runtime.evaluate', expression=HOOK % json.dumps(a.select), returnByValue=True)
    v = r.get('result', {}).get('result', {}).get('value')
    if not isinstance(v, str) or not v.startswith('OK'):
        sys.exit(f'hook failed: {v!r} (page has no <video>? wrong --select?)')
    size = v.split(':', 1)[1]
    print(f'sampling {a.seconds:.0f}s on {a.select} ({size}) …', file=sys.stderr)
    time.sleep(a.seconds)
    r = ws.call('Runtime.evaluate', expression=READ, returnByValue=True)
    t, pf = json.loads(r['result']['result']['value'])
    if len(t) < 3:
        sys.exit(f'only {len(t)} frames presented in {a.seconds}s — is the stream running?')
    d = [b - x for x, b in zip(t, t[1:])]
    span = (t[-1] - t[0]) / 1000.0
    ds = sorted(d)
    p = lambda q: ds[min(len(ds) - 1, int(q * len(ds)))]
    skipped = sum(max(0, (b - x) - 1) for x, b in zip(pf, pf[1:])) if any(pf) else None
    stalls = [x for x in d if x > a.stall_ms]
    stats = dict(frames=len(t), seconds=round(span, 2), fps=round((len(t) - 1) / span, 2),
                 mean_ms=round(statistics.fmean(d), 1), p50_ms=round(p(0.5), 1), p95_ms=round(p(0.95), 1),
                 max_ms=round(max(d), 1), stdev_ms=round(statistics.pstdev(d), 1),
                 stalls=len(stalls), stall_ms=a.stall_ms, skipped_frames=skipped, size=size, label=a.label)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(dict(stats=stats, t=t, presented=pf), f)
    print(json.dumps(stats))
    print(f"| {time.strftime('%Y-%m-%d %H:%M')} | {a.label or '-'} | {size} | {stats['fps']} fps | "
          f"{stats['mean_ms']} / {stats['p95_ms']} / {stats['max_ms']} ms (mean/p95/max) | "
          f"stdev {stats['stdev_ms']} ms | stalls>{int(a.stall_ms)}ms: {stats['stalls']} | skipped: {skipped} |")


if __name__ == '__main__':
    main()
