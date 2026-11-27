"""Four-channel revocation closed loop and tamper-evident RevocationPurgeReceipt."""
from __future__ import annotations
import hashlib, json
from typing import Dict

CHANNELS = ('primary_storage_acl', 'vector_fts_index', 'cache_materialized_snapshot', 'agent_history_cogniweave')


def canonical_json_bytes(payload):
    """Return the exact UTF-8 bytes hashed for receipt_hash (Sync-W2-1 / W2-Gate-1).

    This is the single existing Python canonicalization used by FourChannelRevocation.
    TypeScript must emit identical bytes: recursively sort every object's keys
    (json.dumps sort_keys=True), use compact separators (',' and ':') with no
    spaces, set ensure_ascii=False so non-ASCII is raw UTF-8 rather than \\u
    escapes, keep array order, encode booleans/null as lowercase true/false/null,
    write integers as unquoted decimal JSON numbers, apply standard JSON escaping
    only to quotes, backslashes, and control characters, and add no leading,
    trailing, or interior decorative whitespace and no trailing newline. SHA-256
    is taken over those UTF-8 bytes with no BOM.
    """
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def canonical_sha256_hex(payload):
    """64 lowercase hex characters of SHA-256(canonical_json_bytes(payload))."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _hash(payload):
    return canonical_sha256_hex(payload)


class ChannelStore(object):
    def __init__(self):
        self.records = {name: {} for name in CHANNELS}

    def grant(self, channel, tenant_id, subject_id):
        self.records[channel][(tenant_id, subject_id)] = 'active'

    def revoke(self, channel, tenant_id, subject_id, *, fail=False, timeout=False, missing=False):
        if missing:
            return dict(channel=channel, status='missing')
        if fail:
            return dict(channel=channel, status='failed', receipt_hash=_hash(dict(channel=channel, tenant_id=tenant_id, status='failed')), hash_algorithm='sha256')
        if timeout:
            return dict(channel=channel, status='timeout', receipt_hash=_hash(dict(channel=channel, tenant_id=tenant_id, status='timeout')), hash_algorithm='sha256')
        self.records[channel][(tenant_id, subject_id)] = 'revoked'
        body = dict(channel=channel, tenant_id=tenant_id, subject_id=subject_id, status='success')
        return dict(channel=channel, status='success', receipt_hash=_hash(body), hash_algorithm='sha256')


class FourChannelRevocation(object):
    def __init__(self, store=None):
        self.store = store or ChannelStore()

    def run(self, tenant_id, subject_id, policy_generation, task_id, *, failures=None):
        failures = failures or {}
        receipts = []
        for channel in CHANNELS:
            mode = failures.get(channel) or 'success'
            receipts.append(self.store.revoke(channel, tenant_id, subject_id, fail=mode == 'failed', timeout=mode == 'timeout', missing=mode == 'missing'))
        purged = all(item.get('status') == 'success' for item in receipts) and len(receipts) == 4
        body = dict(task_id=task_id, tenant_id=tenant_id, subject_id=subject_id, policy_generation=policy_generation, channels=receipts, purged=purged, hash_algorithm='sha256')
        receipt = dict(body, receipt_hash=_hash({k: body[k] for k in body if k != 'receipt_hash'}))
        if receipt['purged'] is True and not all(item.get('status') == 'success' for item in receipts):
            raise AssertionError('purged_requires_four_success_receipts')
        return receipt

    def verify(self, receipt):
        body = {k: receipt[k] for k in receipt if k != 'receipt_hash'}
        return receipt.get('hash_algorithm') == 'sha256' and receipt.get('receipt_hash') == _hash(body)
