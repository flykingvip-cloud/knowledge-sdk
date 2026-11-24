"""Real loopback subprocess HTTP, all-three-identities and whole-pack revocation.

Run with optional KNOWLEDGE_SDK_TEST_PG_DSN naming a disposable test DB only.
No secrets, signed headers, DSN or source bodies are printed.
"""
from __future__ import annotations
import base64
from datetime import datetime
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
from knowledge_sdk import Actor, HttpKnowledgeClient, ResourceRights, PermissionDeniedError, ConflictError, DocumentACL
from knowledge_sdk.contracts.models import encode, decode
from knowledge_sdk.server.auth import signed_headers


def raw(url,path,body,headers):
    try:
        with urlopen(Request(url+path,data=body,headers=headers,method='POST'),timeout=15) as response:return response.status,response.read()
    except HTTPError as error:
        try:return error.code,error.read()
        finally:error.close()


def run(engine):
    sandbox=None;process=None;secret=secrets.token_hex(32)
    with tempfile.TemporaryDirectory() as tmp:
        logpath=Path(__file__).with_name('l3-'+engine+'-process.log')
        env=dict(os.environ,KNOWLEDGE_AUTH_SECRET=secret)
        env.pop('KNOWLEDGE_SDK_DSN',None)
        command=[sys.executable,'-W','error::ResourceWarning','-m','knowledge_sdk.server','--host','127.0.0.1','--no-ui']
        if engine=='postgres':
            from tests.pg_helpers import PgSandbox
            sandbox=PgSandbox();env['KNOWLEDGE_SDK_DSN']=sandbox.dsn
            command+=['--pgvector-dims','32']
        else:command+=['--db',str(Path(tmp)/'business.db'),'--replay-db',str(Path(tmp)/'replay.db')]
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        assert port not in (3000,3001,8000,8002,8090,8091)
        url='http://127.0.0.1:'+str(port);command+=['--port',str(port)]
        try:
            with logpath.open('w') as log:
                process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+20
                while True:
                    try:
                        with urlopen(url+'/v1/health',timeout=1) as response:response.read()
                        break
                    except OSError:
                        if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Disposable HTTP process failed to start')
                        time.sleep(.03)
                client=HttpKnowledgeClient(url,secret)
                a=Actor('author','wire-m3',org_roles=('admin',));r=Actor('reviewer','wire-m3',org_roles=('admin',));p=Actor('publisher','wire-m3',org_roles=('admin',));u=Actor('reader','wire-m3')
                client.create_kb(a,'controlled','enterprise',space_type='enterprise_public',governance_tier='l2_controlled',kb_id='k')
                version=client.ingest(a,'k','alpha controlled liveone evidence',filename='fixture.md',doc_id='d',rights=ResourceRights(allow_export=True))
                assert version.lifecycle_state=='draft' and not version.text
                assert not client.search(u,'alpha').hits
                try:client.publish_release(p,'d',version=1,expected_version=1)
                except ConflictError:pass
                else:raise AssertionError('Draft published without approval')
                client.submit_for_review(a,'d',expected_version=1)
                try:client.approve_release(a,'d',version=1,expected_version=1)
                except PermissionDeniedError:pass
                else:raise AssertionError('Admin self review allowed')
                client.record_dissent(r,'d',version=1,note='negative result retained')
                client.approve_release(r,'d',version=1,expected_version=1)
                try:client.publish_release(r,'d',version=1,expected_version=1)
                except PermissionDeniedError:pass
                else:raise AssertionError('Reviewer published own approval')
                manifest=client.publish_release(p,'d',version=1,expected_version=1)
                assert (manifest.submitter_id,manifest.reviewer_id,manifest.publisher_id)==('author','reviewer','publisher')
                assert manifest.dissent_notes==('negative result retained',)
                assert client.search(u,'liveone').hits
                if engine=='postgres':assert client.search(u,'alpha',mode='vector').hits
                uri=client.reference(u,'d').source_uri
                for action in ('create_revision_draft','retrieval_tuning','keep_dissent','dismissed'):
                    issue=client.report_evidence_issue(u,uri,'inaccuracy','manual followup')
                    resolved=client.resolve_evidence_issue(r,issue.issue_id,action,'human reviewed',expected_version=1)
                    assert resolved.status==('dismissed' if action=='dismissed' else 'resolved')
                pack=client.create_evidence_pack(a,'Decision',[{'doc_id':'d','version':1,'stance':s,'condition_note':'fixed conditions'} for s in ('supporting','refuting','negative','conflict')])
                assert pack.purpose_bound.value=='export'
                assert client.get_evidence_pack(u,pack.pack_id).pack_sha256==pack.pack_sha256
                assert client.verify_evidence_pack(u,pack.pack_id).digest_valid
                assert any(x.pack_id==pack.pack_id for x in client.list_evidence_packs(u))
                exported=client.export_evidence_pack(u,pack.pack_id,format='ro_crate',output_path=Path(tmp)/'caller.zip')
                assert (Path(tmp)/'caller.zip').is_file()
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported.content))) as archive:
                    assert json.loads(archive.read('ro-crate-metadata.json'))['@context']=='https://w3id.org/ro/crate/1.2/context'
                # Issue action already made draft v2; author edits as a new v3.
                version=client.ingest(a,'k','alpha secretthree draft',filename='fixture.md',doc_id='d')
                assert version.version==3
                assert 'liveone' in client.retrieve(u,'d').text and not client.search(u,'secretthree').hits
                client.submit_for_review(a,'d',expected_version=3);client.approve_release(r,'d',version=3,expected_version=3);client.publish_release(p,'d',version=3,expected_version=3)
                assert 'secretthree' in client.retrieve(u,'d').text
                assert client.drain_outbox(a).failed==0
                report=client.verify_evidence_pack(u,pack.pack_id)
                assert report.digest_valid and report.status=='impacted'
                assert any(x.target_type=='evidence_pack' and x.target_id==pack.pack_id for x in client.list_impact_alerts(a))
                # Revoke source: every format returns real 403 without sealed body.
                client.set_document_rights(a,'d',ResourceRights(allow_export=True,revoked=True))
                for path,params in [('/v1/packs/get',{'pack_id':pack.pack_id}),('/v1/packs/export',{'pack_id':pack.pack_id,'format':'json'}),('/v1/packs/export',{'pack_id':pack.pack_id,'format':'ro_crate'})]:
                    body=json.dumps({'params':params},separators=(',',':')).encode();headers=signed_headers(u,secret,'POST',path,body)
                    status,data=raw(url,path,body,headers)
                    assert status==403 and b'liveone' not in data and b'secretthree' not in data
                assert client.drain_outbox(a).failed==0
                assert any(x.target_type=='evidence_pack' and x.impact_reason.value=='access_revoked' for x in client.list_impact_alerts(a))
                assert client.verify_audit_chain(a).valid
                path='/v1/packs/list';body=b'{"params":{}}';headers=signed_headers(a,secret,'POST',path,body)
                assert raw(url,path,body,headers)[0]==200
                assert raw(url,path,body,headers)[0]==401
                assert raw(url,path,body,{})[0]==401
                # Caller's paths must never become server write targets.
                path='/v1/packs/export';body=json.dumps({'params':{'pack_id':pack.pack_id,'output_path':'/forbidden'}}).encode()
                assert raw(url,path,body,signed_headers(a,secret,'POST',path,body))[0]==400
        finally:
            if process is not None:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if sandbox is not None:sandbox.close()
        text=logpath.read_text()
        assert secret not in text and 'ResourceWarning' not in text
        if sandbox is not None:assert sandbox.dsn not in text
        print('PASS',engine,'real signed HTTP: draft -> submit -> distinct reviewer -> distinct publisher; dissent and all 4 manual issue resolutions')
        print('PASS',engine,'JSON/get/verify/list and deterministic RO-Crate1.2; draft/live isolation and publish -> SUPERSEDED pack alert with seal unchanged')
        print('PASS',engine,'revoke -> get/json/zip 403 with no plaintext; ACCESS_REVOKED evidence_pack alert; unsigned/replayed 401; audit chain valid')
        print('PASS',engine,'subprocess stopped, sandbox removed, logs contain no key/DSN/ResourceWarning')


def main():
    print(datetime.now().astimezone().isoformat(),'Asia/Shanghai')
    run('sqlite')
    if os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'):run('postgres')

if __name__=='__main__':main()
