"""Official constants for the isolated Schema v7 sandbox.

Reserved T-01–T-27 titles are copied from
docs/acceptance/pre-v7-space-alignment/FORMAL_TEST_PLAN_NOT_RUN.md
on feat/space-alignment-v1-design-proto@4bed2a1c. The official five
Fail-Closed layers are copied from
SDK_SPACE_PERMISSION_MODEL.md (zip-a space-and-favorites). Eight
independent actions are the SPACE-C05 Option A names adopted by 空间-00F.
This module invents no additional layers or formal-acceptance flags.
"""
from __future__ import annotations

SANDBOX_SCHEMA_VERSION = 7
TABLE_PREFIX = 'sv7_'
SYN_PREFIX = 'syn_'

# Official SPACE-C05 eight independent actions.
OFFICIAL_ACTIONS = (
    'read',
    'upload',
    'update',
    'delete',
    'manage_members',
    'manage_permissions',
    'archive',
    'transfer_ownership',
)

SPACE_TYPES = ('enterprise', 'team', 'personal')
TENANT_KINDS = ('enterprise', 'independent_personal')
SPACE_STATUSES = ('active', 'frozen', 'archived', 'pending_purge')
PRINCIPAL_STATUSES = (
    'active',
    'resign_requested',
    'frozen',
    'isolation_retention',
    'handover_pending',
    'handover_complete',
)
# Security state is monotonic: later statuses cannot return to earlier ones.
PRINCIPAL_STATUS_RANK = {
    'active': 0,
    'resign_requested': 1,
    'frozen': 2,
    'isolation_retention': 3,
    'handover_pending': 4,
    'handover_complete': 5,
}

FAVORITE_TARGET_TYPES = ('kb', 'asset')
FORBIDDEN_POINTER_FIELDS = frozenset({
    'body', 'body_text', 'chunk', 'chunks', 'embedding', 'embeddings',
    'evidence', 'content', 'payload',
})

RESIGN_FREEZE_SLA_SECONDS = 60
ISOLATION_RETENTION_SECONDS = 90 * 24 * 60 * 60

# Official five-layer Fail-Closed chain (SDK_SPACE_PERMISSION_MODEL.md §1).
# Numbered Layer 0 through Layer 4 in the source table; do not invent layers.
FIVE_LAYERS = (
    {
        'id': 'layer_0',
        'name': 'Layer 0：租户硬隔离（Tenant + PG FORCE RLS）',
        'english': 'Identity-adjacent tenant hard isolation (Tenant + PG FORCE RLS)',
        'overridable': False,
    },
    {
        'id': 'layer_1',
        'name': 'Layer 1：身份与代次校验（Identity & Revocation）',
        'english': 'Identity & Revocation',
        'overridable': False,
    },
    {
        'id': 'layer_2',
        'name': 'Layer 2：空间边界与生命周期（Space Gate）',
        'english': 'Space Gate',
        'overridable': False,
    },
    {
        'id': 'layer_3',
        'name': 'Layer 3：知识库与文档细粒度 ACL（KB & Document Gate）',
        'english': 'KB & Document Gate',
        'overridable': False,
    },
    {
        'id': 'layer_4',
        'name': 'Layer 4：Agent 权限交集与脱敏（User ∩ Agent & Redaction）',
        'english': 'User ∩ Agent & Redaction',
        'overridable': False,
    },
)
LAYER_IDS = tuple(item['id'] for item in FIVE_LAYERS)

# Official reserved titles (FORMAL_TEST_PLAN_NOT_RUN.md). Status of the
# formal plan remains NOT_RUN_NOT_ACCEPTED even when sandbox cases PASS.
RESERVED_TITLES = {
    'T-01': 'Explicit enterprise tenant and tenant boundary',
    'T-02': 'Flat Tenant-Space-KB, no parent',
    'T-03': 'Same-org composite KB binding',
    'T-04': 'Detach not archive and same-home reattach',
    'T-05': 'Employee personal owner boundary',
    'T-06': 'Enterprise admin no private-content shortcut',
    'T-07': 'Two same-tenant collaboration groups isolation',
    'T-08': 'Eight independent action grants',
    'T-09': 'Explicit Deny precedence',
    'T-10': 'Agent Space ceiling',
    'T-11': 'KB fine-grained consumption scope',
    'T-12': 'Knowledge-file scope',
    'T-13': 'Deliverable scope',
    'T-14': 'Folder scope',
    'T-15': 'Current User intersection and current profile',
    'T-16': 'Transactional revocation/outbox rollback',
    'T-17': 'Current policy generation strictness/staleness',
    'T-18': 'Future HTTP independent-version compatibility',
    'T-19': 'Future Python candidate protocol compatibility',
    'T-20': 'Future MCP candidate policy compatibility',
    'T-21': 'External source missing assertion',
    'T-22': 'External expired assertion',
    'T-23': 'External provider outage',
    'T-24': 'External revocation/tombstone/cursor',
    'T-25': 'Polymorphic favorite current-ACL hydration',
    'T-26': 'Future reviewed migration/rollback drill and security monotonicity',
    'T-27': 'Personal-sharing/offboarding approval gating and full reviewed acceptance',
}

# Production Schema v6 markers. Presence means "do not migrate / do not
# treat this connection as a disposable v7 sandbox".
PRODUCTION_V6_TABLES = frozenset({
    'schema_migrations',
    'idempotency_records',
    'ingestion_jobs',
})

FROZEN_V2_SPACES_PATH = '/v2/spaces'
SANDBOX_V7_SPACES_PATH = '/v7-sandbox/spaces'
FROZEN_V2_BASELINE = '9940818b962ccb186c0dfb0158de6bd9bd49057b'

ASSET_KINDS = ('uploaded_document', 'agent_deliverable', 'enterprise_materialized_ref', 'knowledge_file', 'deliverable')
