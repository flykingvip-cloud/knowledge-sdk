from __future__ import annotations
import hmac
from .models import KnowledgeRef, MaterialReceipt
from .policy import Purpose, DecisionEffect
from .uri import parse_uri
from ..ingestion.fingerprint import normalize_text, sha256
from ..exceptions import TamperedExcerptError, PermissionDeniedError, NotFoundError, ValidationError

def validate_excerpt(ref,version,chunks,*,allow_combined=False):
    if not isinstance(ref,KnowledgeRef): raise ValidationError("Expected KnowledgeRef")
    identity=parse_uri(ref.source_uri)
    if identity[:3] != (ref.org_id,ref.doc_id,ref.version) or (identity[3] and identity[3] not in ref.chunk_ids):
        raise TamperedExcerptError("Reference identity mismatch")
    selected=[c for c in chunks if c.chunk_id in ref.chunk_ids]
    if len(set(ref.chunk_ids))!=len(selected): raise TamperedExcerptError("Unknown referenced chunk")
    if not hmac.compare_digest(sha256(ref.excerpt),ref.excerpt_hash): raise TamperedExcerptError("Excerpt digest mismatch")
    sources=[normalize_text(c.text) for c in selected] if ref.chunk_ids else [normalize_text(version.text)]
    if allow_combined and selected: sources.append(normalize_text("\n".join(c.text for c in selected)))
    if ref.excerpt and not any(ref.excerpt in text for text in sources): raise TamperedExcerptError("Excerpt not present in referenced source")
    return selected

def consume(client,actor,ref,*,agent=None,purpose=Purpose.READ,policy_context=None):
    if not isinstance(ref,KnowledgeRef): raise ValidationError("Expected KnowledgeRef")
    def result(status,kind="none",reason=""):
        return MaterialReceipt(status,ref.source_uri,kind,list(ref.chunk_ids),reason,ref.excerpt_hash)
    if actor.org_id!=ref.org_id: return result("denied",reason="cross_org")
    try:
        d,v,chunks,decision,_=client._delivered_source(actor,ref.doc_id,ref.version,agent=agent,purpose=purpose,policy_context=policy_context)
        if d.org_id!=ref.org_id: return result("denied",reason="cross_org")
        if d.archived and not (policy_context is not None and policy_context.include_archived):
            return result("unavailable",reason="archived")
        redacted=decision.effect == DecisionEffect.ALLOW_WITH_REDACTION
        if redacted and not ref.excerpt: return result("denied",reason="redacted_excerpt_required")
        try: validate_excerpt(ref,v,chunks,allow_combined=redacted)
        except TamperedExcerptError:
            if redacted: return result("denied",reason="redacted_excerpt_mismatch")
            raise
        partial=bool(ref.excerpt and ref.excerpt!=normalize_text(v.text)) or bool(ref.chunk_ids)
        return result("partial" if partial else "consumed","excerpt" if ref.excerpt else ("chunks" if ref.chunk_ids else "document"),"selected_material" if partial else "verified")
    except PermissionDeniedError as exc:
        reason=str(exc)
        if reason == "resource_archived": return result("unavailable",reason="archived")
        return result("denied",reason=reason if reason in ("redaction_hook_missing","redaction_failed","resource_revoked","lifecycle_not_published","outside_validity_window","retention_expired","external_llm_prohibited","export_prohibited","training_prohibited","purpose_not_permitted","agent_purpose_denied","agent_scope_denied","agent_clearance_exceeded","explicit_policy_deny") else "access_denied")
    except NotFoundError: return result("unavailable",reason="not_found")

def batch_consume(client,actor,refs,*,agent=None,purpose=Purpose.READ,policy_context=None):
    if len(refs)>100: raise ValidationError("At most 100 references per batch")
    return [consume(client,actor,ref,agent=agent,purpose=purpose,policy_context=policy_context) for ref in refs]
