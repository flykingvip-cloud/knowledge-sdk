from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import knowledge_sdk
from knowledge_sdk import Actor, LocalKnowledgeClient
from knowledge_sdk.exceptions import ValidationError
from knowledge_sdk.server.auth import InMemoryReplayStore, signed_headers

AVAILABLE = all(importlib.util.find_spec(m) is not None for m in ('fastapi', 'httpx'))
if AVAILABLE:
    from fastapi import Request
SECRET = 'phase1-mount-not-real-secret-' + 'x'*32
ACTOR = Actor('owner', 'org1')


@unittest.skipUnless(AVAILABLE, 'optional HTTP dependencies unavailable')
class Phase1MountTests(unittest.TestCase):
    def setUp(self):
        from knowledge_sdk.storage.sqlite_store import SQLiteStore
        self.local = LocalKnowledgeClient(SQLiteStore(':memory:'))
        self.addCleanup(self.local.store.close)

    def app(self, **kwargs):
        from knowledge_sdk.server.app import create_app
        return create_app(self.local, auth_secret=SECRET, **kwargs)

    def http(self, app, **kwargs):
        from fastapi.testclient import TestClient
        client = TestClient(app, **kwargs)
        self.addCleanup(client.close)
        return client

    def test_prefix_validation(self):
        for prefix in ('', '/', 'ui', '//ui', '/kb//ui', '/kb/../ui', '/u i', '/v1', '/v1/', '/v1/ui', '/ui?x=1', '/ui#x', '/%75i', '/ui\\assets', '/ui/./x', '/docs', '/redoc', '//evil.invalid/ui'):
            with self.subTest(prefix=prefix), self.assertRaises(ValidationError):
                self.app(ui_prefix=prefix)

    def test_custom_prefix_normalized_resources_and_headers(self):
        client = self.http(self.app(ui_prefix='/kb/ui/'))
        for path in ('/kb/ui', '/kb/ui/', '/kb/ui/config', '/kb/ui/assets/workbench.js', '/kb/ui/assets/workbench.css', '/kb/ui/assets/i18n.js'):
            r = client.get(path)
            self.assertEqual(r.status_code, 200, path)
            for header in ('Content-Security-Policy', 'X-Content-Type-Options', 'Referrer-Policy', 'Cache-Control'):
                self.assertIn(header, r.headers)
            self.assertIn("script-src 'self'", r.headers['content-security-policy'])
            self.assertNotIn("'unsafe-inline'", r.headers['content-security-policy'])
            self.assertEqual(r.headers['cache-control'], 'no-store')
        html = client.get('/kb/ui').text
        self.assertIn('src="/kb/ui/assets/workbench.js"', html)
        self.assertNotIn('src="/ui/', html)
        config = client.get('/kb/ui/config').json()
        self.assertEqual(config['api_base'], '')
        self.assertEqual(config['signature_base'], '')
        self.assertEqual(config['ui_base'], '/kb/ui')
        self.assertEqual(config['operations']['list_kbs'][1], '/v1/kbs')
        for path in ('/ui', '/ui/', '/ui/config', '/ui/assets/i18n.js'):
            self.assertEqual(client.get(path).status_code, 404)

    def test_demo_never_enabled_by_headers(self):
        client = self.http(self.app(ui_prefix='/kb/ui'))
        for path in ('/ui/demo/sign', '/kb/ui/demo/sign'):
            for method in ('get', 'post'):
                r = getattr(client, method)(path, headers={'X-KB-Demo':'1', 'Origin':'http://testserver', 'X-Forwarded-For':'127.0.0.1'})
                self.assertEqual(r.status_code, 404)
        self.assertFalse(client.get('/kb/ui/config').json()['demo_enabled'])
        self.assertEqual(client.get('/v1/kbs').status_code, 401)

    def test_ui_boundaries_do_not_bypass_api_auth(self):
        client = self.http(self.app(ui_prefix='/kb/ui'))
        for path in ('/kb/uix/config', '/kb/ui/v1/kbs', '/kb/uiassets/x', '/kb/ui/configuration', '/kb/v1/kbs'):
            self.assertEqual(client.get(path).status_code, 401, path)

    def test_app_and_ui_dynamic_version(self):
        with patch.object(knowledge_sdk, '__version__', '1.2.0-dynamic-test'):
            app = self.app()
            self.assertEqual(app.version, '1.2.0-dynamic-test')
            self.assertEqual(self.http(app).get('/ui/config').json()['version'], '1.2.0-dynamic-test')
        self.assertEqual(knowledge_sdk.__version__, '1.2.0')

    def test_proxy_root_preserved_and_stripped_targets(self):
        # Exercise both ASGI raw_path contracts. root_path is trusted server config.
        for preserved in (False, True):
            app = self.app(ui_prefix='/kb/ui')
            client = self.http(app, root_path='/gateway')
            prefix = '/gateway' if preserved else ''
            config = client.get(prefix + '/kb/ui/config').json()
            self.assertEqual(config['api_base'], '/gateway')
            self.assertEqual(config['signature_base'], prefix)
            self.assertEqual(config['ui_base'], '/gateway/kb/ui')
            self.assertIn('src="/gateway/kb/ui/assets/workbench.js"', client.get(prefix + '/kb/ui').text)
            self.assertEqual(client.get(prefix + '/kb/ui/assets/i18n.js').status_code, 200)
            target = prefix + '/v1/kbs'
            h = signed_headers(ACTOR, SECRET, 'GET', target)
            self.assertEqual(client.get(target, headers=h).status_code, 200)
            self.assertEqual(client.post(prefix + '/kb/ui/demo/sign', json={}).status_code, 404)

    def test_forwarded_headers_do_not_set_bases(self):
        client = self.http(self.app(ui_prefix='/kb/ui'))
        c = client.get('/kb/ui/config', headers={'X-Forwarded-Prefix':'//evil.invalid', 'X-Forwarded-Host':'evil.invalid'}).json()
        self.assertEqual(c['api_base'], '')
        self.assertEqual(c['ui_base'], '/kb/ui')
        self.assertEqual(c['signature_base'], '')

    def test_duplicate_context_headers_rejected(self):
        client = self.http(self.app())
        path = '/v1/kbs'
        h = signed_headers(ACTOR, SECRET, 'GET', path, purpose='read')
        headers = list(h.items()) + [('x-kb-purpose', 'export')]
        self.assertEqual(client.get(path, headers=headers).status_code, 401)

    def test_shared_replay_across_app_workers(self):
        shared = InMemoryReplayStore()
        a = self.http(self.app(replay_store=shared))
        b = self.http(self.app(replay_store=shared))
        path = '/v1/kbs'
        headers = signed_headers(ACTOR, SECRET, 'GET', path)
        self.assertEqual(a.get(path, headers=headers).status_code, 200)
        self.assertEqual(b.get(path, headers=headers).status_code, 401)

    def test_default_replay_is_per_app(self):
        a, b = self.http(self.app()), self.http(self.app())
        path = '/v1/kbs'
        headers = signed_headers(ACTOR, SECRET, 'GET', path)
        self.assertEqual(a.get(path, headers=headers).status_code, 200)
        self.assertEqual(a.get(path, headers=headers).status_code, 401)
        self.assertEqual(b.get(path, headers=headers).status_code, 200)

    def test_request_state_context_and_401_on_tamper(self):
        from fastapi import Request
        app = self.app()
        @app.get('/v1/context')
        async def context(request: Request):
            return {'agent':request.state.agent, 'purpose':request.state.purpose}
        client = self.http(app)
        path = '/v1/context'
        h = signed_headers(ACTOR, SECRET, 'GET', path)
        self.assertEqual(client.get(path, headers=h).json(), {'agent':None,'purpose':'read'})
        agent = {'agent_id':'a','org_id':'org1'}
        h = signed_headers(ACTOR, SECRET, 'GET', path, agent=agent, purpose='export')
        self.assertEqual(client.get(path, headers=h).json(), {'agent':agent,'purpose':'export'})
        h['X-KB-Purpose'] = 'eval_and_train'
        self.assertEqual(client.get(path, headers=h).status_code, 401)
        h['X-KB-Purpose'] = 'invalid'
        self.assertEqual(client.get(path, headers=h).status_code, 401)

    def test_demo_subpath_signs_exact_target_with_root(self):
        for prefix in ('', '/gateway'):
            client = self.http(self.app(ui_prefix='/kb/ui', enable_demo_switcher=True), root_path=prefix,
                               base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
            target = prefix + '/v1/kbs'
            response = client.post(prefix + '/kb/ui/demo/sign', json={'actor':{'user_id':'owner','org_id':'org1'},'method':'GET','target':target},
                                   headers={'Origin':'http://127.0.0.1','X-KB-Demo':'1'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(client.get(target, headers=response.json()['headers']).status_code, 200)

    def test_identity_controls_disabled_before_javascript(self):
        from html.parser import HTMLParser
        class Controls(HTMLParser):
            def __init__(self):
                super().__init__(); self.identity = False; self.controls = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'form' and attrs.get('id') == 'identity-form': self.identity = True
                if self.identity and tag in ('input','select','button'): self.controls.append(attrs)
            def handle_endtag(self, tag):
                if tag == 'form': self.identity = False
        parser = Controls()
        parser.feed(self.http(self.app()).get('/ui').text)
        self.assertGreater(len(parser.controls), 5)
        self.assertTrue(all('disabled' in c for c in parser.controls))
        parser = Controls()
        parser.feed(self.http(self.app(enable_demo_switcher=True)).get('/ui').text)
        self.assertTrue(all('disabled' not in c for c in parser.controls))

    def test_invalid_fallback_rejected_on_startup(self):
        with self.assertRaises(ValidationError):
            self.app(fallback_secrets=('short',))

    def test_cli_options_present(self):
        p = subprocess.run([sys.executable,'-m','knowledge_sdk.server','--help'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn('--replay-db', p.stdout)
        self.assertIn('--ui-prefix', p.stdout)
