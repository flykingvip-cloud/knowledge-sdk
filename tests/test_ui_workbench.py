from __future__ import annotations
import base64
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from urllib.parse import urlencode

from knowledge_sdk import Actor, LocalKnowledgeClient, DocumentACL
from knowledge_sdk.contracts.models import ConsumerBinding, KnowledgeScope, GeneratedAnswer, encode, decode
from knowledge_sdk.client.http_client import OPERATIONS

AVAILABLE = all(importlib.util.find_spec(m) is not None for m in ("fastapi", "httpx"))
ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/knowledge_sdk/ui/static"
SECRET = "workbench-test-only-secret-at-least-32-characters"
ADMIN = Actor("admin", "demo-org", org_roles=("admin", "analyst"), department_ids=("engineering",), managed_department_ids=("engineering",), clearance_level="restricted")
ENGINEER = Actor("engineer", "demo-org", org_roles=("analyst",), department_ids=("engineering/platform",), ancestor_department_ids=("engineering",), clearance_level="internal")
LEAD = Actor("lead", "demo-org", org_roles=("analyst",), department_ids=("engineering",), managed_department_ids=("engineering",), clearance_level="confidential")
MARKETING = Actor("marketer", "demo-org", org_roles=("analyst",), department_ids=("marketing",), clearance_level="internal")
VISITOR = Actor("visitor", "demo-org", org_roles=("viewer",), clearance_level="public")


class StaticWorkbenchTests(unittest.TestCase):
    def test_no_cdn_or_build_chain(self):
        for file in STATIC.iterdir():
            text = file.read_text()
            self.assertNotRegex(text, r'https?://|@import|https?:\\/\\/')
        self.assertNotIn('node', (ROOT / 'pyproject.toml').read_text().lower())
        self.assertIn('dependencies = []', (ROOT / 'pyproject.toml').read_text())

    def test_ui_safe_dom_and_no_automatic_model_requests(self):
        script = (STATIC / 'workbench.js').read_text()
        self.assertNotRegex(script, r'innerHTML|outerHTML|eval\(|localStorage\.|sessionStorage\.')
        startup = script[script.index('async function start()'):]
        self.assertNotIn("api('ask'", startup)
        self.assertNotIn("api('search'", startup)
        self.assertIn("event.submitter?.value || 'search'", script)
        self.assertIn("if (action === 'ask')", script)
        self.assertIn("if (start !== epoch)", script)

    def test_ui_operation_names_exist(self):
        script = (STATIC / 'workbench.js').read_text()
        names = re.findall(r"api\('([^']+)'", script)
        self.assertGreaterEqual(len(set(names)), 16)
        self.assertFalse(set(names) - set(OPERATIONS))

    def test_four_views_accessibility_and_identity_fields(self):
        html = (STATIC / 'index.html').read_text()
        for view in ('spaces', 'documents', 'search', 'receipts'):
            self.assertIn('id="view-' + view + '"', html)
        for field in ('org_id', 'user_id', 'department_ids', 'ancestor_department_ids', 'org_roles', 'clearance_level'):
            self.assertIn('name="' + field + '"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('@media(max-width:760px)', (STATIC / 'workbench.css').read_text())
        self.assertIn('lang="zh-CN"', html)

    def test_cli_rejects_network_demo_and_real_database(self):
        for args in [('--host', '0.0.0.0'), ('--db', 'real.sqlite3'), ('--no-ui',), ('--dev-insecure',)]:
            result = subprocess.run([sys.executable, '-m', 'knowledge_sdk.server', '--demo-seed', *args], capture_output=True, text=True)
            # With -S the optional HTTP import can be absent; that case is covered by stdlib tests.
            if AVAILABLE: self.assertIn('error:', result.stderr)
            self.assertNotEqual(result.returncode, 0)


class WorkbenchCoreTests(unittest.TestCase):
    def setUp(self):
        self.client = LocalKnowledgeClient()
        self.kb = self.client.create_kb(ADMIN, "Public", space_type="enterprise_public")

    def tearDown(self): self.client.store.close()

    def test_atomic_acl_rolls_back_entire_upload_on_storage_error(self):
        original = self.client.store.set_acl
        def fail(*args): raise RuntimeError("Simulated ACL storage failure")
        self.client.store.set_acl = fail
        try:
            with self.assertRaises(RuntimeError):
                self.client.ingest(ADMIN, self.kb.kb_id, "must never appear", acl=DocumentACL(access_level="personal_only"))
        finally: self.client.store.set_acl = original
        self.assertEqual(self.client.list_documents(ADMIN), [])
        self.assertEqual(self.client.search(ADMIN, "appear").hits, [])

    def test_unchanged_upload_can_restrict_acl_without_new_version(self):
        first = self.client.ingest(ADMIN, self.kb.kb_id, "aurora", acl=DocumentACL(access_level="org_public"))
        second = self.client.ingest(ADMIN, self.kb.kb_id, "aurora", doc_id=first.doc_id, acl=DocumentACL(access_level="personal_only"))
        self.assertEqual(first.version, second.version)
        self.assertFalse(self.client.search(VISITOR, "aurora").hits)

    def test_inspection_reauthorizes_and_validates_selected_version(self):
        from knowledge_sdk.exceptions import PermissionDeniedError, ValidationError
        v = self.client.ingest(ADMIN, self.kb.kb_id, "aurora", acl=DocumentACL(access_level="personal_only"))
        with self.assertRaises(PermissionDeniedError): self.client.inspect_document(VISITOR, v.doc_id)
        for value in (True, 0, -1, "1"):
            with self.assertRaises(ValidationError): self.client.inspect_document(ADMIN, v.doc_id, value)
        detail = self.client.inspect_document(ADMIN, v.doc_id)
        self.assertTrue(detail["chunks"]); self.assertTrue(detail["can_manage"])

    def test_scope_search_and_bindings_are_available_without_http(self):
        v = self.client.ingest(ADMIN, self.kb.kb_id, "aurora", acl=DocumentACL(access_level="org_public"))
        scope = KnowledgeScope("documents", doc_ids=(v.doc_id,))
        self.assertTrue(self.client.search(VISITOR, "aurora", scope=scope).hits)
        binding = ConsumerBinding("agent", "research", scope)
        self.client.bind_consumer(VISITOR, binding)
        self.assertEqual(self.client.list_consumer_bindings(VISITOR), [binding])
        self.assertEqual(self.client.list_consumer_bindings(ADMIN), [])
        self.client.set_document_acl(ADMIN, v.doc_id, DocumentACL(access_level="personal_only"))
        self.assertEqual(self.client.list_consumer_bindings(VISITOR), [])

    def test_ingest_acl_requires_management_not_only_upload(self):
        from knowledge_sdk.exceptions import PermissionDeniedError
        legacy = self.client.create_kb(ADMIN, "Legacy", "team")
        self.client.grant_kb_member(ADMIN, legacy.kb_id, VISITOR.user_id, "editor")
        with self.assertRaises(PermissionDeniedError):
            self.client.ingest(VISITOR, legacy.kb_id, "aurora", acl=DocumentACL(access_level="org_public"))
        self.assertEqual(self.client.list_documents(ADMIN, legacy.kb_id), [])


@unittest.skipUnless(AVAILABLE, 'Optional HTTP extra not installed')
class WorkbenchHTTPTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        self.local = LocalKnowledgeClient()
        self.calls = 0
        outer = self
        class Generator:
            def generate(self, question, hits, scope, actor):
                outer.calls += 1
                return GeneratedAnswer('Grounded: ' + hits[0].excerpt, model_called=True)
        self.app = create_app(self.local, auth_secret=SECRET, enable_demo_switcher=True, answer_generator=Generator())
        self.http = TestClient(self.app, base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
        self.guard = {'Origin': 'http://127.0.0.1', 'X-KB-Demo': '1'}

    def tearDown(self):
        self.http.close(); self.local.store.close()

    def sign(self, actor, method, target, body='', **kwargs):
        return self.http.post('/ui/demo/sign', json={'actor': actor.__dict__, 'method': method, 'target': target, 'body': body}, headers=kwargs.get('headers', self.guard))

    def call(self, operation, actor=ADMIN, **params):
        method, path = OPERATIONS[operation]
        body = '' if method == 'GET' else json.dumps({'params': encode(params)}, ensure_ascii=False, separators=(',', ':'))
        if method == 'GET': path += '?' + urlencode({'params': json.dumps(encode(params), separators=(',', ':'))})
        signed = self.sign(actor, method, path, body)
        self.assertEqual(signed.status_code, 200, signed.text)
        return self.http.request(method, path, content=body if method != 'GET' else None, headers={**signed.json()['headers'], 'Content-Type': 'application/json'})

    def value(self, operation, actor=ADMIN, **params):
        response = self.call(operation, actor, **params)
        self.assertEqual(response.status_code, 200, response.text)
        return decode(response.json())

    def kb(self): return self.value('create_kb', name='Public', space_type='enterprise_public')

    def ingest(self, kb, text='aurora engineering rollout', acl=None, **params):
        return self.value('ingest', kb_id=kb.kb_id, content=text, filename='test.md', acl=acl or DocumentACL(access_level='org_public'), **params)

    def test_ui_and_all_assets(self):
        for path in ('/ui', '/ui/'):
            response = self.http.get(path); self.assertEqual(response.status_code, 200)
            self.assertIn('Knowledge SDK', response.text)
            self.assertIn("script-src 'self'", response.headers['content-security-policy'])
        html = self.http.get('/ui').text
        urls = re.findall(r'(?:src|href)="(/ui/assets/[^"]+)"', html)
        self.assertEqual(len(urls), 2)
        for url in urls:
            response = self.http.get(url); self.assertEqual(response.status_code, 200); self.assertTrue(response.content)
        self.assertIn('text/css', self.http.get('/ui/assets/workbench.css').headers['content-type'])
        self.assertIn('javascript', self.http.get('/ui/assets/workbench.js').headers['content-type'])
        self.assertEqual(self.http.get('/ui/assets/missing.js').status_code, 404)
        self.assertEqual(self.http.get('/ui/assets/%2e%2e/routes.py').status_code, 404)
        self.assertEqual(self.calls, 0)

    def test_ui_can_be_disabled(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        with TestClient(create_app(self.local, auth_secret=SECRET, enable_ui=False)) as http:
            for path in ('/ui', '/ui/', '/ui/config', '/ui/assets/workbench.js', '/ui/demo/sign'):
                self.assertEqual(http.get(path).status_code, 404)

    def test_production_demo_route_absent_and_api_remains_signed(self):
        from fastapi.testclient import TestClient
        from knowledge_sdk.server.app import create_app
        with TestClient(create_app(self.local, auth_secret=SECRET)) as http:
            self.assertFalse(http.get('/ui/config').json()['demo_enabled'])
            self.assertEqual(http.post('/ui/demo/sign', json={}).status_code, 404)
            self.assertEqual(http.get('/v1/kbs').status_code, 401)
            actor = base64.urlsafe_b64encode(json.dumps(ADMIN.__dict__).encode()).decode()
            self.assertEqual(http.get('/v1/kbs', headers={'X-KB-Actor': actor}).status_code, 401)
        self.assertEqual(self.http.get('/v1/kbs').status_code, 401)

    def test_demo_rejects_insecure_service(self):
        from knowledge_sdk.server.app import create_app
        from knowledge_sdk.exceptions import ValidationError
        with self.assertRaises(ValidationError): create_app(self.local, dev_insecure=True, enable_demo_switcher=True)

    def test_demo_requires_same_origin_and_custom_header(self):
        for headers in ({}, {'Origin': 'http://evil.test', 'X-KB-Demo': '1'}, {'Origin': 'http://127.0.0.1'}, {**self.guard, 'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.sign(ADMIN, 'GET', '/v1/kbs', headers=headers).status_code, 403)

    def test_demo_rejects_remote_client_and_rebinding_host(self):
        from fastapi.testclient import TestClient
        with TestClient(self.app, base_url='http://127.0.0.1', client=('192.0.2.10', 3456)) as http:
            self.assertEqual(http.post('/ui/demo/sign', json={}, headers=self.guard).status_code, 403)
        with TestClient(self.app, base_url='http://evil.test', client=('127.0.0.1', 3456)) as http:
            self.assertEqual(http.post('/ui/demo/sign', json={}, headers={'Origin': 'http://evil.test', 'X-KB-Demo': '1'}).status_code, 403)

    def test_demo_signer_rejects_arbitrary_targets_and_bad_actors(self):
        for target in ('https://evil.test/v1/kbs', '//evil.test/v1/kbs', '/ui/config', '/v1/kbs#fragment', '/v1/not-an-operation'):
            self.assertEqual(self.sign(ADMIN, 'GET', target).status_code, 400)
        self.assertEqual(self.sign(ADMIN, 'DELETE', '/v1/kbs').status_code, 400)
        self.assertEqual(self.sign(ADMIN, 'GET', '/v1/kbs', '{}').status_code, 400)
        self.assertEqual(self.http.post('/ui/demo/sign', json=[], headers=self.guard).status_code, 400)
        self.assertEqual(self.http.post('/ui/demo/sign', json={'actor': {'user_id': ''}}, headers=self.guard).status_code, 400)

    def test_demo_signature_replay_and_body_tamper_rejected(self):
        body = '{"params":{"query":"aurora"}}'
        headers = self.sign(ADMIN, 'POST', '/v1/search', body).json()['headers']
        self.assertEqual(self.http.post('/v1/search', content=body, headers=headers).status_code, 200)
        self.assertEqual(self.http.post('/v1/search', content=body, headers=headers).status_code, 401)
        headers = self.sign(ADMIN, 'POST', '/v1/search', body).json()['headers']
        self.assertEqual(self.http.post('/v1/search', content=body + ' ', headers=headers).status_code, 401)

    def test_three_space_types_and_permissions(self):
        public = self.kb()
        dep = self.value('create_kb', LEAD, name='Engineering', space_type='department', owner_department_id='engineering')
        personal = self.value('create_kb', ENGINEER, name='Notes', space_type='personal')
        self.assertFalse(self.value('can_manage_kb', ENGINEER, kb_id=public.kb_id))
        self.assertTrue(self.value('can_upload_to_kb', LEAD, kb_id=dep.kb_id))
        self.assertFalse(self.value('can_upload_to_kb', ENGINEER, kb_id=dep.kb_id))
        self.assertTrue(self.value('can_manage_kb', ENGINEER, kb_id=personal.kb_id))
        self.assertEqual(self.call('create_kb', MARKETING, name='No', space_type='enterprise_public').status_code, 403)
        self.assertNotIn(personal.kb_id, [k.kb_id for k in self.value('list_kbs', MARKETING)])

    def test_all_four_acl_levels_with_identity_isolation(self):
        kb = self.kb()
        fixtures = [
            (DocumentACL(access_level='org_public'), {a.user_id for a in (ADMIN, LEAD, ENGINEER, MARKETING, VISITOR)}),
            (DocumentACL(access_level='department', allowed_department_ids=['engineering'], include_sub_departments=True), {'admin', 'lead', 'engineer'}),
            (DocumentACL(access_level='role_clearance', allowed_org_roles=['analyst'], required_clearance='confidential'), {'admin', 'lead'}),
            (DocumentACL(access_level='personal_only'), {'admin'}),
        ]
        for index, (acl, allowed) in enumerate(fixtures):
            version = self.ingest(kb, text=f'policytoken{index}', acl=acl)
            for actor in (ADMIN, LEAD, ENGINEER, MARKETING, VISITOR):
                hits = self.value('search', actor, query=f'policytoken{index}').hits
                self.assertEqual(bool(hits), actor.user_id in allowed, (acl.access_level, actor.user_id))
                self.assertEqual(self.call('inspect_document', actor, doc_id=version.doc_id).status_code, 200 if actor.user_id in allowed else 403)

    def test_department_excludes_subdepartments_and_personal_named_grant(self):
        kb = self.kb()
        v = self.ingest(kb, acl=DocumentACL(access_level='department', allowed_department_ids=['engineering']))
        self.assertFalse(self.value('search', ENGINEER, query='aurora').hits)
        self.value('set_document_acl', doc_id=v.doc_id, acl=DocumentACL(access_level='personal_only', allowed_user_ids=[ENGINEER.user_id]))
        self.assertTrue(self.value('search', ENGINEER, query='aurora').hits)
        self.assertFalse(self.value('search', MARKETING, query='aurora').hits)

    def test_full_text_chunks_version_list_update_and_archive(self):
        kb = self.kb(); first = self.ingest(kb)
        second = self.ingest(kb, text='aurora rollout new revision', doc_id=first.doc_id)
        self.assertEqual(second.version, 2)
        detail = self.value('inspect_document', doc_id=first.doc_id, version=1)
        self.assertEqual(len(detail['versions']), 2)
        self.assertEqual(detail['selected'].text, first.text)
        self.assertTrue(detail['chunks']); self.assertEqual(detail['acl'].access_level, 'org_public')
        self.value('archive', doc_id=first.doc_id)
        self.assertFalse(self.value('list_documents', kb_id=kb.kb_id))
        self.assertFalse(self.value('search', query='aurora').hits)
        self.assertEqual(self.call('inspect_document', doc_id=first.doc_id, version=1).status_code, 403)

    def test_binary_upload_and_atomic_acl(self):
        kb = self.kb()
        result = self.value('ingest', kb_id=kb.kb_id, content_b64=base64.b64encode('secret 私人'.encode()).decode(), filename='secret.txt', acl=DocumentACL(access_level='personal_only'))
        self.assertFalse(self.value('search', VISITOR, query='secret').hits)
        self.assertEqual(self.value('inspect_document', doc_id=result.doc_id)['acl'].access_level, 'personal_only')
        before = len(self.value('list_documents'))
        self.assertEqual(self.call('ingest', kb_id=kb.kb_id, content='bad', acl={'access_level': 'invalid'}).status_code, 400)
        self.assertEqual(len(self.value('list_documents')), before)

    def test_scoped_search_and_ask(self):
        a = self.kb(); b = self.kb(); va = self.ingest(a); vb = self.ingest(b)
        for scope in (KnowledgeScope('spaces', kb_ids=(a.kb_id,)), KnowledgeScope('documents', doc_ids=(va.doc_id,))):
            hits = self.value('search', query='aurora', scope=scope).hits
            self.assertEqual({h.doc_id for h in hits}, {va.doc_id})
            answer = self.value('ask', question='aurora', scope=scope)
            self.assertEqual(answer.status, 'answered'); self.assertTrue(answer.model_called)
            self.assertEqual({c.doc_id for c in answer.citations}, {va.doc_id})
            self.assertTrue(answer.citations[0].excerpt_hash)
            self.assertIn('@1', answer.citations[0].source_uri)
        self.assertEqual(self.calls, 2)

    def test_ask_denied_and_no_match_never_call_generator(self):
        kb = self.kb(); self.ingest(kb, acl=DocumentACL(access_level='personal_only'))
        for actor, query in ((VISITOR, 'aurora'), (ADMIN, 'unmatchedzebratoken')):
            answer = self.value('ask', actor, question=query)
            self.assertEqual(answer.status, 'refused'); self.assertFalse(answer.model_called)
            self.assertFalse(answer.citations)
        self.assertEqual(self.calls, 0)

    def test_cross_org_isolation_for_search_and_preview(self):
        kb = self.kb(); version = self.ingest(kb)
        outsider = Actor('admin', 'another-org', org_roles=('admin',))
        self.assertEqual(self.value('list_kbs', outsider), [])
        self.assertFalse(self.value('search', outsider, query='aurora').hits)
        self.assertEqual(self.call('inspect_document', outsider, doc_id=version.doc_id).status_code, 403)
        self.assertFalse(self.value('ask', outsider, question='aurora').model_called)

    def test_binding_reference_receipt_and_tamper_verification(self):
        kb = self.kb(); version = self.ingest(kb)
        binding = ConsumerBinding('cycle', 'demo-cycle', KnowledgeScope('spaces', kb_ids=(kb.kb_id,)), 'background')
        self.value('bind_consumer', binding=binding)
        self.assertEqual(self.value('list_consumer_bindings'), [binding])
        self.assertEqual(self.value('list_consumer_bindings', VISITOR), [])
        ref = self.value('create_ref', doc_id=version.doc_id, version=1, excerpt='aurora')
        attached = self.value('attach', ref=ref, binding=binding)
        self.assertEqual(attached.receipt.consumer_id, 'demo-cycle')
        verified = self.value('verify_ref', ref=ref)
        self.assertEqual(verified.status, attached.receipt.status)
        self.assertTrue(self.value('verify_receipt', ref=ref, receipt=attached.receipt, binding=binding))
        ref.excerpt = 'forged evidence'
        tampered = self.call('verify_ref', ref=ref)
        self.assertEqual(tampered.status_code, 400)
        self.assertEqual(tampered.json()['error'], 'TamperedExcerptError')

    def test_inspection_and_binding_recheck_after_revocation(self):
        kb = self.kb(); version = self.ingest(kb)
        binding = ConsumerBinding('agent', 'private', KnowledgeScope('documents', doc_ids=(version.doc_id,)))
        self.value('bind_consumer', VISITOR, binding=binding)
        self.value('set_document_acl', doc_id=version.doc_id, acl=DocumentACL(access_level='personal_only'))
        self.assertEqual(self.value('list_consumer_bindings', VISITOR), [])
        self.assertEqual(self.call('inspect_document', VISITOR, doc_id=version.doc_id).status_code, 403)

    def test_demo_seed_and_no_model_calls_on_navigation(self):
        from knowledge_sdk.ui.demo import seed_demo
        seed_demo(self.local); seed_demo(self.local)
        self.assertEqual(len(self.value('list_kbs')), 3)
        self.assertEqual(len(self.value('list_documents')), 6)
        self.value('list_consumer_bindings')
        self.http.get('/ui'); self.http.get('/ui/config')
        self.assertEqual(self.calls, 0)
