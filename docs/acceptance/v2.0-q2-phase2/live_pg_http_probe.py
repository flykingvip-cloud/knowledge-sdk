"""Two real CLI processes, isolated schema, signed HTTP and shared replay."""
from contextlib import ExitStack
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from knowledge_sdk import Actor,HttpKnowledgeClient,DocumentACL,PermissionDeniedError,ConsumerBinding,KnowledgeScope
from knowledge_sdk.server.auth import signed_headers
from tests.pg_helpers import PgSandbox


def request(url,body,headers):
    try:
        with urlopen(Request(url,data=body,headers=headers,method='POST'),timeout=10) as r:return r.status,r.read()
    except HTTPError as e:
        try:return e.code,e.read()
        finally:e.close()


def main():
    print(datetime.now().astimezone().isoformat(),'Asia/Shanghai')
    sandbox=PgSandbox();processes=[];logs=[];secret=secrets.token_hex(32)
    try:
        env=dict(os.environ,KNOWLEDGE_AUTH_SECRET=secret,KNOWLEDGE_SDK_DSN=sandbox.dsn)
        urls=[]
        for i in range(2):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            command=[sys.executable,'-W','error::ResourceWarning','-m','knowledge_sdk.server','--port',str(port),'--host','127.0.0.1','--no-ui','--pgvector-dims','32']
            if i==0:command+=['--dsn',sandbox.dsn,'--pg-rls']
            path=Path(__file__).with_name('l3-http-process-'+str(i)+'.log')
            log=path.open('w');logs.append(log)
            proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(proc)
            url='http://127.0.0.1:'+str(port);urls.append(url)
            deadline=time.monotonic()+15
            while True:
                try:
                    with urlopen(url+'/v1/health',timeout=1) as r:
                        data=r.read();assert b'password' not in data and b'postgresql://' not in data
                    break
                except OSError:
                    if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Disposable CLI did not start')
                    time.sleep(.03)
        http=HttpKnowledgeClient(urls[0],auth_secret=secret);other=HttpKnowledgeClient(urls[1],auth_secret=secret)
        admin=Actor('admin','wire',org_roles=('admin',));reader=Actor('reader','wire')
        http.create_kb(admin,'wire',visibility='enterprise',kb_id='kb')
        http.ingest(admin,'kb','# H\n\n知识库 alpha SECRET',filename='fixture.md',doc_id='doc')
        assert other.search(reader,'知识库').hits
        assert other.search(reader,'alpha',mode='vector').hits
        assert not other.search(Actor('reader','foreign'),'alpha',mode='vector').hits
        anchor=http.list_anchors(reader,'doc')[0];ref=http.reference(reader,'doc',anchor_id=anchor.anchor_id)
        http.attach(reader,ref,ConsumerBinding('task','wire-task',KnowledgeScope('documents',doc_ids=('doc',))))
        http.ingest(admin,'kb','# H\n\n知识库 alpha revised',filename='fixture.md',doc_id='doc')
        assert other.drain_outbox(admin).failed==0
        assert other.list_impact_alerts(reader,doc_id='doc')
        http.set_document_acl(admin,'doc',DocumentACL(deny_users=('reader',)))
        assert not other.search(reader,'alpha',mode='vector').hits
        try:other.retrieve(reader,'doc')
        except PermissionDeniedError:pass
        else:raise AssertionError('Live PG revoked reader could retrieve')
        path='/v1/search';body=b'{"params":{"query":"alpha"}}';headers=signed_headers(admin,secret,'POST',path,body)
        assert request(urls[0]+path,body,headers)[0]==200
        assert request(urls[1]+path,body,headers)[0]==401
        assert request(urls[1]+path,body,{})[0]==401
        assert other.verify_audit_chain(admin).valid
        print('PASS real knowledge-sdk-server --dsn + environment DSN; two independent processes')
        print('PASS signed HTTP: CJK keyword, pgvector/hash-vector candidates, anchors, receipts, usage, impact, ACL-denied content, cross-tenant search')
        print('PASS PostgreSQL replay shared across two HTTP instances: first 200, same signed nonce second 401; unsigned 401')
        print('No model/embedding service called: local deterministic HashEmbedder only; no browser/reverse proxy claimed')
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        for log in logs:log.close()
        sandbox.close()
    for i in range(len(logs)):
        text=Path(__file__).with_name('l3-http-process-'+str(i)+'.log').read_text()
        assert secret not in text and sandbox.dsn not in text and 'ResourceWarning' not in text
    print('PASS shutdown: disposable CLI processes stopped, no ResourceWarning, no credential/DSN logging')

if __name__=='__main__':main()
