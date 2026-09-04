#!/usr/bin/env python3
"""VideoBooth technician panel — one small server, no dependencies, no auth (LAN only).

Serves panel/www and a JSON API that drives the engines, the kiosk and the box:
  GET  /api/status            engines (B: state/fps, A: pipeline/session), GPU, show mode, kiosk, tmux
  GET  /api/preview.jpg       what the visitor screen shows (DevTools screenshot of the kiosk Chromium)
  GET  /api/presets           presets/heroes.json
  POST /api/preset/apply      {name}                      → prompt, negative, depth scale, steps/strength, seed
  POST /api/b/prompt          {prompt}                    live (prompt blending, one prompt)
  POST /api/b/negative        {negative}                  rebuild (~20 s): config re-upload, then re-apply live values
  POST /api/b/params          {control_scale?, steps?, strength?, t_index_list?, guidance_scale?, delta?, seed?}
  POST /api/b/flicker         {on, ms}                    per-frame seed flicker (background seed randomiser)
  POST /api/a/prompt          {prompt}                    Scope session prompts
  POST /api/a/params          {noise_scale?, vace_context_scale?, vace_enabled?, denoising_step_list?, kv_cache_attention_bias?}
  POST /api/a/reset           per-visitor cache reset
  POST /api/ops               {action: showmode_on|showmode_off|engine_b_start|engine_b_stop|engine_a_start|engine_a_stop|kiosk_restart|kiosk_b|kiosk_a}
Runs as kxkm on kxkm-ai (systemd --user booth-panel.service), port PANEL_PORT (7870).
"""
import base64, http.server, io, json, os, random, re, socket, socketserver, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import cdp  # noqa: E402  (DevTools client, stdlib)


def sh_env():
    """setup/env.sh + booth.conf as a dict (the single place for paths and ports)."""
    out = subprocess.run(['bash', '-c', f'. {ROOT}/setup/env.sh >/dev/null 2>&1; env'], capture_output=True, text=True).stdout
    return dict(l.split('=', 1) for l in out.splitlines() if '=' in l)


ENV = sh_env()
B = f"http://127.0.0.1:{ENV.get('SD_PORT', '7860')}"
A = f"http://127.0.0.1:{ENV.get('SCOPE_PORT', '8000')}"
PORT = int(ENV.get('PANEL_PORT', '7870'))
CDP_PORT = int(ENV.get('CDP_PORT', '9222'))
STATE_DIR = ENV.get('BOOTH_STATE', os.path.join(ROOT, '.state'))
SD_CONFIG = ENV.get('SD_CONFIG', os.path.join(ROOT, 'engines/b-streamdiffusion/booth_sd15_depth.yaml'))
KIOSK_B = f"http://127.0.0.1:{ENV.get('KIOSK_HTTP_PORT', '7861')}/output.html?server={B}"
KIOSK_A = f"http://127.0.0.1:{ENV.get('KIOSK_HTTP_PORT', '7861')}/scope.html?server={A}&pipeline=longlive&w=480&h=832"
KIOSK_OFF = f"http://127.0.0.1:{ENV.get('KIOSK_HTTP_PORT', '7861')}/blank.html"
PRESETS_REPO = os.path.join(ROOT, 'presets', 'heroes.json')          # the committed defaults
PRESETS_FILE = os.path.join(STATE_DIR, 'presets.json')               # the technician's live copy (outside git)
LOADED_PRESET = {'name': None, 'at': None}
A_LOAD = {'height': 832, 'width': 480, 'vae_type': 'tae', 'base_seed': 42, 'vace_enabled': True, 'vace_context_scale': 0.85}
SAFETY = 'nudity, naked, nsfw, sexual, explicit, gore, blood, wounds, mutilation'
LOG = []


def log(msg):
    LOG.append(f"{time.strftime('%H:%M:%S')} {msg}"); del LOG[:-60]; print(msg, flush=True)


def call(url, method='GET', body=None, timeout=10, form=None):
    data, headers = None, {}
    if form is not None:                       # multipart file upload (config re-upload)
        bnd = uuid.uuid4().hex
        name, content = form
        data = (f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/x-yaml\r\n\r\n').encode() + content + f'\r\n--{bnd}--\r\n'.encode()
        headers['Content-Type'] = f'multipart/form-data; boundary={bnd}'
    elif body is not None:
        data = json.dumps(body).encode(); headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode(errors='replace')


def try_http(*a, **k):
    try:
        return call(*a, **k)
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)[:200]}


def run(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()


# ---------------------------------------------------------------- engine B helpers
B_LIVE = {'prompt': None, 'params': {}, 'control_scale': None, 'negative': None}   # last values applied live (re-applied after a rebuild)


def b_state():
    return try_http(B + '/api/state', timeout=4)


def steps_strength_to_tindex(steps, strength):
    """t_index_list from (steps 1-4, strength 0-1): the first index sets how far from the input
    we start (lower = more change), later steps spread towards the end of the schedule."""
    steps = max(1, min(4, int(steps))); strength = max(0.05, min(0.95, float(strength)))
    start = int(round((1.0 - strength) * 45)); span = 45 - start
    return [min(49, start + int(round(span * i / steps))) for i in range(steps)]


def b_apply_params(p):
    out = {}
    body = {}
    if 't_index_list' in p:
        body['t_index_list'] = [int(x) for x in p['t_index_list']]
    elif 'steps' in p or 'strength' in p:
        cur = B_LIVE['params']
        st = p.get('steps', cur.get('steps', 1)); sg = p.get('strength', cur.get('strength', 0.5))
        body['t_index_list'] = steps_strength_to_tindex(st, sg); B_LIVE['params'].update(steps=st, strength=sg)
    for k in ('guidance_scale', 'delta', 'seed', 'num_inference_steps'):
        if k in p and p[k] is not None:
            body[k] = p[k]
    if body:
        out['params'] = try_http(B + '/api/params', 'POST', body); B_LIVE['params'].update({k: v for k, v in body.items()})
    if 'control_scale' in p and p['control_scale'] is not None:
        out['control'] = try_http(B + '/api/controlnet/update-strength', 'POST', {'index': 0, 'strength': float(p['control_scale'])})
        B_LIVE['control_scale'] = float(p['control_scale'])
    return out


def b_apply_prompt(prompt):
    B_LIVE['prompt'] = prompt
    return try_http(B + '/api/blending', 'POST', {'prompt_list': [[prompt, 1.0]], 'prompt_interpolation_method': 'slerp'})


def b_apply_negative(negative):
    """Live when the demo carries the booth patch (POST /api/params negative_prompt — the library
    re-encodes the prompt embeddings, no rebuild). Fallback for an unpatched demo: rewrite the
    config and re-upload it (pipeline rebuilt on the kiosk's next stream request, ~20 s black),
    then re-apply the values the technician set live since the last upload."""
    neg = negative.strip()
    for term in SAFETY.split(', '):
        if term not in neg:
            neg = (neg + ', ' if neg else '') + term
    r = try_http(B + '/api/params', 'POST', {'negative_prompt': neg}, timeout=20)
    st = b_state()
    if isinstance(st, dict) and st.get('negative_prompt') == neg:
        B_LIVE['negative'] = neg
        return {'live': True, 'negative': neg}
    log('negative: live route not available (unpatched demo?) — falling back to a config re-upload')
    txt = open(SD_CONFIG).read()
    txt2 = re.sub(r'^negative_prompt:.*$', 'negative_prompt: ' + json.dumps(neg), txt, count=1, flags=re.M)
    if B_LIVE['prompt']:
        txt2 = re.sub(r'^prompt:.*$', 'prompt: ' + json.dumps(B_LIVE['prompt']), txt2, count=1, flags=re.M)
    open(SD_CONFIG, 'w').write(txt2)
    r = try_http(B + '/api/controlnet/upload-config', 'POST', form=('booth_sd15_depth.yaml', txt2.encode()), timeout=60)
    threading.Thread(target=_b_reapply_after_rebuild, daemon=True).start()
    return {'upload': r if isinstance(r, dict) and 'error' in r else 'ok', 'negative': neg}


def _b_reapply_after_rebuild():
    for _ in range(90):
        time.sleep(2)
        st = b_state()
        if isinstance(st, dict) and st.get('pipeline_lifecycle') == 'running' and not st.get('config_needs_reload'):
            break
    time.sleep(2)
    if B_LIVE['prompt']:
        b_apply_prompt(B_LIVE['prompt'])
    p = dict(B_LIVE['params'])
    if B_LIVE['control_scale'] is not None:
        p['control_scale'] = B_LIVE['control_scale']
    if p:
        b_apply_params(p)
    log('engine B rebuilt after negative-prompt change; live values re-applied')


FLICKER = {'on': False, 'ms': 150}


def flicker_loop():
    while True:
        if FLICKER['on']:
            try_http(B + '/api/params', 'POST', {'seed': random.randint(1, 2**31 - 1)}, timeout=2)
            time.sleep(max(0.05, FLICKER['ms'] / 1000.0))
        else:
            time.sleep(0.3)


threading.Thread(target=flicker_loop, daemon=True).start()


# ---------------------------------------------------------------- engine A helpers
def a_params(p):
    return try_http(A + '/api/v1/session/parameters', 'POST', p, timeout=15)


# ---------------------------------------------------------------- preview (DevTools screenshot of the kiosk)
PREVIEW = {'ws': None, 'lock': threading.Lock(), 'vw': None, 'vh': None, 'last': None, 'at': 0}


def preview_jpeg(width=480):
    with PREVIEW['lock']:
        if PREVIEW['last'] and time.time() - PREVIEW['at'] < 0.25:
            return PREVIEW['last']
        try:
            if PREVIEW['ws'] is None:
                PREVIEW['ws'] = cdp.WS(cdp.page()['webSocketDebuggerUrl'])
                m = PREVIEW['ws'].call('Page.getLayoutMetrics')          # cdp.WS.call returns the result dict
                vp = m.get('cssVisualViewport') or m.get('visualViewport') or {}
                PREVIEW['vw'], PREVIEW['vh'] = vp.get('clientWidth', 1920), vp.get('clientHeight', 1080)
            scale = min(1.0, width / float(PREVIEW['vw'] or width))
            r = PREVIEW['ws'].call('Page.captureScreenshot', format='jpeg', quality=55,
                                   clip={'x': 0, 'y': 0, 'width': PREVIEW['vw'], 'height': PREVIEW['vh'], 'scale': scale})
            PREVIEW['last'] = base64.b64decode(r['data']); PREVIEW['at'] = time.time()
            return PREVIEW['last']
        except Exception as e:  # noqa: BLE001
            PREVIEW['ws'] = None
            raise


# ---------------------------------------------------------------- full-rate preview: relay the kiosk's own screencast as MJPEG
class Screencast:
    """One DevTools screencast of the kiosk page, fanned out to every /api/preview.mjpg client.
    Runs only while a client is connected; the browser pushes a frame per repaint (JPEG,
    downscaled by Chromium itself), so the cost stays small."""
    def __init__(self):
        self.lock = threading.Lock(); self.cond = threading.Condition(self.lock)
        self.clients = 0; self.seq = 0; self.frame = None; self.thread = None; self.err = None

    def _run(self):
        try:
            ws = cdp.WS(cdp.page()['webSocketDebuggerUrl']); ws.s.settimeout(5)
            ws.call('Page.enable'); ws.call('Page.startScreencast', format='jpeg', quality=60, maxWidth=540, maxHeight=960, everyNthFrame=1)
            idle = 0
            while True:
                with self.lock:
                    if self.clients <= 0:
                        idle += 1
                        if idle > 3: break
                    else:
                        idle = 0
                try:
                    msg = json.loads(ws.recv())
                except socket.timeout:
                    continue
                if msg.get('method') == 'Page.screencastFrame':
                    p = msg['params']
                    with self.cond:
                        self.frame = base64.b64decode(p['data']); self.seq += 1; self.cond.notify_all()
                    ws.n += 1; ws.send({'id': ws.n, 'method': 'Page.screencastFrameAck', 'params': {'sessionId': p['sessionId']}})
            try: ws.call('Page.stopScreencast')
            except Exception: pass
        except Exception as e:  # noqa: BLE001
            self.err = str(e)[:200]
        finally:
            with self.cond:
                self.thread = None; self.cond.notify_all()

    def attach(self, new_client=True):
        with self.lock:
            if new_client:
                self.clients += 1
            if self.thread is None:
                self.err = None; self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()

    def detach(self):
        with self.lock:
            self.clients = max(0, self.clients - 1)

    def next_frame(self, last_seq, timeout=2.0):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != last_seq or self.thread is None, timeout=timeout)
            return (self.frame, self.seq) if self.seq != last_seq else (None, last_seq)


SCREENCAST = Screencast()


def box_info():
    lan = run("ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \\K[0-9.]+'").split('\n')[0].strip()
    ts = run('tailscale ip -4 2>/dev/null').split('\n')[0].strip()
    views = [{'via': 'LAN', 'ip': lan, 'url': f'http://{lan}:{PORT}/view.html'} for _ in [0] if lan]
    if ts: views.append({'via': 'tailscale', 'ip': ts, 'url': f'http://{ts}:{PORT}/view.html'})
    return {'lan_ip': lan, 'tailscale_ip': ts, 'views': views, 'panel_port': PORT,
            'presets_file': PRESETS_FILE, 'kiosk_urls': {'B': KIOSK_B, 'A': KIOSK_A, 'OFF': KIOSK_OFF}}


# ---------------------------------------------------------------- status
def status():
    b = b_state()
    a_health = try_http(A + '/health', timeout=3); a_pipe = try_http(A + '/api/v1/pipeline/status', timeout=3); a_metrics = try_http(A + '/api/v1/session/metrics', timeout=3)
    gpu = run("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits")
    show = os.path.exists(os.path.join(STATE_DIR, 'showmode.stopped'))
    stopped = open(os.path.join(STATE_DIR, 'showmode.stopped')).read().split() if show else []
    kiosk_active = run('systemctl --user is-active booth-kiosk.service') == 'active'
    kiosk_url = ws_state = None
    try:
        pg = cdp.page(); kiosk_url = pg.get('url')
        ws = cdp.WS(pg['webSocketDebuggerUrl'])
        r = ws.call('Runtime.evaluate', expression='window.__booth&&window.__booth.ws?window.__booth.ws.readyState:-1', returnByValue=True)
        ws_state = r['result'].get('value')
    except Exception:  # noqa: BLE001
        pass
    tmux = run('tmux ls 2>/dev/null | cut -d: -f1').split()
    return {
        'time': time.strftime('%H:%M:%S'),
        'b': {'up': isinstance(b, dict) and 'error' not in b, 'fps': b.get('fps') if isinstance(b, dict) else None,
              'lifecycle': b.get('pipeline_lifecycle') if isinstance(b, dict) else None, 'resolution': b.get('resolution') if isinstance(b, dict) else None,
              'prompt': (b.get('prompt_blending') or [[b.get('config_prompt', '')]])[0][0] if isinstance(b, dict) and 'error' not in b else None,
              'negative': b.get('negative_prompt') if isinstance(b, dict) else None,
              't_index_list': b.get('t_index_list') if isinstance(b, dict) else None, 'seed': b.get('seed') if isinstance(b, dict) else None,
              'guidance_scale': b.get('guidance_scale') if isinstance(b, dict) else None, 'delta': b.get('delta') if isinstance(b, dict) else None,
              'control_scale': ((b.get('controlnet') or {}).get('controlnets') or [{}])[0].get('conditioning_scale') if isinstance(b, dict) and 'error' not in b else None,
              'model': b.get('model_id') if isinstance(b, dict) else None, 'flicker': FLICKER['on'], 'live': B_LIVE['params']},
        'a': {'up': isinstance(a_health, dict) and a_health.get('status') == 'healthy', 'pipeline': a_pipe if isinstance(a_pipe, dict) else None,
              'sessions': a_metrics.get('sessions') if isinstance(a_metrics, dict) else None},
        'gpu': dict(zip(('mem_used', 'mem_total', 'util', 'temp'), [x.strip() for x in gpu.split(',')])) if ',' in gpu else {'raw': gpu[:80]},
        'showmode': {'on': show, 'stopped': stopped},
        'kiosk': {'active': kiosk_active, 'url': kiosk_url, 'ws': ws_state,
                  'engine': 'A' if kiosk_url and 'scope.html' in kiosk_url else ('OFF' if kiosk_url and 'blank.html' in kiosk_url else ('B' if kiosk_url else None))},
        'loaded_preset': LOADED_PRESET['name'],
        'tmux': tmux, 'log': LOG[-12:], 'switch': {k: SWITCH[k] for k in ('running', 'target', 'step', 'error')},
    }


# ---------------------------------------------------------------- presets
PRESET_LOCK = threading.Lock()


def presets():
    """Live presets: $BOOTH_STATE/presets.json, seeded from the repo file on first use."""
    if not os.path.exists(PRESETS_FILE):
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(PRESETS_REPO) as f, open(PRESETS_FILE, 'w') as g:
            g.write(f.read())
    return json.load(open(PRESETS_FILE))


def save_preset(name, values, mode, notes=''):
    """mode 'new' refuses an existing name; mode 'update' refuses a missing one — the UI asks
    for a confirm before 'update'. Writes atomically, keeps a dated backup of the previous file."""
    name = (name or '').strip()
    if not name:
        return {'error': 'a preset needs a name'}
    with PRESET_LOCK:
        d = presets(); items = d['presets']; idx = next((i for i, x in enumerate(items) if x['name'] == name), None)
        if mode == 'new' and idx is not None:
            return {'error': f'"{name}" exists — use Update, or pick another name'}
        if mode == 'update' and idx is None:
            return {'error': f'no preset "{name}" to update'}
        neg = values.get('negative', '')
        for term in SAFETY.split(', '):
            if term not in neg:
                neg = (neg + ', ' if neg else '') + term
        entry = {'name': name, 'prompt': values.get('prompt', ''), 'negative': neg,
                 'control_scale': float(values.get('control_scale', 0.9)), 'strength': float(values.get('strength', 0.5)),
                 'steps': int(values.get('steps', 1)), 'seed_lock': bool(values.get('seed_lock', True)),
                 'guidance_scale': float(values.get('guidance_scale', 1.0)), 'delta': float(values.get('delta', 0.7)),
                 'seed': int(values.get('seed', 42)), 'noise_scale': float(values.get('noise_scale', 0.7)),
                 'vace_scale': float(values.get('vace_scale', 0.85)),
                 'notes': notes if notes is not None else (items[idx].get('notes', '') if idx is not None else ''),
                 'updated': time.strftime('%Y-%m-%d %H:%M')}
        if idx is None:
            items.append(entry)
        else:
            entry['notes'] = notes if notes else items[idx].get('notes', ''); items[idx] = entry
        bak = PRESETS_FILE + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
        try: os.replace(PRESETS_FILE, bak)
        except FileNotFoundError: pass
        tmp = PRESETS_FILE + '.tmp'
        with open(tmp, 'w') as f: json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PRESETS_FILE)
        baks = sorted(x for x in os.listdir(STATE_DIR) if x.startswith('presets.json.bak-'))
        for old in baks[:-10]: os.remove(os.path.join(STATE_DIR, old))
    LOADED_PRESET.update(name=name, at=time.time()); log(f'preset {mode}: {name}')
    return {'saved': name, 'mode': mode, 'count': len(items)}


def remove_preset(name):
    with PRESET_LOCK:
        d = presets(); before = len(d['presets']); d['presets'] = [x for x in d['presets'] if x['name'] != name]
        if len(d['presets']) == before:
            return {'error': f'no preset "{name}"'}
        os.replace(PRESETS_FILE, PRESETS_FILE + '.bak-' + time.strftime('%Y%m%d-%H%M%S'))
        tmp = PRESETS_FILE + '.tmp'
        with open(tmp, 'w') as f: json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PRESETS_FILE)
    if LOADED_PRESET['name'] == name: LOADED_PRESET['name'] = None
    log(f'preset removed: {name}'); return {'removed': name, 'count': len(d['presets'])}


def apply_preset(name, engine):
    p = next((x for x in presets()['presets'] if x['name'] == name), None)
    if not p:
        return {'error': f'no preset {name}'}
    out = {'preset': p}
    if engine == 'A':
        out['prompt'] = a_params({'prompts': [{'text': p['prompt'], 'weight': 1.0}]})
        out['params'] = a_params({'vace_context_scale': float(p.get('vace_scale', p['control_scale'])), 'noise_scale': float(p.get('noise_scale', p['strength']))})
    else:
        out['prompt'] = b_apply_prompt(p['prompt'])
        out['params'] = b_apply_params({'control_scale': p['control_scale'], 'steps': p['steps'], 'strength': p['strength'],
                                        'seed': p.get('seed', 42), 'guidance_scale': p.get('guidance_scale'), 'delta': p.get('delta')})
        FLICKER['on'] = not bool(p.get('seed_lock', True))
        st = b_state()
        if isinstance(st, dict) and st.get('negative_prompt') != p['negative']:
            out['negative'] = b_apply_negative(p['negative'])
    LOADED_PRESET.update(name=name, at=time.time()); log(f'preset {name} → engine {engine}')
    return out


# ---------------------------------------------------------------- ops
TMUX_GUARD = ('tmux ls >/dev/null 2>&1 || systemd-run --user --scope --unit "booth-tmux-$(date +%s)" --quiet tmux start-server; ')
# The tmux server must NOT be born inside this panel's cgroup: a panel restart would then kill
# every session in it (engines, and VoiceClone — it happened on 2026-09-04). If no tmux server
# runs, start one in its own transient scope before creating a session.


def ops(action, arg=None):
    tools = os.path.join(ROOT, 'tools'); eng = os.path.join(ROOT, 'engines')
    if action == 'showmode_on':   return run(f'{tools}/showmode.sh on', 120)
    if action == 'showmode_off':  return run(f'{tools}/showmode.sh off', 120)
    if action == 'engine_b_stop': return run('tmux kill-session -t booth-b 2>&1; echo stopped')
    if action == 'engine_b_start':
        return run(TMUX_GUARD + f'tmux has-session -t booth-b 2>/dev/null && echo "already running" || (tmux new-session -d -s booth-b "{eng}/b-streamdiffusion/run.sh 2>&1 | tee -a {STATE_DIR}/logs/engine_b_server.log" && echo started)')
    if action == 'engine_a_stop': return run('tmux kill-session -t booth-a 2>&1; echo stopped')
    if action == 'engine_a_start':
        return run(TMUX_GUARD + f'tmux has-session -t booth-a 2>/dev/null && echo "already running" || (tmux new-session -d -s booth-a "{eng}/a-scope/run.sh 2>&1 | tee -a {STATE_DIR}/logs/engine_a_server.log" && echo started)')
    if action == 'engine_a_free':   # Scope keeps ~22 GB loaded after a session stop: restart it to free the GPU
        return run(f'tmux kill-session -t booth-a 2>/dev/null; sleep 2; ' + TMUX_GUARD + f'tmux new-session -d -s booth-a "{eng}/a-scope/run.sh 2>&1 | tee -a {STATE_DIR}/logs/engine_a_server.log"; echo "scope restarted (VRAM freed)"')
    if action == 'kiosk_restart': return run('systemctl --user restart --no-block booth-kiosk.service && echo "restart queued"')
    if action in ('kiosk_b', 'kiosk_a', 'kiosk_off', 'kiosk_url'):
        url = {'kiosk_b': KIOSK_B, 'kiosk_a': KIOSK_A, 'kiosk_off': KIOSK_OFF}.get(action, arg)
        conf = os.path.join(ROOT, 'booth.conf'); txt = open(conf).read() if os.path.exists(conf) else ''
        txt = re.sub(r'^KIOSK_URL=.*\n?', '', txt, flags=re.M).rstrip('\n') + f'\nKIOSK_URL="{url}"\n'
        open(conf, 'w').write(txt); PREVIEW['ws'] = None
        return run('systemctl --user restart --no-block booth-kiosk.service && echo "kiosk → ' + url + '"')
    return f'unknown action {action}'


# ---------------------------------------------------------------- engine switch (one button, all the steps)
SWITCH = {'running': False, 'target': None, 'step': '', 'steps': [], 'error': None, 'done_at': None}


def _sw(step):
    SWITCH['step'] = step; SWITCH['steps'].append(f"{time.strftime('%H:%M:%S')} {step}"); log('switch: ' + step)


def _wait(fn, timeout, every=2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(every)
    return False


def _kiosk_shows(fragment, timeout=40):
    def on_page():
        try: return fragment in (cdp.page().get('url') or '')
        except Exception: return False
    return _wait(on_page, timeout, 2)


def switch_job(target):
    try:
        if target == 'OFF':
            _sw('visitor screen → black'); ops('kiosk_off'); FLICKER['on'] = False
            _sw('stopping Engine B'); ops('engine_b_stop')
            _sw('stopping Scope (session + server, frees the GPU)'); try_http(A + '/api/v1/session/stop', 'POST', {}, timeout=10); ops('engine_a_stop')
            _wait(lambda: 'error' in try_http(B + '/api/fps', timeout=2) and 'error' in try_http(A + '/health', timeout=2), 30, 2)
            _kiosk_shows('blank.html')
            _sw('done — stopped, screen black, GPU free for the other tenants')
        elif target == 'A':
            _sw('kiosk → Scope page (waits for the pipeline)'); ops('kiosk_a')
            _sw('stopping Engine B (frees ~5 GB)'); ops('engine_b_stop')
            if not (isinstance(try_http(A + '/health', timeout=3), dict) and 'error' not in try_http(A + '/health', timeout=3)):
                _sw('starting Scope server'); ops('engine_a_start')
                if not _wait(lambda: 'error' not in try_http(A + '/health', timeout=3), 120): raise RuntimeError('Scope did not come up')
            st = try_http(A + '/api/v1/pipeline/status', timeout=5)
            if not (st.get('status') == 'loaded' and st.get('pipeline_id') == 'longlive'):
                _sw('loading LongLive (480x832, tiny VAE, VACE weights) — 1–3 min'); try_http(A + '/api/v1/pipeline/load', 'POST', {'pipeline_ids': ['longlive'], 'load_params': A_LOAD}, timeout=30)
                def loaded():
                    s = try_http(A + '/api/v1/pipeline/status', timeout=5); SWITCH['step'] = f"loading LongLive… {s.get('loading_stage') or s.get('status')}"
                    if s.get('status') == 'error' or s.get('error'): raise RuntimeError(f"pipeline load failed: {s.get('error')}")
                    return s.get('status') == 'loaded'
                if not _wait(loaded, 900, 3): raise RuntimeError('pipeline load timed out')
            _sw('waiting for the kiosk page to connect over WebRTC'); _kiosk_shows('scope.html')
            def streaming():
                s = try_http(A + '/api/v1/session/metrics', timeout=5); return bool(s.get('sessions'))
            _wait(streaming, 60, 2)
            _sw('done — kiosk on Engine A (LongLive); VACE weights loaded, VACE off until toggled')
        else:
            _sw('kiosk → Engine B page (waits for the engine)'); ops('kiosk_b')
            _sw('stopping the Scope session and freeing its VRAM (Scope restarts idle)'); try_http(A + '/api/v1/session/stop', 'POST', {}, timeout=10); ops('engine_a_free')
            _sw('starting Engine B'); ops('engine_b_start')
            if not _wait(lambda: 'error' not in try_http(B + '/api/settings', timeout=3), 180): raise RuntimeError('Engine B did not come up')
            _sw('Engine B up — the kiosk page reconnects and the pipeline rebuilds (~30 s)'); _kiosk_shows('output.html')
            _wait(lambda: (b_state().get('fps') or 0) > 1, 120, 3)
            _sw('done — kiosk on Engine B')
    except Exception as e:  # noqa: BLE001
        SWITCH['error'] = str(e)[:300]; _sw('FAILED: ' + SWITCH['error'])
    finally:
        SWITCH['running'] = False; SWITCH['done_at'] = time.time()


def start_switch(target):
    if SWITCH['running']:
        return {'error': f"a switch to {SWITCH['target']} is already running"}
    SWITCH.update(running=True, target=target, step='starting', steps=[], error=None, done_at=None)
    threading.Thread(target=switch_job, args=(target,), daemon=True).start()
    return {'started': target}


# ---------------------------------------------------------------- HTTP
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(HERE, 'www'), **k)

    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == '/api/status':
            return self._json(status())
        if u.path == '/api/presets':
            return self._json(presets())
        if u.path == '/api/switch/status':
            return self._json(SWITCH)
        if u.path == '/api/info':
            return self._json(box_info())
        if u.path == '/api/preview.mjpg':
            self.send_response(200); self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store'); self.end_headers()
            # Stays open until the CLIENT leaves: if the screencast dies (kiosk restarted during an
            # engine switch), re-attach every second; while nothing repaints, re-send the last frame
            # every 2 s so the browser keeps the stream alive.
            SCREENCAST.attach(); seq = 0; last_sent = time.time(); last_frame = None
            try:
                while True:
                    if SCREENCAST.thread is None:
                        time.sleep(1.0); SCREENCAST.attach(new_client=False)
                    frame, seq2 = SCREENCAST.next_frame(seq)
                    if frame is None:
                        if last_frame is not None and time.time() - last_sent > 2.0:
                            frame = last_frame
                        else:
                            continue
                    else:
                        seq = seq2; last_frame = frame
                    last_sent = time.time()
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n'); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                SCREENCAST.detach()
            return
        if u.path == '/api/preview.jpg':
            try:
                data = preview_jpeg(int(q.get('w', ['480'])[0]))
            except Exception as e:  # noqa: BLE001
                return self._json({'error': f'no preview: {e}'}, 503)
            self.send_response(200); self.send_header('Content-Type', 'image/jpeg'); self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data); return
        if u.path == '/':
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); body = json.loads(self.rfile.read(n) or b'{}')
        p = self.path
        try:
            if p == '/api/preset/apply':   r = apply_preset(body['name'], body.get('engine', 'B'))
            elif p == '/api/b/prompt':     r = b_apply_prompt(body['prompt']); log('B prompt: ' + body['prompt'][:60])
            elif p == '/api/b/negative':   r = b_apply_negative(body.get('negative', '')); log('B negative → rebuild')
            elif p == '/api/b/params':     r = b_apply_params(body)
            elif p == '/api/b/flicker':    FLICKER.update(on=bool(body.get('on')), ms=int(body.get('ms', 150))); r = dict(FLICKER)
            elif p == '/api/a/prompt':     r = a_params({'prompts': [{'text': body['prompt'], 'weight': 1.0}]}); log('A prompt: ' + body['prompt'][:60])
            elif p == '/api/a/params':     r = a_params(body)
            elif p == '/api/a/reset':      r = a_params({'reset_cache': True}); log('A reset')
            elif p == '/api/ops':          r = ops(body['action'], body.get('arg')); log(f"ops {body['action']}: {str(r)[-80:]}")
            elif p == '/api/switch':       r = start_switch(body.get('engine', 'B').upper())
            elif p == '/api/presets/save': r = save_preset(body.get('name'), body.get('values', {}), body.get('mode', 'new'), body.get('notes'))
            elif p == '/api/presets/remove': r = remove_preset(body.get('name', ''))
            else:                          return self._json({'error': 'unknown endpoint'}, 404)
            self._json({'ok': True, 'result': r})
        except Exception as e:  # noqa: BLE001
            self._json({'ok': False, 'error': str(e)[:300]}, 500)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True


if __name__ == '__main__':
    log(f'booth panel on 0.0.0.0:{PORT} — B {B} · A {A} · kiosk CDP :{CDP_PORT}')
    Server(('0.0.0.0', PORT), H).serve_forever()
