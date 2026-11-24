"""L3 real loopback HTTP only. Random ephemeral credentials are never logged."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from knowledge_sdk import Actor
from knowledge_sdk.server.auth import signed_headers

ROOT = Path(__file__).resolve().parents[3]

def main():
    secret, fallback = secrets.token_hex(32), secrets.token_hex(32)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), KNOWLEDGE_AUTH_SECRET=secret,
               KNOWLEDGE_AUTH_FALLBACK_SECRETS=fallback)
    for key in list(env):
        if key.startswith('KNOWLEDGE_SDK_LIVE_'):
            env.pop(key)
    with tempfile.TemporaryDirectory(prefix='kb-phase1-live-') as tmp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = 'http://127.0.0.1:' + str(port)
        command = [sys.executable, '-m', 'knowledge_sdk.server', '--host', '127.0.0.1',
                   '--port', str(port), '--replay-db', str(Path(tmp) / 'replay.sqlite3'), '--ui-prefix', '/kb/ui']
        print('$ PYTHONPATH=src KNOWLEDGE_AUTH_SECRET=<random, redacted> KNOWLEDGE_AUTH_FALLBACK_SECRETS=<random, redacted>', ' '.join(command), flush=True)
        with tempfile.TemporaryFile(mode='w+') as server_log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=server_log, stderr=subprocess.STDOUT)
            def request(path, method='GET', headers=None):
                try:
                    with urllib.request.urlopen(urllib.request.Request(base + path, method=method, headers=headers or {}), timeout=2) as response:
                        return response.status, response.headers, response.read()
                except urllib.error.HTTPError as error:
                    return error.code, error.headers, error.read()
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Isolated server failed startup')
                    try:
                        if request('/v1/health')[0] == 200:
                            break
                    except (OSError, TimeoutError):
                        pass
                    threading.Event().wait(0.05)
                else:
                    raise RuntimeError('Timed out starting isolated server')
                for path in ('/kb/ui', '/kb/ui/', '/kb/ui/config', '/kb/ui/assets/workbench.css', '/kb/ui/assets/workbench.js', '/kb/ui/assets/i18n.js'):
                    status, headers, body = request(path)
                    assert status == 200, (path, status)
                    assert headers['Cache-Control'] == 'no-store'
                    assert headers['X-Content-Type-Options'] == 'nosniff'
                    assert headers['Referrer-Policy'] == 'no-referrer'
                    assert "script-src 'self'" in headers['Content-Security-Policy']
                    print('GET', path, status, 'security headers PASS', 'body_sha256=' + hashlib.sha256(body).hexdigest())
                    if path.endswith('/config'):
                        config = json.loads(body)
                        assert config['version'] == '1.2.0' and not config['demo_enabled']
                        assert config['api_base'] == '' and config['ui_base'] == '/kb/ui'
                for path in ('/ui', '/ui/config', '/ui/demo/sign', '/kb/ui/demo/sign'):
                    method = 'POST' if path.endswith('/sign') else 'GET'
                    status = request(path, method, {'X-KB-Demo':'1','Origin':base})[0]
                    assert status == 404, (path, status)
                    print(method, path, status)
                target = '/v1/kbs'
                assert request(target)[0] == 401
                print('Unsigned GET /v1/kbs 401')
                h = signed_headers(Actor('l3-probe','isolated-org'), secret, 'GET', target)
                assert request(target, headers=h)[0] == 200
                assert request(target, headers=h)[0] == 401
                print('Signed current-key GET /v1/kbs 200; exact replay 401')
                h = signed_headers(Actor('l3-probe','isolated-org'), fallback, 'GET', target)
                assert request(target, headers=h)[0] == 200
                print('Signed fallback-key GET /v1/kbs 200')
                h = signed_headers(Actor('l3-probe','isolated-org'), secret, 'GET', target, agent={'agent_id':'probe','org_id':'isolated-org'}, purpose='read')
                invalid = dict(h, **{'X-KB-Signature':'0'*64})
                assert request(target, headers=invalid)[0] == 401
                assert request(target, headers=h)[0] == 200
                print('Invalid signature 401 then same nonce valid signature 200 (no nonce poisoning)')
                h = signed_headers(Actor('l3-probe','isolated-org'), secret, 'GET', target, purpose='read')
                h['X-KB-Purpose'] = 'export'
                assert request(target, headers=h)[0] == 401
                print('Purpose tampering 401')
                print('Local real HTTP probe: PASS; no embedding/generation/remote vector backend configured or called')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
                print('Isolated server stopped; exit code:', process.returncode)
                server_log.seek(0)
                log = server_log.read()
                assert secret not in log and fallback not in log, 'Secret leaked in server output'
                print('\nRaw server output (verified contains no random secret values):\n' + log)
    print('Temporary replay database and memory-only business data removed with temp directory')

if __name__ == '__main__':
    main()
