"""Dependency-free transactional event and delivery contracts."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Optional
from .policy import PolicyContract, text, freeze_json, parse_time
from ..exceptions import ValidationError

EVENT_TYPES = frozenset(('agent.profile_registered','agent.profile_updated','task.revoked','principal.policy_bumped','doc.ingested','doc.draft_created','issue.resolved','doc.published','doc.revised','doc.archived','doc.restored',
                        'doc.revoked','acl.updated','rights.updated','anchor.drifted',
                        'anchor.orphaned','anchor.reanchored'))


@dataclass(frozen=True)
class OutboxEvent(PolicyContract):
    event_id: str
    org_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = 'pending'
    attempts: int = 0
    available_at: str = ''
    created_at: str = ''
    dispatched_at: Optional[str] = None

    def __post_init__(self):
        for name in ('event_id','org_id','aggregate_id'): text(getattr(self,name),name,True)
        if self.aggregate_type not in ('document','anchor','issue','pack','acl','principal','agent_profile','task_context'):
            raise ValidationError('Invalid aggregate_type')
        if self.event_type not in EVENT_TYPES: raise ValidationError('Invalid event_type')
        if self.status not in ('pending','failed','processing','dispatched','dead_letter'):
            raise ValidationError('Invalid outbox status')
        if type(self.attempts) is not int or self.attempts < 0: raise ValidationError('Invalid attempts')
        parse_time(self.available_at);parse_time(self.created_at)
        if self.dispatched_at is not None: parse_time(self.dispatched_at)
        if not isinstance(self.payload,dict): raise ValidationError('Invalid payload')
        # Broadcast identifiers only: never user text, titles, secrets or excerpts.
        for key,value in self.payload.items():
            if key in ('doc_id','anchor_id','user_id','agent_id','task_id','reason_code'):
                text(value,key,True)
            elif key in ('version','previous_version','policy_generation','profile_generation'):
                if type(value) is not int or value<0:raise ValidationError('Invalid payload version')
            else:raise ValidationError('Outbox payload may contain only identifiers and versions')
        object.__setattr__(self,'payload',freeze_json(self.payload))


@dataclass(frozen=True)
class DispatchSummary(PolicyContract):
    claimed: int = 0
    dispatched: int = 0
    failed: int = 0
    dead_letter: int = 0


@dataclass(frozen=True)
class WebhookSubscription(PolicyContract):
    subscription_id: str
    org_id: str
    url: str
    secret: str = field(repr=False)
    event_types: Tuple[str, ...] = ()
    active: bool = True
    allow_insecure_local: bool = False

    def __post_init__(self):
        for name in ('subscription_id','org_id','url'):text(getattr(self,name),name,True)
        if not isinstance(self.secret,str) or len(self.secret)<32:raise ValidationError('Webhook secret must have at least 32 characters')
        if not isinstance(self.event_types,(tuple,list)) or not self.event_types or any(e not in EVENT_TYPES for e in self.event_types):
            raise ValidationError('Invalid webhook event_types')
        object.__setattr__(self,'event_types',tuple(self.event_types))
        if type(self.active) is not bool or type(self.allow_insecure_local) is not bool:
            raise ValidationError('Invalid webhook flags')

    def public_dict(self):
        value=self.to_dict();value.pop('secret');return value


@dataclass(frozen=True)
class WebhookDelivery(PolicyContract):
    delivery_id: str
    org_id: str
    subscription_id: str
    outbox_event_id: str
    status: str
    http_status: int = 0
    attempted_at: str = ''
    reason_code: str = ''

    def __post_init__(self):
        for name in ('delivery_id','org_id','subscription_id','outbox_event_id'):text(getattr(self,name),name,True)
        if self.status not in ('delivered','failed','dead_letter'):raise ValidationError('Invalid delivery status')
        if type(self.http_status) is not int or not 0<=self.http_status<=599:raise ValidationError('Invalid HTTP status')
        parse_time(self.attempted_at)
