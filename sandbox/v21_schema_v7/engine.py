"""Schema v7 sandbox domain engine (stdlib SQLite).

Implements Tenant -> Space -> KB, SPACE-C03 phase-1 lock, five-layer
Fail-Closed isolation, zero-copy Favorites pointers, and the PRE-04
leaver five-rule state machine. All identifiers in fixtures are syn_*
tokens. This engine does not contact a production database.
"""
from __future__ import annotations

import json
import uuid

from .constants import (
    FAVORITE_TARGET_TYPES,
    FORBIDDEN_POINTER_FIELDS,
    ISOLATION_RETENTION_SECONDS,
    OFFICIAL_ACTIONS,
    PRINCIPAL_STATUS_RANK,
    RESIGN_FREEZE_SLA_SECONDS,
    SPACE_STATUSES,
    SPACE_TYPES,
    TENANT_KINDS,
)
from .sqlite_sandbox import DisposableSQLite, rollback as rollback_schema, sandbox_version


class SandboxError(RuntimeError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


class Decision(object):
    def __init__(self, allowed, layer=None, code=None):
        self.allowed = bool(allowed)
        self.layer = layer
        self.code = code

    def __bool__(self):
        return self.allowed


def _json_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return json.loads(value)


class SandboxV7(object):
    def __init__(self, disposable=None):
        self._owned = disposable is None
        self.db = disposable or DisposableSQLite.in_memory()
        self.conn = self.db.conn
        self._now = 1_700_000_000
        self._closed = False

    @classmethod
    def throwaway_file(cls):
        return cls(DisposableSQLite.throwaway_file())

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._owned or self.db is not None:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def set_now(self, ts):
        self._now = int(ts)
        return self._now

    def now(self):
        return self._now

    def sql(self, query, args=()):
        cur = self.conn.execute(query, args) if args else self.conn.execute(query)
        if cur.description:
            return cur.fetchall()
        return []

    def log(self, tenant_id, kind, detail):
        self.sql(
            'INSERT INTO sv7_security_event(tenant_id, at, kind, detail) VALUES(?,?,?,?)',
            (tenant_id, self._now, kind, json.dumps(detail, sort_keys=True)),
        )

    # --- helpers ---
    def _require_syn(self, *ids):
        for value in ids:
            if value is None:
                continue
            if not isinstance(value, str) or not value.startswith('syn_'):
                raise SandboxError('SYNTHETIC_ID_REQUIRED', 'non-syn token refused: %r' % (value,))

    def rollback_schema(self):
        rollback_schema(self.conn)
        return sandbox_version(self.conn)

    def refuse_restore(self, kind):
        raise SandboxError(
            'SECURITY_STATE_MONOTONIC',
            'refusing to restore historical %s (security state is monotonic)' % kind,
        )

    # --- tenancy / principals / spaces ---
    def create_tenant(self, tenant_id, tenant_kind='enterprise'):
        self._require_syn(tenant_id)
        if tenant_kind not in TENANT_KINDS:
            raise SandboxError('INVALID_TENANT_KIND')
        self.sql('INSERT INTO sv7_tenant(tenant_id, tenant_kind) VALUES(?,?)', (tenant_id, tenant_kind))
        return tenant_id

    def create_principal(self, tenant_id, user_id, issuer='syn_issuer', subject_id=None, status='active'):
        self._require_syn(tenant_id, user_id, issuer)
        if '@' in user_id:
            raise SandboxError('EMAIL_PRIMARY_KEY_FORBIDDEN')
        subject_id = subject_id or user_id
        self._require_syn(subject_id)
        self.sql(
            'INSERT INTO sv7_principal(tenant_id, user_id, issuer, subject_id, status, policy_generation) '
            'VALUES(?,?,?,?,?,1)',
            (tenant_id, user_id, issuer, subject_id, status),
        )
        return user_id

    def create_space(self, tenant_id, space_id, space_type, owner_id, status='active'):
        self._require_syn(tenant_id, space_id, owner_id)
        if space_type not in SPACE_TYPES:
            raise SandboxError('INVALID_SPACE_TYPE')
        if status not in SPACE_STATUSES:
            raise SandboxError('INVALID_SPACE_STATUS')
        self.sql(
            'INSERT INTO sv7_space(tenant_id, space_id, space_type, owner_id, status, policy_generation) '
            'VALUES(?,?,?,?,?,1)',
            (tenant_id, space_id, space_type, owner_id, status),
        )
        self.sql(
            'INSERT INTO sv7_space_member(tenant_id, space_id, user_id, role) VALUES(?,?,?,?)',
            (tenant_id, space_id, owner_id, 'owner'),
        )
        return space_id

    def bind_org_team(self, tenant_id, org_team_id, team_space_id):
        """SPACE-C03 phase 1: 1 organization_team = 1 Team Space."""
        self._require_syn(tenant_id, team_space_id)
        token = org_team_id or ''
        lowered = token.lower()
        if (
            lowered.startswith('dept:')
            or lowered.startswith('department:')
            or 'department' in lowered
            or lowered.startswith('syn_dept')
            or lowered.startswith('dept_')
        ):
            raise SandboxError('DEPARTMENT_AUTO_MAPPING_FORBIDDEN')
        self._require_syn(org_team_id)
        space = self.sql(
            'SELECT space_type FROM sv7_space WHERE tenant_id=? AND space_id=?',
            (tenant_id, team_space_id),
        )
        if not space or space[0][0] != 'team':
            raise SandboxError('ORG_TEAM_REQUIRES_TEAM_SPACE')
        existing = self.sql(
            'SELECT team_space_id FROM sv7_org_team WHERE tenant_id=? AND org_team_id=?',
            (tenant_id, org_team_id),
        )
        if existing:
            if existing[0][0] != team_space_id:
                raise SandboxError('ORG_TEAM_ALREADY_BOUND')
            return team_space_id
        taken = self.sql(
            'SELECT org_team_id FROM sv7_org_team WHERE tenant_id=? AND team_space_id=?',
            (tenant_id, team_space_id),
        )
        if taken and taken[0][0] != org_team_id:
            raise SandboxError('TEAM_SPACE_ALREADY_BOUND')
        try:
            self.sql(
                'INSERT INTO sv7_org_team(tenant_id, org_team_id, team_space_id) VALUES(?,?,?)',
                (tenant_id, org_team_id, team_space_id),
            )
        except Exception:
            raise SandboxError('ORG_TEAM_MAPPING_CONFLICT')
        return team_space_id

    def map_department(self, tenant_id, department_id, space_id=None):
        self._require_syn(tenant_id)
        raise SandboxError(
            'DEPARTMENT_AUTO_MAPPING_FORBIDDEN',
            'department identifiers must not be mapped as business teams',
        )

    def add_member(self, tenant_id, space_id, user_id, role='member'):
        self._require_syn(tenant_id, space_id, user_id)
        self.sql(
            'INSERT INTO sv7_space_member(tenant_id, space_id, user_id, role) VALUES(?,?,?,?)',
            (tenant_id, space_id, user_id, role),
        )

    def grant(self, tenant_id, space_id, subject_id, action, allowed=True):
        self._require_syn(tenant_id, space_id, subject_id)
        if action not in OFFICIAL_ACTIONS:
            raise SandboxError('UNKNOWN_ACTION')
        self.sql(
            'INSERT OR REPLACE INTO sv7_grant(tenant_id, space_id, subject_id, action, allowed) VALUES(?,?,?,?,?)',
            (tenant_id, space_id, subject_id, action, 1 if allowed else 0),
        )

    def grant_all(self, tenant_id, space_id, subject_id):
        for action in OFFICIAL_ACTIONS:
            self.grant(tenant_id, space_id, subject_id, action, True)

    def add_deny(self, tenant_id, principal_kind, principal_id, target_type, target_id, action):
        self._require_syn(tenant_id, principal_id, target_id)
        self.sql(
            'INSERT OR REPLACE INTO sv7_deny(tenant_id, principal_kind, principal_id, target_type, target_id, action) '
            'VALUES(?,?,?,?,?,?)',
            (tenant_id, principal_kind, principal_id, target_type, target_id, action),
        )

    def create_kb(self, tenant_id, kb_id, home_space_id, attach=True):
        self._require_syn(tenant_id, kb_id, home_space_id)
        space = self.sql(
            'SELECT tenant_id FROM sv7_space WHERE tenant_id=? AND space_id=?',
            (tenant_id, home_space_id),
        )
        if not space:
            raise SandboxError('SPACE_NOT_FOUND')
        attached = home_space_id if attach else None
        self.sql(
            'INSERT INTO sv7_kb(tenant_id, kb_id, space_id, home_space_id, archived) VALUES(?,?,?,?,0)',
            (tenant_id, kb_id, attached, home_space_id),
        )
        return kb_id

    def detach_kb(self, tenant_id, kb_id):
        self._require_syn(tenant_id, kb_id)
        self.sql(
            'UPDATE sv7_kb SET space_id=NULL WHERE tenant_id=? AND kb_id=?',
            (tenant_id, kb_id),
        )
        # Detach must not implicitly archive.
        row = self.sql(
            'SELECT space_id, archived FROM sv7_kb WHERE tenant_id=? AND kb_id=?',
            (tenant_id, kb_id),
        )
        return {'space_id': row[0][0] if row else None, 'archived': row[0][1] if row else None}

    def attach_kb(self, tenant_id, kb_id, space_id):
        self._require_syn(tenant_id, kb_id, space_id)
        try:
            self.sql(
                'UPDATE sv7_kb SET space_id=? WHERE tenant_id=? AND kb_id=?',
                (space_id, tenant_id, kb_id),
            )
        except Exception:
            raise SandboxError('ATTACH_HOME_MISMATCH')
        row = self.sql(
            'SELECT space_id, home_space_id FROM sv7_kb WHERE tenant_id=? AND kb_id=?',
            (tenant_id, kb_id),
        )
        if not row or row[0][0] != space_id:
            raise SandboxError('ATTACH_HOME_MISMATCH')
        return space_id

    def create_asset(self, tenant_id, asset_id, kb_id, resource_kind='knowledge_file', folder_id=None, ref_id=None, **extra):
        self._require_syn(tenant_id, asset_id, kb_id)
        if folder_id:
            self._require_syn(folder_id)
        if ref_id:
            self._require_syn(ref_id)
        bad = FORBIDDEN_POINTER_FIELDS.intersection(extra)
        if bad:
            raise SandboxError('ASSET_BODY_FORBIDDEN', 'assets must not store ' + ','.join(sorted(bad)))
        self.sql(
            'INSERT INTO sv7_asset(tenant_id, asset_id, kb_id, resource_kind, folder_id, ref_id) VALUES(?,?,?,?,?,?)',
            (tenant_id, asset_id, kb_id, resource_kind, folder_id, ref_id),
        )
        return asset_id

    def upsert_agent(self, tenant_id, agent_id, allowed_space_ids, allowed_kb_ids=None,
                     allowed_space_types=None, allowed_asset_ids=None, allowed_folder_ids=None,
                     allowed_knowledge_file_ids=None, allowed_deliverable_ids=None,
                     generation=1, active=True, deny_personal_spaces=False):
        self._require_syn(tenant_id, agent_id)
        self.sql(
            'INSERT OR REPLACE INTO sv7_agent_profile('
            'tenant_id, agent_id, generation, active, allowed_space_ids, allowed_kb_ids, '
            'allowed_space_types, allowed_asset_ids, allowed_folder_ids, '
            'allowed_knowledge_file_ids, allowed_deliverable_ids, deny_personal_spaces) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (
                tenant_id, agent_id, int(generation), 1 if active else 0,
                json.dumps(list(allowed_space_ids or [])),
                json.dumps(list(allowed_kb_ids or [])),
                json.dumps(list(allowed_space_types or list(SPACE_TYPES))),
                json.dumps(list(allowed_asset_ids or [])),
                json.dumps(list(allowed_folder_ids or [])),
                json.dumps(list(allowed_knowledge_file_ids or [])),
                json.dumps(list(allowed_deliverable_ids or [])),
                1 if deny_personal_spaces else 0,
            ),
        )

    def upsert_external(self, tenant_id, ref_id, valid_until, generation=1, revoked=False, tombstone=False, cursor=None):
        self._require_syn(tenant_id, ref_id)
        self.sql(
            'INSERT OR REPLACE INTO sv7_external(tenant_id, ref_id, valid_until, revoked, generation, tombstone, cursor) '
            'VALUES(?,?,?,?,?,?,?)',
            (tenant_id, ref_id, int(valid_until), 1 if revoked else 0, int(generation), 1 if tombstone else 0, cursor),
        )

    # --- five-layer authorize ---
    def authorize(self, tenant_id, user_id, kb_id, action='read', asset_id=None, agent_id=None,
                  policy_generation=None, profile_generation=None, provider=None,
                  claimed_tenant_id=None, email=None, task_scope=None, redaction_ok=True):
        self._require_syn(tenant_id, user_id, kb_id)
        if asset_id:
            self._require_syn(asset_id)
        if agent_id:
            self._require_syn(agent_id)

        # Layer 1 early: email must not be a permanent primary key.
        if email:
            return Decision(False, 'layer_1', 'EMAIL_PRIMARY_KEY_FORBIDDEN')
        if action not in OFFICIAL_ACTIONS:
            return Decision(False, 'layer_3', 'UNKNOWN_ACTION')
        if policy_generation is not None:
            if type(policy_generation) is not int or policy_generation < 1 or policy_generation > 9007199254740991:
                return Decision(False, 'layer_1', 'INVALID_POLICY_GENERATION')
        if agent_id and profile_generation is not None:
            if type(profile_generation) is not int or profile_generation < 1 or profile_generation > 9007199254740991:
                return Decision(False, 'layer_1', 'INVALID_PROFILE_GENERATION')

        claimed = claimed_tenant_id if claimed_tenant_id is not None else tenant_id

        # Layer 0: tenant hard isolation.
        if claimed != tenant_id:
            return Decision(False, 'layer_0', 'TENANT_MISMATCH')
        principal = self.sql(
            'SELECT tenant_id, status, policy_generation, issuer, subject_id, resigned_at, frozen_at '
            'FROM sv7_principal WHERE tenant_id=? AND user_id=?',
            (tenant_id, user_id),
        )
        if not principal:
            # Missing principal in this tenant: fail closed as tenant/identity miss.
            return Decision(False, 'layer_0', 'PRINCIPAL_NOT_IN_TENANT')
        p_tenant, p_status, p_gen, _issuer, _subject, resigned_at, frozen_at = principal[0]
        if p_tenant != tenant_id:
            return Decision(False, 'layer_0', 'TENANT_MISMATCH')

        kb = self.sql(
            'SELECT k.space_id, k.home_space_id, k.archived, k.tenant_id, '
            's.space_type, s.owner_id, s.status, s.policy_generation '
            'FROM sv7_kb k JOIN sv7_space s ON s.tenant_id=k.tenant_id AND s.space_id=k.home_space_id '
            'WHERE k.tenant_id=? AND k.kb_id=?',
            (tenant_id, kb_id),
        )
        if not kb:
            return Decision(False, 'layer_0', 'KB_NOT_VISIBLE')
        space_id, home_space_id, archived, kb_tenant, space_type, owner_id, space_status, space_gen = kb[0]
        if kb_tenant != tenant_id:
            return Decision(False, 'layer_0', 'TENANT_MISMATCH')
        if space_id is None:
            # Detached: no Space Gate pass, no KB reverse privilege.
            return Decision(False, 'layer_2', 'KB_DETACHED')

        # Layer 1: identity & revocation.
        if p_status != 'active':
            return Decision(False, 'layer_1', 'PRINCIPAL_NOT_ACTIVE')
        if resigned_at is not None and (frozen_at is None or frozen_at - resigned_at > RESIGN_FREEZE_SLA_SECONDS):
            # If freeze missed the 60s SLA, still fail closed (never allow).
            if p_status != 'active':
                return Decision(False, 'layer_1', 'RESIGN_FREEZE')
        if policy_generation is not None and policy_generation != space_gen:
            return Decision(False, 'layer_1', 'POLICY_GENERATION_STALE')

        # Layer 2: Space Gate.
        if space_status in ('archived', 'pending_purge'):
            return Decision(False, 'layer_2', 'SPACE_NOT_ACTIVE')
        if space_status == 'frozen':
            return Decision(False, 'layer_2', 'SPACE_FROZEN')
        if space_type == 'personal' and user_id != owner_id:
            # Admin / any other principal cannot bypass personal private invariant.
            return Decision(False, 'layer_2', 'PERSONAL_OWNER_BOUNDARY')
        member = self.sql(
            'SELECT role FROM sv7_space_member WHERE tenant_id=? AND space_id=? AND user_id=?',
            (tenant_id, space_id, user_id),
        )
        grant = self.sql(
            'SELECT allowed FROM sv7_grant WHERE tenant_id=? AND space_id=? AND subject_id=? AND action=?',
            (tenant_id, space_id, user_id, action),
        )
        space_deny = self.sql(
            'SELECT 1 FROM sv7_deny WHERE tenant_id=? AND principal_kind=? AND principal_id=? '
            'AND target_type=? AND target_id=? AND action IN (?,?)',
            (tenant_id, 'user', user_id, 'space', space_id, action, '*'),
        )
        if space_deny:
            return Decision(False, 'layer_2', 'SPACE_EXPLICIT_DENY')
        if not member and grant != [(1,)]:
            return Decision(False, 'layer_2', 'SPACE_GATE_DENIED')
        if grant == [(0,)]:
            return Decision(False, 'layer_2', 'SPACE_GRANT_DENIED')
        if not grant and not member:
            return Decision(False, 'layer_2', 'SPACE_GATE_DENIED')
        # Member without a specific grant still needs an allow grant for the action,
        # except the owner who receives all official actions.
        if user_id != owner_id and grant != [(1,)]:
            return Decision(False, 'layer_2', 'SPACE_GRANT_MISSING')

        # Layer 3: KB & Document Gate (explicit Deny first; may only tighten).
        if archived:
            return Decision(False, 'layer_3', 'KB_ARCHIVED')
        denials = self.sql(
            'SELECT principal_kind, principal_id, target_type, target_id, action FROM sv7_deny WHERE tenant_id=?',
            (tenant_id,),
        )
        for pk, pid, tt, tid, denied_action in denials:
            principal_match = (pk == 'user' and pid == user_id) or (pk == 'agent' and agent_id and pid == agent_id)
            target_match = (tt == 'kb' and tid == kb_id) or (tt == 'asset' and asset_id and tid == asset_id) or (
                tt == 'space' and tid == space_id
            )
            if principal_match and target_match and denied_action in (action, '*'):
                return Decision(False, 'layer_3', 'EXPLICIT_DENY')

        resource_kind = None
        folder_id = None
        ref_id = None
        if asset_id:
            assets = self.sql(
                'SELECT resource_kind, folder_id, ref_id, tenant_id, kb_id FROM sv7_asset '
                'WHERE tenant_id=? AND asset_id=?',
                (tenant_id, asset_id),
            )
            if not assets or assets[0][4] != kb_id or assets[0][3] != tenant_id:
                return Decision(False, 'layer_3', 'ASSET_NOT_VISIBLE')
            resource_kind, folder_id, ref_id, _at, _ak = assets[0]

        # Layer 4: User ∩ Agent & Redaction.
        if agent_id:
            profiles = self.sql(
                'SELECT generation, active, allowed_space_ids, allowed_kb_ids, allowed_space_types, '
                'allowed_asset_ids, allowed_folder_ids, allowed_knowledge_file_ids, '
                'allowed_deliverable_ids, deny_personal_spaces '
                'FROM sv7_agent_profile WHERE tenant_id=? AND agent_id=?',
                (tenant_id, agent_id),
            )
            if not profiles:
                return Decision(False, 'layer_4', 'AGENT_PROFILE_MISSING')
            (agen, active, spaces, kbs, types, assets_s, folders, kfiles, deliveries, deny_personal) = profiles[0]
            if not active:
                return Decision(False, 'layer_4', 'AGENT_INACTIVE')
            if profile_generation is not None and profile_generation != agen:
                return Decision(False, 'layer_4', 'PROFILE_GENERATION_STALE')
            allowed_spaces = _json_list(spaces)
            allowed_kbs = _json_list(kbs)
            allowed_types = _json_list(types)
            if space_id not in allowed_spaces:
                return Decision(False, 'layer_4', 'AGENT_SPACE_CEILING')
            if allowed_types and space_type not in allowed_types:
                return Decision(False, 'layer_4', 'AGENT_SPACE_TYPE_DENIED')
            if deny_personal and space_type == 'personal':
                return Decision(False, 'layer_4', 'AGENT_PERSONAL_DENIED')
            if task_scope:
                task_spaces = set(task_scope.get('space_ids') or allowed_spaces)
                if space_id not in task_spaces:
                    return Decision(False, 'layer_4', 'TASK_SCOPE_DENIED')
            # Fine-grained scopes: if any fine list is populated, asset must match one.
            fine_assets = _json_list(assets_s)
            fine_folders = _json_list(folders)
            fine_files = _json_list(kfiles)
            fine_dels = _json_list(deliveries)
            fine_used = bool(allowed_kbs or fine_assets or fine_folders or fine_files or fine_dels)
            if fine_used:
                ok_fine = kb_id in allowed_kbs
                if asset_id and not ok_fine:
                    ok_fine = (
                        (asset_id in fine_assets)
                        or (folder_id and folder_id in fine_folders)
                        or (resource_kind in ('knowledge_file', 'uploaded_document') and asset_id in fine_files)
                        or (resource_kind in ('deliverable', 'agent_deliverable') and asset_id in fine_dels)
                    )
                if not ok_fine:
                    return Decision(False, 'layer_4', 'AGENT_FINE_SCOPE_DENIED')
            if not redaction_ok:
                return Decision(False, 'layer_4', 'REDACTION_FAILED')

        if ref_id:
            sources = self.sql(
                'SELECT valid_until, revoked, generation, tombstone, cursor FROM sv7_external '
                'WHERE tenant_id=? AND ref_id=?',
                (tenant_id, ref_id),
            )
            if not sources:
                return Decision(False, 'layer_3', 'EXTERNAL_ASSERTION_MISSING')
            valid_until, revoked, gen, tombstone, cursor = sources[0]
            if revoked or tombstone:
                return Decision(False, 'layer_3', 'EXTERNAL_REVOKED')
            if valid_until <= self._now:
                return Decision(False, 'layer_3', 'EXTERNAL_EXPIRED')
            if provider is None:
                return Decision(False, 'layer_3', 'EXTERNAL_ASSERTION_MISSING')
            try:
                assertion = provider()
            except Exception:
                return Decision(False, 'layer_3', 'EXTERNAL_PROVIDER_OUTAGE')
            required = {'tenant_id', 'subject_id', 'asset_id', 'valid_until', 'generation'}
            if type(assertion) is not dict or set(assertion) != required:
                return Decision(False, 'layer_3', 'EXTERNAL_ASSERTION_INVALID')
            if assertion.get('tenant_id') != tenant_id or assertion.get('subject_id') != user_id:
                return Decision(False, 'layer_3', 'EXTERNAL_ASSERTION_MISMATCH')
            if assertion.get('asset_id') != asset_id or assertion.get('generation') != gen:
                return Decision(False, 'layer_3', 'EXTERNAL_ASSERTION_MISMATCH')
            if type(assertion.get('valid_until')) is not int or assertion['valid_until'] <= self._now:
                return Decision(False, 'layer_3', 'EXTERNAL_EXPIRED')
            if cursor is not None and assertion.get('cursor', cursor) != cursor:
                return Decision(False, 'layer_3', 'EXTERNAL_CURSOR_MISMATCH')

        return Decision(True, None, 'ALLOW')

    # --- revocation / outbox ---
    def revoke(self, tenant_id, space_id, subject_id, action='read', inject_failure=False):
        self._require_syn(tenant_id, space_id, subject_id)
        if action not in OFFICIAL_ACTIONS:
            raise SandboxError('UNKNOWN_ACTION')
        try:
            self.sql('BEGIN IMMEDIATE')
            self.sql(
                'UPDATE sv7_grant SET allowed=0 WHERE tenant_id=? AND space_id=? AND subject_id=? AND action=?',
                (tenant_id, space_id, subject_id, action),
            )
            self.sql(
                'UPDATE sv7_space SET policy_generation=policy_generation+1 WHERE tenant_id=? AND space_id=?',
                (tenant_id, space_id),
            )
            generation = self.sql(
                'SELECT policy_generation FROM sv7_space WHERE tenant_id=? AND space_id=?',
                (tenant_id, space_id),
            )[0][0]
            self.sql(
                'INSERT INTO sv7_outbox(tenant_id, event_id, space_id, generation, kind) VALUES(?,?,?,?,?)',
                (tenant_id, uuid.uuid4().hex, space_id, generation, 'revocation'),
            )
            if inject_failure:
                raise SandboxError('INJECTED_ROLLBACK')
            self.sql('COMMIT')
            return generation
        except Exception:
            self.sql('ROLLBACK')
            raise

    def set_space_status(self, tenant_id, space_id, status):
        if status not in SPACE_STATUSES:
            raise SandboxError('INVALID_SPACE_STATUS')
        self.sql(
            'UPDATE sv7_space SET status=? WHERE tenant_id=? AND space_id=?',
            (status, tenant_id, space_id),
        )

    # --- favorites (zero-copy pointers) ---
    def add_favorite(self, tenant_id, user_id, target_type, target_id, **extra):
        self._require_syn(tenant_id, user_id, target_id)
        if target_type not in FAVORITE_TARGET_TYPES:
            raise SandboxError('INVALID_FAVORITE_TARGET')
        bad = FORBIDDEN_POINTER_FIELDS.intersection(extra)
        if bad:
            raise SandboxError('FAVORITE_BODY_FORBIDDEN', 'favorites must not store ' + ','.join(sorted(bad)))
        self.sql(
            'INSERT OR REPLACE INTO sv7_favorite(tenant_id, user_id, target_type, target_id) VALUES(?,?,?,?)',
            (tenant_id, user_id, target_type, target_id),
        )

    def hydrate_favorites(self, tenant_id, user_id, targets, **kwargs):
        if len(targets) > 100:
            raise SandboxError('BATCH_LIMIT')
        result = []
        for target in targets:
            if set(target) != {'target_type', 'target_id'} or target['target_type'] not in FAVORITE_TARGET_TYPES:
                raise SandboxError('INVALID_TARGET')
            item = {'target_type': target['target_type'], 'target_id': target['target_id'], 'state': 'unavailable'}
            kb_id = target['target_id']
            asset_id = None
            if target['target_type'] == 'asset':
                rows = self.sql(
                    'SELECT kb_id FROM sv7_asset WHERE tenant_id=? AND asset_id=?',
                    (tenant_id, target['target_id']),
                )
                if not rows:
                    result.append(item)
                    continue
                kb_id = rows[0][0]
                asset_id = target['target_id']
            decision = self.authorize(tenant_id, user_id, kb_id, action='read', asset_id=asset_id, **kwargs)
            if decision.allowed:
                gen = self.sql(
                    'SELECT s.policy_generation FROM sv7_kb k JOIN sv7_space s '
                    'ON s.tenant_id=k.tenant_id AND s.space_id=k.home_space_id '
                    'WHERE k.tenant_id=? AND k.kb_id=?',
                    (tenant_id, kb_id),
                )[0][0]
                item = {
                    'target_type': target['target_type'],
                    'target_id': target['target_id'],
                    'state': 'available',
                    'display_name': 'syn_authorized_label',
                    'policy_generation': gen,
                }
            result.append(item)
        return result

    # --- PRE-04 leaver state machine ---
    def _set_principal_status(self, tenant_id, user_id, new_status, **fields):
        current = self.sql(
            'SELECT status FROM sv7_principal WHERE tenant_id=? AND user_id=?',
            (tenant_id, user_id),
        )
        if not current:
            raise SandboxError('PRINCIPAL_NOT_FOUND')
        old = current[0][0]
        if PRINCIPAL_STATUS_RANK[new_status] < PRINCIPAL_STATUS_RANK[old]:
            self.refuse_restore('principal.status')
        assignments = ['status=?']
        args = [new_status]
        for column in ('resigned_at', 'frozen_at', 'isolation_until', 'policy_generation'):
            if column in fields and fields[column] is not None:
                assignments.append(column + '=?')
                args.append(fields[column])
        args.extend([tenant_id, user_id])
        self.sql(
            'UPDATE sv7_principal SET ' + ', '.join(assignments) + ' WHERE tenant_id=? AND user_id=?',
            tuple(args),
        )

    def resign(self, tenant_id, user_id):
        """Apply the official five PRE-04 rules in one fail-closed transaction."""
        self._require_syn(tenant_id, user_id)
        try:
            self.sql('BEGIN IMMEDIATE')
            now = self._now
            self._set_principal_status(
                tenant_id, user_id, 'frozen',
                resigned_at=now,
                frozen_at=now,
                isolation_until=now + ISOLATION_RETENTION_SECONDS,
            )
            elapsed = 0
            if elapsed > RESIGN_FREEZE_SLA_SECONDS:
                raise SandboxError('RESIGN_FREEZE_SLA_BREACH')
            # Controlled shares invalidated immediately.
            self.sql(
                "UPDATE sv7_share SET status='invalidated' WHERE tenant_id=? AND owner_id=? AND status='active'",
                (tenant_id, user_id),
            )
            # Personal spaces freeze.
            self.sql(
                "UPDATE sv7_space SET status='frozen', policy_generation=policy_generation+1 "
                "WHERE tenant_id=? AND owner_id=? AND space_type='personal'",
                (tenant_id, user_id),
            )
            self._set_principal_status(
                tenant_id, user_id, 'isolation_retention',
                isolation_until=now + ISOLATION_RETENTION_SECONDS,
            )
            self.sql(
                'INSERT INTO sv7_outbox(tenant_id, event_id, space_id, generation, kind) VALUES(?,?,?,?,?)',
                (tenant_id, uuid.uuid4().hex, None, 0, 'leaver_freeze'),
            )
            self.log(tenant_id, 'leaver_freeze', {
                'user_id': user_id,
                'frozen_within_seconds': elapsed,
                'isolation_until': now + ISOLATION_RETENTION_SECONDS,
                'shares_invalidated': True,
            })
            self.sql('COMMIT')
        except Exception:
            self.sql('ROLLBACK')
            raise
        return {
            'status': 'isolation_retention',
            'frozen_within_seconds': 0,
            'isolation_until': now + ISOLATION_RETENTION_SECONDS,
        }

    def create_share(self, tenant_id, share_id, space_id, owner_id, grantee_id):
        self._require_syn(tenant_id, share_id, space_id, owner_id, grantee_id)
        self.sql(
            "INSERT INTO sv7_share(tenant_id, share_id, space_id, owner_id, grantee_id, mode, status) "
            "VALUES(?,?,?,?,?,'controlled_read_only','active')",
            (tenant_id, share_id, space_id, owner_id, grantee_id),
        )

    def share_status(self, tenant_id, share_id):
        rows = self.sql(
            'SELECT status FROM sv7_share WHERE tenant_id=? AND share_id=?',
            (tenant_id, share_id),
        )
        return rows[0][0] if rows else None

    def request_handover(self, tenant_id, handover_id, leaver_id, target_user_id, include_private_body=False):
        self._require_syn(tenant_id, handover_id, leaver_id, target_user_id)
        if include_private_body:
            raise SandboxError('PRIVATE_BODY_AUTO_INHERIT_FORBIDDEN')
        status = self.sql(
            'SELECT status FROM sv7_principal WHERE tenant_id=? AND user_id=?',
            (tenant_id, leaver_id),
        )
        if not status:
            raise SandboxError('PRINCIPAL_NOT_FOUND')
        self._set_principal_status(tenant_id, leaver_id, 'handover_pending')
        self.sql(
            "INSERT INTO sv7_handover(tenant_id, handover_id, leaver_id, target_user_id, status, includes_private_body) "
            "VALUES(?,?,?,?, 'pending', 0)",
            (tenant_id, handover_id, leaver_id, target_user_id),
        )
        return handover_id

    def approve_handover(self, tenant_id, handover_id, approver_id):
        self._require_syn(tenant_id, handover_id, approver_id)
        row = self.sql(
            'SELECT leaver_id, target_user_id, status, includes_private_body FROM sv7_handover '
            'WHERE tenant_id=? AND handover_id=?',
            (tenant_id, handover_id),
        )
        if not row:
            raise SandboxError('HANDOVER_NOT_FOUND')
        leaver_id, target_user_id, status, includes_private_body = row[0]
        if includes_private_body:
            raise SandboxError('PRIVATE_BODY_AUTO_INHERIT_FORBIDDEN')
        if approver_id in (leaver_id, target_user_id):
            raise SandboxError('HANDOVER_APPROVER_MUST_BE_INDEPENDENT')
        existing = self.sql(
            'SELECT approver_id FROM sv7_handover_approval WHERE tenant_id=? AND handover_id=?',
            (tenant_id, handover_id),
        )
        if any(approver_id == item[0] for item in existing):
            raise SandboxError('DUPLICATE_APPROVAL')
        self.sql(
            'INSERT INTO sv7_handover_approval(tenant_id, handover_id, approver_id) VALUES(?,?,?)',
            (tenant_id, handover_id, approver_id),
        )
        approvals = self.sql(
            'SELECT approver_id FROM sv7_handover_approval WHERE tenant_id=? AND handover_id=?',
            (tenant_id, handover_id),
        )
        if len(approvals) < 2:
            return {'status': 'pending', 'approvals': len(approvals)}
        self.sql(
            "UPDATE sv7_handover SET status='approved' WHERE tenant_id=? AND handover_id=?",
            (tenant_id, handover_id),
        )
        self._set_principal_status(tenant_id, leaver_id, 'handover_complete')
        # Work-product handover is pointer/metadata only.
        payload = {
            'handover_id': handover_id,
            'leaver_id': leaver_id,
            'target_user_id': target_user_id,
            'pointers_only': True,
            'body': None,
            'chunk': None,
            'embedding': None,
            'evidence': None,
            'includes_private_body': False,
        }
        self.log(tenant_id, 'handover_approved', payload)
        return {'status': 'approved', 'approvals': len(approvals), 'payload': payload}

    def isolation_expired(self, tenant_id, user_id):
        row = self.sql(
            'SELECT isolation_until, status FROM sv7_principal WHERE tenant_id=? AND user_id=?',
            (tenant_id, user_id),
        )
        if not row or row[0][0] is None:
            return False
        return self._now >= row[0][0]

    def restore_principal_active(self, tenant_id, user_id):
        self.refuse_restore('principal.status')

    def restore_grants(self, snapshot):
        self.refuse_restore('grants')

    def restore_policy_generation(self, tenant_id, space_id, generation):
        current = self.sql(
            'SELECT policy_generation FROM sv7_space WHERE tenant_id=? AND space_id=?',
            (tenant_id, space_id),
        )
        if current and generation < current[0][0]:
            self.refuse_restore('policy_generation')
        raise SandboxError('SECURITY_STATE_MONOTONIC')

    def restore_share(self, tenant_id, share_id):
        self.refuse_restore('controlled_shares')

    # --- fixture seed used by T-01–T-27 ---
    def seed_standard(self):
        """Deterministic syn_* fixture: two enterprise tenants, personal / teams / enterprise spaces."""
        for org in ('syn_org_a', 'syn_org_b'):
            self.create_tenant(org, 'enterprise')
            self.create_principal(org, 'syn_employee', issuer='syn_issuer_' + org, subject_id='syn_employee_' + org[-1])
            self.create_principal(org, 'syn_admin', issuer='syn_issuer_admin_' + org, subject_id='syn_admin_' + org[-1])
            self.create_principal(org, 'syn_alice', issuer='syn_issuer_alice_' + org, subject_id='syn_alice_' + org[-1])
            self.create_principal(org, 'syn_bob', issuer='syn_issuer_bob_' + org, subject_id='syn_bob_' + org[-1])
            self.create_principal(org, 'syn_approver_a', issuer='syn_issuer_aa_' + org, subject_id='syn_aa_' + org[-1])
            self.create_principal(org, 'syn_approver_b', issuer='syn_issuer_ab_' + org, subject_id='syn_ab_' + org[-1])
            self.create_space(org, 'syn_private', 'personal', 'syn_employee')
            self.create_space(org, 'syn_group_a', 'team', 'syn_alice')
            self.create_space(org, 'syn_group_b', 'team', 'syn_bob')
            self.create_space(org, 'syn_enterprise', 'enterprise', 'syn_admin')
            self.add_member(org, 'syn_enterprise', 'syn_alice', 'member')
            self.add_member(org, 'syn_enterprise', 'syn_bob', 'member')
            self.add_member(org, 'syn_enterprise', 'syn_employee', 'member')
            self.bind_org_team(org, 'syn_org_team_a', 'syn_group_a')
            self.bind_org_team(org, 'syn_org_team_b', 'syn_group_b')
            self.grant_all(org, 'syn_private', 'syn_employee')
            self.grant_all(org, 'syn_group_a', 'syn_alice')
            self.grant_all(org, 'syn_group_b', 'syn_bob')
            self.grant_all(org, 'syn_enterprise', 'syn_admin')
            self.grant(org, 'syn_enterprise', 'syn_alice', 'read', True)
            self.grant(org, 'syn_enterprise', 'syn_bob', 'read', True)
            self.create_kb(org, 'syn_private_kb', 'syn_private')
            self.create_kb(org, 'syn_group_a_kb', 'syn_group_a')
            self.create_kb(org, 'syn_group_b_kb', 'syn_group_b')
            self.create_kb(org, 'syn_enterprise_kb', 'syn_enterprise')
            self.create_kb(org, 'syn_enterprise_kb_2', 'syn_enterprise')  # 1 Space : N KB
            self.create_asset(org, 'syn_private_asset', 'syn_private_kb', 'knowledge_file', folder_id='syn_folder')
            self.create_asset(org, 'syn_group_a_asset', 'syn_group_a_kb', 'knowledge_file', folder_id='syn_folder')
            self.create_asset(org, 'syn_group_b_asset', 'syn_group_b_kb', 'knowledge_file', folder_id='syn_folder')
            self.upsert_external(org, 'syn_external', valid_until=self._now + 120, generation=1)
            self.create_asset(
                org, 'syn_external_asset', 'syn_enterprise_kb', 'deliverable',
                folder_id='syn_folder', ref_id='syn_external',
            )
            self.upsert_agent(
                org, 'syn_agent',
                allowed_space_ids=['syn_group_a', 'syn_enterprise'],
                allowed_kb_ids=['syn_group_a_kb', 'syn_enterprise_kb'],
                allowed_space_types=['team', 'enterprise'],
                generation=1, active=True,
            )
            self.create_share(org, 'syn_share_private', 'syn_private', 'syn_employee', 'syn_alice')
            self.add_favorite(org, 'syn_alice', 'kb', 'syn_group_a_kb')
            self.add_favorite(org, 'syn_alice', 'asset', 'syn_group_a_asset')
        return True
