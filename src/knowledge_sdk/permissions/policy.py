from __future__ import annotations
from typing import Optional
from ..contracts.models import Actor, KnowledgeBase, Document, DocumentACL

def _legacy_admin(actor, kb, member_role=None):
    return actor.org_id == kb.org_id and (actor.user_id == kb.owner_id or member_role == "admin")

def _legacy_write(actor, kb, member_role=None):
    return _legacy_admin(actor, kb, member_role) or (actor.org_id == kb.org_id and member_role == "editor")

def can_manage_kb(actor: Actor, kb: KnowledgeBase, member_role: Optional[str] = None) -> bool:
    """Trusted host claims, never client role headers; org is always a hard boundary."""
    if actor.org_id != kb.org_id: return False
    if kb.legacy_permissions: return _legacy_admin(actor, kb, member_role)
    if kb.space_type == "enterprise_public":
        return "admin" in actor.org_roles or actor.public_kb_admin
    if kb.space_type == "department":
        return bool(kb.owner_department_id) and kb.owner_department_id in actor.managed_department_ids
    return actor.user_id == kb.owner_user_id


def can_upload_to_kb(actor: Actor, kb: KnowledgeBase, member_role: Optional[str] = None) -> bool:
    if kb.legacy_permissions: return _legacy_write(actor, kb, member_role)
    return can_manage_kb(actor, kb, member_role)


can_admin = can_manage_kb
can_write = can_upload_to_kb


def _tier_read(actor: Actor, kb: KnowledgeBase) -> bool:
    if kb.legacy_permissions: return False
    if kb.space_type == "enterprise_public": return True
    if kb.space_type == "department":
        return kb.owner_department_id in actor.department_ids or kb.owner_department_id in actor.ancestor_department_ids or kb.owner_department_id in actor.managed_department_ids
    return actor.user_id == kb.owner_user_id


def _fine_acl(actor: Actor, document: Document, acl: DocumentACL) -> bool:
    if acl.access_level == "org_public": return True
    if acl.access_level == "personal_only":
        return actor.user_id == document.owner_id or actor.user_id in acl.allowed_user_ids
    if acl.access_level == "department":
        departments = set(actor.department_ids)
        if acl.include_sub_departments: departments.update(actor.ancestor_department_ids)
        return bool(departments.intersection(acl.allowed_department_ids))
    if acl.access_level == "role_clearance":
        # Configured dimensions are conjunctive, entries in each dimension disjunctive.
        if not (acl.allowed_org_roles or acl.required_clearance or acl.allowed_clearance_tags): return False
        if acl.allowed_org_roles and not set(actor.org_roles).intersection(acl.allowed_org_roles): return False
        levels = ("public", "internal", "confidential", "restricted")
        if acl.required_clearance:
            if acl.required_clearance in levels:
                if actor.clearance_level not in levels or levels.index(actor.clearance_level) < levels.index(acl.required_clearance): return False
            elif actor.clearance_level != acl.required_clearance: return False
        if acl.allowed_clearance_tags and not set(actor.clearance_tags).intersection(acl.allowed_clearance_tags): return False
        return True
    return False


def can_read(actor, kb, document=None, acl=None, member_role=None, include_archived=False):
    if actor.org_id != kb.org_id: return False
    if document and (document.org_id != actor.org_id or (document.archived and not include_archived)): return False
    acl = acl or DocumentACL()
    # Denials override ownership and administrative grants for content reads.
    if actor.user_id in acl.deny_users or set(actor.roles) & set(acl.deny_roles) or set(actor.department_ids) & set(acl.deny_departments): return False
    # KB access is a hard boundary: document grants never bypass it.
    kb_access = can_admin(actor, kb, member_role) or bool(member_role) or kb.visibility == "enterprise" or _tier_read(actor, kb)
    if not kb_access: return False
    if document is None: return True
    if acl.access_level: return _fine_acl(actor, document, acl)
    if actor.user_id == document.owner_id or can_admin(actor, kb, member_role): return True
    explicit = actor.user_id in acl.allow_users or bool(set(actor.roles) & set(acl.allow_roles)) or bool(set(actor.department_ids) & set(acl.allow_departments))
    restricted = bool(acl.allow_users or acl.allow_roles or acl.allow_departments)
    if restricted: return explicit
    return explicit or document.visibility == "enterprise" or (document.visibility == "team" and (bool(member_role) or _tier_read(actor, kb)))

def scope_filter(actor, documents, kb_lookup, role_lookup, acl_lookup):
    return [d for d in documents if can_read(actor, kb_lookup(d.kb_id), d, acl_lookup(d.doc_id), role_lookup(d.kb_id, actor.user_id))]
