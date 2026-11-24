"""Strict, dependency-free policy contracts. No condition DSL or persistence schema."""
from __future__ import annotations
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, Optional, Tuple
from ..exceptions import ValidationError


class Purpose(str, Enum):
    READ = 'read'
    GROUND_INTERNAL_LLM = 'ground_internal_llm'
    GROUND_EXTERNAL_LLM = 'ground_external_llm'
    EXPORT = 'export'
    EVAL_AND_TRAIN = 'eval_and_train'


class PolicyAction(str, Enum):
    READ_CONTENT = 'read_content'
    SEARCH_INDEX = 'search_index'
    WRITE_DOCUMENT = 'write_document'
    MANAGE_SPACE = 'manage_space'
    APPROVE_RELEASE = 'approve_release'
    PUBLISH_RELEASE = 'publish_release'
    EXPORT_PACK = 'export_pack'
    REPORT_ISSUE = 'report_issue'


class DecisionEffect(str, Enum):
    ALLOW = 'allow'
    ALLOW_WITH_REDACTION = 'allow_with_redaction'
    DENY = 'deny'


class GovernanceTier(str, Enum):
    L1_AGILE = 'l1_agile'
    L2_CONTROLLED = 'l2_controlled'


def text(value, name, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ValidationError('Invalid ' + name)
    return value.strip() if nonempty else value


def enum_value(cls, value):
    if not isinstance(value, str):
        raise ValidationError('Invalid ' + cls.__name__)
    try:
        return cls(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Invalid ' + cls.__name__) from exc


def sequence(value, name, cls=None, nonempty=False):
    if not isinstance(value, (list, tuple)) or (nonempty and not value):
        raise ValidationError('Invalid ' + name)
    return tuple(enum_value(cls, v) if cls else text(v, name, True) for v in value)


def parse_time(value, name='timestamp'):
    text(value, name, True)
    try:
        result = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValidationError('Invalid timezone-aware ' + name) from exc


class FrozenDict(dict):
    """JSON-compatible snapshot; normal mutation and nested list aliasing blocked."""
    def _immutable(self, *args, **kwargs):
        raise TypeError('Immutable policy metadata')
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable
    def __copy__(self): return self
    def __deepcopy__(self, memo): return self


def freeze_json(value):
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValidationError('Policy metadata keys must be strings')
        return FrozenDict((k, freeze_json(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(v) for v in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValidationError('Policy metadata must be finite JSON values')


class PolicyContract:
    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValidationError('Invalid ' + cls.__name__ + ' fields')
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValidationError('Invalid ' + cls.__name__ + ' fields') from exc

    def to_dict(self):
        def convert(v):
            if isinstance(v, Enum): return v.value
            if isinstance(v, (list, tuple)): return [convert(x) for x in v]
            if isinstance(v, dict): return {k: convert(x) for k, x in v.items()}
            return v
        return {f.name: convert(getattr(self, f.name)) for f in fields(self)}


@dataclass(frozen=True)
class AgentIdentity(PolicyContract):
    agent_id: str
    org_id: str
    app_id: str = ''
    allowed_purposes: Tuple[Purpose, ...] = (Purpose.READ, Purpose.GROUND_INTERNAL_LLM)
    allowed_kb_ids: Tuple[str, ...] = ()
    max_clearance_level: str = ''
    profile_version: str = '1'

    def __post_init__(self):
        for name in ('agent_id', 'org_id'):
            object.__setattr__(self, name, text(getattr(self, name), name, True))
        for name in ('app_id', 'max_clearance_level', 'profile_version'):
            text(getattr(self, name), name)
        object.__setattr__(self, 'allowed_purposes', sequence(self.allowed_purposes, 'allowed_purposes', Purpose))
        object.__setattr__(self, 'allowed_kb_ids', sequence(self.allowed_kb_ids, 'allowed_kb_ids'))


@dataclass(frozen=True)
class ResourceRights(PolicyContract):
    # Task-book Step 7 correction: EXPORT included so default allow_export=True
    # is meaningful. Explicit allowed_purposes always intersects boolean rights.
    allowed_purposes: Tuple[Purpose, ...] = (Purpose.READ, Purpose.GROUND_INTERNAL_LLM, Purpose.EXPORT)
    allow_external_llm: bool = False
    allow_export: bool = True
    allow_eval_and_train: bool = False
    redaction_profile: str = ''
    license_id: str = ''
    license_terms_version: str = ''
    retention_until: Optional[str] = None
    revoked: bool = False
    revocation_reason: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'allowed_purposes', sequence(self.allowed_purposes, 'allowed_purposes', Purpose))
        for name in ('allow_external_llm','allow_export','allow_eval_and_train','revoked'):
            if type(getattr(self, name)) is not bool:
                raise ValidationError('Invalid ' + name)
        for name in ('redaction_profile','license_id','license_terms_version','revocation_reason'):
            text(getattr(self, name), name)
        if self.retention_until is not None: parse_time(self.retention_until, 'retention_until')
        validate_profiles(self.redaction_profile)


def validate_profiles(value):
    if value and any(not p.strip() or p != p.strip() for p in value.split(',')):
        raise ValidationError('Invalid redaction profile list')


@dataclass(frozen=True)
class PolicyRule(PolicyContract):
    rule_id: str
    org_id: str
    effect: DecisionEffect
    priority: int = 100
    scope_kb_id: str = ''
    scope_doc_id: str = ''
    actions: Tuple[PolicyAction, ...] = (PolicyAction.READ_CONTENT,)
    purposes: Tuple[Purpose, ...] = (Purpose.READ,)
    match_users: Tuple[str, ...] = ()
    match_org_roles: Tuple[str, ...] = ()
    match_departments: Tuple[str, ...] = ()
    match_agent_ids: Tuple[str, ...] = ()
    required_clearance: str = ''
    redaction_profile: str = ''
    condition_meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ('rule_id','org_id'):
            object.__setattr__(self, name, text(getattr(self, name), name, True))
        for name in ('scope_kb_id','scope_doc_id','required_clearance','redaction_profile'):
            text(getattr(self, name), name)
        if type(self.priority) is not int: raise ValidationError('Invalid priority')
        object.__setattr__(self, 'effect', enum_value(DecisionEffect, self.effect))
        object.__setattr__(self, 'actions', sequence(self.actions, 'actions', PolicyAction, True))
        object.__setattr__(self, 'purposes', sequence(self.purposes, 'purposes', Purpose, True))
        for name in ('match_users','match_org_roles','match_departments','match_agent_ids'):
            object.__setattr__(self, name, sequence(getattr(self, name), name))
        if not isinstance(self.condition_meta, dict) or self.condition_meta:
            raise ValidationError('Unsupported policy conditions')
        object.__setattr__(self, 'condition_meta', freeze_json(self.condition_meta))
        validate_profiles(self.redaction_profile)
        if self.effect == DecisionEffect.ALLOW_WITH_REDACTION and not self.redaction_profile:
            raise ValidationError('Redaction rule requires a profile')


@dataclass(frozen=True)
class PolicyContext(PolicyContract):
    request_id: str = ''
    task_id: str = ''
    stage: str = ''
    policy_generation: str = ''
    include_archived: bool = False
    now: Optional[str] = None

    def __post_init__(self):
        for name in ('request_id','task_id','stage','policy_generation'):
            text(getattr(self, name), name)
        if type(self.include_archived) is not bool: raise ValidationError('Invalid include_archived')
        if self.now is not None: parse_time(self.now, 'now')


@dataclass(frozen=True)
class PolicyDecision(PolicyContract):
    effect: DecisionEffect
    reason_code: str
    policy_generation: str
    matched_rule_ids: Tuple[str, ...] = ()
    redaction_profile: str = ''
    audit_summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'effect', enum_value(DecisionEffect, self.effect))
        text(self.reason_code, 'reason_code', True)
        text(self.policy_generation, 'policy_generation')
        text(self.redaction_profile, 'redaction_profile')
        validate_profiles(self.redaction_profile)
        if self.effect == DecisionEffect.ALLOW_WITH_REDACTION and not self.redaction_profile:
            raise ValidationError('Redaction decision requires a profile')
        object.__setattr__(self, 'matched_rule_ids', sequence(self.matched_rule_ids, 'matched_rule_ids'))
        if not isinstance(self.audit_summary, dict): raise ValidationError('Invalid audit_summary')
        object.__setattr__(self, 'audit_summary', freeze_json(self.audit_summary))

    @property
    def allowed(self):
        return self.effect in (DecisionEffect.ALLOW, DecisionEffect.ALLOW_WITH_REDACTION)
