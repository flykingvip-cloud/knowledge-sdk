"""Append-only, canonical tenant audit records. No source text belongs here."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import hashlib
import json
import re
from .policy import (PolicyContract, Purpose, DecisionEffect, enum_value, text,
                     freeze_json, parse_time)
from ..exceptions import ValidationError


@dataclass(frozen=True)
class AuditEvent(PolicyContract):
    event_id: str
    org_id: str
    seq_no: int
    prev_hash: str
    event_hash: str
    occurred_at: str
    actor_id: str
    agent_id: str = ''
    action: str = ''
    purpose: Purpose = Purpose.READ
    resource_uri: str = ''
    doc_id: str = ''
    decision_effect: DecisionEffect = DecisionEffect.ALLOW
    reason_code: str = 'ok'
    policy_generation: str = '0'
    redaction_profile: str = ''
    request_id: str = ''
    task_id: str = ''
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ('event_id', 'org_id', 'actor_id'):
            text(getattr(self, name), name, True)
        for name in ('agent_id', 'action', 'resource_uri', 'doc_id', 'reason_code',
                     'policy_generation', 'redaction_profile', 'request_id', 'task_id'):
            text(getattr(self, name), name)
        if type(self.seq_no) is not int or self.seq_no < 0:
            raise ValidationError('Invalid seq_no')
        for name in ('prev_hash', 'event_hash'):
            if not isinstance(getattr(self, name), str) or not re.fullmatch('[0-9a-f]{64}', getattr(self, name)):
                raise ValidationError('Invalid ' + name)
        parse_time(self.occurred_at)
        object.__setattr__(self, 'purpose', enum_value(Purpose, self.purpose))
        object.__setattr__(self, 'decision_effect', enum_value(DecisionEffect, self.decision_effect))
        # Strict allowlist prevents arbitrary source/user text in audit details.
        if not isinstance(self.details, dict): raise ValidationError('Invalid audit details')
        for key, value in self.details.items():
            if key == 'excerpt_hash':
                if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                    raise ValidationError('Invalid excerpt hash')
            elif key in ('count', 'version', 'result_count','rollback_from_version','previous_current_version','created_version'):
                if type(value) is not int or value < 0: raise ValidationError('Invalid audit count')
            else: raise ValidationError('Audit details may contain only hashes and counts')
        object.__setattr__(self, 'details', freeze_json(self.details))


def audit_hash(event):
    """Hash every contract field except event_hash, then '|' + prev_hash.

    Canonical JSON uses sort_keys=True, separators=(',', ':') and the stdlib
    default ensure_ascii=True. prev_hash is itself also in the canonical payload.
    """
    payload = event.to_dict(); payload.pop('event_hash')
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256((raw + '|' + event.prev_hash).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class AuditChainReport(PolicyContract):
    org_id: str
    valid: bool
    checked: int = 0
    first_invalid_seq: Optional[int] = None
    reason_code: str = 'ok'
    last_hash: str = '0' * 64
