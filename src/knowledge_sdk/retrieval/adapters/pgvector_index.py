"""Metadata-only pgvector candidate index. Never a source of authorized content."""
from __future__ import annotations
import math
from ...storage.postgres_store import PostgresStore
from ...exceptions import ValidationError
from ..base import VectorHit


class PgVectorIndex:
    def __init__(self,dsn=None,dimensions=256,*,store=None,enable_rls=True):
        if type(dimensions) is not int or not 1<=dimensions<=16000:raise ValidationError('Invalid vector dimensions')
        self.store=store if store is not None else PostgresStore(dsn,enable_rls=enable_rls)
        self._owned=store is None;self.dimensions=dimensions
        try:
            with self.store.transaction():
                self.store._execute("SELECT pg_advisory_xact_lock(hashtext('knowledge-sdk:embeddings'))")
                # Exact cosine works on every dataset size; no approximate recall
                # claim or private embedding payload. Provision extension as DBA.
                self.store._execute('CREATE TABLE IF NOT EXISTS chunk_embeddings(org_id TEXT NOT NULL,doc_id TEXT NOT NULL,version INTEGER NOT NULL,chunk_id TEXT NOT NULL,kb_id TEXT NOT NULL,space_type TEXT NOT NULL,archived INTEGER NOT NULL,revoked INTEGER NOT NULL,lifecycle_state TEXT NOT NULL,embedding vector('+str(dimensions)+') NOT NULL,PRIMARY KEY(org_id,doc_id,version,chunk_id))')
                kind=self.store._execute("SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attrelid='chunk_embeddings'::regclass AND attname='embedding'")[0][0]
                if kind!='vector('+str(dimensions)+')':raise ValidationError('Existing vector dimensions differ')
                if enable_rls:
                    self.store._execute('ALTER TABLE chunk_embeddings ENABLE ROW LEVEL SECURITY')
                    self.store._execute('ALTER TABLE chunk_embeddings FORCE ROW LEVEL SECURITY')
                    self.store._execute('DROP POLICY IF EXISTS tenant_isolation ON chunk_embeddings')
                    self.store._execute("CREATE POLICY tenant_isolation ON chunk_embeddings USING(org_id=current_setting('app.current_org_id',true)) WITH CHECK(org_id=current_setting('app.current_org_id',true))")
        except BaseException:
            if self._owned:self.store.close()
            raise

    def _vector(self,vector):
        if len(vector)!=self.dimensions or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):raise ValidationError('Invalid vector')
        if not any(vector):raise ValidationError('Cosine requires a nonzero vector')
        return '['+','.join(str(float(v)) for v in vector)+']'

    def upsert(self,entries):
        with self.store.transaction():
            for hit,vector in entries:
                d=self.store.get_document(hit.doc_id);kb=self.store.get_kb(d.kb_id)
                # Validate candidate identity against authoritative chunks.
                if not any(c.chunk_id==hit.chunk_id for c in self.store.get_chunks(hit.doc_id,hit.version)):raise ValidationError('Unknown chunk')
                with self.store.tenant_scope(d.org_id):
                    self.store._execute('INSERT INTO chunk_embeddings VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT(org_id,doc_id,version,chunk_id) DO UPDATE SET kb_id=excluded.kb_id,space_type=excluded.space_type,archived=excluded.archived,revoked=excluded.revoked,lifecycle_state=excluded.lifecycle_state,embedding=excluded.embedding',
                        (d.org_id,hit.doc_id,hit.version,hit.chunk_id,d.kb_id,kb.space_type,int(d.archived),int(d.lifecycle_state=='revoked' or bool(d.rights and d.rights.revoked)),d.lifecycle_state,self._vector(vector)))

    def search_for_org(self,org_id,vector,limit=100):
        return self.search(vector,limit,org_id=org_id)

    def search(self,vector,limit=100,*,org_id=None):
        tenant=org_id or self.store.org_id
        if not tenant:raise ValidationError('Tenant required for vector search')
        if type(limit) is not int or not 1<=limit<=100000:raise ValidationError('Invalid vector limit')
        with self.store.tenant_scope(tenant):
            rows=self.store._execute('SELECT doc_id,version,chunk_id,1-(embedding <=> %s::vector) FROM chunk_embeddings WHERE org_id=%s AND archived=0 AND revoked=0 AND lifecycle_state=%s ORDER BY embedding <=> %s::vector,doc_id,version,chunk_id LIMIT %s',(self._vector(vector),tenant,'published',self._vector(vector),limit))
        return [VectorHit(*r) for r in rows]

    query=search

    def delete_document(self,doc_id):
        tenant=self.store._locate('document',doc_id)
        with self.store.tenant_scope(tenant):
            self.store._execute('DELETE FROM chunk_embeddings WHERE org_id=%s AND doc_id=%s',(tenant,doc_id))

    delete=delete_document

    def close(self):
        if self._owned:self.store.close()
