import os,unittest,json,tempfile,threading,copy
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.connectors import ConnectorSyncRunner,ControlledFilesystemConnector
from knowledge_sdk.contracts.connectors import ConnectorSyncBatch,ConnectorDocument,TombstoneRecord
from knowledge_sdk.connectors.base import BaseConnector


class CompatCases:
    engine='sqlite'
    def setUp(self):
        self.sandbox=None
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox,golden_client
            self.sandbox=PgSandbox();self.c=golden_client(self.sandbox.dsn)
        else:self.c=LocalKnowledgeClient()
        self.addCleanup(self.cleanup)
        self.a=Actor('owner','o',org_roles=('admin',));self.b=Actor('reader','o');self.foreign=Actor('owner','other',org_roles=('admin',))
        self.c.create_kb(self.a,'private',kb_id='k');self.c.grant_kb_member(self.a,'k','reader','editor')
        self.c.ingest(self.a,'k','first authorized SECRET',doc_id='d',visibility='team',metadata={'label':'current'})
    def cleanup(self):
        try:self.c.store.close()
        finally:
            if self.sandbox:self.sandbox.close()
    def denied(self,fn):
        with self.assertRaises(PermissionDeniedError):fn()
    def test_kb_read_and_uniform_denial(self):
        self.assertEqual(self.c.get_kb(self.b,'k').kb_id,'k')
        for user in (self.foreign,Actor('no-member','o')):
            messages=[]
            for kb in ('k','missing'):
                try:self.c.get_kb(user,kb)
                except PermissionDeniedError as e:messages.append(str(e))
            self.assertEqual(messages,['resource_unavailable']*2)
    def test_new_methods_reject_malformed_resource_ids(self):
        for value in (True,3,[],{},''):
            for method in (self.c.get_kb,self.c.list_kb_members,self.c.list_document_versions):
                with self.assertRaises(ValidationError):method(self.a,value)

    def test_update_field_allowlist_and_agent_intersection(self):
        self.assertEqual(self.c.update_kb(self.a,'k',name='changed').name,'changed')
        self.denied(lambda:self.c.update_kb(self.b,'k',name='bad'))
        self.denied(lambda:self.c.update_kb(self.a,'k',name='bad',agent=AgentIdentity('a','o',allowed_kb_ids=('other',))))
        self.assertEqual(self.c.get_kb(self.a,'k').name,'changed')
        for key in ('org_id','kb_id_transfer','owner_id'):
            with self.assertRaises(TypeError):self.c.update_kb(self.a,'k',**{key:'evil'})
    def test_manage_explicit_deny_wins_owner(self):
        from knowledge_sdk.contracts.policy import PolicyRule,DecisionEffect
        self.c.policy_engine=__import__('knowledge_sdk.permissions.engine',fromlist=['DefaultPolicyEngine']).DefaultPolicyEngine([PolicyRule('deny','o',effect=DecisionEffect.DENY,scope_kb_id='k',actions=(PolicyAction.MANAGE_SPACE,))])
        self.denied(lambda:self.c.update_kb(self.a,'k',name='bad'));self.denied(lambda:self.c.list_kb_members(self.a,'k'))
    def test_members_minimal_and_owner_protected(self):
        self.assertEqual(self.c.list_kb_members(self.a,'k'),[{'user_id':'owner','role':'admin'},{'user_id':'reader','role':'editor'}])
        self.denied(lambda:self.c.list_kb_members(self.b,'k'))
        with self.assertRaises(ConflictError):self.c.revoke_kb_member(self.a,'k','owner')
        self.assertEqual(self.c.store.member_role('k','owner'),'admin')
    def test_revoke_immediate_task_snapshot_search_and_audit(self):
        c=self.c;c.register_agent_profile(self.a,'agent',allowed_kb_ids=('k',));t=c.create_task_context(self.b,'agent',purpose=Purpose.READ)
        snap=c.create_context_snapshot(self.b,t.task_id,[{'doc_id':'d'}]);empty=c.create_task_context(self.b,'agent',purpose=Purpose.READ)
        before=c.store.count_outbox_events('o');c.revoke_kb_member(self.a,'k','reader')
        self.denied(lambda:c.get_document(self.b,'d'));self.assertFalse(c.search(self.b,'authorized').hits)
        self.denied(lambda:c.read_task_snapshot(self.b,t.task_id,snap.snapshot_id));self.denied(lambda:c.create_context_snapshot(self.b,empty.task_id,[{'doc_id':'d'}]))
        self.assertGreater(c.store.count_outbox_events('o'),before)
        rev=c.store.list_task_revocations('o',t.task_id);self.assertTrue(rev)
        with c.store.tenant_scope('o') if hasattr(c.store,'_pg') else __import__('contextlib').nullcontext():
            events=c.store._rt_execute('SELECT event_id FROM outbox_events WHERE org_id=?',('o',))
        self.assertIn((rev[0].trigger_event_id,),events);self.assertTrue(c.verify_audit_chain(self.a).valid)
    def test_revoke_atomic_on_outbox_error(self):
        with patch.object(self.c.store,'enqueue_outbox',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.c.revoke_kb_member(self.a,'k','reader')
        self.assertEqual(self.c.store.member_role('k','reader'),'editor')
    def test_versions_metadata_only_and_immutable(self):
        before=self.c.store.get_version('d',1);self.c.ingest(self.a,'k','second document',doc_id='d')
        versions=self.c.list_document_versions(self.b,'d');self.assertEqual([v.version for v in versions],[1,2]);self.assertTrue(all(v.text=='' and v.blob_key is None for v in versions));self.assertEqual(self.c.store.get_version('d',1),before)
    def test_diff_redacts_before_counts_and_chunks(self):
        from knowledge_sdk.permissions.redaction import RegexRedactionHook
        self.c.ingest(self.a,'k','second SECRET',doc_id='d');self.c.redaction_registry.register('hide',RegexRedactionHook([('SECRET','MASK')]))
        self.c.set_document_rights(self.a,'d',ResourceRights(redaction_profile='hide'))
        value=self.c.diff_document_versions(self.b,'d',1,2);self.assertNotIn('SECRET',json.dumps(value));self.assertIn('MASK',json.dumps(value))
        with self.assertRaises(ValidationError):self.c.diff_document_versions(self.b,'d',True,2)
        self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['reader']));self.denied(lambda:self.c.diff_document_versions(self.b,'d',1,2))
    def test_diff_failclosed_redaction_hook_exception(self):
        from knowledge_sdk.permissions.redaction import RedactionHook
        self.c.ingest(self.a,'k','second SECRET',doc_id='d');self.c.set_document_rights(self.a,'d',ResourceRights(redaction_profile='missing'))
        self.denied(lambda:self.c.diff_document_versions(self.b,'d',1,2))
    def test_rollback_append_even_same_text_preserves_current_controls(self):
        before=self.c.store.get_version('d',1);v=self.c.rollback_document(self.a,'d',1);self.assertEqual(v.version,2);self.assertEqual(v.text,before.text);self.assertEqual(self.c.store.get_version('d',1),before)
        self.assertEqual(self.c.store.get_document('d').metadata,{'label':'current'})
        events=self.c.store.list_audit_events('o',action='rollback_document',limit=100);self.assertEqual(events[-1].details['rollback_from_version'],1)
    def test_rollback_write_and_read_both_required(self):
        self.c.grant_kb_member(self.a,'k','reader','viewer');self.denied(lambda:self.c.rollback_document(self.b,'d',1))
        self.c.set_document_acl(self.a,'d',DocumentACL(deny_users=['owner']));self.denied(lambda:self.c.rollback_document(self.a,'d',1))
    def test_rollback_cannot_revive_archived_or_revoked(self):
        self.c.archive(self.a,'d');self.denied(lambda:self.c.rollback_document(self.a,'d',1));self.c.restore(self.a,'d');self.c.set_document_rights(self.a,'d',ResourceRights(revoked=True));self.denied(lambda:self.c.rollback_document(self.a,'d',1))
    def test_recycle_managed_only_default_contract(self):
        self.c.archive(self.a,'d');self.assertFalse(self.c.list_documents(self.a));self.assertEqual([d.doc_id for d in self.c.list_documents(self.a,archived_only=True)],['d']);self.assertEqual(self.c.list_documents(self.b,archived_only=True),[])
        self.c.restore(self.a,'d');self.assertEqual(len(self.c.list_documents(self.a)),1);self.assertFalse(self.c.list_documents(self.a,archived_only=True))
    def test_scim_stale_management_denied(self):
        from knowledge_sdk.contracts.identity import IdentityPrincipal
        self.c.store.upsert_principal(IdentityPrincipal('o','owner',policy_generation=2));self.denied(lambda:self.c.get_kb(self.a,'k'));self.denied(lambda:self.c.update_kb(self.a,'k',name='bad'))
    def test_controlled_rollback_is_new_draft_three_person_workflow(self):
        c=self.c;c.create_kb(self.a,'controlled','enterprise',kb_id='l2',governance_tier='l2_controlled')
        reviewer=Actor('reviewer','o');publisher=Actor('publisher','o')
        for actor in (reviewer,publisher):c.grant_kb_member(self.a,'l2',actor.user_id,'admin')
        c.ingest(self.a,'l2','controlled source',doc_id='controlled')
        c.submit_for_review(self.a,'controlled',version=1,expected_version=1);c.approve_release(reviewer,'controlled',version=1,expected_version=1);c.publish_release(publisher,'controlled',version=1,expected_version=1)
        original=c.store.get_version('controlled',1);v=c.rollback_document(self.a,'controlled',1)
        self.assertEqual((v.version,v.lifecycle_state,v.text),(2,'draft',''));self.assertEqual(c.store.get_document('controlled').current_version,1);self.assertEqual(c.store.get_version('controlled',1),original)
        with self.assertRaises(ConflictError):c.rollback_document(self.a,'controlled',1)
        with self.assertRaises(ConflictError):c.update_kb(self.a,'l2',governance_tier='l1_agile')
        c.submit_for_review(self.a,'controlled',version=2,expected_version=2)
        with self.assertRaises(PermissionDeniedError):c.approve_release(self.a,'controlled',version=2,expected_version=2)
        c.approve_release(reviewer,'controlled',version=2,expected_version=2);c.publish_release(publisher,'controlled',version=2,expected_version=2)
        self.assertEqual(c.store.get_document('controlled').current_version,2)

    def test_plan_is_readonly_and_matches_commit(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'a.txt';p.write_text('connector first')
            connector=ControlledFilesystemConnector('fs',root,org_id='o');runner=ConnectorSyncRunner(self.c)
            before=self.c.store.count_outbox_events('o');audit=len(self.c.store.list_audit_events('o',limit=1000));plan=runner.plan_sync(self.a,connector,org_id='o',kb_id='k')
            self.assertEqual(len(plan['to_upsert']),1);self.assertEqual(self.c.store.count_outbox_events('o'),before);self.assertEqual(len(self.c.store.list_audit_events('o',limit=1000)),audit);self.assertIsNone(self.c.store.get_connector_sync_state('o','fs'))
            report=runner.run_once(self.a,connector,org_id='o',kb_id='k');self.assertEqual(report.applied_upserts,1);self.assertEqual(runner.plan_sync(self.a,connector,org_id='o',kb_id='k')['to_upsert'],[])
            p.unlink();plan=runner.plan_sync(self.a,connector,org_id='o',kb_id='k');self.assertEqual(len(plan['to_tombstone']),1)
            self.assertEqual(runner.run_once(self.a,connector,org_id='o',kb_id='k').applied_tombstones,1)
    def test_plan_never_calls_custom_consuming_connector(self):
        class Consuming(BaseConnector):
            connector_id='unsafe';org_id='o'
            def sync_since(self,*a,**k):raise AssertionError('Would drain event queue')
        r=ConnectorSyncRunner(self.c)
        with self.assertRaises(ValidationError):r.plan_sync(self.a,Consuming(),org_id='o',kb_id='k')
        self.assertEqual(r.plan_sync(self.a,Consuming(),org_id='o',kb_id='k',batch=ConnectorSyncBatch())['to_upsert'],[])
    def test_plan_rejected_input_no_audit(self):
        class C:connector_id='custom';org_id='o'
        r=ConnectorSyncRunner(self.c);before=len(self.c.store.list_audit_events('o',limit=1000))
        with self.assertRaises(PermissionDeniedError):r.plan_sync(self.b,C(),org_id='o',kb_id='k',batch=ConnectorSyncBatch())
        self.assertEqual(len(self.c.store.list_audit_events('o',limit=1000)),before)
    def test_plan_digest_validation_shared(self):
        class C:connector_id='custom';org_id='o'
        bad=ConnectorSyncBatch(upserts=(ConnectorDocument('e','new','k','text',source_sha256='0'*64),))
        with self.assertRaises(ValidationError):ConnectorSyncRunner(self.c).plan_sync(self.a,C(),org_id='o',kb_id='k',batch=bad)

class SQLiteCompat(CompatCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PostgreSQL DSN unavailable')
class PostgresCompat(CompatCases,unittest.TestCase):
    engine='postgres'
    def test_concurrent_last_owner_immutable_across_connections(self):
        from tests.pg_helpers import golden_client
        other=golden_client(self.sandbox.dsn);errors=[]
        try:
            def attempt(client):
                try:client.revoke_kb_member(self.a,'k','owner')
                except ConflictError:errors.append('owner_protected')
            threads=[threading.Thread(target=attempt,args=(c,)) for c in (self.c,other)]
            for t in threads:t.start()
            for t in threads:t.join(timeout=10);self.assertFalse(t.is_alive())
            self.assertEqual(errors,['owner_protected']*2);self.assertEqual(self.c.store.member_role('k','owner'),'admin')
        finally:other.store.close()
