from __future__ import annotations
import re
from urllib.parse import quote, unquote
from ..exceptions import ValidationError
_PATTERN = re.compile(r"^kb://org/([^/]+)/doc/([^/@]+)@([1-9][0-9]*)(?:#chunk=([^#]+))?$")
def build_uri(org_id, doc_id, version, chunk_id=None):
    if not org_id or not doc_id or not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValidationError("Invalid reference identity")
    uri = "kb://org/{}/doc/{}@{}".format(quote(org_id, safe=""), quote(doc_id, safe=""), version)
    return uri + ("#chunk=" + quote(chunk_id, safe="") if chunk_id else "")
def parse_uri(uri):
    m = _PATTERN.fullmatch(uri)
    if not m: raise ValidationError("Invalid versioned URI")
    return (unquote(m[1]), unquote(m[2]), int(m[3]), unquote(m[4]) if m[4] else None)
