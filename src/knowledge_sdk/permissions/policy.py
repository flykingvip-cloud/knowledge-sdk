from __future__ import annotations
from ..contracts.models import DocumentACL

def can_admin(actor, kb, member_role=None):
    return actor.org_id == kb.org_id and (actor.user_id == kb.owner_id or member_role == "admin")

def can_write(actor, kb, member_role=None):
    return can_admin(actor, kb, member_role) or (actor.org_id == kb.org_id and member_role == "editor")

def can_read(actor, kb, document=None, acl=None, member_role=None, include_archived=False):
    if actor.org_id != kb.org_id: return False
    if document and (document.org_id != actor.org_id or (document.archived and not include_archived)): return False
    acl = acl or DocumentACL()
    # Denials override ownership and administrative grants for content reads.
    if actor.user_id in acl.deny_users or set(actor.roles) & set(acl.deny_roles) or set(actor.department_ids) & set(acl.deny_departments): return False
    # KB access is a hard boundary: document grants never bypass it.
    kb_access = can_admin(actor, kb, member_role) or bool(member_role) or kb.visibility == "enterprise"
    if not kb_access: return False
    if document is None: return True
    if actor.user_id == document.owner_id or can_admin(actor, kb, member_role): return True
    explicit = actor.user_id in acl.allow_users or bool(set(actor.roles) & set(acl.allow_roles)) or bool(set(actor.department_ids) & set(acl.allow_departments))
    restricted = bool(acl.allow_users or acl.allow_roles or acl.allow_departments)
    if restricted: return explicit
    return explicit or document.visibility == "enterprise" or (document.visibility == "team" and bool(member_role))

def scope_filter(actor, documents, kb_lookup, role_lookup, acl_lookup):
    return [d for d in documents if can_read(actor, kb_lookup(d.kb_id), d, acl_lookup(d.doc_id), role_lookup(d.kb_id, actor.user_id))]
