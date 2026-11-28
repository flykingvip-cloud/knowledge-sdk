#!/usr/bin/env python3
"""Wave-V21 architecture boundary gate. Locks FROZEN_V21_REUSE_V1 manifest SHA-256 and M1 /v2/spaces zero-drift. Not formal T-01–T-27 acceptance."""
from __future__ import annotations
import ast, hashlib, importlib.util, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = '9940818b962ccb186c0dfb0158de6bd9bd49057b'
FROZEN_V21_REUSE_V1_MANIFEST_SHA256 = '212537fd41bd4cc4d9d7343cacafaea225ee98b6586df716bf036a397cb2a382'
W2_INTEROP_GOLDEN_PATH = 'sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json'
W2_INTEROP_GOLDEN_SHA256 = 'f8033a902af06b005fa591ab872a74f9569a3783fd3e7cef90c6dc94cf9d0fef'
W2_INTEROP_GOLDEN_BYTE_LENGTH = 33863
FROZEN_V21_REUSE_V1_STATUS = 'FROZEN_V21_REUSE_V1'
REQUIRED_STATUS_FLAGS = {
    'status': FROZEN_V21_REUSE_V1_STATUS,
    'schema_v7_ddl_authorized': False,
    'schema_v8_v9_ddl_authorized': False,
    'final_alignment_frozen': False,
    'prod_shadow_migration_cutover_authorized': False,
    'semantic_object_dual_write_prohibited': True,
    'duplicate_runtime_or_connector_build_prohibited': True,
    'mounted_v3_runtime': False,
    'formal_t01_t27': 'NOT_RUN_NOT_ACCEPTED',
}
ALLOWED_NEW_PREFIXES = (
    'contracts/v21-reuse-v1/',
    'sandbox/v21_reuse_v1/',
    'scripts/verify_v21_boundaries.py',
    'docs/acceptance/v21-wave0/',
    'docs/acceptance/v21-wave1/',
    'docs/acceptance/v21-wave2/',
    'docs/acceptance/v21-wave3/',
    'docs/acceptance/v21-wave4/',
    'docs/acceptance/v21-wave5/',
    'docs/acceptance/v21-wave6/',
    'docs/acceptance/v21-wave7/',
    'sandbox/v21_schema_v7/',
    'tests/wave7/',
    'src/knowledge_sdk/storage/migration_v7.py',
    'src/knowledge_sdk/storage/schema_v7.py',
)
# Wave-V21-7 isolated-branch authorization (AUTH-V21-07-CORE-V7):
# these existing Schema v6 files may be edited so this branch can legally be
# schema_version==7. postgres_schema.sql stays byte-identical to the frozen
# baseline; v7 DDL lives in migration_v7.py. Other baseline files stay locked.
AUTHORIZED_V7_STORAGE_EDITS = frozenset({
    'src/knowledge_sdk/storage/migrations.py',
    'src/knowledge_sdk/storage/migration_v6.py',
    'src/knowledge_sdk/storage/sqlite_store.py',
    'src/knowledge_sdk/storage/postgres_store.py',
})
AUTHORIZED_V7_NEW_STORAGE = frozenset({
    'src/knowledge_sdk/storage/migration_v7.py',
    'src/knowledge_sdk/storage/schema_v7.py',
})

# Pre-existing 9940818b knowledge-domain modules the scanner ignores.
# These are authorized knowledge engines/tools on the Wave2 baseline, not new
# copies of the 12 OpenBot capabilities.
PREEXISTING_ALLOWLIST = (
    'src/knowledge_sdk/connectors/',          # knowledge filesystem/http/planning connectors, not ERP/CRM
    'src/knowledge_sdk/mcp/',                 # knowledge evidence MCP tools
    'src/knowledge_sdk/governance/',          # knowledge governance/workflow/issues
    'src/knowledge_sdk/storage/sqlite_store.py',
    'src/knowledge_sdk/storage/postgres_store.py',
    'src/knowledge_sdk/storage/migrations.py',
    'src/knowledge_sdk/storage/migration_v6.py',
    'src/knowledge_sdk/retrieval/adapters/reranker.py',      # lexical reranker
    'src/knowledge_sdk/retrieval/adapters/openai_embedder.py',  # optional host-injected embedder, no vault
    'src/knowledge_sdk/retrieval/adapters/hash_embedder.py',
    'src/knowledge_sdk/retrieval/adapters/pgvector_index.py',
    'src/knowledge_sdk/retrieval/adapters/qdrant.py',
    'src/knowledge_sdk/runtime/service.py',   # knowledge service, not agent session runtime
    'src/knowledge_sdk/server/',              # HTTP/v2 knowledge server
    'src/knowledge_sdk/contracts/',
    'src/knowledge_sdk/ingestion/',
    'src/knowledge_sdk/permissions/',
    'src/knowledge_sdk/events/',
    'src/knowledge_sdk/packs/',
    'src/knowledge_sdk/audit/',
    'src/knowledge_sdk/impact/',
    'src/knowledge_sdk/client/',
    'src/knowledge_sdk/ui/',
)
PROHIBITED_TYPES = (
    'ModelCredentialVault', 'AgentSessionRuntime', 'AgentRuntime', 'MemoryDistillation',
    'MemoryDistillationPipeline', 'BanditEngine', 'ContextualBandit', 'TextToSQLExecutor',
    'TextToSqlEngine', 'ErpConnector', 'CrmConnector', 'ConnectorVault',
    'DataCapabilityExecutionEngine', 'GeneralToolPlatform', 'WorkflowOrchestratorRuntime',
    'ModelProviderVault', 'PaidModelClient',
)
PROHIBITED_DEFS = re.compile(r'^\s*(class|def)\s+(' + '|'.join(PROHIBITED_TYPES) + r')\b', re.M)


EPHEMERAL_PARTS = frozenset({
    'v21-ci-evidence', '__pycache__', 'node_modules', 'ts-generated',
    '.pytest_cache', '.venv', 'htmlcov', '.mypy_cache',
})


def ephemeral_path(path):
    parts = Path(path).parts
    if any(part in EPHEMERAL_PARTS or part.startswith('.') for part in parts):
        return True
    return Path(path).suffix in {'.pyc', '.pyo'}


def git(*args):
    return subprocess.check_output(['git'] + list(args), cwd=ROOT)


def pyproject_deps_empty():
    text = (ROOT / 'pyproject.toml').read_text()
    if not re.search(r'^dependencies\s*=\s*\[\s*\]', text, re.M):
        raise SystemExit('pyproject dependencies are not empty')
    if (ROOT / 'pyproject.toml').read_bytes() != git('show', BASE + ':pyproject.toml'):
        raise SystemExit('pyproject.toml drifted from 9940818b')
    return True


def baseline_bytes():
    changed = []
    checked = 0
    for line in git('ls-tree', '-r', BASE).decode().splitlines():
        header, path = line.split('\t', 1)
        mode, kind, digest = header.split()
        if kind != 'blob':
            continue
        raw = (ROOT / path).read_bytes()
        if path == '.github/workflows/tests.yml':
            if not raw.startswith(git('show', BASE + ':' + path)):
                raise SystemExit('existing workflow bytes changed')
            continue
        if path in AUTHORIZED_V7_STORAGE_EDITS:
            # Still count this baseline file in the 709 inventory; do not
            # treat the authorized Schema v7 isolated-branch edit as drift.
            checked += 1
            continue
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if actual != digest:
            changed.append(path)
        checked += 1
    if changed:
        raise SystemExit('baseline drift: ' + ','.join(changed))
    committed = [p for p in git('diff', '--name-only', '--diff-filter=A', BASE).decode().splitlines() if p]
    untracked = [p for p in git('ls-files', '--others', '--exclude-standard').decode().splitlines() if p and not ephemeral_path(p)]
    additions = sorted(set(committed + untracked))
    for path in additions:
        if path == '.github/workflows/tests.yml':
            raise SystemExit('workflow should be a modification, not a new file')
        if not any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_NEW_PREFIXES):
            raise SystemExit('unexpected new path: ' + path)
    return checked, additions


def scan_new_files(additions):
    hits = []
    for path in additions:
        if not path.endswith(('.py', '.ts', '.js', '.yaml', '.yml')):
            continue
        if path.startswith('src/knowledge_sdk/'):
            if path not in AUTHORIZED_V7_NEW_STORAGE:
                hits.append(path + ': new production SDK module')
            continue
        text = (ROOT / path).read_text(errors='ignore')
        if PROHIBITED_DEFS.search(text):
            hits.append(path + ': prohibited type or function definition')
    if hits:
        raise SystemExit('duplicate capability scan failed: ' + '; '.join(hits))
    return True


def schema_v6_frozen():
    """Historical name kept as a wrapper; this isolated branch reports 7."""
    return schema_version_gate()


def schema_version_gate():
    """Register Wave-V21-7 isolated-branch authorized state (schema_version==7).

    postgres_schema.sql must remain byte-identical to baseline 9940818b.
    Authorized storage edits must still carry v6 markers and must not
    authorize production Schema v7 migration. Frozen contract flags are
    checked separately and must stay unchanged.
    """
    frozen_sql = 'src/knowledge_sdk/storage/postgres_schema.sql'
    if (ROOT / frozen_sql).read_bytes() != git('show', BASE + ':' + frozen_sql):
        raise SystemExit(frozen_sql + ' drifted from Schema v6 baseline')
    v6 = (ROOT / 'src/knowledge_sdk/storage/migration_v6.py').read_text()
    migrations = (ROOT / 'src/knowledge_sdk/storage/migrations.py').read_text()
    sqlite = (ROOT / 'src/knowledge_sdk/storage/sqlite_store.py').read_text()
    postgres = (ROOT / 'src/knowledge_sdk/storage/postgres_store.py').read_text()
    if 'NEW_TABLES' not in v6 or 'upgrade_v6' not in v6:
        raise SystemExit('Schema v6 markers missing from migration_v6.py')
    if not re.search(r"PRAGMA user_version=6", v6) or not re.search(r"VALUES\(6,", v6):
        raise SystemExit('Schema v6 version markers missing from migration_v6.py')
    v7_path = ROOT / 'src/knowledge_sdk/storage/migration_v7.py'
    if not v7_path.is_file():
        raise SystemExit('migration_v7.py is required on this isolated branch')
    v7 = v7_path.read_text()
    if 'SCHEMA_VERSION = 7' not in v7:
        raise SystemExit('migration_v7.py must declare SCHEMA_VERSION = 7')
    if 'SCHEMA_V7_PROD_MIGRATION_AUTHORIZED = False' not in v7:
        raise SystemExit('schema_v7_prod_migration_authorized must remain false')
    if 'owned_nonproduction' not in v7 or 'upgrade_v7' not in v7 or 'rollback_v7' not in v7:
        raise SystemExit('migration_v7.py must expose upgrade_v7/rollback_v7 with the owned-nonproduction gate')
    if 'FORCE ROW LEVEL SECURITY' not in v7 or "current_setting('app.current_org_id'" not in v7:
        raise SystemExit('PostgreSQL Schema v7 FORCE RLS policy markers missing')
    if 'parent_space_id' in v7 and 'PARENT_SPACE_FORBIDDEN' not in v7:
        raise SystemExit('phase-1 parent_space_id must stay forbidden')
    if 'in (0,1,2,3,4,5,6,7)' not in sqlite.replace(' ', ''):
        # tolerate spacing variants
        if '0,1,2,3,4,5,6,7' not in sqlite:
            raise SystemExit('sqlite_store.py must accept schema version 7')
    if 'in (6, 7)' not in sqlite and 'in (6,7)' not in sqlite:
        raise SystemExit('sqlite_store.py must keep version_id writes for schema 6 and 7')
    if 'in (6, 7)' not in postgres and 'in (6,7)' not in postgres:
        raise SystemExit('postgres_store.py must keep version_id writes for schema 6 and 7')
    if 'version==7' not in migrations.replace(' ', '') and 'version == 7' not in migrations:
        raise SystemExit('migrations.py must register schema version 7')
    schema = (ROOT / 'src/knowledge_sdk/storage/schema_v7.py').read_text()
    if 'EXPERIMENTAL_V3_ENABLED_DEFAULT = False' not in schema:
        raise SystemExit('EXPERIMENTAL_V3_ENABLED must stay default false')
    if 'FORMAL_T01_T27_ACCEPTED = False' not in schema:
        raise SystemExit('formal_t01_t27_accepted must stay false')
    return 7


def frozen():
    path = ROOT / 'docs/acceptance/v2.2-align-wave2/verify_frozen.py'
    spec = importlib.util.spec_from_file_location('verify_frozen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify()


def frozen_contract_status():
    status = json.loads((ROOT / 'contracts/v21-reuse-v1/status.json').read_text())
    for key, expected in REQUIRED_STATUS_FLAGS.items():
        if status.get(key) != expected:
            raise SystemExit('status.json ' + key + ' must be ' + repr(expected))
    return status['status']


def manifest():
    sys.path.insert(0, str(ROOT / 'contracts' / 'v21-reuse-v1'))
    import validate
    computed, digest = validate.write_manifest(ROOT / 'contracts' / 'v21-reuse-v1')
    committed = json.loads((ROOT / 'contracts/v21-reuse-v1/v21-contract-manifest.json').read_text())
    if computed != committed:
        raise SystemExit('v21-contract-manifest.json is not deterministic/current')
    if computed.get('status') != FROZEN_V21_REUSE_V1_STATUS:
        raise SystemExit('v21-contract-manifest.json status is not FROZEN_V21_REUSE_V1')
    if digest != FROZEN_V21_REUSE_V1_MANIFEST_SHA256:
        raise SystemExit('frozen v21-reuse-v1 manifest SHA-256 mismatch: ' + digest)
    return digest, computed['file_count']


def python39_ast():
    count = 0
    for path in list((ROOT / 'sandbox/v21_reuse_v1').glob('*.py')) + list((ROOT / 'sandbox/v21_schema_v7').glob('*.py')) + list((ROOT / 'contracts/v21-reuse-v1').glob('*.py')) + list((ROOT / 'tests/wave7').glob('*.py')) + [ROOT / 'scripts/verify_v21_boundaries.py', ROOT / 'src/knowledge_sdk/storage/migration_v7.py', ROOT / 'src/knowledge_sdk/storage/schema_v7.py']:
        ast.parse(path.read_text())
        count += 1
    return count



def w2_interop_golden_locked():
    """Hard-lock the official Sync-W2-1 golden fixture bytes. Any change fails the gate."""
    path = ROOT / W2_INTEROP_GOLDEN_PATH
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != W2_INTEROP_GOLDEN_BYTE_LENGTH:
        raise SystemExit('w2_interop_golden.json byte length mismatch: ' + str(len(raw)))
    if digest != W2_INTEROP_GOLDEN_SHA256:
        raise SystemExit('w2_interop_golden.json SHA-256 mismatch: ' + digest)
    worktree_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    line = git('ls-tree', 'HEAD', '--', W2_INTEROP_GOLDEN_PATH).decode().strip()
    if not line:
        raise SystemExit('w2_interop_golden.json is not committed at HEAD')
    header, committed_path = line.split('\t', 1)
    _mode, kind, committed_blob = header.split()
    if kind != 'blob' or committed_path != W2_INTEROP_GOLDEN_PATH:
        raise SystemExit('w2_interop_golden.json ls-tree parse failed')
    if worktree_blob != committed_blob:
        raise SystemExit('w2_interop_golden.json worktree blob differs from git blob: ' + worktree_blob + ' != ' + committed_blob)
    return digest, len(raw), worktree_blob


def verify():
    pyproject_deps_empty()
    checked, additions = baseline_bytes()
    scan_new_files(additions)
    frozen_result = frozen()
    version = schema_v6_frozen()
    contract_status = frozen_contract_status()
    manifest_sha, files = manifest()
    golden_sha, golden_bytes, golden_blob = w2_interop_golden_locked()
    ast_count = python39_ast()
    return dict(
        passed=True,
        base_sha=BASE,
        baseline_files_byte_checked=checked,
        baseline_file_drift=0,
        schema_version=version,
        schema_v7_core_branch_ddl_authorized=True,
        schema_v7_prod_migration_authorized=False,
        additions=sorted(additions),
        preexisting_allowlist=list(PREEXISTING_ALLOWLIST),
        historical_frozen=frozen_result,
        v21_contract_status=contract_status,
        v21_manifest_sha256=manifest_sha,
        v21_manifest_file_count=files,
        w2_interop_golden_sha256=golden_sha,
        w2_interop_golden_bytes=golden_bytes,
        w2_interop_golden_git_blob=golden_blob,
        python39_ast_files=ast_count,
        formal_acceptance=False,
    )


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
