"""Real, isolated loopback Phase 2 probe. No external model/vector calls."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from knowledge_sdk import (Actor,AgentIdentity,Purpose,ResourceRights,LocalKnowledgeClient,
                           HttpKnowledgeClient,SQLiteStore,RedactionRegistry,RegexRedactionHook,
                           GeneratedAnswer,KnowledgeScope,PermissionDeniedError)
from knowledge_sdk.contracts.models import encode
from knowledge_sdk.server.auth import signed_headers,SQLiteReplayStore
ROOT=Path(__file__).resolve().parents[3]
ADMIN=Actor('admin','probe-org',org_roles=('admin',))
USER=Actor('user','probe-org')


def serve(port,replay_path):
    import uvicorn
    from knowledge_sdk.server.app import create_app
    client=LocalKnowledgeClient(SQLiteStore(':memory:'))
    for kb_id in ('kb-a','kb-b'):
        client.create_kb(ADMIN,kb_id,kb_id=kb_id,space_type='enterprise_public')
    client.ingest(ADMIN,'kb-a','alpha public evidence',doc_id='doc-a')
    client.ingest(ADMIN,'kb-b','beta sensitive 123-45-6789',doc_id='doc-b')
    old=client.reference(USER,'doc-b',excerpt='beta')
    client.ingest(ADMIN,'kb-b','gamma restricted 123-45-6789',doc_id='doc-missing')
    client.redaction_registry.register('pii',RegexRedactionHook([('123-45-6789','[MASK]')]))
    client.set_document_rights(ADMIN,'doc-b',ResourceRights(redaction_profile='pii'))
    client.set_document_rights(ADMIN,'doc-missing',ResourceRights(redaction_profile='missing'))
    class Stub:
        calls=0
        def generate(self,question,hits,scope,actor):
            self.calls+=1
            return GeneratedAnswer(' '.join(h.excerpt for h in hits),False)
    stub=Stub()
    app=create_app(client,auth_secret=os.environ['KNOWLEDGE_AUTH_SECRET'],answer_generator=stub,
                   replay_store=SQLiteReplayStore(replay_path),ui_prefix='/kb/ui')
    @app.get('/v1/probe-counters')
    async def counters():return {'offline_stub_calls':stub.calls,'real_model_calls':0}
    try:uvicorn.run(app,host='127.0.0.1',port=port,proxy_headers=False)
    finally:client.store.close()


def probe():
    secret=secrets.token_hex(32)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),KNOWLEDGE_AUTH_SECRET=secret)
    for name in list(env):
        if name.startswith('KNOWLEDGE_SDK_LIVE_'):env.pop(name)
    with tempfile.TemporaryDirectory(prefix='kb-phase2-live-') as directory:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base='http://127.0.0.1:'+str(port)
        command=[sys.executable,__file__,'--serve',str(port),str(Path(directory)/'replay.sqlite3')]
        print('$ PYTHONPATH=src KNOWLEDGE_AUTH_SECRET=<random,not logged>',' '.join(command),flush=True)
        with tempfile.TemporaryFile(mode='w+') as output:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
            def raw(path,method='GET',body=b'',headers=None):
                try:
                    req=urllib.request.Request(base+path,data=body if method!='GET' else None,method=method,headers=headers or {})
                    with urllib.request.urlopen(req,timeout=2) as r:return r.status,r.read(),r.headers
                except urllib.error.HTTPError as error:
                    try:return error.code,error.read(),error.headers
                    finally:error.close()
            def signed(path,method='GET',body=b'',agent=None,purpose=None):
                headers=signed_headers(USER,secret,method,path,body,agent=agent,purpose=purpose)
                return raw(path,method,body,{'Content-Type':'application/json',**headers})
            def counters():return json.loads(signed('/v1/probe-counters')[1])
            client=HttpKnowledgeClient(base,auth_secret=secret)
            try:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError('Probe server startup failed')
                    try:
                        if raw('/v1/health')[0]==200:break
                    except (OSError,TimeoutError):pass
                    threading.Event().wait(0.05)
                else:raise RuntimeError('Probe startup timeout')
                assert client.health()['version']=='1.2.0'
                for path in ('/kb/ui','/kb/ui/config','/kb/ui/assets/i18n.js'):
                    status,_,headers=raw(path);assert status==200
                    assert headers['Cache-Control']=='no-store'
                    print('GET',path,status,'no-store')
                assert raw('/v1/kbs')[0]==401;print('Unsigned business GET /v1/kbs 401')
                for path in ('/ui/demo/sign','/kb/ui/demo/sign'):
                    assert raw(path,'POST',headers={'X-KB-Demo':'1'})[0]==404
                    print('POST',path,'404 (production signer disabled)')
                try:client.retrieve(USER,'doc-a',purpose=Purpose.GROUND_EXTERNAL_LLM)
                except PermissionDeniedError as error:assert str(error)=='external_llm_prohibited'
                else:raise AssertionError('External purpose silently allowed')
                print('Signed external purpose default rights -> 403 external_llm_prohibited')
                rights=ResourceRights(allowed_purposes=(Purpose.READ,Purpose.GROUND_INTERNAL_LLM,Purpose.GROUND_EXTERNAL_LLM),allow_external_llm=True)
                client.set_document_rights(ADMIN,'doc-a',rights)
                assert client.retrieve(USER,'doc-a',purpose=Purpose.GROUND_EXTERNAL_LLM).text=='alpha public evidence'
                print('Explicit admin rights update -> signed external retrieve 200 (no generation)')
                agent=AgentIdentity('probe','probe-org',allowed_kb_ids=('kb-a',))
                try:client.retrieve(USER,'doc-b',agent=agent)
                except PermissionDeniedError as error:assert str(error)=='agent_scope_denied'
                else:raise AssertionError('Agent scope bypass')
                assert not client.search(USER,'beta',agent=agent).hits
                print('Signed AgentIdentity kb-a restriction -> doc-b 403 / beta search empty')
                hit=client.search(USER,'beta').hits[0]
                assert '123-45-6789' not in hit.excerpt and '[MASK]' in hit.excerpt
                assert hit.excerpt_hash==hashlib.sha256(hit.excerpt.encode()).hexdigest()
                assert 'pii:replacements=1' in hit.masking_summary
                print('Actual masked HTTP search:',hit.excerpt,'hash='+hit.excerpt_hash,'summary='+hit.masking_summary)
                for result in (client.retrieve(USER,'doc-b'),client.inspect_document(USER,'doc-b'),client.get_document(USER,'doc-b',1)):
                    assert '123-45-6789' not in json.dumps(encode(result))
                print('Retrieve / inspection / version GET delivery contain no source token')
                ref=client.reference(USER,'doc-b',excerpt=hit.excerpt)
                receipt=client.consume(USER,ref)
                assert receipt.status in ('partial','consumed') and receipt.excerpt_hash==hit.excerpt_hash
                print('Masked reference/receipt:',receipt.status,'hash matches delivered content')
                before=counters()['offline_stub_calls']
                answer=client.ask(USER,'beta')
                assert answer.status=='answered' and '[MASK]' in answer.answer and '123-45-6789' not in answer.answer
                assert counters()['offline_stub_calls']==before+1
                print('Explicit ask -> offline stub received masked evidence only; real model calls 0')
                before=counters()['offline_stub_calls']
                assert not client.search(USER,'gamma').hits
                try:client.retrieve(USER,'doc-missing')
                except PermissionDeniedError as error:assert str(error)=='redaction_hook_missing'
                else:raise AssertionError('Missing hook fallback')
                denied=client.ask(USER,'gamma')
                assert denied.status=='refused' and not denied.model_called
                assert counters()['offline_stub_calls']==before
                print('Missing hook -> search empty, retrieve 403, ask refused, zero added stub/model calls')
                for field,value in (('purpose','export'),('agent',{}),('policy_context',{})):
                    body=json.dumps({'params':{'doc_id':'doc-a',field:value}}).encode()
                    assert signed('/v1/retrieve','POST',body)[0]==400
                    print('Signed body injection',field,'-> 400')
                body=json.dumps({'params':{'doc_id':'doc-a'}}).encode()
                assert signed('/v1/retrieve','POST',body,agent={'agent_id':'a','org_id':'probe-org','unknown':True})[0]==401
                print('Signed invalid typed agent unknown field -> 401')
                assert counters()['real_model_calls']==0
                print('L3 isolated real HTTP policy/redaction probe PASS')
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                output.seek(0);server_output=output.read()
                assert secret not in server_output,'Random signing secret leaked'
                print('Probe server stopped; returncode',process.returncode)
                print('Raw server stdout/stderr (no signing secrets):\n'+server_output)
    print('Temporary dedicated replay DB removed; no persistent services or collections touched')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':serve(int(sys.argv[2]),sys.argv[3])
    else:probe()
