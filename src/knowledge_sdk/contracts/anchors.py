"""Precise, immutable evidence selectors; no parser/OCR dependency."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import math
from typing import Any, Dict, Optional, Tuple
from .policy import PolicyContract, enum_value, freeze_json
from ..exceptions import ValidationError


class SelectorKind(str, Enum):
    PDF_BBOX = 'pdf_bbox'
    TABLE_CELL = 'table_cell'
    SECTION_QUOTE = 'section_quote'
    TEXT_OFFSET = 'text_offset'


class ReanchorStatus(str, Enum):
    ANCHORED = 'anchored'
    DRIFT_PENDING = 'drift_pending'
    ORPHANED = 'orphaned'


def string(value, name, required=False):
    if not isinstance(value,str) or required and not value:
        raise ValidationError('Invalid ' + name)
    return value


def identifier(value, name):
    string(value,name,True)
    if not value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValidationError('Invalid ' + name)
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value<minimum: raise ValidationError('Invalid ' + name)
    return value


def strings(value, name):
    if not isinstance(value,(list,tuple)) or any(not isinstance(v,str) for v in value):
        raise ValidationError('Invalid ' + name)
    return tuple(value)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class TextQuoteSelector(PolicyContract):
    exact: str
    prefix: str = ''
    suffix: str = ''
    def __post_init__(self):
        # Preserve whitespace exactly; only the empty string is forbidden.
        string(self.exact,'exact',True); string(self.prefix,'prefix'); string(self.suffix,'suffix')


@dataclass(frozen=True)
class PdfBBoxSelector(PolicyContract):
    page_no: int
    x0: float
    y0: float
    x1: float
    y1: float
    def __post_init__(self):
        integer(self.page_no,'page_no',1)
        for name in ('x0','y0','x1','y1'):
            value=getattr(self,name)
            if type(value) not in (int,float) or not math.isfinite(value): raise ValidationError('Invalid bounding box')
        if not (0<=self.x0<=self.x1<=1 and 0<=self.y0<=self.y1<=1): raise ValidationError('Invalid bounding box')


@dataclass(frozen=True)
class TableCellSelector(PolicyContract):
    sheet_name: str = 'default'
    row_start: int = 1
    row_end: int = 1
    col_headers: Tuple[str,...] = ()
    cell_ref: str = ''
    unit_hint: str = ''
    def __post_init__(self):
        for name in ('sheet_name','cell_ref','unit_hint'): string(getattr(self,name),name)
        integer(self.row_start,'row_start',1); integer(self.row_end,'row_end',1)
        if self.row_end<self.row_start: raise ValidationError('Invalid table row range')
        object.__setattr__(self,'col_headers',strings(self.col_headers,'col_headers'))


@dataclass(frozen=True)
class SectionQuoteSelector(PolicyContract):
    section_path: Tuple[str,...] = ()
    paragraph_hash: str = ''
    start_offset: int = 0
    end_offset: int = 0
    def __post_init__(self):
        object.__setattr__(self,'section_path',strings(self.section_path,'section_path'))
        string(self.paragraph_hash,'paragraph_hash')
        integer(self.start_offset,'start_offset'); integer(self.end_offset,'end_offset')
        if self.end_offset<self.start_offset: raise ValidationError('Invalid text offsets')


def selected(kind,pdf_bbox,table_cell,section_quote):
    kind=enum_value(SelectorKind,kind)
    values=(pdf_bbox,table_cell,section_quote)
    classes=(PdfBBoxSelector,TableCellSelector,SectionQuoteSelector)
    normalized=[]
    for value,cls in zip(values,classes):
        if isinstance(value,dict): value=cls.from_dict(value)
        if value is not None and not isinstance(value,cls): raise ValidationError('Invalid selector')
        normalized.append(value)
    active=0 if kind==SelectorKind.PDF_BBOX else 1 if kind==SelectorKind.TABLE_CELL else 2
    if normalized[active] is None or any(v is not None for i,v in enumerate(normalized) if i!=active):
        raise ValidationError('Selector does not match kind')
    return kind,tuple(normalized)


@dataclass(frozen=True)
class EvidenceAnchor(PolicyContract):
    anchor_id: str
    org_id: str
    doc_id: str
    version: int
    selector_kind: SelectorKind
    quote: TextQuoteSelector
    quote_sha256: str
    pdf_bbox: Optional[PdfBBoxSelector] = None
    table_cell: Optional[TableCellSelector] = None
    section_quote: Optional[SectionQuoteSelector] = None
    reanchor_status: ReanchorStatus = ReanchorStatus.ANCHORED
    parent_anchor_id: Optional[str] = None
    parser_id: str = 'builtin'
    parser_version: str = '1.0'
    metadata: Dict[str,Any] = field(default_factory=dict)
    def __post_init__(self):
        for name in ('anchor_id','org_id','doc_id'): identifier(getattr(self,name),name)
        integer(self.version,'version',1)
        if isinstance(self.quote,dict): object.__setattr__(self,'quote',TextQuoteSelector.from_dict(self.quote))
        if not isinstance(self.quote,TextQuoteSelector): raise ValidationError('Invalid quote')
        if not isinstance(self.quote_sha256,str) or self.quote_sha256!=digest(self.quote.exact):
            raise ValidationError('Quote hash mismatch')
        kind,values=selected(self.selector_kind,self.pdf_bbox,self.table_cell,self.section_quote)
        object.__setattr__(self,'selector_kind',kind)
        for name,value in zip(('pdf_bbox','table_cell','section_quote'),values): object.__setattr__(self,name,value)
        object.__setattr__(self,'reanchor_status',enum_value(ReanchorStatus,self.reanchor_status))
        if self.parent_anchor_id is not None: identifier(self.parent_anchor_id,'parent_anchor_id')
        identifier(self.parser_id,'parser_id'); identifier(self.parser_version,'parser_version')
        if not isinstance(self.metadata,dict): raise ValidationError('Invalid anchor metadata')
        object.__setattr__(self,'metadata',freeze_json(self.metadata))

    def to_dict(self):
        # PolicyContract handles scalar enums/tuples; selectors need nested values.
        result=super().to_dict()
        for name in ('quote','pdf_bbox','table_cell','section_quote'):
            value=getattr(self,name); result[name]=value.to_dict() if value is not None else None
        return result
