"""Fifteen distinct Q2-M1 scenarios. In-memory transport, never external calls."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import hashlib
import json
import time
from unittest.mock import patch
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.audit.ledger import COLUMNS
from knowledge_sdk.events.outbox import OutboxDispatcher
from knowledge_sdk.impact.radar import ImpactRadar,binding_target_id
from knowledge_sdk.impact.webhook import WebhookDispatcher,sign_webhook,verify_webhook_signature,validate_webhook_url

KEY='offline-golden-test-key-never-a-real-secret'


def use(f,*,anchored=False,bound=True):
    f.doc('# H\n\nalpha evidence',filename='fixture.md')
    anchor=f.c.list_anchors(f.u,'doc')[0] if anchored else None
    ref=f.c.reference(f.u,'doc',anchor_id=anchor.anchor_id if anchor else None,excerpt='' if anchor else 'alpha')
    binding=ConsumerBinding('task','golden-task',KnowledgeScope('documents',doc_ids=('doc',)),stage='task-1')
    receipt=f.c.attach(f.u,ref,binding) if bound else f.c.consume(f.u,ref)
    usage=f.c.store.list_usage_events_for_doc('org','doc')[-1]
    return ref,receipt,usage


def expected(usage,bound=True):
    keys={('usage_event',usage.usage_id)}
    if bound:keys.add(('consumer_binding',binding_target_id(usage.actor_id,usage.consumer_type,usage.consumer_id)))
    return keys


def match(o,expected_keys,alerts):
    actual={(a.target_type,a.target_id) for a in alerts}
    o.impact_expected+=len(expected_keys);o.impact_found+=len(expected_keys & actual)
    o.impact_unexpected+=len(actual-expected_keys)
    o.check(actual==expected_keys,'safety')


def audit_check(o,report,seq):
    o.audit_checks+=1
    detected=not report.valid and report.first_invalid_seq==seq
    o.audit_detected+=int(detected);o.check(detected,'safety')


def register_g6(scenario):
    @scenario('q2_usage_real_receipt_mcp_lineage')
    def usage_real(f,o):
        ref,attachment,usage=use(f,anchored=True)
        digest=hashlib.sha256(json.dumps(encode(attachment.receipt),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        o.check(usage.receipt_hash==digest and usage.anchor_id==ref.anchor_id and usage.task_id=='task-1','positive')
        hits=f.call('search_evidence',query='alpha',task_id='mcp-task')['hits']
        events=f.c.store.list_usage_events_for_doc('org','doc')
        o.check(len(events)==1+len(hits) and events[-1].agent_id==f.agent.agent_id and events[-1].task_id=='mcp-task','positive')
        pack=f.call('get_evidence_pack',source_uris=[ref.source_uri])
        o.check(len(f.c.store.list_usage_events_for_doc('org','doc'))==len(events)+len(pack['items']),'positive')

    @scenario('q2_revision_impact_exact_targets')
    def revision(f,o):
        _,_,usage=use(f);f.c.ingest(f.a,'kb','# H\n\nchanged evidence',doc_id='doc')
        f.c.drain_outbox(f.a)
        match(o,expected(usage),[a for a in f.c.list_impact_alerts(f.u) if a.impact_reason==ImpactReason.SUPERSEDED])

    @scenario('q2_drift_and_orphan_anchor_precision')
    def drift(f,o):
        ref,_,usage=use(f,anchored=True)
        plain=f.c.reference(f.u,'doc',excerpt='alpha');f.c.consume(f.u,plain)
        f.c.ingest(f.a,'kb','# H\n\nalpha evidence\n\nalpha evidence',filename='fixture.md',doc_id='doc')
        o.check(f.c.get_anchor(f.a,'doc',ref.anchor_id).reanchor_status==ReanchorStatus.DRIFT_PENDING,'positive')
        f.c.drain_outbox(f.a)
        match(o,expected(usage),[a for a in f.c.list_impact_alerts(f.u) if a.impact_reason==ImpactReason.ANCHOR_DRIFTED])
        f.c.ingest(f.a,'kb','# H\n\nreplacement',doc_id='doc');f.c.drain_outbox(f.a)
        match(o,expected(usage),[a for a in f.c.list_impact_alerts(f.u) if a.impact_reason==ImpactReason.ANCHOR_ORPHANED])

    @scenario('q2_revocation_acl_policy_recheck')
    def revoke(f,o):
        _,_,usage=use(f);other=Actor('still-allowed','org')
        f.c.consume(other,f.c.reference(other,'doc',excerpt='alpha'))
        f.c.set_document_acl(f.a,'doc',DocumentACL(deny_users=['reader']));f.c.drain_outbox(f.a)
        match(o,expected(usage),f.c.list_impact_alerts(f.u))
        o.check(f.c.list_impact_alerts(other)==[],'safety')
        before={a.alert_id for a in f.c.list_impact_alerts(f.u)}
        f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True));f.c.drain_outbox(f.a)
        match(o,expected(usage),[a for a in f.c.list_impact_alerts(f.u) if a.alert_id not in before])

    @scenario('q2_archive_snapshot_lock_no_rewrite')
    def snapshot(f,o):
        ref,attachment,usage=use(f)
        binding=ConsumerBinding('task','saved',KnowledgeScope('documents',doc_ids=('doc',)))
        f.c.bind_consumer(f.u,binding)
        before={t:f.c.store._execute('SELECT * FROM '+t) for t in ('usage_events','consumer_bindings','document_versions')}
        receipt_json=json.dumps(encode(attachment.receipt));f.c.archive(f.a,'doc');f.c.drain_outbox(f.a)
        for table,rows in before.items():o.check(f.c.store._execute('SELECT * FROM '+table)==rows,'safety')
        o.check(ref.version==1 and json.dumps(encode(attachment.receipt))==receipt_json,'safety')
        alerts=f.c.list_impact_alerts(f.u)
        match(o,expected(usage)|{('consumer_binding',binding_target_id('reader','task','saved'))},alerts)
        o.check(all(a.impact_reason==ImpactReason.RESOURCE_ARCHIVED for a in alerts),'positive')

    @scenario('q2_tenant_audit_impact_and_ack_isolation')
    def isolation(f,o):
        use(f);f.c.archive(f.a,'doc');f.c.drain_outbox(f.a)
        foreign=Actor('reader','foreign',org_roles=('admin',));outsider=Actor('outsider','org')
        o.check(f.c.query_audit_events(foreign)==[] and f.c.list_impact_alerts(foreign)==[],'safety')
        o.check(f.c.list_impact_alerts(outsider)==[],'safety')
        o.denied(lambda:f.c.query_audit_events(f.u,actor_id='admin'),'audit_scope_denied')
        alert=f.c.list_impact_alerts(f.u)[0]
        o.denied(lambda:f.c.acknowledge_impact_alert(outsider,alert.alert_id),'impact_scope_denied')
        o.check(f.c.acknowledge_impact_alert(f.u,alert.alert_id).status=='acknowledged','positive')

    @scenario('q2_audit_all_stored_fields_tamper_detected')
    def tamper(f,o):
        f.doc();store=f.c.store
        row=store._execute('SELECT * FROM audit_events WHERE seq_no=2')[0]
        for i,column in enumerate(COLUMNS+('data',)):
            value=222 if column=='seq_no' else '{}' if column=='data' else 'forged'
            store._execute('UPDATE audit_events SET '+column+'=? WHERE event_id=?',(value,row[0]))
            audit_check(o,f.c.verify_audit_chain(f.a),2)
            # Restore by the unchanged original event_id, except that column itself.
            if column=='event_id':store._execute('UPDATE audit_events SET event_id=? WHERE event_id=?',(row[0],value))
            else:store._execute('UPDATE audit_events SET '+column+'=? WHERE event_id=?',(row[i],row[0]))
        o.check(f.c.verify_audit_chain(f.a).valid,'positive')

    @scenario('q2_audit_middle_sequence_deletion_detected')
    def gap(f,o):
        f.doc();f.c.search(f.u,'alpha');f.c.store._execute('DELETE FROM audit_events WHERE seq_no=2')
        audit_check(o,f.c.verify_audit_chain(f.a),2)
        audit_check(o,f.c.verify_audit_chain(f.a,from_seq=3),2)

    @scenario('q2_transaction_rollback_zero_ghost_outbox')
    def rollback(f,o):
        f.doc();before={t:f.c.store._execute('SELECT * FROM '+t) for t in ('documents','document_versions','document_acls','evidence_anchors','outbox_events')}
        with patch.object(f.c.store,'enqueue_outbox',side_effect=RuntimeError('injected rollback')):
            try:f.c.ingest(f.a,'kb','changed',doc_id='doc')
            except RuntimeError:pass
            else:o.check(False,'safety')
        for table,rows in before.items():o.check(f.c.store._execute('SELECT * FROM '+table)==rows,'safety')

    @scenario('q2_outbox_replay_alert_delivery_idempotence')
    def replay(f,o):
        _,_,usage=use(f);f.c.register_webhook_subscription(f.a,'https://93.184.216.34/hook',KEY,['doc.revised'])
        f.c.ingest(f.a,'kb','revision',doc_id='doc');calls=[]
        webhook=WebhookDispatcher(f.c.store,transport=lambda *args,**kw:calls.append(args) or 204)
        radar=ImpactRadar(f.c);worker=OutboxDispatcher(f.c.store,radar=radar,webhook=webhook)
        worker.drain_outbox();event=f.c.store._outbox_from_row(f.c.store._execute("SELECT * FROM outbox_events WHERE event_type='doc.revised'")[0])
        for _ in range(3):radar.process(event);webhook.dispatch(event)
        o.check(len(calls)==1 and len(f.c.store._execute('SELECT * FROM webhook_deliveries'))==1,'safety')
        match(o,expected(usage),[a for a in f.c.list_impact_alerts(f.u) if a.impact_reason==ImpactReason.SUPERSEDED])

    @scenario('q2_webhook_hmac_valid_bound_envelope')
    def signature(f,o):
        stamp=str(int(time.time()));body=b'{"event":"doc.revoked"}'
        signature=sign_webhook(KEY,body,'delivery','event',stamp)
        o.check(verify_webhook_signature(KEY,body,'delivery','event',stamp,signature),'positive')

    @scenario('q2_webhook_tamper_expired_rejected')
    def tamper_signature(f,o):
        stamp=str(int(time.time()));body=b'body';signature=sign_webhook(KEY,body,'delivery','event',stamp)
        for payload,delivery,event,ts in ((body+b'x','delivery','event',stamp),(body,'other','event',stamp),(body,'delivery','other',stamp),(body,'delivery','event',str(int(stamp)-1))):
            o.check(not verify_webhook_signature(KEY,payload,delivery,event,ts,signature),'safety')
        o.check(not verify_webhook_signature(KEY,body,'delivery','event',stamp,signature,now=int(stamp)+301),'safety')

    @scenario('q2_webhook_ssrf_private_metadata_rejected')
    def ssrf(f,o):
        for url in ('https://169.254.169.254','https://10.0.0.1','https://172.16.1.1','https://192.168.1.1','https://127.0.0.1','https://[::1]','https://[fc00::1]','https://[::ffff:127.0.0.1]'):
            o.invalid(lambda:validate_webhook_url(url))
        o.invalid(lambda:validate_webhook_url('http://10.0.0.1',allow_insecure_local=True))
        o.invalid(lambda:validate_webhook_url('https://169.254.169.254',allow_insecure_local=True))

    @scenario('q2_retry_exponential_dead_letter')
    def dead(f,o):
        f.doc();f.c.register_webhook_subscription(f.a,'https://93.184.216.34/hook',KEY,['doc.ingested'])
        calls=[];worker=OutboxDispatcher(f.c.store,webhook=WebhookDispatcher(f.c.store,transport=lambda *a,**kw:calls.append(a) or 503))
        now=datetime.now(timezone.utc)
        for attempt in range(1,6):
            summary=worker.drain_outbox(now=now);o.check(summary.claimed==1,'positive')
            row=f.c.store._execute('SELECT attempts,available_at FROM outbox_events')[0]
            o.check(row==(attempt,(now+timedelta(seconds=2**attempt)).isoformat()),'positive')
            now+=timedelta(seconds=2**attempt)
        o.check(f.c.store._execute('SELECT status FROM outbox_events')==[('dead_letter',)] and len(calls)==5,'safety')
        o.check(f.c.store._execute('SELECT status FROM webhook_deliveries')==[('dead_letter',)],'safety')

    @scenario('q2_drain_complete_targets_and_signed_push_under_minute')
    def converge(f,o):
        f.doc();ref=f.c.reference(f.u,'doc',excerpt='alpha')
        for _ in range(30):f.c.consume(f.u,ref)
        usages=f.c.store.list_usage_events_for_doc('org','doc')
        f.c.register_webhook_subscription(f.a,'https://93.184.216.34/hook',KEY,['doc.revised'])
        f.c.ingest(f.a,'kb','new material',doc_id='doc');calls=[]
        worker=OutboxDispatcher(f.c.store,radar=ImpactRadar(f.c),webhook=WebhookDispatcher(f.c.store,transport=lambda url,body,headers,**kw:calls.append((body,headers)) or 204))
        start=time.monotonic();summary=worker.drain_outbox();o.check(time.monotonic()-start<60 and summary.failed==0 and len(calls)==1,'positive')
        alerts=[a for a in f.c.list_impact_alerts(f.u) if a.impact_reason==ImpactReason.SUPERSEDED]
        match(o,{('usage_event',u.usage_id) for u in usages},alerts)
        body,headers=calls[0];o.check(verify_webhook_signature(KEY,body,headers['X-KB-Webhook-Id'],headers['X-KB-Event-Id'],headers['X-KB-Webhook-Timestamp'],headers['X-KB-Webhook-Signature']),'positive')
        o.check(len(json.loads(body)['impact_alerts'])==30,'positive')
