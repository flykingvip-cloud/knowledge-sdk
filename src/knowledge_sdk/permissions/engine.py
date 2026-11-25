"""Eight ordered policy gates. SQLite-backed callers supply authoritative objects."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Protocol, Sequence
from ..contracts.models import Actor, KnowledgeBase, Document, DocumentACL
from ..contracts.policy import (AgentIdentity, ResourceRights, PolicyRule, PolicyContext,
                                PolicyDecision, Purpose, PolicyAction, DecisionEffect,
                                GovernanceTier, enum_value, parse_time)
from ..exceptions import ValidationError
from .policy import can_manage_kb, can_upload_to_kb, can_read, _tier_read

LEVELS = ('public', 'internal', 'confidential', 'restricted')
CONTENT_ACTIONS = (PolicyAction.READ_CONTENT, PolicyAction.SEARCH_INDEX, PolicyAction.EXPORT_PACK)


class KnowledgePolicyEngine(Protocol):
    def evaluate(self, actor: Actor, agent: Optional[AgentIdentity], kb: KnowledgeBase,
                 document: Optional[Document] = None, acl: Optional[DocumentACL] = None,
                 member_role: Optional[str] = None, action: PolicyAction = PolicyAction.READ_CONTENT,
                 purpose: Purpose = Purpose.READ, context: Optional[PolicyContext] = None) -> PolicyDecision:
        ...


def _clearance(actual, required):
    return actual in LEVELS and required in LEVELS and LEVELS.index(actual) >= LEVELS.index(required)


def _unique(values):
    return tuple(dict.fromkeys(values))


def merge_profiles(values):
    return ','.join(_unique(p for value in values for p in value.split(',') if p))


class DefaultPolicyEngine:
    def __init__(self, rules=(), *, principal_store=None, require_principal=False):
        self.principal_store=principal_store;self.require_principal=require_principal
        if not isinstance(rules, (list, tuple)) or any(not isinstance(r, PolicyRule) for r in rules):
            raise ValidationError('Expected policy rules')
        if len({(r.org_id,r.rule_id) for r in rules}) != len(rules):
            raise ValidationError('Duplicate policy rule id')
        self.rules = tuple(sorted(rules, key=lambda r: r.priority))

    @staticmethod
    def _matches(rule, actor, agent, kb, document, action, purpose):
        return (rule.org_id == actor.org_id == kb.org_id
                and (not rule.scope_kb_id or rule.scope_kb_id == kb.kb_id)
                and (not rule.scope_doc_id or document is not None and rule.scope_doc_id == document.doc_id)
                and action in rule.actions and purpose in rule.purposes
                and (not rule.match_users or actor.user_id in rule.match_users)
                and (not rule.match_org_roles or bool(set(actor.org_roles) & set(rule.match_org_roles)))
                and (not rule.match_departments or bool(set(actor.department_ids) & set(rule.match_departments)))
                and (not rule.match_agent_ids or agent is not None and agent.agent_id in rule.match_agent_ids))

    def evaluate(self, actor, agent, kb, document=None, acl=None, member_role=None,
                 action=PolicyAction.READ_CONTENT, purpose=Purpose.READ, context=None):
        if not isinstance(actor, Actor) or not isinstance(kb, KnowledgeBase):
            raise ValidationError('Invalid policy identity/resource')
        if document is not None and not isinstance(document, Document): raise ValidationError('Invalid document')
        if agent is not None and not isinstance(agent, AgentIdentity): raise ValidationError('Invalid agent')
        context = context if context is not None else PolicyContext()
        if not isinstance(context, PolicyContext): raise ValidationError('Invalid policy context')
        action, purpose = enum_value(PolicyAction, action), enum_value(Purpose, purpose)
        generation = context.policy_generation or actor.policy_generation
        acl = acl if acl is not None else DocumentACL()
        if not isinstance(acl, DocumentACL): raise ValidationError('Invalid ACL')
        def decision(reason, effect=DecisionEffect.DENY, rules=(), profile=''):
            # Deliberately no title, body, resource id, or existence detail.
            return PolicyDecision(effect, reason, generation, tuple(r.rule_id for r in rules), profile)
        if self.principal_store is not None:
            from .identity import check_principal
            from ..exceptions import PermissionDeniedError
            try:check_principal(self.principal_store,actor,required=self.require_principal)
            except PermissionDeniedError:
                from ..audit.ledger import append
                append(self.principal_store,actor,'evaluate_policy',effect=DecisionEffect.DENY,reason='principal_session_stale')
                return decision('principal_session_stale')
        # 1. Tenant boundary is never overridable by a rule or owner/admin grant.
        if actor.org_id != kb.org_id or document is not None and document.org_id != actor.org_id or agent is not None and agent.org_id != actor.org_id:
            return decision('tenant_mismatch')
        if document is not None and document.kb_id != kb.kb_id:
            return decision('space_boundary_denied')
        # 2. Resource state and validity precede all explicit grants.
        rights = None
        if document is not None:
            rights = document.rights or ResourceRights()
            if not isinstance(rights, ResourceRights): return decision('invalid_resource_rights')
            if document.lifecycle_state == 'revoked' or rights.revoked: return decision('resource_revoked')
            if document.archived and not context.include_archived: return decision('resource_archived')
            if (kb.governance_tier == GovernanceTier.L2_CONTROLLED and action in CONTENT_ACTIONS
                and document.lifecycle_state != 'published' and actor.user_id != document.owner_id
                and not can_manage_kb(actor, kb, member_role)):
                return decision('lifecycle_not_published')
            try:
                now = parse_time(context.now) if context.now is not None else datetime.now(timezone.utc)
                if action in CONTENT_ACTIONS and ((document.valid_from is not None and now < parse_time(document.valid_from))
                    or (document.valid_to is not None and now > parse_time(document.valid_to))):
                    return decision('outside_validity_window')
            except (ValidationError, ValueError, TypeError, OverflowError):
                return decision('outside_validity_window')
        # 3. Explicit deny outranks ALL allows. DENY required_clearance cannot
        # weaken a deny: it is treated conservatively as no additional exemption.
        if (actor.user_id in acl.deny_users or set(actor.roles) & set(acl.deny_roles)
            or set(actor.department_ids) & set(acl.deny_departments)):
            return decision('explicit_acl_deny')
        matching = tuple(r for r in self.rules if self._matches(r, actor, agent, kb, document, action, purpose))
        denying = tuple(r for r in matching if r.effect == DecisionEffect.DENY)
        if denying: return decision('explicit_policy_deny', rules=denying)
        # 4. A document grant never broadens space membership/upload/management.
        if action in (PolicyAction.MANAGE_SPACE, PolicyAction.APPROVE_RELEASE, PolicyAction.PUBLISH_RELEASE):
            boundary = can_manage_kb(actor, kb, member_role)
        elif action == PolicyAction.WRITE_DOCUMENT:
            boundary = can_upload_to_kb(actor, kb, member_role)
        else:
            boundary = (can_manage_kb(actor, kb, member_role) or bool(member_role)
                        or kb.visibility == 'enterprise' or _tier_read(actor, kb))
        if not boundary: return decision('space_boundary_denied')
        permitted = tuple(r for r in matching if r.effect != DecisionEffect.DENY and
                          (not r.required_clearance or _clearance(actor.clearance_level, r.required_clearance)))
        # 5. Preserve every existing fine ACL/visibility/legacy grant. Personal
        # ACLs cannot be opened by rules; legacy private docs require a targeted
        # user+document rule, not a broad organization wildcard.
        if document is not None:
            acl_ok = can_read(actor, kb, document, acl, member_role, context.include_archived)
            rule_grants = permitted
            if acl.access_level == 'personal_only' and not acl_ok:
                rule_grants = ()
            elif not acl.access_level and document.visibility == 'private' and not acl_ok:
                rule_grants = tuple(r for r in permitted if r.scope_doc_id == document.doc_id and actor.user_id in r.match_users)
            if not acl_ok and not rule_grants: return decision('document_acl_denied')
        # 6. Agent identity only narrows actor authority, including space-only ops.
        if agent is not None:
            if purpose not in agent.allowed_purposes: return decision('agent_purpose_denied')
            if agent.allowed_kb_ids and kb.kb_id not in agent.allowed_kb_ids: return decision('agent_scope_denied')
            if agent.max_clearance_level and acl.required_clearance and not _clearance(agent.max_clearance_level, acl.required_clearance):
                return decision('agent_clearance_exceeded')
        if document is None: return decision('ok', DecisionEffect.ALLOW)
        # 7. Resource usage rights are independent of actor/agent ACL permission.
        try:
            if rights.retention_until is not None and now > parse_time(rights.retention_until): return decision('retention_expired')
        except (ValidationError, TypeError, ValueError, OverflowError):
            return decision('retention_expired')
        if purpose == Purpose.GROUND_EXTERNAL_LLM and not rights.allow_external_llm: return decision('external_llm_prohibited')
        if (purpose == Purpose.EXPORT or action == PolicyAction.EXPORT_PACK) and not rights.allow_export: return decision('export_prohibited')
        if action == PolicyAction.EXPORT_PACK and Purpose.EXPORT not in rights.allowed_purposes:return decision('export_prohibited')
        if purpose == Purpose.EVAL_AND_TRAIN and not rights.allow_eval_and_train: return decision('training_prohibited')
        if purpose not in rights.allowed_purposes: return decision('purpose_not_permitted')
        # 8. Every applicable redaction obligation survives priority resolution.
        profile = merge_profiles((rights.redaction_profile,) + tuple(r.redaction_profile for r in permitted if r.effect == DecisionEffect.ALLOW_WITH_REDACTION))
        return decision('redaction_required' if profile else 'ok',
                        DecisionEffect.ALLOW_WITH_REDACTION if profile else DecisionEffect.ALLOW, permitted, profile)


def intersect_decisions(decisions: Sequence[PolicyDecision]) -> PolicyDecision:
    if not isinstance(decisions, (list, tuple)) or any(not isinstance(d, PolicyDecision) for d in decisions):
        raise ValidationError('Expected source policy decisions')
    if not decisions: return PolicyDecision(DecisionEffect.DENY, 'empty_source_decisions', '0')
    generations = _unique(d.policy_generation for d in decisions)
    generation = generations[0] if len(generations) == 1 else 'mixed'
    summary = {} if len(generations) == 1 else {'mixed_policy_generations': True, 'source_policy_generations': generations}
    ids = _unique(r for d in decisions for r in d.matched_rule_ids)
    if any(not d.allowed for d in decisions):
        return PolicyDecision(DecisionEffect.DENY, 'derived_source_denied', generation, ids, audit_summary=summary)
    profile = merge_profiles(tuple(d.redaction_profile for d in decisions))
    return PolicyDecision(DecisionEffect.ALLOW_WITH_REDACTION if profile else DecisionEffect.ALLOW,
                          'redaction_required' if profile else 'ok', generation, ids, profile, summary)
