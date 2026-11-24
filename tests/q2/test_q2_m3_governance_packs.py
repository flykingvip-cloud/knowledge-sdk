"""Independent M3 safety contracts; same mixin is exercised on real PG below."""
from __future__ import annotations
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, FrozenInstanceError
from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from knowledge_sdk import Actor, LocalKnowledgeClient, DocumentACL, ResourceRights
from knowledge_sdk.exceptions import PermissionDeniedError, ConflictError, ValidationError, NotFoundError
from knowledge_sdk.contracts.packs import EvidencePack, PackItem, digest, plain
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.contracts.anchors import ReanchorStatus
from knowledge_sdk.storage.sqlite_store import SQLiteStore
from knowledge_sdk.mcp.tools import EvidenceTools
from knowledge_sdk.mcp.gateway import GatewayContext
from knowledge_sdk.contracts.policy import Purpose, AgentIdentity
from knowledge_sdk.permissions.redaction import RegexRedactionHook

class M3Contracts:
    engine='sqlite'
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.sandbox=None
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox
            from knowledge_sdk.server.postgres import postgres_client
            self.sandbox=PgSandbox();self.addCleanup(self.sandbox.close)
            self.c=postgres_client(self.sandbox.dsn,pgvector_dims=32)
        else:self.c=LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'test.db'))
        self.s=self.c.store;self.addCleanup(self.s.close)
        self.a=Actor('author','m3',org_roles=('admin',));self.r=Actor('reviewer','m3',org_roles=('admin',));self.p=Actor('publisher','m3',org_roles=('admin',));self.u=Actor('reader','m3')
        self.c.create_kb(self.a,'controlled',visibility='enterprise',space_type='enterprise_public',kb_id='k',governance_tier='l2_controlled')
    def ingest(self,text='alpha liveone evidence',doc='d'):
        return self.c.ingest(self.a,'k',text,filename='fixture.md',doc_id=doc,rights=ResourceRights(allow_export=True))
    def publish(self,version=1,doc='d'):
        self.c.submit_for_review(self.a,doc,version=version,expected_version=version)
        self.c.approve_release(self.r,doc,version=version,expected_version=version)
        return self.c.publish_release(self.p,doc,version=version,expected_version=version)
    def pack(self,doc='d',**kwargs):return self.c.create_evidence_pack(self.a,'Decision',[{'doc_id':doc,'version':1}],**kwargs)
    def scope(self):return self.s.tenant_scope('m3') if self.engine=='postgres' else nullcontext()
    def sql(self,sql,args=()):
        with self.scope():return self.s._execute(sql.replace('?','%s') if self.engine=='postgres' else sql,args)
    def test_role_separation_admin_and_version_locks(self):
        self.ingest()
        with self.assertRaises(ConflictError):self.c.submit_for_review(self.a,'d',expected_version=42)
        for version in (1,):
            with self.assertRaises(ConflictError):self.c.publish_release(self.p,'d',version=version,expected_version=version)
        self.c.submit_for_review(self.a,'d',expected_version=1)
        with self.assertRaises(PermissionDeniedError):self.c.approve_release(self.a,'d',version=1,expected_version=1)
        with self.assertRaises(PermissionDeniedError):self.c.reject_release(self.a,'d',version=1,expected_version=1,reason='self')
        self.assertTrue(any(e.decision_effect.value=='deny' for e in self.s.list_audit_events('m3',action='approve_release')))
        with self.assertRaises(ConflictError):self.c.approve_release(self.r,'d',version=1,expected_version=99)
        self.c.approve_release(self.r,'d',version=1,expected_version=1)
        for actor in (self.a,self.r):
            with self.assertRaises(PermissionDeniedError):self.c.publish_release(actor,'d',version=1,expected_version=1)
        self.c.publish_release(self.p,'d',version=1,expected_version=1)
        with self.assertRaises(ConflictError):self.c.publish_release(self.p,'d',version=1,expected_version=1)
    def test_draft_live_isolation_every_content_surface(self):
        self.ingest();self.publish();pack=self.pack()
        self.ingest('alpha secrettwo draft')
        self.assertEqual(self.s.get_document('d').current_version,1)
        for phase in ('draft','review','approved'):
            if phase=='review':self.c.submit_for_review(self.a,'d',expected_version=2)
            if phase=='approved':self.c.approve_release(self.r,'d',version=2,expected_version=2)
            for actor in (self.a,self.r,self.u):
                self.assertIn('liveone',self.c.retrieve(actor,'d').text)
                self.assertFalse(self.c.search(actor,'secrettwo').hits)
                self.assertTrue(self.c.search(actor,'liveone').hits)
                for call in (self.c.retrieve,self.c.reference,self.c.get_document):
                    with self.assertRaises(PermissionDeniedError):call(actor,'d',2)
                with self.assertRaises(PermissionDeniedError):self.c.create_evidence_pack(actor,'bad',[{'doc_id':'d','version':2}])
        self.c.publish_release(self.p,'d',version=2,expected_version=2)
        self.assertEqual(self.s.get_document('d').current_version,2)
        self.assertIn('secrettwo',self.c.retrieve(self.u,'d').text)
        self.assertFalse(self.c.search(self.u,'liveone').hits)
        if self.engine=='postgres':self.assertTrue(self.c.search(self.u,'alpha',mode='vector').hits)
        self.assertEqual(self.c.drain_outbox(self.a).failed,0)
        stored=self.s.get_evidence_pack('m3',pack.pack_id)
        self.assertEqual(stored.status,'impacted');self.assertEqual(stored.pack_sha256,pack.pack_sha256)
        self.assertEqual(stored.items,pack.items)
        self.assertTrue(any(a.target_type=='evidence_pack' and a.impact_reason.value=='superseded' for a in self.c.list_impact_alerts(self.a)))
    def test_reject_resubmit_and_append_only_dissent(self):
        self.ingest();self.c.submit_for_review(self.a,'d',expected_version=1)
        self.c.reject_release(self.r,'d',version=1,expected_version=1,reason='needs caveat')
        self.assertEqual(self.s.get_version('d',1).lifecycle_state,'rejected')
        self.assertEqual(self.s.get_document('d').lifecycle_state,'rejected')
        self.c.submit_for_review(self.a,'d',expected_version=1)
        decision=self.c.record_dissent(self.r,'d',version=1,note='negative results remain',stance='negative')
        self.c.approve_release(self.r,'d',version=1,expected_version=1)
        manifest=self.c.publish_release(self.p,'d',version=1,expected_version=1)
        self.assertIn(decision.dissent_note,manifest.dissent_notes)
        for statement in ('DELETE FROM review_decisions WHERE decision_id=?','UPDATE review_decisions SET stage=\'approved\' WHERE decision_id=?'):
            with self.assertRaises((ConflictError,ValidationError)):
                with self.s.transaction():self.sql(statement,(decision.decision_id,))
        self.assertIn(decision.dissent_note,self.pack().dissent_notes)
        self.assertEqual(len([r for r in self.s.list_review_decisions('m3','d') if r.stage=='dissent_recorded']),1)
    def test_four_issue_actions_terminal_and_permissions(self):
        self.ingest();self.publish()
        for action in ('create_revision_draft','retrieval_tuning','keep_dissent','dismissed'):
            issue=self.c.report_evidence_issue(self.u,'kb://org/m3/doc/d@1','inaccuracy','please review')
            with self.assertRaises(PermissionDeniedError):self.c.resolve_evidence_issue(self.u,issue.issue_id,action,'reviewed')
            with self.assertRaises((NotFoundError,PermissionDeniedError)):self.c.resolve_evidence_issue(Actor('x','foreign'),issue.issue_id,action,'reviewed')
            with self.assertRaises(ConflictError):self.c.resolve_evidence_issue(self.r,issue.issue_id,action,'reviewed',expected_version=2)
            result=self.c.resolve_evidence_issue(self.r,issue.issue_id,action,'reviewed',expected_version=1)
            self.assertEqual(result.status,'dismissed' if action=='dismissed' else 'resolved')
            self.assertEqual(result.resolution.resolution_action,action)
            self.assertEqual(self.s.get_issue('m3',issue.issue_id),result)
            with self.assertRaises(ConflictError):self.c.resolve_evidence_issue(self.r,issue.issue_id,action,'again')
        self.assertEqual(self.s.get_document('d').current_version,1)
        self.assertEqual(self.s.get_version('d',2).lifecycle_state,'draft')
        self.assertEqual(len(self.sql("SELECT event_id FROM outbox_events WHERE org_id=? AND event_type='issue.resolved'",('m3',))),4)
        self.assertEqual(len(self.s.list_audit_events('m3',action='resolve_evidence_issue',actor_id=self.r.user_id)),4)
    def test_rollback_approval_publish_issue_and_pack(self):
        self.ingest();self.c.submit_for_review(self.a,'d',expected_version=1)
        before=self.s.list_review_decisions('m3','d')
        with patch.object(self.s,'put_review_decision',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.c.approve_release(self.r,'d',version=1,expected_version=1)
        self.assertEqual(self.s.get_version('d',1).lifecycle_state,'in_review');self.assertEqual(self.s.list_review_decisions('m3','d'),before)
        self.c.approve_release(self.r,'d',version=1,expected_version=1)
        with patch.object(self.s,'enqueue_outbox',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.c.publish_release(self.p,'d',version=1,expected_version=1)
        self.assertEqual(self.s.get_version('d',1).lifecycle_state,'approved');self.assertFalse(self.c.search(self.u,'alpha').hits)
        self.c.publish_release(self.p,'d',version=1,expected_version=1)
        issue=self.c.report_evidence_issue(self.u,'kb://org/m3/doc/d@1','inaccuracy','review')
        reviews=len(self.s.list_review_decisions('m3','d'))
        with patch.object(self.s,'enqueue_outbox',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.c.resolve_evidence_issue(self.r,issue.issue_id,'keep_dissent','retained')
        self.assertEqual(self.s.get_issue('m3',issue.issue_id).status,'open');self.assertEqual(len(self.s.list_review_decisions('m3','d')),reviews)
        with patch.object(self.s,'put_usage_event',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.pack(pack_id='rollback')
        with self.assertRaises(NotFoundError):self.s.get_evidence_pack('m3','rollback')
    def test_multistance_seal_immutability_crate_and_transport(self):
        self.ingest();self.publish()
        entries=[{'doc_id':'d','version':1,'stance':s,'condition_note':'conditions '+s} for s in ('supporting','refuting','negative','conflict','contextual')]
        pack=self.c.create_evidence_pack(self.a,'Decision',entries,effective_decision={'conclusion':['uncertain']},dissent_notes=('retain minority',))
        with self.assertRaises(FrozenInstanceError):pack.title='overwritten'
        with self.assertRaises(TypeError):pack.effective_decision['x']=1
        self.assertEqual(decode(encode(pack)),pack);self.assertEqual(EvidencePack.from_dict(pack.to_dict()),pack)
        self.assertTrue(self.c.verify_evidence_pack(self.u,pack.pack_id).digest_valid)
        one=self.c.export_evidence_pack(self.u,pack.pack_id,format='ro_crate');two=self.c.export_evidence_pack(self.u,pack.pack_id,format='ro_crate')
        self.assertEqual(one,two)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(one.content))) as archive:
            self.assertEqual(set(archive.namelist()),{'ro-crate-metadata.json','evidence-pack.json','REVIEW_SUMMARY.md'})
            metadata=json.loads(archive.read('ro-crate-metadata.json'));self.assertEqual(metadata['@context'],'https://w3id.org/ro/crate/1.2/context')
            nodes={x['@id']:x for x in metadata['@graph']}
            self.assertEqual(nodes['ro-crate-metadata.json']['conformsTo']['@id'],'https://w3id.org/ro/crate/1.2')
            self.assertEqual(nodes['ro-crate-metadata.json']['about'],{'@id':'./'})
            self.assertEqual(nodes['./']['datePublished'],pack.created_at)
            self.assertTrue({'name','description','license','datePublished','hasPart'}<=set(nodes['./']))
            self.assertEqual(len(nodes['./']['hasPart']),7)
            for n in range(1,6):
                self.assertTrue({'stance','conditionNote','sourceUri','sha256','dissentNotes'}<=set(nodes['#item-'+str(n)]))
            body=json.loads(archive.read('evidence-pack.json'));self.assertEqual(body,plain(pack))
            self.assertIn('## negative',archive.read('REVIEW_SUMMARY.md').decode())
        with self.assertRaises(ConflictError):self.pack(pack_id=pack.pack_id)
    def test_revoke_acl_redaction_and_no_partial_file_output(self):
        self.ingest();self.publish();self.ingest('beta second','other');self.publish(doc='other')
        pack=self.c.create_evidence_pack(self.a,'Decision',[{'doc_id':d,'version':1} for d in ('d','other')])
        output=Path(self.tmp.name)/'must-not-exist.zip'
        self.c.set_document_acl(self.a,'other',DocumentACL(deny_users=['reader']))
        for method in ('get_evidence_pack','verify_evidence_pack'):
            with self.assertRaises(PermissionDeniedError):getattr(self.c,method)(self.u,pack.pack_id)
        for format in ('json','ro_crate'):
            with self.assertRaises(PermissionDeniedError):self.c.export_evidence_pack(self.u,pack.pack_id,format=format,output_path=output)
            self.assertFalse(output.exists())
        self.assertFalse(self.c.list_evidence_packs(self.u))
        self.c.set_document_rights(self.a,'other',ResourceRights(allow_export=True,revoked=True))
        with self.assertRaises(PermissionDeniedError):self.c.export_evidence_pack(self.a,pack.pack_id)
        self.assertEqual(self.c.drain_outbox(self.a).failed,0)
        stored=self.s.get_evidence_pack('m3',pack.pack_id)
        self.assertEqual(stored.status,'impacted');self.assertEqual(stored.pack_sha256,pack.pack_sha256)
        self.assertTrue(any(a.target_type=='evidence_pack' for a in self.c.list_impact_alerts(self.a)))
    def test_missing_hook_redaction_change_and_anchor_health(self):
        self.ingest();self.publish();pack=self.pack()
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=True,redaction_profile='mask'))
        with self.assertRaises(PermissionDeniedError):self.pack()
        with self.assertRaises(PermissionDeniedError):self.c.get_evidence_pack(self.a,pack.pack_id)
        self.c.redaction_registry.register('mask',RegexRedactionHook([('alpha','[MASKED]')]))
        masked=self.pack();self.assertNotIn('alpha',masked.items[0].excerpt)
        with self.assertRaises(PermissionDeniedError):self.c.export_evidence_pack(self.a,pack.pack_id)
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=True))
        anchor=self.s.get_anchors('m3','d',1)[0]
        for state in (ReanchorStatus.DRIFT_PENDING,ReanchorStatus.ORPHANED):
            self.s.update_anchor(replace(anchor,reanchor_status=state))
            with self.assertRaises(PermissionDeniedError):self.c.create_evidence_pack(self.a,'unhealthy',[{'doc_id':'d','version':1,'anchor_id':anchor.anchor_id}])
    def test_digest_tamper_and_cross_tenant_rls(self):
        self.ingest();self.publish();pack=self.pack()
        self.assertFalse(self.c.list_evidence_packs(Actor('x','foreign')))
        with self.assertRaises(NotFoundError):self.c.get_evidence_pack(Actor('x','foreign'),pack.pack_id)
        with self.s.transaction():
            self.sql('UPDATE evidence_packs SET data=? WHERE org_id=? AND pack_id=?',(self.s._dump(replace(pack,title='tampered')),'m3',pack.pack_id))
        report=self.c.verify_evidence_pack(self.u,pack.pack_id);self.assertFalse(report.digest_valid)
        for method in ('get_evidence_pack','export_evidence_pack'):
            with self.assertRaises(ConflictError):getattr(self.c,method)(self.u,pack.pack_id)
        if self.engine=='postgres':
            self.assertEqual(self.s._execute('SELECT data FROM evidence_packs'),[])
            with self.s.tenant_scope('foreign'):
                self.assertEqual(self.s._execute('SELECT data FROM evidence_packs'),[])
                self.assertEqual(self.s._execute('SELECT data FROM review_decisions'),[])
            self.assertEqual(self.s._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0],(False,False))
    def test_mcp_persisted_id_ephemeral_and_denied(self):
        self.ingest();self.publish();pack=self.pack()
        tools=EvidenceTools(self.c);context=GatewayContext(self.u,None,Purpose.GROUND_INTERNAL_LLM)
        self.assertEqual(tools.call('get_evidence_pack',{'pack_id':pack.pack_id},context)['pack_sha256'],pack.pack_sha256)
        default_agent_context=GatewayContext(self.u,AgentIdentity('internal-agent','m3'),Purpose.GROUND_INTERNAL_LLM)
        self.assertEqual(tools.call('get_evidence_pack',{'pack_id':pack.pack_id},default_agent_context)['pack_sha256'],pack.pack_sha256)
        self.assertTrue(tools.call('get_evidence_pack',{'source_uris':['kb://org/m3/doc/d@1']},context)['items'])
        self.assertTrue(tools.call('get_evidence_pack',{'query':'alpha'},context)['items'])
        self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']))
        result=tools.call('get_evidence_pack',{'pack_id':pack.pack_id},context)
        self.assertEqual(result['items'],[]);self.assertNotIn('Decision',json.dumps(result))
    def test_independent_connection_approve_and_issue_races(self):
        self.ingest();self.c.submit_for_review(self.a,'d',expected_version=1)
        if self.engine=='postgres':
            from knowledge_sdk.server.postgres import postgres_client
            other=postgres_client(self.sandbox.dsn)
        else:other=LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'test.db'))
        self.addCleanup(other.store.close)
        def approve(client):
            try:client.approve_release(self.r,'d',version=1,expected_version=1);return 'ok'
            except ConflictError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(approve,(self.c,other)))
        self.assertCountEqual(results,['ok','conflict'])
        self.c.publish_release(self.p,'d',version=1,expected_version=1)
        issue=self.c.report_evidence_issue(self.u,'kb://org/m3/doc/d@1','inaccuracy','review')
        def resolve(client):
            try:client.resolve_evidence_issue(self.r,issue.issue_id,'keep_dissent','retain',expected_version=1);return 'ok'
            except ConflictError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(resolve,(self.c,other)))
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(len([r for r in self.s.list_review_decisions('m3','d') if r.stage=='dissent_recorded']),1)

    def test_reentrant_redaction_cannot_revoke_earlier_item_and_leak(self):
        self.ingest();self.publish();self.ingest('beta other','other');self.publish(doc='other')
        entries=[{'doc_id':d,'version':1} for d in ('d','other')]
        pack=self.c.create_evidence_pack(self.a,'Decision',entries)
        self.c.set_document_rights(self.a,'other',ResourceRights(allow_export=True,redaction_profile='reentry'))
        client=self.c;author=self.a
        class Revoker:
            def redact(self,text,profile,purpose,metadata):
                client.set_document_acl(author,'d',DocumentACL(deny_users=['reader']))
                return text,'noop'
        self.c.redaction_registry.register('reentry',Revoker())
        with self.assertRaises(PermissionDeniedError):self.c.get_evidence_pack(self.u,pack.pack_id)
        # The DENY audit survives the rejected transaction, hook's writes do not.
        self.assertTrue(any(e.decision_effect.value=='deny' for e in self.s.list_audit_events('m3',action='get_evidence_pack')))
    def test_archive_export_prohibition_and_metadata_redaction(self):
        self.ingest();self.publish();pack=self.pack(dissent_notes=('sensitive-minority',))
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=False))
        for purpose in (Purpose.READ,Purpose.EXPORT,Purpose.GROUND_INTERNAL_LLM):
            with self.assertRaises(PermissionDeniedError):self.c.export_evidence_pack(self.a,pack.pack_id,purpose=purpose)
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=True,redaction_profile='metadata'))
        self.c.redaction_registry.register('metadata',RegexRedactionHook([('sensitive-minority','[MASKED]')]))
        with self.assertRaises(PermissionDeniedError):self.c.get_evidence_pack(self.a,pack.pack_id)
        self.c.set_document_rights(self.a,'d',ResourceRights(allow_export=True))
        self.c.archive(self.a,'d')
        with self.assertRaises(PermissionDeniedError):self.c.export_evidence_pack(self.a,pack.pack_id)
    def test_l1_unchanged_revision_issue_is_metadata_only(self):
        self.c.create_kb(self.a,'agile','enterprise',kb_id='agile')
        self.c.ingest(self.a,'agile','agile current',doc_id='agile-doc')
        issue=self.c.report_evidence_issue(self.u,'kb://org/m3/doc/agile-doc@1','inaccuracy','followup')
        result=self.c.resolve_evidence_issue(self.a,issue.issue_id,'create_revision_draft','tracked followup')
        self.assertEqual(result.status,'resolved');self.assertIsNone(result.resolution.revision_version)
        self.assertEqual(self.s.latest_version('agile-doc'),1)
        self.assertIn('agile current',self.c.retrieve(self.u,'agile-doc').text)
    def test_rejected_and_successive_drafts_never_overwrite_live_index(self):
        self.ingest();self.publish()
        self.ingest('secretsecond')
        self.c.ingest(self.a,'k','secretsecond',filename='fixture.md',doc_id='d',lifecycle_state='draft')
        self.assertEqual(self.s.get_document('d').current_version,1)
        self.assertEqual(self.s.get_document('d').lifecycle_state,'published')
        self.ingest('secretthird')
        self.assertEqual(self.s.latest_version('d'),3)
        with self.assertRaises(ConflictError):self.c.submit_for_review(self.a,'d',version=2,expected_version=2)
        self.assertEqual(self.s.get_document('d').current_version,1)
        self.assertTrue(self.c.search(self.u,'liveone').hits)
        self.c.submit_for_review(self.a,'d',expected_version=3)
        self.c.reject_release(self.r,'d',version=3,expected_version=3,reason='insufficient')
        with self.assertRaises(ConflictError):self.c.publish_release(self.p,'d',version=3,expected_version=3)
        self.assertEqual(self.s.get_version('d',3).lifecycle_state,'rejected')
    def test_publish_race_has_one_winner_one_event(self):
        self.ingest();self.c.submit_for_review(self.a,'d',expected_version=1);self.c.approve_release(self.r,'d',version=1,expected_version=1)
        if self.engine=='postgres':
            from knowledge_sdk.server.postgres import postgres_client
            other=postgres_client(self.sandbox.dsn)
        else:other=LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'test.db'))
        self.addCleanup(other.store.close)
        def publish(client):
            try:client.publish_release(self.p,'d',version=1,expected_version=1);return 'ok'
            except ConflictError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(publish,(self.c,other)))
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(len(self.sql("SELECT event_id FROM outbox_events WHERE org_id=? AND event_type='doc.published'",('m3',))),1)
        self.assertEqual(len([r for r in self.s.list_review_decisions('m3','d') if r.stage=='published']),1)
    def test_cli_stdlib_adapter_keeps_identity_outside_params(self):
        self.ingest();self.publish();pack=self.pack()
        env=dict(os.environ,KNOWLEDGE_SDK_ACTOR_JSON=json.dumps(encode(self.a)))
        # Actor JSON is untagged trusted host configuration.
        env['KNOWLEDGE_SDK_ACTOR_JSON']=json.dumps(self.a.__dict__)
        if self.engine=='postgres':env['KNOWLEDGE_SDK_DSN']=self.sandbox.dsn
        flags=['-S'] if self.engine=='sqlite' else []
        result=subprocess.run([sys.executable,*flags,'-W','error::ResourceWarning','-m','knowledge_sdk.governance.cli','export_evidence_pack','--db',str(Path(self.tmp.name)/'test.db'),'--params',json.dumps({'pack_id':pack.pack_id})],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(decode(json.loads(result.stdout)).pack_id,pack.pack_id)
        self.assertNotIn('ResourceWarning',result.stderr)
        bad=subprocess.run([sys.executable,'-S','-m','knowledge_sdk.governance.cli','list_evidence_packs','--params','{"actor":{}}'],env=env,capture_output=True,text=True,timeout=15)
        self.assertEqual(bad.returncode,2)

    def test_ingest_publish_interleaving_cannot_restore_stale_live_pointer(self):
        self.ingest();self.publish();self.ingest('second approved')
        self.c.submit_for_review(self.a,'d',expected_version=2);self.c.approve_release(self.r,'d',version=2,expected_version=2)
        if self.engine=='postgres':
            from knowledge_sdk.server.postgres import postgres_client
            other=postgres_client(self.sandbox.dsn)
        else:other=LocalKnowledgeClient(SQLiteStore(Path(self.tmp.name)/'test.db'))
        self.addCleanup(other.store.close)
        split=self.c.chunker.split
        def interleaved(*args,**kwargs):
            other.publish_release(self.p,'d',version=2,expected_version=2)
            return split(*args,**kwargs)
        with patch.object(self.c.chunker,'split',side_effect=interleaved):
            with self.assertRaises(ConflictError):self.ingest('third racing draft')
        self.assertEqual(self.s.latest_version('d'),2)
        self.assertEqual(self.s.get_document('d').current_version,2)
        self.assertIn('second approved',self.c.retrieve(self.u,'d').text)

    def test_pre_m3_v3_draft_payload_is_migrated_without_admin_bypass(self):
        self.ingest()
        payload=encode(self.s.get_version('d',1))
        for field in ('lifecycle_state','author_id','submitter_id','reviewer_id','publisher_id','published_at','source_issue_id'):payload.pop(field)
        with self.s.transaction():self.sql('UPDATE document_versions SET data=? WHERE doc_id=? AND version=?',(json.dumps(payload),'d',1))
        self.assertEqual(self.s.get_version('d',1).lifecycle_state,'draft')
        self.assertEqual(self.s.get_version('d',1).author_id,self.a.user_id)
        self.c.submit_for_review(self.a,'d',expected_version=1)
        with self.assertRaises(PermissionDeniedError):self.c.approve_release(self.a,'d',version=1,expected_version=1)
        self.c.approve_release(self.r,'d',version=1,expected_version=1);self.c.publish_release(self.p,'d',version=1,expected_version=1)
        self.assertTrue(self.c.search(self.u,'alpha').hits)

class SQLiteM3(M3Contracts,unittest.TestCase):pass
