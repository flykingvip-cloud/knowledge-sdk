from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from ..exceptions import ValidationError

class SpaceType(str, Enum):
    ENTERPRISE_PUBLIC = "enterprise_public"
    DEPARTMENT = "department"
    PERSONAL = "personal"


@dataclass(frozen=True)
class Actor:
    user_id: str
    org_id: str
    roles: Tuple[str, ...] = ()
    department_ids: Tuple[str, ...] = ()
    ancestor_department_ids: Tuple[str, ...] = ()
    org_roles: Tuple[str, ...] = ()
    clearance_level: str = ""
    clearance_tags: Tuple[str, ...] = ()
    managed_department_ids: Tuple[str, ...] = ()
    public_kb_admin: bool = False
    policy_generation: str = "0"
    session_id: str = ""
    def __post_init__(self):
        if not isinstance(self.policy_generation, str) or not isinstance(self.session_id, str):
            raise ValidationError("Invalid policy/session claims")
        if not isinstance(self.clearance_level, str) or not isinstance(self.public_kb_admin, bool):
            raise ValidationError("Invalid clearance/admin claims")
        if not isinstance(self.user_id,str) or not isinstance(self.org_id,str) or not self.user_id or not self.org_id:
            raise ValidationError("Actor requires user_id and org_id strings")
        for name in ("roles", "department_ids", "ancestor_department_ids", "org_roles", "clearance_tags", "managed_department_ids"):
            values = getattr(self, name)
            if not isinstance(values,(list,tuple)) or not all(isinstance(v,str) for v in values):
                raise ValidationError("Actor role/department claims must be string sequences")
            object.__setattr__(self, name, tuple(values))

@dataclass
class KnowledgeBase:
    kb_id: str
    org_id: str
    name: str
    owner_id: str
    visibility: str = "private"
    space_type: str = ""
    owner_department_id: str = ""
    owner_user_id: str = ""
    # Old persisted spaces retain v1.0 membership semantics; explicit tiers are strict.
    legacy_permissions: Optional[bool] = None

    def __post_init__(self):
        self.legacy_permissions = not bool(self.space_type) if self.legacy_permissions is None else self.legacy_permissions
        if not self.space_type:
            self.space_type = {"enterprise": "enterprise_public", "team": "department", "private": "personal"}.get(self.visibility, "")
        if self.space_type not in tuple(t.value for t in SpaceType):
            raise ValidationError("Invalid space type")
        if not self.legacy_permissions:
            self.visibility = {"enterprise_public": "enterprise", "department": "team", "personal": "private"}[self.space_type]
        if self.space_type == "personal" and not self.owner_user_id:
            self.owner_user_id = self.owner_id

@dataclass
class Document:
    doc_id: str
    org_id: str
    kb_id: str
    owner_id: str
    title: str
    visibility: str = "private"
    current_version: int = 1
    archived: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DocumentVersion:
    doc_id: str
    version: int
    text: str
    raw_hash: str
    semantic_hash: str
    created_at: str
    filename: str
    blob_key: Optional[str] = None

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    version: int
    text: str
    start_offset: int
    end_offset: int
    chunk_hash: str
    heading: str = ""
    section_path: List[str] = field(default_factory=list)

@dataclass
class DocumentACL:
    allow_users: List[str] = field(default_factory=list)
    deny_users: List[str] = field(default_factory=list)
    allow_roles: List[str] = field(default_factory=list)
    deny_roles: List[str] = field(default_factory=list)
    allow_departments: List[str] = field(default_factory=list)
    deny_departments: List[str] = field(default_factory=list)

    access_level: str = ""
    allowed_department_ids: List[str] = field(default_factory=list)
    include_sub_departments: bool = False
    allowed_org_roles: List[str] = field(default_factory=list)
    required_clearance: str = ""
    allowed_clearance_tags: List[str] = field(default_factory=list)
    allowed_user_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.access_level not in ("", "org_public", "department", "role_clearance", "personal_only"):
            raise ValidationError("Invalid access level")
        if not isinstance(self.include_sub_departments, bool) or not isinstance(self.required_clearance, str):
            raise ValidationError("Invalid ACL policy")
        for key, values in self.__dict__.items():
            if key in ("access_level", "include_sub_departments", "required_clearance"): continue
            if not isinstance(values,(list,tuple)) or not all(isinstance(v,str) and v for v in values):
                raise ValidationError("ACL grants and denials must be string sequences")

@dataclass
class KnowledgeRef:
    org_id: str
    doc_id: str
    version: int
    source_uri: str
    chunk_ids: List[str] = field(default_factory=list)
    excerpt: str = ""
    excerpt_hash: str = ""

@dataclass
class MaterialReceipt:
    status: str
    source_uri: str
    evidence_kind: str = "none"
    chunk_ids: List[str] = field(default_factory=list)
    reason_code: str = ""
    excerpt_hash: str = ""
    consumer_type: str = ""
    consumer_id: str = ""
    used_by_stage: str = ""

@dataclass(frozen=True)
class ExcerptPolicy:
    default_chars: int = 800
    enterprise_chars: int = 1600
    def __post_init__(self):
        if any(not isinstance(v,int) or isinstance(v,bool) or v<1 for v in (self.default_chars,self.enterprise_chars)): raise ValidationError("Invalid excerpt budget")

@dataclass
class SearchHit:
    doc_id: str
    version: int
    chunk_id: str
    title: str
    score: float
    excerpt: str
    excerpt_hash: str
    source_uri: str
    truncated: bool = False
    remaining_chars: int = 0
    partial_notice: str = ""
    masking_summary: str = ""
    highlights: List[List[int]] = field(default_factory=list)

@dataclass
class SearchResponse:
    hits: List[SearchHit] = field(default_factory=list)
    mode: str = "keyword"

@dataclass
class RetrieveResponse:
    doc_id: str
    version: int
    text: str
    offset: int
    limit: int
    total_chars: int
    truncated: bool
    next_offset: Optional[int]
    source_uri: str
    chunk_ids: List[str] = field(default_factory=list)

def _snake(name: str) -> str:
    import re
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class JsonContract:
    def to_dict(self, camel_case: bool = False) -> Dict[str, Any]:
        def convert(value):
            if isinstance(value, JsonContract): return value.to_dict(camel_case)
            if isinstance(value, (list, tuple)): return [convert(v) for v in value]
            return value
        def key(name):
            parts = name.split("_")
            return parts[0] + "".join(p.title() for p in parts[1:]) if camel_case else name
        return {key(k): convert(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if not isinstance(data, dict): raise ValidationError("Expected contract object")
        data = {_snake(k): v for k, v in data.items()}
        if cls is ConsumerBinding and isinstance(data.get("default_scope"), dict):
            data["default_scope"] = KnowledgeScope.from_dict(data["default_scope"])
        try: return cls(**data)
        except TypeError as exc: raise ValidationError("Invalid contract fields") from exc


@dataclass(frozen=True)
class KnowledgeScope(JsonContract):
    mode: str = "all_authorized"
    kb_ids: Tuple[str, ...] = ()
    space_types: Tuple[str, ...] = ()
    doc_ids: Tuple[str, ...] = ()

    def __post_init__(self):
        if self.mode not in ("all_authorized", "spaces", "documents"):
            raise ValidationError("Invalid scope mode")
        for key in ("kb_ids", "space_types", "doc_ids"):
            value = getattr(self, key)
            if not isinstance(value, (tuple, list)) or any(not isinstance(v, str) or not v for v in value):
                raise ValidationError("Invalid scope selectors")
            object.__setattr__(self, key, tuple(value))
        if any(t not in tuple(s.value for s in SpaceType) for t in self.space_types):
            raise ValidationError("Invalid scope space type")
        if (self.mode == "all_authorized" and (self.kb_ids or self.space_types or self.doc_ids)
            or self.mode == "spaces" and (self.doc_ids or not (self.kb_ids or self.space_types))
            or self.mode == "documents" and (self.kb_ids or self.space_types or not self.doc_ids)):
            raise ValidationError("Inconsistent scope selectors")

    def contains(self, document: Document, kb: KnowledgeBase) -> bool:
        if self.mode == "all_authorized": return True
        if self.mode == "documents": return document.doc_id in self.doc_ids
        return (not self.kb_ids or kb.kb_id in self.kb_ids) and (not self.space_types or kb.space_type in self.space_types)


@dataclass(frozen=True)
class ConsumerBinding(JsonContract):
    consumer_type: str
    consumer_id: str
    default_scope: KnowledgeScope = field(default_factory=KnowledgeScope)
    stage: str = ""

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (self.consumer_type, self.consumer_id)) or not isinstance(self.stage, str):
            raise ValidationError("Invalid consumer identity")
        if not isinstance(self.default_scope, KnowledgeScope): raise ValidationError("Invalid default scope")


@dataclass
class Attachment:
    reference: KnowledgeRef
    receipt: MaterialReceipt


@dataclass
class GeneratedAnswer:
    answer: str
    model_called: bool = False


@dataclass
class KnowledgeAnswer:
    answer: str = ""
    status: str = "refused"
    refusal_reason: str = "no_authorized_evidence"
    citations: List[KnowledgeRef] = field(default_factory=list)
    receipts: List[MaterialReceipt] = field(default_factory=list)
    evidence_hits: List[SearchHit] = field(default_factory=list)
    model_called: bool = False
    scope_applied: KnowledgeScope = field(default_factory=KnowledgeScope)
    binding_applied: Optional[ConsumerBinding] = None


# Tagged transport serialization avoids guessing model types or exposing pickle.
_MODELS = {c.__name__: c for c in (Actor, KnowledgeBase, Document, DocumentVersion, Chunk,
    DocumentACL, KnowledgeRef, MaterialReceipt, ExcerptPolicy, SearchHit, SearchResponse, RetrieveResponse, KnowledgeScope, ConsumerBinding, Attachment, GeneratedAnswer, KnowledgeAnswer)}
def encode(value):
    if type(value).__name__ in _MODELS:
        return {"__type__": type(value).__name__, **{k: encode(v) for k,v in value.__dict__.items()}}
    if isinstance(value, (list, tuple)): return [encode(v) for v in value]
    if isinstance(value, dict):
        if "__type__" in value:
            return {"__type__":"__mapping__","items":[[k,encode(v)] for k,v in value.items()]}
        return {k: encode(v) for k,v in value.items()}
    return value

def decode(value):
    if isinstance(value, list): return [decode(v) for v in value]
    if isinstance(value, dict):
        value = dict(value); kind = value.pop("__type__", None)
        if kind=="__mapping__": return {k:decode(v) for k,v in value["items"]}
        data = {k: decode(v) for k,v in value.items()}
        return _MODELS[kind](**data) if kind in _MODELS else data
    return value
