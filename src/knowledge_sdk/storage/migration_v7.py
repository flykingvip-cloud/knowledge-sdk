"""Explicit nonproduction v6 -> v7 upgrade; never invoked by ordinary v1 startup.

AUTH-V21-07-CORE-V7 authorizes this module only on the Wave-V21-7 isolated
branch. schema_v7_prod_migration_authorized remains false. Callers must own a
disposable, non-production database (owned_nonproduction=True). Existing v6
tables, JSON, ACLs, reviews, audit and search rows are never rewritten. The
upgrade is additive and idempotent; rollback is idempotent and does not
restore historical security state.

SQLite uses PRAGMA user_version=7. PostgreSQL records schema_migrations
version 7 and ENABLE/FORCE RLS policies that bind tenant_id to
app.current_org_id.
"""
from __future__ import annotations
from ..exceptions import ConflictError, ValidationError

SCHEMA_VERSION = 7
SCHEMA_V7_PROD_MIGRATION_AUTHORIZED = False
TABLE_PREFIX = 'ks_v7_'

NEW_TABLES = (
    'ks_v7_meta',
    'ks_v7_tenant',
    'ks_v7_principal',
    'ks_v7_space',
    'ks_v7_org_team',
    'ks_v7_kb',
    'ks_v7_space_member',
    'ks_v7_grant',
    'ks_v7_deny',
    'ks_v7_asset',
    'ks_v7_agent_profile',
    'ks_v7_external',
    'ks_v7_outbox',
    'ks_v7_favorite',
    'ks_v7_share',
    'ks_v7_handover',
    'ks_v7_handover_approval',
    'ks_v7_tombstone',
    'ks_v7_security_event',
)

# Drop dependents first.
DROP_ORDER = (
    'ks_v7_security_event',
    'ks_v7_handover_approval',
    'ks_v7_handover',
    'ks_v7_share',
    'ks_v7_favorite',
    'ks_v7_tombstone',
    'ks_v7_outbox',
    'ks_v7_external',
    'ks_v7_deny',
    'ks_v7_grant',
    'ks_v7_asset',
    'ks_v7_agent_profile',
    'ks_v7_space_member',
    'ks_v7_org_team',
    'ks_v7_kb',
    'ks_v7_space',
    'ks_v7_principal',
    'ks_v7_tenant',
    'ks_v7_meta',
)

_APP_ROLE = 'ks_v7_core_app_role'


def schema_version(store):
    from .migration_v6 import schema_version as _v6_schema_version
    return _v6_schema_version(store)


def require_v7(store):
    if schema_version(store) != 7:
        raise ConflictError('SCHEMA_V7_REQUIRED')
    validate_v7(store)


def _guard_authorization(owned_nonproduction):
    if SCHEMA_V7_PROD_MIGRATION_AUTHORIZED is not False:
        raise ValidationError('SCHEMA_V7_PROD_MIGRATION_NOT_AUTHORIZED')
    if owned_nonproduction is not True:
        raise ValidationError('OWNED_NONPRODUCTION_DATABASE_REQUIRED')


def sqlite_v7_statements():
    return (
        """CREATE TABLE IF NOT EXISTS ks_v7_meta (
            tenant_id TEXT NOT NULL DEFAULT 'schema',
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY(tenant_id, key)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_tenant (
            tenant_id TEXT PRIMARY KEY,
            tenant_kind TEXT NOT NULL CHECK(tenant_kind IN ('enterprise','independent_personal')),
            CHECK(length(tenant_id)>0)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_principal (
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            issuer TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'active','resign_requested','frozen','isolation_retention',
                'handover_pending','handover_complete'
            )),
            policy_generation INTEGER NOT NULL CHECK(policy_generation>=1),
            resigned_at INTEGER,
            frozen_at INTEGER,
            isolation_until INTEGER,
            CHECK(user_id NOT LIKE '%@%'),
            PRIMARY KEY(tenant_id, user_id),
            UNIQUE(issuer, subject_id),
            FOREIGN KEY(tenant_id) REFERENCES ks_v7_tenant(tenant_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_space (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            space_type TEXT NOT NULL CHECK(space_type IN ('enterprise','team','personal')),
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('active','frozen','archived','pending_purge')),
            policy_generation INTEGER NOT NULL CHECK(policy_generation>=1),
            PRIMARY KEY(tenant_id, space_id),
            FOREIGN KEY(tenant_id) REFERENCES ks_v7_tenant(tenant_id),
            FOREIGN KEY(tenant_id, owner_id) REFERENCES ks_v7_principal(tenant_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_org_team (
            tenant_id TEXT NOT NULL,
            org_team_id TEXT NOT NULL,
            team_space_id TEXT NOT NULL,
            PRIMARY KEY(tenant_id, org_team_id),
            UNIQUE(tenant_id, team_space_id),
            CHECK(org_team_id NOT LIKE 'dept:%'),
            CHECK(org_team_id NOT LIKE 'department:%'),
            FOREIGN KEY(tenant_id, team_space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_kb (
            tenant_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            space_id TEXT,
            home_space_id TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
            CHECK(space_id IS NULL OR space_id = home_space_id),
            PRIMARY KEY(tenant_id, kb_id),
            FOREIGN KEY(tenant_id, home_space_id) REFERENCES ks_v7_space(tenant_id, space_id),
            FOREIGN KEY(tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_space_member (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY(tenant_id, space_id, user_id),
            FOREIGN KEY(tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id),
            FOREIGN KEY(tenant_id, user_id) REFERENCES ks_v7_principal(tenant_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_grant (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            action TEXT NOT NULL,
            allowed INTEGER NOT NULL CHECK(allowed IN (0,1)),
            PRIMARY KEY(tenant_id, space_id, subject_id, action),
            FOREIGN KEY(tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_deny (
            tenant_id TEXT NOT NULL,
            principal_kind TEXT NOT NULL CHECK(principal_kind IN ('user','agent')),
            principal_id TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('space','kb','asset')),
            target_id TEXT NOT NULL,
            action TEXT NOT NULL,
            PRIMARY KEY(tenant_id, principal_kind, principal_id, target_type, target_id, action)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_asset (
            tenant_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            resource_kind TEXT NOT NULL,
            folder_id TEXT,
            ref_id TEXT,
            PRIMARY KEY(tenant_id, asset_id),
            FOREIGN KEY(tenant_id, kb_id) REFERENCES ks_v7_kb(tenant_id, kb_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_agent_profile (
            tenant_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            generation INTEGER NOT NULL CHECK(generation>=1),
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            allowed_space_ids TEXT NOT NULL,
            allowed_kb_ids TEXT NOT NULL,
            allowed_space_types TEXT NOT NULL,
            allowed_asset_ids TEXT NOT NULL DEFAULT '[]',
            allowed_folder_ids TEXT NOT NULL DEFAULT '[]',
            allowed_knowledge_file_ids TEXT NOT NULL DEFAULT '[]',
            allowed_deliverable_ids TEXT NOT NULL DEFAULT '[]',
            deny_personal_spaces INTEGER NOT NULL DEFAULT 0 CHECK(deny_personal_spaces IN (0,1)),
            PRIMARY KEY(tenant_id, agent_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_external (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            valid_until INTEGER NOT NULL,
            revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
            generation INTEGER NOT NULL CHECK(generation>=1),
            tombstone INTEGER NOT NULL DEFAULT 0 CHECK(tombstone IN (0,1)),
            cursor TEXT,
            PRIMARY KEY(tenant_id, ref_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_outbox (
            tenant_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            space_id TEXT,
            generation INTEGER NOT NULL,
            kind TEXT NOT NULL,
            PRIMARY KEY(tenant_id, event_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_favorite (
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('kb','asset')),
            target_id TEXT NOT NULL,
            PRIMARY KEY(tenant_id, user_id, target_type, target_id),
            FOREIGN KEY(tenant_id, user_id) REFERENCES ks_v7_principal(tenant_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_share (
            tenant_id TEXT NOT NULL,
            share_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            grantee_id TEXT NOT NULL,
            mode TEXT NOT NULL CHECK(mode IN ('controlled_read_only')),
            status TEXT NOT NULL CHECK(status IN ('active','invalidated')),
            PRIMARY KEY(tenant_id, share_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_handover (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            leaver_id TEXT NOT NULL,
            target_user_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
            includes_private_body INTEGER NOT NULL DEFAULT 0 CHECK(includes_private_body=0),
            PRIMARY KEY(tenant_id, handover_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_handover_approval (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            PRIMARY KEY(tenant_id, handover_id, approver_id),
            FOREIGN KEY(tenant_id, handover_id) REFERENCES ks_v7_handover(tenant_id, handover_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_tombstone (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            revoked_at INTEGER NOT NULL,
            PRIMARY KEY(tenant_id, ref_id)
        )""",
        """CREATE TABLE IF NOT EXISTS ks_v7_security_event (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            at INTEGER NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL
        )""",
        """CREATE TRIGGER IF NOT EXISTS ks_v7_home_immutable
            BEFORE UPDATE ON ks_v7_kb
            WHEN NEW.home_space_id IS NOT OLD.home_space_id
            BEGIN
                SELECT RAISE(ABORT, 'HOME_SPACE_IMMUTABLE');
            END""",
        """CREATE TRIGGER IF NOT EXISTS ks_v7_no_parent_space_column
            BEFORE INSERT ON ks_v7_space
            BEGIN
                SELECT RAISE(ABORT, 'PARENT_SPACE_FORBIDDEN')
                WHERE EXISTS (
                    SELECT 1 FROM pragma_table_info('ks_v7_space') WHERE name='parent_space_id'
                );
            END""",
    )


def postgres_v7_ddl(include_semantic_role=True):
    """Return PostgreSQL Schema v7 DDL, including ENABLE/FORCE RLS policies.

    When include_semantic_role is True, a NOSUPERUSER NOBYPASSRLS role
    declaration is included for semantic validation only. apply_postgres()
    does not create that role (CI already provisions a disposable
    non-superuser). This function never opens a connection.
    """
    parts = []
    if include_semantic_role:
        parts.append(
            "CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;".format(role=_APP_ROLE)
        )
    parts.extend([
        """CREATE TABLE IF NOT EXISTS ks_v7_meta (
            tenant_id TEXT NOT NULL DEFAULT 'schema',
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (tenant_id, key)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_tenant (
            tenant_id TEXT PRIMARY KEY,
            tenant_kind TEXT NOT NULL CHECK (tenant_kind IN ('enterprise','independent_personal')),
            CHECK (length(tenant_id)>0)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_principal (
            tenant_id TEXT NOT NULL REFERENCES ks_v7_tenant(tenant_id),
            user_id TEXT NOT NULL,
            issuer TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            status TEXT NOT NULL,
            policy_generation INTEGER NOT NULL CHECK (policy_generation >= 1),
            resigned_at BIGINT,
            frozen_at BIGINT,
            isolation_until BIGINT,
            CHECK (user_id NOT LIKE '%@%'),
            PRIMARY KEY (tenant_id, user_id),
            UNIQUE (issuer, subject_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_space (
            tenant_id TEXT NOT NULL REFERENCES ks_v7_tenant(tenant_id),
            space_id TEXT NOT NULL,
            space_type TEXT NOT NULL CHECK (space_type IN ('enterprise','team','personal')),
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL,
            policy_generation INTEGER NOT NULL CHECK (policy_generation >= 1),
            PRIMARY KEY (tenant_id, space_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_org_team (
            tenant_id TEXT NOT NULL,
            org_team_id TEXT NOT NULL,
            team_space_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, org_team_id),
            UNIQUE (tenant_id, team_space_id),
            CHECK (org_team_id NOT LIKE 'dept:%'),
            CHECK (org_team_id NOT LIKE 'department:%'),
            FOREIGN KEY (tenant_id, team_space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_kb (
            tenant_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            space_id TEXT,
            home_space_id TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1)),
            PRIMARY KEY (tenant_id, kb_id),
            CHECK (space_id IS NULL OR space_id = home_space_id),
            FOREIGN KEY (tenant_id, home_space_id) REFERENCES ks_v7_space(tenant_id, space_id),
            FOREIGN KEY (tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_space_member (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (tenant_id, space_id, user_id),
            FOREIGN KEY (tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_grant (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            action TEXT NOT NULL,
            allowed INTEGER NOT NULL CHECK (allowed IN (0,1)),
            PRIMARY KEY (tenant_id, space_id, subject_id, action),
            FOREIGN KEY (tenant_id, space_id) REFERENCES ks_v7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_deny (
            tenant_id TEXT NOT NULL,
            principal_kind TEXT NOT NULL,
            principal_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            action TEXT NOT NULL,
            PRIMARY KEY (tenant_id, principal_kind, principal_id, target_type, target_id, action)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_asset (
            tenant_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            resource_kind TEXT NOT NULL,
            folder_id TEXT,
            ref_id TEXT,
            PRIMARY KEY (tenant_id, asset_id),
            FOREIGN KEY (tenant_id, kb_id) REFERENCES ks_v7_kb(tenant_id, kb_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_agent_profile (
            tenant_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            generation INTEGER NOT NULL CHECK (generation >= 1),
            active INTEGER NOT NULL CHECK (active IN (0,1)),
            allowed_space_ids TEXT NOT NULL,
            allowed_kb_ids TEXT NOT NULL,
            allowed_space_types TEXT NOT NULL,
            allowed_asset_ids TEXT NOT NULL DEFAULT '[]',
            allowed_folder_ids TEXT NOT NULL DEFAULT '[]',
            allowed_knowledge_file_ids TEXT NOT NULL DEFAULT '[]',
            allowed_deliverable_ids TEXT NOT NULL DEFAULT '[]',
            deny_personal_spaces INTEGER NOT NULL DEFAULT 0 CHECK (deny_personal_spaces IN (0,1)),
            PRIMARY KEY (tenant_id, agent_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_external (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            valid_until BIGINT NOT NULL,
            revoked INTEGER NOT NULL CHECK (revoked IN (0,1)),
            generation INTEGER NOT NULL CHECK (generation >= 1),
            tombstone INTEGER NOT NULL DEFAULT 0 CHECK (tombstone IN (0,1)),
            cursor TEXT,
            PRIMARY KEY (tenant_id, ref_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_outbox (
            tenant_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            space_id TEXT,
            generation INTEGER NOT NULL,
            kind TEXT NOT NULL,
            PRIMARY KEY (tenant_id, event_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_favorite (
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            target_type TEXT NOT NULL CHECK (target_type IN ('kb','asset')),
            target_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, user_id, target_type, target_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_share (
            tenant_id TEXT NOT NULL,
            share_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            grantee_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (tenant_id, share_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_handover (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            leaver_id TEXT NOT NULL,
            target_user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            includes_private_body INTEGER NOT NULL DEFAULT 0 CHECK (includes_private_body = 0),
            PRIMARY KEY (tenant_id, handover_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_handover_approval (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, handover_id, approver_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_tombstone (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            revoked_at BIGINT NOT NULL,
            PRIMARY KEY (tenant_id, ref_id)
        );""",
        """CREATE TABLE IF NOT EXISTS ks_v7_security_event (
            seq BIGSERIAL PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            at BIGINT NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL
        );""",
        """CREATE OR REPLACE FUNCTION ks_v7_home_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.home_space_id IS DISTINCT FROM OLD.home_space_id THEN
        RAISE EXCEPTION 'HOME_SPACE_IMMUTABLE';
    END IF;
    RETURN NEW;
END $$;""",
        "DROP TRIGGER IF EXISTS ks_v7_home_immutable ON ks_v7_kb;",
        "CREATE TRIGGER ks_v7_home_immutable BEFORE UPDATE ON ks_v7_kb FOR EACH ROW EXECUTE FUNCTION ks_v7_home_immutable();",
    ])
    for table in NEW_TABLES:
        parts.append('ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;'.format(t=table))
        parts.append('ALTER TABLE {t} FORCE ROW LEVEL SECURITY;'.format(t=table))
        parts.append(
            "DROP POLICY IF EXISTS tenant_isolation ON {t};".format(t=table)
        )
        parts.append(
            "CREATE POLICY tenant_isolation ON {t} "
            "USING (tenant_id = current_setting('app.current_org_id', true)) "
            "WITH CHECK (tenant_id = current_setting('app.current_org_id', true));".format(t=table)
        )
    return '\n'.join(parts) + '\n'


def _split_sql(ddl):
    statements = []
    buf = []
    in_dollar = False
    for line in ddl.splitlines():
        if '$$' in line:
            # toggle for each $$ pair on the line
            count = line.count('$$')
            if count % 2 == 1:
                in_dollar = not in_dollar
        buf.append(line)
        if not in_dollar and line.rstrip().endswith(';'):
            statements.append('\n'.join(buf))
            buf = []
    if any(item.strip() for item in buf):
        statements.append('\n'.join(buf))
    return [item.strip() for item in statements if item.strip()]


def upgrade_v7(store, *, owned_nonproduction=False):
    """Atomic, retryable upgrade of an explicitly owned, nonproduction v6 DB."""
    _guard_authorization(owned_nonproduction)
    from .migration_v6 import validate_v6
    pg = hasattr(store, '_pg')
    with store.transaction():
        if pg:
            previous_timeout = store._execute('SHOW lock_timeout')[0][0]
            store._execute("SELECT set_config('lock_timeout','5s',true)")
            store._execute("SELECT pg_advisory_xact_lock(hashtext('knowledge-sdk:migrations'))")
        version = schema_version(store)
        if version == 7:
            validate_v7(store)
            validate_v6(store)
            if pg:
                store._execute("SELECT set_config('lock_timeout',%s,true)", (previous_timeout,))
            return
        if version != 6:
            raise ConflictError('SCHEMA_V6_REQUIRED')
        validate_v6(store)
        if pg:
            _postgres(store)
        else:
            _sqlite(store)
        if pg:
            store._execute("SELECT set_config('lock_timeout',%s,true)", (previous_timeout,))
    validate_v7(store)


def rollback_v7(store, *, owned_nonproduction=False):
    """Idempotent structural rollback to Schema v6. Does not restore ACLs."""
    _guard_authorization(owned_nonproduction)
    pg = hasattr(store, '_pg')
    with store.transaction():
        if pg:
            store._execute("SELECT pg_advisory_xact_lock(hashtext('knowledge-sdk:migrations'))")
        version = schema_version(store)
        if version not in (6, 7):
            raise ConflictError('SCHEMA_V6_OR_V7_REQUIRED')
        if pg:
            present = {r[0] for r in store._execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")}
            store._execute('DROP TRIGGER IF EXISTS ks_v7_home_immutable ON ks_v7_kb')
            store._execute('DROP FUNCTION IF EXISTS ks_v7_home_immutable()')
            for table in DROP_ORDER:
                if table in present:
                    store._execute('DROP TABLE IF EXISTS ' + table + ' CASCADE')
            store._execute('DELETE FROM schema_migrations WHERE version=%s', (7,))
        else:
            store._execute('PRAGMA foreign_keys=OFF')
            try:
                store._execute('DROP TRIGGER IF EXISTS ks_v7_home_immutable')
                store._execute('DROP TRIGGER IF EXISTS ks_v7_no_parent_space_column')
                for table in DROP_ORDER:
                    store._execute('DROP TABLE IF EXISTS ' + table)
            finally:
                store._execute('PRAGMA foreign_keys=ON')
            if version == 7:
                store._execute('PRAGMA user_version=6')
    # Replay of a second rollback is a no-op. Historical grants are gone
    # and this function must not re-apply them.
    return schema_version(store)


def _sqlite(store):
    for statement in sqlite_v7_statements():
        store._execute(statement)
    store._execute(
        "INSERT OR REPLACE INTO ks_v7_meta(tenant_id, key, value) VALUES(?,?,?)",
        ('schema', 'schema_version', '7'),
    )
    store._execute(
        "INSERT OR REPLACE INTO ks_v7_meta(tenant_id, key, value) VALUES(?,?,?)",
        ('schema', 'schema_v7_prod_migration_authorized', 'false'),
    )
    store._execute(
        "INSERT OR REPLACE INTO ks_v7_meta(tenant_id, key, value) VALUES(?,?,?)",
        ('schema', 'formal_t01_t27_accepted', 'false'),
    )
    store._execute('PRAGMA user_version=7')


def _postgres(store):
    for statement in _split_sql(postgres_v7_ddl(include_semantic_role=False)):
        store._execute(statement)
    previous = store._execute("SELECT current_setting('app.current_org_id',true)")[0][0] or ''
    store._execute("SELECT set_config('app.current_org_id',%s,true)", ('schema',))
    store._execute(
        "INSERT INTO ks_v7_meta(tenant_id, key, value) VALUES(%s,%s,%s) "
        "ON CONFLICT(tenant_id, key) DO UPDATE SET value=EXCLUDED.value",
        ('schema', 'schema_version', '7'),
    )
    store._execute(
        "INSERT INTO ks_v7_meta(tenant_id, key, value) VALUES(%s,%s,%s) "
        "ON CONFLICT(tenant_id, key) DO UPDATE SET value=EXCLUDED.value",
        ('schema', 'schema_v7_prod_migration_authorized', 'false'),
    )
    store._execute(
        "INSERT INTO ks_v7_meta(tenant_id, key, value) VALUES(%s,%s,%s) "
        "ON CONFLICT(tenant_id, key) DO UPDATE SET value=EXCLUDED.value",
        ('schema', 'formal_t01_t27_accepted', 'false'),
    )
    store._execute("SELECT set_config('app.current_org_id',%s,true)", (previous,))
    store._execute("INSERT INTO schema_migrations VALUES(7,'schema-v7-core-isolation-branch',CURRENT_TIMESTAMP::text) ON CONFLICT DO NOTHING")


def validate_v7(store):
    if hasattr(store, '_pg'):
        tables = {r[0] for r in store._execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")}
        if not set(NEW_TABLES).issubset(tables):
            raise ConflictError('INCOMPLETE_SCHEMA_V7')
        protected = store._execute(
            "SELECT relname FROM pg_class WHERE relnamespace=current_schema()::regnamespace "
            "AND relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity",
            (list(NEW_TABLES),),
        )
        if {r[0] for r in protected} != set(NEW_TABLES):
            raise ConflictError('INCOMPLETE_SCHEMA_V7')
        columns = {r[0] for r in store._execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='ks_v7_space'"
        )}
        if 'parent_space_id' in columns:
            raise ConflictError('PARENT_SPACE_FORBIDDEN')
        fav = {r[0] for r in store._execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='ks_v7_favorite'"
        )}
        if {'body', 'chunk', 'embedding', 'evidence', 'body_text', 'content'} & fav:
            raise ConflictError('FAVORITE_BODY_FORBIDDEN')
    else:
        tables = {r[0] for r in store._execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(NEW_TABLES).issubset(tables):
            raise ConflictError('INCOMPLETE_SCHEMA_V7')
        columns = {r[1] for r in store._execute('PRAGMA table_info(ks_v7_space)')}
        if 'parent_space_id' in columns:
            raise ConflictError('PARENT_SPACE_FORBIDDEN')
        fav = {r[1] for r in store._execute('PRAGMA table_info(ks_v7_favorite)')}
        if {'body', 'chunk', 'embedding', 'evidence', 'body_text', 'content'} & fav:
            raise ConflictError('FAVORITE_BODY_FORBIDDEN')
        triggers = {r[0] for r in store._execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if 'ks_v7_home_immutable' not in triggers:
            raise ConflictError('INCOMPLETE_SCHEMA_V7')
    required = {
        'ks_v7_space': {'tenant_id', 'space_id', 'space_type', 'owner_id', 'status', 'policy_generation'},
        'ks_v7_kb': {'tenant_id', 'kb_id', 'space_id', 'home_space_id', 'archived'},
        'ks_v7_favorite': {'tenant_id', 'user_id', 'target_type', 'target_id'},
        'ks_v7_org_team': {'tenant_id', 'org_team_id', 'team_space_id'},
    }
    for table, names in required.items():
        if hasattr(store, '_pg'):
            actual = {r[0] for r in store._execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s",
                (table,),
            )}
        else:
            actual = {r[1] for r in store._execute('PRAGMA table_info(' + table + ')')}
        if not names.issubset(actual):
            raise ConflictError('INCOMPLETE_SCHEMA_V7')

