"""Pure host-directory adapter. Invalid or ambiguous trees fail closed."""
from __future__ import annotations
from typing import Iterable, Mapping, Any, Tuple
from ..exceptions import ValidationError


def expand_department_ancestors(department_ids: Iterable[str], departments: Iterable[Mapping[str, Any]]) -> Tuple[str, ...]:
    parents = {}
    organizations = {}
    for node in departments:
        identity = node.get("id")
        parent = node.get("parentId", node.get("parent_id"))
        if not isinstance(identity, str) or not identity or identity in parents or (parent is not None and (not isinstance(parent, str) or not parent)):
            raise ValidationError("Invalid or duplicate department")
        parents[identity] = parent
        organizations[identity] = node.get("organizationId", node.get("organization_id"))
    # Validate the entire supplied forest, not only paths used by this user.
    resolved = {}
    for identity in parents:
        path = []; seen = set(); cursor = identity
        while cursor is not None and cursor not in resolved:
            if cursor not in parents: raise ValidationError("Missing parent department")
            if cursor in seen: raise ValidationError("Department cycle")
            seen.add(cursor); path.append(cursor)
            parent = parents[cursor]
            if parent in organizations and organizations[cursor] and organizations[parent] and organizations[cursor] != organizations[parent]:
                raise ValidationError("Cross-organization department edge")
            cursor = parent
        chain = (cursor,) + resolved[cursor] if cursor is not None else ()
        for item in reversed(path):
            resolved[item] = chain
            chain = (item,) + chain
    if isinstance(department_ids, str): raise ValidationError("Expected department sequence")
    result = set()
    for identity in department_ids:
        if identity not in resolved: raise ValidationError("Unknown user department")
        result.update(resolved[identity])
    return tuple(sorted(result))
