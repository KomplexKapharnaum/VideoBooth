#!/usr/bin/env python3
"""cdp.py — talk to the kiosk Chrome over DevTools (--remote-debugging-port=9222), stdlib only.

  cdp.py 'navigator.userAgent'                      # evaluate JS, print the value
  cdp.py --await 'navigator.mediaDevices.enumerateDevices().then(d => JSON.stringify(d))'
  cdp.py --reload                                   # Page.reload
  cdp.py --screenshot /tmp/shot.png                 # Page.captureScreenshot (png)
  cdp.py --title                                    # list page titles
"""
import base64
import json
import os
import socket
import struct
import sys
import urllib.request

PORT = int(os.environ.get('CDP_PORT', '9222'))


def page():
    tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=3))
    return next(t for t in tabs if t.get('type') == 'page')


class WS:
    def __init__(self, url):
        host, path = url.split('//', 1)[1].split('/', 1)
        h, p = host.split(':')
        self.s = socket.create_connection((h, int(p)), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.send((f'GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                     f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        resp = b''
        while b'\r\n\r\n' not in resp:
            resp += self.s.recv(4096)
        self.n = 0

    def _rd(self, n):
        b = b''
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise EOFError('websocket closed')
            b += c
        return b

    def send(self, obj):
        data = json.dumps(obj).encode()
        n = len(data)
        hdr = bytes([0x81])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack('>H', n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack('>Q', n)
        mask = os.urandom(4)
        self.s.send(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        while True:
            b1, b2 = self._rd(2)
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
            if op in (0x1, 0x2):
                return payload

    def call(self, method, **params):
        self.n += 1
        self.send({'id': self.n, 'method': method, 'params': params})
        while True:
            m = json.loads(self.recv())
            if m.get('id') == self.n:
                if 'error' in m:
                    raise SystemExit(f'CDP error: {m["error"]}')
                return m.get('result', {})


def main():
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'):
        print(__doc__); return
    if a[0] == '--title':
        for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=3)):
            if t.get('type') == 'page':
                print(t.get('title', ''), '·', t.get('url', ''))
        return
    ws = WS(page()['webSocketDebuggerUrl'])
    if a[0] == '--reload':
        ws.call('Page.reload', ignoreCache=True); print('reloaded'); return
    if a[0] == '--screenshot':
        r = ws.call('Page.captureScreenshot', format='png')
        with open(a[1], 'wb') as f:
            f.write(base64.b64decode(r['data']))
        print('wrote', a[1]); return
    r = ws.call('Runtime.evaluate', expression=a[-1], awaitPromise='--await' in a, returnByValue=True)
    res = r.get('result', {})
    if 'exceptionDetails' in r:
        print('EXCEPTION:', r['exceptionDetails'].get('exception', {}).get('description', r['exceptionDetails']))
    elif 'value' in res:
        v = res['value']
        print(v if isinstance(v, str) else json.dumps(v))
    else:
        print(json.dumps(res))


if __name__ == '__main__':
    main()
