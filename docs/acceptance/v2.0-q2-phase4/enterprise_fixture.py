"""Disposable test-keys-only enterprise fixture. Never a production identity provider.

Used by the real wire probe and manually supervised browser acceptance. No token,
private key, cookie or DSN is logged. Token files are mode 0600 outside the repo.
"""
from __future__ import annotations
import argparse,base64,json,os,secrets,time,uuid
from pathlib import Path
from knowledge_sdk import Actor,LocalKnowledgeClient,ResourceRights
from knowledge_sdk.contracts.identity import IdentityPrincipal
from knowledge_sdk.connectors import ControlledFilesystemConnector,WebhookSyncConnector
from knowledge_sdk.server.oidc import OIDCAuthenticator
from knowledge_sdk.server.app import create_app
from knowledge_sdk.server.auth import InMemoryReplayStore

ISSUER='https://isolated-m4-test-issuer.invalid'
AUDIENCE='knowledge-sdk-isolated-tests'

def encode64(data):return base64.urlsafe_b64encode(data).decode().rstrip('=')

class TestIssuer:
    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        p=self.key.public_key().public_numbers()
        self.jwk={'kid':'isolated-test-rsa','kty':'RSA','alg':'RS256','use':'sig','n':encode64(p.n.to_bytes(256,'big')),'e':encode64(p.e.to_bytes(3,'big'))}
    def get_key(self,kid):
        from knowledge_sdk.exceptions import ValidationError
        if kid!=self.jwk['kid']:raise ValidationError('Unknown test kid')
        return dict(self.jwk)
    def token(self,actor,**changes):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        now=int(time.time());claims={'iss':ISSUER,'aud':AUDIENCE,'sub':actor.user_id,'org_id':actor.org_id,'roles':list(actor.roles),'department_ids':list(actor.department_ids),'org_roles':list(actor.org_roles),'clearance_level':actor.clearance_level,'policy_generation':actor.policy_generation,'jti':uuid.uuid4().hex,'nbf':now-1,'exp':now+21600};claims.update(changes)
        header=encode64(json.dumps({'alg':'RS256','kid':self.jwk['kid']}).encode());body=encode64(json.dumps(claims).encode());message=(header+'.'+body).encode();return message.decode()+'.'+encode64(self.key.sign(message,padding.PKCS1v15(),hashes.SHA256()))

def build_fixture(engine,workdir,*,auth_mode='oidc',root_path='',provider=None):
    from knowledge_sdk.storage.sqlite_store import SQLiteStore
    workdir=Path(workdir);workdir.mkdir(parents=True,exist_ok=True)
    cleanup=[]
    if engine=='postgres':
        from tests.pg_helpers import PgSandbox
        from knowledge_sdk.server.postgres import postgres_client
        from knowledge_sdk.server.replay_pg import PostgresReplayStore
        pg=PgSandbox();cleanup.append(pg.close);c=postgres_client(pg.dsn,pgvector_dims=32);replay=PostgresReplayStore(pg.dsn);cleanup.append(replay.close)
    else:c=LocalKnowledgeClient(SQLiteStore(workdir/'fixture.db'));replay=InMemoryReplayStore()
    cleanup.append(c.store.close)
    author=Actor('author','m4-browser',org_roles=('admin',),policy_generation='1');reviewer=Actor('reviewer','m4-browser',org_roles=('admin',),policy_generation='1');publisher=Actor('publisher','m4-browser',org_roles=('admin',),policy_generation='1');reader=Actor('reader','m4-browser',policy_generation='1')
    c.create_kb(author,'Controlled enterprise evidence','enterprise',space_type='enterprise_public',kb_id='controlled',governance_tier='l2_controlled')
    c.ingest(author,'controlled','alpha APPROVED_PUBLIC_MARKER verified evidence',doc_id='doc-published',rights=ResourceRights(allow_export=True))
    c.submit_for_review(author,'doc-published',expected_version=1);c.approve_release(reviewer,'doc-published',version=1,expected_version=1);c.publish_release(publisher,'doc-published',version=1,expected_version=1)
    c.ingest(author,'controlled','DRAFT_NEVER_LEAK_MARKER unpublished experiment',doc_id='doc-draft')
    c.create_kb(author,'Connector sources','enterprise',space_type='enterprise_public',kb_id='sources')
    c.ingest(author,'sources','alpha obsolete source',doc_id='doc-impact',rights=ResourceRights(allow_export=True))
    pack=c.create_evidence_pack(reader,'Approved source pack',[{'doc_id':'doc-published','version':1}],pack_id='browser-pack')
    impacted=c.create_evidence_pack(reader,'Impacted source pack',[{'doc_id':'doc-impact','version':1}],pack_id='impacted-pack')
    c.set_document_rights(author,'doc-impact',ResourceRights(revoked=True));c.drain_outbox(author,limit=1000)
    foreign=Actor('owner','foreign-tenant',org_roles=('admin',));c.create_kb(foreign,'Foreign space','enterprise',space_type='enterprise_public',kb_id='foreign-kb');c.ingest(foreign,'foreign-kb','FOREIGN_NEVER_LEAK_MARKER private foreign evidence',doc_id='foreign-doc')
    for actor in (author,reviewer,publisher,reader):c.store.upsert_principal(IdentityPrincipal(actor.org_id,actor.user_id,org_roles=actor.org_roles))
    c.require_principal=True
    issuer=TestIssuer();provider=provider or issuer
    oidc=OIDCAuthenticator(ISSUER,AUDIENCE,provider,algorithms=('RS256',),replay_store=replay)
    source=workdir/'source';source.mkdir(exist_ok=True);(source/'sync.txt').write_text('alpha reference connector source evidence')
    conn_secret=secrets.token_hex(32);hmac_secret=secrets.token_hex(32);scim_secret=secrets.token_hex(32)
    connectors={'filesystem':(ControlledFilesystemConnector('filesystem',source,org_id=author.org_id),'sources'),'wiki':(WebhookSyncConnector('wiki',conn_secret,org_id=author.org_id),'sources')}
    app=create_app(c,auth_secret=hmac_secret if auth_mode!='oidc' else None,auth_mode=auth_mode,oidc_authenticator=oidc,enable_demo_switcher=False,dev_insecure=False,enable_mcp=True,replay_store=replay,connectors=connectors,scim_tokens={scim_secret:author},session_cookie_secure=False)
    # Explicit loopback-only HTTP fixture. Production leaves Secure cookie default on.
    return {'app':app,'client':c,'issuer':issuer,'reader':reader,'author':author,'hmac_secret':hmac_secret,'scim_secret':scim_secret,'conn_secret':conn_secret,'cleanup':cleanup,'root_path':root_path}

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=('sqlite','postgres'),required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--workdir',required=True);p.add_argument('--token-file',required=True);p.add_argument('--root-path',default='/kb-prod');a=p.parse_args()
    state=build_fixture(a.engine,a.workdir,root_path=a.root_path)
    path=Path(a.token_file);fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(state['issuer'].token(state['reader']))
    import uvicorn
    try:uvicorn.run(state['app'],host='127.0.0.1',port=a.port,root_path=a.root_path,access_log=False,log_level='warning')
    finally:
        for close in reversed(state['cleanup']):close()
if __name__=='__main__':main()
