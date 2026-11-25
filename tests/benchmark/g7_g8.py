"""25 additional independent executable scenarios. No legacy assertion is changed."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import base64,hashlib,hmac,json,time,tempfile,zipfile,io
from knowledge_sdk import *
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.contracts.anchors import ReanchorStatus
from knowledge_sdk.contracts.policy import Purpose
from knowledge_sdk.server.oidc import OIDCAuthenticator
from knowledge_sdk.server.scim import SCIMService
from knowledge_sdk.connectors import ControlledFilesystemConnector,WebhookSyncConnector,ConnectorSyncRunner
from knowledge_sdk.connectors.webhook_sync import sign_sync
from knowledge_sdk.exceptions import ConflictError

SCENARIOS={}
def case(name):
    def register(fn):SCENARIOS[name]=fn;return fn
    return register


def controlled(f):
    f.c.create_kb(f.a,'L2','enterprise',kb_id='l2',space_type='enterprise_public',governance_tier='l2_controlled')
    f.c.ingest(f.a,'l2','# H\n\nalpha evidence',filename='f.md',doc_id='doc',rights=ResourceRights(allow_export=True))
    return Actor('reviewer','org',org_roles=('admin',)),Actor('publisher','org',org_roles=('admin',))
def publish(f):
    r,p=controlled(f)
    f.c.submit_for_review(f.a,'doc',expected_version=1)
    f.c.approve_release(r,'doc',version=1,expected_version=1)
    f.c.publish_release(p,'doc',version=1,expected_version=1)
    return r,p
def pack(f,entries=None):return f.c.create_evidence_pack(f.u,'decision',entries or [{'doc_id':'doc','version':1}])

@case('m4_l2_admin_cannot_self_approve')
def g701(f,o):
    controlled(f);f.c.submit_for_review(f.a,'doc',expected_version=1)
    o.denied(lambda:f.c.approve_release(f.a,'doc',version=1,expected_version=1),'self_review_forbidden')
@case('m4_l2_draft_search_and_read_isolation')
def g702(f,o):
    controlled(f);o.check(not f.c.search(f.u,'alpha').hits,'safety');o.denied(lambda:f.c.retrieve(f.u,'doc'),'lifecycle_not_published')
@case('m4_l2_three_identity_publication')
def g703(f,o):
    publish(f);o.check(f.c.retrieve(f.u,'doc').text=='# H\n\nalpha evidence','positive')
@case('m4_l2_optimistic_version_guard')
def g704(f,o):
    controlled(f)
    try:f.c.submit_for_review(f.a,'doc',expected_version=2)
    except ConflictError:pass
    else:o.check(False,'safety')
    o.check(f.c.store.get_version('doc',1).lifecycle_state=='draft','positive')

def issue(f,action):
    publish(f)
    i=f.c.report_evidence_issue(f.u,'kb://org/org/doc/doc@1','inaccuracy','verify source')
    return f.c.resolve_evidence_issue(f.a,i.issue_id,action,'reviewed',expected_version=1)
@case('m4_issue_revision_draft')
def g705(f,o):
    result=issue(f,'create_revision_draft');o.check(result.status=='resolved','positive');o.check(f.c.store.latest_version('doc')==2,'positive');o.check(f.c.store.get_version('doc',2).lifecycle_state=='draft','safety')
@case('m4_issue_retrieval_tuning')
def g706(f,o):o.check(issue(f,'retrieval_tuning').resolution.resolution_action=='retrieval_tuning','positive')
@case('m4_issue_keep_dissent')
def g707(f,o):o.check(issue(f,'keep_dissent').resolution.resolution_action=='keep_dissent','positive')
@case('m4_issue_dismissed')
def g708(f,o):o.check(issue(f,'dismissed').status=='dismissed','positive')
@case('m4_pack_drift_pending_denied')
def g709(f,o):
    publish(f);a=f.c.list_anchors(f.a,'doc')[0]
    f.c.store.update_anchor(replace(a,reanchor_status=ReanchorStatus.DRIFT_PENDING))
    o.denied(lambda:pack(f,[{'doc_id':'doc','version':1,'anchor_id':a.anchor_id}]))
@case('m4_pack_stance_matrix')
def g710(f,o):
    publish(f);p=pack(f,[{'doc_id':'doc','version':1,'stance':s} for s in ('supporting','refuting','negative','conflict')]);o.check({i.stance for i in p.items}=={'supporting','refuting','negative','conflict'},'positive')
@case('m4_pack_ro_crate_integrity')
def g711(f,o):
    publish(f);p=pack(f);data=f.c.export_evidence_pack(f.u,p.pack_id,format='ro_crate')
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(data.content))) as z:
        meta=json.loads(z.read('ro-crate-metadata.json'));o.check('https://w3id.org/ro/crate/1.2' in json.dumps(meta),'positive');o.check(z.testzip() is None,'positive')
@case('m4_pack_acl_deny_blocks_read_and_export')
def g712(f,o):
    publish(f);p=pack(f);f.c.set_document_acl(f.a,'doc',DocumentACL(deny_users=['reader']))
    o.denied(lambda:f.c.get_evidence_pack(f.u,p.pack_id));o.denied(lambda:f.c.export_evidence_pack(f.u,p.pack_id))
@case('m4_pack_revocation_blocks_json_and_zip')
def g713(f,o):
    publish(f);p=pack(f);f.c.set_document_rights(f.a,'doc',ResourceRights(revoked=True))
    for fmt in ('json','ro_crate'):o.denied(lambda:f.c.export_evidence_pack(f.u,p.pack_id,format=fmt))
@case('m4_pack_dissent_ordered_deduplication')
def g714(f,o):
    r,p=publish(f);f.c.record_dissent(r,'doc',version=1,note='minority')
    p=pack(f,[{'doc_id':'doc','version':1,'stance':s} for s in ('supporting','refuting')]);o.check(p.dissent_notes==('minority',),'positive')
@case('m4_pack_sql_payload_digest_parity')
def g715(f,o):
    publish(f);p=pack(f);s=f.c.store
    if f.engine=='postgres':
        with s.tenant_scope('org'):s._execute('UPDATE evidence_packs SET pack_sha256=%s WHERE org_id=%s AND pack_id=%s',('0'*64,'org',p.pack_id))
    else:s._execute('UPDATE evidence_packs SET pack_sha256=? WHERE org_id=? AND pack_id=?',('0'*64,'org',p.pack_id))
    try:s.get_evidence_pack('org',p.pack_id)
    except ConflictError as exc:o.check(str(exc)=='Pack digest mismatch','safety')
    else:o.check(False,'safety')

# Explicitly fake test key; never an enterprise IdP credential.
TEST_KEY=b'offline-m4-benchmark-key-not-production-0000'
def token(**changes):
    header=changes.pop('_header',{'alg':'HS256','kid':'test'})
    claims={'iss':'https://test-issuer.invalid','aud':'sdk','sub':'reader','org_id':'org','exp':int(time.time())+600,'nbf':int(time.time())-1,'roles':[],'department_ids':[],'clearance_level':'','policy_generation':1,'jti':'one'};claims.update(changes)
    enc=lambda v:base64.urlsafe_b64encode(json.dumps(v,separators=(',',':')).encode()).decode().rstrip('=')
    a,b=enc(header),enc(claims);sig=base64.urlsafe_b64encode(hmac.new(TEST_KEY,(a+'.'+b).encode(),hashlib.sha256).digest()).decode().rstrip('=')
    return a+'.'+b+'.'+sig
def authenticator():return OIDCAuthenticator('https://test-issuer.invalid','sdk',algorithms=('HS256',),hs256_keys={'test':TEST_KEY})
@case('m4_oidc_malformed_and_bad_signature')
def g801(f,o):
    auth=authenticator();o.invalid(lambda:auth.authenticate('broken'));t=token();o.invalid(lambda:auth.authenticate(t[:-5]+'wrong'))
@case('m4_oidc_expired_and_temporal_type')
def g802(f,o):
    o.invalid(lambda:authenticator().authenticate(token(exp=int(time.time())-10)));o.invalid(lambda:authenticator().authenticate(token(exp=True)))
@case('m4_oidc_none_and_algorithm_confusion')
def g803(f,o):
    o.invalid(lambda:authenticator().authenticate(token(_header={'alg':'none','kid':'test'})));o.invalid(lambda:authenticator().authenticate(token(_header={'alg':'RS256','kid':'test'})))
@case('m4_oidc_claims_tenant_and_jti')
def g804(f,o):
    auth=authenticator();a=auth.authenticate(token());f.doc();o.check(f.c.retrieve(a,'doc').text,'positive');o.invalid(lambda:auth.authenticate(token()))
    foreign=authenticator().authenticate(token(org_id='foreign'));o.denied(lambda:f.c.retrieve(foreign,'doc'),'tenant_mismatch')
@case('m4_scim_deactivate_stale_privileged_actor')
def g805(f,o):
    f.doc();svc=SCIMService(f.c);svc.write(f.a,{'id':'reader','userName':'reader','roles':[],'org_roles':['admin']})
    a=authenticator().authenticate(token(org_roles=['admin']));o.check(f.c.retrieve(a,'doc').text,'positive');svc.write(f.a,{'active':False},'reader');o.denied(lambda:f.c.retrieve(a,'doc'),'principal_session_stale')
@case('m4_scim_department_generation_stale_mcp')
def g806(f,o):
    from knowledge_sdk.mcp import EvidenceTools,GatewayContext
    f.doc();svc=SCIMService(f.c);svc.write(f.a,{'id':'reader','department_ids':['old']});a=authenticator().authenticate(token(department_ids=['old']))
    svc.write(f.a,{'department_ids':['new']},'reader');o.denied(lambda:f.c.search(a,'alpha'),'principal_session_stale')
    try:EvidenceTools(f.c).call('search_evidence',{'query':'alpha'},GatewayContext(a))
    except PermissionDeniedError:pass
    else:o.check(False,'safety')

def filesystem(f,o,action='revoke'):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'source.txt';path.write_text('alpha filesystem evidence')
        (Path(d)/'source.txt.acl.json').write_text(json.dumps({'rights':{'allow_export':True}}))
        connector=ControlledFilesystemConnector('fs',d,org_id='org',missing_action=action);runner=ConnectorSyncRunner(f.c)
        report=runner.run_once(f.a,connector,org_id='org',kb_id='kb');o.check(report.applied_upserts==1,'positive')
        doc=[d for d in f.c.store.list_documents('org')][0];p=f.c.create_evidence_pack(f.u,'source',[{'doc_id':doc.doc_id,'version':1}])
        report=runner.run_once(f.a,connector,org_id='org',kb_id='kb');o.check(report.applied_upserts==0 and f.c.store.latest_version(doc.doc_id)==1,'positive')
        path.unlink();report=runner.run_once(f.a,connector,org_id='org',kb_id='kb');o.check(report.applied_tombstones==1,'positive');f.c.drain_outbox(f.a)
        o.check(f.c.store.get_evidence_pack('org',p.pack_id).status=='impacted','safety');o.check(any(a.target_id==p.pack_id for a in f.c.store.list_impact_alerts('org')),'positive')
@case('m4_filesystem_incremental_revoke_impact')
def g807(f,o):filesystem(f,o)
@case('m4_filesystem_deleted_archive_impact')
def g808(f,o):filesystem(f,o,'archive')
@case('m4_webhook_signature_cursor_idempotency')
def g809(f,o):
    runner=ConnectorSyncRunner(f.c);conn=WebhookSyncConnector('wiki','offline-webhook-test-key-not-production-000',org_id='org')
    body=json.dumps({'upserts':[{'external_id':'x','doc_id':'wiki-doc','content':'alpha wiki evidence','rights':{'allow_export':True}}]}).encode();stamp=str(int(time.time()));headers={'X-KB-Event-Id':'event1','X-KB-Webhook-Timestamp':stamp,'X-KB-Webhook-Signature':sign_sync(conn._secret,body,'event1',stamp)}
    first=runner.run_once(f.a,conn,org_id='org',kb_id='kb',webhook=(body,headers));second=runner.run_once(f.a,conn,org_id='org',kb_id='kb',webhook=(body,headers));o.check(first.applied_upserts==1 and second.applied_upserts==0 and f.c.store.latest_version('wiki-doc')==1,'positive')
    o.denied(lambda:runner.run_once(f.a,conn,org_id='org',kb_id='kb',webhook=(body,dict(headers,**{'X-KB-Webhook-Signature':'invalid'}))))
@case('m4_webhook_tombstone_impacts_pack')
def g810(f,o):
    runner=ConnectorSyncRunner(f.c);conn=WebhookSyncConnector('wiki','offline-webhook-test-key-not-production-000',org_id='org')
    def send(event,data):
        body=json.dumps(data).encode();stamp=str(int(time.time()));headers={'X-KB-Event-Id':event,'X-KB-Webhook-Timestamp':stamp,'X-KB-Webhook-Signature':sign_sync(conn._secret,body,event,stamp)}
        return runner.run_once(f.a,conn,org_id='org',kb_id='kb',webhook=(body,headers))
    send('create',{'upserts':[{'external_id':'x','doc_id':'wiki-doc','content':'alpha wiki evidence','rights':{'allow_export':True}}]});p=f.c.create_evidence_pack(f.u,'wiki',[{'doc_id':'wiki-doc','version':1}]);send('delete',{'tombstones':[{'external_id':'x','doc_id':'wiki-doc','action':'revoke'}]});f.c.drain_outbox(f.a)
    o.check(f.c.store.get_evidence_pack('org',p.pack_id).status=='impacted','safety');o.check(any(a.target_id==p.pack_id for a in f.c.store.list_impact_alerts('org')),'positive')
