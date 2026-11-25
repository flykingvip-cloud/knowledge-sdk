import os,unittest
from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL,ResourceRights,Purpose,PermissionDeniedError

class RollbackCases:
    engine='sqlite'
    def setUp(self):
        self.sandbox=None
        if self.engine=='postgres':
            from tests.pg_helpers import PgSandbox,golden_client
            self.sandbox=PgSandbox();self.c=golden_client(self.sandbox.dsn)
        else:self.c=LocalKnowledgeClient()
        self.addCleanup(self.cleanup);self.a=Actor('owner','fixture-org',org_roles=('admin',));self.b=Actor('reader','fixture-org')
        self.c.create_kb(self.a,'space',kb_id='space');self.c.grant_kb_member(self.a,'space','reader','editor')
        self.c.ingest(self.a,'space','old content',filename='old.txt',doc_id='d',metadata={'business':'old'})
        self.c.ingest(self.a,'space','new content',filename='new.txt',doc_id='d',metadata={'business':'current'})
    def cleanup(self):
        try:self.c.store.close()
        finally:
            if self.sandbox:self.sandbox.close()
    def test_audit_scope_and_no_response_field_or_historical_security_resurrection(self):
        from knowledge_sdk.contracts.models import encode
        acl=DocumentACL(deny_users=['reader']);rights=ResourceRights(allowed_purposes=(Purpose.READ,))
        self.c.set_document_acl(self.a,'d',acl);self.c.set_document_rights(self.a,'d',rights)
        before=self.c.store.get_version('d',1);result=self.c.rollback_document(self.a,'d',1)
        self.assertEqual(result.version,3);self.assertEqual(result.text,'old content');self.assertEqual(result.filename,'old.txt')
        self.assertEqual(set(encode(before)),set(encode(result)));self.assertEqual(self.c.store.get_acl('d'),acl)
        self.assertEqual(self.c.store.get_document('d').rights,rights);self.assertEqual(self.c.store.get_document('d').metadata,{'business':'current'})
        with self.assertRaises(PermissionDeniedError):self.c.get_document(self.b,'d')
        audit=self.c.store.list_audit_events('fixture-org',action='rollback_document',limit=100)[-1]
        self.assertEqual(audit.details['rollback_scope'],'content_and_filename_only');self.assertIs(audit.details['security_metadata_preserved'],True)
        self.assertEqual(audit.details['rollback_from_version'],1);self.assertEqual(self.c.store.get_version('d',1),before)
        self.c.set_document_rights(self.a,'d',ResourceRights(revoked=True))
        with self.assertRaises(PermissionDeniedError):self.c.rollback_document(self.a,'d',1)
        self.assertEqual(self.c.store.latest_version('d'),3);self.assertTrue(self.c.store.get_document('d').rights.revoked)

class SQLiteRollback(RollbackCases,unittest.TestCase):pass
@unittest.skipUnless(os.environ.get('KNOWLEDGE_SDK_TEST_PG_DSN'),'Disposable PG unavailable')
class PostgresRollback(RollbackCases,unittest.TestCase):engine='postgres'
