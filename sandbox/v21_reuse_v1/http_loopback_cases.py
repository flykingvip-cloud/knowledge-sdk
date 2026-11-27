"""Wave-V21-3 stdlib HTTP loopback cases for the five official golden groups.

Test-only. This module binds a temporary 127.0.0.1:0 socket, serves JSON over
HTTP, and closes the listener in teardown/finally. It is not a product
Workbench or StratAI server, does not bind a non-loopback address, does not
touch port 3000, and does not open a real database.

HTTP paths are limited to /sandbox/v21/*. /v3/* is never mounted. The
EXPERIMENTAL_V3_ENABLED default remains false; this module does not set it.

X-V21-* headers reuse the official seven-key mapping already defined by
AIExecutionTraceContext.headers() (X-V21-Tenant-Id, X-V21-User-Id,
X-V21-Agent-Id, X-V21-Trace-Id, X-V21-Run-Id, X-V21-Plan-Id,
X-V21-Policy-Generation). This loopback does not invent a second header or
hash scheme. Routes other than /sandbox/v21/trace reuse the same official
names when the corresponding field is present in the JSON body. Hashing
still goes through sandbox.v21_reuse_v1.revocation.canonical_json_bytes.

This is isolated-branch sandbox coverage, not formal T-01-T-27 acceptance.
"""
from __future__ import annotations

import http.client
import http.server
import json
import os
import posixpath
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlparse

from sandbox.v21_reuse_v1.adapters import (
    TRACE_KEYS,
    AdapterError,
    AIExecutionTraceContext,
)
from sandbox.v21_reuse_v1.interop_harness import InteropHarness, load_golden
from sandbox.v21_reuse_v1.loopback_service import (
    EXPERIMENTAL_V3_ENV,
    experimental_v3_enabled,
)
from sandbox.v21_reuse_v1.revocation import canonical_json_bytes
from sandbox.v21_reuse_v1.semantic_reference import SemanticReferenceWriteForbidden

GOLDEN_PATH = Path(__file__).resolve().parent / 'fixtures' / 'w2_interop_golden.json'
W2_INTEROP_GOLDEN_SHA256 = 'f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef'
W2_INTEROP_GOLDEN_BYTE_LENGTH = 33863
HARD_RECEIPT_HASH_G4_POS_FOUR_CHANNEL_SUCCESS = 'f4055894fdebb0fc55ae563aaed03ab6f4162b53c4eeab31ad479f6c6707b476'
HARD_RECEIPT_HASH_G4_POS_CHANNEL_TIMEOUT_NOT_PURGED = '6e8c7f178ec452b590e0d0f06defa0a2c21c0fac5c6a672a356a02b31470f0d0'

# Official TRACE_KEYS <-> header names from AIExecutionTraceContext.headers().
OFFICIAL_KEY_TO_HEADER = {
    'tenant_id': 'X-V21-Tenant-Id',
    'user_id': 'X-V21-User-Id',
    'agent_id': 'X-V21-Agent-Id',
    'trace_id': 'X-V21-Trace-Id',
    'run_id': 'X-V21-Run-Id',
    'plan_id': 'X-V21-Plan-Id',
    'policy_generation': 'X-V21-Policy-Generation',
}
OFFICIAL_HEADER_TO_KEY = {header.lower(): key for key, header in OFFICIAL_KEY_TO_HEADER.items()}

SANDBOX_V21_PREFIX = '/sandbox/v21/'
ALLOWED_ROUTES = {
    ('POST', '/sandbox/v21/embed'): 'embed',
    ('POST', '/sandbox/v21/trace'): 'trace',
    ('POST', '/sandbox/v21/catalog/read'): 'catalog_read',
    ('POST', '/sandbox/v21/catalog/write'): 'catalog_write',
    ('POST', '/sandbox/v21/revocation'): 'revocation',
    ('POST', '/sandbox/v21/data-bridge'): 'data_bridge',
}


def _json_equal(actual, expected):
    return json.dumps(actual, sort_keys=True, separators=(',', ':'), ensure_ascii=False) == json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def official_headers_from_payload(payload):
    """Project official X-V21-* headers from a dict when the keys are present."""
    headers = {}
    if not isinstance(payload, dict):
        return headers
    for key, header in OFFICIAL_KEY_TO_HEADER.items():
        if key in payload and payload[key] is not None:
            headers[header] = str(payload[key])
    return headers


def _coerce_official_value(key, value):
    if key == 'policy_generation' and isinstance(value, str) and value.isdigit():
        return int(value)
    return value


def official_fields_from_request_headers(headers):
    extracted = {}
    for header_name, value in headers.items():
        key = OFFICIAL_HEADER_TO_KEY.get(header_name.lower())
        if key is None:
            continue
        extracted[key] = _coerce_official_value(key, value)
    return extracted


def merge_official_headers(body_fields, header_fields):
    merged = dict(body_fields)
    for key, value in header_fields.items():
        if key in merged and merged[key] != value:
            raise AdapterError('VALIDATION_ERROR')
        merged[key] = value
    return merged


def _normalized_path(raw_path):
    parsed = urlparse(raw_path)
    path = parsed.path or '/'
    if '..' in path.split('/'):
        return path, True
    return posixpath.normpath(path), False


class _SandboxV21Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def _read_json(self):
        length = int(self.headers.get('Content-Length') or '0')
        raw = self.rfile.read(length) if length else b''
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise AdapterError('VALIDATION_ERROR')
        if not isinstance(payload, dict):
            raise AdapterError('VALIDATION_ERROR')
        return payload

    def _write_json(self, status, payload, extra_headers=None):
        raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self):
        path, had_parent = _normalized_path(self.path)
        raw_path = urlparse(self.path).path or '/'
        if had_parent or raw_path.startswith('/v3') or path == '/v3' or path.startswith('/v3/'):
            self._write_json(403, dict(ok=False, error='V3_PRODUCTION_MOUNT_FORBIDDEN'))
            return
        if path != '/sandbox/v21' and not path.startswith(SANDBOX_V21_PREFIX):
            self._write_json(404, dict(ok=False, error='PATH_FORBIDDEN'))
            return
        route = ALLOWED_ROUTES.get((self.command, path))
        if route is None:
            self._write_json(404, dict(ok=False, error='PATH_FORBIDDEN'))
            return
        try:
            body = self._read_json()
            status, payload, extra = self._handle_route(route, body)
        except AdapterError as exc:
            self._write_json(400, dict(ok=False, error=exc.code))
            return
        except SemanticReferenceWriteForbidden as exc:
            disk_writes = self.server.harness.catalog.disk_writes
            self._write_json(400, dict(ok=False, error=exc.code, disk_writes=disk_writes))
            return
        self._write_json(status, payload, extra)

    def _handle_route(self, route, body):
        harness = self.server.harness
        header_fields = official_fields_from_request_headers(self.headers)
        if route == 'embed':
            payload = merge_official_headers(body, header_fields)
            result = harness.embed(payload)
            return 200, dict(ok=True, result=result), official_headers_from_payload(result)
        if route == 'trace':
            trace_body = dict(body.get('trace') or {})
            trace = merge_official_headers(trace_body, header_fields)
            result = harness.trace_hops(trace, hop_payloads=body.get('hop_payloads'))
            return 200, dict(ok=True, result=result), dict(result['headers'])
        if route == 'catalog_read':
            payload = merge_official_headers(body, header_fields)
            result = harness.catalog_read(payload.get('tenant_id'), payload.get('semantic_object_key'))
            return 200, dict(ok=True, result=result), official_headers_from_payload(payload)
        if route == 'catalog_write':
            # Writes are always rejected; still perform zero disk I/O.
            harness.catalog_write(body.get('payload') or body)
            raise AssertionError('catalog_write_should_not_return')
        if route == 'revocation':
            payload = merge_official_headers(body, header_fields)
            result = harness.purge_receipt(
                payload['tenant_id'], payload['subject_id'], payload['policy_generation'],
                payload['task_id'], failures=payload.get('failures') or {},
            )
            return 200, dict(ok=True, result=result), official_headers_from_payload(payload)
        if route == 'data_bridge':
            declaration = merge_official_headers(dict(body.get('declaration') or {}), header_fields)
            actual = harness.data_bridge_execute(declaration, body.get('query'))
            if actual.get('ok'):
                return 200, dict(ok=True, result=actual['result']), official_headers_from_payload(declaration)
            return 400, dict(ok=False, error=actual['error']), None
        raise AdapterError('PATH_FORBIDDEN')


class SandboxV21LoopbackServer(object):
    """Temporary 127.0.0.1:0 HTTP server. Must be stopped in finally/teardown."""

    def __init__(self, harness):
        self.harness = harness
        self._httpd = http.server.HTTPServer(('127.0.0.1', 0), _SandboxV21Handler)
        self._httpd.harness = harness
        self.host, self.port = self._httpd.server_address
        if self.host != '127.0.0.1':
            self.stop()
            raise RuntimeError('loopback bound a non-loopback address')
        if self.port == 3000:
            self.stop()
            raise RuntimeError('loopback must not use port 3000')
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs=dict(poll_interval=0.05),
            name='v21-http-loopback',
        )
        self._thread.daemon = True

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if httpd is not None:
            try:
                httpd.shutdown()
            finally:
                httpd.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError('loopback thread did not exit')

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False


class HttpLoopbackCases(unittest.TestCase):
    def setUp(self):
        self.golden = load_golden()
        self.groups = {group['id']: group for group in self.golden['groups']}
        self._disk = tempfile.TemporaryDirectory()
        self.harness = InteropHarness(catalog_records=self.golden['catalog_seed'])
        self.harness.catalog.disk_path = self._disk.name
        self.server = SandboxV21LoopbackServer(self.harness)
        self.server.start()

    def tearDown(self):
        disk = getattr(self, '_disk', None)
        server = getattr(self, 'server', None)
        try:
            if server is not None:
                server.stop()
        finally:
            if disk is not None:
                leftover = list(Path(disk.name).iterdir()) if Path(disk.name).exists() else []
                disk.cleanup()
                self.assertEqual(leftover, [])

    def _request(self, method, path, body=None, headers=None):
        header_map = dict(headers or {})
        raw = b''
        if body is not None:
            raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
            header_map.setdefault('Content-Type', 'application/json; charset=utf-8')
            header_map.setdefault('Content-Length', str(len(raw)))
        header_map.setdefault('Connection', 'close')
        conn = http.client.HTTPConnection(self.server.host, self.server.port, timeout=5)
        try:
            conn.request(method, path, body=raw, headers=header_map)
            response = conn.getresponse()
            data = response.read()
            payload = json.loads(data.decode('utf-8')) if data else None
            official = {}
            for header in OFFICIAL_KEY_TO_HEADER.values():
                value = response.getheader(header)
                if value is not None:
                    official[header] = value
            return response.status, official, payload
        finally:
            conn.close()

    def test_experimental_v3_enabled_remains_default_false(self):
        self.assertFalse(experimental_v3_enabled({}))
        self.assertFalse(experimental_v3_enabled({EXPERIMENTAL_V3_ENV: 'false'}))
        self.assertNotEqual(str(os.environ.get(EXPERIMENTAL_V3_ENV, 'false')).strip().lower(), 'true')
        self.assertIs(self.golden['experimental_v3_enabled_default'], False)
        self.assertEqual(self.golden['mount_production_http'], 'forbidden')

    def test_loopback_binds_ephemeral_loopback_only(self):
        self.assertEqual(self.server.host, '127.0.0.1')
        self.assertNotEqual(self.server.port, 0)
        self.assertNotEqual(self.server.port, 3000)
        status, _headers, payload = self._request('POST', '/sandbox/v21/catalog/read', dict(
            tenant_id='syn_org',
            semantic_object_key='semobj:openbot:finance.invoice',
        ), official_headers_from_payload(dict(tenant_id='syn_org')))
        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])

    def test_v3_paths_are_forbidden_and_unmounted(self):
        for path in ('/v3', '/v3/', '/v3/embed', '/v3/sandbox/v21/embed'):
            status, _headers, payload = self._request('POST', path, dict(probe=True))
            self.assertEqual(status, 403, path)
            self.assertEqual(payload, dict(ok=False, error='V3_PRODUCTION_MOUNT_FORBIDDEN'))
        status, _headers, payload = self._request('POST', '/sandbox/v21/../v3/embed', dict(probe=True))
        self.assertEqual(status, 403)
        self.assertEqual(payload['error'], 'V3_PRODUCTION_MOUNT_FORBIDDEN')

    def test_paths_outside_sandbox_v21_are_forbidden(self):
        for path in ('/', '/sandbox', '/sandbox/v21', '/sandbox/v21/unknown', '/health', '/v2/spaces'):
            status, _headers, payload = self._request('POST', path, dict(probe=True))
            self.assertEqual(status, 404, path)
            self.assertEqual(payload, dict(ok=False, error='PATH_FORBIDDEN'))

    def test_golden_fixture_bytes_remain_locked(self):
        import hashlib
        raw = GOLDEN_PATH.read_bytes()
        self.assertEqual(len(raw), W2_INTEROP_GOLDEN_BYTE_LENGTH)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), W2_INTEROP_GOLDEN_SHA256)

    def test_replay_g1_models_embed_over_http(self):
        for case in self.groups['G1_MODELS_EMBED']['cases']:
            headers = official_headers_from_payload(case['input'])
            status, _headers, payload = self._request('POST', '/sandbox/v21/embed', case['input'], headers)
            if case['expect'] == 'accept':
                self.assertEqual(status, 200, case['id'])
                self.assertTrue(payload['ok'], case['id'])
                actual = payload['result']
                expected = case['expected']
                self.assertEqual(actual['tenant_id'], expected['tenant_id'])
                self.assertEqual(actual['dim'], expected['dim'])
                self.assertTrue(_json_equal(actual['provider'], expected['provider']))
                self.assertTrue(_json_equal(actual['vectors'], expected['vectors']))
                self.assertEqual(
                    canonical_json_bytes(actual['vectors']).decode('utf-8'),
                    expected['vectors_canonical_json'],
                )
            else:
                self.assertEqual(status, 400, case['id'])
                self.assertFalse(payload['ok'])
                self.assertEqual(payload['error'], case['expected']['error'])

    def test_replay_g2_seven_key_hop_with_official_headers(self):
        for case in self.groups['G2_AI_EXECUTION_TRACE']['cases']:
            headers = official_headers_from_payload(case['input']['trace'])
            status, response_headers, payload = self._request(
                'POST', '/sandbox/v21/trace', case['input'], headers,
            )
            if case['expect'] == 'accept':
                self.assertEqual(status, 200, case['id'])
                self.assertTrue(payload['ok'], case['id'])
                actual = payload['result']
                expected = case['expected']
                self.assertEqual(list(actual['seven_keys']), list(TRACE_KEYS))
                self.assertEqual(actual['seven_keys'], expected['seven_keys'])
                self.assertEqual(actual['headers'], expected['headers'])
                self.assertEqual(response_headers, expected['headers'])
                self.assertEqual(len(actual['hops']), 3)
                self.assertEqual(actual['hops'][2]['bound'], expected['final_bound'])
                bounced = AIExecutionTraceContext.from_payload(case['input']['trace']).headers()
                self.assertEqual(bounced, expected['headers'])
            else:
                self.assertEqual(status, 400, case['id'])
                self.assertEqual(payload['error'], case['expected']['error'])

    def test_replay_g3_catalog_read_is_memory_only_zero_disk(self):
        disk = Path(self._disk.name)
        self.assertEqual(list(disk.iterdir()), [])
        for case in self.groups['G3_SEMANTIC_OBJECT_CATALOG']['cases']:
            if case['expect'] == 'accept':
                headers = official_headers_from_payload(case['input'])
                status, _headers, payload = self._request(
                    'POST', '/sandbox/v21/catalog/read', case['input'], headers,
                )
                self.assertEqual(status, 200, case['id'])
                self.assertEqual(payload['result'], case['expected'])
                self.assertEqual(payload['result']['disk_writes'], 0)
                self.assertIs(payload['result']['writable'], False)
                dumped = json.dumps(payload)
                self.assertNotIn('postgresql://example.invalid/db', dumped)
                self.assertNotIn('REDACTED-NOT-A-REAL-SECRET', dumped)
            else:
                status, _headers, payload = self._request(
                    'POST', '/sandbox/v21/catalog/write', case['input'],
                )
                self.assertEqual(status, 400, case['id'])
                self.assertEqual(payload['error'], case['expected']['error'])
                self.assertEqual(payload['disk_writes'], 0)
            self.assertEqual(self.harness.catalog.disk_writes, 0)
            self.assertEqual(list(disk.iterdir()), [])

    def test_replay_g4_revocation_hard_receipt_hashes_over_http(self):
        observed = {}
        for case in self.groups['G4_COGNIWEAVE_REVOCATION']['cases']:
            headers = official_headers_from_payload(case['input'])
            status, _headers, payload = self._request(
                'POST', '/sandbox/v21/revocation', case['input'], headers,
            )
            self.assertEqual(status, 200, case['id'])
            actual = payload['result']
            self.assertEqual(actual['receipt_hash'], case['expected']['receipt_hash'], case['id'])
            self.assertEqual(actual['parent_canonical_json'], case['expected']['parent_canonical_json'])
            self.assertEqual(actual['purged'], case['expected']['purged'])
            observed[case['id']] = actual['receipt_hash']
            for index, channel in enumerate(actual['channels']):
                expected_channel = case['expected']['channels'][index]
                self.assertEqual(channel.get('receipt_hash'), expected_channel.get('receipt_hash'))
        self.assertEqual(observed['G4-POS-FOUR-CHANNEL-SUCCESS'], HARD_RECEIPT_HASH_G4_POS_FOUR_CHANNEL_SUCCESS)
        self.assertEqual(observed['G4-POS-CHANNEL-TIMEOUT-NOT-PURGED'], HARD_RECEIPT_HASH_G4_POS_CHANNEL_TIMEOUT_NOT_PURGED)

    def test_replay_g5_data_bridge_mode_abc_fail_closed(self):
        for case in self.groups['G5_CONTROLLED_DATA_BRIDGE']['cases']:
            headers = official_headers_from_payload(case['input']['declaration'])
            status, _headers, payload = self._request(
                'POST', '/sandbox/v21/data-bridge', case['input'], headers,
            )
            if case['expect'] == 'accept':
                self.assertEqual(status, 200, case['id'])
                self.assertTrue(payload['ok'], case['id'])
                self.assertEqual(payload['result']['mode'], case['expected']['mode'])
                self.assertEqual(payload['result']['query_kind'], case['expected']['query_kind'])
            else:
                self.assertEqual(status, 400, case['id'])
                self.assertFalse(payload['ok'])
                self.assertEqual(payload['error'], case['expected']['error'])

    def test_header_and_body_conflict_fails_closed(self):
        case = self.groups['G1_MODELS_EMBED']['cases'][0]
        headers = official_headers_from_payload(case['input'])
        headers['X-V21-Tenant-Id'] = 'other_org'
        status, _headers, payload = self._request('POST', '/sandbox/v21/embed', case['input'], headers)
        self.assertEqual(status, 400)
        self.assertEqual(payload['error'], 'VALIDATION_ERROR')

    def test_server_closes_cleanly_after_stop(self):
        host, port = self.server.host, self.server.port
        self.server.stop()
        self.server = None
        conn = http.client.HTTPConnection(host, port, timeout=1)
        try:
            with self.assertRaises((ConnectionRefusedError, OSError)):
                conn.request('POST', '/sandbox/v21/embed', body=b'{}', headers={'Content-Type': 'application/json'})
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
