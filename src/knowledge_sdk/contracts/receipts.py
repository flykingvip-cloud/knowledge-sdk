from __future__ import annotations
import hmac
from .models import KnowledgeRef, MaterialReceipt
from .uri import parse_uri
from ..ingestion.fingerprint import normalize_text, sha256
from ..exceptions import TamperedExcerptError, PermissionDeniedError, NotFoundError, ValidationError

def validate_excerpt(ref,version,chunks):
    if not isinstance(ref,KnowledgeRef): raise ValidationError("Expected KnowledgeRef")
    identity=parse_uri(ref.source_uri)
    if identity[:3] != (ref.org_id,ref.doc_id,ref.version) or (identity[3] and identity[3] not in ref.chunk_ids):
        raise TamperedExcerptError("Reference identity mismatch")
    selected=[c for c in chunks if c.chunk_id in ref.chunk_ids]
    if len(set(ref.chunk_ids))!=len(selected): raise TamperedExcerptError("Unknown referenced chunk")
    if not hmac.compare_digest(sha256(ref.excerpt),ref.excerpt_hash): raise TamperedExcerptError("Excerpt digest mismatch")
    sources=[normalize_text(c.text) for c in selected] if ref.chunk_ids else [normalize_text(version.text)]
    if ref.excerpt and not any(ref.excerpt in text for text in sources): raise TamperedExcerptError("Excerpt not present in referenced source")
    return selected

def consume(client,actor,ref):
    if not isinstance(ref,KnowledgeRef): raise ValidationError("Expected KnowledgeRef")
    def result(status,kind="none",reason=""):
        return MaterialReceipt(status,ref.source_uri,kind,list(ref.chunk_ids),reason,ref.excerpt_hash)
    if actor.org_id!=ref.org_id: return result("denied",reason="cross_org")
    try:
        d=client._read(actor,ref.doc_id,include_archived=True)
        if d.org_id!=ref.org_id: return result("denied",reason="cross_org")
        if d.archived: return result("unavailable",reason="archived")
        v=client.store.get_version(ref.doc_id,ref.version)
        validate_excerpt(ref,v,client.store.get_chunks(ref.doc_id,ref.version))
        partial=bool(ref.excerpt and ref.excerpt!=normalize_text(v.text)) or bool(ref.chunk_ids)
        return result("partial" if partial else "consumed","excerpt" if ref.excerpt else ("chunks" if ref.chunk_ids else "document"),"selected_material" if partial else "verified")
    except PermissionDeniedError: return result("denied",reason="access_denied")
    except NotFoundError: return result("unavailable",reason="not_found")

def batch_consume(client,actor,refs):
    if len(refs)>100: raise ValidationError("At most 100 references per batch")
    return [consume(client,actor,ref) for ref in refs]
