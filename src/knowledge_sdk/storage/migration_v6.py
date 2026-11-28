"""Explicit nonproduction v5 -> v6 upgrade; never invoked by ordinary v1 startup.

Callers must own the database. Existing v5 JSON, ACLs, reviews, audit and search
rows are never rewritten. SQLite uses globally unique opaque version IDs (a
stronger constraint than tenant uniqueness); PostgreSQL uses tenant uniqueness.
The two new tables have composite business keys and durable monotonic fences.
"""
from __future__ import annotations
import uuid
from ..exceptions import ConflictError, ValidationError

NEW_TABLES = ('idempotency_records', 'ingestion_jobs')


def schema_version(store):
    if hasattr(store, '_pg'):
        return store._execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations')[0][0]
    return store._execute('PRAGMA user_version')[0][0]


def require_v6(store):
    version = schema_version(store)
    if version not in (6, 7):
        raise ConflictError('SCHEMA_V6_REQUIRED')
    validate_v6(store)
    if version == 7:
        from .migration_v7 import validate_v7
        validate_v7(store)


def upgrade_v6(store, *, owned_nonproduction=False):
    """Atomic, retryable upgrade of an explicitly owned, nonproduction v5 DB.

    This boolean is a deliberate opt-in, not an authorization substitute. No DSN
    discovery, automatic production migration, tenant inference or null migration.
    PG uses the predecessor's advisory migration lock; SQLite BEGIN IMMEDIATE.
    Long-lived readers see a transactionally consistent predecessor or successor.
    """
    if owned_nonproduction is not True:
        raise ValidationError('OWNED_NONPRODUCTION_DATABASE_REQUIRED')
    with store.transaction():
        pg = hasattr(store, '_pg')
        if pg:
            previous_timeout=store._execute('SHOW lock_timeout')[0][0]
            store._execute("SELECT set_config('lock_timeout','5s',true)")
            store._execute("SELECT pg_advisory_xact_lock(hashtext('knowledge-sdk:migrations'))")
        version = schema_version(store)
        if version in (6, 7):
            validate_v6(store)
            if version == 7:
                from .migration_v7 import validate_v7
                validate_v7(store)
            if pg:store._execute("SELECT set_config('lock_timeout',%s,true)",(previous_timeout,))
            return
        if version != 5:
            raise ConflictError('SCHEMA_V5_REQUIRED')
        if pg:
            _postgres(store)
        else:
            _sqlite(store)
        if pg:store._execute("SELECT set_config('lock_timeout',%s,true)",(previous_timeout,))


def _tables(store, pg):
    fence = 'BIGSERIAL PRIMARY KEY' if pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    number = 'DOUBLE PRECISION' if pg else 'REAL'
    store._execute('CREATE TABLE idempotency_records (\n        claim_id {fence}, org_id TEXT NOT NULL CHECK(length(org_id)>0),\n        method TEXT NOT NULL, canonical_path TEXT NOT NULL, idempotency_key TEXT NOT NULL,\n        fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),\n        expires_at {number} NOT NULL, completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),\n        response_snapshot TEXT,\n        UNIQUE(org_id,method,canonical_path,idempotency_key))'.format(fence=fence,number=number))
    store._execute('CREATE INDEX idx_idempotency_expiry ON idempotency_records(org_id,expires_at)')
    store._execute("""CREATE TABLE ingestion_jobs (
        org_id TEXT NOT NULL CHECK(length(org_id)>0), job_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),
        revision INTEGER NOT NULL CHECK(revision>=0),
        status TEXT NOT NULL CHECK(status IN ('queued','parsing','chunking','indexing','completed','failed','cancelled')),
        data TEXT NOT NULL, PRIMARY KEY(org_id,job_id), UNIQUE(org_id,idempotency_key))""")


def _sqlite(store):
    if store._execute("SELECT 1 FROM documents WHERE org_id IS NULL OR trim(org_id)='' LIMIT 1"):
        raise ConflictError('EXPLICIT_ENTERPRISE_TENANT_REQUIRED')
    store._execute('ALTER TABLE document_versions ADD COLUMN version_id TEXT')
    for doc_id, version in store._execute('SELECT doc_id,version FROM document_versions'):
        store._execute('UPDATE document_versions SET version_id=? WHERE doc_id=? AND version=?',
                       (uuid.uuid4().hex,doc_id,version))
    store._execute('CREATE UNIQUE INDEX idx_version_id ON document_versions(version_id)')
    store._execute("""CREATE TRIGGER version_id_required BEFORE INSERT ON document_versions
        WHEN NEW.version_id IS NULL OR length(NEW.version_id)=0
        BEGIN SELECT RAISE(ABORT,'Opaque version ID required'); END""")
    store._execute("""CREATE TRIGGER version_id_immutable BEFORE UPDATE ON document_versions
        WHEN NEW.version_id IS NOT OLD.version_id OR NEW.doc_id IS NOT OLD.doc_id OR NEW.version IS NOT OLD.version
        BEGIN SELECT RAISE(ABORT,'Immutable version coordinates'); END""")
    _tables(store,False)
    store._execute('PRAGMA user_version=6')


def _postgres(store):
    # FORCE RLS remains enabled throughout. Directory rows are routing coordinates,
    # not permission grants. An orphan version fails NOT NULL rather than disappearing.
    store._execute('ALTER TABLE document_versions ADD COLUMN version_id TEXT')
    previous=store._execute("SELECT current_setting('app.current_org_id',true)")[0][0] or ''
    for (org,) in store._execute('SELECT DISTINCT tenant FROM resource_directory'):
        if not org:
            raise ConflictError('EXPLICIT_ENTERPRISE_TENANT_REQUIRED')
        store._execute("SELECT set_config('app.current_org_id',%s,true)",(org,))
        for doc_id,version in store._execute('SELECT doc_id,version FROM document_versions WHERE org_id=%s',(org,)):
            store._execute('UPDATE document_versions SET version_id=%s WHERE org_id=%s AND doc_id=%s AND version=%s',
                           (uuid.uuid4().hex,org,doc_id,version))
    store._execute("SELECT set_config('app.current_org_id',%s,true)",(previous,))
    store._execute('ALTER TABLE document_versions ALTER COLUMN version_id SET NOT NULL')
    store._execute('ALTER TABLE document_versions ADD CHECK(length(version_id)>0)')
    store._execute('CREATE UNIQUE INDEX idx_version_id ON document_versions(org_id,version_id)')
    store._execute("""CREATE FUNCTION knowledge_version_coordinates_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.version_id IS DISTINCT FROM OLD.version_id OR NEW.org_id IS DISTINCT FROM OLD.org_id
          OR NEW.doc_id IS DISTINCT FROM OLD.doc_id OR NEW.version IS DISTINCT FROM OLD.version
        THEN RAISE EXCEPTION 'Immutable version coordinates'; END IF; RETURN NEW; END; $$""")
    store._execute('CREATE TRIGGER version_id_immutable BEFORE UPDATE ON document_versions FOR EACH ROW EXECUTE FUNCTION knowledge_version_coordinates_immutable()')
    _tables(store,True)
    for table in NEW_TABLES:
        store._execute('ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY')
        store._execute('ALTER TABLE '+table+' FORCE ROW LEVEL SECURITY')
        store._execute("CREATE POLICY tenant_isolation ON "+table+" USING (org_id=current_setting('app.current_org_id',true)) WITH CHECK (org_id=current_setting('app.current_org_id',true))")
    store._execute("INSERT INTO schema_migrations VALUES(6,'schema-v6-nonproduction',CURRENT_TIMESTAMP::text)")


def version_id(store, org_id, doc_id, version):
    """Tenant-bound lookup; never guesses or reconstructs a missing historic ID."""
    from ..exceptions import NotFoundError
    require_v6(store)
    if not isinstance(org_id,str) or not org_id:
        raise ValidationError('EXPLICIT_ENTERPRISE_TENANT_REQUIRED')
    if hasattr(store,'_pg'):
        with store.tenant_scope(org_id):
            rows=store._execute('SELECT version_id FROM document_versions WHERE org_id=%s AND doc_id=%s AND version=%s',(org_id,doc_id,version))
    else:
        rows=store._execute('SELECT v.version_id FROM document_versions v JOIN documents d ON d.doc_id=v.doc_id WHERE d.org_id=? AND v.doc_id=? AND v.version=?',(org_id,doc_id,version))
    if not rows or not rows[0][0]:
        raise NotFoundError('HISTORICAL_VERSION_MAPPING_MISSING')
    return rows[0][0]


def validate_v6(store):
    """A version marker alone cannot make an incomplete schema ready/supported."""
    if hasattr(store,'_pg'):
        tables={r[0] for r in store._execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")}
        columns={r[0] for r in store._execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='document_versions'")}
        protected=store._execute("SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relname IN ('idempotency_records','ingestion_jobs') AND relrowsecurity AND relforcerowsecurity")
        if {r[0] for r in protected}!=set(NEW_TABLES):
            raise ConflictError('INCOMPLETE_SCHEMA_V6')
    else:
        tables={r[0] for r in store._execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns={r[1] for r in store._execute('PRAGMA table_info(document_versions)')}
        triggers={r[0] for r in store._execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not {'version_id_required','version_id_immutable'}.issubset(triggers):
            raise ConflictError('INCOMPLETE_SCHEMA_V6')
    if not set(NEW_TABLES).issubset(tables) or 'version_id' not in columns:
        raise ConflictError('INCOMPLETE_SCHEMA_V6')

    required={
        'idempotency_records':{'claim_id','org_id','method','canonical_path','idempotency_key','fingerprint','expires_at','completed','response_snapshot'},
        'ingestion_jobs':{'org_id','job_id','idempotency_key','fingerprint','revision','status','data'}}
    for table,names in required.items():
        if hasattr(store,'_pg'):
            actual={r[0] for r in store._execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s",(table,))}
        else:actual={r[1] for r in store._execute('PRAGMA table_info('+table+')')}
        if not names.issubset(actual):raise ConflictError('INCOMPLETE_SCHEMA_V6')
