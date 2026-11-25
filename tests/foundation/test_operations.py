import importlib.util
import io
import json
import logging
import os
import secrets
import unittest
from dataclasses import replace
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from knowledge_sdk import Actor,LocalKnowledgeClient,HttpKnowledgeClient,DocumentACL,ResourceRights,Purpose,PermissionDeniedError
from knowledge_sdk.contracts.identity import IdentityPrincipal
HTTP=all(importlib.util.find_spec(p) for p in ('fastapi','uvicorn'))


class OperationCases:
    engine='sqlite'
    def setUp(self):
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox
            from knowledge_sdk.server.postgres import postgres_client
            pg=PgSandbox();self.addCleanup(pg.close);self.c=postgres_client(pg.dsn,pgvector_dims=32)
        else:self.c=LocalKnowledgeClient()
        self.addCleanup(self.c.store.close)
        self.a=Actor('owner@example.invalid','tenant@example.invalid',org_roles=('admin','metrics_admin'))
        self.secret=secrets.token_hex(32)
        from knowledge_sdk.server.app import create_app
        from tests.foundation.helpers import live
        ctx=live(create_app(self.c,auth_secret=self.secret,enable_ui=False))
        self.base=ctx.__enter__();self.addCleanup(ctx.__exit__,None,None,None)
        self.h=HttpKnowledgeClient(self.base,self.secret)
    def get(self,path,actor=None,headers=None):
        from knowledge_sdk.server.auth import signed_headers
        hdr=dict(headers or {})
        if actor:hdr.update(signed_headers(actor,self.secret,'GET',path,b''))
        try:r=urlopen(Request(self.base+path,headers=hdr),timeout=15)
        except HTTPError as exc:r=exc
        with r:return r.status,r.read().decode(),r.headers
    def test_complete_log_stream_zero_sensitive_values(self):
        stream=io.StringIO();handler=logging.StreamHandler(stream);root=logging.getLogger();old=root.level;root.addHandler(handler);root.setLevel(logging.INFO)
        try:
            self.h.create_kb(self.a,'fixture',kb_id='k')
            content='BODY_SENTINEL_857982 user@example.invalid'
            self.h.ingest(self.a,'k',content,doc_id='d',title='TITLE_PII_SENTINEL')
            self.h.search(self.a,'BODY_SENTINEL_857982')
            self.h.set_document_acl(self.a,'d',DocumentACL(deny_users=[self.a.user_id]))
            try:self.h.get_document(self.a,'d')
            except Exception:pass
            signature='HMAC_SIGNATURE_SENTINEL_239';token='BEARER_TOKEN_SENTINEL_881'
            self.get('/metrics?email=query@example.invalid',headers={'Authorization':'Bearer '+token,'X-KB-Signature':signature,'X-Request-ID':'email@example.invalid'})
            self.get('/unknown/user@example.invalid?content=RAW_QUERY_SENTINEL')
            self.get('/metrics',self.a)
        finally:root.removeHandler(handler);root.setLevel(old);handler.close()
        raw=stream.getvalue()
        for secret in (self.secret,content,'BODY_SENTINEL_857982','user@example.invalid','tenant@example.invalid','owner@example.invalid','TITLE_PII_SENTINEL',signature,token,'query@example.invalid','RAW_QUERY_SENTINEL','email@example.invalid'):
            self.assertNotIn(secret,raw)
        rows=[json.loads(line) for line in raw.splitlines()];self.assertGreaterEqual(len(rows),8)
        for row in rows:
            self.assertEqual(set(row),{'request_id','tenant_id','operation','status_code','latency_ms','error_code'});self.assertEqual(len(row['request_id']),32)
        self.assertTrue(any(r['status_code']==403 for r in rows));self.assertTrue(any(r['operation']=='/v1/search' for r in rows))
    def test_ready_real_database_schema_failure_and_recovery(self):
        self.assertEqual(self.get('/v1/ready')[0],200)
        if self.engine=='postgres':
            self.c.store._execute('UPDATE schema_migrations SET version=50 WHERE version=5')
            self.assertEqual(self.get('/v1/ready')[0],503)
            self.c.store._execute('UPDATE schema_migrations SET version=5 WHERE version=50')
        else:
            self.c.store._execute('PRAGMA user_version=50');self.assertEqual(self.get('/v1/ready')[0],503);self.c.store._execute('PRAGMA user_version=5')
        self.assertEqual(self.get('/v1/ready')[0],200)
        self.c.store.close();status,body,_=self.get('/v1/ready');self.assertEqual(status,503);self.assertEqual(json.loads(body),{'status':'not_ready'})
    def test_prometheus_auth_current_actor_and_no_labels(self):
        self.assertEqual(self.get('/metrics')[0],401)
        ordinary=replace(self.a,org_roles=())
        self.assertEqual(self.get('/metrics',ordinary)[0],403)
        self.h.create_kb(self.a,'k',kb_id='k');self.h.ingest(self.a,'k','alpha content',doc_id='d');self.h.search(self.a,'alpha')
        self.c.register_agent_profile(self.a,'agent',allowed_kb_ids=['k'])
        task=self.h.create_task_context(self.a,'agent',purpose=Purpose.READ)
        snap=self.h.create_context_snapshot(self.a,task.task_id,[{'doc_id':'d'}])
        self.h.archive(self.a,'d')
        with self.assertRaises(PermissionDeniedError):self.h.read_task_snapshot(self.a,task.task_id,snap.snapshot_id)
        status,body,headers=self.get('/metrics',self.a);self.assertEqual(status,200);self.assertIn('text/plain',headers['Content-Type'])
        values={k:float(v) for k,v in (line.split() for line in body.splitlines())}
        self.assertGreaterEqual(values['knowledge_sdk_permission_denials_total'],2)
        self.assertGreaterEqual(values['knowledge_sdk_search_latency_seconds_count'],1)
        self.assertGreater(values['knowledge_sdk_search_latency_seconds_sum'],0)
        self.assertGreaterEqual(values['knowledge_sdk_revocation_denials_total'],1)
        self.assertNotIn('{',body);self.assertNotIn(self.a.org_id,body);self.assertNotIn('alpha',body)
        self.c.store.upsert_principal(IdentityPrincipal(self.a.org_id,self.a.user_id,policy_generation=2))
        self.assertEqual(self.get('/metrics',replace(self.a,policy_generation='1'))[0],401)
        self.c.store.upsert_principal(IdentityPrincipal(self.a.org_id,self.a.user_id,active=False,policy_generation=3))
        self.assertEqual(self.get('/metrics',replace(self.a,policy_generation='3'))[0],401)


@unittest.skipUnless(HTTP,'HTTP extras unavailable')
class SQLiteOperations(OperationCases,unittest.TestCase):pass
@unittest.skipUnless(HTTP and os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'HTTP/PG unavailable')
class PostgresOperations(OperationCases,unittest.TestCase):engine='postgres'
