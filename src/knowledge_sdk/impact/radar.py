"""Deterministic, idempotent impact computation; never mutates old evidence."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import uuid
from ..contracts.impact import ImpactAlert, ImpactReason
from ..contracts.models import Actor, decode
from ..contracts.policy import AgentIdentity, PolicyContext, DecisionEffect
from ..exceptions import NotFoundError, PermissionDeniedError, ValidationError


def binding_target_id(actor_id,consumer_type,consumer_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([actor_id,consumer_type,consumer_id],separators=(',',':'))))


class ImpactRadar:
    def __init__(self,client):self.client=client;self.store=client.store

    def _lost_access(self,event,actor,agent,purpose):
        try:
            expected_user=actor.user_id;expected_agent=agent.agent_id if agent else ''
            if self.client.identity_resolver is not None:
                value=self.client.identity_resolver(event.org_id,actor.user_id,agent.agent_id if agent else '')
                if isinstance(value,Actor):actor=value;agent=None
                else:actor,agent=value
            if not isinstance(actor,Actor) or (actor.org_id,actor.user_id)!=(event.org_id,expected_user):return True
            if expected_agent and (agent is None or agent.agent_id!=expected_agent or agent.org_id!=event.org_id):return True
            decision=self.client.evaluate_policy(actor,event.payload['doc_id'],agent=agent,purpose=purpose,
                                                   policy_context=PolicyContext())
            if not decision.allowed:return True
            if decision.effect==DecisionEffect.ALLOW_WITH_REDACTION:
                self.client.redaction_registry.apply('',decision.redaction_profile,purpose)
            return False
        except (NotFoundError,PermissionDeniedError,ValidationError,TypeError,ValueError):return True

    def _reason(self,event,version,anchor_id,actor,agent,purpose):
        kind=event.event_type;new_version=event.payload['version']
        if version>new_version:return None
        if kind in ('doc.revised','doc.published'):return ImpactReason.SUPERSEDED if version<new_version else None
        if kind=='doc.archived':return ImpactReason.RESOURCE_ARCHIVED
        if kind in ('doc.revoked','acl.updated','rights.updated'):
            return ImpactReason.ACCESS_REVOKED if self._lost_access(event,actor,agent,purpose) else None
        if kind in ('anchor.drifted','anchor.orphaned') and anchor_id and anchor_id==event.payload.get('anchor_id'):
            return ImpactReason.ANCHOR_DRIFTED if kind=='anchor.drifted' else ImpactReason.ANCHOR_ORPHANED
        return None

    def _alert(self,event,version,target_type,target_id,reason,actor_id,usage_id=''):
        key=json.dumps([event.org_id,event.event_id,target_type,target_id],separators=(',',':'))
        alert=ImpactAlert(str(uuid.uuid5(uuid.NAMESPACE_URL,key)),event.org_id,event.event_id,
                          event.payload['doc_id'],version,target_type,target_id,reason,
                          created_at=datetime.now(timezone.utc).isoformat())
        self.store.put_impact_alert(alert,actor_id=actor_id,usage_id=usage_id)

    def process(self,event):
        if event.event_type not in ('doc.revised','doc.published','doc.archived','doc.revoked','acl.updated','rights.updated','anchor.drifted','anchor.orphaned'):return
        doc_id=event.payload['doc_id']
        with self.client._lock, self.store._write_scope():
            document=self.store.get_document(doc_id)
            if document.org_id!=event.org_id:raise PermissionDeniedError('impact_tenant_mismatch')
            usages=self.store.list_usage_events_for_doc(event.org_id,doc_id)
            known_bindings=set()
            from ..contracts.policy import parse_time
            for usage in usages:
                if parse_time(usage.created_at)>parse_time(event.created_at):continue
                actor,agent=self.store.usage_identity(event.org_id,usage.usage_id)
                actor=actor or Actor(usage.actor_id,usage.org_id)
                if agent is None and usage.agent_id:agent=AgentIdentity(usage.agent_id,usage.org_id)
                binding_key=(usage.actor_id,usage.consumer_type,usage.consumer_id)
                if usage.consumer_type and usage.consumer_id:known_bindings.add(binding_key)
                reason=self._reason(event,usage.version,usage.anchor_id,actor,agent,usage.purpose)
                if reason is None:continue
                self._alert(event,usage.version,'usage_event',usage.usage_id,reason,usage.actor_id,usage.usage_id)
                if usage.consumer_type and usage.consumer_id:
                    self._alert(event,usage.version,'consumer_binding',binding_target_id(*binding_key),reason,usage.actor_id,usage.usage_id)
            # Pre-Q2 saved scopes have no material snapshots. Treat them as scope
            # subscriptions, not invented evidence receipts. Never rewrite them.
            kb=self.store.get_kb(document.kb_id)
            for user_id,binding in self.store.list_all_bindings(event.org_id):
                key=(user_id,binding.consumer_type,binding.consumer_id)
                if key in known_bindings or not binding.default_scope.contains(document,kb):continue
                if event.event_type.startswith('anchor.'):continue  # No anchor lineage to match.
                actor,agent,purpose=self.store.binding_identity(event.org_id,user_id,binding.consumer_type,binding.consumer_id)
                actor=actor or Actor(user_id,event.org_id)
                version=event.payload.get('previous_version') or event.payload['version']
                reason=self._reason(event,version,'',actor,agent,purpose)
                if reason is not None:self._alert(event,version,'consumer_binding',binding_target_id(*key),reason,user_id)
            # Reserved table only: accommodate already-imported sealed records;
            # no EvidencePack construction/export/governance service is added.
            rows=self.store.list_reserved_pack_records(event.org_id)
            for pack_id,data in rows:
                pack=decode(json.loads(data))
                if hasattr(pack,'to_dict'):pack=pack.to_dict()
                if not isinstance(pack,dict):raise ValidationError('Invalid reserved pack metadata')
                owner=pack.get('created_by','')
                for item in pack.get('items',()):
                    if not isinstance(item,dict) or item.get('doc_id')!=doc_id:continue
                    version=item.get('version')
                    if type(version) is not int or version<1:raise ValidationError('Invalid reserved pack version')
                    reason=self._reason(event,version,item.get('anchor_id',''),Actor(owner or 'unknown',event.org_id),None,pack.get('purpose_bound','export'))
                    if reason is not None:
                        self._alert(event,version,'evidence_pack',pack_id,reason,owner)
                        self.store.mark_reserved_pack_impacted(event.org_id,pack_id)
                        break
