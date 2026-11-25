from __future__ import annotations
"""No admin/owner escape hatch from authoritative session revocation."""
from ..exceptions import PermissionDeniedError


def check_principal(store,actor,*,required=False):
    principal=store.get_principal(actor.org_id,actor.user_id) if hasattr(store,'get_principal') else None
    if principal is None:
        if required:raise PermissionDeniedError('principal_required')
        return
    try:valid=principal.active and int(actor.policy_generation)>=principal.policy_generation
    except (ValueError,TypeError,OverflowError):valid=False
    if not valid:raise PermissionDeniedError('principal_session_stale')
