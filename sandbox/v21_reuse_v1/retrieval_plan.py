"""KnowledgeRetrievalPlan dual-view redaction (M-04). No unauthorized existence side-channel."""
from __future__ import annotations
import hashlib, json
from typing import List, Dict

AUDIT_VIEWS = frozenset({'audit', 'governance'})
REDACTED_VIEWS = frozenset({'agent', 'end_user'})


class RetrievalPlanError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class KnowledgeRetrievalPlan(object):
    def __init__(self, tenant_id, policy_generation, authorized, excluded):
        if type(policy_generation) is not int or isinstance(policy_generation, bool) or not 1 <= policy_generation <= 9007199254740991:
            raise RetrievalPlanError('INVALID_POLICY_GENERATION')
        self.tenant_id = tenant_id
        self.policy_generation = policy_generation
        self.authorized = list(authorized)
        self.excluded = list(excluded)  # list of dict(resource_id, permission_denied)

    def render(self, viewer):
        if viewer in AUDIT_VIEWS:
            return dict(view=viewer, resources_excluded=[dict(resource_id=item['resource_id'], permission_denied=item['permission_denied']) for item in self.excluded], authorized_count=len(self.authorized))
        if viewer in REDACTED_VIEWS:
            seed = json.dumps(dict(tenant_id=self.tenant_id, policy_generation=self.policy_generation, count=len(self.excluded)), sort_keys=True).encode('utf-8')
            code = hashlib.sha256(seed).hexdigest()[:16]
            view = dict(view=viewer, redacted_unauthorized_count=len(self.excluded), redaction_code=code, authorized_count=len(self.authorized))
            leaked = [key for key in view if key in ('resources_excluded', 'resource_id', 'permission_denied', 'titles')]
            if leaked:
                raise RetrievalPlanError('SIDE_CHANNEL')
            # existence side-channel guard: never include unauthorized identifiers
            dumped = json.dumps(view)
            for item in self.excluded:
                if item['resource_id'] in dumped or item['permission_denied'] in dumped:
                    raise RetrievalPlanError('SIDE_CHANNEL')
            return view
        raise RetrievalPlanError('INVALID_VIEWER')
