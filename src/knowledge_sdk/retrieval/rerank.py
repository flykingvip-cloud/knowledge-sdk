"""Opt-in scoring of authorized, redacted, bounded summaries only."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import Counter
from collections.abc import Sequence as RuntimeSequence
from typing import Protocol, Sequence
import math
from ..exceptions import ValidationError


def finite(value, name='score'):
    try:
        if type(value) not in (int, float) or not math.isfinite(value):raise ValueError()
        return float(value)
    except (ValueError,OverflowError):raise ValidationError('Invalid '+name) from None


def identifier(value):
    if not isinstance(value, str) or not value or len(value)>256:
        raise ValidationError('Invalid strategy identifier')
    return value


@dataclass(frozen=True)
class RerankCandidate:
    doc_id: str
    version: int
    chunk_id: str
    title: str
    excerpt: str
    source_uri: str
    base_score: float
    rank: int
    redacted: bool = False

    def __post_init__(self):
        for v in (self.doc_id, self.chunk_id, self.source_uri):
            if not isinstance(v,str) or not v: raise ValidationError('Invalid candidate identity')
        if any(type(v) is not int or v<1 for v in (self.version,self.rank)):
            raise ValidationError('Invalid candidate version/rank')
        if not isinstance(self.title,str) or len(self.title)>2000 or not isinstance(self.excerpt,str) or len(self.excerpt)>32000:
            raise ValidationError('Invalid bounded candidate text')
        object.__setattr__(self,'base_score',finite(self.base_score))
        if type(self.redacted) is not bool: raise ValidationError('Invalid redaction flag')

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict): raise ValidationError('Invalid candidate')
        try: return cls(**data)
        except TypeError as exc: raise ValidationError('Invalid candidate fields') from exc


class Reranker(Protocol):
    reranker_id: str
    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> Sequence[float]: ...


def apply_reranker(query,candidates,reranker):
    identifier(getattr(reranker,'reranker_id',None))
    candidates=tuple(candidates)
    if any(not isinstance(c,RerankCandidate) for c in candidates):raise ValidationError('Invalid candidates')
    if not candidates: return ()  # no callable/model invocation on empty input
    try:
        raw=reranker.score(query,candidates)
        if not isinstance(raw,RuntimeSequence) or isinstance(raw,(str,bytes,bytearray)) or len(raw)!=len(candidates):raise ValueError()
        values=tuple(raw)
    except Exception as exc: raise ValidationError('Reranker failed') from None
    if len(values)!=len(candidates) or any(type(v) is not float or not math.isfinite(v) for v in values):
        raise ValidationError('Invalid reranker scores')
    return values


@dataclass(frozen=True)
class DeterministicLexicalReranker:
    coverage_weight: float = .50
    title_weight: float = .18
    proximity_weight: float = .22
    saturation_weight: float = .09
    rank_prior_weight: float = .01
    reranker_id: str = 'lexical-v1'

    def __post_init__(self):
        identifier(self.reranker_id)
        weights=tuple(finite(getattr(self,k),'weight') for k in ('coverage_weight','title_weight','proximity_weight','saturation_weight','rank_prior_weight'))
        if any(w<0 or w>1 for w in weights) or not math.isclose(sum(weights),1.0,abs_tol=1e-9) or self.rank_prior_weight>.05:
            raise ValidationError('Weights must sum to one with a small rank prior')

    def score(self,query,candidates):
        from ..storage.sqlite_store import tokens
        q=tuple(dict.fromkeys(tokens(query))); wanted=set(q)
        phrase=' '.join(query.casefold().split())
        result=[]
        for c in candidates:
            title=tokens(c.title); body=tokens(c.excerpt); count=Counter(title+body)
            cover=len(wanted.intersection(count))/len(wanted) if wanted else 0.0
            title_cover=len(wanted.intersection(title))/len(wanted) if wanted else 0.0
            # Exact normalized phrase plus shortest ordered query-token window.
            joined=' '.join((c.title+' '+c.excerpt).casefold().split())
            proximity=1.0 if phrase and phrase in joined else 0.0
            positions=[i for i,t in enumerate(title+body) if t in wanted]
            if positions and len(wanted)>1 and cover==1:
                span=positions[-1]-positions[0]+1
                proximity=max(proximity,min(1.0,len(wanted)/span)*.5)
            density=sum(count[t]/(count[t]+1.0) for t in wanted)/len(wanted) if wanted else 0.0
            density*=min(1.0, max(1,len(wanted))*8/max(1,len(title)+len(body)))
            value=(self.coverage_weight*cover+self.title_weight*title_cover+self.proximity_weight*proximity+
                   self.saturation_weight*density+self.rank_prior_weight/c.rank)
            result.append(float(value))
        return tuple(result)
