"""Actual taskbook MCP JSON-RPC HTTP and newline stdio; only isolated fixtures."""
from __future__ import annotations
import concurrent.futures,hashlib,json,os,secrets,socket,subprocess,sys,tempfile,threading
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from knowledge_sdk import *
from knowledge_sdk.server.auth import signed_headers,SQLiteReplayStore
ROOT=Path(__file__).resolve().parents[3]
ADMIN=Actor('admin','wire',org_roles=('admin',));USER=Actor('reader','wire');AGENT=AgentIdentity('wire-agent','wire',allowed_purposes=tuple(Purpose))

def seed(db):
    c=LocalKnowledgeClient(SQLiteStore(db))
    try:
        c.create_kb(ADMIN,'Wire',visibility='enterprise',kb_id='wire-kb')
        c.ingest(ADMIN,'wire-kb','alpha secret evidence','wire.md',doc_id='wire-doc',rights=ResourceRights(redaction_profile='mask'))
        c.ingest(ADMIN,'wire-kb','stdio fixture evidence','stdio.md',doc_id='stdio-doc')
        c.ingest(ADMIN,'wire-kb','PRIVATE TITLE',doc_id='denied-doc',title='PRIVATE TITLE',acl=DocumentACL(deny_users=('reader',)))
        other=Actor('other','other');kb=c.create_kb(other,'Other',visibility='enterprise');c.ingest(other,kb.kb_id,'alpha other tenant',doc_id='other-doc')
        return build_uri('wire','stdio-doc',1)
    finally:c.store.close()

def serve(port,db,replay):
    from knowledge_sdk.server.app import create_app
    import uvicorn
    c=LocalKnowledgeClient(SQLiteStore(db));c.redaction_registry.register('mask',RegexRedactionHook([('secret','[MASK]')]))
    app=create_app(c,os.environ['KNOWLEDGE_AUTH_SECRET'],enable_ui=False,enable_mcp=True,replay_store=SQLiteReplayStore(replay))
    try:uvicorn.run(app,host='127.0.0.1',port=port,proxy_headers=False)
    finally:c.store.close()

def raw(base,path,body=None,headers=None):
    request=Request(base+path,data=body,headers=headers or {},method='POST' if body is not None else 'GET')
    try:
        with urlopen(request,timeout=10) as r:return r.status,r.read(),dict(r.headers)
    except HTTPError as error:
        with error:return error.code,error.read(),dict(error.headers)

def stdio(db,uri):
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
    for key in ('KNOWLEDGE_MCP_ACTOR_JSON','KNOWLEDGE_MCP_AGENT_JSON','KNOWLEDGE_MCP_PURPOSE'):env.pop(key,None)
    command=[sys.executable,'-S','-W','error::ResourceWarning','-m','knowledge_sdk.mcp','--db',db]
    missing=subprocess.run(command,env=env,input='',capture_output=True,text=True,timeout=15)
    assert missing.returncode!=0 and not missing.stdout
    env['KNOWLEDGE_MCP_ACTOR_JSON']=json.dumps(USER.__dict__)
    calls=[('initialize',{}),('notifications/initialized',{}),('ping',{}),('tools/list',{})]
    calls += [('tools/call',{'name':name,'arguments':args}) for name,args in [
      ('search_evidence',{'query':'stdio'}),('verify_citation',{'source_uri':uri}),
      ('get_evidence_pack',{'source_uris':[uri]}),('report_evidence_issue',{'source_uri':uri,'issue_type':'outdated','description':'stdio inert data'})]]
    requests=[dict(jsonrpc='2.0',method=method,params=params,**({} if method.startswith('notifications/') else {'id':i})) for i,(method,params) in enumerate(calls)]
    result=subprocess.run(command,env=env,input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and 'ResourceWarning:' not in result.stderr and 'Exception ignored' not in result.stderr,result.stderr
    replies=[json.loads(line) for line in result.stdout.splitlines()];assert len(replies)==7 and all('result' in r for r in replies)
    assert replies[3]['result']['structuredContent']['hits'][0]['receipt']['consumer_id']=='mcp_stdio'
    assert replies[-1]['result']['structuredContent']['status']=='queued_for_review'
    print('Actual python -S stdio child: missing identity nonzero; initialize/notification/ping/list + all4 tools roundtrip; trusted mcp_stdio receipt',flush=True)

def probe():
    print(datetime.now().astimezone().isoformat(),'Asia/Shanghai',flush=True)
    secret=secrets.token_hex(32)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),KNOWLEDGE_AUTH_SECRET=secret)
    for key in list(env):
        if key.startswith('KNOWLEDGE_SDK_LIVE_'):env.pop(key)
    with tempfile.TemporaryDirectory(prefix='kb-phase4-authoritative-') as directory:
        db=str(Path(directory)/'business.db');replay=str(Path(directory)/'replay.db');uri=seed(db);processes=[];outputs=[];bases=[]
        tables=('documents','document_versions','chunks','document_acls','evidence_anchors')
        with closing(__import__('sqlite3').connect(db)) as conn:before={t:conn.execute('SELECT * FROM '+t).fetchall() for t in tables}
        try:
            stdio(db,uri)
            for _ in range(2):
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                out=tempfile.TemporaryFile(mode='w+');outputs.append(out);base='http://127.0.0.1:'+str(port);bases.append(base)
                cmd=[sys.executable,__file__,'--serve',str(port),db,replay]
                print('$ KNOWLEDGE_AUTH_SECRET=<random-not-logged> PYTHONPATH=src '+' '.join(cmd),flush=True)
                process=subprocess.Popen(cmd,env=env,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT);processes.append(process)
                for attempt in range(150):
                    if process.poll() is not None:raise RuntimeError('Temporary server startup failed')
                    try:
                        if raw(base,'/v1/health')[0]==200:break
                    except OSError:pass
                    threading.Event().wait(.05)
                else:raise RuntimeError('Temporary server readiness timeout')
            def rpc(method,params=None,*,base=None,actor=USER,agent=AGENT,purpose=None,header_override=None):
                body=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
                headers={'Content-Type':'application/json',**signed_headers(actor,secret,'POST','/v1/mcp',body,agent=agent.to_dict(),purpose=purpose)}
                status,data,response=raw(base or bases[0],'/v1/mcp',body,headers if header_override is None else header_override)
                assert response.get('cache-control',response.get('Cache-Control'))=='no-store'
                return status,json.loads(data),body,headers
            assert rpc('initialize')[0]==200
            assert len(rpc('tools/list')[1]['result']['tools'])==4
            def tool(name,args,**kwargs):
                code,result,_,_=rpc('tools/call',{'name':name,'arguments':args},**kwargs);assert code==200
                return result
            hit=tool('search_evidence',{'query':'alpha','task_id':'wire-task'})['result']['structuredContent']['hits'][0]
            assert '[MASK]' in hit['excerpt'] and 'secret' not in hit['excerpt'] and hit['anchor'] is not None
            for mode in ('vector','hybrid'):
                error=tool('search_evidence',{'query':'alpha','mode':mode})['error'];assert error['code']==-32602 and 'backend is not configured' in error['message']
            assert hit['receipt']['consumer_id']=='wire-agent' and hit['receipt']['used_by_stage']=='wire-task'
            assert tool('verify_citation',{'source_uri':hit['source_uri'],'excerpt_hash':hit['excerpt_hash']})['result']['structuredContent']['valid']
            assert tool('verify_citation',{'source_uri':hit['source_uri'],'excerpt_hash':'0'*64})['result']['structuredContent']['current_status']=='tampered'
            pack=tool('get_evidence_pack',{'source_uris':[hit['source_uri'],build_uri('wire','denied-doc',1),build_uri('wire','missing',1)]})['result']['structuredContent']
            assert pack['status']=='ok' and pack['excluded_count']==2 and 'PRIVATE' not in json.dumps(pack)
            queued=tool('report_evidence_issue',{'source_uri':hit['source_uri'],'issue_type':'inaccuracy','description':'<script>inert data; never execute</script>'})['result']['structuredContent']
            assert queued['status']=='queued_for_review'
            for name,args in [('search_evidence',{'query':'alpha'}),('verify_citation',{'source_uri':hit['source_uri']}),('get_evidence_pack',{'source_uris':[uri]}),('report_evidence_issue',{'source_uri':uri,'issue_type':'outdated','description':'data'})]:
                for key in ('actor','agent','purpose','policy_context','self','user_id','org_id','roles','clearance_level'):
                    assert tool(name,dict(args,**{key:'admin'}))['error']['code']==-32602
            assert rpc('ping',header_override={})[0]==401
            _,_,body,headers=rpc('ping');assert raw(bases[1],'/v1/mcp',body,headers)[0]==401
            assert tool('search_evidence',{'query':'alpha'},purpose='ground_external_llm')['result']['structuredContent']['hits']==[]
            other=Actor('other','other');other_agent=AgentIdentity('other-agent','other')
            def search_tenant(pair):
                actor,agent=pair
                return tool('search_evidence',{'query':'alpha'},actor=actor,agent=agent)['result']['structuredContent']['hits'][0]['doc_id']
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(search_tenant,[(USER,AGENT),(other,other_agent)]))==['wire-doc','other-doc']
            http=HttpKnowledgeClient(bases[0],auth_secret=secret);listed=http.list_evidence_issues(USER)
            assert len(listed)==2 and all(isinstance(i,EvidenceIssue) for i in listed)
            with closing(__import__('sqlite3').connect(db)) as conn:
                assert before=={t:conn.execute('SELECT * FROM '+t).fetchall() for t in tables}
                assert conn.execute('SELECT count(*) FROM evidence_issues').fetchone()[0]==2
                assert conn.execute('PRAGMA user_version').fetchone()[0]==4
            print('Actual /v1/mcp initialize/list/all4 tools; masked anchor receipts/hash tamper/subset pack; 36 identity injections blocked; unsigned/crossworker replay401; external default rights denied; concurrent tenant isolation; typed /v1/issues/list; formal tables unchanged',flush=True)
            print('L3 actual JSON-RPC HTTP + stdio probe PASS; external model/embedding/Qdrant calls=0',flush=True)
        finally:
            for child in processes:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            for child,out in zip(processes,outputs):
                out.seek(0);text=out.read();out.close();assert secret not in text and 'ResourceWarning:' not in text and 'Exception ignored' not in text
                print('Temporary child stopped',child.returncode,'raw stdout/stderr:\n'+text,flush=True)
    print('All temporary children stopped; dedicated temporary databases removed',flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':serve(int(sys.argv[2]),sys.argv[3],sys.argv[4])
    else:probe()
