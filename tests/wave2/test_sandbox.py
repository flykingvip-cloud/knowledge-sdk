"""Guarded real dual-engine fixture upgrade and v2 signed HTTP; no production target."""
import json
from contextlib import contextmanager
import os
import unittest
from urllib.request import Request,urlopen
from tests.alignment_p5.test_sandbox import FixtureCases,load,HAS_HTTP


@contextmanager
def owned(client):
    try:yield client
    finally:client.store.close()


class V2SandboxCases:
    mode='sqlite'
    setUp=FixtureCases.setUp
    drop_owned_schema=FixtureCases.drop_owned_schema
    seed=FixtureCases.seed
    connect=FixtureCases.connect

    def test_recognized_v5_upgrade_receipts_and_live_v2(self):
        upgrade=load('upgrade_wave2');seedmod=load('seed_openbot_sandbox')
        self.seed();original=(self.data/'seed-receipt.json').read_bytes()
        with owned(self.connect()) as client:before=seedmod.fingerprint(client)
        self.assertEqual(upgrade.upgrade(self.data,self.mode,self.dsn)['schema_version'],6)
        self.assertEqual((self.data/'seed-receipt.json').read_bytes(),original)
        self.assertEqual(upgrade.upgrade(self.data,self.mode,self.dsn)['status'],'WAVE2_IDEMPOTENT_NO_DDL')
        with owned(upgrade.connect_wave2(self.data,self.mode,self.dsn)) as client:
            self.assertEqual(seedmod.fingerprint(client),before)
            if not HAS_HTTP:return
            from knowledge_sdk.server.app import create_app
            from knowledge_sdk.server.v2_auth import signed_v2_headers
            from tests.foundation.helpers import live
            secret='TEST-ONLY-WAVE2-SANDBOX-KEY-NEVER-PRODUCTION'
            org=seedmod.TENANTS[0];actor=seedmod.actor(org)
            ctx=dict(request_id='sandbox-wave2',tenant_id=org,actor=dict(issuer='https://sandbox.example.invalid',subject_id=actor.user_id,actor_type='human',roles=list(actor.roles),department_ids=list(actor.department_ids),ancestor_department_ids=[],org_roles=list(actor.org_roles),clearance_level=actor.clearance_level,clearance_tags=[],policy_generation=1,session_id=actor.session_id),agent=dict(agent_id='fixture-agent-private',profile_generation=1,task_id=''),purpose='read')
            app=create_app(client,auth_secret=secret,enable_ui=False,enable_mcp=True,enable_v2=True,v2_issuer='https://sandbox.example.invalid')
            with live(app) as base:
                for path in ('/v2/spaces','/v2/assets/'+org+'-private-doc'):
                    with urlopen(Request(base+path,headers=signed_v2_headers(ctx,secret,'GET',path)),timeout=15) as r:
                        self.assertEqual(r.status,200);self.assertIsInstance(json.loads(r.read()),list if path.endswith('spaces') else dict)
                path='/v2/assets';payload=dict(kb_id=org+'-private',content='wave2 sandbox alpha',filename='fixture.txt',asset_type='document',idempotency_key='sandbox')
                body=json.dumps(payload).encode();headers=signed_v2_headers(ctx,secret,'POST',path,body);headers['Idempotency-Key']='sandbox';headers['Content-Type']='application/json'
                with urlopen(Request(base+path,data=body,headers=headers),timeout=15) as r:self.assertEqual(r.status,200);self.assertEqual(json.loads(r.read())['hash_algorithm'],'sha256')

    def test_unrecognized_or_modified_wave2_receipt_refused(self):
        upgrade=load('upgrade_wave2')
        self.seed();upgrade.upgrade(self.data,self.mode,self.dsn)
        receipt=self.data/'wave2-receipt.json';data=json.loads(receipt.read_text());data['physical_schema_sha256']='0'*64;receipt.write_text(json.dumps(data))
        with self.assertRaises(ValueError):upgrade.connect_wave2(self.data,self.mode,self.dsn)


class SQLiteV2Sandbox(V2SandboxCases,unittest.TestCase):pass


@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_SANDBOX_TEST_DSN'),'owned PostgreSQL sandbox required')
class PostgresV2Sandbox(V2SandboxCases,unittest.TestCase):mode='postgres'
