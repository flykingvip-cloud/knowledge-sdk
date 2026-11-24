"""Dependency-free layout extension; offsets always address unchanged full_text."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Optional, Protocol, Tuple
from ...contracts.anchors import (SelectorKind,PdfBBoxSelector,TableCellSelector,SectionQuoteSelector,
                                  selected,integer,string,strings,digest)
from ...contracts.policy import PolicyContract
from ...exceptions import ValidationError


@dataclass(frozen=True)
class ParsedSpan(PolicyContract):
    text: str
    start_offset: int
    end_offset: int
    selector_kind: SelectorKind
    pdf_bbox: Optional[PdfBBoxSelector] = None
    table_cell: Optional[TableCellSelector] = None
    section_quote: Optional[SectionQuoteSelector] = None
    def __post_init__(self):
        string(self.text,'span text');integer(self.start_offset,'start_offset');integer(self.end_offset,'end_offset')
        if self.end_offset-self.start_offset!=len(self.text): raise ValidationError('Span offsets do not match text')
        section=self.section_quote
        if self.selector_kind==SelectorKind.TEXT_OFFSET and section is None:
            section=SectionQuoteSelector((),digest(self.text),self.start_offset,self.end_offset)
        kind,values=selected(self.selector_kind,self.pdf_bbox,self.table_cell,section)
        object.__setattr__(self,'selector_kind',kind)
        for name,value in zip(('pdf_bbox','table_cell','section_quote'),values):object.__setattr__(self,name,value)
        if self.section_quote is not None and (self.section_quote.start_offset,self.section_quote.end_offset)!=(self.start_offset,self.end_offset):
            raise ValidationError('Section offsets do not match span')

    def to_dict(self):
        result=super().to_dict()
        for name in ('pdf_bbox','table_cell','section_quote'):
            value=getattr(self,name);result[name]=value.to_dict() if value is not None else None
        return result


@dataclass(frozen=True)
class LayoutParseResult(PolicyContract):
    full_text: str
    spans: Tuple[ParsedSpan,...]
    parser_id: str
    parser_version: str
    warnings: Tuple[str,...] = ()
    def __post_init__(self):
        string(self.full_text,'full_text');string(self.parser_id,'parser_id',True);string(self.parser_version,'parser_version',True)
        if not isinstance(self.spans,(list,tuple)):raise ValidationError('Invalid layout spans')
        spans=tuple(ParsedSpan.from_dict(s) if isinstance(s,dict) else replace(s) if isinstance(s,ParsedSpan) else s for s in self.spans)
        if any(not isinstance(s,ParsedSpan) or not 0<=s.start_offset<=s.end_offset<=len(self.full_text)
               or self.full_text[s.start_offset:s.end_offset]!=s.text for s in spans):
            raise ValidationError('Layout span does not match full_text')
        object.__setattr__(self,'spans',spans)
        object.__setattr__(self,'warnings',strings(self.warnings,'warnings'))

    def to_dict(self):
        result=super().to_dict();result['spans']=[span.to_dict() for span in self.spans];return result


class LayoutParser(Protocol):
    def parse_layout(self,data:bytes,filename:str='')->LayoutParseResult: ...


def text_layout(text,parser_id='legacy-text',parser_version='1.0'):
    import re
    string(text,'parser output')
    spans=[]
    for match in re.finditer(r'[^\r\n]+(?:\r?\n(?!\r?\n)[^\r\n]+)*',text):
        if match[0].strip():spans.append(ParsedSpan(match[0],match.start(),match.end(),SelectorKind.TEXT_OFFSET))
    return LayoutParseResult(text,tuple(spans),parser_id,parser_version)
