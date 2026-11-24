"""Reproducible Phase3 isolated loopback HTTP probe; no external adapters/models."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib,json,os,secrets,socket,subprocess,sys,tempfile,threading
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from knowledge_sdk import (Actor,AgentIdentity,Purpose,ResourceRights,LocalKnowledgeClient,HttpKnowledgeClient,
    SQLiteStore,RegexRedactionHook,PermissionDeniedError,ValidationError,ReanchorStatus)
from knowledge_sdk.contracts.uri import build_uri
from knowledge_sdk.server.auth import SQLiteReplayStore,signed_headers
ROOT=Path(__file__).resolve().parents[3]
ADMIN=Actor('admin','probe-org',org_roles=('admin',));USER=Actor('reader','probe-org')


def serve(port,path):
    import uvicorn
    from knowledge_sdk.server.app import create_app
    c=LocalKnowledgeClient(SQLiteStore(Path(path).with_name('isolated-business.sqlite3')))
    try:
        for kb in ('kb-a','kb-b'):c.create_kb(ADMIN,kb,kb_id=kb,space_type='enterprise_public')
        c.redaction_registry.register('pii',RegexRedactionHook([('secret','[MASK]')]))
        app=create_app(c,auth_secret=os.environ['KNOWLEDGE_AUTH_SECRET'],replay_store=SQLiteReplayStore(path),ui_prefix='/kb/ui')
        uvicorn.run(app,host='127.0.0.1',port=port,proxy_headers=False)
    finally:c.store.close()


def probe():
    print(datetime.now(timezone(timedelta(hours=8))).isoformat(),'Asia/Shanghai',flush=True)
    secret=secrets.token_hex(32);env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),KNOWLEDGE_AUTH_SECRET=secret)
    for key in list(env):
        if key.startswith('KNOWLEDGE_SDK_LIVE_'):env.pop(key)
    with tempfile.TemporaryDirectory(prefix='kb-phase3-live-') as directory:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base='http://127.0.0.1:'+str(port);command=[sys.executable,__file__,'--serve',str(port),str(Path(directory)/'replay.sqlite3')]
        print('$ PYTHONPATH=src KNOWLEDGE_AUTH_SECRET=<random;not logged>',' '.join(command),flush=True)
        with tempfile.TemporaryFile(mode='w+') as output:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
            def raw(path,method='GET',body=b'',headers=None):
                try:
                    with urlopen(Request(base+path,data=body if method!='GET' else None,method=method,headers=headers or {}),timeout=2) as r:return r.status,r.read(),r.headers
                except HTTPError as error:
                    try:return error.code,error.read(),error.headers
                    finally:error.close()
            def expect_denied(call,reason):
                try:call()
                except PermissionDeniedError as error:assert str(error)==reason,(str(error),reason)
                else:raise AssertionError('Expected denial '+reason)
            http=HttpKnowledgeClient(base,auth_secret=secret)
            try:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError('Probe server failed')
                    try:
                        if raw('/v1/health')[0]==200:break
                    except (OSError,TimeoutError):pass
                    threading.Event().wait(.05)
                else:raise RuntimeError('Probe startup timeout')
                assert http.health()['version']=='1.2.0'
                for path in ('/kb/ui','/kb/ui/config','/kb/ui/assets/i18n.js'):
                    status,_,headers=raw(path);assert status==200 and headers['Cache-Control']=='no-store'
                    print('HTTP GET',path,status,'no-store')
                assert raw('/ui')[0]==404
                v=http.ingest(ADMIN,'kb-a','# Policy\n\nsecret policy\n\nstable paragraph','policy.md',doc_id='doc-md')
                anchors=http.list_anchors(USER,'doc-md');a=next(x for x in anchors if x.quote.exact=='secret policy')
                original=http.reference(USER,'doc-md',anchor_id=a.anchor_id)
                assert http.consume(USER,original).evidence_kind=='anchor_excerpt'
                print('Real HTTP MD ingest/list/get/reference/consume: v1 anchored, anchor_excerpt')
                http.ingest(ADMIN,'kb-a','# Moved\n\nsecret policy\n\nsecret policy\n\nstable paragraph','policy.md',doc_id='doc-md')
                pending=http.get_anchor(USER,'doc-md',a.anchor_id);assert pending.reanchor_status==ReanchorStatus.DRIFT_PENDING
                ref2=replace(original,version=2,source_uri=build_uri(USER.org_id,'doc-md',2,anchor_id=a.anchor_id))
                assert http.consume(USER,ref2).reason_code=='anchor_drift_pending'
                expect_denied(lambda:http.confirm_anchor_reanchor(USER,'doc-md',2,a.anchor_id),'space_boundary_denied')
                scoped=AgentIdentity('probe','probe-org',allowed_kb_ids=('kb-b',))
                expect_denied(lambda:http.confirm_anchor_reanchor(ADMIN,'doc-md',2,a.anchor_id,agent=scoped),'agent_scope_denied')
                assert http.confirm_anchor_reanchor(ADMIN,'doc-md',2,a.anchor_id).reanchor_status==ReanchorStatus.ANCHORED
                assert http.consume(USER,http.reference(USER,'doc-md',anchor_id=a.anchor_id)).status=='consumed'
                print('v2 duplicate/moved anchor -> pending receipt denied; reader/scoped-agent confirmation denied; admin explicit confirm -> consumed')
                http.ingest(ADMIN,'kb-a','# Moved\n\nonly replacement','policy.md',doc_id='doc-md')
                ref3=replace(ref2,version=3,source_uri=build_uri(USER.org_id,'doc-md',3,anchor_id=a.anchor_id))
                receipt=http.consume(USER,ref3);assert (receipt.status,receipt.reason_code)==('unavailable','anchor_orphaned')
                try:http.confirm_anchor_reanchor(ADMIN,'doc-md',3,a.anchor_id)
                except ValidationError:pass
                else:raise AssertionError('Orphan forced alive')
                print('v3 deleted quote -> unavailable/anchor_orphaned; confirmation 400')
                csv='compound,activity,units\nsecret,>10000,nM\nB,inactive,mg/kg\nC,<0.01,nM'
                http.ingest(ADMIN,'kb-a',csv,'assay.csv',doc_id='doc-csv',rights=ResourceRights(redaction_profile='pii'))
                rows=http.list_anchors(USER,'doc-csv');row=next(x for x in rows if '>10000' in x.quote.exact)
                assert row.quote.exact=='[MASK] | >10000 | nM' and row.table_cell.cell_ref=='A2:C2' and row.table_cell.unit_hint=='nM'
                assert row.quote_sha256==hashlib.sha256(row.quote.exact.encode()).hexdigest()
                safe=http.reference(USER,'doc-csv',anchor_id=row.anchor_id);assert http.consume(USER,safe).status=='consumed'
                print('Real CSV layout+redaction:',row.quote.exact,'cell='+row.table_cell.cell_ref,'hash='+row.quote_sha256)
                expect_denied(lambda:http.list_anchors(USER,'doc-csv',purpose=Purpose.GROUND_EXTERNAL_LLM),'external_llm_prohibited')
                expect_denied(lambda:http.list_anchors(USER,'doc-csv',agent=scoped),'agent_scope_denied')
                http.set_document_rights(ADMIN,'doc-csv',ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True,redaction_profile='pii'))
                assert http.list_anchors(USER,'doc-csv',purpose=Purpose.GROUND_EXTERNAL_LLM)
                print('Signed purpose/agent policy: external default 403; explicit rights 200; kb-b scoped agent 403; no external call/model')
                http.set_document_rights(ADMIN,'doc-csv',ResourceRights(redaction_profile='missing'))
                expect_denied(lambda:http.list_anchors(USER,'doc-csv'),'redaction_hook_missing')
                assert http.consume(USER,safe).reason_code=='redaction_hook_missing'
                print('Missing hook -> list 403 and consume denied/redaction_hook_missing')
                path='/v1/anchors/list';body=json.dumps({'params':{'doc_id':'doc-md'}}).encode();headers=signed_headers(USER,secret,'POST',path,body)
                assert raw(path,'POST',body,headers)[0]==200;assert raw(path,'POST',body,headers)[0]==401
                print('Dedicated SQLiteReplayStore actual HTTP identical signed nonce: 200 then 401')
                for field in ('agent','purpose','policy_context'):
                    body=json.dumps({'params':{'doc_id':'doc-md',field:{}}}).encode();headers=signed_headers(USER,secret,'POST',path,body)
                    assert raw(path,'POST',body,headers)[0]==400
                    print('Signed body injection',field,'400')
                print('L3 isolated Phase3 real HTTP probe PASS; external embeddings/models/Qdrant calls 0')
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                output.seek(0);server_output=output.read();assert secret not in server_output,'Secret leak'
                assert 'ResourceWarning' not in server_output and 'Exception ignored' not in server_output
                print('Probe stopped; returncode',process.returncode)
                print('Raw server stdout/stderr (no signing secrets):\n'+server_output)
    print('Temporary business/replay DBs removed; no existing services or collections touched')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':serve(int(sys.argv[2]),sys.argv[3])
    else:probe()
