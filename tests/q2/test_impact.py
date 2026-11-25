from __future__ import annotations
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import hashlib
import json
import unittest
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode,decode
from knowledge_sdk.impact.radar import ImpactRadar, binding_target_id
from knowledge_sdk.events.outbox import OutboxDispatcher
from knowledge_sdk.mcp import EvidenceTools,GatewayContext


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.c=LocalKnowledgeClient();self.addCleanup(self.c.store.close)
        self.a=Actor('admin','org',org_roles=('admin',));self.u=Actor('reader','org')
        self.k=self.c.create_kb(self.a,'space','enterprise',kb_id='kb')
        self.c.ingest(self.a,'kb','Original evidence alpha.',doc_id='doc')
        self.binding=ConsumerBinding('task','consumer',KnowledgeScope('documents',doc_ids=('doc',)),stage='task-42')

    def use(self,anchor=False):
        selected=self.c.list_anchors(self.u,'doc')[0].anchor_id if anchor else None
        ref=self.c.reference(self.u,'doc',anchor_id=selected,excerpt='' if anchor else 'Original')
        receipt=self.c.attach(self.u,ref,self.binding).receipt
        return ref,receipt

    def alerts(self,reason=None):
        result=self.c.list_impact_alerts(self.u)
        return [a for a in result if reason is None or a.impact_reason==reason]

    def test_usage_is_real_immutable_and_roundtrippable(self):
        ref,receipt=self.use(True)
        events=self.c.store.list_usage_events_for_doc('org','doc')
        self.assertEqual(len(events),1);usage=events[0]
        expected=hashlib.sha256(json.dumps(encode(receipt),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual((usage.anchor_id,usage.consumer_id,usage.task_id,usage.receipt_hash),(ref.anchor_id,'consumer','task-42',expected))
        self.assertEqual(decode(encode(usage)),usage)
        actor,agent=self.c.store.usage_identity('org',usage.usage_id)
        self.c.store.put_usage_event(usage,actor=actor,agent=agent)
        with self.assertRaises(ConflictError):self.c.store.put_usage_event(replace(usage,version=2))
        self.assertNotIn('Original evidence',self.c.store._execute('SELECT data FROM usage_events')[0][0])

    def test_no_success_lineage_for_denials_tamper_or_failed_attach(self):
        ref=self.c.reference(self.u,'doc',excerpt='Original')
        bad=ConsumerBinding('task','x',KnowledgeScope('documents',doc_ids=('not-present',)))
        with self.assertRaises(NotFoundError):self.c.attach(self.u,ref,bad)
        self.c.set_document_acl(self.a,'doc',DocumentACL(deny_users=['reader']))
        self.assertEqual(self.c.consume(self.u,ref).status,'denied')
        self.assertEqual(self.c.store.list_usage_events_for_doc('org','doc'),[])

    def test_batch_persists_each_success(self):
        ref=self.c.reference(self.u,'doc',excerpt='Original')
        self.c.batch_consume(self.u,[ref,ref])
        self.assertEqual(len(self.c.store.list_usage_events_for_doc('org','doc')),2)

    def test_revision_alerts_usage_and_binding_old_snapshots_unchanged(self):
        ref,receipt=self.use();self.c.bind_consumer(self.u,self.binding)
        before={t:self.c.store._execute('SELECT * FROM '+t) for t in ('usage_events','consumer_bindings','document_versions')}
        self.c.ingest(self.a,'kb','Changed evidence beta.',doc_id='doc')
        self.c.drain_outbox(self.a)
        alerts=self.alerts(ImpactReason.SUPERSEDED)
        self.assertEqual({a.target_type for a in alerts},{'usage_event','consumer_binding'})
        self.assertTrue(all(a.source_version==1 for a in alerts))
        for table in ('usage_events','consumer_bindings'):self.assertEqual(self.c.store._execute('SELECT * FROM '+table),before[table])
        self.assertEqual(self.c.store.get_version('doc',1).text,'Original evidence alpha.')
        self.assertEqual((ref.version,receipt.source_uri),(1,ref.source_uri))
        self.assertNotIn('Changed evidence',json.dumps(encode(alerts)))

    def test_archive_and_revoke_ownership_allows_only_safe_metadata(self):
        self.use();self.c.archive(self.a,'doc');self.c.drain_outbox(self.a)
        self.assertEqual(len(self.alerts(ImpactReason.RESOURCE_ARCHIVED)),2)
        self.c.restore(self.a,'doc');self.c.set_document_rights(self.a,'doc',ResourceRights(revoked=True));self.c.drain_outbox(self.a)
        self.assertEqual(len(self.alerts(ImpactReason.ACCESS_REVOKED)),2)
        self.assertFalse(self.c.evaluate_policy(self.u,'doc').allowed)
        for alert in self.alerts():self.assertEqual(set(json.loads(alert.summary)),{'doc_id','version','target_type','target_id','impact_reason'})

    def test_acl_tightening_only_lost_subject_is_affected(self):
        self.use();allowed=Actor('allowed','org');ref=self.c.reference(allowed,'doc',excerpt='Original');self.c.consume(allowed,ref)
        self.c.set_document_acl(self.a,'doc',DocumentACL(deny_users=['reader']));self.c.drain_outbox(self.a)
        self.assertEqual(len(self.alerts(ImpactReason.ACCESS_REVOKED)),2)
        self.assertEqual(self.c.list_impact_alerts(allowed),[])
        self.assertEqual(len(self.c.store.list_impact_alerts('org')),2)

    def test_agent_and_purpose_original_rights_rechecked(self):
        agent=AgentIdentity('agent','org',allowed_purposes=tuple(Purpose))
        self.c.set_document_rights(self.a,'doc',ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True))
        ref=self.c.reference(self.u,'doc',agent=agent,purpose=Purpose.GROUND_EXTERNAL_LLM,excerpt='Original')
        self.c.consume(self.u,ref,agent=agent,purpose=Purpose.GROUND_EXTERNAL_LLM)
        self.c.set_document_rights(self.a,'doc',ResourceRights());self.c.drain_outbox(self.a)
        self.assertEqual(len(self.alerts(ImpactReason.ACCESS_REVOKED)),1)

    def test_identity_refresh_rejects_wrong_subject_and_updated_clearance(self):
        self.use();seen=[]
        def resolve(org,user,agent):seen.append((org,user,agent));return Actor('impostor',org,org_roles=('admin',))
        self.c.identity_resolver=resolve
        self.c.set_document_acl(self.a,'doc',DocumentACL());self.c.drain_outbox(self.a)
        self.assertTrue(seen);self.assertEqual(len(self.alerts(ImpactReason.ACCESS_REVOKED)),2)

    def test_drift_and_orphan_precisely_match_anchor_lineage(self):
        # Produce a real inherited drift by shifting the exact quote. Also record
        # an unanchored reference: it must never receive anchor-specific alerts.
        self.use(True);self.use(False)
        self.c.ingest(self.a,'kb','Original evidence alpha.\n\nOriginal evidence alpha.',doc_id='doc')
        anchors=self.c.store.get_anchors('org','doc',2)
        self.assertTrue(any(a.reanchor_status==ReanchorStatus.DRIFT_PENDING for a in anchors))
        self.c.drain_outbox(self.a)
        drift=self.alerts(ImpactReason.ANCHOR_DRIFTED)
        self.assertEqual({a.target_type for a in drift},{'usage_event','consumer_binding'})
        self.c.ingest(self.a,'kb','Nothing remains.',doc_id='doc');self.c.drain_outbox(self.a)
        self.assertEqual({a.target_type for a in self.alerts(ImpactReason.ANCHOR_ORPHANED)},{'usage_event','consumer_binding'})

    def test_ack_permission_tenant_scope_no_owner_spoofing(self):
        self.use();self.c.archive(self.a,'doc');self.c.drain_outbox(self.a)
        alert=self.alerts()[0]
        self.assertEqual(self.c.list_impact_alerts(Actor('other','org')),[])
        self.assertEqual(self.c.list_impact_alerts(Actor('reader','other',org_roles=('admin',))),[])
        with self.assertRaises(PermissionDeniedError):self.c.acknowledge_impact_alert(Actor('other','org'),alert.alert_id)
        with self.assertRaises(NotFoundError):self.c.acknowledge_impact_alert(Actor('reader','other'),alert.alert_id)
        changed=self.c.acknowledge_impact_alert(self.u,alert.alert_id)
        self.assertEqual(changed.status,'acknowledged')
        self.assertEqual(self.c.acknowledge_impact_alert(self.u,alert.alert_id,status='resolved').status,'resolved')
        with self.assertRaises(ValidationError):self.c.acknowledge_impact_alert(self.u,alert.alert_id,status='open')

    def test_redaction_missing_hook_fail_closed_even_for_owned_metadata(self):
        self.use();self.c.set_document_rights(self.a,'doc',ResourceRights(redaction_profile='absent'));self.c.drain_outbox(self.a)
        self.assertTrue(self.c.store.list_impact_alerts('org'))
        self.assertEqual(self.alerts(),[])
        self.c.redaction_registry.register('absent',RegexRedactionHook([('Original','[MASK]')]))
        self.assertTrue(self.alerts())

    def test_replay_preserves_ack_and_never_duplicates(self):
        self.use();self.c.archive(self.a,'doc');self.c.drain_outbox(self.a)
        alert=self.alerts()[0];self.c.acknowledge_impact_alert(self.u,alert.alert_id)
        source=self.c.store._outbox_from_row(self.c.store._execute('SELECT * FROM outbox_events WHERE event_id=?',(alert.source_event_id,))[0])
        ImpactRadar(self.c).process(source);ImpactRadar(self.c).process(source)
        self.assertEqual(len(self.alerts()),2)
        self.assertEqual([a.status for a in self.alerts() if a.alert_id==alert.alert_id],['acknowledged'])

    def test_tenant_admin_drain_cannot_claim_other_tenant_events(self):
        other=Actor('x','foreign',org_roles=('admin',));kb=self.c.create_kb(other,'other');self.c.ingest(other,kb.kb_id,'foreign')
        self.c.drain_outbox(self.a)
        self.assertTrue(self.c.store._execute("SELECT 1 FROM outbox_events WHERE org_id='foreign' AND status='pending'"))
        with self.assertRaises(PermissionDeniedError):self.c.drain_outbox(self.u)

    def test_mcp_final_search_and_pack_have_real_agent_task_lineage(self):
        tools=EvidenceTools(self.c);agent=AgentIdentity('mcp-agent','org');context=GatewayContext(self.u,agent,Purpose.GROUND_INTERNAL_LLM)
        from tests.runtime_helpers import provision_task
        provision_task(self.c,self.a,self.u,'mcp-agent','actual-task',context.purpose)
        result=tools.call('search_evidence',{'query':'Original','task_id':'actual-task'},context)
        usages=self.c.store.list_usage_events_for_doc('org','doc')
        self.assertEqual(len(usages),len(result['hits']));self.assertTrue(usages)
        self.assertTrue(all((u.agent_id,u.consumer_id,u.task_id)==('mcp-agent','mcp-agent','actual-task') for u in usages))
        result=tools.call('get_evidence_pack',{'source_uris':[build_uri('org','doc',1)],'max_chars':100},context)
        self.assertEqual(len(self.c.store.list_usage_events_for_doc('org','doc')),len(usages)+len(result['items']))

    def test_reserved_pack_status_only_changes_not_sealed_data(self):
        pack={'created_by':'reader','items':[{'doc_id':'doc','version':1,'anchor_id':''}],'purpose_bound':'read','excerpt':'DO NOT CHANGE'}
        data=json.dumps(pack)
        self.c.store._execute('INSERT INTO evidence_packs VALUES(?,?,?,?,?,?,?)',('p','org','PRIVATE TITLE','sealed','0'*64,'2026-01-01T00:00:00Z',data))
        self.c.ingest(self.a,'kb','revision',doc_id='doc');self.c.drain_outbox(self.a)
        self.assertEqual(self.c.store._execute('SELECT status,data FROM evidence_packs'),[('impacted',data)])
        self.assertEqual(len([a for a in self.alerts() if a.target_type=='evidence_pack']),1)

    def test_saved_legacy_binding_without_usage_still_alerted(self):
        self.c.bind_consumer(self.u,self.binding)
        before=self.c.store._execute('SELECT * FROM consumer_bindings')
        self.c.ingest(self.a,'kb','revision',doc_id='doc');self.c.drain_outbox(self.a)
        alerts=self.alerts(ImpactReason.SUPERSEDED)
        self.assertEqual(len(alerts),1);self.assertEqual(alerts[0].target_type,'consumer_binding')
        self.assertEqual(self.c.store._execute('SELECT * FROM consumer_bindings'),before)

    def test_historical_events_do_not_affect_future_usage(self):
        self.c.archive(self.a,'doc');self.c.restore(self.a,'doc');self.use()
        self.c.drain_outbox(self.a)
        self.assertEqual(self.alerts(),[])

    def test_audit_failure_rolls_back_authoritative_write_and_outbox(self):
        original=self.c.store.append_audit_event
        count=self.c.store._execute('SELECT COUNT(*) FROM outbox_events')[0][0]
        def fail(event):
            if event.action=='archive':raise RuntimeError('audit sink failed')
            return original(event)
        with patch.object(self.c.store,'append_audit_event',side_effect=fail):
            with self.assertRaises(RuntimeError):self.c.archive(self.a,'doc')
        self.assertFalse(self.c.store.get_document('doc').archived)
        self.assertEqual(self.c.store._execute('SELECT COUNT(*) FROM outbox_events')[0][0],count)
        self.assertEqual(self.c.store.list_audit_events('org',action='archive'),[])

    def test_wrong_agent_cannot_read_owned_impact_metadata(self):
        self.use();self.c.archive(self.a,'doc');self.c.drain_outbox(self.a)
        agent=AgentIdentity('limited','org',allowed_kb_ids=('elsewhere',))
        self.assertEqual(self.c.list_impact_alerts(self.u,agent=agent),[])

    def test_background_dispatcher_converges_without_lock_inversion(self):
        import threading
        from knowledge_sdk.impact.webhook import WebhookDispatcher
        finished=threading.Event()
        self.use();self.c.register_webhook_subscription(self.a,'https://93.184.216.34/hook','offline-test-only-key-123456789012345',['doc.revised'])
        self.c.ingest(self.a,'kb','revision',doc_id='doc')
        def deliver(*args,**kwargs):finished.set();return 204
        worker=OutboxDispatcher(self.c.store,radar=ImpactRadar(self.c),webhook=WebhookDispatcher(self.c.store,transport=deliver))
        worker.start(interval=.01)
        try:self.assertTrue(finished.wait(3))
        finally:worker.close()
        self.assertEqual(len(self.alerts(ImpactReason.SUPERSEDED)),2)

    def test_stale_claim_is_fenced_and_expired_attempt_cap_prevents_post(self):
        from knowledge_sdk.impact.webhook import WebhookDispatcher
        now=datetime.now(timezone.utc)
        old=self.c.store.claim_outbox_batch(now.isoformat())[0]
        new=self.c.store.claim_outbox_batch((now+timedelta(seconds=61)).isoformat())[0]
        calls=[];worker=OutboxDispatcher(self.c.store,radar=ImpactRadar(self.c))
        with patch.object(self.c.store,'claim_outbox_batch',return_value=[old]):
            self.assertEqual(worker.drain_outbox(now=now).dispatched,0)
        self.assertEqual(self.c.store._execute('SELECT attempts FROM outbox_events')[0][0],new.attempts)
        self.c.store._execute("UPDATE outbox_events SET attempts=5,available_at=?",(now.isoformat(),))
        result=worker.drain_outbox(now=now)
        self.assertEqual(result.dead_letter,1)
        self.assertEqual(self.c.store._execute('SELECT status FROM outbox_events')[0][0],'dead_letter')

    def test_saved_binding_identity_prevents_false_positive_role_revocation(self):
        scientist=Actor('reader','org',roles=('scientist',))
        self.c.set_document_acl(self.a,'doc',DocumentACL(allow_roles=['scientist']))
        self.c.bind_consumer(scientist,self.binding)
        self.c.drain_outbox(self.a)
        self.c.set_document_rights(self.a,'doc',ResourceRights())
        self.c.drain_outbox(self.a)
        self.assertEqual(self.c.list_impact_alerts(scientist),[])
        self.assertEqual(self.c.get_consumer_binding(scientist,'task','consumer'),self.binding)

    def test_pre_q2_tagged_binding_rows_remain_readable_and_unchanged(self):
        raw=self.c.store._dump(self.binding)
        self.c.store._execute('INSERT INTO consumer_bindings VALUES(?,?,?,?,?)',('org','reader','task','consumer',raw))
        self.assertEqual(self.c.get_consumer_binding(self.u,'task','consumer'),self.binding)
        self.assertEqual(self.c.list_consumer_bindings(self.u),[self.binding])
        self.c.archive(self.a,'doc');self.c.drain_outbox(self.a)
        self.assertEqual(self.c.store._execute('SELECT data FROM consumer_bindings')[0][0],raw)
        self.assertEqual(len(self.alerts(ImpactReason.RESOURCE_ARCHIVED)),1)

    def test_cross_tenant_denial_audit_contains_no_source_text_or_titles(self):
        foreign=Actor('attacker','foreign',org_roles=('admin',))
        with self.assertRaises(PermissionDeniedError):self.c.retrieve(foreign,'doc')
        events=self.c.store.list_audit_events('foreign')
        self.assertTrue(events);self.assertTrue(all(e.org_id=='foreign' and e.decision_effect==DecisionEffect.DENY for e in events))
        data=json.dumps(encode(events))
        self.assertNotIn('Original evidence alpha',data)
        self.assertFalse(any(e.actor_id=='attacker' for e in self.c.query_audit_events(self.a)))
        self.assertTrue(self.c.verify_audit_chain(foreign).valid)

    def test_org_operations_reject_restricted_or_cross_tenant_agents(self):
        for agent in (AgentIdentity('limited','org',allowed_kb_ids=('kb',)),AgentIdentity('other','foreign')):
            with self.assertRaises(PermissionDeniedError):self.c.drain_outbox(self.a,agent=agent)
            with self.assertRaises(PermissionDeniedError):self.c.verify_audit_chain(self.a,agent=agent)

    def test_invalid_drain_purpose_cannot_mutate_pending_events(self):
        before=self.c.store._execute('SELECT * FROM outbox_events')
        with self.assertRaises(ValidationError):self.c.drain_outbox(self.a,purpose='not-a-purpose')
        self.assertEqual(self.c.store._execute('SELECT * FROM outbox_events'),before)
