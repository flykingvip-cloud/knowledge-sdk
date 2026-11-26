"""KSG-Lite Phase 0 plugin. Mounts on existing governance/workflow.py and issues.py
as a standard validation interface. No new production tables and no edits to those modules.
"""
from __future__ import annotations
import inspect
from knowledge_sdk.governance import workflow as governance_workflow
from knowledge_sdk.governance import issues as governance_issues

ALLOWED_OPERATIONS = frozenset({'submit_for_review', 'approve_release', 'publish_release', 'resolve_evidence_issue'})


class KSGDecision(object):
    def __init__(self, allowed, reason_code='OK'):
        self.allowed = allowed
        self.reason_code = reason_code

    def as_dict(self):
        return dict(allowed=self.allowed, reason_code=self.reason_code)


class KSGLitePlugin(object):
    """Fail-closed validation hook. Does not execute governance writes."""

    def __init__(self):
        # Bind to *existing* official operation names without wrapping production objects by default.
        self.workflow_operations = tuple(name for name in ('submit_for_review', 'approve_release', 'reject_release', 'publish_release') if hasattr(governance_workflow.GovernanceMixin, name))
        self.issue_operations = tuple(name for name in ('resolve_evidence_issue',) if hasattr(governance_issues.IssueMixin, name))
        self._assert_existing_interface()

    def _assert_existing_interface(self):
        for name in self.workflow_operations:
            inspect.signature(getattr(governance_workflow.GovernanceMixin, name))
        for name in self.issue_operations:
            inspect.signature(getattr(governance_issues.IssueMixin, name))

    def validate(self, operation, payload):
        if operation not in ALLOWED_OPERATIONS:
            return KSGDecision(False, 'UNKNOWN_OPERATION')
        if not isinstance(payload, dict):
            return KSGDecision(False, 'INVALID_PAYLOAD')
        policy = payload.get('policy_generation')
        if type(policy) is not int or isinstance(policy, bool) or not 1 <= policy <= 9007199254740991:
            return KSGDecision(False, 'INVALID_POLICY_GENERATION')
        if payload.get('visibility') == 'partial_available' or payload.get('partial_available') is True:
            return KSGDecision(False, 'PARTIAL_PUBLICATION_FORBIDDEN')
        compliance = payload.get('compliance_class')
        if compliance in ('high_risk', 'strong_compliance'):
            if payload.get('whole_document_atomic_publication') is not True:
                return KSGDecision(False, 'ATOMIC_PUBLICATION_REQUIRED')
            if operation == 'publish_release' and payload.get('approved') is not True:
                return KSGDecision(False, 'APPROVAL_REQUIRED')
        if payload.get('current_policy_generation') is not None and payload['current_policy_generation'] != policy:
            return KSGDecision(False, 'POLICY_GENERATION_STALE')
        return KSGDecision(True, 'OK')

    def bind(self, governance_client):
        """Return a validating proxy. The original mixin classes are not modified."""
        plugin = self

        class Proxy(object):
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                target = getattr(self._inner, name)
                if name not in ALLOWED_OPERATIONS:
                    return target

                def gated(*args, **kwargs):
                    payload = kwargs.get('policy_context') or kwargs
                    decision = plugin.validate(name, payload if isinstance(payload, dict) else {})
                    if not decision.allowed:
                        raise PermissionError(decision.reason_code)
                    return target(*args, **kwargs)
                return gated
        return Proxy(governance_client)
