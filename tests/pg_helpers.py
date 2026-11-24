"""Disposable-schema test infrastructure; never SQL mocks for PG acceptance."""
import os
import uuid
import json
from knowledge_sdk.storage.pg_support import connect,driver
from knowledge_sdk.storage.postgres_store import PostgresStore
from knowledge_sdk.server.postgres import postgres_client


class PgSandbox:
    def __init__(self,dsn=None):
        self.base=dsn or os.environ['KNOWLEDGE_SDK_TEST_PG_DSN']
        self.schema='sdk_test_'+uuid.uuid4().hex
        pg=driver()
        with connect(self.base) as c:
            c.execute(pg.sql.SQL('CREATE SCHEMA {}').format(pg.sql.Identifier(self.schema)))
        self.dsn=pg.conninfo.make_conninfo(self.base,options='-csearch_path='+self.schema+',public')
    def close(self):
        pg=driver()
        with connect(self.base) as c:
            c.execute(pg.sql.SQL('DROP SCHEMA {} CASCADE').format(pg.sql.Identifier(self.schema)))


class GoldenPostgresStore(PostgresStore):
    """ONLY benchmark white-box probes use SQLite '?' syntax and omit tenant.

    Production native SQL methods remain unchanged. Wrap those original probes in
    an explicit org scope; no RLS bypass or row contents/expectations are changed.
    """
    def _execute(self,sql,args=()):
        sql=sql.replace('?', '%s')
        if sql.startswith('UPDATE audit_events'):
            # Deliberate owner-level corruption probe, never application SQL.
            with self.transaction():
                super()._execute('ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY')
                try:return super()._execute(sql,args)
                finally:super()._execute('ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY')
        diagnostic=self._tenant is None and any((' '+t) in sql for t in ('documents','document_versions','chunks','document_acls','evidence_anchors','usage_events','consumer_bindings','audit_events','outbox_events','webhook_deliveries'))
        if diagnostic:
            with self.tenant_scope('org'):
                return super()._execute(sql.replace('?', '%s'),args)
        return super()._execute(sql,args)


def golden_client(dsn):
    from knowledge_sdk import LocalKnowledgeClient
    from knowledge_sdk.retrieval.adapters.pgvector_index import PgVectorIndex
    from knowledge_sdk.retrieval.adapters.hash_embedder import HashEmbedder
    store=GoldenPostgresStore(dsn)
    try:return LocalKnowledgeClient(store,vector_index=PgVectorIndex(store=store),embedder=HashEmbedder())
    except BaseException:store.close();raise
