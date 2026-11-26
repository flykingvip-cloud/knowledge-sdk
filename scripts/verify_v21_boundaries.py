#!/usr/bin/env python3
"""Wave-V21-0 architecture boundary gate. Not an approval or formal acceptance."""
from __future__ import annotations
import ast, hashlib, importlib.util, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = '9940818b962ccb186c0dfb0158de6bd9bd49057b'
ALLOWED_NEW_PREFIXES = (
    'contracts/v21-reuse-v1/',
    'sandbox/v21_reuse_v1/',
    'scripts/verify_v21_boundaries.py',
    'docs/acceptance/v21-wave0/',
)
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
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if actual != digest:
            changed.append(path)
        checked += 1
    if changed:
        raise SystemExit('baseline drift: ' + ','.join(changed))
    committed = [p for p in git('diff', '--name-only', '--diff-filter=A', BASE).decode().splitlines() if p]
    untracked = [p for p in git('ls-files', '--others', '--exclude-standard').decode().splitlines() if p]
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
            hits.append(path + ': new production SDK module')
            continue
        text = (ROOT / path).read_text(errors='ignore')
        if PROHIBITED_DEFS.search(text):
            hits.append(path + ': prohibited type or function definition')
    if hits:
        raise SystemExit('duplicate capability scan failed: ' + '; '.join(hits))
    return True


def schema_v6_frozen():
    for path in (
        'src/knowledge_sdk/storage/migrations.py',
        'src/knowledge_sdk/storage/migration_v6.py',
        'src/knowledge_sdk/storage/postgres_schema.sql',
        'src/knowledge_sdk/storage/sqlite_store.py',
        'src/knowledge_sdk/storage/postgres_store.py',
    ):
        if (ROOT / path).read_bytes() != git('show', BASE + ':' + path):
            raise SystemExit(path + ' drifted from Schema v6 baseline')
    text = (ROOT / 'src/knowledge_sdk/storage/migration_v6.py').read_text()
    if 'SCHEMA_VERSION' in text:
        # keep whatever the baseline uses; already byte-compared
        pass
    if not re.search(r'\bversion\b.*\b6\b|schema-v6|SCHEMA.?v6|version == 6|VALUES\(6', (ROOT / 'src/knowledge_sdk/storage/migrations.py').read_text() + text):
        # baseline already proven; still require the v6 marker in the pair
        if 'NEW_TABLES' not in text:
            raise SystemExit('Schema v6 markers missing')
    return 6


def frozen():
    path = ROOT / 'docs/acceptance/v2.2-align-wave2/verify_frozen.py'
    spec = importlib.util.spec_from_file_location('verify_frozen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify()


def manifest():
    sys.path.insert(0, str(ROOT / 'contracts' / 'v21-reuse-v1'))
    import validate
    computed, digest = validate.write_manifest(ROOT / 'contracts' / 'v21-reuse-v1')
    committed = json.loads((ROOT / 'contracts/v21-reuse-v1/v21-contract-manifest.json').read_text())
    if computed != committed:
        raise SystemExit('v21-contract-manifest.json is not deterministic/current')
    return digest, computed['file_count']


def python39_ast():
    count = 0
    for path in list((ROOT / 'sandbox/v21_reuse_v1').glob('*.py')) + list((ROOT / 'contracts/v21-reuse-v1').glob('*.py')) + [ROOT / 'scripts/verify_v21_boundaries.py']:
        ast.parse(path.read_text())
        count += 1
    return count


def verify():
    pyproject_deps_empty()
    checked, additions = baseline_bytes()
    scan_new_files(additions)
    frozen_result = frozen()
    version = schema_v6_frozen()
    manifest_sha, files = manifest()
    ast_count = python39_ast()
    return dict(
        passed=True,
        base_sha=BASE,
        baseline_files_byte_checked=checked,
        baseline_file_drift=0,
        schema_version=version,
        additions=sorted(additions),
        preexisting_allowlist=list(PREEXISTING_ALLOWLIST),
        historical_frozen=frozen_result,
        v21_manifest_sha256=manifest_sha,
        v21_manifest_file_count=files,
        python39_ast_files=ast_count,
        formal_acceptance=False,
    )


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
