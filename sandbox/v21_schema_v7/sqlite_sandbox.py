"""Disposable Schema v7 SQLite migration and idempotent rollback.

Opens only a newly created in-memory database or a throwaway temporary
file created by this module. Refuses any connection that already looks
like a Knowledge SDK Schema v6 store. Never upgrades an existing v6
database and never touches src/knowledge_sdk/storage/.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from .constants import (
    PRODUCTION_V6_TABLES,
    SANDBOX_SCHEMA_VERSION,
    TABLE_PREFIX,
)

# Tables in drop order (dependents first).
SANDBOX_TABLES = (
    'sv7_security_event',
    'sv7_handover_approval',
    'sv7_handover',
    'sv7_share',
    'sv7_favorite',
    'sv7_tombstone',
    'sv7_outbox',
    'sv7_external',
    'sv7_deny',
    'sv7_grant',
    'sv7_asset',
    'sv7_agent_profile',
    'sv7_space_member',
    'sv7_org_team',
    'sv7_kb',
    'sv7_space',
    'sv7_principal',
    'sv7_tenant',
    'sv7_meta',
)

_MIGRATE_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS sv7_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_tenant (
        tenant_id TEXT PRIMARY KEY,
        tenant_kind TEXT NOT NULL CHECK(tenant_kind IN ('enterprise','independent_personal')),
        CHECK(length(tenant_id)>0)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_principal (
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
        FOREIGN KEY(tenant_id) REFERENCES sv7_tenant(tenant_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_space (
        tenant_id TEXT NOT NULL,
        space_id TEXT NOT NULL,
        space_type TEXT NOT NULL CHECK(space_type IN ('enterprise','team','personal')),
        owner_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('active','frozen','archived','pending_purge')),
        policy_generation INTEGER NOT NULL CHECK(policy_generation>=1),
        PRIMARY KEY(tenant_id, space_id),
        FOREIGN KEY(tenant_id) REFERENCES sv7_tenant(tenant_id),
        FOREIGN KEY(tenant_id, owner_id) REFERENCES sv7_principal(tenant_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_org_team (
        tenant_id TEXT NOT NULL,
        org_team_id TEXT NOT NULL,
        team_space_id TEXT NOT NULL,
        PRIMARY KEY(tenant_id, org_team_id),
        UNIQUE(tenant_id, team_space_id),
        CHECK(org_team_id NOT LIKE 'dept:%'),
        CHECK(org_team_id NOT LIKE 'department:%'),
        FOREIGN KEY(tenant_id, team_space_id) REFERENCES sv7_space(tenant_id, space_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_kb (
        tenant_id TEXT NOT NULL,
        kb_id TEXT NOT NULL,
        space_id TEXT,
        home_space_id TEXT NOT NULL,
        archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
        CHECK(space_id IS NULL OR space_id = home_space_id),
        PRIMARY KEY(tenant_id, kb_id),
        FOREIGN KEY(tenant_id, home_space_id) REFERENCES sv7_space(tenant_id, space_id),
        FOREIGN KEY(tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_space_member (
        tenant_id TEXT NOT NULL,
        space_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        PRIMARY KEY(tenant_id, space_id, user_id),
        FOREIGN KEY(tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id),
        FOREIGN KEY(tenant_id, user_id) REFERENCES sv7_principal(tenant_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_grant (
        tenant_id TEXT NOT NULL,
        space_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        action TEXT NOT NULL,
        allowed INTEGER NOT NULL CHECK(allowed IN (0,1)),
        PRIMARY KEY(tenant_id, space_id, subject_id, action),
        FOREIGN KEY(tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_deny (
        tenant_id TEXT NOT NULL,
        principal_kind TEXT NOT NULL CHECK(principal_kind IN ('user','agent')),
        principal_id TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK(target_type IN ('space','kb','asset')),
        target_id TEXT NOT NULL,
        action TEXT NOT NULL,
        PRIMARY KEY(tenant_id, principal_kind, principal_id, target_type, target_id, action)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_asset (
        tenant_id TEXT NOT NULL,
        asset_id TEXT NOT NULL,
        kb_id TEXT NOT NULL,
        resource_kind TEXT NOT NULL,
        folder_id TEXT,
        ref_id TEXT,
        PRIMARY KEY(tenant_id, asset_id),
        FOREIGN KEY(tenant_id, kb_id) REFERENCES sv7_kb(tenant_id, kb_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_agent_profile (
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
    """CREATE TABLE IF NOT EXISTS sv7_external (
        tenant_id TEXT NOT NULL,
        ref_id TEXT NOT NULL,
        valid_until INTEGER NOT NULL,
        revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
        generation INTEGER NOT NULL CHECK(generation>=1),
        tombstone INTEGER NOT NULL DEFAULT 0 CHECK(tombstone IN (0,1)),
        cursor TEXT,
        PRIMARY KEY(tenant_id, ref_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_outbox (
        tenant_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        space_id TEXT,
        generation INTEGER NOT NULL,
        kind TEXT NOT NULL,
        PRIMARY KEY(tenant_id, event_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_favorite (
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK(target_type IN ('kb','asset')),
        target_id TEXT NOT NULL,
        PRIMARY KEY(tenant_id, user_id, target_type, target_id),
        FOREIGN KEY(tenant_id, user_id) REFERENCES sv7_principal(tenant_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_share (
        tenant_id TEXT NOT NULL,
        share_id TEXT NOT NULL,
        space_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        grantee_id TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('controlled_read_only')),
        status TEXT NOT NULL CHECK(status IN ('active','invalidated')),
        PRIMARY KEY(tenant_id, share_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_handover (
        tenant_id TEXT NOT NULL,
        handover_id TEXT NOT NULL,
        leaver_id TEXT NOT NULL,
        target_user_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
        includes_private_body INTEGER NOT NULL DEFAULT 0 CHECK(includes_private_body=0),
        PRIMARY KEY(tenant_id, handover_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_handover_approval (
        tenant_id TEXT NOT NULL,
        handover_id TEXT NOT NULL,
        approver_id TEXT NOT NULL,
        PRIMARY KEY(tenant_id, handover_id, approver_id),
        FOREIGN KEY(tenant_id, handover_id) REFERENCES sv7_handover(tenant_id, handover_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_tombstone (
        tenant_id TEXT NOT NULL,
        ref_id TEXT NOT NULL,
        revoked_at INTEGER NOT NULL,
        PRIMARY KEY(tenant_id, ref_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sv7_security_event (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        at INTEGER NOT NULL,
        kind TEXT NOT NULL,
        detail TEXT NOT NULL
    )""",
    """CREATE TRIGGER IF NOT EXISTS sv7_home_immutable
        BEFORE UPDATE ON sv7_kb
        WHEN NEW.home_space_id IS NOT OLD.home_space_id
        BEGIN
            SELECT RAISE(ABORT, 'HOME_SPACE_IMMUTABLE');
        END""",
    """CREATE TRIGGER IF NOT EXISTS sv7_no_parent_space_column
        BEFORE INSERT ON sv7_space
        BEGIN
            SELECT RAISE(ABORT, 'PARENT_SPACE_FORBIDDEN')
            WHERE EXISTS (
                SELECT 1 FROM pragma_table_info('sv7_space') WHERE name='parent_space_id'
            );
        END""",
)

_BOOTSTRAP_META = (
    ('sandbox_schema_version', str(SANDBOX_SCHEMA_VERSION)),
    ('schema_v7_prod_migration_authorized', 'false'),
    ('formal_t01_t27_accepted', 'false'),
    ('prefix', TABLE_PREFIX),
)


class SchemaV6StoreRefused(RuntimeError):
    """Raised when a disposable sandbox is pointed at a Schema v6 store."""


class SandboxClosed(RuntimeError):
    pass


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def assert_not_production_v6(conn):
    names = _table_names(conn)
    hits = sorted(names & PRODUCTION_V6_TABLES)
    if hits:
        raise SchemaV6StoreRefused(
            'refusing to open or migrate a Schema v6 / production-like store: '
            + ','.join(hits)
        )
    if 'schema_migrations' in names:
        raise SchemaV6StoreRefused('refusing schema_migrations (Schema v6 marker)')


def migrate(conn):
    """Idempotent additive install of sandbox sv7_* objects. Never a v6 upgrade."""
    assert_not_production_v6(conn)
    conn.execute('PRAGMA foreign_keys=ON')
    for statement in _MIGRATE_STATEMENTS:
        conn.execute(statement)
    for key, value in _BOOTSTRAP_META:
        conn.execute(
            'INSERT OR IGNORE INTO sv7_meta(key, value) VALUES(?, ?)',
            (key, value),
        )
    row = conn.execute(
        "SELECT value FROM sv7_meta WHERE key='sandbox_schema_version'"
    ).fetchone()
    if row is None or int(row[0]) != SANDBOX_SCHEMA_VERSION:
        raise RuntimeError('sandbox schema version mismatch')
    # Re-running migrate must not rewrite security state.
    return SANDBOX_SCHEMA_VERSION


def rollback(conn):
    """Idempotent rollback: drop sandbox objects. Does not restore ACLs."""
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        for table in SANDBOX_TABLES:
            conn.execute('DROP TABLE IF EXISTS ' + table)
        conn.execute('DROP TRIGGER IF EXISTS sv7_home_immutable')
        conn.execute('DROP TRIGGER IF EXISTS sv7_no_parent_space_column')
    finally:
        conn.execute('PRAGMA foreign_keys=ON')
    # A second call is a no-op. Historical grants are gone and must not
    # be re-applied from this function.
    return True


def sandbox_version(conn):
    names = _table_names(conn)
    if 'sv7_meta' not in names:
        return None
    row = conn.execute(
        "SELECT value FROM sv7_meta WHERE key='sandbox_schema_version'"
    ).fetchone()
    return int(row[0]) if row else None


class DisposableSQLite:
    """Owns a newly created in-memory or throwaway-file SQLite connection."""

    def __init__(self, conn, tmp_path=None, tmp_dir=None):
        self.conn = conn
        self._tmp_path = tmp_path
        self._tmp_dir = tmp_dir
        self._closed = False

    @classmethod
    def in_memory(cls):
        conn = sqlite3.connect(':memory:', isolation_level=None)
        conn.execute('PRAGMA foreign_keys=ON')
        assert_not_production_v6(conn)
        migrate(conn)
        return cls(conn)

    @classmethod
    def throwaway_file(cls):
        tmp_dir = tempfile.mkdtemp(prefix='sv7_sandbox_')
        path = str(Path(tmp_dir) / 'sandbox.sqlite')
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute('PRAGMA foreign_keys=ON')
        assert_not_production_v6(conn)
        migrate(conn)
        return cls(conn, tmp_path=path, tmp_dir=tmp_dir)

    def close(self):
        if self._closed:
            return
        try:
            self.conn.close()
        finally:
            self._closed = True
            if self._tmp_path and os.path.exists(self._tmp_path):
                os.remove(self._tmp_path)
            if self._tmp_dir and os.path.isdir(self._tmp_dir):
                try:
                    os.rmdir(self._tmp_dir)
                except OSError:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
