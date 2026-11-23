from __future__ import annotations
import re
from ..contracts.models import ExcerptPolicy
from ..ingestion.fingerprint import normalize_text, sha256

def make_excerpt(text, policy=None, enterprise=False, allowed=True, query="", partial_notice="", masking_summary=""):
    policy=policy or ExcerptPolicy()
    if not allowed:
        return dict(excerpt="",excerpt_hash=sha256(""),truncated=False,remaining_chars=0,
                    highlights=[],partial_notice="",masking_summary="Access restricted")
    normalized=normalize_text(text); budget=policy.enterprise_chars if enterprise else policy.default_chars
    # Python slices operate on Unicode code points, never split a UTF-8 sequence.
    excerpt=normalized[:budget]; highlights=[]
    for token in set(re.findall(r"[^\W_]+",query,re.UNICODE)):
        highlights.extend([[m.start(),m.end()] for m in re.finditer(re.escape(token),excerpt,re.I)])
    return dict(excerpt=excerpt,excerpt_hash=sha256(excerpt),truncated=len(normalized)>budget,
                remaining_chars=max(0,len(normalized)-len(excerpt)),highlights=sorted(highlights),
                partial_notice=partial_notice,masking_summary=masking_summary)
