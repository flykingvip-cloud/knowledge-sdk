"""Immutable, dependency-free EvidencePack and deterministic sealing contracts."""
from __future__ import annotations
from dataclasses import dataclass, field, fields
from typing import Any, Dict, Tuple
import hashlib
import json
import re
from .uri import parse_uri_v2
from .policy import PolicyContract, Purpose, enum_value, freeze_json, sequence, text
from .anchors import integer
from ..exceptions import ValidationError

def plain(value):
    if isinstance(value,PolicyContract):return {f.name:plain(getattr(value,f.name)) for f in fields(value)}
    if isinstance(value,(list,tuple)):return [plain(v) for v in value]
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    return value.value if hasattr(value,'value') else value

def canonical(value):return json.dumps(plain(value),sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
def digest(pack):return hashlib.sha256(canonical({n:getattr(pack,n) for n in ('org_id','title','topic','items','dissent_notes','effective_decision')})).hexdigest()

@dataclass(frozen=True)
class PackItem(PolicyContract):
    source_uri: str
    doc_id: str
    version: int
    anchor_id: str = ''
    stance: str = 'supporting'
    condition_note: str = ''
    excerpt: str = ''
    excerpt_hash: str = ''
    masking_summary: str = ''
    receipt_id: str = ''
    def __post_init__(self):
        integer(self.version,'version',1)
        uri=parse_uri_v2(self.source_uri)
        if (uri.doc_id,uri.version,uri.anchor_id or '')!=(self.doc_id,self.version,self.anchor_id) or uri.chunk_id:raise ValidationError('Pack source identity mismatch')
        if self.excerpt_hash and not re.fullmatch('[0-9a-f]{64}',self.excerpt_hash):raise ValidationError('Invalid excerpt hash')
        if self.stance not in ('supporting','refuting','negative','conflict','contextual'):raise ValidationError('Invalid stance')
        for f in fields(self):
            if f.name!='version':text(getattr(self,f.name),f.name)
    def to_dict(self):return plain(self)

@dataclass(frozen=True)
class EvidencePack(PolicyContract):
    pack_id: str
    org_id: str
    title: str
    topic: str = ''
    created_by: str = ''
    status: str = 'sealed'
    purpose_bound: Purpose = Purpose.EXPORT
    effective_decision: Dict[str,Any] = field(default_factory=dict)
    items: Tuple[PackItem,...] = ()
    dissent_notes: Tuple[str,...] = ()
    pack_sha256: str = ''
    created_at: str = ''
    def __post_init__(self):
        for n in ('pack_id','org_id','title'):text(getattr(self,n),n,True)
        for n in ('topic','created_by','created_at','pack_sha256'):text(getattr(self,n),n)
        if not isinstance(self.effective_decision,dict):raise ValidationError('Decision metadata must be an object')
        if self.status not in ('draft','sealed','impacted','superseded'):raise ValidationError('Invalid pack status')
        object.__setattr__(self,'purpose_bound',enum_value(Purpose,self.purpose_bound))
        object.__setattr__(self,'items',tuple(PackItem.from_dict(i) if isinstance(i,dict) else i for i in self.items))
        if not self.items or any(not isinstance(i,PackItem) for i in self.items):raise ValidationError('Pack items required')
        object.__setattr__(self,'dissent_notes',sequence(self.dissent_notes,'dissent_notes'))
        object.__setattr__(self,'effective_decision',freeze_json(self.effective_decision))
    def to_dict(self):return plain(self)

@dataclass(frozen=True)
class PackVerificationReport(PolicyContract):
    pack_id: str
    digest_valid: bool
    status: str
    impact_alerts: Tuple[Any,...] = ()
    def __post_init__(self):object.__setattr__(self,'impact_alerts',tuple(self.impact_alerts))

@dataclass(frozen=True)
class ExportResult(PolicyContract):
    pack_id: str
    format: str
    content: str
    media_type: str
    encoding: str = 'utf-8'
    output_path: str = ''
    sha256: str = ''
