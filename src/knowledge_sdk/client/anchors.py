"""Detached anchor delivery views. Never persist a masked view as authority."""
from __future__ import annotations
from dataclasses import replace
from ..contracts.anchors import TextQuoteSelector,ReanchorStatus,EvidenceAnchor,digest
from ..contracts.policy import DecisionEffect
from ..exceptions import PermissionDeniedError,ValidationError


def validate_identity(anchor,org_id,doc_id,version,anchor_id=None):
    if (not isinstance(anchor,EvidenceAnchor) or (anchor.org_id,anchor.doc_id,anchor.version)!=(org_id,doc_id,version)
        or (anchor_id is not None and anchor.anchor_id!=anchor_id)):
        raise PermissionDeniedError('anchor_identity_mismatch')


def validate_source(anchor,version):
    start,end=anchor.metadata.get('candidate_start'),anchor.metadata.get('candidate_end')
    if (anchor.metadata.get('candidate_verified') is not True or type(start) is not int or type(end) is not int
        or not 0<=start<=end<=len(version.text) or version.text[start:end]!=anchor.quote.exact
        or digest(anchor.quote.exact)!=anchor.quote_sha256):
        raise PermissionDeniedError('anchor_candidate_invalid')


def deliver(client,anchor,decision,purpose):
    if decision.effect!=DecisionEffect.ALLOW_WITH_REDACTION:return anchor
    def mask(value):return client.redaction_registry.apply(value,decision.redaction_profile,purpose,{'doc_id':anchor.doc_id,'version':anchor.version})[0]
    try:
        quote=TextQuoteSelector(mask(anchor.quote.exact),mask(anchor.quote.prefix),mask(anchor.quote.suffix))
        table=anchor.table_cell
        if table:table=replace(table,sheet_name=mask(table.sheet_name),col_headers=tuple(mask(x) for x in table.col_headers),cell_ref=mask(table.cell_ref),unit_hint=mask(table.unit_hint))
        section=anchor.section_quote
        if section:section=replace(section,section_path=tuple(mask(x) for x in section.section_path),paragraph_hash='')
        # Metadata keys and values may both be arbitrary content. Omit the
        # entire source metadata on a masked view, rather than leak a sidecar.
        return replace(anchor,quote=quote,quote_sha256=digest(quote.exact),table_cell=table,section_quote=section,
                       parser_id=mask(anchor.parser_id) or 'redacted',parser_version=mask(anchor.parser_version) or 'redacted',metadata={'delivery_view':'redacted'})
    except ValidationError:raise PermissionDeniedError('redaction_failed') from None
