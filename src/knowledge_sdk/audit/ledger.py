"""Tenant audit ledger; verification compares both indexed and encoded fields."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import uuid
from ..contracts.audit import AuditEvent, AuditChainReport, audit_hash
from ..contracts.policy import Purpose, DecisionEffect
from ..exceptions import ValidationError

ZERO = '0' * 64
COLUMNS = ('event_id', 'org_id', 'seq_no', 'prev_hash', 'event_hash', 'occurred_at',
           'actor_id', 'agent_id', 'action', 'purpose', 'resource_uri', 'doc_id',
           'decision_effect', 'reason_code', 'policy_generation', 'redaction_profile')


def append(store, actor, action, *, agent=None, purpose=Purpose.READ, doc_id='',
           effect=DecisionEffect.ALLOW, reason='ok', redaction_profile='',
           resource_uri='', request_id='', task_id='', details=None, policy_generation=None):
    event = AuditEvent(str(uuid.uuid4()), actor.org_id, 0, ZERO, ZERO,
                       datetime.now(timezone.utc).isoformat(), actor.user_id,
                       agent_id=agent.agent_id if agent else '', action=action,
                       purpose=purpose, doc_id=doc_id, decision_effect=effect,
                       reason_code=reason, policy_generation=actor.policy_generation if policy_generation is None else policy_generation,
                       redaction_profile=redaction_profile, resource_uri=resource_uri,
                       request_id=request_id, task_id=task_id, details=details or {})
    return store.append_audit_event(event)


def verify_audit_chain(store, org_id, *, from_seq=1, to_seq=None):
    if type(from_seq) is not int or from_seq < 1 or (to_seq is not None and
            (type(to_seq) is not int or to_seq < from_seq)):
        raise ValidationError('Invalid audit range')
    # Validate the prefix too, so partial verification never trusts a forged
    # predecessor as an unchecked trust anchor.
    expected, prev, checked = 1, ZERO, 0
    with store._write_scope():
        for row in store.iter_audit_chain(org_id, from_seq=1, to_seq=to_seq):
            try:
                event = store._audit_from_row(row)
                if not isinstance(event, AuditEvent): raise ValidationError("Invalid audit record")
                if event.seq_no != expected:
                    return AuditChainReport(org_id, False, checked, expected, 'sequence_gap', prev)
                values = event.to_dict()
                if any(values[name] != row[i] for i, name in enumerate(COLUMNS)):
                    return AuditChainReport(org_id, False, checked, expected, 'column_mismatch', prev)
                if event.prev_hash != prev or audit_hash(event) != event.event_hash:
                    return AuditChainReport(org_id, False, checked, expected, 'hash_mismatch', prev)
            except (ValueError, TypeError, KeyError, ValidationError):
                return AuditChainReport(org_id, False, checked, expected, 'invalid_record', prev)
            if expected >= from_seq: checked += 1
            prev = event.event_hash; expected += 1
        if to_seq is not None and expected <= to_seq:
            return AuditChainReport(org_id, False, checked, expected, 'sequence_gap', prev)
    return AuditChainReport(org_id, True, checked, last_hash=prev)
