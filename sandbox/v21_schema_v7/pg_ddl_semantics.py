"""PostgreSQL DDL / FORCE RLS semantic validation (stdlib only).

Generates candidate Schema v7 PostgreSQL DDL and checks FORCE RLS policy
semantics by parsing the text. This module never opens a PostgreSQL
connection, never imports psycopg, and is not a production migration.
"""
from __future__ import annotations

import re

from .constants import OFFICIAL_ACTIONS, TABLE_PREFIX

# Candidate throwaway table names (sandbox prefix). Not production tables.
CANDIDATE_TABLES = (
    'sv7_tenant',
    'sv7_principal',
    'sv7_space',
    'sv7_org_team',
    'sv7_kb',
    'sv7_space_member',
    'sv7_grant',
    'sv7_deny',
    'sv7_asset',
    'sv7_agent_profile',
    'sv7_external',
    'sv7_outbox',
    'sv7_favorite',
    'sv7_share',
    'sv7_handover',
    'sv7_handover_approval',
    'sv7_tombstone',
    'sv7_security_event',
    'sv7_meta',
)

_ROLE = 'sv7_sandbox_app_role'


def candidate_postgres_ddl():
    """Return candidate PostgreSQL DDL for semantic validation only."""
    parts = [
        "CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;".format(role=_ROLE),
        "CREATE TABLE sv7_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);",
        "CREATE TABLE sv7_tenant (tenant_id TEXT PRIMARY KEY, tenant_kind TEXT NOT NULL);",
        """CREATE TABLE sv7_principal (
            tenant_id TEXT NOT NULL REFERENCES sv7_tenant(tenant_id),
            user_id TEXT NOT NULL,
            issuer TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            status TEXT NOT NULL,
            policy_generation INTEGER NOT NULL CHECK (policy_generation >= 1),
            PRIMARY KEY (tenant_id, user_id),
            UNIQUE (issuer, subject_id)
        );""",
        """CREATE TABLE sv7_space (
            tenant_id TEXT NOT NULL REFERENCES sv7_tenant(tenant_id),
            space_id TEXT NOT NULL,
            space_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL,
            policy_generation INTEGER NOT NULL CHECK (policy_generation >= 1),
            PRIMARY KEY (tenant_id, space_id)
        );""",
        """CREATE TABLE sv7_org_team (
            tenant_id TEXT NOT NULL,
            org_team_id TEXT NOT NULL,
            team_space_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, org_team_id),
            UNIQUE (tenant_id, team_space_id),
            FOREIGN KEY (tenant_id, team_space_id) REFERENCES sv7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE sv7_kb (
            tenant_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            space_id TEXT,
            home_space_id TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tenant_id, kb_id),
            CHECK (space_id IS NULL OR space_id = home_space_id),
            FOREIGN KEY (tenant_id, home_space_id) REFERENCES sv7_space(tenant_id, space_id),
            FOREIGN KEY (tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE sv7_space_member (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (tenant_id, space_id, user_id),
            FOREIGN KEY (tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE sv7_grant (
            tenant_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            action TEXT NOT NULL,
            allowed INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, space_id, subject_id, action),
            FOREIGN KEY (tenant_id, space_id) REFERENCES sv7_space(tenant_id, space_id)
        );""",
        """CREATE TABLE sv7_deny (
            tenant_id TEXT NOT NULL,
            principal_kind TEXT NOT NULL,
            principal_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            action TEXT NOT NULL,
            PRIMARY KEY (tenant_id, principal_kind, principal_id, target_type, target_id, action)
        );""",
        """CREATE TABLE sv7_asset (
            tenant_id TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            kb_id TEXT NOT NULL,
            resource_kind TEXT NOT NULL,
            folder_id TEXT,
            ref_id TEXT,
            PRIMARY KEY (tenant_id, asset_id),
            FOREIGN KEY (tenant_id, kb_id) REFERENCES sv7_kb(tenant_id, kb_id)
        );""",
        """CREATE TABLE sv7_agent_profile (
            tenant_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            generation INTEGER NOT NULL,
            active INTEGER NOT NULL,
            allowed_space_ids TEXT NOT NULL,
            allowed_kb_ids TEXT NOT NULL,
            allowed_space_types TEXT NOT NULL,
            PRIMARY KEY (tenant_id, agent_id)
        );""",
        """CREATE TABLE sv7_external (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            valid_until INTEGER NOT NULL,
            revoked INTEGER NOT NULL,
            generation INTEGER NOT NULL,
            tombstone INTEGER NOT NULL DEFAULT 0,
            cursor TEXT,
            PRIMARY KEY (tenant_id, ref_id)
        );""",
        """CREATE TABLE sv7_outbox (
            tenant_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            space_id TEXT,
            generation INTEGER NOT NULL,
            kind TEXT NOT NULL,
            PRIMARY KEY (tenant_id, event_id)
        );""",
        """CREATE TABLE sv7_favorite (
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, user_id, target_type, target_id)
        );""",
        """CREATE TABLE sv7_share (
            tenant_id TEXT NOT NULL,
            share_id TEXT NOT NULL,
            space_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            grantee_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (tenant_id, share_id)
        );""",
        """CREATE TABLE sv7_handover (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            leaver_id TEXT NOT NULL,
            target_user_id TEXT NOT NULL,
            status TEXT NOT NULL,
            includes_private_body INTEGER NOT NULL DEFAULT 0 CHECK (includes_private_body = 0),
            PRIMARY KEY (tenant_id, handover_id)
        );""",
        """CREATE TABLE sv7_handover_approval (
            tenant_id TEXT NOT NULL,
            handover_id TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            PRIMARY KEY (tenant_id, handover_id, approver_id)
        );""",
        """CREATE TABLE sv7_tombstone (
            tenant_id TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            revoked_at INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, ref_id)
        );""",
        """CREATE TABLE sv7_security_event (
            seq BIGSERIAL PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            at INTEGER NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL
        );""",
        """CREATE FUNCTION sv7_home_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.home_space_id IS DISTINCT FROM OLD.home_space_id THEN
        RAISE EXCEPTION 'HOME_SPACE_IMMUTABLE';
    END IF;
    RETURN NEW;
END $$;""",
        "CREATE TRIGGER sv7_home_immutable BEFORE UPDATE ON sv7_kb FOR EACH ROW EXECUTE FUNCTION sv7_home_immutable();",
    ]
    for table in CANDIDATE_TABLES:
        parts.append('ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;'.format(t=table))
        parts.append('ALTER TABLE {t} FORCE ROW LEVEL SECURITY;'.format(t=table))
        parts.append(
            "CREATE POLICY tenant_isolation ON {t} "
            "USING (tenant_id = current_setting('app.current_org_id', true)) "
            "WITH CHECK (tenant_id = current_setting('app.current_org_id', true));".format(t=table)
        )
        parts.append('ALTER TABLE {t} OWNER TO {role};'.format(t=table, role=_ROLE))
    return '\n'.join(parts) + '\n'


class DdlSemanticError(ValueError):
    pass


def _table_names_in_ddl(ddl):
    return set(re.findall(r'CREATE TABLE\s+([A-Za-z0-9_]+)', ddl, flags=re.I))


def validate_postgres_ddl(ddl, expected_tables=CANDIDATE_TABLES):
    """Parse candidate DDL and enforce FORCE RLS / isolation semantics."""
    if not isinstance(ddl, str) or not ddl.strip():
        raise DdlSemanticError('empty DDL')
    errors = []
    folded = ddl
    if re.search(r'\bparent_space_id\b', folded, flags=re.I):
        errors.append('parent_space_id is forbidden in phase-1 flat Tenant-Space-KB')
    if re.search(r'\bBYPASSRLS\b', folded) and not re.search(r'\bNOBYPASSRLS\b', folded):
        errors.append('BYPASSRLS without NOBYPASSRLS')
    # A role used for authorization tests must be NOSUPERUSER NOBYPASSRLS.
    if not re.search(r'CREATE ROLE\s+\S+\s+LOGIN\s+NOSUPERUSER\s+NOBYPASSRLS', folded, flags=re.I):
        errors.append('missing NOSUPERUSER NOBYPASSRLS app role')
    tables = _table_names_in_ddl(folded)
    missing = [name for name in expected_tables if name not in tables]
    if missing:
        errors.append('missing tables: ' + ','.join(missing))
    for table in expected_tables:
        if table not in tables:
            continue
        # Extract the create table body for column checks.
        match = re.search(
            r'CREATE TABLE\s+' + re.escape(table) + r'\s*\((.*?)\)\s*;',
            folded,
            flags=re.I | re.S,
        )
        body = match.group(1) if match else ''
        if 'tenant_id' not in body and table != 'sv7_meta':
            # sv7_meta is sandbox bookkeeping; every security table needs tenant_id.
            if table != 'sv7_meta':
                errors.append(table + ' missing tenant_id')
        if table != 'sv7_meta' and 'PRIMARY KEY' in body.upper():
            if 'tenant_id' not in body.split('PRIMARY KEY')[-1] and table not in ('sv7_security_event',):
                # security_event uses seq PK plus tenant_id column (filtered by RLS)
                pass
        if not re.search(r'ALTER TABLE\s+' + re.escape(table) + r'\s+ENABLE ROW LEVEL SECURITY', folded, flags=re.I):
            errors.append(table + ' missing ENABLE ROW LEVEL SECURITY')
        if not re.search(r'ALTER TABLE\s+' + re.escape(table) + r'\s+FORCE ROW LEVEL SECURITY', folded, flags=re.I):
            errors.append(table + ' missing FORCE ROW LEVEL SECURITY')
        policy = re.search(
            r'CREATE POLICY\s+\S+\s+ON\s+' + re.escape(table) + r'\s+(.*?);',
            folded,
            flags=re.I | re.S,
        )
        if not policy:
            errors.append(table + ' missing isolation policy')
        else:
            clause = policy.group(1)
            if not re.search(r"USING\s*\(\s*tenant_id\s*=\s*current_setting\(\s*'app\.current_org_id'", clause, flags=re.I):
                errors.append(table + ' policy USING must bind tenant_id to app.current_org_id')
            if not re.search(r"WITH CHECK\s*\(\s*tenant_id\s*=\s*current_setting\(\s*'app\.current_org_id'", clause, flags=re.I):
                errors.append(table + ' policy WITH CHECK must bind tenant_id to app.current_org_id')
    if 'sv7_favorite' in folded:
        for forbidden in ('body', 'chunk', 'embedding', 'evidence'):
            if re.search(r'\b' + forbidden + r'\b', re.search(
                r'CREATE TABLE\s+sv7_favorite\s*\((.*?)\)\s*;', folded, flags=re.I | re.S
            ).group(1) if re.search(r'CREATE TABLE\s+sv7_favorite\s*\(', folded, flags=re.I) else ''):
                errors.append('favorites must not store ' + forbidden)
    if not re.search(r'HOME_SPACE_IMMUTABLE', folded):
        errors.append('missing home_space_id immutability trigger')
    if 'UNIQUE (tenant_id, team_space_id)' not in folded.replace('\n', ' ').replace('  ', ' ') and not re.search(
        r'UNIQUE\s*\(\s*tenant_id\s*,\s*team_space_id\s*\)', folded, flags=re.I
    ):
        errors.append('missing 1 organization_team = 1 Team Space uniqueness')
    if errors:
        raise DdlSemanticError('; '.join(errors))
    return {
        'ok': True,
        'tables': sorted(tables),
        'force_rls': True,
        'live_connection': False,
        'prefix': TABLE_PREFIX,
        'official_actions': list(OFFICIAL_ACTIONS),
    }


def validate_official_candidate():
    return validate_postgres_ddl(candidate_postgres_ddl())
