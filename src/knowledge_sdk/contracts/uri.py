from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Optional
from urllib.parse import quote, unquote
from ..exceptions import ValidationError
from .anchors import identifier, integer
from .policy import PolicyContract

# Legacy parser deliberately retains its historical bare/chunk decoding contract.
_PATTERN = re.compile(r"^kb://org/([^/]+)/doc/([^/@]+)@([1-9][0-9]*)(?:#chunk=([^#]+))?$")
_SEGMENT = r"(?:[A-Za-z0-9._~-]|%[0-9A-Fa-f]{2})+"
_V2 = re.compile(r"^kb://org/("+_SEGMENT+r")/doc/("+_SEGMENT+r")@([1-9][0-9]*)(?:#(chunk|anchor)=("+_SEGMENT+r"))?$")


@dataclass(frozen=True)
class ParsedKBURI(PolicyContract):
    org_id: str
    doc_id: str
    version: int
    chunk_id: Optional[str] = None
    anchor_id: Optional[str] = None
    def __post_init__(self):
        identifier(self.org_id,'org_id'); identifier(self.doc_id,'doc_id'); integer(self.version,'version',1)
        if self.chunk_id is not None: identifier(self.chunk_id,'chunk_id')
        if self.anchor_id is not None: identifier(self.anchor_id,'anchor_id')
        if self.chunk_id is not None and self.anchor_id is not None: raise ValidationError('Conflicting URI selectors')


def build_uri(org_id,doc_id,version,chunk_id=None,*,anchor_id=None):
    identity=ParsedKBURI(org_id,doc_id,version,chunk_id if chunk_id else None,anchor_id)
    uri='kb://org/{}/doc/{}@{}'.format(quote(identity.org_id,safe=''),quote(identity.doc_id,safe=''),version)
    if identity.anchor_id is not None: return uri+'#anchor='+quote(identity.anchor_id,safe='')
    return uri+('#chunk='+quote(identity.chunk_id,safe='') if identity.chunk_id else '')


def parse_uri(uri):
    m=_PATTERN.fullmatch(uri)
    if not m: raise ValidationError('Invalid versioned URI')
    return unquote(m[1]),unquote(m[2]),int(m[3]),unquote(m[4]) if m[4] else None


def _decode(segment):
    try:
        decoded=unquote(segment,encoding='utf-8',errors='strict')
    except UnicodeError as exc:
        raise ValidationError('Invalid URI encoding') from exc
    # Canonical quoting rules remove aliases such as %41 for A. Hex case alone
    # is harmless and accepted. Identifiers are opaque, decoded exactly once.
    encoded=quote(decoded,safe='')
    normalize=lambda s: re.sub(r'%[0-9a-fA-F]{2}',lambda m:m[0].upper(),s)
    if normalize(encoded)!=normalize(segment): raise ValidationError('Noncanonical URI encoding')
    return decoded


def parse_uri_v2(uri):
    if not isinstance(uri,str): raise ValidationError('Invalid versioned URI')
    m=_V2.fullmatch(uri)
    if not m: raise ValidationError('Invalid versioned URI')
    value=_decode(m[5]) if m[5] else None
    return ParsedKBURI(_decode(m[1]),_decode(m[2]),int(m[3]),value if m[4]=='chunk' else None,value if m[4]=='anchor' else None)
