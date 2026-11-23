from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from ..exceptions import ValidationError

@dataclass(frozen=True)
class Actor:
    user_id: str
    org_id: str
    roles: Tuple[str, ...] = ()
    department_ids: Tuple[str, ...] = ()
    def __post_init__(self):
        if not isinstance(self.user_id,str) or not isinstance(self.org_id,str) or not self.user_id or not self.org_id:
            raise ValidationError("Actor requires user_id and org_id strings")
        for values in (self.roles,self.department_ids):
            if not isinstance(values,(list,tuple)) or not all(isinstance(v,str) for v in values):
                raise ValidationError("Actor role/department claims must be string sequences")

@dataclass
class KnowledgeBase:
    kb_id: str
    org_id: str
    name: str
    owner_id: str
    visibility: str = "private"

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

    def __post_init__(self):
        for values in self.__dict__.values():
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

# Tagged transport serialization avoids guessing model types or exposing pickle.
_MODELS = {c.__name__: c for c in (Actor, KnowledgeBase, Document, DocumentVersion, Chunk,
    DocumentACL, KnowledgeRef, MaterialReceipt, ExcerptPolicy, SearchHit, SearchResponse, RetrieveResponse)}
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
