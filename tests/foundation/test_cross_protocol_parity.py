"""Real ephemeral /v1 and four MCP tools share the same authority as Python."""
import importlib.util
import json
import os
import secrets
import unittest
from dataclasses import replace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from knowledge_sdk import *
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.contracts.models import encode

HTTP=all(importlib.util.find_spec(p) for p in ('fastapi','uvicorn'))


class ParityCases:
    engine='sqlite'
    def setUp(self):
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox
            from knowledge_sdk.server.postgres import postgres_client
            pg=PgSandbox();self.addCleanup(pg.close);self.c=postgres_client(pg.dsn,pgvector_dims=32)
        else:self.c=LocalKnowledgeClient()
        self.addCleanup(self.c.store.close)
        self.a=Actor('author','t',org_roles=('admin',));self.u=Actor('reader','t',policy_generation='1')
        self.c.create_kb(self.a,'private','private',kb_id='k');self.c.grant_kb_member(self.a,'k','reader','editor')
        self.c.ingest(self.a,'k','alpha evidence parity',doc_id='d',visibility='team',rights=ResourceRights(allow_export=True))
        self.secret=secrets.token_hex(32)
        from knowledge_sdk.server.app import create_app
        from tests.foundation.helpers import live
        self.base=self.enterContext(live(create_app(self.c,auth_secret=self.secret,enable_ui=False,enable_mcp=True,default_mcp_purpose=Purpose.READ))) if hasattr(self,'enterContext') else self._enter(live(create_app(self.c,auth_secret=self.secret,enable_ui=False,enable_mcp=True,default_mcp_purpose=Purpose.READ)))
        self.h=HttpKnowledgeClient(self.base,self.secret)
    def _enter(self,ctx):
        value=ctx.__enter__();self.addCleanup(ctx.__exit__,None,None,None);return value
    def mcp(self,tool,params,actor=None,agent=None):
        from knowledge_sdk.server.auth import signed_headers
        actor=actor or self.u
        body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':params}},separators=(',',':')).encode()
        headers=signed_headers(actor,self.secret,'POST','/v1/mcp',body,agent=agent.to_dict() if agent else None,purpose='read');headers['Content-Type']='application/json'
        try:r=urlopen(Request(self.base+'/v1/mcp',body,headers),timeout=15)
        except HTTPError as exc:r=exc
        with r:
            data=json.load(r);status=r.status
        if status!=200:return {}
        return data.get('result',{}).get('structuredContent',{})
    def matrix(self,label,allowed,actor=None,agent=None,version=None):
        actor=actor or self.u;version=version or self.c.store.get_document('d').current_version
        uri='kb://org/t/doc/d@'+str(version);ctx=dict(agent=agent,purpose=Purpose.READ)
        for name,c in (('python',self.c),('http',self.h)):
            with self.subTest(case=label,transport=name):
                try:found=bool(c.search(actor,'alpha',scope=KnowledgeScope('documents',doc_ids=['d']),**ctx).hits)
                except (PermissionDeniedError,NotFoundError):found=False
                self.assertEqual(found,allowed)
                try:
                    c.get_document(actor,'d',version,**ctx);ref=c.reference(actor,'d',version,**ctx)
                    verified=c.verify_ref(actor,ref,**ctx).status in ('consumed','partial')
                    c.report_evidence_issue(actor,uri,'outdated','fixture issue',**ctx)
                except (PermissionDeniedError,NotFoundError):verified=False
                self.assertEqual(verified,allowed)
        args={'search_evidence':dict(query='alpha',doc_ids=['d']), 'verify_citation':dict(source_uri=uri),
              'get_evidence_pack':dict(source_uris=[uri]),'report_evidence_issue':dict(source_uri=uri,issue_type='outdated',description='fixture')}
        for tool,params in args.items():
            with self.subTest(case=label,tool=tool):
                data=self.mcp(tool,params,actor,agent)
                ok=bool(data.get('hits')) if tool=='search_evidence' else bool(data.get('items')) if tool=='get_evidence_pack' else data.get('valid') is True if tool=='verify_citation' else data.get('status')=='queued_for_review'
                self.assertEqual(ok,allowed,(label,tool,data))
    def test_eight_scenarios_real_transports(self):
        self.matrix('authorized',True)
        # 1: tenant/space and robot binding never grants human access.
        self.matrix('cross_tenant',False,Actor('reader','foreign'))
        self.matrix('agent_binding_nonmember',False,Actor('outsider','t'),AgentIdentity('bound','t',allowed_kb_ids=('k',)))
        # 2: User intersection Agent and Purpose.
        self.matrix('agent_scope_intersection',False,agent=AgentIdentity('bound','t',allowed_kb_ids=('other',)))
        self.matrix('purpose_intersection',False,agent=AgentIdentity('bound','t',allowed_purposes=(Purpose.EXPORT,)))
        # 3: explicit ACL and redaction failure, never raw fallback.
        self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']));self.matrix('deny',False)
        self.c.set_document_acl(self.a,'d',DocumentACL())
        class Broken:
            def redact(self,*a):raise RuntimeError('PRIVATE_CONTENT secret@example.com')
        self.c.redaction_registry.register('broken',Broken());self.c.set_document_rights(self.a,'d',ResourceRights(redaction_profile='broken'));self.matrix('redaction_failclosed',False)
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=True))
        # 4: stale policy generation.
        self.c.store.upsert_principal(IdentityPrincipal('t','reader',policy_generation=2));self.matrix('stale_generation',False)
        self.u=replace(self.u,policy_generation='2')
        # 5: real snapshot invalidation immediately on ACL change; all entrypoints deny.
        self.c.register_agent_profile(self.a,'bound',allowed_kb_ids=['k'])
        task=self.h.create_task_context(self.u,'bound',purpose=Purpose.READ)
        snap=self.h.create_context_snapshot(self.u,task.task_id,[{'doc_id':'d'}]);self.assertTrue(snap.items)
        self.h.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']));self.matrix('midtask_revoked',False)
        for c in (self.c,self.h):
            with self.assertRaises(PermissionDeniedError):c.read_task_snapshot(self.u,task.task_id,snap.snapshot_id)
        for tool,params in [('search_evidence',dict(query='alpha')),('verify_citation',dict(source_uri='kb://org/t/doc/d@1')),('get_evidence_pack',dict(source_uris=['kb://org/t/doc/d@1'])),('report_evidence_issue',dict(source_uri='kb://org/t/doc/d@1',issue_type='outdated',description='fixture'))]:
            data=self.mcp(tool,dict(params,task_id=task.task_id));self.assertNotIn('alpha evidence parity',json.dumps(data))
        self.c.set_document_acl(self.a,'d',DocumentACL())
        # 6: exact tamper status; local and HTTP receipts agree, MCP uses its documented vocabulary.
        ref=self.c.reference(self.u,'d');bad=replace(ref,excerpt_hash='0'*64)
        for c in (self.c,self.h):
            with self.assertRaises(TamperedExcerptError):c.verify_ref(self.u,bad)
        self.assertEqual(self.mcp('verify_citation',dict(source_uri=ref.source_uri,excerpt_hash='0'*64))['current_status'],'tampered')
        # 7: L1 append-only rollback retains present security metadata.
        self.h.ingest(self.a,'k','alpha revised',doc_id='d');acl=DocumentACL(deny_users=['blocked']);self.h.set_document_acl(self.a,'d',acl)
        v=self.h.rollback_document(self.a,'d',1);self.assertEqual(v.version,3);self.assertEqual(self.c.store.get_acl('d'),acl);self.matrix('l1_rollback',True)
        # 8: archive/restore visibility is live and ACL-bound.
        self.h.archive(self.a,'d');self.matrix('archived',False);self.h.restore(self.a,'d');self.matrix('restored',True)
        self.h.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']));self.matrix('restored_still_acl_bound',False)
    def test_l2_publish_approve_rollback_and_budget_intersection(self):
        c=self.c;a=self.a;r=Actor('reviewer','t',org_roles=('admin',));p=Actor('publisher','t',org_roles=('admin',))
        self.h.create_kb(a,'controlled','enterprise',kb_id='l2',space_type='enterprise_public',governance_tier='l2_controlled')
        # Reuse matrix target d in this fresh fixture by creating controlled document d2 and checking it directly.
        self.h.ingest(a,'l2','alpha controlled',doc_id='d2')
        for transport in (c,self.h):
            with self.assertRaises(PermissionDeniedError):transport.get_document(self.u,'d2',1)
        def publish(version):
            self.h.submit_for_review(a,'d2',version=version,expected_version=version)
            self.h.approve_release(r,'d2',version=version,expected_version=version)
            self.h.publish_release(p,'d2',version=version,expected_version=version)
        publish(1);self.assertTrue(self.mcp('verify_citation',dict(source_uri='kb://org/t/doc/d2@1'))['valid'])
        self.h.ingest(a,'l2','alpha controlled revision',doc_id='d2');publish(2)
        self.h.set_document_acl(a,'d2',DocumentACL(deny_users=['blocked']))
        draft=self.h.rollback_document(a,'d2',1);self.assertEqual(draft.version,3)
        self.assertEqual(self.c.store.get_document('d2').current_version,2)
        for transport in (c,self.h):
            with self.assertRaises(PermissionDeniedError):transport.get_document(self.u,'d2',3)
        publish(3)
        self.assertTrue(self.mcp('verify_citation',dict(source_uri='kb://org/t/doc/d2@3'))['valid'])
        self.assertEqual(list(self.c.store.get_acl('d2').deny_users),['blocked'])
        self.c.register_agent_profile(a,'small',allowed_kb_ids=['k'],default_budget=ContextBudget(max_documents=1,max_items=1,max_chars_per_item=5,max_total_chars=5))
        for transport in (c,self.h):
            task=transport.create_task_context(self.u,'small',purpose=Purpose.READ,budget=ContextBudget(max_total_chars=500))
            self.assertEqual(task.budget.max_total_chars,5)
            snap=transport.create_context_snapshot(self.u,task.task_id,[{'doc_id':'d'}]);self.assertLessEqual(sum(len(i.text) for i in snap.items),5)
            result=self.mcp('get_evidence_pack',dict(source_uris=['kb://org/t/doc/d@1'],task_id=task.task_id,max_chars=4000))
            self.assertLessEqual(sum(len(i.get('text','')) for i in result.get('items',[])),5)


@unittest.skipUnless(HTTP,'HTTP optional dependencies unavailable')
class SQLiteParity(ParityCases,unittest.TestCase):pass
@unittest.skipUnless(HTTP and os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'HTTP/Disposable PG unavailable')
class PostgresParity(ParityCases,unittest.TestCase):engine='postgres'
