"""Wave-V21-2 cross-stack interop harness and golden-fixture verifier.

Stdlib plus in-repo sandbox modules only. No third-party imports, no implicit
network I/O, no hardcoded credentials, and no production HTTP mount.

Canonical JSON / receipt_hash reuse the single existing algorithm in
``sandbox.v21_reuse_v1.revocation`` (``canonical_json_bytes`` /
``FourChannelRevocation._hash``). Do not invent a second serializer.

Rule, precise enough for a TypeScript twin: serialize the hash input with
``json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)``
and UTF-8-encode the result with no BOM and no trailing newline. Object keys
are sorted recursively at every nesting level; array order is preserved;
booleans and null are lowercase ``true`` / ``false`` / ``null``; integers are
unquoted decimal JSON numbers; ``ensure_ascii=False`` emits non-ASCII as raw
UTF-8 rather than ``\\u`` escapes; standard JSON escaping still applies to
quotes, backslashes, and control characters; there is no decorative
whitespace. SHA-256 is taken over those exact UTF-8 bytes and formatted as 64
lowercase hex characters.

Hash inputs for CogniWeave ``RevocationPurgeReceipt`` (must not be guessed
from the public channel object alone):

* channel ``success``: ``{channel, tenant_id, subject_id, status}``
* channel ``failed`` or ``timeout``: ``{channel, tenant_id, status}``
  (``subject_id`` is omitted)
* channel ``missing``: the current Python store emits no ``receipt_hash``
* the returned channel object that is placed in the parent ``channels``
  array is ``{channel, status, receipt_hash, hash_algorithm}`` (no
  ``tenant_id`` / ``subject_id``); a ``missing`` channel is only
  ``{channel, status}``
* top-level ``receipt_hash`` hashes the full receipt with only the top-level
  ``receipt_hash`` key removed; nested channel ``receipt_hash`` and
  ``hash_algorithm`` fields stay inside the parent hash input
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sandbox.v21_reuse_v1.adapters import (
    AdapterError,
    AIExecutionTraceContext,
    CogniWeaveMemoryBridgeClient,
    ControlledDataBridgeClient,
    EmbeddingRerankAdapterClient,
    TRACE_KEYS,
)
from sandbox.v21_reuse_v1.revocation import (
    CHANNELS,
    FourChannelRevocation,
    canonical_json_bytes,
    canonical_sha256_hex,
)
from sandbox.v21_reuse_v1.semantic_reference import (
    FORBIDDEN_FIELDS,
    SemanticReferenceWriteForbidden,
    from_payload,
)

GOLDEN_RELATIVE = 'sandbox/v21_reuse_v1/fixtures/w2_interop_golden.json'
GOLDEN_PATH = Path(__file__).resolve().parent / 'fixtures' / 'w2_interop_golden.json'
REDACTED_SECRET_KEYS = frozenset(FORBIDDEN_FIELDS)


def channel_hash_input(channel, tenant_id, subject_id, status):
    """Return the exact object ``ChannelStore.revoke`` hashes, or None if none."""
    if status == 'success':
        return dict(channel=channel, tenant_id=tenant_id, subject_id=subject_id, status='success')
    if status in ('failed', 'timeout'):
        return dict(channel=channel, tenant_id=tenant_id, status=status)
    if status == 'missing':
        return None
    raise AdapterError('VALIDATION_ERROR')


def explain_purge_receipt(tenant_id, subject_id, policy_generation, task_id, failures=None):
    """Run FourChannelRevocation and attach the exact hash inputs and bytes."""
    failures = failures or {}
    loop = FourChannelRevocation()
    receipt = loop.run(tenant_id, subject_id, policy_generation, task_id, failures=failures)
    channels = []
    for item in receipt['channels']:
        hashed = channel_hash_input(item['channel'], tenant_id, subject_id, item['status'])
        entry = dict(channel=item['channel'], status=item['status'], channel_receipt=item)
        if hashed is not None:
            raw = canonical_json_bytes(hashed)
            digest = canonical_sha256_hex(hashed)
            if digest != item.get('receipt_hash'):
                raise AssertionError('channel_receipt_hash_mismatch')
            entry['hash_input'] = hashed
            entry['canonical_json'] = raw.decode('utf-8')
            entry['receipt_hash'] = digest
        channels.append(entry)
    parent_input = {key: receipt[key] for key in receipt if key != 'receipt_hash'}
    parent_raw = canonical_json_bytes(parent_input)
    parent_digest = canonical_sha256_hex(parent_input)
    if parent_digest != receipt['receipt_hash']:
        raise AssertionError('parent_receipt_hash_mismatch')
    if not loop.verify(receipt):
        raise AssertionError('receipt_verify_failed')
    return dict(
        input=dict(
            tenant_id=tenant_id,
            subject_id=subject_id,
            policy_generation=policy_generation,
            task_id=task_id,
            failures=dict(failures),
        ),
        channels=channels,
        parent_hash_input=parent_input,
        parent_canonical_json=parent_raw.decode('utf-8'),
        receipt_hash=parent_digest,
        receipt=receipt,
        purged=receipt['purged'],
        verifier_ok=True,
    )


class SemanticObjectCatalogReadAdapter(object):
    """Read-only in-memory catalog projection. Never writes to disk.

    Mirrors the official SemanticObjectCatalogReadAdapter contract Team B will
    exercise: return ``semantic_object_key``, canonical mapping fields, and a
    redacted classification; strip connector/credential fields; reject writes.
    """

    def __init__(self, records=None, disk_path=None):
        self._records = {}
        for record in list(records or ()):
            self._ingest(record)
        self.disk_path = disk_path
        self.write_attempts = 0
        self.disk_writes = 0

    def _ingest(self, record):
        if not isinstance(record, dict):
            raise SemanticReferenceWriteForbidden('INVALID_PAYLOAD')
        pointer = {key: record[key] for key in record if key not in REDACTED_SECRET_KEYS and key not in ('write', 'mutate', 'classification')}
        ref = from_payload(pointer)
        classification = record.get('classification', 'unclassified')
        if type(classification) is not str or not classification or len(classification) > 64:
            raise SemanticReferenceWriteForbidden('INVALID_CLASSIFICATION')
        redacted = sorted(set(record) & REDACTED_SECRET_KEYS)
        self._records[(ref.tenant_id, ref.semantic_object_key)] = dict(
            tenant_id=ref.tenant_id,
            semantic_object_key=ref.semantic_object_key,
            concept_ids=list(ref.concept_ids),
            policy_clause_ids=list(ref.policy_clause_ids),
            classification=classification,
            redacted_fields=redacted,
        )

    def read(self, tenant_id, semantic_object_key):
        # Never open disk_path for write or read; the catalog is memory-only.
        record = self._records.get((tenant_id, semantic_object_key))
        if record is None:
            raise SemanticReferenceWriteForbidden('NOT_FOUND')
        return dict(record, writable=False, disk_writes=self.disk_writes)

    def write(self, *args, **kwargs):
        self.write_attempts += 1
        # Still no disk I/O.
        raise SemanticReferenceWriteForbidden('SEMANTIC_WRITE_FORBIDDEN')


class InteropHarness(object):
    """Offline, injectable-client assembly for the five official interop groups."""

    def __init__(self, catalog_records=None):
        self.embed_client = EmbeddingRerankAdapterClient()
        self.data_bridge = ControlledDataBridgeClient()
        self.memory = CogniWeaveMemoryBridgeClient()
        self.catalog = SemanticObjectCatalogReadAdapter(catalog_records or ())

    def embed(self, payload):
        return self.embed_client.embed(payload)

    def trace_hops(self, payload, hop_payloads=None):
        context = AIExecutionTraceContext.from_payload(payload)
        hops = []
        # Hop 0: accepted context (seven keys + cost envelope).
        hops.append(dict(
            hop=0,
            stage='context_accepted',
            seven_keys=context.seven_keys(),
            cost_attribution=dict(context.payload['cost_attribution']),
        ))
        # Hop 1: header projection (the cross-service wire form).
        hops.append(dict(
            hop=1,
            stage='header_projection',
            seven_keys=context.seven_keys(),
            headers=context.headers(),
        ))
        # Hop 2: payload bind / propagate into the next in-process hop.
        incoming = dict(hop_payloads[0]) if hop_payloads else {}
        hops.append(dict(
            hop=2,
            stage='propagate_bind',
            seven_keys=context.seven_keys(),
            bound=context.propagate(incoming),
        ))
        keys = context.seven_keys()
        for hop in hops:
            if hop['seven_keys'] != keys:
                raise AdapterError('VALIDATION_ERROR')
        return dict(seven_keys=keys, headers=context.headers(), hops=hops, key_order=list(TRACE_KEYS))

    def catalog_read(self, tenant_id, semantic_object_key):
        return self.catalog.read(tenant_id, semantic_object_key)

    def catalog_write(self, payload):
        return self.catalog.write(payload)

    def purge_receipt(self, tenant_id, subject_id, policy_generation, task_id, failures=None):
        explained = explain_purge_receipt(tenant_id, subject_id, policy_generation, task_id, failures=failures)
        accepted = self.memory.apply_purge(explained['receipt'])
        explained['accepted'] = accepted.get('accepted') is True
        return explained

    def data_bridge_execute(self, declaration, query=None):
        try:
            result = self.data_bridge.execute(declaration, query)
            return dict(ok=True, result=result)
        except AdapterError as exc:
            return dict(ok=False, error=exc.code)


def load_golden(path=None):
    target = Path(path) if path else GOLDEN_PATH
    return json.loads(target.read_text(encoding='utf-8'))


def _equal(actual, expected):
    return json.dumps(actual, sort_keys=True, separators=(',', ':'), ensure_ascii=False) == json.dumps(expected, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def verify_golden(path=None, harness=None):
    """Recompute every frozen sample and compare to the committed golden file."""
    golden = load_golden(path)
    harness = harness or InteropHarness(catalog_records=golden['catalog_seed'])
    failures = []

    for probe in golden['canonicalization']['probes']:
        actual_json = canonical_json_bytes(probe['input']).decode('utf-8')
        actual_hash = canonical_sha256_hex(probe['input'])
        if actual_json != probe['canonical_json'] or actual_hash != probe['sha256']:
            failures.append('probe:' + probe['id'])

    groups = {group['id']: group for group in golden['groups']}

    embed_group = groups['G1_MODELS_EMBED']
    for case in embed_group['cases']:
        if case['expect'] == 'accept':
            actual = harness.embed(case['input'])
            expected = case['expected']
            if actual['tenant_id'] != expected['tenant_id'] or actual['dim'] != expected['dim']:
                failures.append(case['id'] + ':meta')
            if not _equal(actual['vectors'], expected['vectors']):
                failures.append(case['id'] + ':vectors')
            if not _equal(actual['provider'], expected['provider']):
                failures.append(case['id'] + ':provider')
            vectors_json = canonical_json_bytes(actual['vectors']).decode('utf-8')
            if vectors_json != expected['vectors_canonical_json']:
                failures.append(case['id'] + ':vectors_canonical_json')
        else:
            try:
                harness.embed(case['input'])
                failures.append(case['id'] + ':expected_reject')
            except AdapterError as exc:
                if exc.code != case['expected']['error']:
                    failures.append(case['id'] + ':error')

    trace_group = groups['G2_AI_EXECUTION_TRACE']
    for case in trace_group['cases']:
        if case['expect'] == 'accept':
            actual = harness.trace_hops(case['input']['trace'], hop_payloads=case['input'].get('hop_payloads'))
            if list(actual['seven_keys']) != list(TRACE_KEYS):
                failures.append(case['id'] + ':key_order')
            if actual['seven_keys'] != case['expected']['seven_keys']:
                failures.append(case['id'] + ':seven_keys')
            if actual['headers'] != case['expected']['headers']:
                failures.append(case['id'] + ':headers')
            if len(actual['hops']) != 3:
                failures.append(case['id'] + ':hop_count')
            if actual['hops'][2]['bound'] != case['expected']['final_bound']:
                failures.append(case['id'] + ':final_bound')
        else:
            try:
                harness.trace_hops(case['input']['trace'])
                failures.append(case['id'] + ':expected_reject')
            except AdapterError as exc:
                if exc.code != case['expected']['error']:
                    failures.append(case['id'] + ':error')

    catalog_group = groups['G3_SEMANTIC_OBJECT_CATALOG']
    for case in catalog_group['cases']:
        if case['expect'] == 'accept':
            actual = harness.catalog_read(case['input']['tenant_id'], case['input']['semantic_object_key'])
            if actual != case['expected']:
                failures.append(case['id'] + ':read')
            if actual.get('disk_writes') != 0 or actual.get('writable') is not False:
                failures.append(case['id'] + ':zero_write')
        else:
            try:
                if case['input'].get('operation') == 'write':
                    harness.catalog_write(case['input'].get('payload') or {})
                else:
                    harness.catalog_read(case['input']['tenant_id'], case['input']['semantic_object_key'])
                failures.append(case['id'] + ':expected_reject')
            except SemanticReferenceWriteForbidden as exc:
                if exc.code != case['expected']['error']:
                    failures.append(case['id'] + ':error')
            if harness.catalog.disk_writes != 0:
                failures.append(case['id'] + ':disk_write')

    receipt_group = groups['G4_COGNIWEAVE_REVOCATION']
    for case in receipt_group['cases']:
        payload = case['input']
        actual = harness.purge_receipt(
            payload['tenant_id'], payload['subject_id'], payload['policy_generation'],
            payload['task_id'], failures=payload.get('failures') or {},
        )
        if actual['receipt_hash'] != case['expected']['receipt_hash']:
            failures.append(case['id'] + ':receipt_hash')
        if actual['parent_canonical_json'] != case['expected']['parent_canonical_json']:
            failures.append(case['id'] + ':parent_canonical_json')
        if actual['purged'] != case['expected']['purged']:
            failures.append(case['id'] + ':purged')
        if not _equal(actual['receipt'], case['expected']['receipt']):
            failures.append(case['id'] + ':receipt')
        for index, channel in enumerate(actual['channels']):
            expected_channel = case['expected']['channels'][index]
            if channel.get('receipt_hash') != expected_channel.get('receipt_hash'):
                failures.append(case['id'] + ':channel_hash:' + channel['channel'])
            if channel.get('canonical_json') != expected_channel.get('canonical_json'):
                failures.append(case['id'] + ':channel_canonical:' + channel['channel'])

    bridge_group = groups['G5_CONTROLLED_DATA_BRIDGE']
    for case in bridge_group['cases']:
        actual = harness.data_bridge_execute(case['input']['declaration'], case['input'].get('query'))
        if actual.get('ok') != (case['expect'] == 'accept'):
            failures.append(case['id'] + ':ok')
        elif case['expect'] == 'accept':
            if actual['result']['mode'] != case['expected']['mode']:
                failures.append(case['id'] + ':mode')
            if actual['result']['query_kind'] != case['expected']['query_kind']:
                failures.append(case['id'] + ':query_kind')
        else:
            if actual.get('error') != case['expected']['error']:
                failures.append(case['id'] + ':error')

    passed = not failures
    return dict(
        passed=passed,
        failures=failures,
        formal_acceptance=False,
        group_count=len(golden['groups']),
        case_count=sum(len(group['cases']) for group in golden['groups']),
        probe_count=len(golden['canonicalization']['probes']),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify Wave-V21-2 golden interop fixture (not formal T-01..T-27).')
    parser.add_argument('--fixture', default=str(GOLDEN_PATH), help='Path to w2_interop_golden.json')
    args = parser.parse_args(argv)
    report = verify_golden(args.fixture)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
