"""Real disposable signed HTTP -> usage -> impact -> signed Webhook proof."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import uvicorn
from knowledge_sdk import *
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.server.app import create_app
from knowledge_sdk.server.auth import signed_headers
from tests.q2.test_outbox_webhook import Receiver


def main():
    print(datetime.now().astimezone().isoformat(),'Asia/Shanghai',flush=True)
    auth=secrets.token_hex(32);hook_key=secrets.token_hex(32)
    admin=Actor('admin','wire',org_roles=('admin',));user=Actor('reader','wire');stranger=Actor('stranger','wire')
    with tempfile.TemporaryDirectory(prefix='q2-impact-wire-') as tmp,closing(Receiver()) as receiver:
        with closing(SQLiteStore(Path(tmp)/'disposable.db')) as store:
            client=LocalKnowledgeClient(store,allow_insecure_local_webhook=True)
            client.create_kb(admin,'wire','enterprise',kb_id='kb')
            for doc in ('revised','archived','acl'):
                client.ingest(admin,'kb','# H\n\nalpha evidence',filename='fixture.md',doc_id=doc,title='DO NOT LEAK TITLE')
            client.drain_outbox(admin)
            sub=client.register_webhook_subscription(admin,receiver.url,hook_key,
                  ['doc.revised','doc.revoked','doc.archived','acl.updated','anchor.drifted','anchor.orphaned'],allow_insecure_local=True)
            assert 'secret' not in sub
            server=uvicorn.Server(uvicorn.Config(create_app(client,auth_secret=auth,enable_ui=False),log_level='warning',proxy_headers=False,ws='none'))
            sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(32)
            thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]});thread.start()
            try:
                deadline=time.monotonic()+10
                while not server.started:
                    if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Temporary listener did not start')
                    threading.Event().wait(.01)
                http=HttpKnowledgeClient('http://127.0.0.1:%d'%sock.getsockname()[1],auth_secret=auth)
                old_refs=[];old_receipts=[]
                for doc in ('revised','archived','acl'):
                    anchor=http.list_anchors(user,doc)[0]
                    ref=http.reference(user,doc,anchor_id=anchor.anchor_id)
                    attachment=http.attach(user,ref,ConsumerBinding('task','wire-'+doc,stage='wire-task'))
                    old_refs.append(ref);old_receipts.append(attachment.receipt)
                before=store._execute('SELECT * FROM usage_events');receipt_json=json.dumps(encode(old_receipts),sort_keys=True)
                began=time.monotonic()
                http.ingest(admin,'kb','# H\n\nalpha evidence\n\nalpha evidence',filename='fixture.md',doc_id='revised')
                assert http.drain_outbox(admin).failed==0
                alerts=http.list_impact_alerts(user,doc_id='revised')
                assert len([a for a in alerts if a.impact_reason==ImpactReason.SUPERSEDED])==2
                assert len([a for a in alerts if a.impact_reason==ImpactReason.ANCHOR_DRIFTED])==2
                http.ingest(admin,'kb','# H\n\nreplacement',filename='fixture.md',doc_id='revised')
                http.drain_outbox(admin)
                assert len([a for a in http.list_impact_alerts(user,doc_id='revised') if a.impact_reason==ImpactReason.ANCHOR_ORPHANED])==2
                http.set_document_rights(admin,'revised',ResourceRights(revoked=True));http.archive(admin,'archived')
                http.set_document_acl(admin,'acl',DocumentACL(deny_users=['reader']))
                assert http.drain_outbox(admin).failed==0
                alerts=http.list_impact_alerts(user)
                assert all(isinstance(a,ImpactAlert) for a in alerts)
                assert len([a for a in alerts if a.impact_reason==ImpactReason.ACCESS_REVOKED])==4
                assert len([a for a in alerts if a.impact_reason==ImpactReason.RESOURCE_ARCHIVED])==2
                assert store._execute('SELECT * FROM usage_events')==before
                assert json.dumps(encode(old_receipts),sort_keys=True)==receipt_json and all(r.version==1 for r in old_refs)
                assert store.get_version('revised',1).text=='# H\n\nalpha evidence'
                assert http.list_impact_alerts(stranger)==[]
                foreign=Actor('reader','foreign',org_roles=('admin',))
                assert http.list_impact_alerts(foreign)==[]
                foreign_audit=http.query_audit_events(foreign)
                assert all(e.org_id=='foreign' and not e.doc_id for e in foreign_audit)
                alert=alerts[0]
                try:http.acknowledge_impact_alert(stranger,alert.alert_id)
                except PermissionDeniedError:pass
                else:raise AssertionError('Unrelated actor acknowledged alert')
                assert http.acknowledge_impact_alert(user,alert.alert_id).status=='acknowledged'
                assert http.acknowledge_impact_alert(user,alert.alert_id,status='resolved').status=='resolved'
                # The admin can audit decisions on sources it currently can read;
                # denied source data is never returned via an audit-query bypass.
                audit=http.query_audit_events(admin);assert audit and all(isinstance(a,AuditEvent) for a in audit)
                assert http.verify_audit_chain(admin).valid
                raw=json.dumps({'params':{}}).encode();path='/v1/impact/alerts'
                headers={'Content-Type':'application/json',**signed_headers(user,auth,'POST',path,raw)}
                def request(headers):
                    try:
                        with urlopen(Request(http.base_url+path,data=raw,headers=headers),timeout=10) as response:return response.status
                    except HTTPError as error:
                        with error:return error.code
                assert request({})==401 and request(headers)==200 and request(headers)==401
                # Foreign pending event must not be claimed by this tenant admin.
                foreignkb=client.create_kb(foreign,'foreign','enterprise')
                client.ingest(foreign,foreignkb.kb_id,'other tenant')
                http.drain_outbox(admin)
                assert store._execute("SELECT COUNT(*) FROM outbox_events WHERE org_id='foreign' AND status='pending'")[0][0]==1
                assert time.monotonic()-began<60
                assert receiver.requests
                delivered_ids=set();webhook_alerts=set()
                for headers,body in receiver.requests:
                    assert verify_webhook_signature(hook_key,body,headers['X-KB-Webhook-Id'],headers['X-KB-Event-Id'],headers['X-KB-Webhook-Timestamp'],headers['X-KB-Webhook-Signature'])
                    assert not verify_webhook_signature(hook_key,body+b'x',headers['X-KB-Webhook-Id'],headers['X-KB-Event-Id'],headers['X-KB-Webhook-Timestamp'],headers['X-KB-Webhook-Signature'])
                    assert headers['X-KB-Webhook-Id'] not in delivered_ids;delivered_ids.add(headers['X-KB-Webhook-Id'])
                    assert b'DO NOT LEAK TITLE' not in body and b'alpha evidence' not in body
                    webhook_alerts.update(a['alert_id'] for a in json.loads(body)['impact_alerts'])
                assert {a.alert_id for a in alerts}<=webhook_alerts
                count=len(receiver.requests);http.drain_outbox(admin);assert len(receiver.requests)==count
                print('PASS actual signed HTTP: consume/attach lineage, audit/query + audit/verify, impact/alerts + impact/ack + events/drain, typed parity',flush=True)
                print('PASS real revisions: SUPERSEDED + DRIFT_PENDING + ORPHANED; archive + revoke + ACL deny: exact usage/binding targets and locked v1 snapshots',flush=True)
                print('PASS signed real loopback Webhook: %d unique deliveries, %d/%d impact alert IDs covered, valid HMAC accepted/tamper rejected, <60 seconds'%(count,len({a.alert_id for a in alerts}&webhook_alerts),len(alerts)),flush=True)
                print('PASS unsigned401/replay401/unrelated403/foreign-empty, tenant-isolated drain, old source versions and receipts unchanged',flush=True)
            finally:
                server.should_exit=True;thread.join(15);sock.close();assert not thread.is_alive()
    print('All disposable DBs/listeners closed; no model/embedding/paid/Qdrant calls. L4 NOT_RUN; independent L5 PENDING.',flush=True)


if __name__=='__main__':main()
