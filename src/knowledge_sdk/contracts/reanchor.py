"""Pure conservative reanchoring. Ambiguity never becomes an automatic grant."""
from __future__ import annotations
from dataclasses import replace
import json
from typing import List, Sequence
from .anchors import (EvidenceAnchor,TextQuoteSelector,SectionQuoteSelector,SelectorKind,
                      ReanchorStatus,digest,identifier,integer)
from ..ingestion.parsers.layout import LayoutParseResult
from ..exceptions import ValidationError


def _layout(layout):
    if not isinstance(layout,LayoutParseResult):raise ValidationError('Expected LayoutParseResult')
    return LayoutParseResult(layout.full_text,layout.spans,layout.parser_id,layout.parser_version,layout.warnings)


def _quote(text,start,end):
    return TextQuoteSelector(text[start:end],text[max(0,start-48):start],text[end:end+48])


def build_anchors_from_layout(org_id,doc_id,version,layout)->List[EvidenceAnchor]:
    identifier(org_id,'org_id');identifier(doc_id,'doc_id');integer(version,'version',1);layout=_layout(layout)
    result=[]
    for index,span in enumerate(layout.spans):
        if not span.text:continue
        payload=json.dumps([org_id,doc_id,version,index,span.start_offset,span.end_offset,span.selector_kind.value,digest(span.text)],ensure_ascii=False,separators=(',',':'))
        anchor_id=digest(payload)[:32]
        result.append(EvidenceAnchor(anchor_id,org_id,doc_id,version,span.selector_kind,
            _quote(layout.full_text,span.start_offset,span.end_offset),digest(span.text),span.pdf_bbox,span.table_cell,span.section_quote,
            parser_id=layout.parser_id,parser_version=layout.parser_version,
            metadata={'candidate_start':span.start_offset,'candidate_end':span.end_offset,'candidate_verified':True,'span_index':index}))
    return result


def _occurrences(text,quote):
    # Two matches are enough to prove ambiguity; no unbounded candidate list.
    first=text.find(quote)
    if first<0:return ()
    second=text.find(quote,first+1)
    return (first,) if second<0 else (first,second)


def _consistent(old,span,unique_span):
    if old.selector_kind!=span.selector_kind:return False
    if old.selector_kind==SelectorKind.TABLE_CELL:return old.table_cell.col_headers==span.table_cell.col_headers
    if old.selector_kind==SelectorKind.SECTION_QUOTE:return old.section_quote.section_path==span.section_quote.section_path
    if old.selector_kind==SelectorKind.PDF_BBOX:
        a,b=old.pdf_bbox,span.pdf_bbox
        overlap=min(a.x1,b.x1)>max(a.x0,b.x0) and min(a.y1,b.y1)>max(a.y0,b.y0)
        return a.page_no==b.page_no and (overlap or unique_span)
    return True


def reanchor_to_version(old_anchors:Sequence[EvidenceAnchor],new_version:int,new_layout)->List[EvidenceAnchor]:
    integer(new_version,'new_version',1);layout=_layout(new_layout)
    if not isinstance(old_anchors,(list,tuple)) or any(not isinstance(a,EvidenceAnchor) for a in old_anchors):raise ValidationError('Invalid old anchors')
    if len({(a.org_id,a.doc_id) for a in old_anchors})>1 or len({a.anchor_id for a in old_anchors})!=len(old_anchors):
        raise ValidationError('Mixed or duplicate anchor lineage')
    result=[]
    for old in old_anchors:
        if new_version<=old.version:raise ValidationError('Reanchor version must increase')
        positions=_occurrences(layout.full_text,old.quote.exact)
        meta=dict(old.metadata);meta['source_version']=old.version
        if not positions:
            meta.update(candidate_verified=False,reanchor_reason='quote_missing')
            result.append(replace(old,version=new_version,parent_anchor_id=old.anchor_id,reanchor_status=ReanchorStatus.ORPHANED,
                                  parser_id=layout.parser_id,parser_version=layout.parser_version,metadata=meta))
            continue
        # Deterministic proposal: prefer strongest matching surrounding context
        # among the first two occurrences. Multiple matches ALWAYS stay pending.
        def context_score(pos):
            return (bool(old.quote.prefix) and layout.full_text[max(0,pos-len(old.quote.prefix)):pos]==old.quote.prefix)+(bool(old.quote.suffix) and layout.full_text[pos+len(old.quote.exact):pos+len(old.quote.exact)+len(old.quote.suffix)]==old.quote.suffix)
        start=max(positions,key=lambda p:(context_score(p),-p));end=start+len(old.quote.exact)
        matches=[(i,s) for i,s in enumerate(layout.spans) if s.start_offset<=start and end<=s.end_offset and s.selector_kind==old.selector_kind]
        verified=len(matches)==1;span=matches[0][1] if verified else None
        consistent=verified and _consistent(old,span,True)
        anchored=len(positions)==1 and consistent and old.reanchor_status==ReanchorStatus.ANCHORED
        status=ReanchorStatus.ANCHORED if anchored else ReanchorStatus.DRIFT_PENDING
        meta.update(candidate_start=start,candidate_end=end,candidate_verified=verified,
                    reanchor_reason='exact_unique' if anchored else 'ambiguous_quote' if len(positions)>1 else 'structure_changed' if not consistent else 'previously_unconfirmed')
        if verified:meta['span_index']=matches[0][0]
        selector=span.section_quote if verified else old.section_quote
        if selector is not None and verified:selector=replace(selector,start_offset=start,end_offset=end,paragraph_hash=digest(span.text))
        result.append(replace(old,version=new_version,parent_anchor_id=old.anchor_id,quote=_quote(layout.full_text,start,end),
                              reanchor_status=status,pdf_bbox=span.pdf_bbox if verified else old.pdf_bbox,
                              table_cell=span.table_cell if verified else old.table_cell,section_quote=selector,
                              parser_id=layout.parser_id,parser_version=layout.parser_version,metadata=meta))
    return result


def merge_anchors_for_version(org_id,doc_id,version,layout,old_anchors=()):
    """Keep all old identities/statuses; add only genuinely independent spans."""
    if not old_anchors:return build_anchors_from_layout(org_id,doc_id,version,layout)
    updated=reanchor_to_version(old_anchors,version,layout)
    if any((a.org_id,a.doc_id)!=(org_id,doc_id) for a in old_anchors):raise ValidationError('Anchor tenant mismatch')
    ids={a.anchor_id for a in updated};quotes={a.quote.exact for a in old_anchors}
    for fresh in build_anchors_from_layout(org_id,doc_id,version,layout):
        start,end=fresh.metadata['candidate_start'],fresh.metadata['candidate_end']
        # Suppress every duplicated/contained candidate, not only the proposed
        # occurrence, so a new id cannot launder an unconfirmed old anchor.
        if fresh.quote.exact in quotes or any(q in fresh.quote.exact for q in quotes):continue
        if any(a.reanchor_status!=ReanchorStatus.ORPHANED and a.metadata.get('candidate_start',end)<end and
               a.metadata.get('candidate_end',start)>start for a in updated):continue
        if fresh.anchor_id in ids:raise ValidationError('Anchor identity collision')
        updated.append(fresh);ids.add(fresh.anchor_id)
    return updated
