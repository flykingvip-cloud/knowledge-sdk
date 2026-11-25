"""Internal, memory-only C-07/C-09 preparation; not a transport/persistence API."""
from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import math
import threading
import time
from typing import Any, Callable, Optional, Protocol, Tuple
from copy import deepcopy
from ..exceptions import ValidationError, ConflictError

Key = Tuple[str, str, str, str]


def request_fingerprint(payload: Any) -> str:
    """Deterministic strict JSON, without content normalization or float NaN."""
    def validate(value):
        if value is None or type(value) in (str, bool, int):
            return
        if type(value) is float and math.isfinite(value):
            return
        if type(value) is list:
            for item in value: validate(item)
            return
        if type(value) is dict and all(type(k) is str for k in value):
            for item in value.values(): validate(item)
            return
        raise ValidationError('INVALID_IDEMPOTENCY_PAYLOAD')
    validate(payload)
    try:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, UnicodeError) as exc:
        raise ValidationError('INVALID_IDEMPOTENCY_PAYLOAD') from exc
    return hashlib.sha256(raw).hexdigest()


class IdempotencyDecision(str, Enum):
    NEW = 'NEW'
    REPLAY_EXACT = 'REPLAY_EXACT'
    CONFLICT_PAYLOAD_MISMATCH = 'CONFLICT_PAYLOAD_MISMATCH'
    IN_PROGRESS = 'IN_PROGRESS'


@dataclass(frozen=True)
class IdempotencyRecord:
    key: Key
    fingerprint: str
    claim_id: int
    expires_at: float
    completed: bool = False
    result: Any = None


class IdempotencyStore(Protocol):
    def begin(self, tenant_id: str, method: str, canonical_path: str,
              idempotency_key: str, payload: Any) -> Tuple[IdempotencyDecision, IdempotencyRecord]: ...
    def complete(self, record: IdempotencyRecord, result: Any) -> IdempotencyRecord: ...
    def cleanup(self) -> int: ...


class InMemoryIdempotencyStore:
    """Atomic claims, isolated response copies, TTL and stale-worker fencing.

    Canonical path is supplied by the trusted adapter; percent escapes/query order
    are NOT decoded or silently changed here. No automatic mutation retries.
    """
    def __init__(self, ttl_seconds: float = 300, *, clock: Callable[[], float] = time.monotonic):
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValidationError('INVALID_IDEMPOTENCY_TTL')
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.RLock()
        self._records = {}
        self._sequence = 0

    def cleanup(self):
        with self._lock:
            expired = [k for k, v in self._records.items() if v.expires_at <= self._clock()]
            for key in expired: del self._records[key]
            return len(expired)

    def begin(self, tenant_id, method, canonical_path, idempotency_key, payload):
        if any(type(v) is not str or not v or v != v.strip() for v in (tenant_id, method, canonical_path, idempotency_key)) or not canonical_path.startswith('/') or method != method.upper():
            raise ValidationError('INVALID_IDEMPOTENCY_KEY')
        key = (tenant_id, method, canonical_path, idempotency_key)
        fingerprint = request_fingerprint(payload)
        with self._lock:
            self.cleanup()
            record = self._records.get(key)
            if record is None:
                self._sequence += 1
                record = IdempotencyRecord(key, fingerprint, self._sequence, self._clock() + self.ttl_seconds)
                self._records[key] = record
                decision = IdempotencyDecision.NEW
            elif record.fingerprint != fingerprint:
                decision = IdempotencyDecision.CONFLICT_PAYLOAD_MISMATCH
            else:
                decision = IdempotencyDecision.REPLAY_EXACT if record.completed else IdempotencyDecision.IN_PROGRESS
            return decision, deepcopy(record)

    def complete(self, record, result):
        with self._lock:
            self.cleanup()
            current = self._records.get(record.key)
            if current is None or current.claim_id != record.claim_id or current.fingerprint != record.fingerprint:
                raise ConflictError('STALE_IDEMPOTENCY_CLAIM')
            if current.completed:
                if current.result != result: raise ConflictError('IDEMPOTENCY_RESULT_CONFLICT')
                return deepcopy(current)
            current = replace(current, completed=True, result=deepcopy(result))
            self._records[record.key] = current
            return deepcopy(current)
