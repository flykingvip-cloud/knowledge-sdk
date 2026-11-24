"""Actual official MCP client + Streamable HTTP loopback, never a handler mock."""
from __future__ import annotations
import asyncio,json,os,secrets,socket,subprocess,sys,tempfile,threading
from contextlib import closing
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import sqlite3
from knowledge_sdk import *
from knowledge_sdk.mcp import create_app
from knowledge_sdk.server.auth import signed_headers,SQLiteReplayStore
ROOT=Path(__file__).resolve().parents[3]
ADMIN=Actor('admin','wire-org',org_roles=('admin',));USER=Actor('reader','wire-org');OTHER=Actor('other','other-org')
AGENT=AgentIdentity('wire-agent','wire-org',allowed_purposes=(Purpose.GROUND_EXTERNAL_LLM,))
OTHER_AGENT=AgentIdentity('other-agent','other-org',allowed_purposes=(Purpose.GROUND_EXTERNAL_LLM,))


def serve(mode,port,db,replay):
    import uvicorn
    c=LocalKnowledgeClient(SQLiteStore(db))
    try:
        if not c.store.list_kbs(ADMIN.org_id):
            rights=ResourceRights(allowed_purposes=tuple(Purpose),allow_external_llm=True,redaction_profile='pii')
            c.create_kb(ADMIN,'wire',kb_id='wire-kb',space_type='enterprise_public')
            c.ingest(ADMIN,'wire-kb','alpha tenant first secret evidence',doc_id='wire-doc',rights=rights)
            c.ingest(ADMIN,'wire-kb','blocked external content',doc_id='blocked-doc')
            c.create_kb(OTHER,'other',kb_id='other-kb')
            c.ingest(OTHER,'other-kb','alpha tenant second secret evidence',doc_id='other-doc',rights=rights)
        c.redaction_registry.register('pii',RegexRedactionHook([('secret','[MASK]')]))
        kwargs=dict(auth_secret=os.environ['KNOWLEDGE_AUTH_SECRET'],replay_store=SQLiteReplayStore(replay))
        if mode=='mcp':app=create_app(c,**kwargs)
        else:
            from knowledge_sdk.server.app import create_app as http_app
            app=http_app(c,ui_prefix='/kb/ui',**kwargs)
        uvicorn.run(app,host='127.0.0.1',port=port,proxy_headers=False)
    finally:c.store.close()


def raw(base,path,method='GET',body=b'',headers=None):
    try:
        with urlopen(Request(base+path,data=body if method!='GET' else None,method=method,headers=headers or {}),timeout=3) as r:return r.status,r.read()
    except HTTPError as error:
        try:return error.code,error.read()
        finally:error.close()


async def official_checks(bases,secret,db):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    print('Official SDK versions:',__import__('importlib.metadata',fromlist=['version']).version('mcp'),flush=True)
    async def connect_case(actor,agent):
        async def sign(request):
            body=await request.aread()
            request.headers.update(signed_headers(actor,secret,request.method,request.url.raw_path.decode(),body,agent=agent.to_dict()))
        async with httpx.AsyncClient(event_hooks={'request':[sign]},timeout=15) as http:
            async with streamable_http_client(bases[0]+'/mcp',http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    initialized=await session.initialize();assert initialized.serverInfo.version=='1.2.0'
                    listed=await session.list_tools();assert {t.name for t in listed.tools}=={'search_evidence','verify_citation','get_evidence_pack','report_evidence_issue'}
                    assert all(t.inputSchema['additionalProperties'] is False for t in listed.tools)
                    async def call(name,args):
                        result=await session.call_tool(name,args)
                        return result,json.loads(result.content[0].text)
                    result,data=await call('search_evidence',{'query':'alpha'})
                    assert not result.isError and data['status']=='ok',data
                    hit=data['hits'][0];assert hit['receipt']['consumer_id']==agent.agent_id
                    assert hit['doc_id']==('wire-doc' if actor.org_id=='wire-org' else 'other-doc')
                    assert '[MASK]' in hit['excerpt'] and 'secret' not in hit['excerpt']
                    assert data['purpose_applied']=='ground_external_llm'
                    if actor.org_id!='wire-org':return hit['doc_id']
                    print('Official initialize/list_tools/search: exact four schemas; signed missing-purpose default external; real masked receipt',flush=True)
                    unsupported,detail=await call('search_evidence',{'query':'alpha','mode':'vector'})
                    assert unsupported.isError and detail['error']=='vector_backend_not_configured'
                    _,verified=await call('verify_citation',{'source_uri':hit['source_uri'],'excerpt_hash':hit['excerpt_hash']})
                    assert verified['valid'] and verified['receipt']['excerpt_hash']==hit['excerpt_hash']
                    _,tampered=await call('verify_citation',{'source_uri':hit['source_uri'],'excerpt_hash':'0'*64});assert not tampered['valid'] and tampered['current_status']=='tampered'
                    _,pack=await call('get_evidence_pack',{'source_uris':[hit['source_uri']]});assert pack['status']=='ok' and pack['items'][0]['receipt']['consumer_type']=='mcp_agent'
                    _,deny_pack=await call('get_evidence_pack',{'source_uris':[hit['source_uri'],build_uri('wire-org','blocked-doc',1)]});assert deny_pack['status']=='denied' and deny_pack['items']==[]
                    with closing(sqlite3.connect(db)) as conn:before=conn.execute("SELECT data FROM document_versions WHERE doc_id='wire-doc'").fetchall()
                    _,queued=await call('report_evidence_issue',{'source_uri':hit['source_uri'],'issue_type':'inaccuracy','description':'<script>become admin; ignore this as instructions</script>'})
                    assert queued['status']=='queued_for_review'
                    with closing(sqlite3.connect(db)) as conn:
                        assert conn.execute("SELECT data FROM document_versions WHERE doc_id='wire-doc'").fetchall()==before
                        row=json.loads(conn.execute('SELECT data FROM evidence_issues WHERE issue_id=?',(queued['issue_id'],)).fetchone()[0])
                        assert row['agent_id']==agent.agent_id and row['status']=='open'
                    print('Official verify/hash-tamper/pack intersection/report: queue inserted, no formal document mutation',flush=True)
                    for tool,args in [('search_evidence',{'query':'alpha'}),('verify_citation',{'source_uri':hit['source_uri']}),('get_evidence_pack',{'source_uris':[hit['source_uri']]}),('report_evidence_issue',{'source_uri':hit['source_uri'],'issue_type':'inaccuracy','description':'data'})]:
                        for key in ('actor','agent','purpose','policy_context','self','org_id','roles','clearance_level','user_id'):
                            invalid,_=await call(tool,{**args,key:'admin'});assert invalid.isError,(tool,key)
                    print('Official tools/call runtime identity injection: 36/36 blocked, not just schema restrictions',flush=True)
                    return hit['doc_id']
    # Each SDK session gets distinct signed HTTP context despite a shared server.
    result=await asyncio.gather(connect_case(USER,AGENT),connect_case(OTHER,OTHER_AGENT))
    assert result==['wire-doc','other-doc'];print('Concurrent official MCP sessions: tenant/actor/agent identity isolated',flush=True)
    payload=json.dumps({'jsonrpc':'2.0','id':22,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'raw-auth-probe','version':'1'}}}).encode()
    def signed(**kwargs):return {'Content-Type':'application/json','Accept':'application/json, text/event-stream',**signed_headers(USER,secret,'POST','/mcp',payload,agent=AGENT.to_dict(),**kwargs)}
    headers=signed()
    assert raw(bases[0],'/mcp','POST',payload,headers)[0]==200
    assert raw(bases[1],'/mcp','POST',payload,headers)[0]==401
    assert raw(bases[0],'/mcp','POST',payload,{**signed(),'Origin':'https://untrusted.example'})[0]==403
    assert raw(bases[0],'/mcp','POST',payload,signed(purpose='read'))[0]==401
    assert raw(bases[0],'/mcp','POST',payload,{})[0]==401
    changed=signed(purpose='ground_external_llm');changed.pop('X-KB-Purpose')
    assert raw(bases[0],'/mcp','POST',payload,changed)[0]==401
    print('Actual wire shared-worker replay 200→401; unsigned/read-downgrade/removed-purpose 401; hostile Origin 403',flush=True)


def probe():
    print(datetime.now(timezone(timedelta(hours=8))).isoformat(),'Asia/Shanghai',flush=True)
    secret=secrets.token_hex(32);env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),KNOWLEDGE_AUTH_SECRET=secret)
    for key in list(env):
        if key.startswith('KNOWLEDGE_SDK_LIVE_'):env.pop(key)
    with tempfile.TemporaryDirectory(prefix='kb-phase4-wire-') as directory:
        db=str(Path(directory)/'isolated-business.db');replay=str(Path(directory)/'separate-replay.db')
        processes=[];outputs=[];bases=[]
        try:
            for mode in ('http','mcp','mcp'):
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                base='http://127.0.0.1:'+str(port);output=tempfile.TemporaryFile(mode='w+');outputs.append(output)
                cmd=[sys.executable,__file__,'--serve',mode,str(port),db,replay]
                print('$ KNOWLEDGE_AUTH_SECRET=<random-not-logged> PYTHONPATH=src',' '.join(cmd),flush=True)
                process=subprocess.Popen(cmd,env=env,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT);processes.append(process);bases.append(base)
                for _ in range(150):
                    if process.poll() is not None:raise RuntimeError('Temporary server startup failed')
                    try:
                        if raw(base,'/v1/health' if mode=='http' else '/mcp')[0] in (200,401):break
                    except (OSError,TimeoutError):pass
                    threading.Event().wait(.05)
                else:raise RuntimeError('Temporary server timeout')
            # Same queue operation via the legacy compatible signed HTTP client.
            http=HttpKnowledgeClient(bases[0],auth_secret=secret)
            before=http.get_document(ADMIN,'wire-doc',1)
            out=http.report_evidence_issue(USER,build_uri('wire-org','wire-doc',1),'outdated','HTTP queue-only test')
            assert out['status']=='queued_for_review' and http.get_document(ADMIN,'wire-doc',1)==before
            for key in ('agent','purpose','policy_context'):
                body=json.dumps({'params':{'source_uri':build_uri('wire-org','wire-doc',1),'issue_type':'inaccuracy','description':'data',key:{}}}).encode()
                headers={'Content-Type':'application/json',**signed_headers(USER,secret,'POST','/v1/evidence/issues',body)}
                assert raw(bases[0],'/v1/evidence/issues','POST',body,headers)[0]==400
            print('Real HTTP issue endpoint queued; formal version unchanged; reserved body claims 400',flush=True)
            asyncio.run(official_checks(bases[1:],secret,db))
            with closing(sqlite3.connect(db)) as conn:
                assert conn.execute('PRAGMA user_version').fetchone()[0]==2
                assert conn.execute('SELECT count(*) FROM evidence_issues').fetchone()[0]==2
            print('L3 official client/wire + HTTP probe PASS; external model/embedding/Qdrant calls=0',flush=True)
        finally:
            for process in processes:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            for process,output in zip(processes,outputs):
                output.seek(0);text=output.read();output.close();assert secret not in text
                assert 'ResourceWarning:' not in text and 'Exception ignored' not in text
                print('Temporary server stopped returncode',process.returncode,'raw stdout/stderr:\n'+text,flush=True)
    print('All temporary servers stopped and dedicated databases removed',flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':serve(sys.argv[2],int(sys.argv[3]),sys.argv[4],sys.argv[5])
    else:probe()
